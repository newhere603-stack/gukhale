import os
import random
import string
import io
import logging
import html
import asyncio
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.error import BadRequest

from shivu import application, user_collection, db
from shivu.modules.words_data_full_az import WORD_LIST

LOGGER = logging.getLogger(__name__)

# --- MONGODB COLLECTIONS FOR PERSISTENCE ---
grid_games_col = db['grid_games']
grid_settings_col = db['grid_settings']

# Game State & Settings Storage
active_games = {}
chat_settings = {}  
stop_votes = {}  
LOG_GROUP_ID = -1003893927065  

DB_LOADED = False

# SUPERFAST OPTIMIZATION: Font Cache System 🚀
_FONT_CACHE = {}
# SUPERFAST OPTIMIZATION: Leaderboard Cache System 🚀
LB_CACHE = {}
LB_CACHE_TTL = 10  # Seconds

async def ensure_db_loaded():
    global DB_LOADED
    if not DB_LOADED:
        try:
            # 🚀 Create Index for Lightning Fast Leaderboard queries
            try:
                await user_collection.create_index([("grid_points", -1)], background=True)
            except Exception:
                pass

            async for game in grid_games_col.find({}):
                active_games[game['_id']] = game['game_data']
                
            async for setting in grid_settings_col.find({}):
                chat_settings[setting['_id']] = setting['settings']
                
            DB_LOADED = True
            LOGGER.info("WordGrid DB State Loaded Successfully!")
        except Exception as e:
            LOGGER.error(f"Error loading WordGrid state from DB: {e}")

# ==========================================
# 🚀 ZERO-LAG CACHED FONT LOADER
# ==========================================
def get_bold_font(size):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
        
    font_paths = [
        "Roboto-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _FONT_CACHE[size] = font  
                return font
            except:
                pass
                
    font = ImageFont.load_default()
    _FONT_CACHE[size] = font
    return font

def get_chat_settings(chat_id):
    if chat_id not in chat_settings:
        chat_settings[chat_id] = {"pin": True, "mark_words": True, "theme": "automatic"}
    return chat_settings[chat_id]

def is_night_ist():
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return not (6 <= ist_now.hour < 18)

# ==========================================
# 🧠 SMART WORD PICKER
# ==========================================
def generate_game_grid(mode="normal"):
    if mode == "easy":
        size = 6
        target_lengths = [3, 3, 4, 4, 5, 5]
    elif mode == "hard":
        size = 10
        target_lengths = [4, 4, 5, 5, 5, 6, 6, 6, 7, 7, 7, 7]
    else:
        size = 8
        target_lengths = [3, 3, 4, 4, 5, 5, 6, 6, 7]

    grid = [['' for _ in range(size)] for _ in range(size)]
    chosen_words = []
    
    for length in target_lengths:
        pool = [w for w in WORD_LIST if len(w) == length and w not in chosen_words]
        if not pool: 
            pool = [w for w in WORD_LIST if w not in chosen_words]
        if pool:
            chosen_words.append(random.choice(pool))
            
    placed_words = {}
    directions = [(0, 1), (1, 0), (1, 1), (-1, 1), (-1, -1), (0, -1), (-1, 0), (1, -1)] 
    
    for word in chosen_words:
        placed = False
        for _ in range(300):
            d_r, d_c = random.choice(directions)
            r, c = random.randint(0, size - 1), random.randint(0, size - 1)
            
            if 0 <= r + d_r * (len(word)-1) < size and 0 <= c + d_c * (len(word)-1) < size:
                if all(grid[r + d_r * i][c + d_c * i] in ['', word[i]] for i in range(len(word))):
                    for i in range(len(word)): 
                        grid[r + d_r * i][c + d_c * i] = word[i]
                    placed_words[word] = [(r + d_r * i, c + d_c * i) for i in range(len(word))]
                    placed = True
                    break
        if not placed:
            continue

    for r in range(size):
        for c in range(size):
            if grid[r][c] == '':
                grid[r][c] = random.choice(string.ascii_uppercase)
                
    return grid, placed_words

def create_grid_image(grid, placed_words, found_words, chat_id):
    settings = get_chat_settings(chat_id)
    theme = settings["theme"]
    mark_words = settings["mark_words"]

    if theme == "automatic":
        is_dark = is_night_ist()
    else:
        is_dark = (theme == "black")

    bg_color = "#0a0a0a" if is_dark else "#ffffff"
    line_color = "#222222" if is_dark else "#cccccc"
    text_color = "#ffffff" if is_dark else "#000000"

    cell_size = 100
    size = len(grid)
    img_size = cell_size * size
    
    img = Image.new('RGBA', (img_size, img_size), color=bg_color) 
    draw = ImageDraw.Draw(img)
    font = get_bold_font(50)

    for r in range(size + 1):
        draw.line([(0, r*cell_size), (img_size, r*cell_size)], fill=line_color, width=3)
        draw.line([(r*cell_size, 0), (r*cell_size, img_size)], fill=line_color, width=3)

    if mark_words:
        colors = [
            (60, 150, 120, 180), (180, 70, 70, 180), (60, 150, 60, 180), 
            (130, 90, 180, 180), (180, 140, 50, 180), (60, 100, 200, 180)
        ]
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        for i, word in enumerate(found_words):
            if word in placed_words:
                coords = placed_words[word]
                c1, r1 = coords[0][1] * cell_size + cell_size // 2, coords[0][0] * cell_size + cell_size // 2
                c2, r2 = coords[-1][1] * cell_size + cell_size // 2, coords[-1][0] * cell_size + cell_size // 2
                
                color = colors[i % len(colors)]
                line_width = 50 
                radius = line_width // 2
                
                overlay_draw.line([(c1, r1), (c2, r2)], fill=color, width=line_width)
                overlay_draw.ellipse([c1 - radius, r1 - radius, c1 + radius, r1 + radius], fill=color)
                overlay_draw.ellipse([c2 - radius, r2 - radius, c2 + radius, r2 + radius], fill=color)

        img = Image.alpha_composite(img, overlay)
        
    draw = ImageDraw.Draw(img)

    for r in range(size):
        for c in range(size):
            x0, y0 = c * cell_size, r * cell_size
            letter = grid[r][c]
            
            try:
                bbox = font.getbbox(letter)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                text_x = x0 + (cell_size - w) / 2 - bbox[0]
                text_y = y0 + (cell_size - h) / 2 - bbox[1]
            except AttributeError:
                w, h = font.getsize(letter)
                text_x = x0 + (cell_size - w) / 2
                text_y = y0 + (cell_size - h) / 2

            draw.text((text_x, text_y), letter, fill=text_color, font=font)

    img = img.convert("RGB")
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.name = 'grid.png'
    return bio

def get_sorted_caption(placed_words, found_words):
    caption = "<tg-emoji emoji-id=\"5224450179368767019\">🌎</tg-emoji> <b>WORD GRID CHALLENGE</b> <tg-emoji emoji-id=\"5224450179368767019\">🌎</tg-emoji>\n\n<b>Find these words:</b>\n"
    sorted_words = sorted(placed_words.keys(), key=len)
    
    for w in sorted_words:
        if w in found_words:
            caption += f"<tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji> <code>{w}</code>\n"
        else:
            masked = w[0] + "".join("-" for _ in range(len(w) - 1))
            caption += f"<code>{masked}({len(w)})</code>\n"
            
    caption += "\n<b>Tap <tg-emoji emoji-id=\"5260491539167073671\">🔄</tg-emoji> Refresh Grid to mark!</b>"
    return caption

def get_msg_link(chat, msg_id):
    if chat.username:
        return f"https://t.me/{chat.username}/{msg_id}"
    else:
        return f"https://t.me/c/{str(chat.id).replace('-100', '', 1)}/{msg_id}"

async def is_admin(chat, user_id, bot):
    if chat.type == 'private':
        return True
    member = await bot.get_chat_member(chat.id, user_id)
    return member.status in ['administrator', 'creator']

# --- HANDLERS ---
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_db_loaded() 
    chat = update.effective_chat
    if not chat or chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("<b>This game can only be played in groups!</b>", parse_mode="HTML")
        return

    chat_id = chat.id
    if chat_id in active_games:
        game_data = active_games[chat_id]
        reply_markup = None
        if game_data.get("msg_id"):
            link = get_msg_link(chat, game_data["msg_id"])
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("ɢᴏ ᴛᴏ ɢʀɪᴅ ⤻", url=link)]])
            
        await update.message.reply_text(
            "<tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> <b>A WordGrid game is already running! Use /stopgame or /endgrid to end it.</b>",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        return

    cmd = update.message.text.split('@')[0].lower()
    mode = "easy" if 'easy' in cmd else "hard" if 'hard' in cmd else "normal"

    grid, placed_words = generate_game_grid(mode=mode)
    stop_votes.pop(chat_id, None) 
    
    active_games[chat_id] = {
        "grid": grid, 
        "words": placed_words, 
        "found": [], 
        "msg_id": None, 
        "round_scores": {},
        "mode": mode
    }

    img_bio = await asyncio.to_thread(create_grid_image, grid, placed_words, [], chat_id)
    img_bio.seek(0)

    caption = get_sorted_caption(placed_words, [])
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("ʀᴇꜰʀᴇsʜ ɢʀɪᴅ", callback_data="refresh_grid")]])
    
    msg = await context.bot.send_photo(chat_id=chat_id, photo=img_bio, caption=caption, parse_mode="HTML", reply_markup=btn)
    
    active_games[chat_id]["msg_id"] = msg.message_id
    await grid_games_col.update_one({'_id': chat_id}, {'$set': {'game_data': active_games[chat_id]}}, upsert=True)

    settings = get_chat_settings(chat_id)
    if settings["pin"]:
        try:
            await context.bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id)
        except Exception:
            pass
            
    try:
        group_name = html.escape(chat.title)
        game_link = get_msg_link(chat, msg.message_id)
        words_list = " ".join([w.capitalize() for w in placed_words.keys()])
        log_text = (
            f"🎮 <b>New WordGrid Game Started!</b>\n\n"
            f"🏢 <b>Group:</b> <a href='{game_link}'>{group_name}</a>\n"
            f"🆔 <b>Group ID:</b> <code>{chat_id}</code>\n"
            f"🎚 <b>Mode:</b> {mode.capitalize()} (Total {len(placed_words)} words)\n\n"
            f"📝 <b>Words to guess:</b>\n<code>{words_list}</code>"
        )
        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        pass

async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_db_loaded() 
    chat = update.effective_chat
    user = update.effective_user
    
    if not chat or chat.type not in ["group", "supergroup"]:
        return
        
    chat_id = chat.id
    if chat_id not in active_games:
        await update.message.reply_text("<b><tg-emoji emoji-id=\"6309717264639726942\">⚠️</tg-emoji> No active game running right now.</b>", parse_mode="HTML")
        return

    is_adm = await is_admin(chat, user.id, context.bot)
    
    if is_adm:
        del active_games[chat_id]
        stop_votes.pop(chat_id, None)
        await grid_games_col.delete_one({'_id': chat_id})
        await update.message.reply_text("<tg-emoji emoji-id=\"5465626908165163181\">✅</tg-emoji> <b>The active game has been stopped by an admin. Start another with /grid_hard or /grid</b>", parse_mode="HTML")
    else:
        if chat_id not in stop_votes:
            stop_votes[chat_id] = set()
        stop_votes[chat_id].add(user.id)
        votes_needed = 3
        current_votes = len(stop_votes[chat_id])
        
        if current_votes >= votes_needed:
            del active_games[chat_id]
            stop_votes.pop(chat_id, None)
            await grid_games_col.delete_one({'_id': chat_id})
            await update.message.reply_text("<tg-emoji emoji-id=\"5465626908165163181\">✅</tg-emoji> <b>The active game has been stopped by community vote (3/3). Start another with /grid_hard or /grid</b>", parse_mode="HTML")
        else:
            btn = InlineKeyboardMarkup([[InlineKeyboardButton(f"Vote to Stop ({current_votes}/{votes_needed})", callback_data="wg_vote_stop")]])
            text = f"<b>🛑 {html.escape(user.first_name)} wants to stop the game.</b>\n\nNon-admins need <b>{votes_needed} votes</b> to stop the game. \n\nClick below to vote!"
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=btn)

async def vote_stop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_db_loaded() 
    query = update.callback_query
    chat_id = query.message.chat_id
    user = update.effective_user
    
    if chat_id not in active_games:
        await query.answer("No active game running!", show_alert=True)
        try:
            await query.message.delete()
        except Exception:
            pass
        return
        
    if chat_id not in stop_votes:
        stop_votes[chat_id] = set()
        
    if user.id in stop_votes[chat_id]:
        await query.answer("You have already voted to stop the game!", show_alert=True)
        return
        
    stop_votes[chat_id].add(user.id)
    votes_needed = 3
    current_votes = len(stop_votes[chat_id])
    
    if current_votes >= votes_needed:
        del active_games[chat_id]
        stop_votes.pop(chat_id, None)
        await grid_games_col.delete_one({'_id': chat_id})
        await query.answer("Game stopped by vote!", show_alert=True)
        await query.edit_message_text("<tg-emoji emoji-id=\"5465626908165163181\">✅</tg-emoji> <b>The active game has been stopped by community vote (3/3). Start another with /grid_hard or /grid</b>", parse_mode="HTML")
    else:
        await query.answer("Vote registered!")
        btn = InlineKeyboardMarkup([[InlineKeyboardButton(f"Vote to Stop ({current_votes}/{votes_needed})", callback_data="wg_vote_stop")]])
        text = f"<b>🛑 Vote to stop the game in progress!</b>\n\nNon-admins need <b>{votes_needed} votes</b> to stop the game.\n\nCurrent Votes: <b>{current_votes}/{votes_needed}</b>"
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=btn)

def calculate_points(mode, is_first, is_last):
    if mode == "easy": return 5  
    elif mode == "normal": return 6 if (is_first or is_last) else 4  
    elif mode == "hard": return 5 if (is_first or is_last) else 4  
    return 4

async def handle_guesses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_db_loaded() 
    chat = update.effective_chat
    if not chat or chat.type not in ["group", "supergroup"]:
        return
    
    chat_id = chat.id
    if chat_id not in active_games:
        return

    message = update.effective_message
    if not message or not message.text:
        return

    game = active_games[chat_id]
    guess = message.text.upper().strip()

    if guess in game["words"] and guess not in game["found"]:
        is_first = len(game["found"]) == 0
        is_last = len(game["found"]) == len(game["words"]) - 1
        points = calculate_points(game["mode"], is_first, is_last)
        
        game["found"].append(guess)
        user = update.effective_user
        mention = user.mention_html()
        uid_str = str(user.id)
        
        if uid_str not in game["round_scores"]:
            game["round_scores"][uid_str] = {"mention": mention, "score": 0}
        game["round_scores"][uid_str]["score"] += points

        link = get_msg_link(chat, game["msg_id"])
        btn_go = InlineKeyboardMarkup([[InlineKeyboardButton("ɢᴏ ᴛᴏ ɢʀɪᴅ ⤻", url=link)]])
        try:
            await message.reply_text(f"<tg-emoji emoji-id=\"6080267780836302938\">💎</tg-emoji> <b>+{points} ᴘᴏɪɴᴛs ꜰᴏʀ {mention}!\n\n<tg-emoji emoji-id=\"5465626908165163181\">✅</tg-emoji> ʏᴏᴜ ꜰᴏᴜɴᴅ {guess}.</b>", parse_mode="HTML", reply_markup=btn_go)
        except Exception:
            pass
        
        async def background_update_task():
            now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
            today_str = now_ist.strftime("%Y-%m-%d")
            week_str = now_ist.strftime("%Y-W%V")
            month_str = now_ist.strftime("%Y-%m")
            year_str = now_ist.strftime("%Y")

            inc_dict = {
                "grid_points": points,
                f"{today_str}_grid_points": points,
                f"{week_str}_grid_points": points,
                f"{month_str}_grid_points": points,
                f"{year_str}_grid_points": points,
                f"{chat_id}_grid_points": points,
                f"{chat_id}_{today_str}_grid_points": points,
                f"{chat_id}_{week_str}_grid_points": points,
                f"{chat_id}_{month_str}_grid_points": points,
                f"{chat_id}_{year_str}_grid_points": points
            }
            try:
                await grid_games_col.update_one({'_id': chat_id}, {'$set': {'game_data': game}}, upsert=True)
                await user_collection.update_one({"id": user.id}, {"$inc": inc_dict, "$setOnInsert": {"first_name": user.first_name, "username": user.username}}, upsert=True)
            except Exception:
                pass
            
            img_bio = await asyncio.to_thread(create_grid_image, game["grid"], game["words"], list(game["found"]), chat_id)
            img_bio.seek(0)
            caption = get_sorted_caption(game["words"], game["found"])
            btn_refresh = InlineKeyboardMarkup([[InlineKeyboardButton("ʀᴇꜰʀᴇsʜ ɢʀɪᴅ", callback_data="refresh_grid")]])
            
            try:
                await context.bot.edit_message_media(
                    chat_id=chat_id, message_id=game["msg_id"],
                    media=InputMediaPhoto(img_bio, caption=caption, parse_mode="HTML"), reply_markup=btn_refresh
                )
            except Exception:
                pass

        if is_last:
            await background_update_task() 
            sorted_scores = sorted(game["round_scores"].values(), key=lambda x: x["score"], reverse=True)
            summary = "<tg-emoji emoji-id=\"5233477268617053735\">🕹</tg-emoji><tg-emoji emoji-id=\"5233546451950256512\">🕹</tg-emoji><tg-emoji emoji-id=\"5233604395354047945\">🕹</tg-emoji><tg-emoji emoji-id=\"5233544652358962131\">🕹</tg-emoji><tg-emoji emoji-id=\"5233619423444616550\">🕹</tg-emoji><tg-emoji emoji-id=\"5233286945731267091\">🕹</tg-emoji>\n\n<tg-emoji emoji-id=\"5280939169793732849\">🃏</tg-emoji> <b>Round Summary</b>\n\n"
            medals = ["<tg-emoji emoji-id=\"5440539497383087970\">🥇</tg-emoji>", "<tg-emoji emoji-id=\"5447203607294265305\">🥈</tg-emoji>", "<tg-emoji emoji-id=\"5453902265922376865\">🥉</tg-emoji>", "🏅", "🏅"] 
            for idx, data in enumerate(sorted_scores):
                medal = medals[idx] if idx < len(medals) else "🏅"
                summary += f"{medal} <b>{data['mention']}</b> <b>+{data['score']}</b> <tg-emoji emoji-id=\"6080267780836302938\">💎</tg-emoji>\n"
            
            summary += "\n<b>Thanks for playing! Start another game by /playgrid.</b>"
            blockquote_summary = f"<blockquote>{summary}</blockquote>"
            end_btn = InlineKeyboardMarkup([[InlineKeyboardButton("Ꮮᴇᴀꜰ ꪜɪʟʟᴀɢᴇ", url="https://t.me/Anime_Group_hai")]])
            try:
                await context.bot.send_message(chat_id=chat_id, text=blockquote_summary, parse_mode="HTML", reply_markup=end_btn)
            except Exception:
                pass
            del active_games[chat_id]
            stop_votes.pop(chat_id, None)
            await grid_games_col.delete_one({'_id': chat_id}) 
        else:
            asyncio.create_task(background_update_task())

async def refresh_grid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_db_loaded() 
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    
    if chat_id not in active_games:
        await query.answer("No active game found!", show_alert=True)
        return

    game = active_games[chat_id]
    img_bio = await asyncio.to_thread(create_grid_image, game["grid"], game["words"], game["found"], chat_id)
    img_bio.seek(0)
    
    caption = get_sorted_caption(game["words"], game["found"])
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("ʀᴇꜰʀᴇsʜ ɢʀɪᴅ", callback_data="refresh_grid")]])
    try:
        await query.edit_message_media(
            media=InputMediaPhoto(img_bio, caption=caption, parse_mode="HTML"), reply_markup=btn
        )
    except Exception:
        pass

# --- SETTINGS MENU ---
def build_settings_keyboard(chat_id):
    settings = get_chat_settings(chat_id)
    pin_text = "✅ On" if settings["pin"] else "❌ Off"
    mark_text = "✅ On" if settings["mark_words"] else "❌ Off"
    theme_text = settings["theme"].capitalize()
    
    keyboard = [
        [InlineKeyboardButton("📌 Pin", callback_data="ignore"), InlineKeyboardButton(pin_text, callback_data="wg_toggle_pin")],
        [InlineKeyboardButton("📝 Mark Words", callback_data="ignore"), InlineKeyboardButton(mark_text, callback_data="wg_toggle_mark")],
        [InlineKeyboardButton("🎨 Theme", callback_data="ignore"), InlineKeyboardButton(theme_text, callback_data="wg_theme_menu")],
        [InlineKeyboardButton("✖️ Close", callback_data="wg_close")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_theme_keyboard(chat_id):
    settings = get_chat_settings(chat_id)
    t = settings["theme"]
    
    auto_btn = "Automatic ✅" if t == "automatic" else "Automatic"
    blk_btn = "Black ✅" if t == "black" else "Black"
    wht_btn = "White ✅" if t == "white" else "White"
    
    keyboard = [
        [InlineKeyboardButton(auto_btn, callback_data="wg_set_theme_automatic")],
        [InlineKeyboardButton(blk_btn, callback_data="wg_set_theme_black"), InlineKeyboardButton(wht_btn, callback_data="wg_set_theme_white")],
        [InlineKeyboardButton("Back", callback_data="wg_back_settings")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_db_loaded() 
    chat = update.effective_chat
    user = update.effective_user
    
    if not await is_admin(chat, user.id, context.bot):
        await update.message.reply_text("<b>Only admins can change these settings.</b>", parse_mode="HTML")
        return
        
    text = "<tg-emoji emoji-id=\"6307567066572396133\">⚙</tg-emoji> <b>WordGrid Group Settings</b>\n\nManage the bot's behavior in this chat. Only admins can change these settings."
    await update.message.reply_text(text, reply_markup=build_settings_keyboard(chat.id), parse_mode="HTML")

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_db_loaded() 
    query = update.callback_query
    user = update.effective_user
    chat = update.effective_chat
    
    if query.data == "ignore":
        await query.answer()
        return
        
    if not await is_admin(chat, user.id, context.bot):
        await query.answer("Only admins can change these settings.", show_alert=True)
        return

    data = query.data
    settings = get_chat_settings(chat.id)

    if data == "wg_toggle_pin":
        settings["pin"] = not settings["pin"]
        await query.edit_message_reply_markup(reply_markup=build_settings_keyboard(chat.id))
    elif data == "wg_toggle_mark":
        settings["mark_words"] = not settings["mark_words"]
        await query.edit_message_reply_markup(reply_markup=build_settings_keyboard(chat.id))
    elif data == "wg_theme_menu":
        text = "🎨 <b>Board Theme</b>\n\nCurrent mode: <b>{}</b>\n\n• <b>Automatic</b> - light during the day, dark at night.\n• <b>Black</b> - always dark board.\n• <b>White</b> - always light board.".format(settings["theme"].capitalize())
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=build_theme_keyboard(chat.id))
    elif data.startswith("wg_set_theme_"):
        theme_val = data.split("_")[-1]
        settings["theme"] = theme_val
        text = "🎨 <b>Board Theme</b>\n\nCurrent mode: <b>{}</b>\n\n• <b>Automatic</b> - light during the day, dark at night.\n• <b>Black</b> - always dark board.\n• <b>White</b> - always light board.".format(theme_val.capitalize())
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=build_theme_keyboard(chat.id))
    elif data == "wg_back_settings":
        text = "<tg-emoji emoji-id=\"6307567066572396133\">⚙</tg-emoji> <b>WordGrid Group Settings</b>\n\nManage the bot's behavior in this chat. Only admins can change these settings."
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=build_settings_keyboard(chat.id))
    elif data == "wg_close":
        await query.message.delete()
        
    await grid_settings_col.update_one({'_id': chat.id}, {'$set': {'settings': settings}}, upsert=True)
    await query.answer()

# --- LEADERBOARD LOGIC ---
WG_LEADERBOARD_STATES = {}
LEADERBOARD_IMG = "https://files.catbox.moe/5t41mo.jpg"

def get_wg_user_state(chat_id):
    if chat_id not in WG_LEADERBOARD_STATES:
        WG_LEADERBOARD_STATES[chat_id] = {"scope": "global", "time": "all"}
    return WG_LEADERBOARD_STATES[chat_id]

def get_wg_target_key(time_filter, scope, chat_id):
    base_key = "grid_points"
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    time_prefix = None
    
    if time_filter == "today": time_prefix = now_ist.strftime("%Y-%m-%d")
    elif time_filter == "week": time_prefix = now_ist.strftime("%Y-W%V")
    elif time_filter == "month": time_prefix = now_ist.strftime("%Y-%m")
    elif time_filter == "year": time_prefix = now_ist.strftime("%Y")

    time_key = f"{time_prefix}_{base_key}" if time_prefix else base_key
    return f"{chat_id}_{time_key}" if scope == "chat" else time_key

def get_grid_top_keyboard(state):
    scope = state["scope"]
    time_f = state["time"]

    global_btn = "ɢʟᴏʙᴀʟ ⎋" if scope == "global" else "ɢʟᴏʙᴀʟ"
    chat_btn = "ᴛʜɪs ᴄʜᴀᴛ ⎋" if scope == "chat" else "ᴛʜɪs ᴄʜᴀᴛ"
    today_btn = "ᴛᴏᴅᴀʏ ⎋" if time_f == "today" else "ᴛᴏᴅᴀʏ"
    week_btn = "ᴡᴇᴇᴋ ⎋" if time_f == "week" else "ᴡᴇᴇᴋ"
    month_btn = "ᴍᴏɴᴛʜ ⎋" if time_f == "month" else "ᴍᴏɴᴛʜ"
    year_btn = "ʏᴇᴀʀ ⎋" if time_f == "year" else "ʏᴇᴀʀ"
    all_btn = "ᴀʟʟ-ᴛɪᴍᴇ ⎋" if time_f == "all" else "ᴀʟʟ-ᴛɪᴍᴇ"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(global_btn, callback_data="wg_top_scope_global"), InlineKeyboardButton("⟳", callback_data="wg_top_refresh"), InlineKeyboardButton(chat_btn, callback_data="wg_top_scope_chat")],
        [InlineKeyboardButton(today_btn, callback_data="wg_top_time_today"), InlineKeyboardButton(week_btn, callback_data="wg_top_time_week"), InlineKeyboardButton(month_btn, callback_data="wg_top_time_month")],
        [InlineKeyboardButton(year_btn, callback_data="wg_top_time_year"), InlineKeyboardButton(all_btn, callback_data="wg_top_time_all")]
    ])

# 🚀 DB Optimization: Optimized Projection to load data fast without fetching heavy user documents
async def fetch_grid_leaderboard(chat_id, state):
    scope = state["scope"]
    time_f = state["time"]
    sort_key = get_wg_target_key(time_f, scope, chat_id)
    
    # 🚀 SUPERFAST OPTIMIZATION: Check Memory Cache first!
    cache_key = f"{chat_id}_{scope}_{time_f}"
    now_ts = datetime.utcnow().timestamp()
    if cache_key in LB_CACHE:
        cached_msg, timestamp = LB_CACHE[cache_key]
        if now_ts - timestamp < LB_CACHE_TTL:
            return cached_msg
            
    try:
        # Reduced payload size for faster DB queries
        projection = {"id": 1, "_id": 1, "first_name": 1, "username": 1, sort_key: 1}
        cursor = user_collection.find({sort_key: {"$gt": 0}}, projection).sort(sort_key, -1).limit(10)
        top_users = await cursor.to_list(length=10)
        
        title_scope = "GLOBAL" if scope == "global" else "THIS CHAT"
        time_title = "" if time_f == "all" else f" ({time_f.upper()})"
        msg = f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>WordGrid Leaderboard</b> <tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji>\n━━━━━━━━━━━━━━━━━━━━━\n"
        
        if not top_users:
            msg += "<b><i>No players on the leaderboard yet! Play WordGrid to score points.</i></b>"
        else:
            for i, user in enumerate(top_users):
                uid = user.get('id', user.get('_id'))
                first_name = user.get('first_name', '')
                username = user.get('username', '')
                
                if not first_name or first_name.strip() == '':
                    first_name = username if username else 'Unknown'
                name = html.escape(first_name)
                
                # Silent profile link HTML
                if uid:
                    user_mention = f"<a href='tg://user?id={uid}'>{name}</a>"
                else:
                    user_mention = name
                
                points = user.get(sort_key, 0)
                msg += f"<b>{i + 1}.</b> <b>{user_mention}</b> - <b>{points:,}</b> <tg-emoji emoji-id=\"6080267780836302938\">💎</tg-emoji>\n"
        
        LB_CACHE[cache_key] = (msg, now_ts)
        return msg
    except Exception as e:
        return "<b><tg-emoji emoji-id=\"6309717264639726942\">⚠️</tg-emoji> Error fetching leaderboard.</b>"

async def leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state = get_wg_user_state(chat_id)
    msg = await fetch_grid_leaderboard(chat_id, state)
    keyboard = get_grid_top_keyboard(state)
    
    # 🚀 SILENT MENTION HACK: Pehle bina tags ke load karega, fir edit kar dega tag ke saath. (No @ Notification)
    loading_msg = await update.message.reply_photo(
        photo=LEADERBOARD_IMG,
        caption="<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>Loading WordGrid Leaderboard...</b>",
        parse_mode="HTML"
    )
    await loading_msg.edit_caption(caption=msg, parse_mode="HTML", reply_markup=keyboard)

async def grid_leaderboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # 🚀 INSTANT BUTTON FEEDBACK: Spinner turant stop hoga
    try:
        await query.answer()
    except Exception:
        pass
        
    data = query.data
    chat_id = query.message.chat_id
    state = get_wg_user_state(chat_id)

    if data == "wg_top_scope_global": state["scope"] = "global"
    elif data == "wg_top_scope_chat": state["scope"] = "chat"
    elif data.startswith("wg_top_time_"): state["time"] = data.replace("wg_top_time_", "")
        
    msg = await fetch_grid_leaderboard(chat_id, state)
    keyboard = get_grid_top_keyboard(state)
    
    try:
        # 🚀 ZERO LAG: edit_message_caption se bina image reload kiye text instantly badlega
        await query.edit_message_caption(caption=msg, parse_mode="HTML", reply_markup=keyboard)
    except BadRequest as e:
        if "not modified" in str(e).lower(): return
        try:
            # Fallback agar image purani cache se issue de
            await query.edit_message_media(
                media=InputMediaPhoto(media=LEADERBOARD_IMG, caption=msg, parse_mode="HTML"),
                reply_markup=keyboard
            )
        except Exception:
            pass
    except Exception:
        pass

# --- REGISTER HANDLERS ---
application.add_handler(CommandHandler(["playgrid", "new_grid", "wordgrid", "grid", "grid_easy", "grid_hard"], start_game, block=False))
application.add_handler(CommandHandler(["stopgame", "endgrid"], stop_game, block=False))
application.add_handler(CommandHandler(["gridtop", "topgrid"], leaderboard_handler, block=False))
application.add_handler(CommandHandler(["helpgrid", "gridsettings"], settings_cmd, block=False))

application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_guesses, block=False), group=5)
application.add_handler(CallbackQueryHandler(refresh_grid_callback, pattern="^refresh_grid$", block=False))
application.add_handler(CallbackQueryHandler(grid_leaderboard_callback, pattern="^wg_top_", block=False))
application.add_handler(CallbackQueryHandler(vote_stop_callback, pattern="^wg_vote_stop$", block=False))
application.add_handler(CallbackQueryHandler(settings_callback, pattern="^wg_|ignore", block=False))

__mod_name__ = "WordGrid"
__help__ = """
🎮 <b>WordGrid Game Commands:</b>
- /grid: Start normal mode.
- /grid_easy: Start a smaller, easier board.
- /grid_hard: Start a larger, tougher board.
- /end: Stop the active game.
- /gridtop: View the WordGrid Leaderboard.
- /gridsettings: Manage chat settings for the game.
"""

import random
import string
import io
import logging
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from shivu import application, user_collection

LOGGER = logging.getLogger(__name__)

# Game State Storage
active_games = {}

# Massive Word Pool to prevent boredom (100+ words)
WORD_LIST = [
    "PROFIT", "RESERVE", "READY", "PRODUCE", "MARRY", "REACH", "JOY", "AGE", "MET", "FUR", "TIDE", 
    "ODDS", "FEVER", "TRADE", "INCHES", "AFFECT", "STATING", "FIRE", "WATER", "MAGIC", "POWER", 
    "BLADE", "SHADOW", "NINJA", "STORM", "LIGHT", "HEART", "DREAM", "BRAVE", "QUEST", "TITAN", 
    "GHOST", "SOUND", "MUSIC", "ROBOT", "SUPER", "SPEED", "ROYAL", "WORLD", "HOUSE", "ENERGY", 
    "FORCE", "TABLE", "CHAIR", "APPLE", "GRAPE", "LEMON", "PIZZA", "BURGER", "SNACK", "TIGER", 
    "PLANT", "EARTH", "SPACE", "TRAIN", "ANCHOR", "BRIDGE", "CASTLE", "DESERT", "STARS", "MOON",
    "JUMP", "DANCE", "VOICE", "PAINT", "WRITE", "PHONE", "CLOCK", "WATCH", "RADIO", "PLANE",
    "PILOT", "FIGHT", "GUARD", "CLIMB", "BUILD", "CRAFT", "FIELD", "RIVER", "OCEAN", "BEACH",
    "CHAMPION", "EXPLORE", "MYSTERY", "VOLCANO", "DIAMOND", "CRYSTAL", "DYNAMIC", "TRIUMPH",
    "WELCOME", "PIRATE", "WIZARD", "DRAGON", "LEGEND", "HUNTER", "WARRIOR", "FUTURE", "SYSTEM"
]

def generate_game_grid(size=8, num_words=9):
    grid = [['' for _ in range(size)] for _ in range(size)]
    chosen_words = random.sample(WORD_LIST, min(num_words, len(WORD_LIST)))
    placed_words = {}
    directions = [(0, 1), (1, 0), (1, 1), (-1, 1), (-1, -1), (0, -1), (-1, 0), (1, -1)] 
    
    for word in chosen_words:
        placed = False
        for _ in range(200):
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

def create_grid_image(grid, placed_words, found_words):
    cell_size = 70  # Bada cell size taaki letter box ke andar poora fit ho
    size = len(grid)
    img_size = cell_size * size
    
    img = Image.new('RGB', (img_size, img_size), color='#0a0a0a') 
    draw = ImageDraw.Draw(img, 'RGBA')

    try:
        font = ImageFont.truetype("arialbd.ttf", 36) # Bada, bold font
    except IOError:
        font = ImageFont.load_default()

    # Capsule colors for found words
    colors = [
        (60, 120, 120, 185), 
        (150, 60, 60, 185), 
        (60, 150, 60, 185), 
        (100, 80, 150, 185), 
        (150, 120, 50, 185),
        (50, 100, 180, 185)
    ]
    
    # Draw Found Words (Capsules/Lines)
    for i, word in enumerate(found_words):
        if word in placed_words:
            coords = placed_words[word]
            c1, r1 = coords[0][1] * cell_size + cell_size // 2, coords[0][0] * cell_size + cell_size // 2
            c2, r2 = coords[-1][1] * cell_size + cell_size // 2, coords[-1][0] * cell_size + cell_size // 2
            
            color = colors[i % len(colors)]
            draw.line([(c1, r1), (c2, r2)], fill=color, width=52)
            draw.ellipse([c1 - 26, r1 - 26, c1 + 26, r1 + 26], fill=color)
            draw.ellipse([c2 - 26, r2 - 26, c2 + 26, r2 + 26], fill=color)

    # Draw Grid Lines & Full Box Centered Letters
    for r in range(size):
        for c in range(size):
            x0, y0 = c * cell_size, r * cell_size
            x1, y1 = x0 + cell_size, y0 + cell_size
            draw.rectangle([x0, y0, x1, y1], outline="#222222", width=2)
            
            letter = grid[r][c]
            # Center text perfectly inside the 70x70 box
            bbox = font.getbbox(letter)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            text_x = x0 + (cell_size - w) / 2 - bbox[0]
            text_y = y0 + (cell_size - h) / 2 - bbox[1]
            
            draw.text((text_x, text_y), letter, fill="#ffffff", font=font)

    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.name = 'grid.png'
    return bio

def get_sorted_caption(placed_words, found_words):
    caption = "<tg-emoji emoji-id=\"5224450179368767019\">🌎</tg-emoji> <b>WORD GRID CHALLENGE</b> <tg-emoji emoji-id=\"5224450179368767019\">🌎</tg-emoji>\n\nFind these words:\n"
    sorted_words = sorted(placed_words.keys(), key=len)
    
    for w in sorted_words:
        if w in found_words:
            caption += f"<tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji> {w}\n"
        else:
            masked = w[0] + "-" * (len(w) - 1)
            caption += f"<code>{masked}</code> ({len(w)})\n"
    caption += "\nTap <tg-emoji emoji-id=\"5260491539167073671\">🔄</tg-emoji> Refresh Grid to mark!"
    return caption

# --- HANDLERS ---

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("This game can only be played in groups!")
        return

    chat_id = chat.id
    if chat_id in active_games:
        await update.message.reply_text("<tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> A WordGrid game is already running! Use /stopgame to end it.")
        return

    grid, placed_words = generate_game_grid()
    active_games[chat_id] = {
        "grid": grid, "words": placed_words, "found": [], "msg_id": None, "round_scores": {}
    }

    img_bio = create_grid_image(grid, placed_words, [])
    img_bio.seek(0)

    caption = get_sorted_caption(placed_words, [])
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("Refresh Grid", callback_data="refresh_grid")]])
    
    msg = await context.bot.send_photo(chat_id=chat_id, photo=img_bio, caption=caption, parse_mode="HTML", reply_markup=btn)
    active_games[chat_id]["msg_id"] = msg.message_id

async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type not in ["group", "supergroup"]:
        return
    chat_id = chat.id
    if chat_id in active_games:
        del active_games[chat_id]
        await update.message.reply_text("<tg-emoji emoji-id=\"6310066608689650607\">⬅️</tg-emoji> <b>WordGrid game has been stopped.</b>", parse_mode="HTML")
    else:
        await update.message.reply_text("<b><tg-emoji emoji-id=\"6309717264639726942\">⚠️</tg-emoji> No active game running right now.</b>", parse_mode="HTML")

async def handle_guesses(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        
        points = 3 if is_first else (5 if is_last else 2)
        game["found"].append(guess)
        
        user = update.effective_user
        mention = user.mention_html()
        game["round_scores"][user.first_name] = game["round_scores"].get(user.first_name, 0) + points
        
        # Save points to database (grid_points)
        try:
            await user_collection.update_one(
                {"id": user.id},
                {"$inc": {"grid_points": points}},
                upsert=True
            )
        except Exception as e:
            LOGGER.error(f"Error updating grid points: {e}")
        
        img_bio = create_grid_image(game["grid"], game["words"], game["found"])
        img_bio.seek(0)
        
        caption = get_sorted_caption(game["words"], game["found"])
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("Refresh Grid", callback_data="refresh_grid")]])
        
        try:
            await context.bot.edit_message_media(
                chat_id=chat_id, message_id=game["msg_id"],
                media=InputMediaPhoto(img_bio, caption=caption, parse_mode="HTML"), reply_markup=btn
            )
        except Exception:
            pass

        await message.reply_text(f"<tg-emoji emoji-id=\"5465626908165163181\">✅</tg-emoji> <b>+{points} points for {mention}! You found {guess}.</b>", parse_mode="HTML")
        
        if is_last:
            sorted_scores = sorted(game["round_scores"].items(), key=lambda x: x[1], reverse=True)
            summary = "👾 <b>GAME OVER</b> 👾\n\n--- Round Summary ---\n\n"
            medals = ["🥇", "🥈", "🥉", "🏅", "🏅"] 
            for idx, (name, score) in enumerate(sorted_scores):
                summary += f"{medals[idx] if idx < len(medals) else '🏅'} {name}: {score} points\n"
            
            summary += "\nThanks for playing! Start another game by /playgrid."
            end_btn = InlineKeyboardMarkup([[InlineKeyboardButton("SUPPORT GROUP", url="https://t.me/LeafVillage")]])
            await context.bot.send_message(chat_id=chat_id, text=summary, parse_mode="HTML", reply_markup=end_btn)
            del active_games[chat_id]

async def refresh_grid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    
    if chat_id not in active_games:
        await query.answer("No active game found!", show_alert=True)
        return

    game = active_games[chat_id]
    img_bio = create_grid_image(game["grid"], game["words"], game["found"])
    img_bio.seek(0)
    
    caption = get_sorted_caption(game["words"], game["found"])
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("Refresh Grid", callback_data="refresh_grid")]])
    try:
        await query.edit_message_media(
            media=InputMediaPhoto(img_bio, caption=caption, parse_mode="HTML"), reply_markup=btn
        )
    except Exception:
        pass

async def leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cursor = user_collection.find({"grid_points": {"$gt": 0}}).sort("grid_points", -1).limit(10)
        top_users = await cursor.to_list(length=10)
        
        msg = "🏆 <b>GRID TOP LEADERBOARD</b> 🏆\n\n"
        if not top_users:
            msg += "<i>No players on the leaderboard yet! Play WordGrid to score points.</i>"
        else:
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            for i, user in enumerate(top_users):
                medal = medals[i] if i < len(medals) else "🏅"
                name = user.get('first_name', 'Player')
                points = user.get('grid_points', 0)
                msg += f"{medal} <b>{name}</b> — <code>{points} pts</code>\n"
        
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        LOGGER.error(f"Leaderboard error: {e}")
        await update.message.reply_text("<b><tg-emoji emoji-id=\"6309717264639726942\">⚠️</tg-emoji> Error fetching leaderboard.</b>", parse_mode="HTML")

# --- REGISTER HANDLERS ---
application.add_handler(CommandHandler(["playgrid", "new_grid", "wordgrid"], start_game))
application.add_handler(CommandHandler(["stopgame", "endgrid"], stop_game))
application.add_handler(CommandHandler("gridtop", leaderboard_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_guesses), group=5)
application.add_handler(CallbackQueryHandler(refresh_grid_callback, pattern="refresh_grid"))

__mod_name__ = "WordGrid"
__help__ = """
🎮 <b>WordGrid Game Commands:</b>
- /playgrid : Start a new word search game.
- /stopgame : Stop the active game.
- /gridtop: View the WordGrid Leaderboard.
"""

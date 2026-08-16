import random
import string
import io
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from shivu import application

# Game State Storage
active_games = {}

# Bada aur unlimited feel dene wala word pool
WORD_LIST = [
    "PROFIT", "RESERVE", "READY", "PRODUCE", "MARRY", "REACH", "JOY", "AGE", "MET", 
    "FUR", "TIDE", "ODDS", "FEVER", "TRADE", "INCHES", "AFFECT", "STATING", 
    "FIRE", "WATER", "MAGIC", "POWER", "BLADE", "SHADOW", "NINJA", "STORM", 
    "LIGHT", "HEART", "DREAM", "BRAVE", "QUEST", "TITAN", "GHOST", "SOUND", 
    "ROBOT", "SUPER", "SPEED", "ROYAL", "WORLD", "HOUSE", "ENERGY", "FORCE",
    "TABLE", "CHAIR", "APPLE", "GRAPE", "LEMON", "PIZZA", "BURGER", "SNACK",
    "TIGER", "PLANT", "EARTH", "SPACE", "MUSIC", "RADIO", "PHONE", "CHAMP", 
    "BLOOD", "TRAIN", "PLASTIC", "ANCHOR", "BRIDGE", "CASTLE", "DESERT", "FORCE"
]

def generate_game_grid(size=8, num_words=8):
    grid = [['' for _ in range(size)] for _ in range(size)]
    chosen_words = random.sample(WORD_LIST, min(num_words, len(WORD_LIST)))
    placed_words = {}
    directions = [(0, 1), (1, 0), (1, 1), (-1, 1)] 
    
    for word in chosen_words:
        placed = False
        attempts = 0
        while not placed and attempts < 200:
            d_r, d_c = random.choice(directions)
            r = random.randint(0, size - 1)
            c = random.randint(0, size - 1)
            
            if 0 <= r + d_r * (len(word)-1) < size and 0 <= c + d_c * (len(word)-1) < size:
                can_place = True
                coords = []
                for i in range(len(word)):
                    nr, nc = r + d_r * i, c + d_c * i
                    if grid[nr][nc] != '' and grid[nr][nc] != word[i]:
                        can_place = False
                        break
                    coords.append((nr, nc))
                
                if can_place:
                    for i in range(len(word)):
                        nr, nc = coords[i]
                        grid[nr][nc] = word[i]
                    placed_words[word] = coords
                    placed = True
            attempts += 1

    for r in range(size):
        for c in range(size):
            if grid[r][c] == '':
                grid[r][c] = random.choice(string.ascii_uppercase)
    return grid, placed_words

def create_grid_image(grid, placed_words, found_words):
    cell_size = 60
    size = len(grid)
    img_size = cell_size * size
    img = Image.new('RGB', (img_size, img_size), color='#0a0a0a') 
    draw = ImageDraw.Draw(img, 'RGBA')

    try:
        font = ImageFont.truetype("arialbd.ttf", 32) # Bold & Clear font
    except:
        font = ImageFont.load_default()

    # Premium looking capsule colors
    colors = [
        (60, 120, 120, 180), 
        (150, 60, 60, 180), 
        (60, 150, 60, 180), 
        (100, 80, 150, 180), 
        (150, 120, 50, 180),
        (50, 100, 180, 180)
    ]
    
    # Draw Found Words with Rounded Capsules
    for i, word in enumerate(found_words):
        if word in placed_words:
            coords = placed_words[word]
            c1, r1 = coords[0][1] * cell_size + 30, coords[0][0] * cell_size + 30
            c2, r2 = coords[-1][1] * cell_size + 30, coords[-1][0] * cell_size + 30
            
            color = colors[i % len(colors)]
            draw.line([(c1, r1), (c2, r2)], fill=color, width=45)
            draw.ellipse([c1-22, r1-22, c1+22, r1+22], fill=color)
            draw.ellipse([c2-22, r2-22, c2+22, r2+22], fill=color)

    # Draw Grid and Letters
    for r in range(size):
        for c in range(size):
            x, y = c * cell_size, r * cell_size
            draw.rectangle([x, y, x+cell_size, y+cell_size], outline="#222222", width=1)
            draw.text((x + 20, y + 15), grid[r][c], fill="#dddddd", font=font)

    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.name = 'grid.png'
    return bio

def get_sorted_caption(placed_words, found_words):
    caption = "🌐 <b>WORD GRID CHALLENGE</b> 🌐\n\nFind these words:\n"
    for w in sorted(placed_words.keys(), key=len):
        if w in found_words:
            caption += f"✅ {w}\n"
        else:
            caption += f"<code>{w[0] + '-'*(len(w)-1)}</code> ({len(w)})\n"
    caption += "\nTap 🔄 Refresh Grid to mark!"
    return caption

# --- HANDLERS ---

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("This game can only be played in groups!")
        return

    chat_id = chat.id
    if chat_id in active_games:
        await update.message.reply_text("⚠️ A WordGrid game is already running! Use /stopgame to end it.")
        return

    grid, placed_words = generate_game_grid()
    active_games[chat_id] = {
        "grid": grid, "words": placed_words, "found": [], "msg_id": None, "round_scores": {}
    }

    img_bio = create_grid_image(grid, placed_words, [])
    img_bio.seek(0)

    caption = get_sorted_caption(placed_words, [])
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh Grid", callback_data="refresh_grid")]])
    
    msg = await context.bot.send_photo(chat_id=chat_id, photo=img_bio, caption=caption, parse_mode="HTML", reply_markup=btn)
    active_games[chat_id]["msg_id"] = msg.message_id

async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        return
    chat_id = chat.id
    if chat_id in active_games:
        del active_games[chat_id]
        await update.message.reply_text("⏹ <b>WordGrid game has been stopped.</b>", parse_mode="HTML")
    else:
        await update.message.reply_text("<b>ℹ️ No active game running right now.</b>", parse_mode="HTML")

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
        
        img_bio = create_grid_image(game["grid"], game["words"], game["found"])
        img_bio.seek(0)
        
        caption = get_sorted_caption(game["words"], game["found"])
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh Grid", callback_data="refresh_grid")]])
        
        try:
            await context.bot.edit_message_media(
                chat_id=chat_id, message_id=game["msg_id"],
                media=InputMediaPhoto(img_bio, caption=caption, parse_mode="HTML"), reply_markup=btn
            )
        except Exception:
            pass

        await message.reply_text(f"✅ <b>+{points} points for {mention}! You found {guess}.</b>", parse_mode="HTML")
        
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
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh Grid", callback_data="refresh_grid")]])
    try:
        await query.edit_message_media(
            media=InputMediaPhoto(img_bio, caption=caption, parse_mode="HTML"), reply_markup=btn
        )
    except Exception:
        pass

# --- REGISTER HANDLERS ---
application.add_handler(CommandHandler(["playgrid", "new_grid", "wordgrid"], start_game))
application.add_handler(CommandHandler(["stopgame", "endgrid"], stop_game))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_guesses), group=5)
application.add_handler(CallbackQueryHandler(refresh_grid_callback, pattern="refresh_grid"))

__mod_name__ = "WordGrid"
__help__ = """
🎮 <b>WordGrid Game Commands:</b>
- /playgrid or /wordgrid: Start a new word search game.
- /stopgame or /end: Stop the active game.
"""

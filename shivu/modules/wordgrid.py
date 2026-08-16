import random
import string
import io
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from shivu import application

# Game State Storage
active_games = {}

WORD_LIST = [
    "MET", "FUR", "TIDE", "ODDS", "FEVER", "TRADE", "INCHES", "AFFECT", 
    "STATING", "JOY", "USED", "EARN", "LENS", "LADDER", "SILENCE", "AGE",
    "FIRE", "WATER", "MAGIC", "POWER", "BLADE", "SHADOW", "NINJA", "STORM",
    "LIGHT", "HEART", "DREAM", "BRAVE", "CHAMP", "QUEST", "BLOOD", "TITAN"
]

def generate_game_grid(size=8, num_words=8):
    grid = [['' for _ in range(size)] for _ in range(size)]
    chosen_words = random.sample(WORD_LIST, min(num_words, len(WORD_LIST)))
    placed_words = {}
    directions = [(0, 1), (1, 0), (1, 1), (-1, 1)] 
    
    for word in chosen_words:
        placed = False
        attempts = 0
        while not placed and attempts < 100:
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
    cell_size = 50
    size = len(grid)
    img_size = cell_size * size
    
    img = Image.new('RGB', (img_size, img_size), color='#121212') 
    draw = ImageDraw.Draw(img, 'RGBA')

    try:
        font = ImageFont.truetype("arial.ttf", 26) 
    except IOError:
        font = ImageFont.load_default()

    for r in range(size):
        for c in range(size):
            x0, y0 = c * cell_size, r * cell_size
            x1, y1 = x0 + cell_size, y0 + cell_size
            draw.rectangle([x0, y0, x1, y1], outline="#333333", width=1)
            letter = grid[r][c]
            draw.text((x0 + 17, y0 + 10), letter, fill="white", font=font)

    colors = [
        (255, 85, 85, 120), (85, 255, 85, 120), (85, 85, 255, 120), 
        (255, 255, 85, 120), (255, 170, 85, 120), (255, 85, 255, 120)
    ]
    color_idx = 0
    
    for word in found_words:
        if word in placed_words:
            coords = placed_words[word]
            start_x = coords[0][1] * cell_size + cell_size // 2
            start_y = coords[0][0] * cell_size + cell_size // 2
            end_x = coords[-1][1] * cell_size + cell_size // 2
            end_y = coords[-1][0] * cell_size + cell_size // 2
            
            color = colors[color_idx % len(colors)]
            draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=28, joint="curve")
            color_idx += 1

    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.name = 'grid.png'
    return bio

# --- HANDLERS ---

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("This game can only be played in groups!")
        return

    chat_id = chat.id
    if chat_id in active_games:
        await update.message.reply_text("⚠️ A WordGrid game is already running in this group!")
        return

    grid, placed_words = generate_game_grid()
    active_games[chat_id] = {
        "grid": grid, "words": placed_words, "found": [], "msg_id": None, "round_scores": {}
    }

    img_bio = create_grid_image(grid, placed_words, [])
    img_bio.seek(0)

    caption = "🌐 **WORD GRID CHALLENGE** 🌐\n\nFind these words:\n"
    for w in placed_words.keys():
        caption += f"{w[0]}{'-' * (len(w)-1)} ({len(w)})\n"
    caption += "\nTap 🔄 Refresh Grid to mark!"

    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh Grid", callback_data="refresh_grid")]])
    msg = await context.bot.send_photo(chat_id=chat_id, photo=img_bio, caption=caption, parse_mode="Markdown", reply_markup=btn)
    active_games[chat_id]["msg_id"] = msg.message_id

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
        user_name = user.first_name or "Player"
        game["round_scores"][user_name] = game["round_scores"].get(user_name, 0) + points
        
        img_bio = create_grid_image(game["grid"], game["words"], game["found"])
        img_bio.seek(0)
        
        caption = "🌐 **WORD GRID CHALLENGE** 🌐\n\nFind these words:\n"
        for w in game["words"].keys():
            caption += f"✅ {w}\n" if w in game["found"] else f"{w[0]}{'-' * (len(w)-1)} ({len(w)})\n"
        caption += "\nTap 🔄 Refresh Grid to mark!"
        
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh Grid", callback_data="refresh_grid")]])
        
        try:
            await context.bot.edit_message_media(
                chat_id=chat_id, message_id=game["msg_id"],
                media=InputMediaPhoto(img_bio, caption=caption, parse_mode="Markdown"), reply_markup=btn
            )
        except Exception as e:
            print(f"Image update error: {e}")

        mention = user.mention_html() if hasattr(user, "mention_html") else user_name
        await message.reply_text(f"✅ **+{points} points** for {mention}! You found **{guess}**.", parse_mode="Markdown")
        
        if is_last:
            sorted_scores = sorted(game["round_scores"].items(), key=lambda x: x[1], reverse=True)
            summary = "👾 **GAME OVER** 👾\n\n--- Round Summary ---\n\n"
            medals = ["🥇", "🥈", "🥉", "🏅", "🏅"] 
            for idx, (name, score) in enumerate(sorted_scores):
                summary += f"{medals[idx] if idx < len(medals) else '🏅'} {name}: {score} points\n"
            
            summary += "\nThanks for playing! Start another game by /new."
            end_btn = InlineKeyboardMarkup([[InlineKeyboardButton("SUPPORT GROUP", url="https://t.me/LeafVillage")]])
            await context.bot.send_message(chat_id=chat_id, text=summary, parse_mode="Markdown", reply_markup=end_btn)
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
    
    caption = "🌐 **WORD GRID CHALLENGE** 🌐\n\nFind these words:\n"
    for w in game["words"].keys():
        caption += f"✅ {w}\n" if w in game["found"] else f"{w[0]}{'-' * (len(w)-1)} ({len(w)})\n"
    caption += "\nTap 🔄 Refresh Grid to mark!"
    
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh Grid", callback_data="refresh_grid")]])
    try:
        await query.edit_message_media(
            media=InputMediaPhoto(img_bio, caption=caption, parse_mode="Markdown"), reply_markup=btn
        )
    except Exception:
        pass

async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        return
    chat_id = chat.id
    if chat_id in active_games:
        del active_games[chat_id]
        await update.message.reply_text("⏹ WordGrid game stopped.")
    else:
        await update.message.reply_text("No active WordGrid game to stop.")

# --- REGISTER HANDLERS ---
application.add_handler(CommandHandler(["playgrid", "new_grid", "wordgrid"], start_game))
application.add_handler(CommandHandler(["stopgame", "endgrid"], stop_game))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_guesses))
application.add_handler(CallbackQueryHandler(refresh_grid_callback, pattern="refresh_grid"))

__mod_name__ = "WordGrid"
__help__ = """
🎮 **WordGrid Game Commands:**
- /play or /new: Start a new word search grid game in the group.
- /stopgame: Stop the active game.
"""

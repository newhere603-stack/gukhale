import random
import string
import io
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from shivu import application

active_games = {}

# Unlimited feel dene ke liye bada pool
WORD_LIST = [
    "PROFIT", "RESERVE", "READY", "PRODUCE", "MARRY", "REACH", "JOY", "AGE", "MET", 
    "FUR", "TIDE", "ODDS", "FEVER", "TRADE", "INCHES", "AFFECT", "STATING", 
    "FIRE", "WATER", "MAGIC", "POWER", "BLADE", "SHADOW", "NINJA", "STORM", 
    "LIGHT", "HEART", "DREAM", "BRAVE", "QUEST", "TITAN", "GHOST", "SOUND", 
    "ROBOT", "SUPER", "SPEED", "ROYAL", "WORLD", "HOUSE", "ENERGY", "FORCE",
    "TABLE", "CHAIR", "APPLE", "GRAPE", "LEMON", "PIZZA", "BURGER", "SNACK"
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
        font = ImageFont.truetype("arialbd.ttf", 32) # Bold font
    except:
        font = ImageFont.load_default()

    # Capsule colors
    colors = [(60, 120, 120, 180), (150, 60, 60, 180), (60, 150, 60, 180), (100, 80, 150, 180), (150, 120, 50, 180)]
    
    # Draw Found Words (Capsules)
    for i, word in enumerate(found_words):
        if word in placed_words:
            coords = placed_words[word]
            c1, r1 = coords[0][1] * cell_size + 30, coords[0][0] * cell_size + 30
            c2, r2 = coords[-1][1] * cell_size + 30, coords[-1][0] * cell_size + 30
            
            # Draw Capsule
            draw.line([(c1, r1), (c2, r2)], fill=colors[i % len(colors)], width=45)
            # Rounded ends for capsule
            draw.ellipse([c1-22, r1-22, c1+22, r1+22], fill=colors[i % len(colors)])
            draw.ellipse([c2-22, r2-22, c2+22, r2+22], fill=colors[i % len(colors)])

    # Draw Grid Lines & Letters
    for r in range(size):
        for c in range(size):
            x, y = c * cell_size, r * cell_size
            draw.rectangle([x, y, x+cell_size, y+cell_size], outline="#222222", width=1)
            draw.text((x + 20, y + 15), grid[r][c], fill="#dddddd", font=font)

    bio = io.BytesIO()
    img.save(bio, format='PNG')
    return bio

def get_sorted_caption(placed_words, found_words):
    caption = "🌐 <b>WORD GRID CHALLENGE</b> 🌐\n\nFind these words:\n"
    for w in sorted(placed_words.keys(), key=len):
        caption += f"✅ {w}\n" if w in found_words else f"<code>{w[0] + '-'*(len(w)-1)}</code> ({len(w)})\n"
    return caption + "\nTap 🔄 Refresh Grid to mark!"

# --- HANDLERS ---
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in active_games:
        await update.message.reply_text("⚠️ Game already running!")
        return
    grid, placed_words = generate_game_grid()
    active_games[chat_id] = {"grid": grid, "words": placed_words, "found": [], "msg_id": None, "scores": {}}
    img = create_grid_image(grid, placed_words, [])
    msg = await context.bot.send_photo(chat_id, img, caption=get_sorted_caption(placed_words, []), parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_grid")]]))
    active_games[chat_id]["msg_id"] = msg.message_id

async def handle_guesses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_games: return
    game = active_games[chat_id]
    guess = update.message.text.upper().strip()
    
    if guess in game["words"] and guess not in game["found"]:
        game["found"].append(guess)
        img = create_grid_image(game["grid"], game["words"], game["found"])
        await context.bot.edit_message_media(chat_id, game["msg_id"], InputMediaPhoto(img, caption=get_sorted_caption(game["words"], game["found"]), parse_mode="HTML"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_grid")]]))
        await update.message.reply_text(f"✅ <b>{guess} Found!</b>", parse_mode="HTML")
        if len(game["found"]) == len(game["words"]):
            await update.message.reply_text("🎉 <b>Round Complete!</b>")
            del active_games[chat_id]

application.add_handler(CommandHandler(["playgrid", "new_grid", "wordgrid"], start_game))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_guesses), group=5)
application.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.answer(), pattern="refresh_grid"))

import os
import random
import string
import io
from PIL import Image, ImageDraw, ImageFont
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

# ==========================================
# ⚙️ HEROKU BOT CONFIGURATION
# ==========================================
# Heroku ke settings (Config Vars) se values lega
API_ID = int(os.environ.get("API_ID", "1234567")) 
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")

app = Client("wordgrid_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# In-memory storage active games ke liye
active_games = {}
user_stats = {} 

WORD_LIST = ["MET", "FUR", "TIDE", "ODDS", "FEVER", "TRADE", "INCHES", "AFFECT", "STATING", "JOY", "USED", "EARN", "LENS", "LADDER", "SILENCE", "AGE"]

# (generate_game_grid aur create_grid_image function bilkul pehle jaise rahenge, 
# main seedha main logic update kar raha hoon)

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

    colors = [(255, 85, 85, 120), (85, 255, 85, 120), (85, 85, 255, 120), (255, 255, 85, 120), (255, 170, 85, 120)]
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

@app.on_message(filters.command(["play", "new"]) & filters.group)
async def start_game(client, message):
    chat_id = message.chat.id
    if chat_id in active_games:
        await message.reply_text("⚠️ A game is already running! Use /stopgame to end it first.")
        return

    grid, placed_words = generate_game_grid()
    active_games[chat_id] = {
        "grid": grid,
        "words": placed_words,
        "found": [],
        "msg_id": None,
        "round_scores": {} # NAYA: Is round ke current scores track karne ke liye
    }

    img_bio = create_grid_image(grid, placed_words, [])
    img_bio.seek(0)

    caption = "🌐 **WORD GRID CHALLENGE** 🌐\n\nFind these words:\n"
    for w in placed_words.keys():
        caption += f"{w[0]}{'-' * (len(w)-1)} ({len(w)})\n"
    caption += "\nTap 🔄 Refresh Grid to mark!"

    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh Grid", callback_data="refresh_grid")]])
    msg = await message.reply_photo(photo=img_bio, caption=caption, reply_markup=btn)
    active_games[chat_id]["msg_id"] = msg.id

@app.on_message(filters.text & filters.group, group=1)
async def handle_guesses(client, message):
    chat_id = message.chat.id
    if chat_id not in active_games:
        return

    game = active_games[chat_id]
    guess = message.text.upper().strip()

    if guess in game["words"] and guess not in game["found"]:
        is_first = len(game["found"]) == 0
        is_last = len(game["found"]) == len(game["words"]) - 1
        
        points = 2 
        if is_first: points = 3
        elif is_last: points = 5
        
        game["found"].append(guess)
        
        # Name aur points save karna
        user_name = message.from_user.first_name or "Player"
        user_id = message.from_user.id
        
        game["round_scores"][user_name] = game["round_scores"].get(user_name, 0) + points
        user_stats[user_id] = user_stats.get(user_id, 0) + points
        
        reply_text = f"✅ **+{points} points** for {message.from_user.mention}! You found **{guess}**."
        
        group_username_or_id = str(chat_id).replace('-100', '')
        link = f"https://t.me/c/{group_username_or_id}/{game['msg_id']}"
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("Go to Grid ➡", url=link)]])
        
        await message.reply_text(reply_text, reply_markup=btn)
        
        # NAYA: GAME OVER LOGIC (Screenshot jaisa)
        if is_last:
            # Score ko sort karna (Highest se lowest)
            sorted_scores = sorted(game["round_scores"].items(), key=lambda x: x[1], reverse=True)
            
            summary = "👾 **GAME OVER** 👾\n\n--- Round Summary ---\n\n"
            medals = ["🥇", "🥈", "🥉", "🏅", "🏅"] # Top 3 ko badhiya medal, baaki sab ko normal
            
            for idx, (name, score) in enumerate(sorted_scores):
                medal = medals[idx] if idx < len(medals) else "🏅"
                summary += f"{medal} {name}: {score} points\n"
            
            summary += "\nThanks for playing start another game by /new_hard or /new."
            
            # Support group ka button 
            end_btn = InlineKeyboardMarkup([[
                InlineKeyboardButton("SUPPORT GROUP", url="https://t.me/YourSupportGroupLink")
            ]])
            
            await message.reply_text(summary, reply_markup=end_btn)
            del active_games[chat_id]

@app.on_callback_query(filters.regex("refresh_grid"))
async def refresh_grid_callback(client, callback_query):
    chat_id = callback_query.message.chat.id
    if chat_id not in active_games:
        await callback_query.answer("No active game found!", show_alert=True)
        return

    game = active_games[chat_id]
    img_bio = create_grid_image(game["grid"], game["words"], game["found"])
    img_bio.seek(0)
    
    caption = "🌐 **WORD GRID CHALLENGE** 🌐\n\nFind these words:\n"
    for w in game["words"].keys():
        if w in game["found"]:
            caption += f"✅ {w}\n"
        else:
            caption += f"{w[0]}{'-' * (len(w)-1)} ({len(w)})\n"
    caption += "\nTap 🔄 Refresh Grid to mark!"
    
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh Grid", callback_data="refresh_grid")]])
    await callback_query.edit_message_media(media=InputMediaPhoto(img_bio, caption=caption), reply_markup=btn)
    await callback_query.answer("Grid Updated!", show_alert=False)

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()

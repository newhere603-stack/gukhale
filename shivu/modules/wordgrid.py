import random
import string
import io
import logging
import requests
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from shivu import application, user_collection

LOGGER = logging.getLogger(__name__)

# Game State Storage
active_games = {}

# ==========================================
# 🛠 100% FOOLPROOF FONT LOADER (Direct to RAM)
# ==========================================
GLOBAL_FONT_BYTES = None

def get_bold_font(size):
    global GLOBAL_FONT_BYTES
    try:
        if GLOBAL_FONT_BYTES is None:
            url = "https://github.com/google/fonts/raw/main/ofl/roboto/Roboto-Bold.ttf"
            response = requests.get(url, timeout=10)
            GLOBAL_FONT_BYTES = response.content
        return ImageFont.truetype(io.BytesIO(GLOBAL_FONT_BYTES), size)
    except Exception as e:
        LOGGER.error(f"RAM Font load failed: {e}")
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except:
            return ImageFont.load_default()

# Massive Word Pool
WORD_LIST = [
    "ACT", "AGE", "AIR", "ALL", "ANT", "ANY", "ARM", "ART", "ASK", "BAD", "BAG", "BAT", "BEE", "BIG", "BOX", "BOY", 
    "BUG", "BUS", "BUT", "BUY", "CAN", "CAR", "CAT", "COW", "CRY", "CUP", "CUT", "DAY", "DOG", "DRY", "EAR", "EAT", 
    "EGG", "END", "EYE", "FAR", "FAT", "FEW", "FIT", "FLY", "FUN", "GAS", "GET", "GOD", "HAT", "HIT", "HOT", "HOW", 
    "HUG", "ICE", "ILL", "INK", "JAM", "JAR", "JOB", "JOY", "KEY", "KID", "LAP", "LAW", "LEG", "LET", "LIP", "LOG", 
    "LOW", "MAD", "MAN", "MAP", "MAT", "MAY", "MEN", "MIX", "MOB", "MUD", "MUG", "NET", "NEW", "NOD", "NOT", "NOW", 
    "NUT", "OAK", "ODD", "OFF", "OLD", "ONE", "OUT", "OWL", "OWN", "PAN", "PAY", "PEG", "PEN", "PET", "PIG", "PIN", 
    "POT", "PRO", "PUT", "RAW", "RED", "RID", "RIP", "ROB", "ROW", "RUB", "RUN", "SAD", "SAY", "SEA", "SEE", "SET", 
    "SHE", "SIT", "SKY", "SON", "SUN", "TAP", "TAX", "TEA", "TEN", "TIE", "TIN", "TIP", "TOE", "TOP", "TOY", "TRY", 
    "TWO", "USE", "VAN", "VET", "WAR", "WAS", "WAY", "WEB", "WET", "WHO", "WHY", "WIN", "YES", "YET", "YOU", "ZOO",
    "ABLE", "ALSO", "AREA", "ARMY", "AWAY", "BABY", "BACK", "BALL", "BAND", "BANK", "BASE", "BATH", "BEAR", "BEAT", 
    "BIRD", "BLOW", "BLUE", "BOAT", "BODY", "BONE", "BOOK", "BORN", "BOTH", "BOWL", "BURN", "BUSH", "BUSY", "CALL", 
    "CALM", "CAMP", "CARE", "CASH", "CAST", "CHAT", "CITY", "CLUB", "COAL", "COAT", "COLD", "COME", "COOK", "COOL", 
    "COPE", "COPY", "CORE", "COST", "CREW", "CROP", "DARK", "DATA", "DATE", "DAWN", "DAYS", "DEAD", "DEAL", "DEAN", 
    "DEAR", "DEBT", "DEEP", "DEER", "DESK", "DIAL", "DIET", "DIRT", "DISH", "DOOR", "DOSE", "DOWN", "DRAW", "DROP", 
    "DRUG", "DUAL", "DUKE", "DUST", "DUTY", "EACH", "EARN", "EAST", "EASY", "EDGE", "ELSE", "EVEN", "EVER", "EVIL", 
    "EXIT", "FACE", "FACT", "FAIL", "FAIR", "FALL", "FARM", "FAST", "FEAR", "FEEL", "FEET", "FILL", "FILM", "FIND", 
    "FINE", "FIRE", "FIRM", "FISH", "FIVE", "FLAT", "FLOW", "FOOD", "FOOT", "FORD", "FORM", "FREE", "FUND", "GAME", 
    "GANG", "GATE", "GIFT", "GIRL", "GLAD", "GOAL", "GOES", "GOLD", "GOLF", "GOOD", "GRAY", "GREY", "GROW", "GULF", 
    "HAIR", "HALF", "HALL", "HAND", "HANG", "HARD", "HARM", "HATE", "HAVE", "HEAD", "HEAR", "HEAT", "HELP", "HERE", 
    "HERO", "HIGH", "HILL", "HOLE", "HOME", "HOPE", "HOST", "HOUR", "IDEA", "INTO", "IRON", "ITEM", "JACK", "JANE", 
    "JEAN", "JOHN", "JOIN", "JUMP", "JURY", "JUST", "KEEN", "KEEP", "KICK", "KILL", "KIND", "KING", "KNEE", "KNEW", 
    "KNOW", "LACK", "LADY", "LAKE", "LAND", "LANE", "LAST", "LATE", "LEAD", "LEFT", "LESS", "LIFE", "LIFT", "LIKE", 
    "LINE", "LINK", "LIST", "LIVE", "LOAD", "LOAN", "LOCK", "LOGO", "LONG", "LOOK", "LORD", "LOSE", "LOSS", "LOST", 
    "LOVE", "LUCK", "MADE", "MAIL", "MAIN", "MAKE", "MALE", "MANY", "MARK", "MASS", "MATT", "MEAL", "MEAN", "MEAT", 
    "MEET", "MENU", "MERE", "MIKE", "MILE", "MILK", "MILL", "MIND", "MINE", "MISS", "MODE", "MOOD", "MOON", "MORE", 
    "MOST", "MOVE", "MUCH", "MUST", "NAME", "NAVY", "NEAR", "NECK", "NEED", "NEWS", "NEXT", "NICE", "NINE", "NONE", 
    "NOSE", "NOTE", "ONLY", "OPEN", "ORAL", "OVER", "PACE", "PACK", "PAGE", "PAID", "PAIN", "PAIR", "PALM", "PARK", 
    "PART", "PASS", "PAST", "PATH", "PEAK", "PICK", "PINE", "PINK", "PIPE", "PLAN", "PLAY", "PLOT", "PLUG", "PLUS", 
    "POEM", "POET", "POOL", "POOR", "PORT", "POST", "PULL", "PURE", "PUSH", "RACE", "RAIL", "RAIN", "RANK", "RARE", 
    "RATE", "READ", "REAL", "REAR", "RELY", "RENT", "REST", "RICE", "RICH", "RIDE", "RING", "RISE", "RISK", "ROAD", 
    "ROCK", "ROLE", "ROLL", "ROOF", "ROOM", "ROOT", "ROSE", "RULE", "RUSH", "SAFE", "SAID", "SAKE", "SALE", "SALT", 
    "SAME", "SAND", "SAVE", "SEAT", "SEED", "SEEK", "SEEM", "SELL", "SEND", "SETT", "SHIP", "SHOE", "SHOP", "SHOT", 
    "SHOW", "SHUT", "SICK", "SIDE", "SIGN", "SITE", "SIZE", "SKIN", "SLIP", "SLOW", "SNOW", "SOFT", "SOIL", "SOLD", 
    "SOLE", "SOME", "SONG", "SOON", "SORT", "SOUL", "SPOT", "STAR", "STAY", "STEP", "STOP", "SUCH", "SUIT", "SURE", 
    "TAKE", "TALE", "TALK", "TALL", "TANK", "TAPE", "TASK", "TEAM", "TEAR", "TELL", "TEND", "TERM", "TEST", "TEXT", 
    "THAN", "THAT", "THEM", "THEN", "THEY", "THIN", "THIS", "THOU", "THUS", "TICK", "TIME", "TINY", "TIRE", "TOLL", 
    "TOMB", "TONE", "TOOL", "TOUR", "TOWN", "TREE", "TRIP", "TRUE", "TUBE", "TURN", "TWIN", "TYPE", "UNIT", "UPON", 
    "USER", "VARY", "VAST", "VERY", "VICE", "VIEW", "VOTE", "WAGE", "WAIT", "WAKE", "WALK", "WALL", "WANT", "WARD", 
    "WARM", "WASH", "WAVE", "WAYS", "WEAK", "WEAR", "WEEK", "WELL", "WENT", "WERE", "WEST", "WHAT", "WHEN", "WHOM", 
    "WIDE", "WIFE", "WILD", "WILL", "WIND", "WINE", "WING", "WIRE", "WISE", "WISH", "WITH", "WOOD", "WORD", "WORK"
]

def generate_game_grid(size=8, num_words=9):
    grid = [['' for _ in range(size)] for _ in range(size)]
    valid_words = [w for w in WORD_LIST if 3 <= len(w) <= size]
    chosen_words = random.sample(valid_words, min(num_words, len(valid_words)))
    placed_words = {}
    directions = [(0, 1), (1, 0), (1, 1), (-1, 1), (-1, -1), (0, -1), (-1, 0), (1, -1)] 
    
    for word in chosen_words:
        placed = False
        for _ in range(250):
            d_r, d_c = random.choice(directions)
            r, c = random.randint(0, size - 1), random.randint(0, size - 1)
            if 0 <= r + d_r * (len(word)-1) < size and 0 <= c + d_c * (len(word)-1) < size:
                if all(grid[r + d_r * i][c + d_c * i] in ['', word[i]] for i in range(len(word))):
                    for i in range(len(word)): grid[r + d_r * i][c + d_c * i] = word[i]
                    placed_words[word] = [(r + d_r * i, c + d_c * i) for i in range(len(word))]
                    placed = True
                    break
        if not placed: continue
    for r in range(size):
        for c in range(size):
            if grid[r][c] == '': grid[r][c] = random.choice(string.ascii_uppercase)
    return grid, placed_words

def create_grid_image(grid, placed_words, found_words):
    cell_size = 100
    size = len(grid)
    img_size = cell_size * size
    img = Image.new('RGBA', (img_size, img_size), color='#0a0a0a') 
    draw = ImageDraw.Draw(img)
    font = get_bold_font(65)

    for r in range(size + 1):
        draw.line([(0, r*cell_size), (img_size, r*cell_size)], fill="#222222", width=3)
        draw.line([(r*cell_size, 0), (r*cell_size, img_size)], fill="#222222", width=3)

    colors = [(60, 150, 120, 180), (180, 70, 70, 180), (60, 150, 60, 180), (130, 90, 180, 180), (180, 140, 50, 180), (60, 100, 200, 180)]
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    for i, word in enumerate(found_words):
        if word in placed_words:
            coords = placed_words[word]
            c1, r1 = coords[0][1] * cell_size + cell_size // 2, coords[0][0] * cell_size + cell_size // 2
            c2, r2 = coords[-1][1] * cell_size + cell_size // 2, coords[-1][0] * cell_size + cell_size // 2
            color = colors[i % len(colors)]
            line_width = 70
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
            bbox = font.getbbox(letter)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            draw.text((x0 + (cell_size - w) / 2 - bbox[0], y0 + (cell_size - h) / 2 - bbox[1]), letter, fill="#ffffff", font=font)

    img = img.convert("RGB")
    bio = io.BytesIO(); img.save(bio, format='PNG'); bio.name = 'grid.png'; return bio

def get_sorted_caption(placed_words, found_words):
    caption = "<tg-emoji emoji-id=\"5224450179368767019\">🌎</tg-emoji> <b>WORD GRID CHALLENGE</b> <tg-emoji emoji-id=\"5224450179368767019\">🌎</tg-emoji>\n\nFind these words:\n"
    for w in sorted(placed_words.keys(), key=len):
        if w in found_words:
            caption += f"<tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji> {w}\n"
        else:
            caption += f"{w[0] + '-' * (len(w) - 1)} ({len(w)})\n"
    caption += "\nTap <tg-emoji emoji-id=\"5260491539167073671\">🔄</tg-emoji> Refresh Grid to mark!"
    return caption

# --- HANDLERS ---
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in active_games: return await update.message.reply_text("<tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> Game already running!")
    grid, placed_words = generate_game_grid()
    active_games[chat_id] = {"grid": grid, "words": placed_words, "found": [], "msg_id": None, "round_scores": {}}
    img = create_grid_image(grid, placed_words, [])
    msg = await context.bot.send_photo(chat_id, img, caption=get_sorted_caption(placed_words, []), parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Refresh Grid", callback_data="refresh_grid")]]))
    active_games[chat_id]["msg_id"] = msg.message_id

async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in active_games:
        del active_games[chat_id]
        await update.message.reply_text("<tg-emoji emoji-id=\"6310066608689650607\">⬅️</tg-emoji> <b>WordGrid game stopped.</b>", parse_mode="HTML")

async def handle_guesses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_games: return
    game = active_games[chat_id]
    guess = update.message.text.upper().strip()
    if guess in game["words"] and guess not in game["found"]:
        game["found"].append(guess)
        points = len(guess) * 2
        await user_collection.update_one({"id": update.effective_user.id}, {"$inc": {"grid_points": points}}, upsert=True)
        img = create_grid_image(game["grid"], game["words"], game["found"])
        await context.bot.edit_message_media(chat_id, game["msg_id"], InputMediaPhoto(img, caption=get_sorted_caption(game["words"], game["found"]), parse_mode="HTML"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Refresh Grid", callback_data="refresh_grid")]]))
        await update.message.reply_text(f"<tg-emoji emoji-id=\"5465626908165163181\">✅</tg-emoji> <b>+{points} pts for {update.effective_user.mention_html()}! Found {guess}.</b>", parse_mode="HTML")
        if len(game["found"]) == len(game["words"]):
            del active_games[chat_id]
            await update.message.reply_text("👾 <b>GAME OVER!</b>")

async def leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor = user_collection.find({"grid_points": {"$gt": 0}}).sort("grid_points", -1).limit(10)
    msg = "🏆 <b>GRID TOP LEADERBOARD</b> 🏆\n\n"
    for i, user in enumerate(await cursor.to_list(length=10), 1):
        msg += f"{['🥇','🥈','🥉'][i-1] if i<=3 else '🏅'} <b>{user.get('first_name', 'Player')}</b> — <code>{user.get('grid_points', 0)} pts</code>\n"
    await update.message.reply_text(msg, parse_mode="HTML")

application.add_handler(CommandHandler(["playgrid", "grid"], start_game))
application.add_handler(CommandHandler(["stopgame", "endgame"], stop_game))
application.add_handler(CommandHandler("gridtop", leaderboard_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_guesses), group=5)
application.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.edit_message_caption(caption=get_sorted_caption(active_games[u.callback_query.message.chat_id]["words"], active_games[u.callback_query.message.chat_id]["found"]), parse_mode="HTML") or u.callback_query.answer(), pattern="refresh_grid"))

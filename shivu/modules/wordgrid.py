import random
import string
import io
import logging
import html
import requests
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from shivu import application, user_collection

LOGGER = logging.getLogger(__name__)

# Game State & Settings Storage
active_games = {}
chat_settings = {}  # Format: {chat_id: {"pin": True, "mark_words": True, "theme": "automatic"}}
stop_votes = {}  # NAYA: Voting track karne ke liye
LOG_GROUP_ID = -1003893927065  # Tumhara private log group

# ==========================================
# 🛠 100% FOOLPROOF FONT LOADER (Error Fixed)
# ==========================================
GLOBAL_FONT_BYTES = None

def get_bold_font(size):
    global GLOBAL_FONT_BYTES
    try:
        if GLOBAL_FONT_BYTES is None:
            # Using direct raw URL to prevent HTML/404 redirects causing "unknown format"
            url = "https://raw.githubusercontent.com/google/fonts/main/ofl/roboto/Roboto-Bold.ttf"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                GLOBAL_FONT_BYTES = response.content
            else:
                raise Exception(f"HTTP Status {response.status_code}")
                
        return ImageFont.truetype(io.BytesIO(GLOBAL_FONT_BYTES), size)
    except Exception as e:
        LOGGER.error(f"RAM Font load failed: {e}")
        GLOBAL_FONT_BYTES = None # Reset so it retries next time
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
    "WIDE", "WIFE", "WILD", "WILL", "WIND", "WINE", "WING", "WIRE", "WISE", "WISH", "WITH", "WOOD", "WORD", "WORK",
    "ABOUT", "ABOVE", "ACTOR", "ACUTE", "ADAPT", "ADMIT", "ADOPT", "ADULT", "AFTER", "AGAIN", "AGENT", "AGREE", "AHEAD",
    "ALARM", "ALBUM", "ALERT", "ALIEN", "ALIKE", "ALIVE", "ALLOW", "ALONE", "ALONG", "ALTER", "AMONG", "ANGER", "ANGLE",
    "ANGRY", "APPLE", "APPLY", "AREAS", "ARENA", "ARGUE", "ARISE", "ARMED", "ARRAY", "ARROW", "ASIAN", "ASIDE", "ASSET",
    "AUDIO", "AUDIT", "AVOID", "AWARD", "AWARE", "BADLY", "BAKER", "BASES", "BASIC", "BASIS", "BEACH", "BEAST", "BEGIN",
    "BEING", "BELOW", "BENCH", "BIRTH", "BLACK", "BLADE", "BLAME", "BLIND", "BLOCK", "BLOOD", "BOARD", "BOAST", "BONUS",
    "BOOST", "BOOTH", "BOUND", "BRAIN", "BRASS", "BRAVE", "BREAD", "BREAK", "BRICK", "BRIEF", "BROAD", "BROKE", "BROWN",
    "BRUSH", "BUILD", "BUNCH", "BUYER", "CABLE", "CARRY", "CATCH", "CAUSE", "CHAIN", "CHAIR", "CHART", "CHASE", "CHEAP",
    "CHECK", "CHIEF", "CHILD", "CHINA", "CHOSE", "CIVIL", "CLAIM", "CLASS", "CLEAN", "CLEAR", "CLERK", "CLICK", "CLOCK",
    "CLOSE", "COACH", "COAST", "COUNT", "COURT", "COVER", "CRAFT", "CRASH", "CREAM", "CRIME", "CROSS", "CROWD", "CROWN",
    "CURVE", "CYCLE", "DAILY", "DANCE", "DEATH", "DELAY", "DEPTH", "DOUBT", "DRAFT", "DRAMA", "DREAM", "DRESS", "DRINK",
    "DRIVE", "EARLY", "EARTH", "EIGHT", "ELITE", "EMPTY", "ENEMY", "ENJOY", "ENTER", "ENTRY", "EQUAL", "ERROR", "EVENT",
    "EXACT", "EXIST", "EXTRA", "FAITH", "FALSE", "FAULT", "FIBER", "FIELD", "FIFTH", "FIFTY", "FIGHT", "FINAL", "FIRST",
    "FIXED", "FLASH", "FLEET", "FLOOR", "FLUID", "FOCUS", "FORCE", "FORUM", "FOUND", "FRAME", "FRANK", "FRAUD", "FRESH",
    "FRONT", "FRUIT", "FULLY", "FUNNY", "GIANT", "GIVEN", "GLASS", "GLOBE", "GOING", "GRACE", "GRADE", "GRAND", "GRANT",
    "GRASS", "GREAT", "GREEN", "GROSS", "GROUP", "GROWN", "GUARD", "GUESS", "GUEST", "GUIDE", "HAPPY", "HEART", "HEAVY",
    "HENCE", "HORSE", "HOTEL", "HOUSE", "HUMAN", "IDEAL", "IMAGE", "INDEX", "INNER", "INPUT", "ISSUE", "JAPAN", "JOINT",
    "JUDGE", "KNOWN", "LABEL", "LARGE", "LASER", "LATER", "LAUGH", "LAYER", "LEARN", "LEASE", "LEAST", "LEAVE", "LEGAL",
    "LEVEL", "LIGHT", "LIMIT", "LINKS", "LIVES", "LOCAL", "LOGIC", "LOOSE", "LOWER", "LUCKY", "MAGIC", "MAJOR", "MAKER",
    "MARCH", "MATCH", "MAYOR", "MEANT", "MEDIA", "METAL", "MIGHT", "MINOR", "MINUS", "MIXED", "MODEL", "MONEY", "MONTH",
    "MORAL", "MOTOR", "MOUNT", "MOUSE", "MOUTH", "MOVIE", "MUSIC", "NEEDS", "NEVER", "NIGHT", "NOISE", "NORTH", "NOTED",
    "NOVEL", "NURSE", "OCCUR", "OCEAN", "OFFER", "OFTEN", "ORDER", "OTHER", "OUGHT", "PAINT", "PANEL", "PAPER", "PARTY",
    "PEACE", "PHASE", "PHONE", "PHOTO", "PIECE", "PILOT", "PITCH", "PLACE", "PLAIN", "PLANE", "PLANT", "PLATE", "POINT",
    "POUND", "POWER", "PRESS", "PRICE", "PRIDE", "PRIME", "PRINT", "PRIOR", "PRIZE", "PROOF", "PROUD", "PROVE", "QUEEN",
    "QUICK", "QUIET", "QUITE", "RADIO", "RAISE", "RANGE", "RAPID", "RATIO", "REACH", "READY", "REFER", "RIGHT", "RIVAL",
    "RIVER", "ROBOT", "ROUGH", "ROUND", "ROUTE", "ROYAL", "RURAL", "SCALE", "SCENE", "SCOPE", "SCORE", "SENSE", "SERVE",
    "SEVEN", "SHALL", "SHAPE", "SHARE", "SHARP", "SHEET", "SHELF", "SHELL", "SHIFT", "SHIRT", "SHOCK", "SHOOT", "SHORT",
    "SHOWN", "SIGHT", "SIXTH", "SKILL", "SLEEP", "SMALL", "SMART", "SMILE", "SMITH", "SMOKE", "SOLID", "SOLVE", "SORRY",
    "SOUND", "SOUTH", "SPACE", "SPARE", "SPEAK", "SPEED", "SPEND", "SPORT", "SQUAD", "STAFF", "STAGE", "STAND", "START",
    "STATE", "STEAM", "STEEL", "STICK", "STILL", "STOCK", "STONE", "STORE", "STORM", "STORY", "STRIP", "STUDY", "STUFF",
    "STYLE", "SUGAR", "SUPER", "SWEET", "TABLE", "TASTE", "TEACH", "TEETH", "TEXAS", "THANK", "THEFT", "THEIR", "THEME",
    "THERE", "THESE", "THICK", "THING", "THINK", "THIRD", "THOSE", "THREE", "THROW", "TIGHT", "TIMES", "TITLE", "TODAY",
    "TOPIC", "TOTAL", "TOUCH", "TOUGH", "TOWER", "TRACK", "TRADE", "TRAIN", "TREAT", "TREND", "TRIAL", "TRUST", "TRUTH",
    "TWICE", "UNDER", "UNDUE", "UNION", "UNITY", "UNTIL", "UPPER", "UPSET", "URBAN", "USAGE", "USUAL", "VALID", "VALUE",
    "VIDEO", "VIRUS", "VISIT", "VITAL", "VOICE", "WASTE", "WATCH", "WATER", "WHEEL", "WHERE", "WHICH", "WHILE", "WHITE",
    "WHOLE", "WHOSE", "WOMAN", "WORDS", "WORLD", "WORRY", "WORSE", "WORST", "WORTH", "WOULD", "WOUND", "WRITE", "WRONG",
    "YIELD", "YOUNG", "ACTION", "ADVICE", "ANIMAL", "ANSWER", "APPEAR", "AROUND", "ARTIST", "ATTACK", "AUTHOR", "BATTLE",
    "BEAUTY", "BECOME", "BEFORE", "BEHIND", "BELIEF", "BELONG", "BOTTLE", "BRANCH", "BREATH", "BRIDGE", "BRIGHT", "BROKEN",
    "BUDGET", "BUTTON", "CAMERA", "CANCER", "CASTLE", "CHANCE", "CHANGE", "CHARGE", "CHOICE", "CHOOSE", "CHURCH", "CIRCLE",
    "CLIENT", "CLOSED", "COFFEE", "COLUMN", "COMBAT", "COMMON", "CORNER", "COURSE", "CREDIT", "CUSTOM", "DAMAGE", "DANGER",
    "DEBATE", "DECIDE", "DEFEND", "DEGREE", "DEMAND", "DEPEND", "DESIGN", "DESIRE", "DETAIL", "DEVICE", "DIFFER", "DINNER",
    "DIRECT", "DIVIDE", "DOCTOR", "DOUBLE", "DRAWER", "DRIVER", "DURING", "EASILY", "EFFECT", "EFFORT", "EITHER", "ENERGY",
    "ENGINE", "ENOUGH", "ENTIRE", "ESCAPE", "ESTATE", "EXCEED", "EXCEPT", "EXPECT", "EXPERT", "EXTEND", "FABRIC", "FACTOR",
    "FAMILY", "FAMOUS", "FARMER", "FATHER", "FIGURE", "FINGER", "FINISH", "FLIGHT", "FLOWER", "FLYING", "FOLLOW", "FOREST",
    "FORGET", "FORMAL", "FORMER", "FRIEND", "FUTURE", "GARDEN", "GATHER", "GENDER", "GENTLE", "GLOBAL", "GOLDEN", "GROUND",
    "GROWTH", "GUILTY", "HANDLE", "HAPPEN", "HEALTH", "HEIGHT", "HIDDEN", "HONEST", "HUNTER", "IGNORE", "IMPACT", "IMPORT",
    "INCOME", "INDEED", "INJURY", "INSIDE", "INTEND", "INVENT", "ISLAND", "ITSELF", "JACKET", "JUNGLE", "LADDER", "LATEST",
    "LEADER", "LEGEND", "LENGTH", "LESSON", "LETTER", "LISTEN", "LITTLE", "LIVING", "LOCKED", "LONELY", "MADAME", "MAIDEN",
    "MANAGE", "MARKET", "MASTER", "MATRIX", "MATTER", "MEMORY", "MENTAL", "METHOD", "MIDDLE", "MIGHTY", "MINUTE", "MIRROR",
    "MODERN", "MOMENT", "MONKEY", "MOTHER", "MOTION", "MURDER", "MUSCLE", "MUSEUM", "MYSTIC", "NATION", "NATIVE", "NATURE",
    "NEARLY", "NINETY", "NOBODY", "NORMAL", "NOTICE", "NUMBER", "OBJECT", "OFFICE", "OPTION", "ORANGE", "ORIGIN", "OUTPUT",
    "PALACE", "PARENT", "PARISH", "PASTEL", "PATENT", "PEOPLE", "PERIOD", "PERSON", "PHRASE", "PLANET", "PLAYER", "PLEASE",
    "POCKET", "POISON", "POLICE", "POLICY", "PROFIT", "PUBLIC", "PULLER", "PUNISH", "PURPLE", "PURSUE", "PUZZLE", "RABBIT",
    "RADIAL", "RANDOM", "RATHER", "RATING", "READER", "REASON", "RECORD", "REDUCE", "REFUSE", "REGION", "REMAIN", "REMIND",
    "REMOVE", "REPAIR", "REPEAT", "REPORT", "RESCUE", "RESIGN", "RESULT", "RETURN", "REVEAL", "REVIEW", "REWARD", "RIDING",
    "ROCKET", "ROLLER", "RUBBER", "RULING", "SACRED", "SAFETY", "SAILOR", "SALARY", "SAMPLE", "SAVING", "SCARED", "SCHOOL",
    "SCREEN", "SEARCH", "SEASON", "SECOND", "SECRET", "SECURE", "SELECT", "SENIOR", "SERIES", "SERVER", "SETTLE", "SEVERE",
    "SHADOW", "SIGNAL", "SILENT", "SILVER", "SIMPLE", "SINGER", "SINGLE", "SISTER", "SKETCH", "SLEEVE", "SLIGHT", "SMOOTH",
    "SOCIAL", "SOCIETY", "SOLDIER", "SOURCE", "SOVIET", "SPEECH", "SPIRIT", "SPOKEN", "SPREAD", "SPRING", "SQUARE", "STATUS",
    "STREAM", "STREET", "STRESS", "STRIKE", "STRING", "STRONG", "STUDIO", "SUBMIT", "SUDDEN", "SUFFER", "SUMMER", "SUMMIT",
    "SUPPLY", "SURELY", "SYMBOL", "SYSTEM", "TACKLE", "TAILOR", "TALENT", "TARGET", "TENNIS", "THANKS", "THEORY", "THIRTY",
    "THOUGH", "THREAD", "THREAT", "TICKET", "TIMBER", "TISSUE", "TOMATO", "TONGUE", "TOWARD", "TRAVEL", "TREATY", "TRIBAL",
    "TROPIC", "TWELVE", "TWENTY", "TYPICAL", "UNIQUE", "UNLESS", "UNLIKE", "USEFUL", "VALLEY", "VICTIM", "VISION", "VISUAL",
    "VOLUME", "WALKER", "WEALTH", "WEAPON", "WEIGHT", "WINDOW", "WINTER", "WONDER", "WORKER", "WRITER", "YELLOW"
]

def get_chat_settings(chat_id):
    if chat_id not in chat_settings:
        chat_settings[chat_id] = {"pin": True, "mark_words": True, "theme": "automatic"}
    return chat_settings[chat_id]

def is_night_ist():
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return not (6 <= ist_now.hour < 18)

def generate_game_grid(mode="normal"):
    if mode == "easy":
        size, num_words = 6, 6
        valid_words = [w for w in WORD_LIST if 3 <= len(w) <= 5]
    elif mode == "hard":
        size, num_words = 10, 12
        valid_words = [w for w in WORD_LIST if 5 <= len(w) <= 8]
    else: # normal
        size, num_words = 8, 9
        valid_words = [w for w in WORD_LIST if 3 <= len(w) <= 7]

    grid = [['' for _ in range(size)] for _ in range(size)]
    chosen_words = random.sample(valid_words, min(num_words, len(valid_words)))
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

    font = get_bold_font(60)

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
            text_x = x0 + (cell_size - w) / 2 - bbox[0]
            text_y = y0 + (cell_size - h) / 2 - bbox[1]
            
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
            caption += f"<tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji> <b>{w}</b>\n"
        else:
            # FORMAT FIX: Screenshot ke according proper space aur dash add kiya
            masked = w[0] + "".join(" -" for _ in range(len(w) - 1))
            caption += f"<b>{masked} &nbsp;&nbsp;({len(w)})</b>\n"
            
    caption += "\n<b>Tap <tg-emoji emoji-id=\"5260491539167073671\">🔄</tg-emoji> Refresh Grid to mark!</b>"
    return caption

def get_msg_link(chat, msg_id):
    if chat.username:
        return f"https://t.me/{chat.username}/{msg_id}"
    else:
        return f"https://t.me/c/{str(chat.id).replace('-100', '', 1)}/{msg_id}"

# Naya function - Admin check karne ke liye (pehle se tha bas thoda adjust kiya gaya hai)
async def is_admin(chat, user_id, bot):
    if chat.type == 'private':
        return True
    member = await bot.get_chat_member(chat.id, user_id)
    return member.status in ['administrator', 'creator']

# --- HANDLERS ---

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("<b>This game can only be played in groups!</b>", parse_mode="HTML")
        return

    chat_id = chat.id
    if chat_id in active_games:
        await update.message.reply_text("<tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> <b>A WordGrid game is already running! Use /stopgame or /endgrid to end it.</b>", parse_mode="HTML")
        return

    cmd = update.message.text.split('@')[0].lower()
    if 'easy' in cmd:
        mode = "easy"
    elif 'hard' in cmd:
        mode = "hard"
    else:
        mode = "normal"

    grid, placed_words = generate_game_grid(mode=mode)
    
    stop_votes.pop(chat_id, None) # NAYA: Purane votes clear karna
    
    active_games[chat_id] = {
        "grid": grid, 
        "words": placed_words, 
        "found": [], 
        "msg_id": None, 
        "round_scores": {},
        "mode": mode
    }

    img_bio = create_grid_image(grid, placed_words, [], chat_id)
    img_bio.seek(0)

    caption = get_sorted_caption(placed_words, [])
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("Refresh Grid", callback_data="refresh_grid")]])
    
    msg = await context.bot.send_photo(chat_id=chat_id, photo=img_bio, caption=caption, parse_mode="HTML", reply_markup=btn)
    active_games[chat_id]["msg_id"] = msg.message_id

    settings = get_chat_settings(chat_id)
    if settings["pin"]:
        try:
            await context.bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id)
        except Exception as e:
            LOGGER.error(f"Failed to pin game message: {e}")
            
    # Send Log to Private Group
    try:
        group_name = html.escape(chat.title)
        game_link = get_msg_link(chat, msg.message_id)
        words_list = ", ".join(placed_words.keys())
        
        log_text = (
            f"🎮 <b>New WordGrid Game Started!</b>\n\n"
            f"🏢 <b>Group:</b> <a href='{game_link}'>{group_name}</a>\n"
            f"🆔 <b>Group ID:</b> <code>{chat_id}</code>\n"
            f"🎚 <b>Mode:</b> {mode.capitalize()} (Total {len(placed_words)} words)\n\n"
            f"📝 <b>Words to guess:</b>\n<code>{words_list}</code>"
        )
        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        LOGGER.error(f"Failed to send game log: {e}")

# NAYA: Stop game modified with voting system
async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    
    if not chat or chat.type not in ["group", "supergroup"]:
        return
        
    chat_id = chat.id
    if chat_id not in active_games:
        await update.message.reply_text("<b><tg-emoji emoji-id=\"6309717264639726942\">⚠️</tg-emoji> No active game running right now.</b>", parse_mode="HTML")
        return

    # Check admin status
    is_adm = await is_admin(chat, user.id, context.bot)
    
    if is_adm:
        del active_games[chat_id]
        stop_votes.pop(chat_id, None)
        await update.message.reply_text("<tg-emoji emoji-id=\"5465626908165163181\">✅</tg-emoji> <b>The active game has been stopped by an admin. Start another with /grid_hard or /grid</b>", parse_mode="HTML")
    else:
        # Start voting process for normal users
        if chat_id not in stop_votes:
            stop_votes[chat_id] = set()
            
        stop_votes[chat_id].add(user.id)
        votes_needed = 3
        current_votes = len(stop_votes[chat_id])
        
        if current_votes >= votes_needed:
            del active_games[chat_id]
            stop_votes.pop(chat_id, None)
            await update.message.reply_text("<tg-emoji emoji-id=\"5465626908165163181\">✅</tg-emoji> <b>The active game has been stopped by community vote (3/3). Start another with /grid_hard or /grid</b>", parse_mode="HTML")
        else:
            btn = InlineKeyboardMarkup([[InlineKeyboardButton(f"Vote to Stop ({current_votes}/{votes_needed})", callback_data="wg_vote_stop")]])
            text = f"<b>🛑 {html.escape(user.first_name)} wants to stop the game.</b>\n\nNon-admins need <b>{votes_needed} votes</b> to stop the game. \n\nClick below to vote!"
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=btn)

# NAYA: Voting callback handler
async def vote_stop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user = update.effective_user
    
    if chat_id not in active_games:
        await query.answer("No active game running!", show_alert=True)
        await query.message.delete()
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
        await query.answer("Game stopped by vote!", show_alert=True)
        await query.edit_message_text("<tg-emoji emoji-id=\"5465626908165163181\">✅</tg-emoji> <b>The active game has been stopped by community vote (3/3). Start another with /grid_hard or /grid</b>", parse_mode="HTML")
    else:
        await query.answer("Vote registered!")
        btn = InlineKeyboardMarkup([[InlineKeyboardButton(f"Vote to Stop ({current_votes}/{votes_needed})", callback_data="wg_vote_stop")]])
        text = f"<b>🛑 Vote to stop the game in progress!</b>\n\nNon-admins need <b>{votes_needed} votes</b> to stop the game.\n\nCurrent Votes: <b>{current_votes}/{votes_needed}</b>"
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=btn)

def calculate_points(mode, is_first, is_last):
    if mode == "easy":
        return 5  # 6 words * 5 = 30 points
    elif mode == "normal":
        return 6 if (is_first or is_last) else 4  # First(6) + 7*(4) + Last(6) = 40 points
    elif mode == "hard":
        return 5 if (is_first or is_last) else 4  # First(5) + 10*(4) + Last(5) = 50 points
    return 4

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
        
        # Calculate strict points dynamically
        points = calculate_points(game["mode"], is_first, is_last)
        
        game["found"].append(guess)
        
        user = update.effective_user
        mention = user.mention_html()
        
        if user.id not in game["round_scores"]:
            game["round_scores"][user.id] = {"mention": mention, "score": 0}
        game["round_scores"][user.id]["score"] += points
        
        try:
            await user_collection.update_one(
                {"id": user.id},
                {"$inc": {"grid_points": points}},
                upsert=True
            )
        except Exception as e:
            LOGGER.error(f"Error updating grid points: {e}")
        
        img_bio = create_grid_image(game["grid"], game["words"], game["found"], chat_id)
        img_bio.seek(0)
        
        caption = get_sorted_caption(game["words"], game["found"])
        btn_refresh = InlineKeyboardMarkup([[InlineKeyboardButton("Refresh Grid", callback_data="refresh_grid")]])
        
        try:
            await context.bot.edit_message_media(
                chat_id=chat_id, message_id=game["msg_id"],
                media=InputMediaPhoto(img_bio, caption=caption, parse_mode="HTML"), reply_markup=btn_refresh
            )
        except Exception:
            pass
            
        link = get_msg_link(chat, game["msg_id"])
        btn_go = InlineKeyboardMarkup([[InlineKeyboardButton("Go to Grid ⤻", url=link)]])

        await message.reply_text(f"<tg-emoji emoji-id=\"5465626908165163181\">✅</tg-emoji> <b>+{points} points for {mention}! You found {guess}.</b>", parse_mode="HTML", reply_markup=btn_go)
        
        if is_last:
            sorted_scores = sorted(game["round_scores"].values(), key=lambda x: x["score"], reverse=True)
            summary = "<tg-emoji emoji-id=\"5233477268617053735\">🕹</tg-emoji><tg-emoji emoji-id=\"5233546451950256512\">🕹</tg-emoji><tg-emoji emoji-id=\"5233604395354047945\">🕹</tg-emoji><tg-emoji emoji-id=\"5233544652358962131\">🕹</tg-emoji><tg-emoji emoji-id=\"5233619423444616550\">🕹</tg-emoji><tg-emoji emoji-id=\"5233286945731267091\">🕹</tg-emoji>\n\n<tg-emoji emoji-id=\"5280939169793732849\">🃏</tg-emoji> <b>Round Summary</b>\n\n"
            medals = ["<tg-emoji emoji-id=\"5440539497383087970\">🥇</tg-emoji>", "<tg-emoji emoji-id=\"5447203607294265305\">🥈</tg-emoji>", "<tg-emoji emoji-id=\"5453902265922376865\">🥉</tg-emoji>", "🏅", "🏅"] 
            for idx, data in enumerate(sorted_scores):
                medal = medals[idx] if idx < len(medals) else "🏅"
                summary += f"{medal} <b>{data['mention']}</b> +<b><code>{data['score']} points</code></b>\n"
            
            summary += "\n<b>Thanks for playing! Start another game by /playgrid.</b>"
            blockquote_summary = f"<blockquote>{summary}</blockquote>"
            
            end_btn = InlineKeyboardMarkup([[InlineKeyboardButton("Ꮮᴇᴀꜰ ꪜɪʟʟᴀɢᴇ", url="https://t.me/Anime_Group_hai")]])
            await context.bot.send_message(chat_id=chat_id, text=blockquote_summary, parse_mode="HTML", reply_markup=end_btn)
            del active_games[chat_id]
            stop_votes.pop(chat_id, None) # NAYA: Votes clear karna last word k baad

async def refresh_grid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    
    if chat_id not in active_games:
        await query.answer("No active game found!", show_alert=True)
        return

    game = active_games[chat_id]
    img_bio = create_grid_image(game["grid"], game["words"], game["found"], chat_id)
    img_bio.seek(0)
    
    caption = get_sorted_caption(game["words"], game["found"])
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("Refresh Grid", callback_data="refresh_grid")]])
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
        [InlineKeyboardButton("↻ Back", callback_data="wg_back_settings")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    
    if not await is_admin(chat, user.id, context.bot):
        await update.message.reply_text("<b>Only admins can change these settings.</b>", parse_mode="HTML")
        return
        
    text = "<tg-emoji emoji-id=\"6307567066572396133\">⚙</tg-emoji> <b>WordGrid Group Settings</b>\n\nManage the bot's behavior in this chat. Only admins can change these settings."
    await update.message.reply_text(text, reply_markup=build_settings_keyboard(chat.id), parse_mode="HTML")

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        
    await query.answer()

async def leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cursor = user_collection.find({"grid_points": {"$gt": 0}}).sort("grid_points", -1).limit(10)
        top_users = await cursor.to_list(length=10)
        
        msg = "<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>GRID TOP LEADERBOARD</b> <tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji>\n\n"
        if not top_users:
            msg += "<b><i>No players on the leaderboard yet! Play WordGrid to score points.</i></b>"
        else:
            medals = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
            for i, user in enumerate(top_users):
                medal = medals[i] if i < len(medals) else "🏅"
                uid = user.get('id')
                name = html.escape(user.get('first_name', 'Player'))
                user_mention = f"<a href='tg://user?id={uid}'>{name}</a>" if uid else f"<b>{name}</b>"
                points = user.get('grid_points', 0)
                msg += f"{medal} <b>{user_mention}</b> - <b><code>{points} pts</code></b>\n"
        
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("Refresh", callback_data="refresh_leaderboard")]])
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=btn)
    except Exception as e:
        LOGGER.error(f"Leaderboard error: {e}")
        await update.message.reply_text("<b><tg-emoji emoji-id=\"6309717264639726942\">⚠️</tg-emoji> Error fetching leaderboard.</b>", parse_mode="HTML")

async def refresh_leaderboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Leaderboard refreshed!")
    try:
        cursor = user_collection.find({"grid_points": {"$gt": 0}}).sort("grid_points", -1).limit(10)
        top_users = await cursor.to_list(length=10)
        
        msg = "<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>GRID TOP LEADERBOARD</b> <tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji>\n\n"
        if not top_users:
            msg += "<b><i>No players on the leaderboard yet! Play WordGrid to score points.</i></b>"
        else:
            medals = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
            for i, user in enumerate(top_users):
                medal = medals[i] if i < len(medals) else "🏅"
                uid = user.get('id')
                name = html.escape(user.get('first_name', 'Player'))
                user_mention = f"<a href='tg://user?id={uid}'>{name}</a>" if uid else f"<b>{name}</b>"
                points = user.get('grid_points', 0)
                msg += f"{medal} <b>{user_mention}</b> - <b><code>{points} pts</code></b>\n"
        
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("Refresh", callback_data="refresh_leaderboard")]])
        await query.edit_message_text(msg, parse_mode="HTML", reply_markup=btn)
    except Exception as e:
        LOGGER.error(f"Leaderboard refresh error: {e}")


# --- REGISTER HANDLERS ---
application.add_handler(CommandHandler(["playgrid", "new_grid", "wordgrid", "grid", "grid_easy", "grid_hard"], start_game))
application.add_handler(CommandHandler(["stopgame", "endgrid"], stop_game))
application.add_handler(CommandHandler(["gridtop", "topgrid"], leaderboard_handler))
application.add_handler(CommandHandler(["helpgrid", "gridsettings"], settings_cmd))

application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_guesses), group=5)
application.add_handler(CallbackQueryHandler(refresh_grid_callback, pattern="^refresh_grid$"))
application.add_handler(CallbackQueryHandler(refresh_leaderboard_callback, pattern="^refresh_leaderboard$"))
# NAYA: Voting pattern handle karega ye niche wala 
application.add_handler(CallbackQueryHandler(vote_stop_callback, pattern="^wg_vote_stop$"))

# Settings Callbacks
application.add_handler(CallbackQueryHandler(settings_callback, pattern="^wg_|ignore"))

__mod_name__ = "WordGrid"
__help__ = """
🎮 <b>WordGrid Game Commands:</b>
- /grid: Start normal mode.
- /grid_easy: Start a smaller, easier board.
- /grid_hard: Start a larger, tougher board.
- /end: Stop the active game.
- /gridtop: View the WordGrid Leaderboard.
- /helpgrid: Manage chat settings for the game.
"""

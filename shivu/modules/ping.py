import random
import logging
from telegram import Update, ReactionTypeEmoji
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes

from shivu import application, user_collection

LOGGER = logging.getLogger(__name__)

# --- MASSIVE UNLIMITED WORD LISTS ---
WORDS_4 = [
    "ABLE", "ACID", "AQUA", "ATOM", "BABY", "BACK", "BAKE", "BALL", "BAND", "BANK", "BASE", "BATH", "BEAR", "BEAT",
    "BELL", "BIRD", "BITE", "BLUE", "BOAT", "BODY", "BONE", "BOOK", "BORN", "BOSS", "BOWL", "BUMP", "BURN", "BUSH", 
    "CAKE", "CALL", "CALM", "CAMP", "CARD", "CARE", "CASE", "CASH", "CELL", "CHAT", "CITY", "CLUB", "COAL", "COAT", 
    "CODE", "COLD", "COME", "COOK", "COOL", "COPY", "CORE", "COST", "CREW", "CRIB", "DARK", "DART", "DATA", "DATE", 
    "DAWN", "DAYS", "DEAD", "DEAL", "DEAR", "DEEP", "DEER", "DESK", "DIET", "DIRT", "DISH", "DOOR", "DOWN", "DRAW", 
    "DROP", "DRUG", "DUCK", "DUST", "DUTY", "EACH", "EARN", "EASE", "EAST", "EASY", "ECHO", "EDGE", "EDIT", "EPIC",
    "EVEN", "EVER", "EXAM", "EXIT", "FACE", "FACT", "FAIL", "FAIR", "FALL", "FARM", "FAST", "FEAR", "FEED", "FEEL", 
    "FEET", "FILE", "FILL", "FILM", "FIND", "FINE", "FIRE", "FIRM", "FISH", "FIVE", "FLAT", "FLIP", "FLOW", "FOOD", 
    "FOOT", "FORM", "FREE", "FROG", "FROM", "FUEL", "FULL", "FUND", "GAIN", "GAME", "GATE", "GIFT", "GIRL", "GIVE", 
    "GLAD", "GLOW", "GOAL", "GOLD", "GOLF", "GOOD", "GRAY", "GROW", "HAIR", "HALF", "HALL", "HAND", "HANG", "HARD", 
    "HARM", "HATE", "HAVE", "HAWK", "HEAD", "HEAR", "HEAT", "HELL", "HELP", "HERE", "HERO", "HIGH", "HILL", "HIRE", 
    "HOLD", "HOLE", "HOME", "HOPE", "HOST", "HOUR", "HUGE", "HUNT", "HURT", "IDEA", "INCH", "IRON", "ITEM", "JOIN",
    "JOKE", "JUMP", "JUST", "KEEP", "KICK", "KILL", "KIND", "KING", "KISS", "KITE", "KNOW", "LACK", "LADY", "LAKE", 
    "LAND", "LATE", "LEAD", "LEAF", "LEFT", "LESS", "LIFE", "LIFT", "LIKE", "LINE", "LINK", "LION", "LIST", "LIVE", 
    "LOAD", "LOAN", "LOCK", "LONG", "LOOK", "LORD", "LOSE", "LOSS", "LOST", "LOUD", "LOVE", "LUCK", "MADE", "MAIL", 
    "MAIN", "MAKE", "MALE", "MANY", "MARK", "MASS", "MEAL", "MEAN", "MEAT", "MEET", "MENU", "MILE", "MILK", "MIND", 
    "MINE", "MODE", "MOON", "MORE", "MOST", "MOVE", "MUCH", "MUST", "MYTH", "NAME", "NEAR", "NECK", "NEED", "NEWS", 
    "NEXT", "NICE", "NINE", "NONE", "NOSE", "NOTE", "ONLY", "OPEN", "OVEN", "OVER", "PACE", "PACK", "PAGE", "PAIN", 
    "PAIR", "PARK", "PART", "PASS", "PAST", "PATH", "PLAN", "PLAY", "PLUM", "PLUS", "POEM", "POOL", "POOR", "PORT", 
    "POST", "PULL", "PURE", "PUSH", "RACE", "RAIN", "RATE", "READ", "REAL", "RENT", "REST", "RICE", "RICH", "RIDE", 
    "RING", "RISE", "RISK", "ROAD", "ROCK", "ROLE", "ROLL", "ROOF", "ROOM", "ROOT", "ROSE", "RULE", "RUSH", "SAFE", 
    "SALE", "SALT", "SAME", "SAND", "SAVE", "SEAT", "SEED", "SEEK", "SELL", "SEND", "SHIP", "SHOP", "SHOW", "SHUT", 
    "SICK", "SIDE", "SIGN", "SILK", "SING", "SINK", "SITE", "SIZE", "SKIN", "SLIP", "SLOW", "SNOW", "SOFT", "SOIL", 
    "SOLD", "SOME", "SONG", "SOON", "SORT", "SOUL", "SOUP", "SPIN", "SPOT", "STAR", "STAY", "STEP", "STOP", "SUCH", 
    "SUIT", "SURE", "TAKE", "TALE", "TALK", "TALL", "TANK", "TAPE", "TASK", "TEAM", "TECH", "TELL", "TEND", "TERM", 
    "TEST", "TEXT", "THAN", "THAT", "THEM", "THEN", "THEY", "THIN", "THIS", "THUS", "TIME", "TINY", "TOOL", "TOUR", 
    "TOWN", "TREE", "TRIP", "TRUE", "TUBE", "TURN", "TWIN", "UNIT", "USER", "VAST", "VOTE", "WAIT", "WAKE", "WALK", 
    "WALL", "WANT", "WARM", "WASH", "WAVE", "WEAK", "WEAR", "WEEK", "WELL", "WEST", "WHAT", "WHEN", "WIDE", "WIFE", 
    "WILD", "WILL", "WIND", "WINE", "WING", "WIRE", "WISE", "WISH", "WITH", "WOOD", "WORD", "WORK", "YARD", "YEAR", 
    "YOUR", "ZERO", "ZINC", "ZONE", "ZOOM"
]

WORDS_5 = [
    "ABOUT", "ABOVE", "ACTOR", "ADMIT", "ADULT", "AFTER", "AGAIN", "AGENT", "AGREE", "AHEAD", "ALARM", "ALBUM", 
    "ALERT", "ALIEN", "ALIKE", "ALIVE", "ALLOW", "ALONE", "ALONG", "ALTER", "AMONG", "ANGER", "ANGLE", "ANGRY", 
    "APART", "APPLE", "APPLY", "ARENA", "ARGUE", "ARISE", "ARMOR", "ARMY", "ASIDE", "ASSET", "AUDIO", "AUDIT", 
    "AVOID", "AWAKE", "BACON", "BADGE", "BADLY", "BAKER", "BASIC", "BASIS", "BEACH", "BEAST", "BEGIN", "BEING", 
    "BELOW", "BENCH", "BINGO", "BIRTH", "BLACK", "BLADE", "BLAME", "BLANK", "BLAST", "BLEND", "BLESS", "BLIND", 
    "BLINK", "BLOCK", "BLOOD", "BOARD", "BOAST", "BONDS", "BONES", "BOOST", "BOOTH", "BOUND", "BOXER", "BRAIN", 
    "BRAND", "BRASS", "BRAVE", "BREAD", "BREAK", "BREED", "BRIEF", "BRING", "BRISK", "BROAD", "BROKE", "BROWN", 
    "BRUSH", "BUDDY", "BUDGET", "BUILD", "BUNCH", "BURST", "BUYER", "CABIN", "CABLE", "CAMEL", "CANAL", "CANDY", 
    "CANON", "CARGO", "CARRY", "CARVE", "CATCH", "CATER", "CAUSE", "CHAIN", "CHAIR", "CHALK", "CHAMP", "CHANT", 
    "CHAOS", "CHARM", "CHART", "CHASE", "CHEAP", "CHEAT", "CHECK", "CHEEK", "CHEER", "CHESS", "CHEST", "CHICK", 
    "CHIEF", "CHILD", "CHILL", "CHINA", "CHOSE", "CIGAR", "CLAIM", "CLAMP", "CLASH", "CLASS", "CLEAN", "CLEAR", 
    "CLERK", "CLICK", "CLIFF", "CLIMB", "CLOCK", "CLONE", "CLOSE", "CLOTH", "CLOUD", "CLOWN", "COACH", "COAST", 
    "COCOA", "COLON", "COLOR", "COMET", "COMIC", "CORAL", "COUCH", "COUGH", "COULD", "COUNT", "COURT", "COVER", 
    "CRACK", "CRAFT", "CRANE", "CRASH", "CRATE", "CRAWL", "CRAZY", "CREAM", "CREEK", "CREEP", "CRIME", "CRISP", 
    "CROSS", "CROWD", "CROWN", "CRUSH", "CRUST", "CRYPT", "CUBIC", "CURVE", "CYCLE", "DADDY", "DAILY", "DANCE", 
    "DEBUT", "DECAY", "DELAY", "DELTA", "DENSE", "DEPOT", "DEPTH", "DERBY", "DETER", "DEVIL", "DIARY", "DIGIT", 
    "DIRTY", "DISCO", "DITCH", "DIVER", "DIZZY", "DODGE", "DONOR", "DONUT", "DOUBT", "DOUGH", "DRAFT", "DRAIN", 
    "DRAMA", "DRANK", "DRAWN", "DREAM", "DRESS", "DRIFT", "DRILL", "DRINK", "DRIVE", "DROVE", "DROWN", "DRUM", 
    "DRUNK", "DUSTY", "DUTCH", "DWARF", "EAGER", "EAGLE", "EARLY", "EARTH", "EIGHT", "ELBOW", "ELDER", "ELECT", 
    "ELITE", "EMPTY", "ENACT", "ENEMY", "ENJOY", "ENTER", "ENTRY", "ENVY", "EQUAL", "EQUIP", "ERASE", "ERUPT", 
    "ESSAY", "ETHIC", "EVENT", "EVERY", "EVICT", "EXACT", "EXCEL", "EXIST", "EXPEL", "EXTRA", "FAINT", "FAIRY", 
    "FAITH", "FALSE", "FANCY", "FATAL", "FAULT", "FEAST", "FENCE", "FERRY", "FETCH", "FEVER", "FIBER", "FIELD", 
    "FIFTH", "FIFTY", "FIGHT", "FILTH", "FINAL", "FIRST", "FJORD", "FLAKE", "FLAME", "FLASH", "FLASK", "FLEET", 
    "FLESH", "FLICK", "FLOAT", "FLOCK", "FLOOD", "FLOOR", "FLORA", "FLOUR", "FLUFF", "FLUID", "FLUSH", "FLYER", 
    "FOCAL", "FOCUS", "FORCE", "FORUM", "FOUND", "FRAME", "FRAUD", "FRESH", "FRIED", "FRONT", "FROST", "FRUIT", 
    "FUNNY", "GHOST", "GIANT", "GIVEN", "GLASS", "GLOBE", "GLORY", "GLOVE", "GRACE", "GRADE", "GRAND", "GRANT", 
    "GRAPE", "GRAPH", "GRASP", "GRASS", "GRAVE", "GREAT", "GREED", "GREEN", "GREET", "GRIEF", "GRILL", "GRIND", 
    "GRIP", "GROUP", "GROVE", "GROWN", "GUARD", "GUESS", "GUEST", "GUIDE", "GUILT", "HABIT", "HAPPY", "HARSH", 
    "HEART", "HEAVY", "HELLO", "HONEY", "HORSE", "HOTEL", "HOUSE", "HUMAN", "HUMOR", "IDEAL", "IGLOO", "IMAGE", 
    "INDEX", "INNER", "INPUT", "ISSUE", "JELLY", "JOINT", "JUDGE", "JUICE", "KNIFE", "KNOCK", "LABEL", "LABOR", 
    "LARGE", "LASER", "LATER", "LAUGH", "LAYER", "LEARN", "LEASE", "LEAST", "LEAVE", "LEGAL", "LEMON", "LEVEL", 
    "LIGHT", "LIMIT", "LOCAL", "LOGIC", "LOOSE", "LUCKY", "LUNCH", "MAGIC", "MAJOR", "MAKER", "MARCH", "MATCH", 
    "MAYOR", "MEDIA", "METAL", "METER", "MINOR", "MODEL", "MONEY", "MONTH", "MORAL", "MOTOR", "MOUNT", "MOUSE", 
    "MOUTH", "MOVIE", "MUSIC", "NAKED", "NIGHT", "NOISE", "NORTH", "NOVEL", "NURSE", "OCCUR", "OCEAN", "OFFER", 
    "OFTEN", "ONION", "ORDER", "OTHER", "OUGHT", "PAINT", "PANEL", "PAPER", "PARTY", "PEACE", "PHASE", "PHONE", 
    "PHOTO", "PIECE", "PILOT", "PITCH", "PLACE", "PLAIN", "PLANE", "PLANT", "PLATE", "PLAZA", "POINT", "POUND", 
    "POWER", "PRESS", "PRICE", "PRIDE", "PRIME", "PRINT", "PRIOR", "PRIZE", "PROOF", "PROUD", "PRUNE", "PROVE", 
    "QUEEN", "QUICK", "QUIET", "QUITE", "RADIO", "RAISE", "RANGE", "RAPID", "RATIO", "REACH", "READY", "REFER", 
    "RIGHT", "RIVAL", "RIVER", "ROUGH", "ROUND", "ROUTE", "ROYAL", "RURAL", "SADLY", "SCALE", "SCENE", "SCOPE", 
    "SCORE", "SENSE", "SERVE", "SEVEN", "SHALL", "SHAPE", "SHARE", "SHARP", "SHEET", "SHELF", "SHELL", "SHIFT", 
    "SHIRT", "SHOCK", "SHOOT", "SHORT", "SHOWN", "SIGHT", "SKILL", "SLEEP", "SMALL", "SMART", "SMILE", "SMITH", 
    "SMOKE", "SOLID", "SOLVE", "SORRY", "SOUND", "SOUTH", "SPACE", "SPARE", "SPEAK", "SPEED", "SPEND", "SPORT", 
    "SQUAD", "STAFF", "STAGE", "STAND", "START", "STATE", "STEAM", "STEEL", "STICK", "STILL", "STOCK", "STONE", 
    "STORE", "STORM", "STORY", "STRIP", "STUDY", "STUFF", "STYLE", "SUGAR", "SUPER", "SWEET", "TABLE", "TASTE", 
    "TEACH", "TENSE", "TERMS", "THANK", "THEFT", "THEIR", "THEME", "THERE", "THESE", "THICK", "THING", "THINK", 
    "THIRD", "THOSE", "THREE", "THROW", "TIGER", "TITLE", "TODAY", "TOPIC", "TOTAL", "TOUCH", "TOUGH", "TOWER", 
    "TRACK", "TRADE", "TRAIN", "TREAT", "TREND", "TRIAL", "TRIBE", "TRICK", "TRUCK", "TRULY", "TRUST", "TRUTH", 
    "TUTOR", "UNCLE", "UNDER", "UNION", "UNTIL", "UPPER", "UPSET", "URBAN", "USAGE", "USUAL", "VALID", "VALUE", 
    "VIDEO", "VIRUS", "VISIT", "VITAL", "VOICE", "WATER", "WEALTH", "WHERE", "WHICH", "WHILE", "WHITE", "WHOLE", 
    "WOMAN", "WORLD", "WORRY", "WORSE", "WORST", "WORTH", "WOULD", "WOUND", "WRONG", "YIELD", "YOUNG", "YOUTH", 
    "ZEBRA", "ZESTY"
]

WORDS_6 = [
    "ABSORB", "ACTION", "ACTIVE", "ACTUAL", "ADVICE", "ADVISE", "AFFECT", "AGENCY", "AGENDA", "ALMOST", "ALWAYS", 
    "AMOUNT", "ANIMAL", "ANSWER", "ANYONE", "ANYWAY", "APPEAL", "APPEAR", "AROUND", "ARRIVE", "ARTIST", "ASPECT", 
    "ASSESS", "ASSIST", "ASSUME", "ATTACK", "ATTEND", "AUTHOR", "AVENUE", "BAKING", "BATTLE", "BEAUTY", "BECOME", 
    "BEFORE", "BEHALF", "BEHIND", "BELIEF", "BELONG", "BESIDE", "BETTER", "BEYOND", "BISHOP", "BORDER", "BOTTLE", 
    "BOTTOM", "BOUNCE", "BRANCH", "BREATH", "BRIDGE", "BRIGHT", "BROKEN", "BUDGET", "BURDEN", "BUREAU", "BUTTON", 
    "CAMERA", "CANCER", "CANDID", "CANVAS", "CARBON", "CAREER", "CASTLE", "CASUAL", "CAUGHT", "CENTER", "CHAMBER", 
    "CHANCE", "CHANGE", "CHARGE", "CHEESE", "CHERRY", "CHOICE", "CHOOSE", "CHORUS", "CIRCLE", "CIRCUS", "CLIENT", 
    "CLINIC", "CLOSED", "CLOSET", "COFFEE", "COLDLY", "COLLEGE", "COLUMN", "COMBAT", "COMEDY", "COMMIT", "COMMON", 
    "COMPEL", "COMPLY", "CONFER", "COOPER", "CORNER", "CORPUS", "COSTLY", "COUNTY", "COUPLE", "COURSE", "COUSIN", 
    "COVERS", "CREATE", "CREDIT", "CRISIS", "CRITIC", "CROWN", "CUSTOM", "DAMAGE", "DANGER", "DARING", "DEBATE", 
    "DECADE", "DECIDE", "DECREE", "DEFEND", "DEFINE", "DEGREE", "DEMAND", "DEPEND", "DEPUTY", "DERIVE", "DESIGN", 
    "DESIRE", "DETAIL", "DETECT", "DEVICE", "DIFFER", "DINNER", "DIRECT", "DIVIDE", "DOCTOR", "DOLLAR", "DOMAIN", 
    "DOUBLE", "DRAGON", "DRAWER", "DREAMY", "DRIVEN", "DRIVER", "DURING", "EASILY", "EATING", "EDITOR", "EFFECT", 
    "EFFORT", "EIGHTH", "EITHER", "ELEVEN", "EMERGE", "EMPIRE", "EMPLOY", "ENABLE", "ENERGY", "ENGAGE", "ENGINE", 
    "ENOUGH", "ENSURE", "ENTIRE", "ENTITY", "EQUITY", "ESCAPE", "ESTATE", "ETHICS", "EXCEED", "EXCEPT", "EXCESS", 
    "EXPAND", "EXPECT", "EXPERT", "EXPORT", "EXTENT", "FABRIC", "FACING", "FACTOR", "FAILED", "FAIRLY", "FALLEN", 
    "FAMILY", "FAMOUS", "FATHER", "FELLOW", "FEMALE", "FIGURE", "FILLER", "FILTER", "FINISH", "FIRM", "FLIGHT", 
    "FLOWER", "FOLLOW", "FOREST", "FORGET", "FORMAL", "FORMAT", "FORMER", "FOSTER", "FOURTH", "FRENCH", "FRIEND", 
    "FUTURE", "GARDEN", "GATHER", "GENDER", "GENIUS", "GENTLE", "GLOBAL", "GOLDEN", "GROUND", "GROWTH", "GUILTY", 
    "GUITAR", "HAMMER", "HANDLE", "HAPPEN", "HARDLY", "HEALTH", "HEAVEN", "HEIGHT", "HIDDEN", "HOLDER", "HONEST", 
    "HORROR", "HUNTER", "IGNORE", "IMPACT", "IMPORT", "INCOME", "INDOOR", "INFANT", "INFORM", "INJURY", "INSECT", 
    "INSIDE", "INTEND", "INTENT", "INVEST", "ISLAND", "ITSELF", "JERSEY", "JUNGLE", "JUNIOR", "JUSTLY", "KILLED", 
    "LADDER", "LARGELY", "LATEST", "LAUNCH", "LAWYER", "LEADER", "LEAGUE", "LEAVES", "LEGACY", "LENGTH", "LESSON", 
    "LETTER", "LISTEN", "LITTLE", "LIVING", "LOCATE", "LOCKED", "LONELY", "LOSING", "LOUNGE", "LOVING", "MAINLY", 
    "MAKEUP", "MAKING", "MANAGE", "MANNER", "MANUAL", "MARGIN", "MARKET", "MASTER", "MATRIX", "MATTER", "MEDIUM", 
    "MEMORY", "MENTAL", "METHOD", "MIDDLE", "MINING", "MINUTE", "MIRROR", "MOBILE", "MODERN", "MODEST", "MODULE", 
    "MOMENT", "MORALS", "MOTHER", "MOTION", "MOTIVE", "MURDER", "MUSCLE", "MUSEUM", "MUTUAL", "MYSELF", "NARROW", 
    "NATION", "NATIVE", "NATURE", "NEARLY", "NEEDED", "NEPHEW", "NERVES", "NEWEST", "NIGHTS", "NORMAL", "NOTICE", 
    "NUMBER", "NURSER", "OBJECT", "OBTAIN", "OFFICE", "OFFSET", "ONLINE", "OPENLY", "OPPOSE", "OPTION", "ORANGE", 
    "ORIGIN", "OUTPUT", "OWNERS", "OXFORD", "PACKET", "PALACE", "PARENT", "PARISH", "PARLOR", "PARROT", "PASSES", 
    "PASTOR", "PATENT", "PATROL", "PATRON", "PAYING", "PEANUT", "PENCIL", "PEOPLE", "PEPPER", "PERIOD", "PERMIT", 
    "PERSON", "PHRASE", "PILLAR", "PLANET", "PLAQUE", "PLEASE", "PLEDGE", "PLENTY", "POCKET", "POETRY", "POISON", 
    "POLICE", "POLICY", "POLISH", "POLITE", "POORLY", "POSTAL", "POTATO", "POWDER", "PRAISE", "PRAYER", "PREFER", 
    "PRETTY", "PRIEST", "PRINCE", "PRISON", "PROFIT", "PROMPT", "PROPER", "PROVEN", "PUBLIC", "PULLEN", "PUNISH", 
    "PUPILS", "PURITY", "PURPLE", "PURSUE", "PUZZLE", "QUOTES", "RABBIT", "RACISM", "RADIAL", "RADIUS", "RATHER", 
    "RATING", "READER", "REALLY", "REASON", "REBEL", "RECALL", "RECENT", "RECIPE", "RECORD", "REDUCE", "REFINE", 
    "REFORM", "REFUGE", "REFUND", "REFUSE", "REGARD", "REGION", "REGRET", "REJECT", "RELATE", "RELIEF", "REMAIN", 
    "REMIND", "REMOTE", "REMOVE", "REPAIR", "REPEAT", "REPLAY", "REPORT", "RESCUE", "RESIGN", "RESIST", "RESULT", 
    "RETAIL", "RETAIN", "RETURN", "REVEAL", "REVIEW", "REWARD", "RHYTHM", "RIBBON", "RIDING", "ROBUST", "ROCKET", 
    "ROLLIN", "ROUTER", "RUBBER", "RULING", "RUNNER", "SACRED", "SADDLE", "SAFETY", "SAILOR", "SALARY", "SAMPLE", 
    "SAVING", "SAYING", "SCARCE", "SCHEME", "SCHOOL", "SCREEN", "SEARCH", "SEASON", "SECOND", "SECRET", "SECURE", 
    "SEEING", "SELECT", "SENATE", "SENIOR", "SENSES", "SERIES", "SERVER", "SETTLE", "SEVERE", "SEXUAL", "SHADES", 
    "SHADOW", "SHAKEN", "SHARED", "SHARES", "SHIELDS", "SHIRTS", "SHOOT", "SHOULD", "SHOWED", "SHRIMP", "SIGNAL", 
    "SILENT", "SILVER", "SIMPLE", "SIMPLY", "SINGER", "SINGLE", "SISTER", "SKILLS", "SLEEVE", "SLIGHT", "SLOWLY", 
    "SMILES", "SMOOTH", "SOCIAL", "SOCIETY", "SOFTLY", "SOIL", "SOLVER", "SORROW", "SOURCE", "SOVIET", "SPEECH", 
    "SPEEDY", "SPIDER", "SPIRIT", "SPOKEN", "SPORTS", "SPOUSE", "SPRING", "SQUARE", "STABLE", "STATUS", "STEADY", 
    "STOLEN", "STRAIN", "STREET", "STRESS", "STRICT", "STRIKE", "STRING", "STRONG", "STUDIO", "STUPID", "SUBMIT", 
    "SUDDEN", "SUFFER", "SUMMER", "SUMMIT", "SUPPLY", "SURELY", "SURVEY", "SWITCH", "SYMBOL", "SYSTEM", "TACKLE", 
    "TAILOR", "TAKING", "TALENT", "TARGET", "TAUGHT", "TEFLON", "TEMPER", "TEMPLE", "TENANT", "TENDER", "TENNIS", 
    "TENTH", "TERROR", "TESTER", "THANKS", "THEORY", "THINGS", "THIRTY", "THOUGH", "THREAT", "THRILL", "TICKET", 
    "TIMBER", "TISSUE", "TOILET", "TOMATO", "TONGUE", "TRADED", "TRAGIC", "TRAILS", "TRAINS", "TRAUMA", "TRAVEL", 
    "TREATY", "TRENDS", "TRIBAL", "TRICKS", "TRUCKS", "TRUSTS", "TRUTHS", "TUNNEL", "TURKEY", "TWELVE", "TWENTY", 
    "TYPICAL", "UNABLE", "UNFAIR", "UNIONS", "UNIQUE", "UNITED", "UNLESS", "UNLIKE", "UNLOCK", "UNPAID", "UNSEEN", 
    "UNSURE", "UPDATE", "URGENT", "USEFUL", "VALLEY", "VALUES", "VANISH", "VAULTS", "VECTOR", "VELVET", "VERBAL", 
    "VESSEL", "VICTIM", "VIEWER", "VIKING", "VILLAGE", "VIRTUE", "VISION", "VISUAL", "VOICES", "VOLUME", "WAKING", 
    "WALNUT", "WANDER", "WANTED", "WARMTH", "WARNIN", "WEALTH", "WEAPON", "WEAVER", "WEEKLY", "WEIGHT", "WIDELY", 
    "WINDOW", "WINNER", "WINTER", "WIRING", "WISDOM", "WONDER", "WORKER", "WRITER", "WRITTEN", "YELLOW", "ZIGZAG", 
    "ZIPPER"
]

ACTIVE_GAMES = {}
DELETE_SETTINGS = {}
REACTION_EMOJIS = ["🔥", "👍", "❤️", "🎉", "🤩", "⚡", "🏆", "👏", "😎", "💘", "💯", "👌", "❤️‍🔥", "🎯"]

# --- WORD SEEK GAME LOGIC ---

def get_wordle_hints(guess: str, target: str) -> str:
    length = len(target)
    result = ["🟥"] * length
    target_chars = list(target)
    guess_chars = list(guess)

    for i in range(length):
        if guess_chars[i] == target_chars[i]:
            result[i] = "🟩"
            target_chars[i] = None
            guess_chars[i] = None

    for i in range(length):
        if guess_chars[i] is not None:
            if guess_chars[i] in target_chars:
                result[i] = "🟨"
                target_chars[target_chars.index(guess_chars[i])] = None

    return "".join(result)

async def toggle_delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return
    chat_id = update.effective_chat.id
    current_status = DELETE_SETTINGS.get(chat_id, False)
    NEW_STATUS = not current_status
    DELETE_SETTINGS[chat_id] = NEW_STATUS
    status_text = "ENABLED 🗑️" if NEW_STATUS else "DISABLED 🛡️"
    await update.message.reply_text(f"<b>Auto-Delete is now: {status_text}</b>", parse_mode="HTML")

async def start_game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message:
        return
    chat_id = update.effective_chat.id

    if chat_id in ACTIVE_GAMES:
        await update.message.reply_text("<b>There is already a game in progress in this chat. Use /end to end it.</b>", parse_mode="HTML")
        return

    command = update.message.text.split()[0].lower()
    length = 5
    if "4" in command:
        length = 4
    elif "6" in command:
        length = 6
    elif context.args:
        try:
            arg = int(context.args[0])
            if arg in [4, 5, 6]:
                length = arg
        except ValueError:
            pass

    target = random.choice(WORDS_4 if length == 4 else (WORDS_6 if length == 6 else WORDS_5))
    ACTIVE_GAMES[chat_id] = {"target": target, "length": length, "guesses": [], "max_attempts": 30, "message_id": None}

    try:
        msg = await update.message.reply_text(f"<b>Game started! Guess the {length}-letter word!</b>", parse_mode="HTML")
        ACTIVE_GAMES[chat_id]["message_id"] = msg.message_id
    except Exception as e:
        LOGGER.error(f"Error starting game: {e}")

async def end_game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return
    chat_id = update.effective_chat.id
    if chat_id in ACTIVE_GAMES:
        target = ACTIVE_GAMES[chat_id]["target"]
        del ACTIVE_GAMES[chat_id]
        await update.message.reply_text(f"<b>🛑 Game ended. The word was: {target.lower()}</b>", parse_mode="HTML")
    else:
        await update.message.reply_text("<b>ℹ️ No active game running.</b>", parse_mode="HTML")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("<b>WordSeek Help Menu</b>\nCommands: /new, /new4, /new5, /new6, /end, /toggledelete", parse_mode="HTML")

async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    if chat_id not in ACTIVE_GAMES:
        return

    text = update.message.text.strip().upper()
    game = ACTIVE_GAMES[chat_id]
    length = game["length"]

    valid_list = WORDS_4 if length == 4 else (WORDS_6 if length == 6 else WORDS_5)
    
    # Strict validation: Agar length match nahi karti ya word valid list mein nahi hai, toh message bhej kar alert karega
    if len(text) != length or not text.isalpha() or text not in valid_list:
        if len(text) == length:
            await update.message.reply_text(f"<b>{text.lower()} is not a valid {length}-letter word.</b>", parse_mode="HTML")
        return

    target = game["target"]
    feedback = get_wordle_hints(text, target)

    game["guesses"].append((feedback, text))
    attempt_num = len(game["guesses"])

    board_lines = [f"<b>{length}-letter mode · {attempt_num}/{game['max_attempts']}</b>\n"]
    for fb, guess_word in game["guesses"]:
        board_lines.append(f"{fb} <b>{guess_word}</b>")

    board_text = "\n".join(board_lines)
    won = (text == target)
    lost = (attempt_num >= game["max_attempts"] and not won)
    old_message_id = game.get("message_id")
    should_delete = DELETE_SETTINGS.get(chat_id, False)

    try:
        if not won and not lost:
            msg = await context.bot.send_message(chat_id=chat_id, text=board_text, parse_mode="HTML")
            game["message_id"] = msg.message_id
            if should_delete and old_message_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=old_message_id)
                except Exception:
                    pass
            
        elif won:
            points_earned = game["max_attempts"] - attempt_num + 1
            user_id = update.effective_user.id
            
            # 5-letter ke liye points seedhe general 'gold' mein save honge, baaki ke liye unke specific fields mein
            if length == 5:
                update_query = {"$inc": {"gold": points_earned}}
            else:
                letter_field = f"gold_{length}"
                update_query = {"$inc": {letter_field: points_earned}}
            
            await user_collection.update_one(
                {"$or": [{"id": user_id}, {"user_id": user_id}, {"_id": user_id}]},
                update_query,
                upsert=True
            )
            
            if should_delete and old_message_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=old_message_id)
                except Exception:
                    pass
            
            del ACTIVE_GAMES[chat_id]
            win_msg = f"<blockquote>Congrats! You guessed it correctly.</b>\n<b>Correct Word: {target.lower()}</b>\n<b>Added {points_earned} to the leaderboard.</blockquote>"
            await update.message.reply_text(win_msg, parse_mode="HTML", reply_to_message_id=update.message.message_id)
            
            try:
                await context.bot.set_message_reaction(chat_id=chat_id, message_id=update.message.message_id, reaction=[ReactionTypeEmoji(random.choice(REACTION_EMOJIS))])
            except Exception:
                pass
            
        elif lost:
            if should_delete and old_message_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=old_message_id)
                except Exception:
                    pass
            del ACTIVE_GAMES[chat_id]
            await update.message.reply_text(f"<b>Game Over! Correct Word: {target.lower()}</b>", parse_mode="HTML", reply_to_message_id=update.message.message_id)

    except Exception as e:
        LOGGER.error(f"Error handling guess: {e}")

# Registering Game Handlers Only
application.add_handler(CommandHandler(["new", "new4", "new5", "new6"], start_game_handler))
application.add_handler(CommandHandler("toggledelete", toggle_delete_handler))
application.add_handler(CommandHandler("end", end_game_handler))
application.add_handler(CommandHandler("helpword", help_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))

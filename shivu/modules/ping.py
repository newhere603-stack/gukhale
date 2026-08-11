import random
import logging
import re
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes
from shivu import application

LOGGER = logging.getLogger(__name__)

# Comprehensive word lists for 4, 5, and 6 letter modes
WORDS_4 = [
    "BABY", "BALL", "BIRD", "BLUE", "BOAT", "BOOK", "CAKE", "CITY", "COLD", "DARK",
    "DOOR", "DUCK", "FIRE", "FISH", "GAME", "GOLD", "HAIR", "HAND", "HOME", "HOPE",
    "JUMP", "KING", "LIFE", "LION", "MOON", "MILK", "NAME", "PARK", "RAIN", "RING",
    "ROSE", "SHIP", "SNOW", "STAR", "TREE", "WIND", "WISH", "WOOD", "YEAR", "ZERO"
]

WORDS_5 = [
    "APPLE", "BEACH", "CHAIR", "DRIVE", "EAGLE", "FRUIT", "GRAPE", "HOUSE", "IMAGE", "JUICE",
    "KNIFE", "LEMON", "MOUSE", "NIGHT", "OCEAN", "PAPER", "QUEEN", "RADIO", "SMILE", "TIGER",
    "UNION", "VOICE", "WATER", "YOUTH", "ZEBRA", "CROWN", "FRIED", "PRUNE", "PLANT", "SADLY",
    "BREAD", "TRAIN", "SLEEP", "LIGHT", "GREEN", "BLACK", "WHITE", "SMART", "BRAVE", "HAPPY",
    "STORM", "PLAZA", "TRACK", "MONEY", "PLUCK", "SHARK", "WHALE", "SNAKE", "TOWER", "CLOCK"
]

WORDS_6 = [
    "ANIMAL", "BANANA", "BOTTLE", "BRIDGE", "CAMERA", "CASTLE", "CIRCLE", "COFFEE", "DESERT", "DONKEY",
    "FAMILY", "FLOWER", "GARDEN", "GUITAR", "HAMMER", "ISLAND", "JUNGLE", "KITTEN", "LADDER", "LANTERN",
    "MARKET", "MIRROR", "NEEDLE", "ORANGE", "PALACE", "PARROT", "PENCIL", "PLANET", "POCKET", "RABBIT",
    "ROCKET", "SCHOOL", "SCREEP", "SILVER", "SPRING", "STREAM", "SUMMER", "TARGET", "TEMPLE", "TOMATO",
    "TUNNEL", "VALLEY", "WANDER", "WINDOW", "WINTER", "YELLOW", "CHARGE", "STRIKE", "OBJECT", "DEFEND"
]

# Active games storage: chat_id -> game_state dict
ACTIVE_GAMES = {}

def get_wordle_hints(guess: str, target: str) -> str:
    """Accurate Wordle hint algorithm handling duplicate letters correctly."""
    length = len(target)
    result = ["🟥"] * length
    target_chars = list(target)
    guess_chars = list(guess)

    # First pass: Check for Greens (Correct position)
    for i in range(length):
        if guess_chars[i] == target_chars[i]:
            result[i] = "🟩"
            target_chars[i] = None
            guess_chars[i] = None

    # Second pass: Check for Yellows (Wrong position)
    for i in range(length):
        if guess_chars[i] is not None:
            if guess_chars[i] in target_chars:
                result[i] = "🟨"
                target_chars[target_chars.index(guess_chars[i])] = None

    return "".join(result)

async def start_game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /new, /new4, /new5, /new6 and /new [length] commands."""
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    command = update.message.text.split()[0].lower()
    
    # Determine word length based on command or arguments
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

    # Select word list
    if length == 4:
        target = random.choice(WORDS_4)
    elif length == 6:
        target = random.choice(WORDS_6)
    else:
        target = random.choice(WORDS_5)

    ACTIVE_GAMES[chat_id] = {
        "target": target,
        "length": length,
        "guesses": [],
        "max_attempts": 30,
        "message_id": None
    }

    try:
        msg = await update.message.reply_text(
            f"<b>WordSeek</b>\nGame started! Guess the {length}-letter word!",
            parse_mode="HTML"
        )
        ACTIVE_GAMES[chat_id]["message_id"] = msg.message_id
    except Exception as e:
        LOGGER.error(f"Error starting wordseek game: {e}")

async def end_game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ends the current active game using /end."""
    if not update.effective_chat:
        return
    chat_id = update.effective_chat.id
    if chat_id in ACTIVE_GAMES:
        target = ACTIVE_GAMES[chat_id]["target"]
        del ACTIVE_GAMES[chat_id]
        await update.message.reply_text(f"🛑 <b>Game ended by admin/user. The word was: {target}</b>", parse_mode="HTML")
    else:
        await update.message.reply_text("ℹ️ No active WordSeek game running in this chat.", parse_mode="HTML")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the complete help menu matching your requirements."""
    help_text = (
        "<b>▸ How to Play WordSeek</b>\n\n"
        "1. Start a game using /new, /new4, /new5, or /new6\n"
        "2. Guess the hidden word\n"
        "3. After each guess, you'll get color hints:\n"
        "   🟩 Correct letter in the right spot\n"
        "   🟨 Correct letter in the wrong spot\n"
        "   🟥 Letter not in the word\n"
        "4. First person to guess correctly wins!\n"
        "5. Maximum 30 guesses per game\n\n"
        "<b>Word Length Modes:</b>\n"
        "• /new → Start default 5-letter game\n"
        "• /new [4/5/6] → Start specific length\n"
        "• /new4 → Start 4-letter game\n"
        "• /new5 → Start 5-letter game\n"
        "• /new6 → Start 6-letter game\n\n"
        "<b>Basic Commands:</b>\n"
        "• /end - End current game\n"
        "• /help - Show this help menu"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes user chat messages as guesses for the active WordSeek game."""
    if not update.message or not update.message.text or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    if chat_id not in ACTIVE_GAMES:
        return

    text = update.message.text.strip().upper()
    game = ACTIVE_GAMES[chat_id]
    length = game["length"]

    # Validate word length and alphabetic chars
    if len(text) != length or not text.isalpha():
        return

    target = game["target"]
    feedback = get_wordle_hints(text, target)

    game["guesses"].append((feedback, text))
    attempt_num = len(game["guesses"])

    # Build board layout matching your template style
    board_lines = [f"<b>WordSeek</b>\n<i>{length}-letter mode · {attempt_num}/{game['max_attempts']}</i>\n"]
    for fb, guess_word in game["guesses"]:
        board_lines.append(f"{fb} <b>{guess_word}</b>")

    board_text = "\n".join(board_lines)

    won = (text == target)
    lost = (attempt_num >= game["max_attempts"] and not won)

    if won:
        board_text += f"\n\n🎉 <b>Correct! {update.effective_user.first_name} guessed the word: {target}!</b>"
        del ACTIVE_GAMES[chat_id]
    elif lost:
        board_text += f"\n\n❌ <b>Game Over! Maximum attempts reached. The word was: {target}.</b>"
        del ACTIVE_GAMES[chat_id]

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game["message_id"],
            text=board_text,
            parse_mode="HTML"
        )
        # Delete user guess message to keep group chat clean
        await update.message.delete()
    except Exception as e:
        LOGGER.error(f"Error updating wordseek game board: {e}")

# Register handlers to the main shivu application
application.add_handler(CommandHandler(["new", "new4", "new5", "new6"], start_game_handler))
application.add_handler(CommandHandler("end", end_game_handler))
application.add_handler(CommandHandler("helpword", help_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))

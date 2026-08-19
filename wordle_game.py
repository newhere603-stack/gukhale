import os
import json
import random
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, ReactionTypeEmoji
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes
from pymongo import ReturnDocument

# Yahan 'db' import kar lena apne main database connection se
from shivu import application, user_collection, db

LOGGER = logging.getLogger(__name__)

# MongoDB collection game state save karne ke liye (Restart proof)
game_collection = db['wordseek_games']

DELETE_SETTINGS = {}
WORDSEEK_ENABLED = {}  

REACTION_EMOJIS = ["🔥", "🍓", "❤️", "🎉", "😍", "🥰", "⚡", "🏆", "👏", "❤️‍🔥", "🍾", "💯", "💘", "👌", "🕊️", "🤩", "🐳"]
LOG_GROUP_ID = -1003893927065  

# --- FAST JSON LOADING ---
def load_words_from_json(filename):
    try:
        paths_to_check = [filename, os.path.join("wordseek", filename), os.path.join("shivu", filename)]
        for path in paths_to_check:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return set(str(w).strip().upper() for w in data)
    except Exception as e:
        LOGGER.error(f"Error loading {filename}: {e}")
    return set()

WORDS_4_ALL = load_words_from_json("all-four.json")
WORDS_5_ALL = load_words_from_json("all-five.json")
WORDS_6_ALL = load_words_from_json("all-six.json")

WORDS_4_COMMON = load_words_from_json("common-four.json")
WORDS_5_COMMON = load_words_from_json("common-five.json")
WORDS_6_COMMON = load_words_from_json("common-six.json")

VALID_WORDS_4 = WORDS_4_ALL | WORDS_4_COMMON
VALID_WORDS_5 = WORDS_5_ALL | WORDS_5_COMMON
VALID_WORDS_6 = WORDS_6_ALL | WORDS_6_COMMON

def to_bold_sans_serif(text: str) -> str:
    result = []
    for char in text:
        if 'A' <= char <= 'Z': result.append(chr(ord(char) + 0x1D5D4 - ord('A')))
        elif 'a' <= char <= 'z': result.append(chr(ord(char) + 0x1D5EE - ord('a')))
        elif '0' <= char <= '9': result.append(chr(ord(char) + 0x1D7EC - ord('0')))
        else: result.append(char)
    return "".join(result)

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

    return " ".join(result)

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user: return False
    if chat.type == "private": return True
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ["creator", "administrator"]
    except Exception:
        return False

async def toggle_wordseek_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat: return
    if not await is_admin(update, context):
        await update.message.reply_text("<b>❌ Only group admins can enable or disable WordSeek.</b>", parse_mode="HTML")
        return
    chat_id = update.effective_chat.id
    new_status = not WORDSEEK_ENABLED.get(chat_id, True)
    WORDSEEK_ENABLED[chat_id] = new_status
    await update.message.reply_text(f"<b>WordSeek Game is now: {'ENABLED ✅' if new_status else 'DISABLED ❌'}</b>", parse_mode="HTML")

async def toggle_delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat: return
    chat_id = update.effective_chat.id
    new_status = not DELETE_SETTINGS.get(chat_id, False)
    DELETE_SETTINGS[chat_id] = new_status
    await update.message.reply_text(f"<b>Auto-Delete is now: {'ENABLED 🗑️' if new_status else 'DISABLED 🛡️'}</b>", parse_mode="HTML")

async def start_game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message: return
    chat = update.effective_chat
    chat_id = chat.id

    if chat.type == "private":
        await update.message.reply_text("<b>ʏᴏᴜ ᴄᴀɴ ᴘʟᴀʏ ᴡᴏʀᴅsᴇᴇᴋ ᴏɴʟʏ ɪɴ ɢʀᴏᴜᴘs!</b>", parse_mode="HTML")
        return
    if not WORDSEEK_ENABLED.get(chat_id, True):
        await update.message.reply_text("<b>WordSeek is currently disabled in this chat.</b>", parse_mode="HTML")
        return

    active_game = await game_collection.find_one({"chat_id": chat_id})
    if active_game:
        await update.message.reply_text("<b>There is already a game in progress in this chat. Use /end to end it.</b>", parse_mode="HTML")
        return

    command = update.message.text.split()[0].lower()
    length = 5
    if "4" in command: length = 4
    elif "6" in command: length = 6
    elif context.args:
        try:
            arg = int(context.args[0])
            if arg in [4, 5, 6]: length = arg
        except ValueError: pass

    word_pool = WORDS_4_COMMON if length == 4 else (WORDS_6_COMMON if length == 6 else WORDS_5_COMMON)
    if not word_pool:
        await update.message.reply_text(f"<b>⚠️ Error: No common words found for {length}-letter mode! Check your JSON files.</b>", parse_mode="HTML")
        return

    target = random.choice(list(word_pool))
    
    try:
        msg = await context.bot.send_message(chat_id=chat_id, text=f"<b>Game started! Guess the {length}-letter word!</b>", parse_mode="HTML")
        
        # Save game in DB
        game_data = {
            "chat_id": chat_id,
            "target": target,
            "length": length,
            "max_attempts": 30,
            "guesses": [], # Format: [[feedback, word], ...]
            "message_id": msg.message_id
        }
        await game_collection.insert_one(game_data)
        
        async def send_log():
            try:
                chat_name = chat.title if chat.title else "Group"
                log_text = f"🎮 <b>New WordSeek Started!</b>\n<b>Group:</b> {chat_name}\n<b>Target Word:</b> <code>{target}</code>"
                await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_text, parse_mode="HTML", disable_web_page_preview=True)
            except Exception: pass
        asyncio.create_task(send_log())
            
    except Exception as e:
        LOGGER.error(f"Error starting game: {e}")

async def end_game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat: return
    chat_id = update.effective_chat.id
    
    active_game = await game_collection.find_one({"chat_id": chat_id})
    if not active_game:
        await update.message.reply_text("<b><blockquote>ℹ️ No active wordseek running.</blockquote></b>", parse_mode="HTML")
        return

    target = active_game["target"]
    await game_collection.delete_one({"chat_id": chat_id})
    await update.message.reply_text(f"<b><blockquote>🛑 Game ended.\nThe word was: {target.lower()}</blockquote></b>", parse_mode="HTML")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat: return
    help_text = (
        "<b>▸ How to Play WordSeek</b>\n\n"
        "1. Start a game using /new, /new4, /new5, or /new6\n"
        "2. Guess the hidden word\n"
        "3. Color hints:\n"
        "   🟩 Correct letter & spot\n"
        "   🟨 Correct letter, wrong spot\n"
        "   🟥 Letter not in word\n"
        "4. First to guess correctly wins!\n\n"
        "<b>Game Modes:</b>\n"
        "• /new or /new5 → 5-letter game\n"
        "• /new4 → 4-letter game\n"
        "• /new6 → 6-letter game\n\n"
        "<b>Commands:</b>\n"
        "• /end → End current game\n"
        "• /toggledelete → Toggle auto-delete hints\n"
        "• /togglewordseek → Enable/Disable bot in chat"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

async def update_user_gold_task(user_id, first_name, username, points, inc_field, chat_id, now_ist):
    try:
        today_str = now_ist.strftime("%Y-%m-%d")
        week_str = now_ist.strftime("%Y-W%V")
        month_str = now_ist.strftime("%Y-%m")
        year_str = now_ist.strftime("%Y")

        inc_dict = {
            inc_field: points,
            f"{today_str}_{inc_field}": points,
            f"{week_str}_{inc_field}": points,
            f"{month_str}_{inc_field}": points,
            f"{year_str}_{inc_field}": points,
            f"{chat_id}_{inc_field}": points,
            f"{chat_id}_{today_str}_{inc_field}": points,
            f"{chat_id}_{week_str}_{inc_field}": points,
            f"{chat_id}_{month_str}_{inc_field}": points,
            f"{chat_id}_{year_str}_{inc_field}": points
        }
        
        await user_collection.update_one(
            {"id": user_id},
            {"$inc": inc_dict, "$setOnInsert": {"first_name": first_name, "username": username}},
            upsert=True
        )
    except Exception as db_err:
        LOGGER.error(f"Database error while updating gold: {db_err}")

async def safe_delete_message(context, chat_id, message_id):
    try: await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception: pass

async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_chat: return
    chat_id = update.effective_chat.id
    if not WORDSEEK_ENABLED.get(chat_id, True): return

    game = await game_collection.find_one({"chat_id": chat_id})
    if not game: return

    original_text = update.message.text.strip()
    text = original_text.upper()
    length = game["length"]

    if len(text) != length or not text.isalpha(): return

    valid_list = VALID_WORDS_4 if length == 4 else (VALID_WORDS_6 if length == 6 else VALID_WORDS_5)
    
    if text not in valid_list:
        asyncio.create_task(context.bot.send_message(chat_id=chat_id, text=f"{original_text.lower()} is not a valid word.", parse_mode="HTML"))
        return

    # Check already guessed
    guessed_words = [g[1] for g in game.get("guesses", [])]
    if text in guessed_words:
        asyncio.create_task(context.bot.send_message(chat_id=chat_id, text="Someone has already guessed your word. Please try another one!", parse_mode="HTML"))
        return

    target = game["target"]
    feedback = get_wordle_hints(text, target)

    # Superfast Single DB Call: Add guess and get the new list instantly
    updated_game = await game_collection.find_one_and_update(
        {"chat_id": chat_id},
        {"$push": {"guesses": [feedback, text]}},
        return_document=ReturnDocument.AFTER
    )
    
    attempts = len(updated_game["guesses"])
    
    # Board create ho raha hai (Stacked style)
    board_lines = [f"<b>{length}-letter mode · {attempts}/{updated_game['max_attempts']}</b>\n"]
    for fb, guess_word in updated_game["guesses"]:
        board_lines.append(f"{fb} {to_bold_sans_serif(guess_word)}")
        
    board_text = "\n".join(board_lines)
    
    won = (text == target)
    lost = (attempts >= updated_game["max_attempts"] and not won)
    should_delete = DELETE_SETTINGS.get(chat_id, False)
    old_message_id = updated_game.get("message_id")

    try:
        if not won and not lost:
            # User ke naye guess pe naya message reply bhejega
            new_msg = await update.message.reply_text(board_text, parse_mode="HTML", reply_to_message_id=update.message.message_id)
            
            # DB mein naya message ID update
            await game_collection.update_one({"chat_id": chat_id}, {"$set": {"message_id": new_msg.message_id}})
            
            # Agar auto-delete on hai to purana wala bina lag ke udd jayega
            if should_delete and old_message_id: 
                asyncio.create_task(safe_delete_message(context, chat_id, old_message_id))
            
        elif won:
            points_earned = updated_game["max_attempts"] - attempts + 1
            await game_collection.delete_one({"chat_id": chat_id}) 
            
            user = update.effective_user
            inc_field = "gold" if length == 5 else f"gold_{length}"
            now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
            
            asyncio.create_task(update_user_gold_task(user.id, user.first_name, user.username, points_earned, inc_field, chat_id, now_ist))
            if should_delete and old_message_id: 
                asyncio.create_task(safe_delete_message(context, chat_id, old_message_id))
                
            suggested_cmd = f"/new{length}" if length in [4, 6] else "/new"
            win_msg = f"{board_text}\n\n<b><blockquote>Congrats! You guessed it correctly.\nCorrect Word: {target.lower()}\nAdded {points_earned} to the leaderboard.</blockquote>\nStart with {suggested_cmd}</b>"
            
            await update.message.reply_text(win_msg, parse_mode="HTML", reply_to_message_id=update.message.message_id)
            
            async def set_reaction_safe():
                try: await context.bot.set_message_reaction(chat_id=chat_id, message_id=update.message.message_id, reaction=[ReactionTypeEmoji(random.choice(REACTION_EMOJIS))])
                except Exception as reaction_error: LOGGER.error(f"Reaction fail ho gaya: {reaction_error}")
            asyncio.create_task(set_reaction_safe())
            
        elif lost:
            await game_collection.delete_one({"chat_id": chat_id})
            if should_delete and old_message_id: 
                asyncio.create_task(safe_delete_message(context, chat_id, old_message_id))
            await update.message.reply_text(f"{board_text}\n\n<b>Game Over! Correct Word:</b>\n<blockquote>{target.lower()}</blockquote>", parse_mode="HTML", reply_to_message_id=update.message.message_id)

    except Exception as e:
        LOGGER.error(f"Error handling guess: {e}")

# Registering Handlers
application.add_handler(CommandHandler(["new", "new4", "new5", "new6"], start_game_handler))
application.add_handler(CommandHandler("toggledelete", toggle_delete_handler))
application.add_handler(CommandHandler("togglewordseek", toggle_wordseek_handler))
application.add_handler(CommandHandler("end", end_game_handler))
application.add_handler(CommandHandler("helpword", help_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))

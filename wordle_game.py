import os
import json
import random
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, ReactionTypeEmoji
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes

from shivu import application, user_collection

LOGGER = logging.getLogger(__name__)

ACTIVE_GAMES = {}
DELETE_SETTINGS = {}
WORDSEEK_ENABLED = {}  

# Safe reactions list (Telegram-approved bot emojis)
REACTION_EMOJIS = ["🔥", "🍓", "❤️", "🎉", "😍", "🥰", "⚡", "🏆", "👏", "❤️‍🔥", "🍾", "💯", "💘", "👌", "🕊️", "🤩", "🐳"]
LOG_GROUP_ID = -1003893927065  # Aapka log group ID

# --- FAST JSON LOADING (NO FALLBACKS) ---
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

# Load ALL words (For guessing validation)
WORDS_4_ALL = load_words_from_json("all-four.json")
WORDS_5_ALL = load_words_from_json("all-five.json")
WORDS_6_ALL = load_words_from_json("all-six.json")

# Load COMMON words (For selecting the target word)
WORDS_4_COMMON = load_words_from_json("common-four.json")
WORDS_5_COMMON = load_words_from_json("common-five.json")
WORDS_6_COMMON = load_words_from_json("common-six.json")

# Valid words pool (ALL + COMMON) for checking user guesses
VALID_WORDS_4 = WORDS_4_ALL | WORDS_4_COMMON
VALID_WORDS_5 = WORDS_5_ALL | WORDS_5_COMMON
VALID_WORDS_6 = WORDS_6_ALL | WORDS_6_COMMON

def to_bold_sans_serif(text: str) -> str:
    result = []
    for char in text:
        if 'A' <= char <= 'Z':
            result.append(chr(ord(char) + 0x1D5D4 - ord('A')))
        elif 'a' <= char <= 'z':
            result.append(chr(ord(char) + 0x1D5EE - ord('a')))
        elif '0' <= char <= '9':
            result.append(chr(ord(char) + 0x1D7EC - ord('0')))
        else:
            result.append(char)
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
    if not chat or not user:
        return False
    if chat.type == "private":
        return True
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ["creator", "administrator"]
    except Exception:
        return False

async def toggle_wordseek_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return
    
    if not await is_admin(update, context):
        await update.message.reply_text("<b>❌ Only group admins can enable or disable WordSeek.</b>", parse_mode="HTML")
        return

    chat_id = update.effective_chat.id
    current_status = WORDSEEK_ENABLED.get(chat_id, True)
    new_status = not current_status
    WORDSEEK_ENABLED[chat_id] = new_status
    
    status_text = "ENABLED ✅" if new_status else "DISABLED ❌"
    await update.message.reply_text(f"<b>WordSeek Game is now: {status_text}</b>", parse_mode="HTML")

async def toggle_delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return
    chat_id = update.effective_chat.id
    if not WORDSEEK_ENABLED.get(chat_id, True):
        return

    current_status = DELETE_SETTINGS.get(chat_id, False)
    NEW_STATUS = not current_status
    DELETE_SETTINGS[chat_id] = NEW_STATUS
    status_text = "ENABLED 🗑️" if NEW_STATUS else "DISABLED 🛡️"
    await update.message.reply_text(f"<b>Auto-Delete is now: {status_text}</b>", parse_mode="HTML")

async def start_game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message:
        return
    
    chat = update.effective_chat
    chat_id = chat.id

    if chat.type == "private":
        await update.message.reply_text(
            "<b>ʏᴏᴜ ᴄᴀɴ ᴘʟᴀʏ ᴡᴏʀᴅsᴇᴇᴋ ᴏɴʟʏ ɪɴ ɢʀᴏᴜᴘs!</b>", 
            parse_mode="HTML"
        )
        return

    if not WORDSEEK_ENABLED.get(chat_id, True):
        await update.message.reply_text("<b>WordSeek is currently disabled in this chat.</b>", parse_mode="HTML")
        return

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

    word_pool = WORDS_4_COMMON if length == 4 else (WORDS_6_COMMON if length == 6 else WORDS_5_COMMON)
    if not word_pool:
        await update.message.reply_text(f"<b>⚠️ Error: No common words found for {length}-letter mode! Check your JSON files.</b>", parse_mode="HTML")
        return

    target = random.choice(list(word_pool))
    ACTIVE_GAMES[chat_id] = {"target": target, "length": length, "guesses": [], "max_attempts": 30, "message_id": None}

    try:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=f"<b>Game started! Guess the {length}-letter word!</b>",
            parse_mode="HTML"
        )
        ACTIVE_GAMES[chat_id]["message_id"] = msg.message_id
        
        chat_name = chat.title if chat.title else "Group"
        chat_link = f"https://t.me/{chat.username}" if chat.username else f"ID: {chat.id}"
        
        log_text = (
            f"🎮 <b>New WordSeek Game Started!</b>\n"
            f"<b>Group:</b> {chat_name}\n"
            f"<b>Link/ID:</b> {chat_link}\n"
            f"<b>Target Word:</b> <code>{target}</code>"
        )
        
        try:
            await context.bot.send_message(
                chat_id=LOG_GROUP_ID,
                text=log_text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception as log_e:
            LOGGER.error(f"Could not send log to log group: {log_e}")
            
    except Exception as e:
        LOGGER.error(f"Error starting game: {e}")

async def end_game_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return
    chat_id = update.effective_chat.id
    if not WORDSEEK_ENABLED.get(chat_id, True):
        return

    if chat_id in ACTIVE_GAMES:
        target = ACTIVE_GAMES[chat_id]["target"]
        del ACTIVE_GAMES[chat_id]
        await update.message.reply_text(f"<b><blockquote>🛑 Game ended.\nThe word was:{target.lower()}</blockquote></b>", parse_mode="HTML")
    else:
        await update.message.reply_text("<b>ℹ️ No active game running.</b>", parse_mode="HTML")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return
    chat_id = update.effective_chat.id
    if not WORDSEEK_ENABLED.get(chat_id, True):
        return
        
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
        "• /togglewordseek → Enable/Disable bot in chat\n"
        "• /helpword → Show this help menu"
    )
    
    await update.message.reply_text(help_text, parse_mode="HTML")

async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    if not WORDSEEK_ENABLED.get(chat_id, True):
        return

    if chat_id not in ACTIVE_GAMES:
        return

    original_text = update.message.text.strip()
    text = original_text.upper()
    game = ACTIVE_GAMES[chat_id]
    length = game["length"]

    if len(text) != length or not text.isalpha():
        return

    valid_list = VALID_WORDS_4 if length == 4 else (VALID_WORDS_6 if length == 6 else VALID_WORDS_5)
    
    if text not in valid_list:
        error_msg = f"{original_text.lower()} is not a valid word."
        await context.bot.send_message(
            chat_id=chat_id,
            text=error_msg,
            parse_mode="HTML"
        )
        return

    guessed_words = [g[1] for g in game["guesses"]]
    if text in guessed_words:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Someone has already guessed your word. Please try another one!",
            parse_mode="HTML"
        )
        return

    target = game["target"]
    feedback = get_wordle_hints(text, target)

    game["guesses"].append((feedback, text))
    attempt_num = len(game["guesses"])

    board_lines = [f"<b>{length}-letter mode · {attempt_num}/{game['max_attempts']}</b>\n"]
    for fb, guess_word in game["guesses"]:
        styled_word = to_bold_sans_serif(guess_word)
        board_lines.append(f"{fb} {styled_word}")

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
            del ACTIVE_GAMES[chat_id]
            
            try:
                user = update.effective_user
                user_id = user.id
                
                # Fetching Current Date/Time in IST (Indian Standard Time)
                now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
                today_str = now_ist.strftime("%Y-%m-%d")
                week_str = now_ist.strftime("%Y-W%V")
                month_str = now_ist.strftime("%Y-%m")
                year_str = now_ist.strftime("%Y")

                inc_field = "gold" if length == 5 else f"gold_{length}"
                
                # Updating the Dictionary to use Time-Prefixed Keys
                inc_dict = {
                    inc_field: points_earned,
                    f"{today_str}_{inc_field}": points_earned,
                    f"{week_str}_{inc_field}": points_earned,
                    f"{month_str}_{inc_field}": points_earned,
                    f"{year_str}_{inc_field}": points_earned,
                    
                    f"{chat_id}_{inc_field}": points_earned,
                    f"{chat_id}_{today_str}_{inc_field}": points_earned,
                    f"{chat_id}_{week_str}_{inc_field}": points_earned,
                    f"{chat_id}_{month_str}_{inc_field}": points_earned,
                    f"{chat_id}_{year_str}_{inc_field}": points_earned
                }
                
                # OPTIMIZATION: Ultra-fast single database round-trip using upsert=True
                await user_collection.update_one(
                    {"id": user_id},
                    {
                        "$inc": inc_dict,
                        "$setOnInsert": {
                            "first_name": user.first_name,
                            "username": user.username
                        }
                    },
                    upsert=True
                )
                    
            except Exception as db_err:
                LOGGER.error(f"Database error while updating gold: {db_err}")
            
            if should_delete and old_message_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=old_message_id)
                except Exception:
                    pass
            
            suggested_cmd = f"/new{length}" if length in [4, 6] else "/new"
            
            win_msg = (
                f"<b><blockquote>Congrats! You guessed it correctly.\nCorrect Word: {target.lower()}\nAdded {points_earned} to the leaderboard.</blockquote>\nStart with {suggested_cmd}</b>"
            )
            await update.message.reply_text(win_msg, parse_mode="HTML", reply_to_message_id=update.message.message_id)
            
            # OPTIMIZATION: Non-blocking background task for reaction so it never delays the response
            async def set_reaction_safe():
                try:
                    await context.bot.set_message_reaction(
                        chat_id=chat_id, 
                        message_id=update.message.message_id, 
                        reaction=[ReactionTypeEmoji(random.choice(REACTION_EMOJIS))]
                    )
                except Exception as reaction_error:
                    LOGGER.error(f"Reaction fail ho gaya: {reaction_error}")
            
            asyncio.create_task(set_reaction_safe())
            
        elif lost:
            if should_delete and old_message_id:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=old_message_id)
                except Exception:
                    pass
            del ACTIVE_GAMES[chat_id]
            await update.message.reply_text(f"<b>Game Over! Correct Word:</b>\n<blockquote>{target.lower()}</blockquote>", parse_mode="HTML", reply_to_message_id=update.message.message_id)

    except Exception as e:
        LOGGER.error(f"Error handling guess: {e}")

# Registering Game Handlers Only
application.add_handler(CommandHandler(["new", "new4", "new5", "new6"], start_game_handler))
application.add_handler(CommandHandler("toggledelete", toggle_delete_handler))
application.add_handler(CommandHandler("togglewordseek", toggle_wordseek_handler))
application.add_handler(CommandHandler("end", end_game_handler))
application.add_handler(CommandHandler("helpword", help_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))

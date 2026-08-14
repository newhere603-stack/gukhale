import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.helpers import mention_html
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler
from telegram.error import BadRequest

from shivu import application, user_collection, group_user_totals_collection

LOGGER = logging.getLogger(__name__)

# Temporary state tracking for filters (chat_id -> state dict)
LEADERBOARD_STATES = {}

def get_user_state(chat_id):
    if chat_id not in LEADERBOARD_STATES:
        LEADERBOARD_STATES[chat_id] = {
            "scope": "chat",    # Default: chat
            "time": "month",    # Default: month
            "letters": "5"      # Default: 5 letters
        }
    return LEADERBOARD_STATES[chat_id]

def extract_gold(user_doc, letter_filter="all", time_filter="all"):
    if not user_doc or not isinstance(user_doc, dict):
        return 0
    
    if letter_filter == "4":
        base_keys = ['gold_4', 'points_4', 'golds_4']
    elif letter_filter == "5":
        base_keys = ['gold', 'golds', 'gold_5', 'points_5', 'golds_5', 'wordseek_points', 'score', 'points']
    elif letter_filter == "6":
        base_keys = ['gold_6', 'points_6', 'golds_6']
    else:
        base_keys = ['gold', 'golds', 'wordseek_points', 'score', 'points']
    
    if time_filter == "all":
        keys_to_check = base_keys
    else:
        keys_to_check = [f"{time_filter}_{key}" for key in base_keys]
    
    for key in keys_to_check:
        val = user_doc.get(key)
        if val is not None:
            try:
                val = int(val)
                if val > 0:
                    return val
            except (ValueError, TypeError):
                pass
                
    return 0

async def send_or_edit(update, context, text, kb, edit):
    photo_url = "https://files.catbox.moe/ewtw4l.png"
    if edit:
        q = update.callback_query
        try:
            await q.answer()
        except Exception:
            pass

        try:
            await q.edit_message_media(
                media=InputMediaPhoto(media=photo_url, caption=text, parse_mode='HTML'),
                reply_markup=kb
            )
        except BadRequest as e:
            if "not modified" in str(e).lower():
                return
            try:
                await q.message.delete()
            except Exception:
                pass
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_url, caption=text, parse_mode='HTML', reply_markup=kb)
        except Exception:
            try:
                await q.message.delete()
            except Exception:
                pass
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_url, caption=text, parse_mode='HTML', reply_markup=kb)
    else:
        await update.message.reply_photo(photo=photo_url, caption=text, parse_mode='HTML', reply_markup=kb)

def get_wordseek_keyboard(state):
    scope = state["scope"]
    time_f = state["time"]
    letter_f = state["letters"]

    global_btn = "ɢʟᴏʙᴀʟ ⎋" if scope == "global" else "ɢʟᴏʙᴀʟ"
    chat_btn = "ᴄʜᴀᴛ ⎋" if scope == "chat" else "ᴄʜᴀᴛ"
    
    today_btn = "ᴛᴏᴅᴀʏ ⎋" if time_f == "today" else "ᴛᴏᴅᴀʏ"
    week_btn = "ᴡᴇᴇᴋ ⎋" if time_f == "week" else "ᴡᴇᴇᴋ"
    month_btn = "ᴍᴏɴᴛʜ ⎋" if time_f == "month" else "ᴍᴏɴᴛʜ"
    year_btn = "ʏᴇᴀʀ ⎋" if time_f == "year" else "ʏᴇᴀʀ"
    all_btn = "ᴀʟʟ-ᴛɪᴍᴇ ⎋" if time_f == "all" else "ᴀʟʟ-ᴛɪᴍᴇ"

    l4_btn = "4 ʟᴇᴛʀ ⎋" if letter_f == "4" else "4 ʟᴇᴛʀ"
    l5_btn = "5 ʟᴇᴛʀ ⎋" if letter_f == "5" else "5 ʟᴇᴛʀ"
    l6_btn = "6 ʟᴇᴛʀ ⎋" if letter_f == "6" else "6 ʟᴇᴛʀ"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(global_btn, callback_data="ws_scope_global"),
            InlineKeyboardButton("⟳", callback_data="ws_refresh"),
            InlineKeyboardButton(chat_btn, callback_data="ws_scope_chat")
        ],
        [
            InlineKeyboardButton(today_btn, callback_data="ws_time_today"),
            InlineKeyboardButton(week_btn, callback_data="ws_time_week"),
            InlineKeyboardButton(month_btn, callback_data="ws_time_month")
        ],
        [
            InlineKeyboardButton(year_btn, callback_data="ws_time_year"),
            InlineKeyboardButton(all_btn, callback_data="ws_time_all")
        ],
        [
            InlineKeyboardButton(l4_btn, callback_data="ws_let_4"),
            InlineKeyboardButton(l5_btn, callback_data="ws_let_5"),
            InlineKeyboardButton(l6_btn, callback_data="ws_let_6")
        ]
    ])

async def wordseek_leaderboard(update: Update, context: CallbackContext, edit=False):
    chat_id = update.effective_chat.id
    state = get_user_state(chat_id)

    query_filter = {}
    
    if state["scope"] == "chat":
        group_users = await group_user_totals_collection.distinct("user_id", {"group_id": chat_id})
        if group_users:
            query_filter["$or"] = [{"id": {"$in": group_users}}, {"user_id": {"$in": group_users}}, {"_id": {"$in": group_users}}]
        else:
            query_filter["id"] = {"$in": []}

    # Fetching all matching players
    data = await user_collection.find(query_filter).to_list(None)
    
    time_f = state["time"]
    letter_f = state["letters"]
    
    # Extracting current scores for everyone in real-time
    user_scores = []
    for u in data:
        gold = extract_gold(u, letter_f, time_f)
        if gold > 0:
            user_scores.append((u, gold))

    if not user_scores:
        text = (
            "<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>WordSeek Leaderboard</b> <tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji>\n\n"
            "<i>No data found for this time/letter mode!</i>"
        )
        return await send_or_edit(update, context, text, get_wordseek_keyboard(state), edit)

    # Completely sorting all players highest to lowest, and ONLY then picking the top 20
    sorted_data = sorted(user_scores, key=lambda x: x[1], reverse=True)[:20]

    rows = []
    for i, (u, gold_val) in enumerate(sorted_data, 1):
        uid = u.get('id') or u.get('user_id') or u.get('_id', 0)
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            pass
        name = u.get('first_name', 'Unknown')
        link = mention_html(uid, name)
        
        rows.append(f"<b>{i}. {link} - {gold_val:,} <tg-emoji emoji-id=\"6332287240470798249\">🪙</tg-emoji></b>")

    rows_text = "\n".join(rows)
    
    text = (
        "<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>WordSeek Leaderboard</b> <tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{rows_text}"
    )
    
    await send_or_edit(update, context, text, get_wordseek_keyboard(state), edit)

async def ws_callback_router(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    chat_id = update.effective_chat.id
    state = get_user_state(chat_id)

    if data == "ws_scope_global":
        state["scope"] = "global"
    elif data == "ws_scope_chat":
        state["scope"] = "chat"
    elif data.startswith("ws_time_"):
        state["time"] = data.replace("ws_time_", "")
    elif data.startswith("ws_let_"):
        state["letters"] = data.replace("ws_let_", "")
    elif data == "ws_refresh":
        pass 

    await wordseek_leaderboard(update, context, edit=True)

# Handlers registration
application.add_handler(CommandHandler(["wordseektop", "wstop", "leaderboard"], wordseek_leaderboard, block=False))
application.add_handler(CallbackQueryHandler(ws_callback_router, pattern="^ws_"))

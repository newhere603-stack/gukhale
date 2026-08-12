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
            "scope": "global",  # global / chat
            "time": "all",      # today / week / month / year / all
            "letters": "all"    # 4 / 5 / 6 / all
        }
    return LEADERBOARD_STATES[chat_id]

def extract_gold(user_doc, letter_filter="all"):
    if not user_doc or not isinstance(user_doc, dict):
        return 0
    
    # Letter-wise keys mapping
    key_map = {
        "4": ['gold_4', 'points_4', 'golds_4'],
        "5": ['gold_5', 'points_5', 'golds_5'],
        "6": ['gold_6', 'points_6', 'golds_6'],
        "all": ['gold', 'golds', 'wordseek_points', 'score', 'points']
    }
    
    keys_to_check = key_map.get(letter_filter, key_map["all"])
    
    # Pehle specific letter field check karein
    for key in keys_to_check:
        val = user_doc.get(key)
        if val is not None:
            if isinstance(val, (int, float)):
                return int(val)
            elif isinstance(val, str) and val.isdigit():
                return int(val)
                
    # Fallback: Agar specific letter field nahi hai (purane score ke liye), toh general gold check karein
    if letter_filter != "all":
        for key in ['gold', 'golds', 'wordseek_points', 'score', 'points']:
            val = user_doc.get(key)
            if val is not None:
                if isinstance(val, (int, float)):
                    return int(val)
                elif isinstance(val, str) and val.isdigit():
                    return int(val)
                    
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

    global_btn = "« Global »" if scope == "global" else "Global"
    chat_btn = "« T Chat »" if scope == "chat" else "This chat"
    
    today_btn = "« Today »" if time_f == "today" else "Today"
    week_btn = "« T Week »" if time_f == "week" else "This week"
    month_btn = "« T Month »" if time_f == "month" else "This month"
    year_btn = "« T Year »" if time_f == "year" else "This year"
    all_btn = "« All Time »" if time_f == "all" else "All time"

    l4_btn = "« 4 Let »" if letter_f == "4" else "4 letters"
    l5_btn = "« 5 Let »" if letter_f == "5" else "5 letters"
    l6_btn = "« 6 Let »" if letter_f == "6" else "6 letters"

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

    data = await user_collection.find(query_filter).to_list(None)
    
    # Filter users based on points > 0 using smart extraction
    filtered_data = [u for u in data if extract_gold(u, state["letters"]) > 0]

    if not filtered_data:
        header_title = "Global Leaderboard" if state["scope"] == "global" else "Group Leaderboard"
        text = (
            "<b>Word Seek</b>\n\n"
            f"🏆 <b>{header_title}</b> 🏆\n\n"
            f"<i>No data found for this letter mode!</i>"
        )
        return await send_or_edit(update, context, text, get_wordseek_keyboard(state), edit)

    sorted_data = sorted(filtered_data, key=lambda x: extract_gold(x, state["letters"]), reverse=True)[:20]

    rows = []
    for i, u in enumerate(sorted_data, 1):
        uid = u.get('id') or u.get('user_id') or u.get('_id', 0)
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            pass
        name = u.get('first_name', 'Unknown')
        link = mention_html(uid, name)
        gold_val = extract_gold(u, state["letters"])
        
        rows.append(f"<b>{i}. {link} - {gold_val:,} <tg-emoji emoji-id=\"6332287240470798249\">🪙</tg-emoji></b>")

    rows_text = "\n".join(rows)
    header_title = "Global Leaderboard" if state["scope"] == "global" else "Group Leaderboard"
    
    text = (
        "<b>Word Seek</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>{header_title}</b> 🏆\n\n"
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

    await wordseek_leaderboard(update, context, edit=True)

# Handlers registration
application.add_handler(CommandHandler(["wordseektop", "wstop", "leaderboard"], wordseek_leaderboard, block=False))
application.add_handler(CallbackQueryHandler(ws_callback_router, pattern="^ws_"))

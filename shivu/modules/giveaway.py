import logging
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.helpers import mention_html
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler
from telegram.error import BadRequest

# 🔥 NAYA IMPORT: Score aur points naye economy database se fetch karne ke liye
from shivu import application
from shivu.Database.db import eco_collection as user_collection

LOGGER = logging.getLogger(__name__)

# Temporary state tracking for filters (chat_id -> state dict)
LEADERBOARD_STATES = {}

# --- 🔥 Superfast Cache System ---
WS_LB_CACHE = {}
CACHE_TTL = 300  # 5 minutes tak result memory me save rahega

def get_user_state(chat_id):
    if chat_id not in LEADERBOARD_STATES:
        LEADERBOARD_STATES[chat_id] = {
            "scope": "chat",    # Default: Chat select rahega
            "time": "all",      # Default: All-Time rahega
            "letters": "5"      # Default: 5 Letter rahega
        }
    return LEADERBOARD_STATES[chat_id]

# Yeh function sirf utna hi score filter karega jitna us scope mein valid hai
def get_target_keys(letter_filter, time_filter, scope, chat_id):
    if letter_filter == "4":
        base_keys = ['gold_4', 'points_4', 'golds_4']
    elif letter_filter == "5":
        base_keys = ['gold', 'golds', 'gold_5', 'points_5', 'golds_5', 'wordseek_points', 'score', 'points']
    elif letter_filter == "6":
        base_keys = ['gold_6', 'points_6', 'golds_6']
    else:
        base_keys = ['gold', 'golds', 'wordseek_points', 'score', 'points']
    
    # Fetching Current Date/Time in IST (Indian Standard Time)
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    time_prefix = None
    
    if time_filter == "today":
        time_prefix = now_ist.strftime("%Y-%m-%d")
    elif time_filter == "week":
        time_prefix = now_ist.strftime("%Y-W%V")
    elif time_filter == "month":
        time_prefix = now_ist.strftime("%Y-%m")
    elif time_filter == "year":
        time_prefix = now_ist.strftime("%Y")

    keys = []
    for b_key in base_keys:
        time_key = f"{time_prefix}_{b_key}" if time_prefix else b_key
            
        if scope == "chat":
            final_key = f"{chat_id}_{time_key}"
        else:
            final_key = time_key
            
        keys.append(final_key)
    return keys

def extract_gold(user_doc, target_keys):
    if not user_doc or not isinstance(user_doc, dict):
        return 0
    
    for key in target_keys:
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
    all_btn = "ᴀʟʟ-ᴛɪᴍᴇ ⎋" if time_f == "all" else "ᴀʟʟ-ᴛɪ-ᴍᴇ"

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

async def get_cached_wordseek_lb(chat_id, scope_f, time_f, letter_f, target_keys):
    """Smart cache function to return fast results"""
    if scope_f == "global":
        cache_key = f"ws_global_{time_f}_{letter_f}"
    else:
        cache_key = f"ws_chat_{chat_id}_{time_f}_{letter_f}"
        
    now = time.time()
    if cache_key in WS_LB_CACHE and now - WS_LB_CACHE[cache_key]['time'] < CACHE_TTL:
        return WS_LB_CACHE[cache_key]['data']

    # Projection: Sirf zaroorat ka data nikalega, characters array ignore kar dega (Superfast)
    query_filter = {"$or": [{k: {"$exists": True}} for k in target_keys]}
    projection = {"id": 1, "user_id": 1, "_id": 1, "first_name": 1}
    for k in target_keys:
        projection[k] = 1

    data = await user_collection.find(query_filter, projection).to_list(None)
    
    user_scores = []
    for u in data:
        gold = extract_gold(u, target_keys)
        if gold > 0:
            user_scores.append((u, gold))

    sorted_data = sorted(user_scores, key=lambda x: x[1], reverse=True)[:20]
    
    WS_LB_CACHE[cache_key] = {'time': now, 'data': sorted_data}
    return sorted_data


async def wordseek_leaderboard(update: Update, context: CallbackContext, edit=False):
    chat_id = update.effective_chat.id
    state = get_user_state(chat_id)

    time_f = state["time"]
    letter_f = state["letters"]
    scope_f = state["scope"]

    # Target keys set kar lega depending on Global ya Chat hai
    target_keys = get_target_keys(letter_f, time_f, scope_f, chat_id)
    
    # Fetch data through optimized cache system
    sorted_data = await get_cached_wordseek_lb(chat_id, scope_f, time_f, letter_f, target_keys)

    if not sorted_data:
        text = (
            "<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>WordSeek Leaderboard</b> <tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji>\n\n"
            "<i>No data found for this mode! Play some games to rank up!</i>"
        )
        return await send_or_edit(update, context, text, get_wordseek_keyboard(state), edit)

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

# 🔥 FIX: Isme block=False missing tha jisse button dabane pe bot hang ho sakta tha
application.add_handler(CallbackQueryHandler(ws_callback_router, pattern="^ws_", block=False))

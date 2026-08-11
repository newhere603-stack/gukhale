import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.helpers import mention_html
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler
from telegram.error import BadRequest

from shivu import application, user_collection

LOGGER = logging.getLogger(__name__)

def extract_gold(user_doc):
    if not user_doc or not isinstance(user_doc, dict):
        return 0
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

def get_wordseek_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Global", callback_data="ws_global"),
            InlineKeyboardButton("🔄", callback_data="ws_refresh"),
            InlineKeyboardButton("« This chat", callback_data="ws_chat")
        ],
        [
            InlineKeyboardButton("Today", callback_data="ws_today"),
            InlineKeyboardButton("This week", callback_data="ws_week"),
            InlineKeyboardButton("« This month", callback_data="ws_month")
        ],
        [
            InlineKeyboardButton("This year", callback_data="ws_year"),
            InlineKeyboardButton("All time", callback_data="ws_all")
        ],
        [
            InlineKeyboardButton("4 letters", callback_data="ws_4l"),
            InlineKeyboardButton("« 5 letters »", callback_data="ws_5l"),
            InlineKeyboardButton("6 letters", callback_data="ws_6l")
        ]
    ])

async def wordseek_leaderboard(update: Update, context: CallbackContext, edit=False):
    data = await user_collection.find({}).to_list(None)
    filtered_data = [u for u in data if extract_gold(u) > 0]

    if not filtered_data:
        text = (
            "WordSeek\nAdmin\n\n"
            "🏆 <b>Group Leaderboard</b> 🏆\n\n"
            "<i>No data found yet! Play WordSeek to rank up.</i>"
        )
        return await send_or_edit(update, context, text, get_wordseek_keyboard(), edit)

    # Top 20 users sort karke fetch karna
    sorted_data = sorted(filtered_data, key=lambda x: extract_gold(x), reverse=True)[:20]

    rows = []
    for i, u in enumerate(sorted_data, 1):
        uid = u.get('id') or u.get('user_id') or u.get('_id', 0)
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            pass
        name = u.get('first_name', 'Unknown')
        link = mention_html(uid, name)
        gold_val = extract_gold(u)
        
        # Har ek entry ke liye line number (1 se 20 tak) aur 🪙 symbol ka format
        rows.append(f"<b>{i}. {link} - 🪙 {gold_val:,}</b>")

    rows_text = "\n".join(rows)
    text = (
        "WordSeek\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🏆 <b>Group Leaderboard</b> 🏆\n\n"
        f"{rows_text}"
    )
    
    await send_or_edit(update, context, text, get_wordseek_keyboard(), edit)

async def ws_callback_router(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    if data and data.startswith("ws_"):
        await wordseek_leaderboard(update, context, edit=True)

# Handlers registration
application.add_handler(CommandHandler(["wordseektop", "leaderboard"], wordseek_leaderboard, block=False))
application.add_handler(CallbackQueryHandler(ws_callback_router, pattern="^ws_"))

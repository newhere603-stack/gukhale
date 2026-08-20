import pytz
from dataclasses import dataclass
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from telegram.error import TelegramError

# 🔥 NAYA IMPORT: Economy database se connect karne ke liye
from shivu import application
from shivu.Database.db import eco_collection as user_collection

IST = pytz.timezone('Asia/Kolkata')
BONUS_IMG_URL = "https://files.catbox.moe/ewtw4l.png"


@dataclass(frozen=True)
class BonusConfig:
    daily_base: int = 1000
    daily_cooldown_hours: int = 24
    streak_reset_hours: int = 48
    streak_bonus_per_day: float = 0.05
    max_streak_bonus_days: int = 30
    weekly_cooldown_hours: int = 168
    weekly_days_worth: int = 7
    weekly_bonus_rate: float = 0.20


CONFIG = BonusConfig()
COOLDOWNS = {'daily': CONFIG.daily_cooldown_hours, 'weekly': CONFIG.weekly_cooldown_hours}


def now_ist() -> datetime:
    return datetime.now(IST)


def to_ist(dt: datetime) -> datetime:
    return pytz.UTC.localize(dt).astimezone(IST) if dt.tzinfo is None else dt.astimezone(IST)


def daily_reward(streak: int) -> int:
    bonus_days = min(max(streak - 1, 0), CONFIG.max_streak_bonus_days)
    return int(CONFIG.daily_base * (1 + bonus_days * CONFIG.streak_bonus_per_day))


def weekly_reward(streak: int) -> int:
    return int(daily_reward(streak) * CONFIG.weekly_days_worth * (1 + CONFIG.weekly_bonus_rate))


def next_streak(last_claim, current_streak: int, now: datetime) -> int:
    if not last_claim or now - to_ist(last_claim) > timedelta(hours=CONFIG.streak_reset_hours):
        return 1
    return current_streak + 1


def format_countdown(remaining: timedelta) -> str:
    total = int(remaining.total_seconds())
    if total <= 0:
        return "ʀᴇᴀᴅʏ"
    h, r = divmod(total, 3600)
    m, s = divmod(r, 60)
    return f"{h}ʜ {m}ᴍ" if h else (f"{m}ᴍ" if m else f"{s}s")


class UserDB:
    @staticmethod
    async def get(user_id: int) -> dict | None:
        return await user_collection.find_one({'id': user_id})

    @staticmethod
    async def ensure(user_id: int, first_name: str = None, username: str = None) -> dict:
        return await UserDB.get(user_id) or await UserDB._create(user_id, first_name, username)

    @staticmethod
    async def _create(user_id: int, first_name: str, username: str) -> dict:
        doc = {'id': user_id, 'first_name': first_name or 'Unknown', 'username': username,
               'balance': 0, 'bonus_streak': 0, 'bonus_highest_streak': 0}
        await user_collection.insert_one(doc)
        return doc

    @staticmethod
    async def update(user_id: int, inc: dict = None, set_: dict = None):
        ops = {k: v for k, v in {'$inc': inc, '$set': set_}.items() if v}
        if ops:
            await user_collection.update_one({'id': user_id}, ops, upsert=True)


def build_bonus_text(user: dict, first_name: str) -> str:
    # BUG FIXED: Added 'f' before the string to make it an f-string
    return (
        f"<b><tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji> ᴀʟɪꜱᴀ ᴡᴀɪꜰᴜ ʙᴏᴛ </b>\n\n"
        f"<tg-emoji emoji-id=\"6091632796877463207\">🧩</tg-emoji> <b>ᴀʟɪꜱᴀ ʙᴏɴᴜs sʏsᴛᴇᴍ</b>\n\n"
        f"<tg-emoji emoji-id=\"5255861796350224063\">❤️</tg-emoji> <b>ᴜsᴇʀ:</b> <b>{first_name}</b>\n"
        f"<tg-emoji emoji-id=\"5287606810168028257\">🗓</tg-emoji> <b>ᴅᴀᴛᴇ:</b> <b>{now_ist().strftime('%Y-%m-%d %H:%M')}</b>\n\n"
        f"<tg-emoji emoji-id=\"6053280534220513008\">🔥</tg-emoji> <b>ᴄᴜʀʀᴇɴᴛ sᴛʀᴇᴀᴋ:</b> <b>{user.get('bonus_streak', 0)} ᴅᴀʏs</b>\n"
        f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>ʜɪɢʜᴇsᴛ sᴛʀᴇᴀᴋ:</b> <b>{user.get('bonus_highest_streak', 0)} ᴅᴀʏs</b>\n\n"
        f"<tg-emoji emoji-id=\"6093676372381671194\">🪩</tg-emoji> <b>sᴇʟᴇᴄᴛ ᴀɴ ᴏᴘᴛɪᴏɴ ʙᴇʟᴏᴡ:</b>"
    )


def build_bonus_keyboard(user: dict, now: datetime, user_id: int) -> InlineKeyboardMarkup:
    rows = []
    
    # Daily Button 
    daily_label = "Daily 🎁"
    if last_d := user.get('last_daily_claim'):
        rem_d = timedelta(hours=COOLDOWNS['daily']) - (now - to_ist(last_d))
        if rem_d.total_seconds() > 0:
            daily_label = f"Daily ⏳ {format_countdown(rem_d)}"
            
    # Weekly Button 
    weekly_label = "Weekly 🎁"
    if last_w := user.get('last_weekly_claim'):
        rem_w = timedelta(hours=COOLDOWNS['weekly']) - (now - to_ist(last_w))
        if rem_w.total_seconds() > 0:
            weekly_label = f"Weekly ⏳ {format_countdown(rem_w)}"

    # Embed user_id inside callback_data to strictly secure buttons
    rows.append([InlineKeyboardButton(daily_label, callback_data=f"bonus:daily:{user_id}")])
    rows.append([InlineKeyboardButton(weekly_label, callback_data=f"bonus:weekly:{user_id}")])
    rows.append([
        InlineKeyboardButton("sᴛᴀᴛs", callback_data=f"bonus:stats:{user_id}"),
        InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data=f"bonus:close:{user_id}")
    ])
    return InlineKeyboardMarkup(rows)


async def bonus_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user = await UserDB.ensure(user_id, update.effective_user.first_name, update.effective_user.username)
    
    # Sent as a photo with caption
    await update.message.reply_photo(
        photo=BONUS_IMG_URL,
        caption=build_bonus_text(user, update.effective_user.first_name),
        reply_markup=build_bonus_keyboard(user, now_ist(), user_id),
        parse_mode='HTML'
    )


async def refresh_menu(query, user_id: int, now: datetime):
    user = await UserDB.get(user_id)
    first_name = user.get('first_name', 'User') if user else query.from_user.first_name
    
    await query.edit_message_caption(
        caption=build_bonus_text(user or {}, first_name),
        reply_markup=build_bonus_keyboard(user or {}, now, user_id),
        parse_mode='HTML'
    )


async def claim(update: Update, context: CallbackContext, kind: str, owner_id: int):
    query = update.callback_query
    user_id = query.from_user.id

    # Strict ownership check
    if user_id != owner_id:
        await query.answer("ᴛʜɪs ɪs ɴᴏᴛ ʏᴏᴜʀ ʙᴏɴᴜs ᴍᴇɴᴜ! ᴘʟᴇᴀsᴇ ᴛʏᴘᴇ /bonus ᴛᴏ ᴏᴘᴇɴ ʏᴏᴜʀ ᴏᴡɴ.", show_alert=True)
        return

    user = await UserDB.ensure(user_id, query.from_user.first_name, query.from_user.username)
    now = now_ist()

    if last := user.get(f'last_{kind}_claim'):
        remaining = timedelta(hours=COOLDOWNS[kind]) - (now - to_ist(last))
        if remaining.total_seconds() > 0:
            await query.answer(f"⏳ ᴄᴏᴍᴇ ʙᴀᴄᴋ ɪɴ {format_countdown(remaining)}", show_alert=True)
            return

    set_fields = {f'last_{kind}_claim': now}
    streak = user.get('bonus_streak', 0)

    if kind == 'daily':
        streak = next_streak(user.get('last_daily_claim'), streak, now)
        set_fields['bonus_streak'] = streak
        set_fields['bonus_highest_streak'] = max(streak, user.get('bonus_highest_streak', 0))
        reward = daily_reward(streak)
        alert = f"🎁 +{reward:,} ᴄᴏɪɴs! sᴛʀᴇᴀᴋ: {streak}ᴅ"
    else:
        reward = weekly_reward(streak)
        alert = f"🎁 +{reward:,} ᴄᴏɪɴs!"

    await UserDB.update(user_id, inc={'balance': reward}, set_=set_fields)
    await query.answer(alert, show_alert=True)
    await refresh_menu(query, user_id, now)


async def show_stats(update: Update, context: CallbackContext, owner_id: int):
    query = update.callback_query
    user_id = query.from_user.id

    if user_id != owner_id:
        await query.answer("ᴛʜɪs ɪs ɴᴏᴛ ʏᴏᴜʀ ʙᴏɴᴜs ᴍᴇɴᴜ! ᴘʟᴇᴀsᴇ ᴛʏᴘᴇ /bonus ᴛᴏ ᴏᴘᴇɴ ʏᴏᴜʀ ᴏᴡɴ.", show_alert=True)
        return

    user = await UserDB.ensure(user_id, query.from_user.first_name, query.from_user.username)
    streak = user.get('bonus_streak', 0)

    text = (
        f"<tg-emoji emoji-id=\"6093755816391745206\">📊</tg-emoji> <b>ʙᴏɴᴜs sᴛᴀᴛs</b>\n\n"
        f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>ʙᴀʟᴀɴᴄᴇ:</b> <b>{user.get('balance', 0):,} ᴄᴏɪɴs</b>\n"
        f"<tg-emoji emoji-id=\"6053280534220513008\">🔥</tg-emoji> <b>ᴄᴜʀʀᴇɴᴛ sᴛʀᴇᴀᴋ:</b> <b>{streak} ᴅᴀʏs</b>\n"
        f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>ʜɪɢʜᴇsᴛ sᴛʀᴇᴀᴋ:</b> <b>{user.get('bonus_highest_streak', 0)} ᴅᴀʏs</b>\n\n"
        f"<tg-emoji emoji-id=\"6093475058674576576\">🎁</tg-emoji> <b>ɴᴇxᴛ ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ:</b> <b>{daily_reward(streak):,} ᴄᴏɪɴs</b>\n"
        f"<tg-emoji emoji-id=\"6093475058674576576\">🎁</tg-emoji> <b>ɴᴇxᴛ ᴡᴇᴇᴋʟʏ ʀᴇᴡᴀʀᴅ:</b> <b>{weekly_reward(streak):,} ᴄᴏɪɴs</b>"
    )
    
    await query.answer()
    
    await query.edit_message_caption(
        caption=text, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"bonus:menu:{user_id}")]])
    )


async def back_to_menu(update: Update, context: CallbackContext, owner_id: int):
    query = update.callback_query
    if query.from_user.id != owner_id:
        await query.answer("ᴛʜɪs ɪs ɴᴏᴛ ʏᴏᴜʀ ʙᴏɴᴜs ᴍᴇɴᴜ! ᴘʟᴇᴀsᴇ ᴛʏᴘᴇ /bonus ᴛᴏ ᴏᴘᴇɴ ʏᴏᴜʀ ᴏᴡɴ.", show_alert=True)
        return
    await query.answer()
    await refresh_menu(query, owner_id, now_ist())


async def close_menu(update: Update, context: CallbackContext, owner_id: int):
    query = update.callback_query
    if query.from_user.id != owner_id:
        await query.answer("ᴛʜɪs ɪs ɴᴏᴛ ʏᴏᴜʀ ʙᴏɴᴜs ᴍᴇɴᴜ! ᴘʟᴇᴀsᴇ ᴛʏᴘᴇ /bonus ᴛᴏ ᴏᴘᴇɴ ʏᴏᴜʀ ᴏᴡɴ.", show_alert=True)
        return
    await query.answer()
    await query.message.delete()


async def bonus_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    data_parts = query.data.split(':')
    
    if len(data_parts) < 3:
        await query.answer("ᴜɴᴋɴᴏᴡɴ ᴀᴄᴛɪᴏɴ", show_alert=True)
        return

    action = data_parts[1]
    owner_id = int(data_parts[2])

    try:
        if action == 'daily':
            await claim(update, context, 'daily', owner_id)
        elif action == 'weekly':
            await claim(update, context, 'weekly', owner_id)
        elif action == 'stats':
            await show_stats(update, context, owner_id)
        elif action == 'menu':
            await back_to_menu(update, context, owner_id)
        elif action == 'close':
            await close_menu(update, context, owner_id)
        else:
            await query.answer("ᴜɴᴋɴᴏᴡɴ ᴀᴄᴛɪᴏɴ", show_alert=True)
    except TelegramError as e:
        await query.answer(f"ᴇʀʀᴏʀ: {type(e).__name__}", show_alert=True)


application.add_handler(CommandHandler("bonus", bonus_command, block=False))
application.add_handler(CallbackQueryHandler(bonus_callback, pattern=r'^bonus:', block=False))

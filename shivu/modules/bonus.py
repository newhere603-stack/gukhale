import os
import pytz
import pymongo
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from telegram.error import TelegramError

from shivu import application

IST = pytz.timezone('Asia/Kolkata')

# MongoDB connection setup using pymongo to avoid event loop conflicts
MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGO_DB_URI")
pymongo_client = pymongo.MongoClient(MONGO_URL) if MONGO_URL else None
db = pymongo_client.get_default_database() if pymongo_client and pymongo_client.get_default_database() is not None else (pymongo_client['shivu'] if pymongo_client else None)
sync_user_collection = db['user_collection'] if db is not None else None


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
    if dt.tzinfo is None:
        return pytz.UTC.localize(dt).astimezone(IST)
    return dt.astimezone(IST)


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
        def _get():
            return sync_user_collection.find_one({'id': user_id})
        return await asyncio.to_thread(_get)

    @staticmethod
    async def ensure(user_id: int, first_name: str = None, username: str = None) -> dict:
        user = await UserDB.get(user_id)
        if user:
            return user
        return await UserDB._create(user_id, first_name, username)

    @staticmethod
    async def _create(user_id: int, first_name: str, username: str) -> dict:
        doc = {
            'id': user_id, 
            'first_name': first_name or 'Unknown', 
            'username': username,
            'balance': 0, 
            'bonus_streak': 0, 
            'bonus_highest_streak': 0
        }
        def _create_doc():
            sync_user_collection.update_one({'id': user_id}, {'$setOnInsert': doc}, upsert=True)
            return sync_user_collection.find_one({'id': user_id})
        return await asyncio.to_thread(_create_doc)

    @staticmethod
    async def update(user_id: int, inc: dict = None, set_: dict = None):
        ops = {}
        if inc:
            ops['$inc'] = inc
        if set_:
            ops['$set'] = set_
        if ops:
            def _update():
                sync_user_collection.update_one({'id': user_id}, ops, upsert=True)
            await asyncio.to_thread(_update)


def build_bonus_text(user: dict, first_name: str) -> str:
    return (
        "<b>🌸 ᴀʟɪꜱᴀ ᴡᴀɪꜰᴜ ʙᴏᴛ 🫧</b>\n\n"
        "🎮 <b>ʙᴏɴᴜs sʏsᴛᴇᴍ</b>\n\n"
        f"👤 <b>User:</b> <b>{first_name}</b>\n"
        f"📅 <b>Date:</b> <b>{now_ist().strftime('%Y-%m-%d %H:%M')}</b>\n\n"
        f"🔥 <b>ᴄᴜʀʀᴇɴᴛ sᴛʀᴇᴀᴋ:</b> <b>{user.get('bonus_streak', 0)} ᴅᴀʏs</b>\n"
        f"🏆 <b>ʜɪɢʜᴇsᴛ sᴛʀᴇᴀᴋ:</b> <b>{user.get('bonus_highest_streak', 0)} ᴅᴀʏs</b>\n\n"
        "<b>sᴇʟᴇᴄᴛ ᴀɴ ᴏᴘᴛɪᴏɴ ʙᴇʟᴏᴡ:</b>"
    )


def build_bonus_keyboard(user: dict, now: datetime) -> InlineKeyboardMarkup:
    rows = []
    
    daily_label = "Daily 🎁"
    if last_d := user.get('last_daily_claim'):
        rem_d = timedelta(hours=COOLDOWNS['daily']) - (now - to_ist(last_d))
        if rem_d.total_seconds() > 0:
            daily_label = f"Daily ⏳ {format_countdown(rem_d)}"
            
    weekly_label = "Weekly 🎁"
    if last_w := user.get('last_weekly_claim'):
        rem_w = timedelta(hours=COOLDOWNS['weekly']) - (now - to_ist(last_w))
        if rem_w.total_seconds() > 0:
            weekly_label = f"Weekly ⏳ {format_countdown(rem_w)}"

    rows.append([InlineKeyboardButton(daily_label, callback_data="bonus:daily")])
    rows.append([InlineKeyboardButton(weekly_label, callback_data="bonus:weekly")])
    rows.append([
        InlineKeyboardButton("sᴛᴀᴛs", callback_data="bonus:stats"),
        InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="bonus:close")
    ])
    return InlineKeyboardMarkup(rows)


async def bonus_command(update: Update, context: CallbackContext):
    user = await UserDB.ensure(update.effective_user.id, update.effective_user.first_name, update.effective_user.username)
    await update.message.reply_text(
        build_bonus_text(user, update.effective_user.first_name),
        reply_markup=build_bonus_keyboard(user, now_ist()),
        parse_mode='HTML',
        reply_to_message_id=update.message.message_id
    )


async def refresh_menu(query, user_id: int, now: datetime):
    user = await UserDB.get(user_id)
    first_name = user.get('first_name', 'User') if user else 'User'
    await query.edit_message_text(
        build_bonus_text(user, first_name),
        reply_markup=build_bonus_keyboard(user, now),
        parse_mode='HTML'
    )


async def claim(update: Update, context: CallbackContext, kind: str):
    query = update.callback_query
    user_id = query.from_user.id
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


async def show_stats(update: Update, context: CallbackContext):
    query = update.callback_query
    user = await UserDB.ensure(query.from_user.id, query.from_user.first_name, query.from_user.username)
    streak = user.get('bonus_streak', 0)

    text = (
        "📊 <b>ʙᴏɴᴜs sᴛᴀᴛs</b>\n\n"
        f"💸 <b>ʙᴀʟᴀɴᴄᴇ:</b> <b>{user.get('balance', 0):,} ᴄᴏɪɴs</b>\n"
        f"🔥 <b>ᴄᴜʀʀᴇɴᴛ sᴛʀᴇᴀᴋ:</b> <b>{streak} ᴅᴀʏs</b>\n"
        f"🏆 <b>ʜɪɢʜᴇsᴛ sᴛʀᴇᴀᴋ:</b> <b>{user.get('bonus_highest_streak', 0)} ᴅᴀʏs</b>\n\n"
        f"🎁 <b>ɴᴇxᴛ ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ:</b> <b>{daily_reward(streak):,} ᴄᴏɪɴs</b>\n"
        f"🎁 <b>ɴᴇxᴛ ᴡᴇᴇᴋʟʏ ʀᴇᴡᴀʀᴅ:</b> <b>{weekly_reward(streak):,} ᴄᴏɪɴs</b>"
    )
    await query.answer()
    await query.edit_message_text(
        text, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data="bonus:menu")]])
    )


async def back_to_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    await refresh_menu(query, query.from_user.id, now_ist())


async def close_menu(update: Update, context: CallbackContext):
    await update.callback_query.answer()
    await update.callback_query.message.delete()


HANDLERS = {
    'daily': lambda u, c: claim(u, c, 'daily'),
    'weekly': lambda u, c: claim(u, c, 'weekly'),
    'stats': show_stats,
    'menu': back_to_menu,
    'close': close_menu,
}


async def bonus_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    
    if query.message.reply_to_message:
        owner_id = query.message.reply_to_message.from_user.id
        if owner_id != query.from_user.id:
            await query.answer("ᴛʜɪs ɪs ɴᴏᴛ ʏᴏᴜʀ ʙᴏɴᴜs ᴍᴇɴᴜ! ᴘʟᴇᴀsᴇ ᴛʏ𝒑ᴇ /bonus ᴛᴏ ᴏᴘᴇɴ ʏᴏᴜʀ ᴏᴡɴ.", show_alert=True)
            return

    data_parts = query.data.split(':', 1)
    if len(data_parts) < 2:
        await query.answer("ᴜɴᴋɴᴏᴡɴ ᴀᴄᴛɪᴏɴ", show_alert=True)
        return

    handler = HANDLERS.get(data_parts[1])
    if not handler:
        await query.answer("ᴜɴᴋɴᴏᴡɴ ᴀᴄᴛɪᴏɴ", show_alert=True)
        return
    
    try:
        await handler(update, context)
    except TelegramError as e:
        await query.answer(f"ᴇʀʀᴏʀ: {type(e).__name__}", show_alert=True)


application.add_handler(CommandHandler("bonus", bonus_command, block=False))
application.add_handler(CallbackQueryHandler(bonus_callback, pattern=r'^bonus:', block=False))

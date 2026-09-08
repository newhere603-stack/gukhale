import random
import html
import logging
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, CallbackContext

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔥 NAYA IMPORT: Economy database se connect karne ke liye
from shivu import application, db
from shivu.Database.db import eco_collection as user_collection

# 🔥 NAYA IMPORT: Task system ke daily explore-count ke liye
user_tasks_collection = db['user_tasks']
IST = timezone(timedelta(hours=5, minutes=30))

COOLDOWN_SEC = 73
FEE = 300
MIN_REWARD = 600
MAX_REWARD = 1000
MIN_BALANCE = 500

user_cooldowns = {}

EXPLORE_ACTIONS = [
    "ᴇxᴘʟᴏʀᴇᴅ ᴀ ᴅᴜɴɢᴇᴏɴ",
    "ᴠᴇɴᴛᴜʀᴇᴅ ɪɴᴛᴏ ᴀ ᴅᴀʀᴋ ғᴏʀᴇsᴛ",
    "ᴅɪsᴄᴏᴠᴇʀᴇᴅ ᴀɴᴄɪᴇɴᴛ ʀᴜɪɴs",
    "ɪɴғɪʟᴛʀᴀᴛᴇᴅ ᴀɴ ᴇʟᴠɪsʜ ᴠɪʟʟᴀɢᴇ",
    "ʀᴀɪᴅᴇᴅ ᴀ ɢᴏʙʟɪɴ ɴᴇsᴛ",
    "sᴜʀᴠɪᴠᴇᴅ ᴀɴ ᴏʀᴄ ᴅᴇɴ"
]


# 🔥 NAYA HELPER: user_tasks doc ko aaj ke din ke hisaab se reset/create karta hai
# (tasks.py ke ensure_user_data() jaisa hi logic, explore_count_today ke saath)
async def _sync_daily_reset(user_id: int, today_str: str):
    doc = await user_tasks_collection.find_one({'user_id': user_id})
    if not doc:
        await user_tasks_collection.insert_one({
            'user_id': user_id,
            'completed_daily': [],
            'completed_onetime': [],
            'coins_spent_today': 0,
            'group_messages_today': {},
            'explore_count_today': 0,
            'pending_invites': 0,
            'total_invites': 0,
            'last_reset_date': today_str
        })
    elif doc.get('last_reset_date') != today_str:
        await user_tasks_collection.update_one(
            {'user_id': user_id},
            {'$set': {
                'completed_daily': [],
                'coins_spent_today': 0,
                'group_messages_today': {},
                'explore_count_today': 0,
                'last_reset_date': today_str
            }}
        )


async def explore_cmd(update: Update, context: CallbackContext) -> None:
    if not update.message:
        return

    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "<b>ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴄᴀɴ ᴏɴʟʏ ʙᴇ ᴜsᴇᴅ ɪɴ ɢʀᴏᴜᴘs!</b>",
            parse_mode=ParseMode.HTML
        )
        return

    if update.message.reply_to_message:
        await update.message.reply_text(
            "<b>ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴄᴀɴɴᴏᴛ ʙᴇ ᴜsᴇᴅ ᴀs ᴀ ʀᴇᴘʟʏ!</b>",
            parse_mode=ParseMode.HTML
        )
        return

    user_id = update.effective_user.id
    now = datetime.now(timezone.utc)

    # Cooldown Check
    if user_id in user_cooldowns:
        elapsed = (now - user_cooldowns[user_id]).total_seconds()
        if elapsed < COOLDOWN_SEC:
            remaining = int(COOLDOWN_SEC - elapsed)
            await update.message.reply_text(
                f"<b>⏰ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ {remaining} sᴇᴄᴏɴᴅs ʙᴇғᴏʀᴇ ᴇxᴘʟᴏʀɪɴɢ ᴀɢᴀɪɴ!</b>",
                parse_mode=ParseMode.HTML
            )
            return

    # 🔥 FIX: Cooldown turant lock kar diya taaki spam/race-condition bypass na ho
    user_cooldowns[user_id] = now

    try:
        user = await user_collection.find_one({'id': user_id})
        if not user:
            # Agar DB fail hua toh cooldown wapas hata do taaki user stuck na ho
            user_cooldowns.pop(user_id, None)
            await update.message.reply_text(
                "<b>sᴛᴀʀᴛ ᴍᴇ ꜰɪʀsᴛ!</b>",
                parse_mode=ParseMode.HTML
            )
            return

        if user.get('balance', 0) < MIN_BALANCE:
            user_cooldowns.pop(user_id, None)
            await update.message.reply_text(
                f"<b>ʏᴏᴜ ɴᴇᴇᴅ ᴀᴛ ʟᴇᴀsᴛ {MIN_BALANCE} ᴄᴏɪɴs ᴛᴏ ᴇxᴘʟᴏʀᴇ!</b>",
                parse_mode=ParseMode.HTML
            )
            return

        reward = random.randint(MIN_REWARD, MAX_REWARD)
        net_reward = reward - FEE

        # Single atomic update for balance
        await user_collection.update_one(
            {'id': user_id},
            {'$inc': {'balance': net_reward}}
        )

        # 🔥 NAYA: Task system ke liye daily explore count badhao
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        await _sync_daily_reset(user_id, today_str)
        await user_tasks_collection.update_one(
            {'user_id': user_id, 'last_reset_date': today_str},
            {'$inc': {'explore_count_today': 1}}
        )

        action = random.choice(EXPLORE_ACTIONS)

        # Using correct emoji-id attribute for Telegram custom emojis
        await update.message.reply_text(
            f"<b><tg-emoji emoji-id=\"5224450179368767019\">🌎</tg-emoji> ʏᴏᴜ {action} ᴀɴᴅ ғᴏᴜɴᴅ <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {reward} ᴄᴏɪɴs!</b>\n"
            f"<b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> ᴇxᴘʟᴏʀᴀᴛɪᴏɴ ғᴇᴇ: <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {FEE} ᴄᴏɪɴs</b>",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        # Error aane par bhi cooldown lock hata do
        user_cooldowns.pop(user_id, None)
        logger.error(f"Explore error: {e}")
        await update.message.reply_text(
            f"<b>ᴇʀʀᴏʀ:</b> <code>{str(e)}</code>",
            parse_mode=ParseMode.HTML
        )

application.add_handler(CommandHandler("explore", explore_cmd, block=False))

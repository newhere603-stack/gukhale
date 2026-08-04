import random
import html
import logging
from datetime import datetime, timezone
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, CallbackContext

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from shivu import application, user_collection

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

async def explore_cmd(update: Update, context: CallbackContext) -> None:
    if not update.message:
        return

    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "<b>❌ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴄᴀɴ ᴏɴʟʏ ʙᴇ ᴜsᴇᴅ ɪɴ ɢʀᴏᴜPS!</b>",
            parse_mode=ParseMode.HTML
        )
        return

    if update.message.reply_to_message:
        await update.message.reply_text(
            "<b>❌ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴄᴀɴɴᴏᴛ ʙᴇ ᴜsᴇᴅ ᴀs ᴀ ʀᴇᴘʟʏ!</b>",
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

    try:
        user = await user_collection.find_one({'id': user_id})
        if not user:
            await update.message.reply_text(
                "<b>sᴛᴀʀᴛ ᴍᴇ ꜰɪʀsᴛ!</b>",
                parse_mode=ParseMode.HTML
            )
            return

        if user.get('balance', 0) < MIN_BALANCE:
            await update.message.reply_text(
                f"<b>ʏᴏᴜ ɴᴇᴇᴅ ᴀᴛ ʟᴇᴀsᴛ {MIN_BALANCE} ᴄᴏɪɴs ᴛᴏ ᴇxᴘʟᴏʀᴇ!</b>",
                parse_mode=ParseMode.HTML
            )
            return

        reward = random.randint(MIN_REWARD, MAX_REWARD)
        net_reward = reward - FEE

        await user_collection.update_one(
            {'id': user_id},
            {'$inc': {'balance': net_reward}}
        )
        user_cooldowns[user_id] = now
        action = random.choice(EXPLORE_ACTIONS)

        # Fixed Custom Emoji syntax to use <tg-emoji>
        await update.message.reply_text(
            f"<b><tg-emoji id=\"6093547287139590167\">🗺️</tg-emoji> ʏᴏᴜ {action} ᴀɴᴅ ғᴏᴜɴᴅ <tg-emoji id=\"5472030678633684592\">💸</tg-emoji> {reward} ᴄᴏɪɴs!</b>\n"
            f"<b><tg-emoji id=\"5472030678633684592\">💸</tg-emoji> ᴇxᴘʟᴏʀᴀᴛɪᴏɴ ғᴇᴇ: <tg-emoji id=\"5472030678633684592\">💸</tg-emoji> {FEE} ᴄᴏɪɴs</b>",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"Explore error: {e}")
        await update.message.reply_text(
            f"<b>ᴇʀʀᴏʀ:</b> <code>{str(e)}</code>",
            parse_mode=ParseMode.HTML
        )

application.add_handler(CommandHandler("explore", explore_cmd, block=False))

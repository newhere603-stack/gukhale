import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, CallbackContext

from shivu import application, user_collection


@dataclass(frozen=True)
class ExploreConfig:
    cooldown: int = 73
    fee: int = 300
    min_reward: int = 600
    max_reward: int = 1000
    min_balance: int = 500


CONFIG = ExploreConfig()
user_cooldowns = {}

EXPLORE_ACTIONS = [
    "ᴇxᴘʟᴏʀᴇᴅ ᴀ ᴅᴜɴɢᴇᴏɴ",
    "ᴠᴇɴᴛᴜʀᴇᴅ ɪɴᴛᴏ ᴀ ᴅᴀʀᴋ ғᴏʀᴇsᴛ",
    "ᴅɪsᴄᴏᴠᴇʀᴇᴅ ᴀɴᴄɪᴇɴᴛ ʀᴜɪɴs",
    "ɪɴғɪʟᴛʀᴀᴛᴇᴅ ᴀɴ ᴇʟᴠɪsʜ ᴠɪʟʟᴀɢᴇ",
    "ʀᴀɪᴅᴇᴅ ᴀ ɢᴏʙʟɪɴ ɴᴇsᴛ",
    "sᴜʀᴠɪᴠᴇᴅ ᴀɴ ᴏʀᴄ ᴅᴇɴ"
]


def check_cooldown(user_id: int) -> Optional[int]:
    if user_id not in user_cooldowns:
        return None
    
    now = datetime.now(timezone.utc)
    elapsed = (now - user_cooldowns[user_id]).total_seconds()
    remaining = CONFIG.cooldown - elapsed
    return int(remaining) if remaining > 0 else None


async def explore_cmd(update: Update, context: CallbackContext) -> None:
    if not update.message:
        return

    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "<b>❌ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴄᴀɴ ᴏɴʟʏ ʙᴇ ᴜsᴇᴅ ɪɴ ɢʀᴏᴜᴘs!</b>", 
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

    remaining = check_cooldown(user_id)
    if remaining is not None:
        await update.message.reply_text(
            f"<b>⏰ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ {remaining} sᴇᴄᴏɴᴅs ʙᴇғᴏʀᴇ ᴇxᴘʟᴏʀɪɴɢ ᴀɢᴀɪɴ!</b>",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        user = await user_collection.find_one({'id': user_id})
        
        if not user:
            await update.message.reply_text(
                "<b>❌ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴ ᴀᴄᴄᴏᴜɴᴛ ʏᴇᴛ!</b>", 
                parse_mode=ParseMode.HTML
            )
            return

        if user.get('balance', 0) < CONFIG.min_balance:
            await update.message.reply_text(
                f"<b>❌ ʏᴏᴜ ɴᴇᴇᴅ ᴀᴛ ʟᴇᴀsᴛ {CONFIG.min_balance} ᴄᴏɪɴs ᴛᴏ ᴇxᴘʟᴏʀᴇ!</b>",
                parse_mode=ParseMode.HTML
            )
            return

        reward = random.randint(CONFIG.min_reward, CONFIG.max_reward)
        net_reward = reward - CONFIG.fee

        await user_collection.update_one(
            {'id': user_id},
            {'$inc': {'balance': net_reward}}
        )

        user_cooldowns[user_id] = datetime.now(timezone.utc)

        action = random.choice(EXPLORE_ACTIONS)
        await update.message.reply_text(
            f"<b>🗺️ ʏᴏᴜ {action} ᴀɴᴅ ғᴏᴜɴᴅ 💸 {reward} ᴄᴏɪɴs!</b>\n"
            f"<b>💸 ᴇxᴘʟᴏʀᴀᴛɪᴏɴ ғᴇᴇ: 💸 {CONFIG.fee} ᴄᴏɪɴs</b>",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        await update.message.reply_text(
            f"<b>❌ ᴇʀʀᴏʀ:</b> <code>{str(e)}</code>",
            parse_mode=ParseMode.HTML
        )


application.add_handler(CommandHandler("explore", explore_cmd, block=False))

import random
from dataclasses import dataclass
from datetime import datetime, timezone
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


@dataclass
class ExploreResult:
    success: bool
    message: str
    reward: int = 0


CONFIG = ExploreConfig()
user_cooldowns = {}

# Sabhi actions ko Small Caps font aur bold me kar diya gaya hai
EXPLORE_ACTIONS = [
    "<b>ᴇxᴘʟᴏʀᴇᴅ ᴀ ᴅᴜɴɢᴇᴏɴ</b>",
    "<b>ᴠᴇɴᴛᴜʀᴇᴅ ɪɴᴛᴏ ᴀ ᴅᴀʀᴋ ғᴏʀᴇsᴛ</b>",
    "<b>ᴅɪsᴄᴏᴠᴇʀᴇᴅ ᴀɴᴄɪᴇɴᴛ ʀᴜɪɴs</b>",
    "<b>ɪɴғɪʟᴛʀᴀᴛᴇᴅ ᴀɴ ᴇʟᴠɪsʜ ᴠɪʟʟᴀɢᴇ</b>",
    "<b>ʀᴀɪᴅᴇᴅ ᴀ ɢᴏʙʟɪɴ ɴᴇsᴛ</b>",
    "<b>sᴜʀᴠɪᴠᴇᴅ ᴀɴ ᴏʀᴄ ᴅᴇɴ</b>"
]


def check_cooldown(user_id: int) -> int | None:
    if user_id not in user_cooldowns:
        return None
    
    elapsed = (datetime.now(timezone.utc) - user_cooldowns[user_id]).total_seconds()
    return None if elapsed >= CONFIG.cooldown else int(CONFIG.cooldown - elapsed)


async def explore_cmd(update: Update, context: CallbackContext) -> None:
    if not update.message:
        return

    if update.effective_chat.type == "private":
        await update.message.reply_text("<b>❌ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴄᴀɴ ᴏɴʟʏ ʙᴇ ᴜsᴇᴅ ɪɴ ɢʀᴏᴜᴘs!</b>", parse_mode=ParseMode.HTML)
        return

    if update.message.reply_to_message:
        await update.message.reply_text("<b>❌ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴄᴀɴɴᴏᴛ ʙᴇ ᴜsᴇᴅ ᴀs ᴀ ʀᴇᴘʟʏ!</b>", parse_mode=ParseMode.HTML)
        return

    user_id = update.effective_user.id

    if remaining := check_cooldown(user_id):
        await update.message.reply_text(
            f"<b>⏰ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ {remaining} sᴇᴄᴏɴᴅs ʙᴇғᴏʀᴇ ᴇxᴘʟᴏʀɪɴɢ ᴀɢᴀɪɴ!</b>",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        user = await user_collection.find_one({'id': user_id})
        
        if not user:
            await update.message.reply_text("<b>❌ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴ ᴀᴄᴄᴏᴜɴᴛ ʏᴇᴛ!</b>", parse_mode=ParseMode.HTML)
            return

        if user.get('balance', 0) < CONFIG.min_balance:
            await update.message.reply_text(
                f"<b>❌ ʏᴏᴜ ɴᴇᴇᴅ ᴀᴛ ʟᴇᴀsᴛ {CONFIG.min_balance} ᴛᴏᴋᴇɴs ᴛᴏ ᴇxᴘʟᴏʀᴇ!</b>",
                parse_mode=ParseMode.HTML
            )
            return

        reward = random.randint(CONFIG.min_reward, CONFIG.max_reward)
        
        await user_collection.update_one(
            {'id': user_id},
            {'$inc': {'balance': reward - CONFIG.fee}}
        )

        user_cooldowns[user_id] = datetime.now(timezone.utc)

        action = random.choice(EXPLORE_ACTIONS)
        await update.message.reply_text(
            f"<b>🗺️ ʏᴏᴜ</b> {action} <b>ᴀɴᴅ ғᴏᴜɴᴅ 💸 {reward} ᴄᴏɪɴs!</b>\n"
            f"<b>💸 ᴇxᴘʟᴏʀᴀᴛɪᴏɴ ғᴇᴇ: 💸 {CONFIG.fee} ᴄᴏɪɴs</b>",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        await update.message.reply_text(
            f"<b>❌ ᴇʀʀᴏʀ:</b> <code>{str(e)}</code>",
            parse_mode=ParseMode.HTML
        )


application.add_handler(CommandHandler("explore", explore_cmd, block=False))

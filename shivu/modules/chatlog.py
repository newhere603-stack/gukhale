import asyncio
from typing import Dict, Any
from datetime import datetime
from telegram import Update
from telegram.ext import MessageHandler, filters, ContextTypes
from shivu import user_collection, application, LOGGER

LOG_GROUP_ID = -1003893927065

def create_log_message(title: str, data: Dict[str, Any]) -> str:
    """Beautiful bold and small-caps log designer."""
    timestamp = datetime.now().strftime("%I:%M %p • %d/%m/%y")
    base = f"<b>{title}</b>\n\n"
    
    items = list(data.items())
    for i, (key, value) in enumerate(items):
        prefix = "<b>╰</b>" if i == len(items) - 1 else "<b>├</b>"
        base += f"{prefix} <b>{key} :</b> {value}\n"
        
    base += f"\n<b>⌚ ᴛɪᴍᴇ :</b> <b>{timestamp}</b>"
    return base


async def send_log_to_group(text: str):
    try:
        await application.bot.send_message(
            chat_id=LOG_GROUP_ID,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return True
    except Exception as e:
        LOGGER.error(f"Log Sending Error: {e}")
        return False


# --- 1. USER START LOG ---
async def track_bot_start(user_id: int, first_name: str, username: str, is_new: bool):
    try:
        user_mention = f"<b><a href='tg://user?id={user_id}'>{first_name}</a></b>"
        username_str = f"<b>@{username}</b>" if username else "<b>ɴᴏ ᴜsᴇʀɴᴀᴍᴇ</b>"
        
        try:
            total_users = await user_collection.count_documents({})
        except:
            total_users = "N/A"
            
        status = f"<b>ɴᴇᴡ ᴜsᴇʀ #{total_users}</b>" if is_new else "<b>ʀᴇᴛᴜʀɴɪɴɢ ᴜsᴇʀ</b>"
        
        data = {
            "sᴛᴀᴛᴜs": status,
            "ᴜsᴇʀ": user_mention,
            "ɪᴅ": f"<code>{user_id}</code>",
            "ᴜsᴇʀɴᴀᴍᴇ": username_str
        }
        
        log = create_log_message("˹ ʙᴏᴛ sᴛᴀʀᴛᴇᴅ ˼ 🌸", data)
        await send_log_to_group(log)
    except Exception as e:
        LOGGER.error(f"Track start error: {e}")


# --- 2. ADMIN / SUDO ACTION LOGS ---
async def log_admin_action(action_name: str, admin_name: str, admin_id: int, details: Dict[str, Any]):
    try:
        data = {
            "ᴀᴅᴍɪɴ": f"<b><a href='tg://user?id={admin_id}'>{admin_name}</a></b>",
            "ɪᴅ": f"<code>{admin_id}</code>"
        }
        data.update({k: f"<b>{v}</b>" if not str(v).startswith("<") else v for k, v in details.items()})
        
        log = create_log_message(f"˹ ᴀᴅᴍɪɴ ᴀᴄᴛɪᴏɴ ˼ ⚡", data)
        await send_log_to_group(log)
    except Exception as e:
        LOGGER.error(f"Admin log error: {e}")


# --- 3. GROUP JOIN AND LEAVE LOGS (Direct Service Message Handler) ---
async def track_group_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message
        if not message:
            return

        bot_id = context.bot.id

        # Check if bot was added to the group
        if message.new_chat_members:
            if any(member.id == bot_id for member in message.new_chat_members):
                chat = message.chat
                added_by = message.from_user
                added_by_mention = f"<b><a href='tg://user?id={added_by.id}'>{added_by.first_name}</a></b>" if added_by else "<b>ᴜɴᴋɴᴏᴡɴ</b>"
                
                try:
                    count = await context.bot.get_chat_members_count(chat.id)
                    member_count = f"<b>{count}</b>"
                except:
                    member_count = "<b>N/A</b>"

                data = {
                    "ᴄʜᴀᴛ": f"<b>{chat.title}</b>",
                    "ɪᴅ": f"<code>{chat.id}</code>",
                    "ᴜsᴇʀɴᴀᴍᴇ": f"<b>@{chat.username}</b>" if chat.username else "<b>ᴘʀɪᴠᴀᴛᴇ</b>",
                    "ᴍᴇᴍʙᴇʀs": member_count,
                    "ᴀᴅᴅᴇᴅ ʙʏ": added_by_mention
                }
                log = create_log_message("˹ ɢʀᴀʙʙɪɴɢ ʏᴏᴜʀ ᴡᴀɪғᴜ ˼ 🥀", data)
                await send_log_to_group(log)

        # Check if bot was removed / left the group
        if message.left_chat_member:
            if message.left_chat_member.id == bot_id:
                chat = message.chat
                removed_by = message.from_user
                removed_by_mention = f"<b><a href='tg://user?id={removed_by.id}'>{removed_by.first_name}</a></b>" if removed_by else "<b>ᴜɴᴋɴᴏᴡɴ</b>"

                data = {
                    "ᴄʜᴀᴛ": f"<b>{chat.title}</b>",
                    "ɪᴅ": f"<code>{chat.id}</code>",
                    "ᴜsᴇʀɴᴀᴍᴇ": f"<b>@{chat.username}</b>" if chat.username else "<b>ᴘʀɪᴠᴀᴛᴇ</b>",
                    "ʀᴇᴍᴏᴠᴇᴅ ʙʏ": removed_by_mention
                }
                log = create_log_message("˹ ʟᴇғᴛ ɢʀᴏᴜᴘ ˼ ✫", data)
                await send_log_to_group(log)

    except Exception as e:
        LOGGER.error(f"Group membership tracking error: {e}", exc_info=True)

# Register the message handler for status updates
application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER, track_group_membership))
LOGGER.info("✓ Chatlog module loaded with direct MessageHandler service detection")

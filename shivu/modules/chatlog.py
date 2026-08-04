import asyncio
from typing import Dict, Any
from datetime import datetime

from telegram import Update
from telegram.ext import ChatMemberHandler, ContextTypes

from shivu import user_collection, application

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
    """Sends logs using PTB (application.bot) directly"""
    try:
        await application.bot.send_message(
            chat_id=LOG_GROUP_ID,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return True
    except Exception as e:
        print(f"Log Sending Error: {e}")
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
        print(f"Track start error: {e}")


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
        pass


# --- 3. GROUP JOIN AND LEAVE LOGS (PTB Native Handler) ---
async def on_bot_membership_changed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    PTB ka MyChatMember handler. Ye strictly tab trigger hoga 
    jab bot ko kisi group me add ya remove kiya jayega.
    """
    result = update.my_chat_member
    if not result:
        return

    chat = result.chat
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    action_by = result.from_user

    chat_title = f"<b>{chat.title}</b>"
    chat_username = f"<b>@{chat.username}</b>" if chat.username else "<b>ᴘʀɪᴠᴀᴛᴇ</b>"
    action_user = f"<b><a href='tg://user?id={action_by.id}'>{action_by.first_name}</a></b>" if action_by else "<b>ᴜɴᴋɴᴏᴡɴ</b>"

    # CONDITION A: BOT WAS ADDED TO A GROUP
    if old_status not in ['member', 'administrator'] and new_status in ['member', 'administrator']:
        try:
            count = await chat.get_member_count()
            member_count = f"<b>{count}</b>"
        except:
            member_count = "<b>N/A</b>"
            
        data = {
            "ᴄʜᴀᴛ": chat_title,
            "ɪᴅ": f"<code>{chat.id}</code>",
            "ᴜsᴇʀɴᴀᴍᴇ": chat_username,
            "ᴍᴇᴍʙᴇʀs": member_count,
            "ᴀᴅᴅᴇᴅ ʙʏ": action_user
        }
        log = create_log_message("˹ ɢʀᴀʙʙɪɴɢ ʏᴏᴜʀ ᴡᴀɪғᴜ ˼ 🥀", data)
        await send_log_to_group(log)
        
    # CONDITION B: BOT WAS REMOVED / KICKED FROM A GROUP
    elif old_status in ['member', 'administrator'] and new_status in ['kicked', 'left', 'restricted']:
        data = {
            "ᴄʜᴀᴛ": chat_title,
            "ɪᴅ": f"<code>{chat.id}</code>",
            "ᴜsᴇʀɴᴀᴍᴇ": chat_username,
            "ʀᴇᴍᴏᴠᴇᴅ ʙʏ": action_user
        }
        log = create_log_message("˹ ʟᴇғᴛ ɢʀᴏᴜᴘ ˼ ✫", data)
        await send_log_to_group(log)

# Add handler to application
application.add_handler(ChatMemberHandler(on_bot_membership_changed, ChatMemberHandler.MY_CHAT_MEMBER))

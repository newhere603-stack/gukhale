import asyncio
from typing import Dict, Any
from datetime import datetime
from pyrogram import Client
from pyrogram.types import ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus

# Importing both Pyrogram (app) and PTB (application)
from shivu import user_collection, shivuu as app, application

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
    """
    Sends logs using PTB (application.bot). 
    This bypasses Pyrogram's peer cache, preventing 'PeerIdInvalid' errors completely.
    """
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


# --- 1. BOT RESTART LOG (Bulletproof Startup) ---
async def startup_log_task():
    """Waits for the bot to fully initialize before sending the restart log."""
    print("Waiting for bot to come online to send startup log...")
    
    # Loop continuously until the bot is officially online
    while True:
        try:
            bot_info = await application.bot.get_me()
            if bot_info:
                break
        except Exception:
            await asyncio.sleep(5)  # Wait 5 seconds and check again
    
    try:
        data = {
            "ʙᴏᴛ": f"<b>@{bot_info.username}</b>",
            "sᴛᴀᴛᴜs": "<b>ᴏɴʟɪɴᴇ & ʀᴇᴀᴅʏ ⚡</b>"
        }
        log = create_log_message("˹ ʙᴏᴛ ʀᴇsᴛᴀʀᴛᴇᴅ ˼ 🔄", data)
        await send_log_to_group(log)
        print("Startup log sent successfully!")
    except Exception as e:
        print(f"Startup log error: {e}")

# Create the startup task securely in the event loop
loop = asyncio.get_event_loop()
if loop.is_running():
    loop.create_task(startup_log_task())


# --- 2. USER START LOG ---
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


# --- 3. ADMIN / SUDO ACTION LOGS ---
async def log_admin_action(action_name: str, admin_name: str, admin_id: int, details: Dict[str, Any]):
    """You can import and call this function from your sudo/redeem modules."""
    try:
        data = {
            "ᴀᴅᴍɪɴ": f"<b><a href='tg://user?id={admin_id}'>{admin_name}</a></b>",
            "ɪᴅ": f"<code>{admin_id}</code>"
        }
        # Safely bold all details
        data.update({k: f"<b>{v}</b>" if not str(v).startswith("<") else v for k, v in details.items()})
        
        log = create_log_message(f"˹ ᴀᴅᴍɪɴ ᴀᴄᴛɪᴏɴ ˼ ⚡", data)
        await send_log_to_group(log)
    except Exception as e:
        print(f"Admin log error: {e}")


# --- 4 & 5. GROUP JOIN AND LEAVE LOGS (API Level Detection) ---
@app.on_chat_member_updated()
async def bot_added_or_removed(client: Client, update: ChatMemberUpdated):
    """
    This uses ChatMemberUpdated instead of reading chat messages. 
    It triggers reliably straight from Telegram's servers.
    """
    try:
        bot = await client.get_me()
        
        # We only care if the update is about our bot
        if not update.new_chat_member or update.new_chat_member.user.id != bot.id:
            return

        old_status = update.old_chat_member.status if update.old_chat_member else None
        new_status = update.new_chat_member.status

        chat_title = f"<b>{update.chat.title}</b>"
        chat_username = f"<b>@{update.chat.username}</b>" if update.chat.username else "<b>ᴘʀɪᴠᴀᴛᴇ</b>"
        action_by = f"<b><a href='tg://user?id={update.from_user.id}'>{update.from_user.first_name}</a></b>" if update.from_user else "<b>ᴜɴᴋɴᴏᴡɴ</b>"
        
        # CONDITION A: BOT WAS ADDED TO A GROUP
        if new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR] and old_status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
            try:
                count = await client.get_chat_members_count(update.chat.id)
                member_count = f"<b>{count}</b>"
            except:
                member_count = "<b>N/A</b>"
                
            data = {
                "ᴄʜᴀᴛ": chat_title,
                "ɪᴅ": f"<code>{update.chat.id}</code>",
                "ᴜsᴇʀɴᴀᴍᴇ": chat_username,
                "ᴍᴇᴍʙᴇʀs": member_count,
                "ᴀᴅᴅᴇᴅ ʙʏ": action_by
            }
            log = create_log_message("˹ ɢʀᴀʙʙɪɴɢ ʏᴏᴜʀ ᴡᴀɪғᴜ ˼ 🥀", data)
            await send_log_to_group(log)
            
        # CONDITION B: BOT WAS REMOVED FROM A GROUP
        elif new_status in [ChatMemberStatus.BANNED, ChatMemberStatus.LEFT, ChatMemberStatus.RESTRICTED] and old_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
            data = {
                "ᴄʜᴀᴛ": chat_title,
                "ɪᴅ": f"<code>{update.chat.id}</code>",
                "ᴜsᴇʀɴᴀᴍᴇ": chat_username,
                "ʀᴇᴍᴏᴠᴇᴅ ʙʏ": action_by
            }
            log = create_log_message("˹ ʟᴇғᴛ ɢʀᴏᴜᴘ ˼ ✫", data)
            await send_log_to_group(log)
            
    except Exception as e:
        print(f"Membership update error: {e}")

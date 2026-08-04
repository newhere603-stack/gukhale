import asyncio
from typing import Dict, Any
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait, PeerIdInvalid
from shivu import user_collection, shivuu as app

# Yahan aapki group ID set kar di gayi hai
LOG_GROUP_ID = -1003893927065

def create_log_message(title: str, data: Dict[str, Any]) -> str:
    """Beautiful bold + small caps text designer"""
    timestamp = datetime.now().strftime("%I:%M %p • %d/%m/%y")
    base = f"<b>{title}</b>\n\n"
    
    items = list(data.items())
    for i, (key, value) in enumerate(items):
        prefix = "<b>╰</b>" if i == len(items) - 1 else "<b>├</b>"
        base += f"{prefix} <b>{key} :</b> {value}\n"
        
    base += f"\n<b>⌚ ᴛɪᴍᴇ :</b> <b>{timestamp}</b>"
    return base


async def send_log_to_group(text: str):
    """Bulletproof sender jo bot connected hone ka wait karta hai"""
    # Wait until bot is fully connected
    while not app.is_connected:
        await asyncio.sleep(2)
        
    for attempt in range(3):
        try:
            await app.send_message(
                chat_id=LOG_GROUP_ID, 
                text=text, 
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            return True
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except PeerIdInvalid:
            # Agar bot bhul gaya hai group ko toh force update karega
            try:
                await app.get_chat(LOG_GROUP_ID)
                await asyncio.sleep(1)
            except Exception:
                pass
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Log Error: {e}")
            await asyncio.sleep(2)
    return False


# --- 1. BOT RESTART LOG (Jab bot on hoga) ---
async def on_bot_startup():
    while not app.is_connected:
        await asyncio.sleep(2)
    
    try:
        bot = await app.get_me()
        data = {
            "ʙᴏᴛ": f"<b>@{bot.username}</b>",
            "sᴛᴀᴛᴜs": "<b>ᴏɴʟɪɴᴇ & ʀᴇᴀᴅʏ ⚡</b>"
        }
        log = create_log_message("˹ ʙᴏᴛ ʀᴇsᴛᴀʀᴛᴇᴅ ˼ 🔄", data)
        await send_log_to_group(log)
    except Exception as e:
        print(f"Startup log error: {e}")

# Start the background task
if asyncio.get_event_loop().is_running():
    asyncio.create_task(on_bot_startup())


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
        asyncio.create_task(send_log_to_group(log))
    except Exception as e:
        print(f"Track start error: {e}")


# --- 3. ADMIN / SUDO LOGS (Kahin se bhi use kar sakte hain) ---
async def log_admin_action(action_name: str, admin_name: str, admin_id: int, details: Dict[str, Any]):
    try:
        data = {
            "ᴀᴅᴍɪɴ": f"<b><a href='tg://user?id={admin_id}'>{admin_name}</a></b>",
            "ɪᴅ": f"<code>{admin_id}</code>"
        }
        data.update({k: f"<b>{v}</b>" if not str(v).startswith("<") else v for k, v in details.items()})
        
        log = create_log_message(f"˹ ᴀᴅᴍɪɴ ᴀᴄᴛɪᴏɴ ˼ ⚡", data)
        asyncio.create_task(send_log_to_group(log))
    except Exception as e:
        pass


async def get_chat_member_count(chat_id: int) -> str:
    try:
        count = await app.get_chat_members_count(chat_id)
        return f"<b>{count}</b>"
    except:
        return "<b>N/A</b>"


# --- 4. GROUP JOIN LOG ---
# (Group = 20 use kiya hai taaki kisi aur command se clash na ho)
@app.on_message(filters.new_chat_members, group=20)
async def on_bot_added(client: Client, message: Message):
    try:
        bot = await client.get_me()
        if not any(user.id == bot.id for user in message.new_chat_members):
            return
            
        added_by = f"<b><a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a></b>" if message.from_user else "<b>ᴜɴᴋɴᴏᴡɴ</b>"
        chat_title = f"<b>{message.chat.title}</b>"
        chat_username = f"<b>@{message.chat.username}</b>" if message.chat.username else "<b>ᴘʀɪᴠᴀᴛᴇ</b>"
        member_count = await get_chat_member_count(message.chat.id)
        
        data = {
            "ᴄʜᴀᴛ": chat_title,
            "ɪᴅ": f"<code>{message.chat.id}</code>",
            "ᴜsᴇʀɴᴀᴍᴇ": chat_username,
            "ᴍᴇᴍʙᴇʀs": member_count,
            "ᴀᴅᴅᴇᴅ ʙʏ": added_by
        }
        
        log = create_log_message("˹ ɢʀᴀʙʙɪɴɢ ʏᴏᴜʀ ᴡᴀɪғᴜ ˼ 🥀", data)
        asyncio.create_task(send_log_to_group(log))
    except Exception as e:
        print(f"Join log error: {e}")


# --- 5. GROUP LEAVE LOG ---
@app.on_message(filters.left_chat_member, group=21)
async def on_bot_kicked(client: Client, message: Message):
    try:
        bot = await client.get_me()
        if message.left_chat_member.id != bot.id:
            return
            
        removed_by = f"<b><a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a></b>" if message.from_user else "<b>ᴜɴᴋɴᴏᴡɴ</b>"
        chat_title = f"<b>{message.chat.title}</b>"
        chat_username = f"<b>@{message.chat.username}</b>" if message.chat.username else "<b>ᴘʀɪᴠᴀᴛᴇ</b>"
        
        data = {
            "ᴄʜᴀᴛ": chat_title,
            "ɪᴅ": f"<code>{message.chat.id}</code>",
            "ᴜsᴇʀɴᴀᴍᴇ": chat_username,
            "ʀᴇᴍᴏᴠᴇᴅ ʙʏ": removed_by
        }
        
        log = create_log_message("˹ ʟᴇғᴛ ɢʀᴏᴜᴘ ˼ ✫", data)
        asyncio.create_task(send_log_to_group(log))
    except Exception as e:
        print(f"Leave log error: {e}")

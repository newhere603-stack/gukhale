import asyncio
from typing import Dict, Any
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import MessageHandler, CommandHandler, filters, ContextTypes
from shivu import user_collection, application, LOGGER

LOG_GROUP_ID = -1003893927065
OWNER_ID = 7657218453

# Indian Standard Time (IST -> UTC +5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def create_log_message(title: str, data: Dict[str, Any]) -> str:
    timestamp = datetime.now(IST).strftime("%I:%M %p • %d/%m/%y")
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
            total_users = "ɴ/ᴀ"
            
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


# --- 3. GROUP JOIN AND LEAVE LOGS ---
async def track_group_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message
        if not message:
            return

        bot_id = context.bot.id

        # Check if bot was added to the group
        if message.new_chat_members and any(member.id == bot_id for member in message.new_chat_members):
            chat = message.chat
            added_by = message.from_user
            
            added_by_name = added_by.first_name if added_by.first_name else "ᴜsᴇʀ"
            added_by_mention = f"<b><a href='tg://user?id={added_by.id}'>{added_by_name}</a></b>" if added_by else "<b>ᴜɴᴋɴᴏᴡɴ</b>"
            
            try:
                count = await context.bot.get_chat_member_count(chat.id)
                member_count = f"<b>{count}</b>"
            except Exception as e:
                LOGGER.error(f"Member Count Error: {e}")
                member_count = "<b>ɴ/ᴀ</b>"

            invite_link = ""
            try:
                invite_link = await context.bot.export_chat_invite_link(chat.id)
            except Exception:
                if chat.username:
                    invite_link = f"https://t.me/{chat.username}"
                else:
                    invite_link = "No Admin Rights"

            if invite_link.startswith("http"):
                chat_name = f"<b><a href='{invite_link}'>{chat.title}</a></b>"
                link_status = f"<b><a href='{invite_link}'>ᴄʟɪᴄᴋ ʜᴇʀᴇ</a></b>"
            else:
                chat_name = f"<b>{chat.title}</b>"
                link_status = "<b>ʙᴏᴛ ɴᴇᴇᴅs ᴀᴅᴍɪɴ ʀɪɢʜᴛs ⚠️</b>"

            data = {
                "ᴄʜᴀᴛ": chat_name,
                "ɪᴅ": f"<code>{chat.id}</code>",
                "ᴜsᴇʀɴᴀᴍᴇ": f"<b>@{chat.username}</b>" if chat.username else "<b>ᴘʀɪᴠᴀᴛᴇ</b>",
                "ᴍᴇᴍʙᴇʀs": member_count,
                "ʟɪɴᴋ": link_status,
                "ᴀᴅᴅᴇᴅ ʙʏ": added_by_mention
            }
            log = create_log_message("˹ ɴᴇᴡ ɢʀᴏᴜᴘ ᴀᴅᴅᴇᴅ ˼ 🥀", data)
            await send_log_to_group(log)

        # Check if bot was removed / left the group
        elif message.left_chat_member and message.left_chat_member.id == bot_id:
            chat = message.chat
            removed_by = message.from_user
            
            removed_by_name = removed_by.first_name if removed_by.first_name else "ᴜsᴇʀ"
            removed_by_mention = f"<b><a href='tg://user?id={removed_by.id}'>{removed_by_name}</a></b>" if removed_by else "<b>ᴜɴᴋɴᴏᴡɴ</b>"

            try:
                count = await context.bot.get_chat_member_count(chat.id)
                member_count = f"<b>{count}</b>"
            except:
                member_count = "<b>ɴ/ᴀ (ɴᴏ ᴀᴄᴄᴇss)</b>"
                
            if chat.username:
                chat_name = f"<b><a href='https://t.me/{chat.username}'>{chat.title}</a></b>"
            else:
                chat_name = f"<b>{chat.title}</b>"

            data = {
                "ᴄʜᴀᴛ": chat_name,
                "ɪᴅ": f"<code>{chat.id}</code>",
                "ᴜsᴇʀɴᴀᴍᴇ": f"<b>@{chat.username}</b>" if chat.username else "<b>ᴘʀɪᴠᴀᴛᴇ</b>",
                "ᴍᴇᴍʙᴇʀs": member_count,
                "ʀᴇᴍᴏᴠᴇᴅ ʙʏ": removed_by_mention
            }
            log = create_log_message("˹ ʟᴇғᴛ ɢʀᴏᴜᴘ ˼ ✫", data)
            await send_log_to_group(log)

    except Exception as e:
        LOGGER.error(f"Group membership tracking error: {e}", exc_info=True)


# --- 4. OWNER COMMAND TO GET GROUP LINK ---
async def fetch_group_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner ke liye command: /grouplink <chat_id>"""
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return # Ignore ordinary users silently
    
    if not context.args:
        await update.message.reply_text("<b>ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ɢʀᴏᴜᴘ ɪᴅ.\nᴇxᴀᴍᴘʟᴇ:</b> <code>/grouplink -1001234567890</code>", parse_mode="HTML")
        return
        
    chat_id = context.args[0]
    
    try:
        chat_id = int(chat_id)
    except ValueError:
        await update.message.reply_text("<b>ɪɴᴠᴀʟɪᴅ ɪᴅ ғᴏʀᴍᴀᴛ. ɪᴅ ᴍᴜsᴛ ʙᴇ ᴀ ɴᴜᴍʙᴇʀ.</b>", parse_mode="HTML")
        return

    m = await update.message.reply_text("<b>ғᴇᴛᴄʜɪɴɢ ʟɪɴᴋ, ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ...</b>", parse_mode="HTML")
    
    try:
        # Export Link
        invite_link = await context.bot.export_chat_invite_link(chat_id)
        chat = await context.bot.get_chat(chat_id)
        
        try:
            count = await context.bot.get_chat_member_count(chat.id)
            member_count = f"<b>{count}</b>"
        except:
            member_count = "<b>ɴ/ᴀ</b>"
            
        data = {
            "ᴄʜᴀᴛ": f"<b><a href='{invite_link}'>{chat.title}</a></b>",
            "ɪᴅ": f"<code>{chat.id}</code>",
            "ᴍᴇᴍʙᴇʀs": member_count,
            "ʟɪɴᴋ": f"<b><a href='{invite_link}'>ᴊᴏɪɴ ʜᴇʀᴇ</a></b>",
            "ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ": f"<b><a href='tg://user?id={user_id}'>ᴏᴡɴᴇʀ</a></b>"
        }
        
        log = create_log_message("˹ ɢʀᴏᴜᴘ ʟɪɴᴋ ғᴇᴛᴄʜᴇᴅ ˼ 🔗", data)
        await send_log_to_group(log)
        
        await m.edit_text("<b>ᴅᴏɴᴇ! sᴜᴄᴄᴇssғᴜʟʟʏ sᴇɴᴛ ᴛʜᴇ ʟɪɴᴋ ᴛᴏ ᴛʜᴇ ʟᴏɢ ɢʀᴏᴜᴘ.</b>", parse_mode="HTML")
        
    except Exception as e:
        error_msg = str(e)
        if "Chat not found" in error_msg:
            await m.edit_text("<b>ʙᴏᴛ ɪs ɴᴏᴛ ɪɴ ᴛʜᴀᴛ ɢʀᴏᴜᴘ ᴏʀ ɪɴᴠᴀʟɪᴅ ɪᴅ.</b>", parse_mode="HTML")
        elif "Not enough rights" in error_msg:
            await m.edit_text("<b>ʙᴏᴛ ɪs ɴᴏᴛ ᴀɴ ᴀᴅᴍɪɴ ɪɴ ᴛʜᴀᴛ ɢʀᴏᴜᴘ.</b>", parse_mode="HTML")
        else:
            await m.edit_text(f"<b>ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ: {error_msg}</b>", parse_mode="HTML")


# Register handlers
application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER, track_group_membership))
application.add_handler(CommandHandler("grouplink", fetch_group_link))
LOGGER.info("✓ Chatlog module loaded with direct MessageHandler service detection and Link Fetcher")

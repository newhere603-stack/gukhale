import asyncio
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler
from shivu import application, top_global_groups_collection, user_collection

# --- CONFIGURATION ---
OWNER_ID = 7657218453

# --- UNICODE SMALL CAPS STYLE ---
class Style:
    HEADER = "📢 ʙʀᴏᴀᴅᴄᴀꜱᴛ ꜱʏꜱᴛᴇᴍ"
    STATUS = "📊 ʙʀᴏᴀᴅᴄᴀꜱᴛ ꜱᴛᴀᴛᴜꜱ"
    SENT = "✅ ꜱᴇɴᴛ :"
    FAILED = "❌ ꜰᴀɪʟᴇᴅ :"
    INVALID = "🗑️ ɪɴᴠᴀʟɪᴅ :"
    TOTAL = "👥 ᴛᴏᴛᴀʟ ᴛᴀʀɢᴇᴛꜱ :"
    TARGET = "🎯 ᴛᴀʀɢᴇᴛ :"
    LINE = "──────────────────"

async def deliver_msg(context, chat_id, reply_msg, inline_text, is_forward):
    """Core function to send, copy or forward messages"""
    try:
        if reply_msg:
            # Agar user ne reply kiya hai
            if is_forward:
                await context.bot.forward_message(
                    chat_id=chat_id,
                    from_chat_id=reply_msg.chat_id,
                    message_id=reply_msg.message_id
                )
            else:
                # copy_message use karne se Premium Emojis aur media bina Forward Tag ke send hote hain
                await context.bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=reply_msg.chat_id,
                    message_id=reply_msg.message_id
                )
        else:
            # Agar user ne command ke aage text likha hai
            await context.bot.send_message(chat_id=chat_id, text=inline_text)
            
        return {"status": "success", "chat_id": chat_id}
        
    except Exception as e:
        error_text = str(e).lower()

        if "retry after" in error_text or "flood" in error_text:
            await asyncio.sleep(5) # Rate limit hit hone par wait karega
            try:
                if reply_msg:
                    if is_forward:
                        await context.bot.forward_message(chat_id=chat_id, from_chat_id=reply_msg.chat_id, message_id=reply_msg.message_id)
                    else:
                        await context.bot.copy_message(chat_id=chat_id, from_chat_id=reply_msg.chat_id, message_id=reply_msg.message_id)
                else:
                    await context.bot.send_message(chat_id=chat_id, text=inline_text)
                return {"status": "success", "chat_id": chat_id}
            except:
                pass

        if any(x in error_text for x in ["chat not found", "bot was blocked", "user is deactivated", "forbidden", "chat_write_forbidden"]):
            return {"status": "invalid", "chat_id": chat_id}

        return {"status": "failed", "chat_id": chat_id}


async def broadcast_command(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("<b>❌ ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ.</b>", parse_mode='HTML')
        return

    message_text = update.message.text
    command_name = message_text.split()[0].lower()
    
    # Check if it's a forward broadcast
    is_forward = command_name == "/fbroadcast"
    
    send_to_users = "-user" in message_text
    send_to_chats = "-chat" in message_text

    if not send_to_users and not send_to_chats:
        await update.message.reply_text(
            "<b>❌ ᴘʟᴇᴀꜱᴇ ꜱᴘᴇᴄɪꜰʏ ᴛᴀʀɢᴇᴛ:</b> <code>-user</code>, <code>-chat</code>, ᴏʀ ʙᴏᴛʜ.", 
            parse_mode='HTML'
        )
        return

    # Extract inline message (if any)
    inline_text = message_text.replace(command_name, "").replace("-user", "").replace("-chat", "").strip()
    reply_msg = update.message.reply_to_message

    if not reply_msg and not inline_text:
        await update.message.reply_text("<b>❌ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇꜱꜱᴀɢᴇ ᴏʀ ᴛʏᴘᴇ ᴍᴇꜱꜱᴀɢᴇ ᴀꜰᴛᴇʀ ᴄᴏᴍᴍᴀɴᴅ.</b>", parse_mode='HTML')
        return

    # Fetch targets based on flags
    targets = set()
    if send_to_users:
        users = await user_collection.distinct("id")
        targets.update(users)
    if send_to_chats:
        chats = await top_global_groups_collection.distinct("group_id")
        targets.update(chats)
        
    targets = list(targets)

    start_msg = await update.message.reply_text(
        f"<b>{Style.HEADER}</b>\n{Style.LINE}\n🚀 ʙʀᴏᴀᴅᴄᴀꜱᴛɪɴɢ ᴛᴏ {len(targets)} ᴛᴀʀɢᴇᴛꜱ...",
        parse_mode='HTML'
    )

    # Process broadcasting
    tasks = [deliver_msg(context, chat_id, reply_msg, inline_text, is_forward) for chat_id in targets]
    results = await asyncio.gather(*tasks)

    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    invalid = sum(1 for r in results if r["status"] == "invalid")

    # Final Summary Status Message
    final_text = (
        f"<b>{Style.STATUS}</b>\n"
        f"{Style.LINE}\n"
        f"<b>{Style.SENT}</b> <code>{success}</code>\n"
        f"<b>{Style.FAILED}</b> <code>{failed}</code>\n"
        f"<b>{Style.INVALID}</b> <code>{invalid}</code>\n"
        f"{Style.LINE}\n"
        f"<b>{Style.TOTAL}</b> <code>{len(targets)}</code>\n"
        f"✨ ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ!"
    )

    await start_msg.edit_text(final_text, parse_mode='HTML')


async def specific_send(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("<b>❌ ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ.</b>", parse_mode='HTML')
        return

    parts = update.message.text.split()
    if len(parts) < 2:
        await update.message.reply_text("<b>❌ ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴀɴ ɪᴅ.</b>", parse_mode='HTML')
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await update.message.reply_text("<b>❌ ɪɴᴠᴀʟɪᴅ ɪᴅ ꜰᴏʀᴍᴀᴛ.</b>", parse_mode='HTML')
        return

    # Extract inline text everything after the ID
    inline_text = update.message.text.split(parts[1], 1)[1].strip()
    reply_msg = update.message.reply_to_message

    if not reply_msg and not inline_text:
        await update.message.reply_text("<b>❌ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇꜱꜱᴀɢᴇ ᴏʀ ᴛʏᴘᴇ ᴍᴇꜱꜱᴀɢᴇ ᴀꜰᴛᴇʀ ɪᴅ.</b>", parse_mode='HTML')
        return

    result = await deliver_msg(context, target_id, reply_msg, inline_text, is_forward=False)

    if result["status"] == "success":
        await update.message.reply_text(
            f"<b>{Style.HEADER}</b>\n{Style.LINE}\n<b>{Style.SENT}</b> ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ!\n<b>{Style.TARGET}</b> <code>{target_id}</code>", 
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            f"<b>{Style.FAILED}</b> ᴄᴏᴜʟᴅ ɴᴏᴛ ꜱᴇɴᴅ ᴛᴏ <code>{target_id}</code>. (ɪɴᴠᴀʟɪᴅ ᴏʀ ʙʟᴏᴄᴋᴇᴅ)", 
            parse_mode='HTML'
        )


# --- REGISTRATIONS ---
application.add_handler(CommandHandler(["broadcast", "fbroadcast"], broadcast_command, block=False))
application.add_handler(CommandHandler(["send", "csend"], specific_send, block=False))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from shivu import application, user_collection

LOG_GROUP_ID = -1003893927065

# Indian Standard Time (IST -> UTC +5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def create_log_message(title: str, data: Dict[str, Any]) -> str:
    """Beautiful bold and small-caps log designer."""
    timestamp = datetime.now(IST).strftime("%I:%M %p • %d/%m/%y")
    base = f"<b>{title}</b>\n\n"
    
    items = list(data.items())
    for i, (key, value) in enumerate(items):
        prefix = "<b>╰</b>" if i == len(items) - 1 else "<b>├</b>"
        base += f"{prefix} <b>{key} :</b> {value}\n"
        
    base += f"\n<b>⌚ ᴛɪᴍᴇ :</b> <b>{timestamp}</b>"
    return base


async def send_log(context: CallbackContext, text: str):
    try:
        await context.bot.send_message(
            chat_id=LOG_GROUP_ID,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Log Error: {e}")


# ==========================================
# 1. COINS PAYMENT LOGIC (/pay)
# ==========================================

async def pay_cmd(update: Update, context: CallbackContext):
    sender = update.effective_user
    if not update.message or not update.message.reply_to_message:
        return await update.message.reply_text("<b>ʀᴇᴘʟʏ ᴛᴏ ᴛʜᴇ ᴜꜱᴇʀ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴘᴀʏ.</b>", parse_mode="HTML")
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("<b>ᴜꜱᴀɢᴇ: /pay <ᴀᴍᴏᴜɴᴛ> (ᴀꜱ ʀᴇᴘʟʏ)</b>", parse_mode="HTML")

    amount = int(context.args[0])
    receiver = update.message.reply_to_message.from_user
    if amount <= 0 or receiver.id == sender.id or receiver.is_bot:
        return await update.message.reply_text("<b>ɪɴᴠᴀʟɪᴅ ᴛʀᴀɴꜱᴀᴄᴛɪᴏɴ.</b>", parse_mode="HTML")

    s = await user_collection.find_one({'id': sender.id})
    if not s or int(s.get('balance', 0)) < amount:
        return await update.message.reply_text("<b>ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ᴄᴏɪɴꜱ ʙᴀʟᴀɴᴄᴇ.</b>", parse_mode="HTML")

    # Shortened callback data to fit within Telegram's 64-byte limit
    kb = [[
        InlineKeyboardButton("ᴄᴏɴꜰɪʀᴍ", callback_data=f"py_y_{sender.id}_{receiver.id}_{amount}"),
        InlineKeyboardButton("ᴄᴀɴᴄᴇʟ", callback_data=f"py_n_{sender.id}")
    ]]
    await update.message.reply_text(
        f"<b>ᴀʀᴇ ʏᴏᴜ ꜱᴜʀᴇ ᴛᴏ ꜱᴇɴᴅ <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {amount} ᴄᴏɪɴꜱ ᴛᴏ</b> {receiver.mention_html()}<b>?</b>",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )


async def pay_coins_callback(update: Update, context: CallbackContext):
    q = update.callback_query
    data_parts = q.data.split("_")
    action = data_parts[1]
    sender_id = int(data_parts[2])

    if q.from_user.id != sender_id:
        return await q.answer("ɴᴏᴛ ʏᴏᴜʀ ᴛʀᴀɴꜱᴀᴄᴛɪᴏɴ.", show_alert=True)

    if action == "n":
        await q.edit_message_text("<b>ᴘᴀʏᴍᴇɴᴛ ᴄᴀɴᴄᴇʟʟᴇᴅ.</b>", parse_mode="HTML")
        return await q.answer()

    receiver_id = int(data_parts[3])
    amount = int(data_parts[4])

    res = await user_collection.find_one_and_update(
        {'id': sender_id, 'balance': {'$gte': amount}},
        {'$inc': {'balance': -amount}}
    )
    if not res:
        await q.edit_message_text("<b>ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ᴄᴏɪɴꜱ ʙᴀʟᴀɴᴄᴇ.</b>", parse_mode="HTML")
        return await q.answer()

    await user_collection.update_one({'id': receiver_id}, {'$inc': {'balance': amount}}, upsert=True)

    try:
        sender_user = await context.bot.get_chat(sender_id)
        sender_name = sender_user.first_name
        receiver_user = await context.bot.get_chat(receiver_id)
        receiver_mention = receiver_user.mention_html()
        receiver_name = receiver_user.first_name
    except Exception:
        sender_name = "User"
        receiver_mention = f"<code>{receiver_id}</code>"
        receiver_name = "User"

    await q.edit_message_text(
        f"<tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji> <b>ᴘᴀʏᴍᴇɴᴛ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ!</b>\n\n<b>ʏᴏᴜ ꜱᴇɴᴛ <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {amount} ᴄᴏɪɴꜱ ᴛᴏ</b> {receiver_mention}<b>.</b>",
        parse_mode="HTML"
    )
    await q.answer()

    # Log the successful coin transfer
    log_data = {
        "sᴇɴᴅᴇʀ": f"<b><a href='tg://user?id={sender_id}'>{sender_name}</a></b>",
        "sᴇɴᴅᴇʀ ɪᴅ": f"<code>{sender_id}</code>",
        "ʀᴇᴄᴇɪᴠᴇʀ": f"<b><a href='tg://user?id={receiver_id}'>{receiver_name}</a></b>",
        "ʀᴇᴄᴇɪᴠᴇʀ ɪᴅ": f"<code>{receiver_id}</code>",
        "ᴀᴍᴏᴜɴᴛ": f"<b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {amount} ᴄᴏɪɴꜱ</b>"
    }
    await send_log(context, create_log_message("˹ ᴄᴏɪɴs ᴛʀᴀɴsғᴇʀʀᴇᴅ ˼ 💸", log_data))


# ==========================================
# 2. TOKENS PAYMENT LOGIC (/tpay)
# ==========================================

async def tpay_cmd(update: Update, context: CallbackContext):
    sender = update.effective_user
    if not update.message or not update.message.reply_to_message:
        return await update.message.reply_text("<b>ʀᴇᴘʟʏ ᴛᴏ ᴛʜᴇ ᴜꜱᴇʀ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴘᴀʏ.</b>", parse_mode="HTML")
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("<b>ᴜꜱᴀɢᴇ: /tpay <ᴀᴍᴏᴜɴᴛ> (ᴀꜱ ʀᴇᴘʟʏ)</b>", parse_mode="HTML")

    amount = int(context.args[0])
    receiver = update.message.reply_to_message.from_user
    if amount <= 0 or receiver.id == sender.id or receiver.is_bot:
        return await update.message.reply_text("<b>ɪɴᴠᴀʟɪᴅ ᴛʀᴀɴꜱᴀᴄᴛɪᴏɴ.</b>", parse_mode="HTML")

    s = await user_collection.find_one({'id': sender.id})
    if not s or int(s.get('tokens', 0)) < amount:
        return await update.message.reply_text("<b>ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ᴛᴏᴋᴇɴꜱ ʙᴀʟᴀɴᴄᴇ.</b>", parse_mode="HTML")

    # Shortened callback data to fit within Telegram's 64-byte limit
    kb = [[
        InlineKeyboardButton("ᴄᴏɴꜰɪʀᴍ", callback_data=f"pt_y_{sender.id}_{receiver.id}_{amount}"),
        InlineKeyboardButton("ᴄᴀɴᴄᴇʟ", callback_data=f"pt_n_{sender.id}")
    ]]
    await update.message.reply_text(
        f"<b>ᴀʀᴇ ʏᴏᴜ ꜱᴜʀᴇ ᴛᴏ ꜱᴇɴᴅ <tg-emoji emoji-id=\"6332379101231323246\">💠</tg-emoji> {amount} ᴛᴏᴋᴇɴꜱ ᴛᴏ</b> {receiver.mention_html()}<b>?</b>",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )


async def pay_tokens_callback(update: Update, context: CallbackContext):
    q = update.callback_query
    data_parts = q.data.split("_")
    action = data_parts[1]
    sender_id = int(data_parts[2])

    if q.from_user.id != sender_id:
        return await q.answer("ɴᴏᴛ ʏᴏᴜʀ ᴛʀᴀɴꜱᴀᴄᴛɪᴏɴ.", show_alert=True)

    if action == "n":
        await q.edit_message_text("<b>ᴘᴀʏᴍᴇɴᴛ ᴄᴀɴᴄᴇʟʟᴇᴅ.</b>", parse_mode="HTML")
        return await q.answer()

    receiver_id = int(data_parts[3])
    amount = int(data_parts[4])

    res = await user_collection.find_one_and_update(
        {'id': sender_id, 'tokens': {'$gte': amount}},
        {'$inc': {'tokens': -amount}}
    )
    if not res:
        await q.edit_message_text("<b>ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ᴛᴏᴋᴇɴꜱ ʙᴀʟᴀɴᴄᴇ.</b>", parse_mode="HTML")
        return await q.answer()

    await user_collection.update_one({'id': receiver_id}, {'$inc': {'tokens': amount}}, upsert=True)

    try:
        sender_user = await context.bot.get_chat(sender_id)
        sender_name = sender_user.first_name
        receiver_user = await context.bot.get_chat(receiver_id)
        receiver_mention = receiver_user.mention_html()
        receiver_name = receiver_user.first_name
    except Exception:
        sender_name = "User"
        receiver_mention = f"<code>{receiver_id}</code>"
        receiver_name = "User"

    await q.edit_message_text(
        f"<tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji> <b>ᴘᴀʏᴍᴇɴᴛ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ!</b>\n\n<b>ʏᴏᴜ ꜱᴇɴᴛ <tg-emoji emoji-id=\"6332379101231323246\">💠</tg-emoji> {amount} ᴛᴏᴋᴇɴꜱ ᴛᴏ</b> {receiver_mention}<b>.</b>",
        parse_mode="HTML"
    )
    await q.answer()

    # Log the successful token transfer
    log_data = {
        "sᴇɴᴅᴇʀ": f"<b><a href='tg://user?id={sender_id}'>{sender_name}</a></b>",
        "sᴇɴᴅᴇʀ ɪᴅ": f"<code>{sender_id}</code>",
        "ʀᴇᴄᴇɪᴠᴇʀ": f"<b><a href='tg://user?id={receiver_id}'>{receiver_name}</a></b>",
        "ʀᴇᴄᴇɪᴠᴇʀ ɪᴅ": f"<code>{receiver_id}</code>",
        "ᴀᴍᴏᴜɴᴛ": f"<b><tg-emoji emoji-id=\"6332379101231323246\">💠</tg-emoji> {amount} ᴛᴏᴋᴇɴꜱ</b>"
    }
    await send_log(context, create_log_message("˹ ᴛᴏᴋᴇɴs ᴛʀᴀɴsғᴇʀʀᴇᴅ ˼ 💠", log_data))


# Handlers Registration
application.add_handler(CommandHandler("pay", pay_cmd, block=False))
application.add_handler(CommandHandler("tpay", tpay_cmd, block=False))
application.add_handler(CallbackQueryHandler(pay_coins_callback, pattern="^py_", block=False))
application.add_handler(CallbackQueryHandler(pay_tokens_callback, pattern="^pt_", block=False))

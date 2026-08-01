from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from shivu import application, user_collection


# ==========================================
# 1. COINS PAYMENT LOGIC (/pay)
# ==========================================

async def pay_cmd(update: Update, context: CallbackContext):
    sender = update.effective_user
    if not update.message.reply_to_message:
        return await update.message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴛʜᴇ ᴜꜱᴇʀ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴘᴀʏ.")
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("ᴜꜱᴀɢᴇ: /pay <ᴀᴍᴏᴜɴᴛ> (ᴀꜱ ʀᴇᴘʟʏ)")

    amount = int(context.args[0])
    receiver = update.message.reply_to_message.from_user
    if amount <= 0 or receiver.id == sender.id or receiver.is_bot:
        return await update.message.reply_text("ɪɴᴠᴀʟɪᴅ ᴛʀᴀɴꜱᴀᴄᴛɪᴏɴ.")

    s = await user_collection.find_one({'id': sender.id})
    if not s or int(s.get('balance', 0)) < amount:
        return await update.message.reply_text("ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ᴄᴏɪɴꜱ ʙᴀʟᴀɴᴄᴇ.")

    kb = [[
        InlineKeyboardButton("ᴄᴏɴꜰɪʀᴍ", callback_data=f"paycoins_yes_{sender.id}_{receiver.id}_{amount}"),
        InlineKeyboardButton("ᴄᴀɴᴄᴇʟ", callback_data=f"paycoins_no_{sender.id}")
    ]]
    await update.message.reply_text(
        f"ᴀʀᴇ ʏᴏᴜ ꜱᴜʀᴇ ᴛᴏ ꜱᴇɴᴅ 💸 {amount} ᴄᴏɪɴꜱ ᴛᴏ {receiver.mention_html()}?",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )


async def pay_coins_callback(update: Update, context: CallbackContext):
    q = update.callback_query
    _, action, sender_id, *rest = q.data.split("_")
    sender_id = int(sender_id)

    if q.from_user.id != sender_id:
        return await q.answer("ɴᴏᴛ ʏᴏᴜʀ ᴛʀᴀɴꜱᴀᴄᴛɪᴏɴ.", show_alert=True)

    if action == "no":
        await q.edit_message_text("ᴘᴀʏᴍᴇɴᴛ ᴄᴀɴᴄᴇʟʟᴇᴅ.")
        return await q.answer()

    receiver_id, amount = int(rest[0]), int(rest[1])

    res = await user_collection.find_one_and_update(
        {'id': sender_id, 'balance': {'$gte': amount}},
        {'$inc': {'balance': -amount}}
    )
    if not res:
        await q.edit_message_text("ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ᴄᴏɪɴꜱ ʙᴀʟᴀɴᴄᴇ.")
        return await q.answer()

    await user_collection.update_one({'id': receiver_id}, {'$inc': {'balance': amount}}, upsert=True)

    # Fetch Receiver details to show name
    try:
        receiver_user = await context.bot.get_chat(receiver_id)
        receiver_mention = receiver_user.mention_html()
    except Exception:
        receiver_mention = f"<code>{receiver_id}</code>"

    await q.edit_message_text(
        f"<b>ᴘᴀʏᴍᴇɴᴛ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ!</b>\n\nʏᴏᴜ ꜱᴇɴᴛ 💸 <b>{amount}</b> ᴄᴏɪɴꜱ ᴛᴏ {receiver_mention}.",
        parse_mode="HTML"
    )
    await q.answer()


# ==========================================
# 2. TOKENS PAYMENT LOGIC (/tpay)
# ==========================================

async def tpay_cmd(update: Update, context: CallbackContext):
    sender = update.effective_user
    if not update.message.reply_to_message:
        return await update.message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴛʜᴇ ᴜꜱᴇʀ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴘᴀʏ.")
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("ᴜꜱᴀɢᴇ: /tpay <ᴀᴍᴏᴜɴᴛ> (ᴀꜱ ʀᴇᴘʟʏ)")

    amount = int(context.args[0])
    receiver = update.message.reply_to_message.from_user
    if amount <= 0 or receiver.id == sender.id or receiver.is_bot:
        return await update.message.reply_text("ɪɴᴠᴀʟɪᴅ ᴛʀᴀɴꜱᴀᴄᴛɪᴏɴ.")

    s = await user_collection.find_one({'id': sender.id})
    if not s or int(s.get('tokens', 0)) < amount:
        return await update.message.reply_text("ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ᴛᴏᴋᴇɴꜱ ʙᴀʟᴀɴᴄᴇ.")

    kb = [[
        InlineKeyboardButton("ᴄᴏɴꜰɪʀᴍ", callback_data=f"paytokens_yes_{sender.id}_{receiver.id}_{amount}"),
        InlineKeyboardButton("ᴄᴀɴᴄᴇʟ", callback_data=f"paytokens_no_{sender.id}")
    ]]
    await update.message.reply_text(
        f"ᴀʀᴇ ʏᴏᴜ ꜱᴜʀᴇ ᴛᴏ ꜱᴇɴᴅ 💠 {amount} ᴛᴏᴋᴇɴꜱ ᴛᴏ {receiver.mention_html()}?",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )


async def pay_tokens_callback(update: Update, context: CallbackContext):
    q = update.callback_query
    _, action, sender_id, *rest = q.data.split("_")
    sender_id = int(sender_id)

    if q.from_user.id != sender_id:
        return await q.answer("ɴᴏᴛ ʏᴏᴜʀ ᴛʀᴀɴꜱᴀᴄᴛɪᴏɴ.", show_alert=True)

    if action == "no":
        await q.edit_message_text("ᴘᴀʏᴍᴇɴᴛ ᴄᴀɴᴄᴇʟʟᴇᴅ.")
        return await q.answer()

    receiver_id, amount = int(rest[0]), int(rest[1])

    res = await user_collection.find_one_and_update(
        {'id': sender_id, 'tokens': {'$gte': amount}},
        {'$inc': {'tokens': -amount}}
    )
    if not res:
        await q.edit_message_text("ɪɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ ᴛᴏᴋᴇɴꜱ ʙᴀʟᴀɴᴄᴇ.")
        return await q.answer()

    await user_collection.update_one({'id': receiver_id}, {'$inc': {'tokens': amount}}, upsert=True)

    # Fetch Receiver details to show name
    try:
        receiver_user = await context.bot.get_chat(receiver_id)
        receiver_mention = receiver_user.mention_html()
    except Exception:
        receiver_mention = f"<code>{receiver_id}</code>"

    await q.edit_message_text(
        f"<b>ᴘᴀʏᴍᴇɴᴛ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ!</b>\n\nʏᴏᴜ ꜱᴇɴᴛ 💠 <b>{amount}</b> ᴛᴏᴋᴇɴꜱ ᴛᴏ {receiver_mention}.",
        parse_mode="HTML"
    )
    await q.answer()


# Handlers Registration
application.add_handler(CommandHandler("pay", pay_cmd, block=False))
application.add_handler(CommandHandler("tpay", tpay_cmd, block=False))
application.add_handler(CallbackQueryHandler(pay_coins_callback, pattern="^paycoins_", block=False))
application.add_handler(CallbackQueryHandler(pay_tokens_callback, pattern="^paytokens_", block=False))

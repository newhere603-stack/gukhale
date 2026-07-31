from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from shivu import application, user_collection


async def pay_cmd(update: Update, context: CallbackContext):
    sender = update.effective_user
    if not update.message.reply_to_message:
        return await update.message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴛʜᴇ ᴜsᴇʀ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴘᴀʏ.")
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("ᴜsᴀɢᴇ: /pay <ᴀᴍᴏᴜɴᴛ> (ᴀs ʀᴇᴘʟʏ)")

    amount = int(context.args[0])
    receiver = update.message.reply_to_message.from_user
    if amount <= 0 or receiver.id == sender.id:
        return await update.message.reply_text("ɪɴᴠᴀʟɪᴅ ᴛʀᴀɴsᴀᴄᴛɪᴏɴ.")

    s = await user_collection.find_one({'id': sender.id})
    if not s or int(s.get('balance', 0)) < amount:
        return await update.message.reply_text("ɪɴsᴜғғɪᴄɪᴇɴᴛ ʙᴀʟᴀɴᴄᴇ.")

    kb = [[
        InlineKeyboardButton("ᴄᴏɴғɪʀᴍ", callback_data=f"pay_yes_{sender.id}_{receiver.id}_{amount}"),
        InlineKeyboardButton("ᴄᴀɴᴄᴇʟ", callback_data=f"pay_no_{sender.id}")
    ]]
    await update.message.reply_text(
        f"ᴀʀᴇ ʏᴏᴜ sᴜʀᴇ sᴇɴᴅ 💸 {amount} ᴛᴏ {receiver.mention_html()}?",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
    )


async def pay_callback(update: Update, context: CallbackContext):
    q = update.callback_query
    _, action, sender_id, *rest = q.data.split("_")
    sender_id = int(sender_id)

    if q.from_user.id != sender_id:
        return await q.answer("ɴᴏᴛ ʏᴏᴜʀ ᴛʀᴀɴsᴀᴄᴛɪᴏɴ.", show_alert=True)

    if action == "no":
        await q.edit_message_text("ᴘᴀʏᴍᴇɴᴛ ᴄᴀɴᴄᴇʟʟᴇᴅ.")
        return await q.answer()

    receiver_id, amount = int(rest[0]), int(rest[1])

    res = await user_collection.find_one_and_update(
        {'id': sender_id, 'balance': {'$gte': amount}},
        {'$inc': {'balance': -amount}}
    )
    if not res:
        await q.edit_message_text("ɪɴsᴜғғɪᴄɪᴇɴᴛ ʙᴀʟᴀɴᴄᴇ.")
        return await q.answer()

    await user_collection.update_one({'id': receiver_id}, {'$inc': {'balance': amount}}, upsert=True)
    await q.edit_message_text(f"ᴘᴀʏᴍᴇɴᴛ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ! ʏᴏᴜ ꜱᴇɴᴛ 💸 {amount} ᴄᴏɪɴ ᴛᴏ {receiver.name}.")
    await q.answer()


application.add_handler(CommandHandler("pay", pay_cmd, block=False))
application.add_handler(CallbackQueryHandler(pay_callback, pattern="^pay_", block=False))

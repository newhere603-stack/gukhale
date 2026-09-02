import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from shivu import application, user_collection

# --- CONFIGURATION ---
OWNER_ID = 7657218453
LOG_GROUP_ID = -1003893927065 

# --- UNICODE SMALL CAPS STYLE ---
class Style:
    HEADER = "🔄 ᴛʀᴀɴꜱꜰᴇʀ ʀᴇǫᴜᴇꜱᴛ"
    FROM = "👤 ꜰʀᴏᴍ :"
    TO = "👤 ᴛᴏ :"
    TOTAL = "🍥 ᴛᴏᴛᴀʟ :"
    BY = "👤 ʙʏ ᴏᴡɴᴇʀ :"
    STATUS = "✨ ꜱᴛᴀᴛᴜꜱ :"
    LINE = "──────────────────"

async def transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return 

    if len(context.args) != 2:
        await update.message.reply_text(f'<b>❌ ᴜꜱᴀɢᴇ:</b> <code>/transfer [sender_id] [receiver_id]</code>', parse_mode='HTML')
        return

    try:
        s_id = int(context.args[0])
        r_id = int(context.args[1])

        sender = await user_collection.find_one({'id': s_id})
        receiver = await user_collection.find_one({'id': r_id})

        if not sender or not receiver:
            await update.message.reply_text('<b>❌ ᴜꜱᴇʀ ɴᴏᴛ ꜰᴏᴜɴᴅ ɪɴ ᴅᴀᴛᴀʙᴀꜱᴇ.</b>', parse_mode='HTML')
            return

        s_waifus = sender.get('characters', [])
        
        keyboard = [
            [InlineKeyboardButton("✅ ᴄᴏɴꜰɪʀᴍ", callback_data=f"TR|{s_id}|{r_id}")],
            [InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="TR|CANCEL")]
        ]

        msg = (
            f"<b>{Style.HEADER}</b>\n"
            f"{Style.LINE}\n"
            f"<b>{Style.FROM}</b> <code>{s_id}</code>\n"
            f"<b>{Style.TO}</b> <code>{r_id}</code>\n"
            f"<b>{Style.TOTAL}</b> <code>{len(s_waifus)}</code> ᴄʜᴀʀᴀᴄᴛᴇʀꜱ\n"
            f"{Style.LINE}\n"
            f"<i>💡 ᴄᴏɴꜰɪʀᴍ ᴛᴏ ᴍᴏᴠᴇ ᴀʟʟ ᴅᴀᴛᴀ.</i>"
        )
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    except ValueError:
        await update.message.reply_text('<b>❌ ᴇʀʀᴏʀ: ɪᴅꜱ ᴍᴜꜱᴛ ʙᴇ ɪɴ ɴᴜᴍʙᴇʀꜱ.</b>', parse_mode='HTML')

async def transfer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split('|')
    await query.answer()

    if data[1] == "CANCEL":
        await query.edit_message_text(f"<b>❌ ᴛʀᴀɴꜱꜰᴇʀ ᴄᴀɴᴄᴇʟʟᴇᴅ ʙʏ ᴏᴡɴᴇʀ.</b>", parse_mode='HTML')
        return

    s_id, r_id = int(data[1]), int(data[2])

    try:
        sender = await user_collection.find_one({'id': s_id})
        s_waifus = sender.get('characters', [])

        if not s_waifus:
            await query.edit_message_text(f"<b>⚠️ ꜱᴇɴᴅᴇʀ ʜᴀꜱ 𝟶 ᴄʜᴀʀᴀᴄᴛᴇʀꜱ.</b>", parse_mode='HTML')
            return

        # Atomic Database Update
        await user_collection.update_one({'id': r_id}, {'$push': {'characters': {'$each': s_waifus}}})
        await user_collection.update_one({'id': s_id}, {'$set': {'characters': []}})

        await query.edit_message_text(f"<b>✅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴍᴏᴠᴇᴅ {len(s_waifus)} ᴄʜᴀʀᴀᴄᴛᴇʀꜱ!</b>", parse_mode='HTML')

        # --- LOGGING ---
        user_name = html.escape(update.effective_user.first_name)
        log_text = (
            f"📢 <b>#ᴛʀᴀɴꜱꜰᴇʀ_ʟᴏɢ</b>\n"
            f"{Style.LINE}\n"
            f"<b>{Style.BY}</b> {user_name} (<code>{OWNER_ID}</code>)\n"
            f"<b>{Style.FROM}</b> <code>{s_id}</code>\n"
            f"<b>{Style.TO}</b> <code>{r_id}</code>\n"
            f"<b>{Style.TOTAL}</b> <code>{len(s_waifus)}</code>\n"
            f"<b>{Style.STATUS}</b> ᴄᴏᴍᴘʟᴇᴛᴇᴅ ✅"
        )
        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_text, parse_mode='HTML')

    except Exception as e:
        error_msg = html.escape(str(e))
        await query.edit_message_text(f"<b>❌ ᴅᴀᴛᴀʙᴀꜱᴇ ᴇʀʀᴏʀ:</b> <code>{error_msg}</code>", parse_mode='HTML')

# Handlers Registration
application.add_handler(CommandHandler("transfer", transfer))
application.add_handler(CallbackQueryHandler(transfer_callback, pattern="^TR\|"))

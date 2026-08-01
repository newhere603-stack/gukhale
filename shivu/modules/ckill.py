from html import escape
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
from shivu import application, user_collection

OWNER_ID = 7657218453

async def get_target_user(update: Update, context: CallbackContext):
    if reply := update.message.reply_to_message:
        return reply.from_user.id
    if context.args:
        try:
            return int(context.args[0])
        except ValueError:
            return None
    return None

async def tkill(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("<b>⛔ ᴏᴡɴᴇʀ ᴏɴʟＹ ᴄᴏᴍᴍᴀɴᴅ.</b>", parse_mode='HTML')
        return
    
    target_id = await get_target_user(update, context)
    if not target_id:
        await update.message.reply_text(
            "<b>⚠️ ɪɴᴠᴀʟɪᴅ ᴜꜱᴀɢᴇ!</b>\n\n"
            "<b>ᴜꜱᴀɢᴇ:</b> <code>/tkill [user_id]</code> (ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴜꜱᴇʀ)",
            parse_mode='HTML'
        )
        return
    
    try:
        user = await user_collection.find_one({'id': target_id})
        
        if not user:
            await update.message.reply_text(
                f"❌ <b>ᴜꜱᴇʀ ɴᴏᴛ ꜰᴏᴜɴᴅ</b>\nID: <code>{target_id}</code>",
                parse_mode='HTML'
            )
            return
        
        first_name = user.get('first_name', 'Unknown')
        current_tokens = user.get('tokens', 0)
        
        result = await user_collection.update_one(
            {'id': target_id},
            {'$set': {'tokens': 0}}
        )
        
        if result.modified_count > 0 or current_tokens > 0:
            await update.message.reply_text(
                f"<b>✅ ᴛᴏᴋᴇɴꜱ ʀᴇꜱᴇᴛ</b>\n\n"
                f"<b>ᴜꜱᴇʀ:</b> <a href='tg://user?id={target_id}'>{escape(first_name)}</a>\n"
                f"<b>ɪᴅ:</b> <code>{target_id}</code>\n\n"
                f"<b>ᴘʀᴇᴠɪᴏᴜꜱ ᴛᴏᴋᴇɴꜱ:</b> <code>{current_tokens:,}</code>\n"
                f"<b>ɴᴇᴡ ʙᴀʟᴀɴᴄᴇ:</b> <code>0</code>",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ <b>ᴜꜱᴇʀ'ꜱ ᴛᴏᴋᴇɴꜱ ᴀʟʀᴇᴀᴅʏ ᴢᴇʀᴏ ᴏʀ ꜰᴀɪʟᴇᴅ.</b>", parse_mode='HTML')
    
    except Exception as e:
        await update.message.reply_text(
            f"<b>ᴇʀʀᴏʀ:</b> <code>{str(e)}</code>",
            parse_mode='HTML'
        )

application.add_handler(CommandHandler('tkill', tkill, block=False))

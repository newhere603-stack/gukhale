from html import escape
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
from shivu import application, user_collection

OWNER_ID = 7657218453

async def get_target_and_amount(update: Update, context: CallbackContext):
    target_id = None
    amount = None
    
    if reply := update.message.reply_to_message:
        target_id = reply.from_user.id
        if context.args and context.args[0].isdigit():
            amount = int(context.args[0])
    else:
        if len(context.args) >= 1:
            try:
                target_id = int(context.args[0])
            except ValueError:
                pass
        if len(context.args) >= 2:
            try:
                amount = int(context.args[1])
            except ValueError:
                pass
                
    return target_id, amount

# --- COINS DEDUCT COMMAND (/ckill) ---
async def ckill(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("<b>⛔ ᴏᴡɴᴇʀ ᴏɴʟʏ ᴄᴏᴍᴍᴀɴᴅ.</b>", parse_mode='HTML')
        return
    
    target_id, amount = await get_target_and_amount(update, context)
    if not target_id or amount is None:
        await update.message.reply_text(
            "<b>⚠️ ɪɴᴠᴀʟɪᴅ ᴜꜱᴀɢᴇ!</b>\n\n"
            "<b>ᴜꜱᴀɢᴇ:</b> <code>/ckill [user_id] [amount]</code> (ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴜꜱᴇʀ ᴡɪᴛʜ ᴀᴍᴏᴜɴᴛ)",
            parse_mode='HTML'
        )
        return
    
    try:
        user = await user_collection.find_one({'id': target_id})
        if not user:
            await update.message.reply_text(f"❌ <b>ᴜꜱᴇʀ ɴᴏᴛ ꜰᴏᴜɴᴅ</b>\nID: <code>{target_id}</code>", parse_mode='HTML')
            return
        
        first_name = user.get('first_name', 'Unknown')
        current_balance = user.get('balance', 0)
        
        # Jitna amount doge, utna hi minus hoga (0 se kam nahi jayega)
        new_balance = max(0, current_balance - amount)
        
        await user_collection.update_one(
            {'id': target_id},
            {'$set': {'balance': new_balance}}
        )
        
        await update.message.reply_text(
            f"<b>✅ ᴄᴏɪɴꜱ ᴅᴇᴅᴜᴄᴛᴇᴅ</b>\n\n"
            f"<b>ᴜꜱᴇʀ:</b> <a href='tg://user?id={target_id}'>{escape(first_name)}</a>\n"
            f"<b>ɪᴅ:</b> <code>{target_id}</code>\n\n"
            f"<b>ᴅᴇᴅᴜᴄᴛᴇᴅ:</b> <code>{amount:,}</code>\n"
            f"<b>ᴘʀᴇᴠɪᴏᴜꜱ:</b> <code>{current_balance:,}</code>\n"
            f"<b>ɴᴇᴡ ʙᴀʟᴀɴᴄᴇ:</b> <code>{new_balance:,}</code>",
            parse_mode='HTML'
        )
    except Exception as e:
        await update.message.reply_text(f"<b>ᴇʀʀᴏʀ:</b> <code>{str(e)}</code>", parse_mode='HTML')


# --- TOKENS DEDUCT COMMAND (/tkill) ---
async def tkill(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("<b>⛔ ᴏᴡɴᴇʀ ᴏɴʟʏ ᴄᴏᴍᴍᴀɴᴅ.</b>", parse_mode='HTML')
        return
    
    target_id, amount = await get_target_and_amount(update, context)
    if not target_id or amount is None:
        await update.message.reply_text(
            "<b>⚠️ ɪɴᴠᴀʟɪᴅ ᴜꜱᴀɢᴇ!</b>\n\n"
            "<b>ᴜꜱᴀɢᴇ:</b> <code>/tkill [user_id] [amount]</code> (ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴜꜱᴇʀ ᴡɪᴛʜ ᴀᴍᴏᴜɴᴛ)",
            parse_mode='HTML'
        )
        return
    
    try:
        user = await user_collection.find_one({'id': target_id})
        if not user:
            await update.message.reply_text(f"❌ <b>ᴜꜱᴇʀ ɴᴏᴛ ꜰᴏᴜɴᴅ</b>\nID: <code>{target_id}</code>", parse_mode='HTML')
            return
        
        first_name = user.get('first_name', 'Unknown')
        current_tokens = user.get('tokens', 0)
        
        # Jitna amount doge, utna hi minus hoga (0 se kam nahi jayega)
        new_tokens = max(0, current_tokens - amount)
        
        await user_collection.update_one(
            {'id': target_id},
            {'$set': {'tokens': new_tokens}}
        )
        
        await update.message.reply_text(
            f"<b>✅ ᴛᴏᴋᴇɴꜱ ᴅᴇᴅᴜᴄᴛᴇᴅ</b>\n\n"
            f"<b>ᴜꜱᴇʀ:</b> <a href='tg://user?id={target_id}'>{escape(first_name)}</a>\n"
            f"<b>ɪᴅ:</b> <code>{target_id}</code>\n\n"
            f"<b>ᴅᴇᴅᴜᴄᴛᴇᴅ:</b> <code>{amount:,}</code>\n"
            f"<b>ᴘʀᴇᴠɪᴏᴜꜱ ᴛᴏᴋᴇɴꜱ:</b> <code>{current_tokens:,}</code>\n"
            f"<b>ɴᴇᴡ ʙᴀʟᴀɴᴄᴇ:</b> <code>{new_tokens:,}</code>",
            parse_mode='HTML'
        )
    except Exception as e:
        await update.message.reply_text(f"<b>ᴇʀʀᴏʀ:</b> <code>{str(e)}</code>", parse_mode='HTML')

application.add_handler(CommandHandler('ckill', ckill, block=False))
application.add_handler(CommandHandler('tkill', tkill, block=False))

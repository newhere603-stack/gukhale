import asyncio
from html import escape
from datetime import datetime
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
# Main collection bhi import ki gayi hai updated rarity dikhane ke liye
from shivu import application, user_collection, collection

# Configuration
OWNER_ID = 7657218453
LOG_GROUP_ID = -1003893927065  # Aapka Log Group

async def Ukill(update: Update, context: CallbackContext) -> None:
    # Owner Check - Normal user ke use karne par bina koi reply kiye ignore karega
    if update.effective_user.id != OWNER_ID:
        return
    
    target_id = None
    action_arg = None  # Ye check karega ki specific ID hai ya '-all'
    first_name = "Unknown"

    # Agar message par reply kiya gaya hai
    if reply := update.message.reply_to_message:
        target_id = reply.from_user.id
        first_name = reply.from_user.first_name
        
        if not context.args:
            await update.message.reply_text(
                "<b>⚠️ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀɴ ᴀᴄᴛɪᴏɴ!</b>\n"
                "<b>ᴜsᴀɢᴇ:</b> <code>/Ukill [ᴄʜᴀʀ_ɪᴅ]</code> ᴏʀ <code>/Ukill -all</code>", 
                parse_mode='HTML'
            )
            return
        action_arg = context.args[0]
        
    else:
        # Bina reply ke command dene par (User ID + Char ID / -all)
        if len(context.args) < 2:
            await update.message.reply_text(
                "<b>⚠️ ɪɴᴠᴀʟɪᴅ ᴜsᴀɢᴇ!</b>\n"
                "<b>ʀᴇᴘʟʏ:</b> <code>/Ukill [ᴄʜᴀʀ_ɪᴅ]</code> ᴏʀ <code>/Ukill -all</code>\n"
                "<b>ᴅɪʀᴇᴄᴛ:</b> <code>/Ukill [ᴜsᴇʀ_ɪᴅ] [ᴄʜᴀʀ_ɪᴅ]</code> ᴏʀ <code>/Ukill [ᴜsᴇʀ_ɪᴅ] -all</code>",
                parse_mode='HTML'
            )
            return
        
        try:
            target_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("<b>❌ ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ!</b>", parse_mode='HTML')
            return
        
        action_arg = context.args[1]

    try:
        # Database se user fetch karna
        user = await user_collection.find_one({'id': target_id})
        
        if not user:
            await update.message.reply_text(
                f"<b>❌ ᴜsᴇʀ ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ ᴅᴀᴛᴀʙᴀsᴇ!</b>\n<b>ɪᴅ:</b> <code>{target_id}</code>",
                parse_mode='HTML'
            )
            return
        
        first_name = user.get('first_name', first_name)
        characters = user.get('characters', [])
        
        # ----------------------------------------------------
        # ACTION 1: WIPE ALL CHARACTERS (-all)
        # ----------------------------------------------------
        if action_arg == '-all':
            char_count = len(characters)
            
            if char_count == 0:
                await update.message.reply_text(
                    f"<b>❌ ᴜsᴇʀ ʜᴀs ɴᴏ ᴄʜᴀʀᴀᴄᴛᴇʀs ᴛᴏ ᴡɪᴘᴇ!</b>\n"
                    f"<b>👤 ᴘʟᴀʏᴇʀ:</b> <a href='tg://user?id={target_id}'>{escape(first_name)}</a>",
                    parse_mode='HTML'
                )
                return
            
            result = await user_collection.update_one(
                {'id': target_id},
                {'$set': {'characters': []}}
            )
            
            if result.modified_count > 0:
                success_msg = (
                    f"<b>✅ ᴀʟʟ ᴄʜᴀʀᴀᴄᴛᴇʀs ᴡɪᴘᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"<b>👤 ᴘʟᴀʏᴇʀ:</b> <a href='tg://user?id={target_id}'>{escape(first_name)}</a>\n"
                    f"<b>🆔 ɪᴅ:</b> <code>{target_id}</code>\n"
                    f"<b>🗑️ ʀᴇᴍᴏᴠᴇᴅ:</b> <code>{char_count}</code> ᴄʜᴀʀᴀᴄᴛᴇʀs\n"
                    f"━━━━━━━━━━━━━━━━━━━━"
                )
                await update.message.reply_text(success_msg, parse_mode='HTML')

                # Log to group
                log_text = (
                    f"<b>🚨 U-ᴋɪʟʟ ʟᴏɢ (ᴍᴀss ᴡɪᴘᴇ)</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"<b>👨‍💻 ᴀᴅᴍɪɴ:</b> <a href='tg://user?id={OWNER_ID}'>Owner</a>\n"
                    f"<b>👤 ᴛᴀʀɢᴇᴛ:</b> <a href='tg://user?id={target_id}'>{escape(first_name)}</a>\n"
                    f"<b>🆔 ᴛ-ɪᴅ:</b> <code>{target_id}</code>\n"
                    f"<b>📊 ᴛᴏᴛᴀʟ ʟᴏss:</b> <code>{char_count}</code> ᴄʜᴀʀs\n"
                    f"<b>📅 ᴅᴀᴛᴇ:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━━"
                )
                try:
                    await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_text, parse_mode='HTML')
                except Exception as log_e:
                    print(f"Log Error: {log_e}")
            return

        # ----------------------------------------------------
        # ACTION 2: REMOVE SPECIFIC CHARACTER BY ID
        # ----------------------------------------------------
        target_char = next((c for c in characters if str(c.get('id')) == str(action_arg)), None)
        
        if not target_char:
            await update.message.reply_text(
                f"<b>❌ ᴄʜᴀʀᴀᴄᴛᴇʀ (ɪᴅ: {action_arg}) ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ ᴜsᴇʀ's ᴄᴏʟʟᴇᴄᴛɪᴏɴ!</b>",
                parse_mode='HTML'
            )
            return
        
        # Yahan main collection se data fetch kar rahe hain taaki original Rarity mil sake
        global_char = await collection.find_one({'id': str(action_arg)})
        
        if global_char:
            char_name = global_char.get('name', target_char.get('name', 'Unknown'))
            char_rarity = global_char.get('rarity', target_char.get('rarity', 'N/A'))
        else:
            char_name = target_char.get('name', 'Unknown')
            char_rarity = target_char.get('rarity', 'N/A')

        # Sirf ek instance remove karna (duplicate prevent)
        characters.remove(target_char)
        
        result = await user_collection.update_one(
            {'id': target_id},
            {'$set': {'characters': characters}}
        )
        
        if result.modified_count > 0:
            success_msg = (
                f"<b>✅ ᴄʜᴀʀᴀᴄᴛᴇʀ sᴜᴄᴄᴇssғᴜʟʟʏ ʀᴇᴍᴏᴠᴇᴅ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>👤 ᴘʟᴀʏᴇʀ:</b> <a href='tg://user?id={target_id}'>{escape(first_name)}</a>\n"
                f"<b>🆔 ɪᴅ:</b> <code>{target_id}</code>\n"
                f"<b>🗑️ ʀᴇᴍᴏᴠᴇᴅ:</b> <code>{char_name}</code> ({char_rarity})\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )
            await update.message.reply_text(success_msg, parse_mode='HTML')

            # Log to group
            log_text = (
                f"<b>🚨 U-ᴋɪʟʟ ʟᴏɢ (sɪɴɢʟᴇ ʀᴇᴍᴏᴠᴇ)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>👨‍💻 ᴀᴅᴍɪɴ:</b> <a href='tg://user?id={OWNER_ID}'>Owner</a>\n"
                f"<b>👤 ᴛᴀʀɢᴇᴛ:</b> <a href='tg://user?id={target_id}'>{escape(first_name)}</a>\n"
                f"<b>🆔 ᴛ-ɪᴅ:</b> <code>{target_id}</code>\n"
                f"<b>🗑️ ᴄʜᴀʀ ɪᴅ:</b> <code>{action_arg}</code>\n"
                f"<b>📝 ᴄʜᴀʀ ɴᴀᴍᴇ:</b> <code>{char_name} ({char_rarity})</code>\n"
                f"<b>📅 ᴅᴀᴛᴇ:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )
            try:
                await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_text, parse_mode='HTML')
            except Exception as log_e:
                print(f"Log Error: {log_e}")
        else:
            await update.message.reply_text("<b>❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴍᴏᴅɪғʏ ᴅᴀᴛᴀʙᴀsᴇ.</b>", parse_mode='HTML')
            
    except Exception as e:
        await update.message.reply_text(f"<b>⚠️ ᴇʀʀᴏʀ:</b> <code>{str(e)}</code>", parse_mode='HTML')

# Handler Register Karna
application.add_handler(CommandHandler('Ukill', Ukill, block=False))

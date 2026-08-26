import asyncio
from html import escape
from datetime import datetime
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
from shivu import application, user_collection, collection

# Configuration
OWNER_ID = 7657218453
LOG_GROUP_ID = -1003893927065  # Aapka Log Group

async def Ukill(update: Update, context: CallbackContext) -> None:
    message = update.effective_message
    user_id = update.effective_user.id
    
    # Owner Check
    if user_id != OWNER_ID:
        return
    
    target_id = None
    action_arg = None  
    first_name = "Unknown"

    # Agar message par reply kiya gaya hai
    if reply := message.reply_to_message:
        target_id = reply.from_user.id
        first_name = reply.from_user.first_name
        
        # Bot ke message par reply marne se roko
        if target_id == context.bot.id:
            await message.reply_text(
                "<b>❌ Bot ke message par reply mat kar bhai! User ke message par reply kar ya direct ID use kar.</b>", 
                parse_mode='HTML'
            )
            return

        if not context.args:
            await message.reply_text(
                "<b>⚠️ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀɴ ᴀᴄᴛɪᴏɴ!</b>\n"
                "<b>ᴜsᴀɢᴇ:</b> <code>/ukill [ᴄʜᴀʀ_ɪᴅ]</code> ᴏʀ <code>/ukill -all</code>", 
                parse_mode='HTML'
            )
            return
        
        action_arg = context.args[0].strip()
        
    else:
        # Bina reply ke command dene par
        if len(context.args) < 2:
            await message.reply_text(
                "<b>⚠️ ɪɴᴠᴀʟɪᴅ ᴜsᴀɢᴇ!</b>\n"
                "<b>ʀᴇᴘʟʏ:</b> <code>/ukill [ᴄʜᴀʀ_ɪᴅ]</code> ᴏʀ <code>/ukill -all</code>\n"
                "<b>ᴅɪʀᴇᴄᴛ:</b> <code>/ukill [ᴜsᴇʀ_ɪᴅ] [ᴄʜᴀʀ_ɪᴅ]</code> ᴏʀ <code>/ukill [ᴜsᴇʀ_ɪᴅ] -all</code>",
                parse_mode='HTML'
            )
            return
        
        try:
            target_id = int(context.args[0])
        except ValueError:
            await message.reply_text("<b>❌ ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ!</b>", parse_mode='HTML')
            return
        
        action_arg = context.args[1].strip()

    try:
        # Database se user fetch karna
        user = await user_collection.find_one({'id': target_id})
        
        if not user:
            await message.reply_text(
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
                await message.reply_text(
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
                await message.reply_text(success_msg, parse_mode='HTML')

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
                except Exception:
                    pass
            return

        # ----------------------------------------------------
        # ACTION 2: REMOVE SPECIFIC CHARACTER BY ID
        # ----------------------------------------------------
        
        target_index = -1
        # Input arg ko normalize karo (leading zero hatane ke liye)
        clean_action_arg = action_arg.lstrip('0') if action_arg.lstrip('0') else '0'

        for i, c in enumerate(characters):
            db_id_str = str(c.get('id')).strip()
            clean_db_id = db_id_str.lstrip('0') if db_id_str.lstrip('0') else '0'
            
            # Check for exact match OR match without leading zeros
            if db_id_str == action_arg or clean_db_id == clean_action_arg:
                target_index = i
                break
                
        if target_index == -1:
            await message.reply_text(
                f"<b>❌ ᴄʜᴀʀᴀᴄᴛᴇʀ (ɪᴅ: {action_arg}) ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ ᴜsᴇʀ's ᴄᴏʟʟᴇᴄᴛɪᴏɴ!</b>",
                parse_mode='HTML'
            )
            return
            
        # Sirf us ek instance ko safe tareeqe se pop karna 
        removed_char = characters.pop(target_index)
        
        # Main collection se data fetch kar rahe hain taaki original Rarity mil sake
        query = {'$or': [{'id': action_arg}, {'id': str(action_arg)}]}
        if action_arg.isdigit():
            query['$or'].append({'id': int(action_arg)})
            
        global_char = await collection.find_one(query)
        
        if global_char:
            char_name = global_char.get('name', removed_char.get('name', 'Unknown'))
            char_rarity = global_char.get('rarity', removed_char.get('rarity', 'N/A'))
        else:
            char_name = removed_char.get('name', 'Unknown')
            char_rarity = removed_char.get('rarity', 'N/A')

        # Database ko updated array se overwrite kar do
        result = await user_collection.update_one(
            {'id': target_id},
            {'$set': {'characters': characters}}
        )
        
        if result.modified_count > 0:
            success_msg = (
                f"<b>✅ ᴄʜᴀʀᴀᴄᴛᴇʀ sᴜᴄssғᴜʟʟʏ ʀᴇᴍᴏᴠᴇᴅ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>👤 ᴘʟᴀʏᴇʀ:</b> <a href='tg://user?id={target_id}'>{escape(first_name)}</a>\n"
                f"<b>🆔 ɪᴅ:</b> <code>{target_id}</code>\n"
                f"<b>🗑️ ʀᴇᴍᴏᴠᴇᴅ:</b> <code>{char_name}</code> ({char_rarity})\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )
            await message.reply_text(success_msg, parse_mode='HTML')

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
            except Exception:
                pass
        else:
            await message.reply_text("<b>❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴍᴏᴅɪғʏ ᴅᴀᴛᴀʙᴀsᴇ.</b>", parse_mode='HTML')
            
    except Exception as e:
        await message.reply_text(f"<b>⚠️ ᴇʀʀᴏʀ:</b> <code>{str(e)}</code>", parse_mode='HTML')

# Group -10 rakha hai taaki hamesha trigger ho
application.add_handler(CommandHandler(['Ukill', 'ukill'], Ukill, block=False), group=-10)

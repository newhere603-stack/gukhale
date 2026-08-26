import asyncio
from html import escape
from datetime import datetime
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
from shivu import application, user_collection, collection
from kill import clear_char_cache  # ⚠️ Ye dhyan rakhna ki ye properly exist karta ho

# Configuration
OWNER_ID = 7657218453
LOG_GROUP_ID = -1003893927065  # Aapka Log Group

async def Ukill(update: Update, context: CallbackContext) -> None:
    message = update.effective_message
    user_id = update.effective_user.id
    
    # --- TERMINAL DEBUG LOG 1 ---
    print(f"🔥 [UKILL DEBUG] Command Received from User ID: {user_id}")
    
    # Owner Check
    if user_id != OWNER_ID:
        print(f"❌ [UKILL DEBUG] Failed! User {user_id} is not the Owner ({OWNER_ID}).")
        return
        
    print(f"✅ [UKILL DEBUG] Owner Verified! Executing command...")
    
    target_id = None
    action_arg = None  
    first_name = "Unknown"

    # Agar message par reply kiya gaya hai
    if reply := message.reply_to_message:
        target_id = reply.from_user.id
        first_name = reply.from_user.first_name
        print(f"📩 [UKILL DEBUG] Reply detected! Target ID: {target_id}")
        
        if target_id == context.bot.id:
            print(f"⚠️ [UKILL DEBUG] Target is BOT itself. Sending warning.")
            await message.reply_text(
                "<b>❌ Bot ke message par reply mat kar bhai! User ke message par reply kar ya direct ID use kar.</b>", 
                parse_mode='HTML'
            )
            return

        if not context.args:
            print(f"⚠️ [UKILL DEBUG] No arguments provided in reply.")
            await message.reply_text(
                "<b>⚠️ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀɴ ᴀᴄᴛɪᴏɴ!</b>\n"
                "<b>ᴜsᴀɢᴇ:</b> <code>/ukill [ᴄʜᴀʀ_ɪᴅ]</code> ᴏʀ <code>/ukill -all</code>", 
                parse_mode='HTML'
            )
            return
        
        action_arg = context.args[0].strip()
        
    else:
        print(f"⌨️ [UKILL DEBUG] Direct command (no reply) detected.")
        if len(context.args) < 2:
            print(f"⚠️ [UKILL DEBUG] Not enough arguments for direct command.")
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
            print(f"❌ [UKILL DEBUG] Target ID is not a valid integer: {context.args[0]}")
            await message.reply_text("<b>❌ ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ!</b>", parse_mode='HTML')
            return
        
        action_arg = context.args[1].strip()

    print(f"🔍 [UKILL DEBUG] Target ID: {target_id} | Action Arg: {action_arg}")

    try:
        print(f"⏳ [UKILL DEBUG] Fetching user from Database...")
        user = await user_collection.find_one({'id': target_id})
        
        if not user:
            print(f"❌ [UKILL DEBUG] User not found in DB.")
            await message.reply_text(
                f"<b>❌ ᴜsᴇʀ ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ ᴅᴀᴛᴀʙᴀsᴇ!</b>\n<b>ɪᴅ:</b> <code>{target_id}</code>",
                parse_mode='HTML'
            )
            return
        
        first_name = user.get('first_name', first_name)
        characters = user.get('characters', [])
        print(f"✅ [UKILL DEBUG] User found. Total characters: {len(characters)}")
        
        # ----------------------------------------------------
        # ACTION 1: WIPE ALL CHARACTERS (-all)
        # ----------------------------------------------------
        if action_arg == '-all':
            print(f"🧨 [UKILL DEBUG] Mass Wipe (-all) initiated.")
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
                print(f"✅ [UKILL DEBUG] Mass wipe successful in DB. Clearing caches...")
                try:
                    for char in characters:
                        cid = str(char.get('id'))
                        clear_char_cache(cid)
                except Exception as cache_err:
                    print(f"⚠️ [UKILL DEBUG] Mass cache clear error: {cache_err}")

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
                except Exception as log_e:
                    print(f"⚠️ [UKILL DEBUG] Log Error: {log_e}")
            return

        # ----------------------------------------------------
        # ACTION 2: REMOVE SPECIFIC CHARACTER BY ID
        # ----------------------------------------------------
        print(f"🔫 [UKILL DEBUG] Single remove initiated for ID: {action_arg}")
        target_index = -1
        clean_action_arg = action_arg.lstrip('0') if action_arg.lstrip('0') else '0'

        for i, c in enumerate(characters):
            db_id_str = str(c.get('id')).strip()
            clean_db_id = db_id_str.lstrip('0') if db_id_str.lstrip('0') else '0'
            
            if db_id_str == action_arg or clean_db_id == clean_action_arg:
                target_index = i
                break
                
        if target_index == -1:
            print(f"❌ [UKILL DEBUG] Character {action_arg} not found in user inventory.")
            await message.reply_text(
                f"<b>❌ ᴄʜᴀʀᴀᴄᴛᴇʀ (ɪᴅ: {action_arg}) ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ ᴜsᴇʀ's ᴄᴏʟʟᴇᴄᴛɪᴏɴ!</b>",
                parse_mode='HTML'
            )
            return
            
        removed_char = characters.pop(target_index)
        print(f"✅ [UKILL DEBUG] Character popped from list. Fetching global stats...")
        
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

        print(f"💾 [UKILL DEBUG] Updating user DB...")
        result = await user_collection.update_one(
            {'id': target_id},
            {'$set': {'characters': characters}}
        )
        
        if result.modified_count > 0:
            print(f"✅ [UKILL DEBUG] DB Update successful. Clearing cache...")
            try:
                clear_char_cache(str(action_arg))
            except Exception as cache_err:
                print(f"⚠️ [UKILL DEBUG] Cache clear error: {cache_err}")

            success_msg = (
                f"<b>✅ ᴄʜᴀʀᴀᴄᴛᴇʀ sᴜᴄssғᴜʟʟʏ ʀᴇᴍᴏᴠᴇᴅ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>👤 ᴘʟᴀʏᴇʀ:</b> <a href='tg://user?id={target_id}'>{escape(first_name)}</a>\n"
                f"<b>🆔 ɪᴅ:</b> <code>{target_id}</code>\n"
                f"<b>🗑️ ʀᴇᴍᴏᴠᴇᴅ:</b> <code>{char_name}</code> ({char_rarity})\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )
            await message.reply_text(success_msg, parse_mode='HTML')

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
                print(f"⚠️ [UKILL DEBUG] Log Error: {log_e}")
        else:
            print(f"❌ [UKILL DEBUG] Failed to modify DB (modified_count == 0).")
            await message.reply_text("<b>❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴍᴏᴅɪғʏ ᴅᴀᴛᴀʙᴀsᴇ.</b>", parse_mode='HTML')
            
    except Exception as e:
        print(f"⚠️ [UKILL DEBUG] CRITICAL ERROR: {str(e)}")
        await message.reply_text(f"<b>⚠️ ᴇʀʀᴏʀ:</b> <code>{str(e)}</code>", parse_mode='HTML')

# 🔥 GROUP 69 ADD KIYA HAI - TAKI PURANA CODE ISE BLOCK NA KAR PAYE
application.add_handler(CommandHandler(['Ukill', 'ukill'], Ukill, block=False), group=827)

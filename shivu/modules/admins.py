from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

# Main database collections ko import kiya gaya hai
from shivu import application, user_collection, db, collection

# 🔥 NAYA IMPORT: Economy operations ke liye eco_collection
from shivu.Database.db import eco_collection

OWNER_ID = 7657218453
SUDO_USERS = [7657218453]

def is_authorized(user_id):
    return user_id == OWNER_ID or user_id in SUDO_USERS

bot_settings_collection = db['bot_settings']

# Economy Fields
COIN_FIELD = 'balance'   # /bal ke liye
TOKEN_FIELD = 'tokens'   # /tbal ke liye
GOLD_4_FIELD = 'gold_4'  # 4-letter word seek gold
GOLD_5_FIELD = 'gold'    # 5-letter word seek gold (default 'gold')
GOLD_6_FIELD = 'gold_6'  # 6-letter word seek gold

# --- Helper for adding/removing currency ---
async def modify_currency(update: Update, context: CallbackContext, field: str, currency_name: str, is_add: bool):
    try:
        requester_id = update.effective_user.id
        if not is_authorized(requester_id):
            return  # Normal users completely ignored
            
        text = update.message.text or update.message.caption
        if not text:
            return
            
        parts = text.split()
        command_used = parts[0].lower()
        args = parts[1:]
            
        target_id = None
        amount = None
        target_name = "ᴜsᴇʀ"
        
        # Check if replying to a user
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
            target_id = target_user.id
            target_name = target_user.first_name
            if len(args) >= 1:
                amount = args[0]
        else:
            if len(args) >= 2:
                target_id = args[0]
                amount = args[1]
                
        if target_id is None or amount is None:
            await update.message.reply_text(
                f"<b>ᴜsᴀɢᴇ: {command_used} ᴜsᴇʀ_ɪᴅ ᴀᴍᴏᴜɴᴛ ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴜsᴇʀ ᴡɪᴛʜ {command_used} ᴀᴍᴏᴜɴᴛ</b>", 
                parse_mode='HTML'
            )
            return
            
        try:
            target_id = int(target_id)
            amount = int(float(amount)) 
        except ValueError:
            await update.message.reply_text("<b>ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ ᴏʀ ᴀᴍᴏᴜɴᴛ.</b>", parse_mode='HTML')
            return
            
        # 🔥 FIX: Currency operations ab strictly eco_collection par hongi
        eco_user = await eco_collection.find_one({'id': target_id})
        
        # Fetch Name if not from reply
        if update.message.reply_to_message is None:
            if eco_user and 'first_name' in eco_user:
                target_name = eco_user['first_name']
            else:
                try:
                    chat = await context.bot.get_chat(target_id)
                    target_name = chat.first_name
                except:
                    target_name = "ᴜsᴇʀ"

        mention = f'<a href="tg://user?id={target_id}">{target_name}</a>'

        # Update currency with Auto-Upsert (Agar user DB me nahi hai toh create kar dega)
        if is_add:
            await eco_collection.update_one(
                {'id': target_id}, 
                {'$inc': {field: amount}, '$setOnInsert': {'first_name': target_name}}, 
                upsert=True
            )
        else:
            current = eco_user.get(field, 0) if eco_user else 0
            new_balance = max(0, current - amount)
            await eco_collection.update_one(
                {'id': target_id}, 
                {'$set': {field: new_balance}, '$setOnInsert': {'first_name': target_name}}, 
                upsert=True
            )
            
        # Fetch updated balance
        eco_user_updated = await eco_collection.find_one({'id': target_id})
        new_balance = eco_user_updated.get(field, 0)
        
        action = "ᴀᴅᴅᴇᴅ ᴛᴏ" if is_add else "ʀᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ"
        
        if currency_name == 'tokens':
            c_name = "ᴛᴏᴋᴇɴs"
        elif currency_name == 'gold_4':
            c_name = "4-ʟᴇᴛᴛᴇʀ ɢᴏʟᴅ"
        elif currency_name == 'gold_5':
            c_name = "5-ʟᴇᴛᴛᴇʀ ɢᴏʟᴅ"
        elif currency_name == 'gold_6':
            c_name = "6-ʟᴇᴛᴛᴇʀ ɢᴏʟᴅ"
        else:
            c_name = "ᴄᴏɪns"
        
        await update.message.reply_text(
            f"<b>sᴜᴄᴄᴇss! {amount} {c_name} {action} {mention}.\nᴜᴘᴅᴀᴛᴇᴅ ʙᴀʟᴀɴᴄᴇ: {new_balance} {c_name}.</b>",
            parse_mode='HTML'
        )
    except Exception as e:
        await update.message.reply_text(f"<b>ᴇʀʀᴏʀ: {str(e)}</b>", parse_mode='HTML')


# --- /destroy <user_id> OR Reply ---
async def destroy_cmd(update: Update, context: CallbackContext):
    try:
        requester_id = update.effective_user.id
        if not is_authorized(requester_id):
            return 

        text = update.message.text or update.message.caption
        parts = text.split()
        args = parts[1:]

        target_id = None
        target_name = "ᴜsᴇʀ"

        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
            target_id = target_user.id
            target_name = target_user.first_name
        elif len(args) >= 1:
            target_id = args[0]

        if not target_id:
            await update.message.reply_text("<b>ᴜsᴀɢᴇ: /destroy ᴜsᴇʀ_ɪᴅ ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ</b>", parse_mode='HTML')
            return

        try:
            target_id = int(target_id)
        except ValueError:
            await update.message.reply_text("<b>ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ.</b>", parse_mode='HTML')
            return

        # Destroy command Harem (user_collection) par hi chalegi
        user = await user_collection.find_one({'id': target_id})
        if not user:
            await update.message.reply_text("<b>ᴜsᴇʀ ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ ᴅᴀᴛᴀʙᴀsᴇ.</b>", parse_mode='HTML')
            return
            
        if update.message.reply_to_message is None and 'first_name' in user:
             target_name = user['first_name']

        mention = f'<a href="tg://user?id={target_id}">{target_name}</a>'
        count = len(user.get('characters', []))

        await user_collection.update_one(
            {'id': target_id},
            {'$set': {'characters': []}}
        )

        await update.message.reply_text(
            f"<b>sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇsᴛʀᴏʏᴇᴅ {count} ᴄʜᴀʀᴀᴄᴛᴇʀs ғᴏʀ {mention}</b>", 
            parse_mode='HTML'
        )
    except Exception as e:
        await update.message.reply_text(f"<b>ᴇʀʀᴏʀ: {str(e)}</b>", parse_mode='HTML')


# --- /fixrarity <char_id> (ADVANCED DYNAMIC UPDATE & ID FIX) ---
async def fixrarity_cmd(update: Update, context: CallbackContext):
    try:
        requester_id = update.effective_user.id
        if not is_authorized(requester_id):
            return 

        text = update.message.text or update.message.caption
        parts = text.split()
        args = parts[1:]

        if len(args) < 1:
            await update.message.reply_text("<b>⚠️ ᴜsᴀɢᴇ:</b> <code>/fixrarity [ᴄʜᴀʀ_ɪᴅ]</code>", parse_mode='HTML')
            return

        char_id_input = str(args[0])
        
        search_ids = [char_id_input]
        if char_id_input.isdigit():
            search_ids.append(str(int(char_id_input))) 
            search_ids.append(int(char_id_input))      

        global_char = await collection.find_one({'id': {'$in': search_ids}})
        
        if not global_char:
            await update.message.reply_text(f"<b>❌ ᴄʜᴀʀᴀᴄᴛᴇʀ ɪᴅ <code>{char_id_input}</code> ᴍᴀɪɴ ᴅᴀᴛᴀʙᴀsᴇ ᴍᴇ ɴᴀʜɪ ᴍɪʟᴀ!</b>", parse_mode='HTML')
            return

        current_rarity = global_char.get('rarity', 'Unknown')
        current_name = global_char.get('name', 'Unknown')

        # Harem DB mein rarities fix karega
        users_cursor = user_collection.find({"characters.id": {"$in": search_ids}})
        affected_count = 0
        
        async for user in users_cursor:
            updated_chars = []
            modified = False
            for c in user.get('characters', []):
                if c.get('id') in search_ids:
                    c['rarity'] = current_rarity
                    c['name'] = current_name
                    modified = True
                updated_chars.append(c)
            
            if modified:
                await user_collection.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"characters": updated_chars}}
                )
                affected_count += 1

        success_msg = (
            f"<b>✅ ᴅᴀᴛᴀʙᴀsᴇ ᴜᴘᴅᴀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>🆔 ᴄʜᴀʀ ɪᴅ:</b> <code>{char_id_input}</code>\n"
            f"<b>📝 ᴄʜᴀʀ ɴᴀᴍᴇ:</b> <code>{current_name}</code>\n"
            f"<b>✨ ᴄᴜʀʀᴇɴᴛ ʀᴀʀɪᴛʏ:</b> <code>{current_rarity}</code>\n"
            f"<b>👥 ᴜsᴇʀs ᴀғғᴇᴄᴛᴇᴅ:</b> <code>{affected_count}</code> ᴘʟᴀʏᴇʀs\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(success_msg, parse_mode='HTML')

    except Exception as e:
        await update.message.reply_text(f"<b>⚠️ ᴇʀʀᴏʀ:</b> <code>{str(e)}</code>", parse_mode='HTML')


# --- /setded <percentage> ---
async def setded_cmd(update: Update, context: CallbackContext):
    try:
        requester_id = update.effective_user.id
        if not is_authorized(requester_id):
            return 

        text = update.message.text or update.message.caption
        parts = text.split()
        args = parts[1:]

        if len(args) < 1:
            await update.message.reply_text("<b>ᴜsᴀɢᴇ: /setded ᴘᴇʀᴄᴇɴᴛᴀɢᴇ</b>", parse_mode='HTML')
            return

        try:
            percentage = float(args[0])
        except ValueError:
            await update.message.reply_text("<b>ɪɴᴠᴀʟɪᴅ ᴘᴇʀᴄᴇɴᴛᴀɢᴇ.</b>", parse_mode='HTML')
            return

        await bot_settings_collection.update_one(
            {'_id': 'settings'},
            {'$set': {'deduction_percentage': percentage}},
            upsert=True
        )

        await update.message.reply_text(
            f"<b>ᴅᴇᴅᴜᴄᴛɪᴏɴ ᴘᴇʀᴄᴇɴᴛᴀɢᴇ sᴇᴛ ᴛᴏ {percentage:.1f}%</b>", 
            parse_mode='HTML'
        )
    except Exception as e:
        await update.message.reply_text(f"<b>ᴇʀʀᴏʀ: {str(e)}</b>", parse_mode='HTML')


# --- Economy Wrappers ---
async def tadd_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, TOKEN_FIELD, 'tokens', True)

async def cadd_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, COIN_FIELD, 'coins', True)

# 4-Letter Gold Add/Rem
async def g4add_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, GOLD_4_FIELD, 'gold_4', True)

async def g4rem_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, GOLD_4_FIELD, 'gold_4', False)

# 5-Letter Gold Add/Rem (Default /gadd aur /grem)
async def gadd_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, GOLD_5_FIELD, 'gold_5', True)

async def grem_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, GOLD_5_FIELD, 'gold_5', False)

# 6-Letter Gold Add/Rem
async def g6add_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, GOLD_6_FIELD, 'gold_6', True)

async def g6rem_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, GOLD_6_FIELD, 'gold_6', False)

async def trem_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, TOKEN_FIELD, 'tokens', False)

async def crem_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, COIN_FIELD, 'coins', False)


# Handlers registration
application.add_handler(CommandHandler(['destroy'], destroy_cmd, block=False))
application.add_handler(CommandHandler(['setded'], setded_cmd, block=False))
application.add_handler(CommandHandler(['tadd'], tadd_cmd, block=False))
application.add_handler(CommandHandler(['cadd'], cadd_cmd, block=False))
application.add_handler(CommandHandler(['gadd'], gadd_cmd, block=False))
application.add_handler(CommandHandler(['g4add'], g4add_cmd, block=False))
application.add_handler(CommandHandler(['g6add'], g6add_cmd, block=False))
application.add_handler(CommandHandler(['trem'], trem_cmd, block=False))
application.add_handler(CommandHandler(['crem'], crem_cmd, block=False))
application.add_handler(CommandHandler(['grem'], grem_cmd, block=False))
application.add_handler(CommandHandler(['g4rem'], g4rem_cmd, block=False))
application.add_handler(CommandHandler(['g6rem'], g6rem_cmd, block=False))
application.add_handler(CommandHandler(['fixrarity'], fixrarity_cmd, block=False))

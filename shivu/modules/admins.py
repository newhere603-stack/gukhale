from telegram import Update
from telegram.ext import CommandHandler, CallbackContext, TypeHandler, ApplicationHandlerStop

# Main database collections ko import kiya gaya hai
from shivu import application, user_collection, db, collection

# 🔥 NAYA IMPORT: Economy operations ke liye eco_collection
from shivu.Database.db import eco_collection

OWNER_ID = 7657218453
SUDO_USERS = [7657218453]

def is_authorized(user_id):
    return user_id == OWNER_ID or user_id in SUDO_USERS

bot_settings_collection = db['bot_settings']
banned_collection = db['banned_users'] # 🔥 BAN SYSTEM KE LIYE NAYA COLLECTION

# Economy Fields
COIN_FIELD = 'balance'   
TOKEN_FIELD = 'tokens'   
GOLD_4_FIELD = 'gold_4'  
GOLD_5_FIELD = 'gold'    
GOLD_6_FIELD = 'gold_6'  

# --- Global Ban Interceptor (Har update se pehle check karega) ---
async def ban_interceptor(update: Update, context: CallbackContext):
    if not update.effective_user:
        return
        
    user_id = update.effective_user.id
    
    # Sudo users ko kabhi block nahi karna hai
    if is_authorized(user_id):
        return

    # Check if user is in banned database
    is_banned = await banned_collection.find_one({'user_id': user_id})
    if is_banned:
        # 🔥 FIX: Ab sirf tabhi reply aayega jab user '/' (command) lagakar kuch bheje
        if update.message and update.message.text and update.message.text.startswith('/'):
            await update.message.reply_text("<b>ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ ʙᴀᴋᴀ!</b>", parse_mode='HTML')
        elif update.callback_query:
            await update.callback_query.answer("ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ ʙᴀᴋᴀ!", show_alert=True)
            
        # Bot ki aage ki saari processing rok dega
        raise ApplicationHandlerStop()


# --- /gban <user_id> OR Reply ---
async def ban_user(update: Update, context: CallbackContext):
    try:
        requester_id = update.effective_user.id
        if not is_authorized(requester_id):
            return 

        text = update.message.text or update.message.caption
        parts = text.split()
        args = parts[1:]

        target_id = None

        if update.message.reply_to_message:
            target_id = update.message.reply_to_message.from_user.id
        elif len(args) >= 1:
            target_id = args[0]

        if not target_id:
            await update.message.reply_text("<b>ᴜsᴀɢᴇ: /gban ᴜsᴇʀ_ɪᴅ ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ</b>", parse_mode='HTML')
            return

        try:
            target_id = int(target_id)
        except ValueError:
            await update.message.reply_text("<b>ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ.</b>", parse_mode='HTML')
            return

        # Sudo user ya Owner ko ban hone se rokne ke liye
        if is_authorized(target_id):
            await update.message.reply_text("<b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʙᴀɴ ᴀɴ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴜsᴇʀ! ⚠️</b>", parse_mode='HTML')
            return
            
        # Khud bot ko ban hone se rokne ke liye
        if context.bot.id == target_id:
            await update.message.reply_text("<b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʙᴀɴ ᴛʜᴇ ʙᴏᴛ! 🤖</b>", parse_mode='HTML')
            return

        # Check if already banned
        already_banned = await banned_collection.find_one({'user_id': target_id})
        if already_banned:
            await update.message.reply_text(f"<b>ᴜsᴇʀ <code>{target_id}</code> ɪs ᴀʟʀᴇᴀᴅʏ ʙᴀɴɴᴇᴅ! ⚠️</b>", parse_mode='HTML')
            return

        # Database me add karna
        await banned_collection.update_one(
            {'user_id': target_id},
            {'$set': {'user_id': target_id}},
            upsert=True
        )

        await update.message.reply_text(f"<b>ᴜsᴇʀ <code>{target_id}</code> ʜᴀs ʙᴇᴇɴ ʙᴀɴɴᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ! 🛑</b>", parse_mode='HTML')

    except Exception as e:
        await update.message.reply_text(f"<b>ᴇʀʀᴏʀ: {str(e)}</b>", parse_mode='HTML')


# --- /gunban <user_id> OR Reply ---
async def unban_user(update: Update, context: CallbackContext):
    try:
        requester_id = update.effective_user.id
        if not is_authorized(requester_id):
            return 

        text = update.message.text or update.message.caption
        parts = text.split()
        args = parts[1:]

        target_id = None

        if update.message.reply_to_message:
            target_id = update.message.reply_to_message.from_user.id
        elif len(args) >= 1:
            target_id = args[0]

        if not target_id:
            await update.message.reply_text("<b>ᴜsᴀɢᴇ: /gunban ᴜsᴇʀ_ɪᴅ ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ</b>", parse_mode='HTML')
            return

        try:
            target_id = int(target_id)
        except ValueError:
            await update.message.reply_text("<b>ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ.</b>", parse_mode='HTML')
            return

        # Database se remove karna
        result = await banned_collection.delete_one({'user_id': target_id})
        
        if result.deleted_count > 0:
            await update.message.reply_text(f"<b>ᴜsᴇʀ <code>{target_id}</code> ʜᴀs ʙᴇᴇɴ ᴜɴʙᴀɴɴᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ! ✅</b>", parse_mode='HTML')
        else:
            await update.message.reply_text(f"<b>ᴜsᴇʀ <code>{target_id}</code> ɪs ɴᴏᴛ ʙᴀɴɴᴇᴅ. ⚠️</b>", parse_mode='HTML')

    except Exception as e:
        await update.message.reply_text(f"<b>ᴇʀʀᴏʀ: {str(e)}</b>", parse_mode='HTML')


# --- Helper for adding/removing currency ---
async def modify_currency(update: Update, context: CallbackContext, field: str, currency_name: str, is_add: bool):
    try:
        requester_id = update.effective_user.id
        if not is_authorized(requester_id):
            return  
            
        text = update.message.text or update.message.caption
        if not text:
            return
            
        parts = text.split()
        command_used = parts[0].lower()
        args = parts[1:]
            
        target_id = None
        amount = None
        target_name = "ᴜsᴇʀ"
        
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
            
        eco_user = await eco_collection.find_one({'id': target_id})
        
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

async def g4add_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, GOLD_4_FIELD, 'gold_4', True)

async def g4rem_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, GOLD_4_FIELD, 'gold_4', False)

async def gadd_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, GOLD_5_FIELD, 'gold_5', True)

async def grem_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, GOLD_5_FIELD, 'gold_5', False)

async def g6add_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, GOLD_6_FIELD, 'gold_6', True)

async def g6rem_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, GOLD_6_FIELD, 'gold_6', False)

async def trem_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, TOKEN_FIELD, 'tokens', False)

async def crem_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, COIN_FIELD, 'coins', False)


# 🔥 BAN INTERCEPTOR KO SBSE PEHLE ADD KARNA (Group -10) TAAKI WO SABSE PEHLE CHECK HO
application.add_handler(TypeHandler(Update, ban_interceptor), group=-10)

# Handlers registration
application.add_handler(CommandHandler(['gban'], ban_user, block=False))
application.add_handler(CommandHandler(['gunban'], unban_user, block=False))
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

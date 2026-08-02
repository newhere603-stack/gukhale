from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from shivu import application, user_collection, db

OWNER_ID = 7657218453
SUDO_USERS = [7657218453]

def is_authorized(user_id):
    return user_id == OWNER_ID or user_id in SUDO_USERS

bot_settings_collection = db['bot_settings']

# Sahi Economy Fields
COIN_FIELD = 'balance'   # /bal ke liye
TOKEN_FIELD = 'tokens'   # /tbal ke liye

# --- Helper for adding/removing currency ---
async def modify_currency(update: Update, context: CallbackContext, field: str, currency_name: str, is_add: bool):
    try:
        requester_id = update.effective_user.id
        if not is_authorized(requester_id):
            return  # Normal users completely ignored
            
        # Get the actual command used (e.g., /tadd, /cadd)
        command_used = update.message.text.split()[0].lower()
            
        target_id = None
        amount = None
        target_name = "ᴜsᴇʀ"
        
        # Check if replying to a user
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
            target_id = target_user.id
            target_name = target_user.first_name
            if len(context.args) >= 1:
                amount = context.args[0]
        else:
            # Command with user ID and amount
            if len(context.args) >= 2:
                target_id = context.args[0]
                amount = context.args[1]
                
        if target_id is None or amount is None:
            await update.message.reply_text(
                f"<b>ᴜsᴀɢᴇ: {command_used} ᴜsᴇʀ_ɪᴅ ᴀᴍᴏᴜɴᴛ ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴜsᴇʀ ᴡɪᴛʜ {command_used} ᴀᴍᴏᴜɴᴛ</b>", 
                parse_mode='HTML'
            )
            return
            
        try:
            target_id = int(target_id)
            amount = int(float(amount)) # Float ko int me convert karne ke liye in case decimal aaye
        except ValueError:
            await update.message.reply_text("<b>ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ ᴏʀ ᴀᴍᴏᴜɴᴛ.</b>", parse_mode='HTML')
            return
            
        # Check if user exists
        user = await user_collection.find_one({'id': target_id})
        if not user:
            await update.message.reply_text("<b>ᴜsᴇʀ ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ ᴅᴀᴛᴀʙᴀsᴇ.</b>", parse_mode='HTML')
            return

        # Fetch Name if not from reply
        if update.message.reply_to_message is None:
            if 'first_name' in user:
                target_name = user['first_name']
            else:
                try:
                    chat = await context.bot.get_chat(target_id)
                    target_name = chat.first_name
                except:
                    target_name = "ᴜsᴇʀ"

        mention = f'<a href="tg://user?id={target_id}">{target_name}</a>'

        # Update currency
        if is_add:
            await user_collection.update_one({'id': target_id}, {'$inc': {field: amount}})
        else:
            current = user.get(field, 0)
            new_balance = max(0, current - amount)
            await user_collection.update_one({'id': target_id}, {'$set': {field: new_balance}})
            
        # Fetch updated balance
        user = await user_collection.find_one({'id': target_id})
        new_balance = user.get(field, 0)
        
        action = "ᴀᴅᴅᴇᴅ ᴛᴏ" if is_add else "ʀᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ"
        c_name = "ᴛᴏᴋᴇɴs" if currency_name == 'tokens' else "ᴄᴏɪɴs"
        
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

        target_id = None
        target_name = "ᴜsᴇʀ"

        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
            target_id = target_user.id
            target_name = target_user.first_name
        elif context.args:
            target_id = context.args[0]

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

        if not context.args:
            await update.message.reply_text("<b>ᴜsᴀɢᴇ: /setded ᴘᴇʀᴄᴇɴᴛᴀɢᴇ</b>", parse_mode='HTML')
            return

        try:
            percentage = float(context.args[0])
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

async def trem_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, TOKEN_FIELD, 'tokens', False)

async def crem_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, COIN_FIELD, 'coins', False)


# Handlers registration
application.add_handler(CommandHandler(['destroy'], destroy_cmd, block=False))
application.add_handler(CommandHandler(['setded'], setded_cmd, block=False))
application.add_handler(CommandHandler(['tadd'], tadd_cmd, block=False))
application.add_handler(CommandHandler(['cadd'], cadd_cmd, block=False))
application.add_handler(CommandHandler(['trem'], trem_cmd, block=False))
application.add_handler(CommandHandler(['crem'], crem_cmd, block=False))

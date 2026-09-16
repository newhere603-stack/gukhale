from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

# Main database collections ko import kiya gaya hai
from shivu import application

# 🔥 Economy operations ke liye eco_collection
from shivu.Database.db import eco_collection

OWNER_ID = 7657218453
SUDO_USERS = [7657218453]

def is_authorized(user_id):
    return user_id == OWNER_ID or user_id in SUDO_USERS

# Economy Fields (Sirf Gold wale rakhe gaye hain)
GOLD_4_FIELD = 'gold_4'  
GOLD_5_FIELD = 'gold'    
GOLD_6_FIELD = 'gold_6'  

# --- Helper for adding currency ---
async def modify_currency(update: Update, context: CallbackContext, field: str, currency_name: str):
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

        # Sirf add karne ka logic rakha gaya hai
        await eco_collection.update_one(
            {'id': target_id}, 
            {'$inc': {field: amount}, '$setOnInsert': {'first_name': target_name}}, 
            upsert=True
        )
            
        eco_user_updated = await eco_collection.find_one({'id': target_id})
        new_balance = eco_user_updated.get(field, 0)
        
        if currency_name == 'gold_4':
            c_name = "4-ʟᴇᴛᴛᴇʀ ɢᴏʟᴅ"
        elif currency_name == 'gold_5':
            c_name = "5-ʟᴇᴛᴛᴇʀ ɢᴏʟᴅ"
        elif currency_name == 'gold_6':
            c_name = "6-ʟᴇᴛᴛᴇʀ ɢᴏʟᴅ"
        else:
            c_name = "ɢᴏʟᴅ"
        
        await update.message.reply_text(
            f"<b>sᴜᴄᴄᴇss! {amount} {c_name} ᴀᴅᴅᴇᴅ ᴛᴏ {mention}.\nᴜᴘᴅᴀᴛᴇᴅ ʙᴀʟᴀɴᴄᴇ: {new_balance} {c_name}.</b>",
            parse_mode='HTML'
        )
    except Exception as e:
        await update.message.reply_text(f"<b>ᴇʀʀᴏʀ: {str(e)}</b>", parse_mode='HTML')


# --- Economy Wrappers (Sirf Gold Add) ---
async def g4add_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, GOLD_4_FIELD, 'gold_4')

async def gadd_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, GOLD_5_FIELD, 'gold_5')

async def g6add_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, GOLD_6_FIELD, 'gold_6')


# Handlers registration
application.add_handler(CommandHandler(['gadd'], gadd_cmd, block=False))
application.add_handler(CommandHandler(['g4add'], g4add_cmd, block=False))
application.add_handler(CommandHandler(['g6add'], g6add_cmd, block=False))

from bson import ObjectId
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from shivu import application, db

user_collection = db['user_collection_lmaoooo']
market_collection = db['market_collection']

# States
WAITING_FOR_CHARACTER_ID, WAITING_FOR_PRICE = 1, 2

# Helper for small caps
def to_small_caps(text: str) -> str:
    return str(text).translate(str.maketrans("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"))

# 1. MAIN COMMAND
async def pmarket_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 ʙᴜʏ", callback_data=f"pm_b:{user_id}")],
        [InlineKeyboardButton("💸 sᴇʟʟ", callback_data=f"pm_sm:{user_id}")]
    ])
    await update.message.reply_text("<b>🟡 ᴘ2ᴘ ᴍᴀʀᴋᴇᴛᴘʟᴀᴄᴇ</b>\n\n<i>ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ.</i>", reply_markup=keyboard, parse_mode='HTML')

# 2. SELLING CONVERSATION
async def sell_start(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    await query.message.edit_text("<b>💸 Sᴇɴᴅ ᴛʜᴇ ᴄʜᴀʀᴀᴄᴛᴇʀ ɪᴅ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ sᴇʟʟ:</b>", parse_mode='HTML')
    return WAITING_FOR_CHARACTER_ID

async def ask_character_id(update: Update, context: CallbackContext):
    char_id = update.message.text.strip()
    user_id = update.message.from_user.id
    user_data = await user_collection.find_one({'id': user_id})
    character = next((c for c in user_data.get('characters', []) if str(c.get('id')) == char_id), None)
    
    if not character:
        await update.message.reply_text("❌ ɪɴᴠᴀʟɪᴅ ɪᴅ! sᴇɴᴅ ᴀɢᴀɪɴ ᴏʀ /cancel")
        return WAITING_FOR_CHARACTER_ID
    
    context.user_data['sell_character'] = character
    await update.message.reply_text("✅ ᴄʜᴀʀᴀᴄᴛᴇʀ ғᴏᴜɴᴅ! ɴᴏᴡ sᴇɴᴅ ᴛʜᴇ ᴘʀɪᴄᴇ (ɴᴜᴍʙᴇʀ ᴏɴʟʏ):")
    return WAITING_FOR_PRICE

async def ask_price(update: Update, context: CallbackContext):
    price = update.message.text.strip()
    if not price.isdigit():
        await update.message.reply_text("❌ ᴇɴᴛᴇʀ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ!")
        return WAITING_FOR_PRICE
    
    character = context.user_data.get('sell_character')
    user_id = update.message.from_user.id
    
    await user_collection.update_one({'id': user_id}, {'$pull': {'characters': {'id': character['id']}}})
    await market_collection.insert_one({'seller_id': user_id, 'price': int(price), 'character': character})
    
    await update.message.reply_text(f"🎉 {character['name']} sᴜᴄᴄᴇssғᴜʟʟʏ ʟɪsᴛᴇᴅ ғᴏʀ {price}!")
    context.user_data.pop('sell_character', None)
    return ConversationHandler.END

async def cancel_sell(update: Update, context: CallbackContext):
    context.user_data.pop('sell_character', None)
    await update.message.reply_text("❌ ᴄᴀɴᴄᴇʟʟᴇᴅ.")
    return ConversationHandler.END

# 3. HANDLER
sell_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(sell_start, pattern='^pm_sm:')],
    states={
        WAITING_FOR_CHARACTER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_character_id)],
        WAITING_FOR_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_price)]
    },
    fallbacks=[CommandHandler('cancel', cancel_sell)],
    persistent=False,
    allow_reentry=True
)

# Registering
application.add_handler(sell_conv, group=0)
application.add_handler(CommandHandler("pmarket", pmarket_command))

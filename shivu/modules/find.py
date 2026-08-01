import random
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from shivu import application, db

# Collections
collection = db['anime_characters_lol']
user_collection = db['user_collection_groups'] 

# Sudo Users List
SUDO_USERS = [7657218453] 

# --- Rarity and Default Pricing ---
DEFAULT_PRICES = {
    "🟢 Common": 10000,
    "🔵 Rare": 20000,
    "🟠 Medium": 30000,
    "🟡 Legendary": 50000,
    "🪽 Celestial": 75000,
    "🥵 Spicy": 100000,
    "🥴 Seductive": 125000,
    "💎 Mythic": 150000,
    "🔮 Premium Edition": 200000,
    "🍭 Sweet": 250000,
    "💋 Erotic": 300000,
    "❄️ Winter": 350000,
    "⚡ Neon": 400000,
    "🐚 Summer": 450000,
    "🌌 Manga": 500000
}

# --- Universal Small Caps & Bold Converter ---
def to_small_caps(text: str, is_html=True) -> str:
    mapping = {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 
        'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 
        'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 
        's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 
        'y': 'ʏ', 'z': 'ᴢ',
        'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ꜰ', 
        'G': 'ɢ', 'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 
        'M': 'ᴍ', 'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'ǫ', 'R': 'ʀ', 
        'S': 'ꜱ', 'T': 'ᴛ', 'U': 'ᴜ', 'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x', 
        'Y': 'ʏ', 'Z': 'ᴢ'
    }
    converted = "".join(mapping.get(c, c) for c in str(text))
    if is_html:
        return f"<b>{converted}</b>"
    return converted

def get_price(char):
    if 'mp_price' in char and char['mp_price'] is not None:
        return char['mp_price']
    rarity = char.get('rarity', 'Unknown')
    return DEFAULT_PRICES.get(rarity, 50000) 


# --- Sudo Command to Set Custom Price ---
async def set_mp_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in SUDO_USERS:
        await update.message.reply_text(to_small_caps("❌ Only Sudo/Owner can use this command."), parse_mode='HTML')
        return
    
    if len(context.args) != 2:
        msg = "Usage: /setprice <char_id> <price>\nExample: /setprice 1024 15000"
        await update.message.reply_text(f"<blockquote>{to_small_caps(msg)}</blockquote>", parse_mode='HTML')
        return
        
    char_id = context.args[0]
    try:
        price = int(context.args[1])
    except ValueError:
        await update.message.reply_text(to_small_caps("❌ Price numbers me hona chahiye."), parse_mode='HTML')
        return
        
    result = await collection.update_one({'id': char_id}, {'$set': {'mp_price': price}})
    if result.modified_count > 0:
        await update.message.reply_text(to_small_caps(f"✅ Character ID {char_id} ka marketplace price {price:,} 💰 set ho gaya hai."), parse_mode='HTML')
    else:
        await update.message.reply_text(to_small_caps("❌ Character ID nahi mila, ya price already same hai."), parse_mode='HTML')


# --- Marketplace Feature ---
async def marketplace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        pipeline = [{"$sample": {"size": 1}}]
        chars = await collection.aggregate(pipeline).to_list(length=1)
        
        if not chars:
            await update.message.reply_text(to_small_caps('❌ No characters found in database.'), parse_mode='HTML')
            return
            
        char = chars[0]
        name = char.get('name', 'Unknown')
        anime = char.get('anime', 'Unknown')
        char_id = char.get('id', str(random.randint(1000, 9999)))
        rarity = char.get('rarity', 'Unknown')
        img_url = char.get('img_url', None)

        price = get_price(char)

        caption = f"""{to_small_caps('🏪 Daily Deals Marketplace')}

{to_small_caps('📛 Name:')} {to_small_caps(name)}
{to_small_caps('📺 Series:')} {to_small_caps(anime)}
{to_small_caps('🆔 ID:')} {to_small_caps(char_id)}
{to_small_caps('💫 Rarity:')} {to_small_caps(rarity)}
{to_small_caps('💰 Price:')} {to_small_caps(f"{price:,} Tokens")}

{to_small_caps('🛒 Status:')} {to_small_caps('Available')}"""

        buttons = [
            [InlineKeyboardButton(to_small_caps("🛒 Buy Character", is_html=False), callback_data=f"mp_buy_{char_id}_{price}")],
            [InlineKeyboardButton(to_small_caps("🔄 Refresh Deal", is_html=False), callback_data="mp_refresh")]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)

        if img_url:
            await update.message.reply_photo(
                photo=img_url, 
                caption=caption, 
                reply_markup=reply_markup, 
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                text=caption, 
                reply_markup=reply_markup, 
                parse_mode='HTML'
            )

    except Exception as e:
        await update.message.reply_text(f"<blockquote>{to_small_caps(f'Error in Marketplace: {str(e)}') }</blockquote>", parse_mode='HTML')


# --- Purchase Callback Handler ---
async def marketplace_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if data == "mp_refresh":
        await query.answer(to_small_caps("Refreshing Marketplace...", is_html=False), show_alert=False)
        await query.message.delete()
        await query.message.reply_text(to_small_caps("🔄 Marketplace deal refresh ho gaya hai. Naya character dekhne ke liye dubara /mp use karein."), parse_mode='HTML')
        return

    if data.startswith("mp_buy_"):
        parts = data.split("_")
        char_id = parts[2]
        price = int(parts[3])
        
        char = await collection.find_one({'id': char_id})
        if not char:
            await query.answer(to_small_caps("❌ Ye character ab database me nahi hai!", is_html=False), show_alert=True)
            return
            
        user = await user_collection.find_one({'id': user_id})
        if not user:
            await query.answer(to_small_caps("❌ Please /start the bot first to create an account!", is_html=False), show_alert=True)
            return

        user_balance = user.get('balance', 0) 
        
        if user_balance < price:
            await query.answer(to_small_caps(f"❌ Funds kam hain! Price {price:,} hai par aapke paas sirf {user_balance:,} tokens hain.", is_html=False), show_alert=True)
            return
            
        await user_collection.update_one(
            {'id': user_id},
            {
                '$inc': {'balance': -price},
                '$push': {'characters': char}
            }
        )
        
        await query.answer(to_small_caps(f"✅ Transaction Successful! {char['name']} is now yours.", is_html=False), show_alert=True)
        
        sold_text = to_small_caps(f"🎉 {char['name']} has been SOLD to {query.from_user.first_name} for {price:,} Tokens!")
        
        # FIX: Check if message has photo to prevent crash when editing text
        try:
            if query.message.photo:
                await query.edit_message_caption(caption=sold_text, parse_mode='HTML')
            else:
                await query.edit_message_text(text=sold_text, parse_mode='HTML')
        except Exception as e:
            print(f"Error editing message: {e}")


# --- Handlers Register ---
application.add_handler(CommandHandler(['mp', 'marketplace'], marketplace))
application.add_handler(CommandHandler('setprice', set_mp_price))
application.add_handler(CallbackQueryHandler(marketplace_callbacks, pattern="^mp_"))

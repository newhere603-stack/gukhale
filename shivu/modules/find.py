import random
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from shivu import application, db

# Collections (Apne database ke actual user collection ka naam check kar lena agar alag ho)
collection = db['anime_characters_lol']
user_collection = db['user_collection_groups'] 

# Sudo Users List (Tumhari ID added hai)
SUDO_USERS = [7657218453] 

# --- Rarity and Default Pricing (Strictly based on Photo) ---
# Yahan tum prices ko apne hisaab se ghata/badha sakte ho
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
def to_small_caps(text: str) -> str:
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
    return f"<b>{converted}</b>"

def get_price(char):
    """Character ki price nikalta hai (Sudo set price ya phir default)"""
    if 'mp_price' in char and char['mp_price'] is not None:
        return char['mp_price']
    
    rarity = char.get('rarity', 'Unknown')
    return DEFAULT_PRICES.get(rarity, 50000) # Agar rarity list me na ho to 50k default


# --- Sudo Command to Set Custom Price ---
async def set_mp_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in SUDO_USERS:
        await update.message.reply_text("❌ Only Sudo/Owner can use this command.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("<blockquote>Usage: /setprice <char_id> <price>\nExample: /setprice 1024 15000</blockquote>", parse_mode='HTML')
        return
        
    char_id = context.args[0]
    try:
        price = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Price numbers me hona chahiye.")
        return
        
    result = await collection.update_one({'id': char_id}, {'$set': {'mp_price': price}})
    if result.modified_count > 0:
        await update.message.reply_text(f"✅ Character ID <b>{char_id}</b> ka marketplace price <b>{price:,} 💰</b> set ho gaya hai.", parse_mode='HTML')
    else:
        await update.message.reply_text("❌ Character ID nahi mila, ya price already same hai.")


# --- Marketplace Feature ---
async def marketplace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Pick 1 random character for the marketplace deal
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

        # Get final price
        price = get_price(char)

        caption = f"""{to_small_caps('🏪 Daily Deals Marketplace')}

{to_small_caps('📛 Name:')} {to_small_caps(name)}
{to_small_caps('📺 Series:')} {to_small_caps(anime)}
{to_small_caps('🆔 ID:')} <b>{char_id}</b>
{to_small_caps('💫 Rarity:')} {to_small_caps(rarity)}
{to_small_caps('💰 Price:')} <b>{price:,} Tokens</b>

{to_small_caps('🛒 Status:')} {to_small_caps('Available')}"""

        buttons = [
            [InlineKeyboardButton("🛒 Buy Character", callback_data=f"mp_buy_{char_id}_{price}")],
            [InlineKeyboardButton("🔄 Refresh Deal", callback_data="mp_refresh")]
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
        await query.answer("Refreshing Marketplace...", show_alert=False)
        await query.message.delete()
        await query.message.reply_text("🔄 Marketplace deal refresh ho gaya hai. Naya character dekhne ke liye dubara /mp use karein.")
        return

    if data.startswith("mp_buy_"):
        parts = data.split("_")
        char_id = parts[2]
        price = int(parts[3])
        
        # 1. Check if character still exists in main collection
        char = await collection.find_one({'id': char_id})
        if not char:
            await query.answer("❌ Ye character ab database me nahi hai!", show_alert=True)
            return
            
        # 2. Get user info
        user = await user_collection.find_one({'id': user_id})
        if not user:
            await query.answer("❌ Please /start the bot first to create an account!", show_alert=True)
            return

        # Bot ka token/coin system idhar handle hota hai
        user_balance = user.get('balance', 0) 
        
        # 3. Check Balance
        if user_balance < price:
            await query.answer(f"❌ Funds kam hain! Price {price:,} hai par aapke paas sirf {user_balance:,} tokens hain.", show_alert=True)
            return
            
        # 4. Deduct Money and Add Character
        await user_collection.update_one(
            {'id': user_id},
            {
                '$inc': {'balance': -price},
                '$push': {'characters': char}
            }
        )
        
        await query.answer(f"✅ Transaction Successful! {char['name']} is now yours.", show_alert=True)
        
        # 5. Update UI so no one else clicks buy
        await query.edit_message_caption(
            caption=f"🎉 <b>{char['name']}</b> has been SOLD to {query.from_user.first_name} for <b>{price:,} Tokens</b>!",
            parse_mode='HTML'
        )


# --- Handlers Register ---
# /mp aur /marketplace ek hi function kholenge
application.add_handler(CommandHandler(['mp', 'marketplace'], marketplace))
application.add_handler(CommandHandler('setprice', set_mp_price))
application.add_handler(CallbackQueryHandler(marketplace_callbacks, pattern="^mp_"))

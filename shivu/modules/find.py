import random
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from shivu import application, db

# --- Database Setup ---
collection = db['anime_characters_lol'] 
user_collection = db['users'] 

# OWNER ID
OWNER_ID = 7657218453

# --- Default Prices ---
DEFAULT_PRICES = {
    "🟢 Common": 10000, "🔵 Rare": 20000, "🟠 Medium": 30000, 
    "🟡 Legendary": 50000, "🪽 Celestial": 75000, "🥵 Spicy": 100000, 
    "🥴 Seductive": 125000, "💎 Mythic": 150000, "🔮 Premium Edition": 200000, 
    "🍭 Sweet": 250000, "💋 Erotic": 300000, "❄️ Winter": 350000, 
    "⚡ Neon": 400000, "🐚 Summer": 450000, "🌌 Manga": 500000
}

def get_price(char):
    if 'mp_price' in char and char['mp_price'] is not None:
        return char['mp_price']
    rarity = char.get('rarity', 'Unknown')
    return DEFAULT_PRICES.get(rarity, 50000) 

def get_current_mp_day():
    """4 AM IST ke hisaab se aaj ka din calculate karta hai"""
    IST = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(IST)
    if now.hour < 4:
        # Raat ke 4 baje se pehle, pichle din me count hoga
        return (now - timedelta(days=1)).strftime('%Y-%m-%d')
    return now.strftime('%Y-%m-%d')


# --- Set Price Command (Fixed) ---
async def set_mp_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Only Owner can use this command.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /setprice <char_id> <price>\nExample: /setprice 7742 15000")
        return
        
    char_id = context.args[0]
    try:
        price = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Price numbers mein hona chahiye.")
        return
        
    # DB me ID string ya integer kuch bhi ho sakti hai, dono try karenge
    result = await collection.update_one({'id': char_id}, {'$set': {'mp_price': price}})
    if result.modified_count == 0 and char_id.isdigit():
        result = await collection.update_one({'id': int(char_id)}, {'$set': {'mp_price': price}})
        
    if result.modified_count > 0:
        await update.message.reply_text(f"✅ Character ID {char_id} ka marketplace price {price:,} set ho gaya hai.")
    else:
        await update.message.reply_text("❌ Character ID nahi mila, ya price already same hai.")


# --- Generate/Load User Deals ---
async def load_user_deals(user_id):
    user = await user_collection.find_one({'user_id': user_id})
    if not user:
        return None
        
    current_day = get_current_mp_day()
    mp_data = user.get('mp_data', {})
    
    # Agar aaj ka deal nahi bana hai ya fresh start chahiye
    if mp_data.get('day') != current_day or not mp_data.get('chars'):
        pipeline = [{"$sample": {"size": 2}}] # Roz ke sirf 2 character
        chars = await collection.aggregate(pipeline).to_list(length=2)
        
        formatted_chars = []
        for c in chars:
            orig = get_price(c)
            disc = random.randint(2, 15)
            sale = int(orig - (orig * (disc / 100)))
            c['mp_orig'] = orig
            c['mp_disc'] = disc
            c['mp_sale'] = sale
            c['mp_status'] = "🛒 AVAILABLE"
            formatted_chars.append(c)
            
        mp_data = {'day': current_day, 'chars': formatted_chars}
        await user_collection.update_one({'user_id': user_id}, {'$set': {'mp_data': mp_data}})
        user['mp_data'] = mp_data
        
    return user


# --- UI Renderer (Screenshot jaisa exact format) ---
async def render_mp_message(update_obj, user, index, is_edit=False):
    chars = user['mp_data']['chars']
    if index >= len(chars): index = 0
    
    char = chars[index]
    
    # Owned count check
    owned_count = len([c for c in user.get('characters', []) if str(c.get('id')) == str(char.get('id'))])
    
    name = str(char.get('name', 'Unknown')).upper()
    anime = str(char.get('anime', 'Unknown')).upper()
    char_id = char.get('id', 'N/A')
    rarity = str(char.get('rarity', 'Unknown')).upper()
    
    caption = f"""🏪 <b>DAILY DEALS</b> ({index+1}/2)

🎭 <b>NAME:</b> {name}
📺 <b>SERIES:</b> {anime}
🆔 <b>ID:</b> {char_id}
💫 <b>RARITY:</b> {rarity}
💰 <b>ORIGINAL:</b> {char['mp_orig']:,}
🏷️ <b>SALE PRICE:</b> {char['mp_sale']:,}
📊 <b>DISCOUNT:</b> {char['mp_disc']}%
📋 <b>STATUS:</b> {char['mp_status']}
🔴 <b>OWNED:</b> {owned_count}"""

    buttons = [
        [
            InlineKeyboardButton("⬅️", callback_data=f"mp_nav_0"),
            InlineKeyboardButton("Buy", callback_data=f"mp_buy_{index}"),
            InlineKeyboardButton("➡️", callback_data=f"mp_nav_1")
        ],
        [InlineKeyboardButton("🍃 Auction", callback_data="mp_auction")],
        [InlineKeyboardButton("Refresh (30,000 💰)", callback_data="mp_refresh")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    img_url = char.get('img_url')

    if is_edit:
        if update_obj.message.photo and img_url:
            await update_obj.edit_message_media(
                media=InputMediaPhoto(media=img_url, caption=caption, parse_mode='HTML'),
                reply_markup=reply_markup
            )
        else:
            await update_obj.edit_message_caption(caption=caption, reply_markup=reply_markup, parse_mode='HTML')
    else:
        if img_url:
            await update_obj.message.reply_photo(photo=img_url, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update_obj.message.reply_text(text=caption, reply_markup=reply_markup, parse_mode='HTML')


# --- Commands & Callbacks ---
async def marketplace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = await load_user_deals(user_id)
    if not user:
        await update.message.reply_text("❌ Please /start the bot first to create an account.")
        return
    await render_mp_message(update, user, 0, is_edit=False)


async def marketplace_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    # Sirf us user ko button click karne de jiska ye message hai
    user = await load_user_deals(user_id)
    if not user:
        await query.answer("❌ Account not found!", show_alert=True)
        return

    # Button: Navigation (⬅️ ➡️)
    if data.startswith("mp_nav_"):
        index = int(data.split("_")[2])
        await render_mp_message(query, user, index, is_edit=True)
        await query.answer()
        return

    # Button: Buy Character
    if data.startswith("mp_buy_"):
        index = int(data.split("_")[2])
        chars = user['mp_data']['chars']
        char = chars[index]
        
        if char['mp_status'] == "❌ SOLD":
            await query.answer("❌ Ye character tum already khareed chuke ho!", show_alert=True)
            return
            
        user_balance = user.get('balance', 0)
        price = char['mp_sale']
        
        if user_balance < price:
            await query.answer(f"❌ Balance kam hai! (Required: {price:,} 💰 | Yours: {user_balance:,} 💰)", show_alert=True)
            return
            
        # Deduct coins, add char, update status
        char['mp_status'] = "❌ SOLD"
        await user_collection.update_one(
            {'user_id': user_id},
            {
                '$inc': {'balance': -price},
                '$push': {'characters': char},
                '$set': {'mp_data': user['mp_data']} # Local status update in DB
            }
        )
        
        await query.answer(f"✅ Transaction Successful! You bought {char.get('name')}.", show_alert=True)
        await render_mp_message(query, user, index, is_edit=True)
        return

    # Button: Auction
    if data == "mp_auction":
        await query.answer("🍃 Auction feature coming soon!", show_alert=True)
        return

    # Button: Paid Refresh
    if data == "mp_refresh":
        user_balance = user.get('balance', 0)
        cost = 30000
        
        if user_balance < cost:
            await query.answer(f"❌ Not enough coins to refresh! (Required: 30,000 💰)", show_alert=True)
            return
            
        # Deduct coins and force a new day refresh
        await user_collection.update_one(
            {'user_id': user_id},
            {
                '$inc': {'balance': -cost},
                '$set': {'mp_data.day': "FORCE_REFRESH"} # Day change karenge taaki load_user_deals naye laye
            }
        )
        
        # Load deals again (yeha fresh 2 chars aayenge)
        new_user = await load_user_deals(user_id)
        await render_mp_message(query, new_user, 0, is_edit=True)
        await query.answer("🔄 Marketplace successfully refreshed!", show_alert=False)


# Handlers Register
application.add_handler(CommandHandler(['mp', 'marketplace'], marketplace))
application.add_handler(CommandHandler('setprice', set_mp_price))
application.add_handler(CallbackQueryHandler(marketplace_callbacks, pattern="^mp_"))

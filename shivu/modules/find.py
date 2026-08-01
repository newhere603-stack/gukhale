import random
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from shivu import application, db, user_collection

# --- Character Database ---
collection = db['anime_characters_lol'] 
OWNER_ID = 7657218453

DEFAULT_PRICES = {
    "🟢 Common": 10000, "🔵 Rare": 20000, "🟠 Medium": 30000, 
    "🟡 Legendary": 50000, "🪽 Celestial": 75000, "🥵 Spicy": 100000, 
    "🥴 Seductive": 125000, "💎 Mythic": 150000, "🔮 Premium Edition": 200000, 
    "🍭 Sweet": 250000, "💋 Erotic": 300000, "❄️ Winter": 350000, 
    "⚡ Neon": 400000, "🐚 Summer": 450000, "🌌 Manga": 500000
}

# --- Formatting Functions ---
def to_small_caps(text: str) -> str:
    mapping = {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 
        'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 
        'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 
        's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 
        'y': 'ʏ', 'z': 'ᴢ', 'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 
        'E': 'ᴇ', 'F': 'ꜰ', 'G': 'ɢ', 'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 
        'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ', 
        'Q': 'ǫ', 'R': 'ʀ', 'S': 'ꜱ', 'T': 'ᴛ', 'U': 'ᴜ', 'V': 'ᴠ', 
        'W': 'ᴡ', 'X': 'x', 'Y': 'ʏ', 'Z': 'ᴢ', '0': '0', '1': '1',
        '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7',
        '8': '8', '9': '9'
    }
    return "".join(mapping.get(c, c) for c in str(text))

def bold_sc(text: str) -> str:
    return f"<b>{to_small_caps(text)}</b>"

def get_price(char):
    if 'mp_price' in char and char['mp_price'] is not None:
        return char['mp_price']
    rarity = char.get('rarity', 'Unknown')
    return DEFAULT_PRICES.get(rarity, 50000) 

def get_current_mp_day():
    IST = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(IST)
    if now.hour < 4:
        return (now - timedelta(days=1)).strftime('%Y-%m-%d')
    return now.strftime('%Y-%m-%d')


# --- Set Price Command ---
async def set_mp_price(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text(bold_sc("❌ Only Owner can use this command."), parse_mode='HTML')
        return
    
    if len(context.args) != 2:
        msg = "Usage: /setprice <char_id> <price>\nExample: /setprice 7742 15000"
        await update.message.reply_text(f"<blockquote>{bold_sc(msg)}</blockquote>", parse_mode='HTML')
        return
        
    char_id = context.args[0]
    try:
        price = int(context.args[1])
    except ValueError:
        await update.message.reply_text(bold_sc("❌ Price numbers mein hona chahiye."), parse_mode='HTML')
        return
        
    result = await collection.update_one({'id': char_id}, {'$set': {'mp_price': price}})
    if result.modified_count == 0 and char_id.isdigit():
        result = await collection.update_one({'id': int(char_id)}, {'$set': {'mp_price': price}})
        
    if result.modified_count > 0:
        await update.message.reply_text(bold_sc(f"✅ Character ID {char_id} ka marketplace price {price:,} set ho gaya hai."), parse_mode='HTML')
    else:
        await update.message.reply_text(bold_sc("❌ Character ID nahi mila, ya price already same hai."), parse_mode='HTML')


# --- Generate/Load User Deals ---
async def load_user_deals(user_id):
    user = await user_collection.find_one({'id': user_id})
    if not user:
        return None
        
    current_day = get_current_mp_day()
    mp_data = user.get('mp_data', {})
    
    # Check if we need to generate new characters for today
    if mp_data.get('day') != current_day or not mp_data.get('chars'):
        pipeline = [{"$sample": {"size": 2}}] 
        chars = await collection.aggregate(pipeline).to_list(length=2)
        
        formatted_chars = []
        for c in chars:
            orig = get_price(c)
            disc = random.randint(2, 15)
            sale = int(orig - (orig * (disc / 100)))
            c['mp_orig'] = orig
            c['mp_disc'] = disc
            c['mp_sale'] = sale
            c['mp_status'] = f"🛒 {to_small_caps('AVAILABLE')}"
            formatted_chars.append(c)
            
        mp_data = {'day': current_day, 'chars': formatted_chars}
        # Save to DB so it stays the same all day
        await user_collection.update_one({'id': user_id}, {'$set': {'mp_data': mp_data}})
        user['mp_data'] = mp_data
        
    return user


# --- UI Renderer ---
async def render_mp_message(update_obj, user, index, is_edit=False):
    chars = user['mp_data']['chars']
    if index >= len(chars): index = 0
    
    char = chars[index]
    owned_count = len([c for c in user.get('characters', []) if str(c.get('id')) == str(char.get('id'))])
    
    name = str(char.get('name', 'Unknown')).upper()
    anime = str(char.get('anime', 'Unknown')).upper()
    char_id = char.get('id', 'N/A')
    rarity = str(char.get('rarity', 'Unknown'))
    
    caption = f"""🏪 {bold_sc(f'DAILY DEALS ({index+1}/2)')}

🎭 {bold_sc('NAME:')} {bold_sc(name)}
📺 {bold_sc('SERIES:')} {bold_sc(anime)}
🆔 {bold_sc('ID:')} {bold_sc(str(char_id))}
💫 {bold_sc('RARITY:')} {bold_sc(rarity)}
💰 {bold_sc('ORIGINAL:')} {bold_sc(f"{char['mp_orig']:,}")}
🏷️ {bold_sc('SALE PRICE:')} {bold_sc(f"{char['mp_sale']:,}")}
📊 {bold_sc('DISCOUNT:')} {bold_sc(f"{char['mp_disc']}%")}
📋 {bold_sc('STATUS:')} <b>{char['mp_status']}</b>
🔴 {bold_sc('OWNED:')} {bold_sc(str(owned_count))}"""

    # Pagination logic (Toggle between 0 and 1)
    nav_index = 1 if index == 0 else 0

    buttons = [
        [
            InlineKeyboardButton("⬅️", callback_data=f"mp_nav_{nav_index}"),
            InlineKeyboardButton(to_small_caps("Buy"), callback_data=f"mp_buy_{index}"),
            InlineKeyboardButton("➡️", callback_data=f"mp_nav_{nav_index}")
        ],
        [InlineKeyboardButton(f"🍃 {to_small_caps('Auction')}", callback_data="mp_auction")],
        [InlineKeyboardButton(to_small_caps("Refresh (30,000 💰)"), callback_data="mp_refresh")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    img_url = char.get('img_url')

    try:
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
    except Exception as e:
        # Ignore message not modified errors safely
        pass


# --- Commands & Callbacks ---
async def marketplace(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user = await load_user_deals(user_id)
    
    if not user:
        await update.message.reply_text(bold_sc("❌ Please /start the bot first to create an account."), parse_mode='HTML')
        return
        
    await render_mp_message(update, user, 0, is_edit=False)


async def marketplace_callbacks(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    user = await load_user_deals(user_id)
    if not user:
        await query.answer(to_small_caps("❌ Account not found!"), show_alert=True)
        return

    # Navigation (Back/Next)
    if data.startswith("mp_nav_"):
        index = int(data.split("_")[2])
        await render_mp_message(query, user, index, is_edit=True)
        await query.answer()
        return

    # Buy Character
    if data.startswith("mp_buy_"):
        index = int(data.split("_")[2])
        chars = user['mp_data']['chars']
        char = chars[index]
        
        sold_text = f"❌ {to_small_caps('SOLD')}"
        if char['mp_status'] == sold_text:
            await query.answer(to_small_caps("❌ Ye character tum already khareed chuke ho!"), show_alert=True)
            return
            
        user_balance = user.get('balance', 0)
        price = char['mp_sale']
        
        if user_balance < price:
            await query.answer(to_small_caps(f"❌ Balance kam hai! (Required: {price:,} | Yours: {user_balance:,})"), show_alert=True)
            return
            
        # Update character status in user's saved array
        char['mp_status'] = sold_text
        
        await user_collection.update_one(
            {'id': user_id},
            {
                '$inc': {'balance': -price},
                '$push': {'characters': char},
                '$set': {'mp_data': user['mp_data']} 
            }
        )
        
        await query.answer(to_small_caps(f"✅ Transaction Successful! You bought {char.get('name')}."), show_alert=True)
        await render_mp_message(query, user, index, is_edit=True)
        return

    # Auction Button
    if data == "mp_auction":
        await query.answer(to_small_caps("🍃 Auction feature coming soon!"), show_alert=True)
        return

    # Refresh Deals
    if data == "mp_refresh":
        user_balance = user.get('balance', 0)
        cost = 30000
        
        if user_balance < cost:
            await query.answer(to_small_caps("❌ Not enough coins to refresh! (Required: 30,000)"), show_alert=True)
            return
            
        await user_collection.update_one(
            {'id': user_id},
            {
                '$inc': {'balance': -cost},
                '$set': {'mp_data.day': "FORCE_REFRESH"} 
            }
        )
        
        new_user = await load_user_deals(user_id)
        await render_mp_message(query, new_user, 0, is_edit=True)
        await query.answer(to_small_caps("🔄 Marketplace successfully refreshed!"), show_alert=False)


# Handlers Register
application.add_handler(CommandHandler(['mp', 'marketplace'], marketplace, block=False))
application.add_handler(CommandHandler('setprice', set_mp_price, block=False))
application.add_handler(CallbackQueryHandler(marketplace_callbacks, pattern="^mp_", block=False))

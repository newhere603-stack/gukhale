import asyncio
import html
import uuid
import re
from datetime import datetime, timedelta
from bson import ObjectId
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, filters, TypeHandler
from shivu import application, db

# 🔥 NAYA IMPORT: Dual Database Sync Ke Liye
from shivu.Database.db import eco_collection

# --- CONFIGURATION ---
LOG_GROUP_ID = -1003893927065
BUY_LOG_GROUP_ID = -1003757326893  # 🔥 NAYA LOG GROUP SIRF BUY TOKENS/COINS KE LIYE
OWNER_ID = 7657218453

# --- DATABASE COLLECTIONS ---
user_collection = db['user_collection_lmaoooo'] # Character Harem DB
market_collection = db['market_collection'] 
bot_settings_collection = db['bot_settings'] 

# --- HELPER: GET INDIAN STANDARD TIME (IST) ---
def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# --- HELPER: SEND LOGS TO LOG GROUP ---
async def send_market_log(context: CallbackContext, action: str, details: str):
    ist_now = get_ist_now()
    log_msg = (
        f"<b>⚡️ PMARKET ʟᴏɢs | {action}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{details}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 <i>{ist_now.strftime('%Y-%m-%d %I:%M:%S %p')} IST</i>"
    )
    try:
        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_msg, parse_mode='HTML')
    except Exception as e:
        pass

# 🔥 HELPER: SEND BUY LOGS TO THE NEW GROUP STEP-BY-STEP
async def send_buy_log(context: CallbackContext, action: str, user, details: str):
    ist_now = get_ist_now()
    user_mention = f"<a href='tg://user?id={user.id}'>{html.escape(user.first_name)}</a> (<code>{user.id}</code>)"
    log_msg = (
        f"<b>💳 ʙᴜʏ ʟᴏɢ | {action}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Usᴇʀ:</b> {user_mention}\n"
        f"{details}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 <i>{ist_now.strftime('%Y-%m-%d %I:%M:%S %p')} IST</i>"
    )
    try:
        await context.bot.send_message(chat_id=BUY_LOG_GROUP_ID, text=log_msg, parse_mode='HTML')
    except Exception as e:
        pass

# --- HELPER: GET DAILY LIMIT INFO ---
async def get_token_limit_info(user_id):
    settings = await bot_settings_collection.find_one({'_id': 'pmarket_settings'})
    global_limit = settings.get('daily_token_limit', 70) if settings else 70

    user = await eco_collection.find_one({'id': user_id})
    if not user:
        return global_limit, 0, ""

    today_str = get_ist_now().strftime('%Y-%m-%d')
    last_date = user.get('last_token_exchange_date', '')
    used_today = user.get('daily_token_limit_used', 0)

    if last_date != today_str:
        used_today = 0 

    return global_limit, used_today, today_str

# --- HELPER TO GET LIVE CHARACTER (PARALLEL & FAST) ---
async def get_live_character_doc(char_id):
    if char_id is None:
        return None
    query = {'$or': [{'id': char_id}, {'id': str(char_id)}, {'id': int(char_id) if str(char_id).isdigit() else None}]}
    tasks = [
        db['anime_characters_lol'].find_one(query),
        db['characters'].find_one(query),
        db['collection'].find_one(query)
    ]
    results = await asyncio.gather(*tasks)
    for res in results:
        if res: return res
    return None

# --- CONVERSATION STATES ---
WAITING_FOR_CHARACTER_ID, WAITING_FOR_PRICE = 1, 2
WAITING_FOR_EXCHANGE_AMOUNT = 3
WAITING_FOR_BUY_PRODUCT = 4
WAITING_FOR_BUY_AMOUNT = 5
WAITING_FOR_BUY_SCREENSHOT = 6

# --- SMALL CAPS CONVERTER HELPERS ---
SMALL_CAPS_TRANS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
)
def to_small_caps(text: str) -> str:
    return str(text).translate(SMALL_CAPS_TRANS) if text else ""

# --- RARITIES & PRICES ---
RARITIES = {
    "common": ("🟢", '<tg-emoji emoji-id="6093722470265658964">🟢</tg-emoji>', "Common"), 
    "rare": ("🟠", '<tg-emoji emoji-id="5339390195768774311">🟠</tg-emoji>', "Rare"), 
    "legendary": ("🟡", '<tg-emoji emoji-id="6084550327086883643">🔥</tg-emoji>', "Legendary"),
    "special": ("🔵", '<tg-emoji emoji-id="5393592081748877575">🔵</tg-emoji>', "Medium"), 
    "celestial": ("🪽", '<tg-emoji emoji-id="5434121252874756456">🕊</tg-emoji>', "Celestial"), 
    "erotic": ("🥵", '<tg-emoji emoji-id="6093490292923574796">❤️‍🔥</tg-emoji>', "Spicy"),
    "exclusive": ("💮", '<tg-emoji emoji-id="5262772355779809182">💮</tg-emoji>', "Exclusive"), 
    "cosmic": ("🌌", '<tg-emoji emoji-id="5431783411981228752">🎆</tg-emoji>', "Cosmic"), 
    "mythic": ("💎", '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>', "Mythic"),
    "sweet": ("🍭", '<tg-emoji emoji-id="6222115531122546353">🍭</tg-emoji>', "Sweet"), 
    "valentine": ("💞", '<tg-emoji emoji-id="5255861796350224063">❤️</tg-emoji>', "Valentine"), 
    "winter": ("❄️", '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>', "Winter"),
    "neon": ("⚡", '<tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>', "Neon"), 
    "pearl": ("🏝️", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"), 
    "premium": ("🔮", '<tg-emoji emoji-id="6093919703753831564">🔮</tg-emoji>', "Premium Edition"), 
}

# Real money me sell hone wale characters ke Coin prices
CHAR_PRICES_COINS = {
    "common": 1000, "rare": 3200, "special": 2900, "legendary": 5000, 
    "celestial": 70000, "erotic": 59000, "exclusive": 12000, "mythic": 180000, 
    "premium": 250000, "sweet": 52000, "valentine": 90000, "winter": 55000, 
    "neon": 67000, "pearl": 60000, "cosmic": 640000
}

def chunk(items: list, size: int) -> list:
    return [items[i:i + size] for i in range(0, len(items), size)]

async def update_menu(query, text, keyboard):
    if query.message.photo or query.message.video:
        await query.message.delete()
        await query.message.reply_html(text, reply_markup=keyboard)
    else:
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')

async def get_pmarket_keyboard(user_id, bot_username=""):
    settings = await bot_settings_collection.find_one({'_id': 'pmarket_settings'})
    exchange_enabled = settings.get('exchange_enabled', True) if settings else True
    
    keyboard = []
    if exchange_enabled: keyboard.append([InlineKeyboardButton("♻️ ᴇxᴄʜᴀɴɢᴇ", callback_data=f"pm_exc_menu:{user_id}")])
    keyboard.append([
        InlineKeyboardButton("🛒 ʙᴜʏ", callback_data=f"pm_b:{user_id}"),
        InlineKeyboardButton("💸 sᴇʟʟ", callback_data=f"pm_sm:{user_id}")
    ])
    if bot_username:
        keyboard.append([InlineKeyboardButton("💳 ʙᴜʏ ᴛᴏᴋᴇɴs/ᴄᴏɪɴs", url=f"https://t.me/{bot_username}?start=buy_tokens")])
    return InlineKeyboardMarkup(keyboard)

# ========================
# MAIN COMMANDS
# ========================
async def pmarket_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    keyboard = await get_pmarket_keyboard(user_id, context.bot.username)
    await update.message.reply_text(
        "<b><tg-emoji emoji-id=\"5278702045883292456\">🛍</tg-emoji> P2P ᴍᴀʀᴋᴇᴛᴘʟᴀᴄᴇ</b>\n\n<i>ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ.</i>",
        reply_markup=keyboard, parse_mode='HTML'
    )

async def toggle_exchange_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: return
    settings = await bot_settings_collection.find_one({'_id': 'pmarket_settings'})
    new_state = not (settings.get('exchange_enabled', True) if settings else True)
    await bot_settings_collection.update_one({'_id': 'pmarket_settings'}, {'$set': {'exchange_enabled': new_state}}, upsert=True)
    await update.message.reply_html(f"<b>PMarket exchange button ab {'ENABLED ✅' if new_state else 'DISABLED ❌'} ho gaya hai.</b>")

async def set_exchange_limit_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return
        
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_html("⚠️ <b>Iɴᴠᴀʟɪᴅ ғᴏʀᴍᴀᴛ.</b>\nUsaɢᴇ: <code>/set_exchange_limit <amount></code>")
        return
        
    new_limit = int(context.args[0])
    
    await bot_settings_collection.update_one(
        {'_id': 'pmarket_settings'}, 
        {'$set': {'daily_token_limit': new_limit}}, 
        upsert=True
    )
    
    await update.message.reply_html(f"✅ <b>Dᴀɪʟʏ ᴇxᴄʜᴀɴɢᴇ ʟɪᴍɪᴛ ʜᴀs ʙᴇᴇɴ ᴜᴘᴅᴀᴛᴇᴅ ᴛᴏ <code>{new_limit}</code> ᴛᴏᴋᴇɴs!</b>")

async def force_delist_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: return
    if not context.args: return await update.message.reply_html("⚠️ <b>Invalid format.</b>\nUsage: <code>/forcedelist <char_id></code>")
    char_id = context.args[0]
    listings = await market_collection.find({'$or': [{'character.id': char_id}, {'character.id': int(char_id) if char_id.isdigit() else char_id}]}).to_list(length=None)
    
    if not listings: return await update.message.reply_html(f"⚠️ <b>Character ID <code>{char_id}</code> ka koi listing nahi mila bhai.</b>")
    tasks, market_ids, count = [], [], 0
    for item in listings:
        seller_id, char = item['seller_id'], item['character']
        market_ids.append(item['_id'])
        tasks.append(user_collection.update_one({'id': seller_id}, {'$push': {'characters': char}}))
        tasks.append(send_market_log(context, "📉 FORCE DELISTED", f"👤 <b>Seller:</b> <a href='tg://user?id={seller_id}'>{seller_id}</a>\n🎭 <b>Character:</b> {char.get('name')} (<code>{char.get('id')}</code>)"))
        count += 1
    await asyncio.gather(*tasks)
    await market_collection.delete_many({'_id': {'$in': market_ids}})
    await update.message.reply_html(f"✅ <b>Done! <code>{count}</code> listings remove kardi hai ID <code>{char_id}</code> ki.</b>")


# ========================
# RARITY TOGGLE COMMANDS
# ========================
async def mrarity_on(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: return
    if not context.args: return await update.message.reply_html("<b>⚠️ Rarity ka naam bhi to de bhai. Example: <code>/mrarity_on common</code></b>")
    rarity = context.args[0].lower()
    if rarity not in CHAR_PRICES_COINS: return await update.message.reply_html("<b>⚠️ Ye konsi rarity hai be? Valid rarity daal.</b>")
    await bot_settings_collection.update_one({'_id': 'market_rarity_settings'}, {'$set': {f'enabled.{rarity}': True}}, upsert=True)
    await update.message.reply_html(f"<b>✅ Done bhai! <code>{rarity}</code> rarity ab buy menu me ON ho gayi hai.</b>")

async def mrarity_off(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: return
    if not context.args: return await update.message.reply_html("<b>⚠️ Rarity ka naam daal bhai. Example: <code>/mrarity_off common</code></b>")
    rarity = context.args[0].lower()
    if rarity not in CHAR_PRICES_COINS: return await update.message.reply_html("<b>⚠️ Valid rarity daal bhai.</b>")
    await bot_settings_collection.update_one({'_id': 'market_rarity_settings'}, {'$set': {f'enabled.{rarity}': False}}, upsert=True)
    await update.message.reply_html(f"<b>❌ Done! <code>{rarity}</code> rarity ab buy menu se OFF ho gayi hai.</b>")


# ========================
# BUY TOKENS & COINS MENU
# ========================
async def buy_command_pm(update: Update, context: CallbackContext):
    if update.effective_chat.type != "private":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Buy Here", url=f"https://t.me/{context.bot.username}?start=buy_tokens")]])
        await update.message.reply_html("<b>Bhai yaha group me allow nahi hai, direct mere PM me aake buy karlo 👇</b>", reply_markup=kb)
        return ConversationHandler.END
    return await start_buy_menu(update, context)

async def start_buy_menu(update: Update, context: CallbackContext):
    order_id = uuid.uuid4().hex[:8]
    context.user_data['buy_order_id'] = order_id

    await send_buy_log(context, "🚀 STARTED", update.effective_user, f"🆔 <b>Order ID:</b> <code>{order_id}</code>\n💬 <b>Action:</b> Initiated Buy Menu")

    text = (
        f"<b>✅ Session Created! (ID: <code>{order_id}</code>)</b>\n\n"
        f"<b>Kya buy karna hai bhai? Niche se select karlo:</b>"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🪙 Tokens", callback_data="buy_prod_tokens"), InlineKeyboardButton("💰 Coins", callback_data="buy_prod_coins")],
        [InlineKeyboardButton("🎭 Characters", callback_data="buy_prod_chars")],
        [InlineKeyboardButton("❌ Cancel", callback_data="buy_cancel")]
    ])

    if update.message: await update.message.reply_html(text, reply_markup=keyboard)
    elif update.callback_query: await update.callback_query.message.reply_html(text, reply_markup=keyboard)
    return WAITING_FOR_BUY_PRODUCT

async def buy_product_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    
    if query.data == "buy_prod_chars":
        # Check konsi rarity on hai
        settings = await bot_settings_collection.find_one({'_id': 'market_rarity_settings'})
        enabled_dict = settings.get('enabled', {}) if settings else {}
        
        buttons = []
        for r_key in CHAR_PRICES_COINS.keys():
            if enabled_dict.get(r_key, True): # Default ON 
                r_name = RARITIES.get(r_key, ("","","Unknown"))[2]
                buttons.append(InlineKeyboardButton(f"{r_name}", callback_data=f"buy_char:{r_key}"))
        
        if not buttons:
            await query.answer("⚠️ Filhal koi bhi character market me available nahi hai bhai!", show_alert=True)
            return WAITING_FOR_BUY_PRODUCT
            
        kb = chunk(buttons, 2)
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="buy_back_main")])
        await query.message.edit_text("<b>Konsi Rarity ka character buy karna hai bhai? Niche se select karo 👇</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
        return WAITING_FOR_BUY_PRODUCT

    if query.data == "buy_back_main":
        return await start_buy_menu(update, context)

    # Prevent double tapping
    if context.user_data.get('buy_amount_prompt_active'):
        await query.answer("⚠️ Pehle pura process complete kar ya /cancel likh!", show_alert=True)
        return WAITING_FOR_BUY_AMOUNT
        
    await query.answer()
    context.user_data['buy_amount_prompt_active'] = True
    context.user_data['buy_product'] = query.data 

    order_id = context.user_data.get('buy_order_id', 'UNKNOWN')
    
    if query.data == "buy_prod_tokens":
        text = "<b>Kitne TOKENS buy karne hain bhai? (Min: 10, Max: 1000)</b>\n<i>Rate: 10 Tokens = 5 INR</i>"
    elif query.data == "buy_prod_coins":
        text = "<b>Kitne COINS buy karne hain bhai? (Min: 50,000, Max: 2,500,000)</b>\n<i>Rate: 5000 Coins = 1 INR</i>"
    elif query.data.startswith("buy_char:"):
        r_key = query.data.split(":")[1]
        r_name = RARITIES.get(r_key, ("","","Unknown"))[2]
        c_price = CHAR_PRICES_COINS[r_key]
        text = f"<b>Kitne {r_name} Characters buy karne hain bhai? (Max 100)</b>\n<i>1 {r_name} = {c_price} Coins ki value me milega</i>"

    await send_buy_log(context, "📦 SELECTED", query.from_user, f"🆔 <b>Order ID:</b> <code>{order_id}</code>\n💬 <b>Product:</b> <code>{query.data}</code>")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="buy_cancel")]])
    await query.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    return WAITING_FOR_BUY_AMOUNT

async def ask_buy_amount(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0: return WAITING_FOR_BUY_AMOUNT
    
    amount = int(text)
    prod = context.user_data.get('buy_product')
    
    if prod == 'buy_prod_tokens':
        if amount < 10 or amount > 1000:
            await update.message.reply_html("<b>⚠️ Amount 10 se 1000 ke beech mein hona chahiye bhai.</b>")
            return WAITING_FOR_BUY_AMOUNT
        price_inr = (amount / 10) * 5
        disp_txt = f"{amount} Tokens"
        
    elif prod == 'buy_prod_coins':
        if amount < 50000 or amount > 2500000:
            await update.message.reply_html("<b>⚠️ Bhai Coins kam se kam 50,000 aur maximum 25 Lakh buy kar sakte ho.</b>")
            return WAITING_FOR_BUY_AMOUNT
        price_inr = amount / 5000
        disp_txt = f"{amount:,} Coins"
        
    elif prod.startswith('buy_char:'):
        rarity_key = prod.split(':')[1]
        if amount < 1 or amount > 100:
            await update.message.reply_html("<b>⚠️ Ek baar mein 1 se 100 characters tak hi buy kar sakte ho bhai.</b>")
            return WAITING_FOR_BUY_AMOUNT
        coin_price = CHAR_PRICES_COINS[rarity_key]
        price_inr = (amount * coin_price) / 5000
        r_name = RARITIES.get(rarity_key, ("","","Unknown"))[2]
        disp_txt = f"{amount} x {r_name} Characters"

    order_id = context.user_data.get('buy_order_id', 'UNKNOWN')
    context.user_data['buy_amount'] = amount
    context.user_data['buy_price'] = price_inr

    await send_buy_log(context, "🪙 AMOUNT ENTERED", update.message.from_user, f"🆔 <b>Order ID:</b> <code>{order_id}</code>\n🪙 <b>Items:</b> {disp_txt}\n💸 <b>Price:</b> {price_inr:g} INR")

    caption = (
        f"<b>✅ Order Set Ho Gaya Hai!</b>\n"
        f"<b>Order ID:</b> <code>{order_id}</code>\n\n"
        f"<b>Item:</b> {disp_txt}\n"
        f"<b>Total Price:</b> <b>{price_inr:g} INR</b>\n\n"
        f"<b>Is UPI par payment kar aur screenshot bhej:</b>\n<b>UPI ID:</b> <code>sasuke72@ptyes</code>\n\n"
        f"<b>⚠️ Payment ka sahi screenshot niche send kar de confirm karne ke liye.</b>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="buy_cancel")]])

    await context.bot.send_photo(
        chat_id=update.message.chat_id,
        photo="https://files.catbox.moe/0qjgih.png",
        caption=caption, reply_markup=kb, parse_mode='HTML'
    )
    return WAITING_FOR_BUY_SCREENSHOT

async def receive_buy_screenshot(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if not update.message.photo: return WAITING_FOR_BUY_SCREENSHOT

    photo_id = update.message.photo[-1].file_id
    order_id = context.user_data.get('buy_order_id', 'UNKNOWN')
    amount = context.user_data.get('buy_amount', 0)
    price_inr = context.user_data.get('buy_price', 0)
    prod = context.user_data.get('buy_product', '')

    admin_text = (
        f"<b>🛒 ɴᴇᴡ ᴘᴜʀᴄʜᴀsᴇ ʀᴇǫᴜᴇsᴛ</b>\n"
        f"<b>👤 ᴜsᴇʀ:</b> <a href='tg://user?id={user_id}'>{html.escape(update.message.from_user.first_name)}</a> (<code>{user_id}</code>)\n"
        f"<b>🆔 ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n"
        f"<b>📦 ᴘʀᴏᴅᴜᴄᴛ:</b> <code>{prod}</code>\n"
        f"<b>🪙 ǫᴛʏ:</b> <code>{amount}</code>\n"
        f"<b>💸 ᴘᴀʏᴀʙʟᴇ:</b> <b>{price_inr:g} ɪɴʀ</b>"
    )
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ᴄᴏɴғɪʀᴍ", callback_data=f"bcnf:{user_id}:{amount}:{prod}:{order_id}")],
        [InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data=f"bcan:{user_id}:{order_id}")]
    ])
    
    await context.bot.send_photo(chat_id=BUY_LOG_GROUP_ID, photo=photo_id, caption=admin_text, reply_markup=kb, parse_mode='HTML')
    await update.message.reply_html("<b>✅ Bhai tera payment screenshot admin ke paas chala gaya hai. Thodi der wait kar, verify hote hi item mil jayega.</b>")

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_buy_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    if query.message.photo: await query.message.edit_caption("<b>❌ Bhai process cancel kar diya gaya hai.</b>", parse_mode='HTML')
    else: await query.message.edit_text("<b>❌ Bhai process cancel kar diya gaya hai.</b>", parse_mode='HTML')
        
    await send_buy_log(context, "❌ CANCELLED", query.from_user, "User cancelled the process")
    context.user_data.clear()
    return ConversationHandler.END

async def admin_buy_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    if query.from_user.id != OWNER_ID: return await query.answer("⚠️ Chacha, ye sirf owner ke liye hai!", show_alert=True)

    data = query.data.split(':')
    action = data[0]
    target_user_id = int(data[1])
    
    if action == "bcan":
        order_id = data[-1]
        await query.edit_message_caption(caption=f"{query.message.caption_html}\n\n<b>❌ ʀᴇᴊᴇᴄᴛᴇᴅ ʙʏ ᴀᴅᴍɪɴ</b>", parse_mode='HTML')
        try:
            await context.bot.send_message(chat_id=target_user_id, text=f"<b>❌ Bhai tera payment reject ho gaya hai Order ID <code>{order_id}</code> ke liye. Agar galti se hua hai to support pe message kar de.</b>", parse_mode='HTML')
        except Exception: pass
        return

    if action == "bcnf":
        amount = int(data[2])
        prod = data[3]
        if len(data) > 5: # safety for format
             prod = data[3] + ":" + data[4]
             order_id = data[5]
        else:
             order_id = data[4]
             
        today_str = get_ist_now().strftime('%Y-%m-%d')
        msg_out = ""

        if prod == "buy_prod_tokens":
            await eco_collection.update_one({'id': target_user_id}, {'$inc': {'tokens': amount}}, upsert=True)
            msg_out = f"<code>{amount}</code> ᴛᴏᴋᴇɴs"
        
        elif prod == "buy_prod_coins":
            await eco_collection.update_one({'id': target_user_id}, {'$inc': {'balance': amount}}, upsert=True)
            msg_out = f"<code>{amount:,}</code> ᴄᴏɪɴs"

        elif prod.startswith("buy_char:"):
            rarity_key = prod.split(":")[1]
            r_name = RARITIES.get(rarity_key, ("","","Unknown"))[2]
            
            # Fast Pipeline to get random characters
            pipeline = [{'$match': {'rarity': r_name}}, {'$sample': {'size': amount}}]
            chars = await db['characters'].aggregate(pipeline).to_list(length=amount)
            if not chars or len(chars) < amount:
                fallback_chars = await db['anime_characters_lol'].aggregate(pipeline).to_list(length=amount - len(chars))
                chars.extend(fallback_chars)
                
            if chars:
                await user_collection.update_one({'id': target_user_id}, {'$push': {'characters': {'$each': chars}}})
            msg_out = f"<code>{len(chars)}</code> <b>{r_name}</b> Characters"

        await query.edit_message_caption(caption=f"{query.message.caption_html}\n\n<b>✅ ᴄᴏɴғɪʀᴍᴇᴅ & ᴅᴇʟɪᴠᴇʀᴇᴅ</b>", parse_mode='HTML')

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"<b>🎉 Congrats Bhai! Payment confirm ho gaya hai.</b>\n\n<b>{msg_out} tere account me add kar diye gaye hain. Maze kar!</b>\n\n<b>Order ID:</b> <code>{order_id}</code>",
                parse_mode='HTML'
            )
        except Exception: pass

# ========================
# MARKET CALLBACKS
# ========================
async def pmarket_callbacks(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    parts = data.split(':')
    user_id = query.from_user.id
    
    owner_id = int(parts[-1])
    if user_id != owner_id:
        await query.answer("⚠️ Apna khud ka menu khol bhai, dusro ka mat chhu!", show_alert=True)
        return

    action = parts[0]

    if action == "pm_b":
        buttons = [InlineKeyboardButton(f"{db_emoji} {to_small_caps(name)}", callback_data=f"pm_r:{key}:{user_id}") for key, (db_emoji, _, name) in RARITIES.items()]
        keyboard = chunk(buttons, 2)
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_m:{user_id}")])
        await update_menu(query, "<b><tg-emoji emoji-id=\"5312361253610475399\">🛒</tg-emoji> ʙᴜʏ ᴄʜᴀʀᴀᴄᴛᴇʀs ғʀᴏᴍ ᴍᴀʀᴋᴇᴛ</b>\n\n<i>sᴇʟᴇᴄᴛ ᴀ ʀᴀʀɪᴛʏ ᴛᴏ ᴠɪᴇᴡ ᴘʀᴏᴅᴜᴄᴛs.</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_m":
        keyboard = await get_pmarket_keyboard(user_id, context.bot.username)
        await update_menu(query, "<b><tg-emoji emoji-id=\"5278702045883292456\">🛍</tg-emoji> P2P ᴍᴀʀᴋᴇᴛᴘʟᴀᴄᴇ</b>\n\n<i>ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ.</i>", keyboard)

    elif action == "pm_exc_menu":
        global_limit, used_today, _ = await get_token_limit_info(user_id)
        limit_text = f"♾️" if user_id == OWNER_ID else f"{global_limit - used_today} ʟᴇғᴛ ᴛᴏᴅᴀʏ"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("ɢᴇᴛ ᴄᴏɪɴs", callback_data=f"pm_start_exc_t2c:{user_id}"), InlineKeyboardButton("ɢᴇᴛ ᴛᴏᴋᴇɴ", callback_data=f"pm_start_exc_c2t:{user_id}")],
            [InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_m:{user_id}")]
        ])
        await update_menu(query, f"<b>💱 ᴇxᴄʜᴀɴɢᴇ ᴍᴇɴᴜ</b>\n\n<i>Dᴀɪʟʏ Lɪᴍɪᴛ: {limit_text}</i>\n<i>ᴡʜᴀᴛ ᴡᴏᴜʟᴅ ʏᴏᴜ ʟɪᴋᴇ ᴛᴏ ᴅᴏ?</i>", keyboard)

    elif action == "pm_r":
        rarity_key = parts[1]
        db_emoji, prem_emoji, name = RARITIES.get(rarity_key, RARITIES["common"])
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("ᴘʀɪᴄᴇ ʟᴏᴡ ᴛᴏ ʜɪɢʜ", callback_data=f"pm_s:{rarity_key}:asc:{user_id}")],
            [InlineKeyboardButton("ᴘʀɪᴄᴇ ʜɪɢʜ ᴛᴏ ʟᴏᴡ", callback_data=f"pm_s:{rarity_key}:desc:{user_id}")],
            [InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_b:{user_id}")]
        ])
        await update_menu(query, f"<b>{prem_emoji} {to_small_caps(name)} ᴄʜᴀʀᴀᴄᴛᴇʀs</b>\n\n<i>ʜᴏᴡ ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ sᴏʀᴛ ᴛʜᴇᴍ?</i>", keyboard)

    elif action == "pm_s":
        rarity_key, order = parts[1], parts[2]
        sort_order = 1 if order == "asc" else -1
        db_emoji, prem_emoji, name = RARITIES.get(rarity_key, RARITIES["common"])
        
        search_terms = [name, rarity_key]
        if rarity_key == "premium": search_terms.extend(["Premium Edition", "Premium"])
        regex_pattern = "|".join([re.escape(term) for term in search_terms])
        
        market_items = await market_collection.find({'character.rarity': {'$regex': regex_pattern, '$options': 'i'}}).sort('price', sort_order).limit(10).to_list(length=10)

        if not market_items: return await query.answer("Nahi mila bhai koi character is rarity me market pe!", show_alert=True)

        keyboard = [[InlineKeyboardButton(f"{db_emoji} {to_small_caps(item['character'].get('name', 'Unknown'))} - 💸 {item['price']:,}", callback_data=f"pm_v:{str(item['_id'])}:{user_id}")] for item in market_items]
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_r:{rarity_key}:{user_id}")])
        await update_menu(query, f"<b>{prem_emoji} ᴄʜᴀʀᴀᴄᴛᴇʀs ғᴏʀ sᴀʟᴇ</b>\n\n<i>sᴏʀᴛᴇᴅ ʙʏ ᴘʀɪᴄᴇ</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_v":
        item = await market_collection.find_one({'_id': ObjectId(parts[1])})
        if not item: return await query.answer("Bhai ye bik gaya ya delete ho gaya market se!", show_alert=True)

        char = item['character']
        display_char = await get_live_character_doc(char.get('id')) or char
        
        prem_emoji, name = '<tg-emoji emoji-id="6093722470265658964">🟢</tg-emoji>', str(display_char.get('rarity', 'Common'))
        for k, (d_emoji, p_emoji, r_name) in RARITIES.items():
            if r_name.lower() in name.lower() or k.lower() in name.lower():
                prem_emoji, name = p_emoji, r_name
                break

        caption = (
            f"<b>{prem_emoji} {to_small_caps(display_char.get('name', 'Unknown'))}</b>\n\n"
            f"<b><tg-emoji emoji-id=\"6312254267461739671\">⛩</tg-emoji> ᴀɴɪᴍᴇ:</b> {to_small_caps(display_char.get('anime', 'Unknown'))}\n"
            f"<b><tg-emoji emoji-id=\"5260426225599405269\">🪄</tg-emoji> ʀᴀʀɪᴛʏ:</b> {prem_emoji} {to_small_caps(name)}\n"
            f"<b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> ᴘʀɪᴄᴇ:</b> <code>{item['price']:,}</code>\n"
            f"<b><tg-emoji emoji-id=\"6332443074769196273\">🆔</tg-emoji> sᴇʟʟᴇʀ:</b> <code>{item['seller_id']}</code>"
        )
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 ʙᴜʏ ɴᴏᴡ", callback_data=f"pm_buy:{parts[1]}:{user_id}")], [InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_b:{user_id}")]])

        await query.message.delete()
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=display_char.get('img_url', 'https://files.catbox.moe/0qjgih.png'), caption=caption, reply_markup=keyboard, parse_mode='HTML')

    elif action == "pm_buy":
        item = await market_collection.find_one({'_id': ObjectId(parts[1])})
        if not item: return await query.answer("Nahi mila bhai koi character is rarity me market pe!", show_alert=True)
        if item['seller_id'] == user_id: return await query.answer("Bhai apna character khud nahi kharid sakta tu!", show_alert=True)

        eco_buyer = await eco_collection.find_one_and_update({'id': user_id, 'balance': {'$gte': item['price']}}, {'$inc': {'balance': -item['price']}})
        if not eco_buyer: return await query.answer(f"Balance low hai bhai! Tere paas 💸 {item['price']:,} coins hone chahiye.", show_alert=True)

        if not await market_collection.find_one_and_delete({'_id': ObjectId(parts[1])}):
            await eco_collection.update_one({'id': user_id}, {'$inc': {'balance': item['price']}})
            return await query.answer("Oof! Kisi aur ne pehle hi kharid liya bhai ye character.", show_alert=True)

        await asyncio.gather(
            user_collection.update_one({'id': user_id}, {'$push': {'characters': item['character']}}),
            eco_collection.update_one({'id': item['seller_id']}, {'$inc': {'balance': item['price']}})
        )
        await send_market_log(context, "🛒 CHARACTER SOLD", f"👤 <b>Buyer:</b> <a href='tg://user?id={user_id}'>{user_id}</a>\n🏪 <b>Seller:</b> <a href='tg://user?id={item['seller_id']}'>{item['seller_id']}</a>\n💰 <b>Price:</b> {item['price']:,} coins")
        await query.message.edit_caption(caption=f"<b>🎉 Congo! Tune successfully {to_small_caps(item['character'].get('name'))} buy kar liya <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {item['price']:,} coins de kar.</b>", parse_mode='HTML')

    elif action == "pm_sm":
        listings = await market_collection.find({'seller_id': user_id}).limit(50).to_list(length=50)
        keyboard = [[InlineKeyboardButton("➕ ʟɪsᴛ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ", callback_data=f"pm_start_s:{user_id}")]]
        for item in listings: keyboard.append([InlineKeyboardButton(f"ᴄᴀɴᴄᴇʟ | {to_small_caps(item['character'].get('name', 'Unknown'))} - 💸 {item['price']:,}", callback_data=f"pm_delist:{str(item['_id'])}:{user_id}")])
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_m:{user_id}")])
        await update_menu(query, "<b>💸 ʏᴏᴜʀ ᴀᴄᴛɪᴠᴇ ʟɪsᴛɪɴɢs</b>\n\n<i>ᴍᴀɴᴀɢᴇ ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ʟɪsᴛɪɴɢs ᴏʀ ᴀᴅᴅ ᴀ ɴᴇᴡ ᴏɴᴇ.</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_delist":
        item = await market_collection.find_one({'_id': ObjectId(parts[1])})
        if item:
            await asyncio.gather(user_collection.update_one({'id': user_id}, {'$push': {'characters': item['character']}}), market_collection.delete_one({'_id': ObjectId(parts[1])}))
            await query.answer(f"✅ Delete ho gaya aur character tere inventory me wapas aa gaya!", show_alert=True)
        listings = await market_collection.find({'seller_id': user_id}).limit(50).to_list(length=50)
        keyboard = [[InlineKeyboardButton("➕ ʟɪsᴛ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ", callback_data=f"pm_start_s:{user_id}")]]
        for item in listings: keyboard.append([InlineKeyboardButton(f"ᴄᴀɴᴄᴇʟ | {to_small_caps(item['character'].get('name', 'Unknown'))} - 💸 {item['price']:,}", callback_data=f"pm_delist:{str(item['_id'])}:{user_id}")])
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_m:{user_id}")])
        await update_menu(query, "<b>ʏᴏᴜʀ ᴀᴄᴛɪᴠᴇ ʟɪsᴛɪɴɢs</b>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_exc_conf":
        exc_type, amount = parts[1], int(parts[2]) 
        global_limit, used_today, today_str = await get_token_limit_info(user_id)
        if user_id != OWNER_ID and amount + used_today > global_limit:
            return await query.answer(f"⚠️ Daily limit reach ho gayi bhai! Sirf {max(0, global_limit - used_today)} aur exchange kar sakta hai.", show_alert=True)

        if exc_type == "t2c":
            if not await eco_collection.find_one_and_update({'id': user_id, 'tokens': {'$gte': amount}}, {'$inc': {'tokens': -amount, 'balance': amount * 2500}}):
                return await query.answer("⚠️ Bhai tokens khatam ho gaye tere paas!", show_alert=True)
            msg = f"<b>✅ Successfully exchanged <code>{amount}</code> tokens into <code>{amount * 2500:,}</code> coins!</b>"

        elif exc_type == "c2t":
            if not await eco_collection.find_one_and_update({'id': user_id, 'balance': {'$gte': amount * 2500}}, {'$inc': {'balance': -(amount * 2500), 'tokens': amount}}):
                return await query.answer("⚠️ Coins nahi bache tere paas itne bhai!", show_alert=True)
            msg = f"<b>✅ Successfully spent <code>{amount * 2500:,}</code> coins to buy <code>{amount}</code> tokens!</b>"

        if user_id != OWNER_ID:
            user_fresh = await eco_collection.find_one({'id': user_id})
            if user_fresh.get('last_token_exchange_date', '') != today_str: await eco_collection.update_one({'id': user_id}, {'$set': {'daily_token_limit_used': amount, 'last_token_exchange_date': today_str}})
            else: await eco_collection.update_one({'id': user_id}, {'$inc': {'daily_token_limit_used': amount}})

        await update_menu(query, msg, InlineKeyboardMarkup([[InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_exc_menu:{user_id}")]]))

# ========================
# CANCEL AND TIMEOUT METHODS
# ========================
async def cancel_process(update: Update, context: CallbackContext):
    context.user_data.clear()
    await update.message.reply_html("<b>❌ Bhai process cancel kar diya maine.</b>")
    return ConversationHandler.END

async def timeout_process(update: Update, context: CallbackContext):
    context.user_data.clear()
    msg = "<b>⌛ Bhai bohot time laga raha hai tu, timeout ho gaya. Dubara try kar.</b>"
    if update.message: await update.message.reply_html(msg)
    elif update.callback_query: await update.callback_query.message.reply_html(msg)
    return ConversationHandler.END

# --- 1. SELL CONVERSATION ---
async def sell_start(update: Update, context: CallbackContext):
    query = update.callback_query
    owner_id = int(query.data.split(':')[-1])
    if query.from_user.id != owner_id: return await query.answer("⚠️ Tera menu nahi hai ye!", show_alert=True)
    if context.user_data.get('sell_owner_id'): return await query.answer("⚠️ Pehle wala complete kar ya /cancel likh!", show_alert=True)
    await query.answer()
    context.user_data['sell_owner_id'] = owner_id
    await query.message.reply_html("💸 <b>Character ID daal jise sell karna hai:</b>\n\n(Cancel karne ke liye /cancel type kar de)")
    return WAITING_FOR_CHARACTER_ID

async def ask_character_id(update: Update, context: CallbackContext):
    if not update.message.text: return WAITING_FOR_CHARACTER_ID
    user_id = update.message.from_user.id
    if context.user_data.get('sell_owner_id') != user_id: return WAITING_FOR_CHARACTER_ID
    user_data = await user_collection.find_one({'id': user_id})
    character = next((c for c in user_data.get('characters', []) if str(c.get('id')) == update.message.text.strip()), None) if user_data else None
    
    if not character: return WAITING_FOR_CHARACTER_ID
    context.user_data['sell_character'] = character
    await update.message.reply_html(f"✅ <b>Mil gaya! Ab iski price bata.</b>\n\nSelected: <b>{to_small_caps(character.get('name'))}</b>\n<i>Coins daal jaldi (in <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>).</i>")
    return WAITING_FOR_PRICE

async def ask_price(update: Update, context: CallbackContext):
    if not update.message.text or not update.message.text.isdigit(): return WAITING_FOR_PRICE
    user_id = update.message.from_user.id
    if context.user_data.get('sell_owner_id') != user_id: return WAITING_FOR_PRICE
    price = int(update.message.text.strip())
    
    if price > 1000000: return await update.message.reply_html("<b>⚠️ Bhai max 1,000,000 coins set kar sakta hai!</b>") or WAITING_FOR_PRICE
    character = context.user_data.get('sell_character')
    if not character: return await update.message.reply_html("<b>Timeout ho gaya. Dubara /pmarket kar.</b>") or ConversationHandler.END

    live_char = await get_live_character_doc(character['id']) or character
    user_doc = await user_collection.find_one({'id': user_id})
    if user_doc:
        chars_list = user_doc.get('characters', [])
        for i, c in enumerate(chars_list):
            if str(c.get('id')) == str(character['id']):
                del chars_list[i]
                break
        await user_collection.update_one({'id': user_id}, {'$set': {'characters': chars_list}})

    await market_collection.insert_one({'seller_id': user_id, 'price': price, 'character': live_char})
    context.user_data.clear()
    await update.message.reply_html(f"<b>🎉 Done! Tera {to_small_caps(live_char.get('name'))} market me aa gaya hai <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {price:,} coins me!</b>")
    return ConversationHandler.END

# --- 2. EXCHANGE CONVERSATION ---
async def exchange_start_t2c(update: Update, context: CallbackContext):
    query = update.callback_query
    if query.from_user.id != int(query.data.split(':')[-1]): return await query.answer("⚠️ Tera menu nahi hai!", show_alert=True)
    if context.user_data.get('exc_owner_id'): return await query.answer("⚠️ Pura kar ya /cancel likh!", show_alert=True)
    await query.answer()
    context.user_data.update({'exc_owner_id': query.from_user.id, 'exc_type': 't2c'})
    user = await eco_collection.find_one({'id': query.from_user.id})
    await query.message.reply_html(f"<b>💱 Kitne tokens ke coins banane hain bhai?</b>\n<i>1 Token = 2,500 Coins.</i>\n<b>Tere paas:</b> <code>{user.get('tokens', 0) if user else 0:,}</code> Tokens")
    return WAITING_FOR_EXCHANGE_AMOUNT

async def exchange_start_c2t(update: Update, context: CallbackContext):
    query = update.callback_query
    if query.from_user.id != int(query.data.split(':')[-1]): return await query.answer("⚠️ Tera menu nahi hai!", show_alert=True)
    if context.user_data.get('exc_owner_id'): return await query.answer("⚠️ Pura kar ya /cancel likh!", show_alert=True)
    await query.answer()
    context.user_data.update({'exc_owner_id': query.from_user.id, 'exc_type': 'c2t'})
    user = await eco_collection.find_one({'id': query.from_user.id})
    await query.message.reply_html(f"<b>💱 Kitne tokens lene hain coins de ke?</b>\n<i>2,500 Coins = 1 Token.</i>\n<b>Tere paas:</b> <code>{user.get('balance', 0) if user else 0:,}</code> Coins")
    return WAITING_FOR_EXCHANGE_AMOUNT

async def ask_exchange_amount(update: Update, context: CallbackContext):
    if not update.message.text or not update.message.text.isdigit(): return WAITING_FOR_EXCHANGE_AMOUNT
    user_id = update.message.from_user.id
    if context.user_data.get('exc_owner_id') != user_id: return WAITING_FOR_EXCHANGE_AMOUNT

    amount, exc_type = int(update.message.text.strip()), context.user_data.get('exc_type')
    global_limit, used_today, _ = await get_token_limit_info(user_id)
    if user_id != OWNER_ID and amount + used_today > global_limit:
        return await update.message.reply_html(f"⚠️ <b>Daily Limit Cross ho rahi bhai!</b>\nSirf <code>{max(0, global_limit - used_today)}</code> tokens aur exchange kar sakta hai aaj.") or WAITING_FOR_EXCHANGE_AMOUNT

    user = await eco_collection.find_one({'id': user_id})
    tokens, coins = user.get('tokens', 0) if user else 0, user.get('balance', 0) if user else 0
    
    if exc_type == 't2c':
        if amount > tokens: return await update.message.reply_html(f"<b>Kam Tokens hain bhai, bas <code>{tokens:,}</code> hain.</b>") or WAITING_FOR_EXCHANGE_AMOUNT
        text_msg = f"<i>Kya tu sure hai tu <code>{amount}</code> tokens udana chahta hai <code>{amount * 2500:,}</code> coins lene ke liye?</i>"
    else:
        if amount * 2500 > coins: return await update.message.reply_html(f"<b>Coins kam pad rahe hain! Tere paas <code>{coins:,}</code> coins hain aur chahiye <code>{amount * 2500:,}</code></b>") or WAITING_FOR_EXCHANGE_AMOUNT
        text_msg = f"<i>Kya tu sure hai <code>{amount * 2500:,}</code> coins udane hain <code>{amount}</code> tokens ke liye?</i>"
        
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Yes Confirm", callback_data=f"pm_exc_conf:{exc_type}:{amount}:{user_id}")], [InlineKeyboardButton("Cancel", callback_data=f"pm_exc_menu:{user_id}")]])
    await update.message.reply_html(f"<b>Confirm Exchange</b>\n\n{text_msg}", reply_markup=kb)
    context.user_data.clear()
    return ConversationHandler.END


# ========================
# REGISTER HANDLERS
# ========================
sell_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(sell_start, pattern=r"^pm_start_s:")],
    states={
        WAITING_FOR_CHARACTER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_character_id)],
        WAITING_FOR_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_price)],
        ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_process)]
    },
    fallbacks=[CommandHandler("cancel", cancel_process)],
    conversation_timeout=60, allow_reentry=True, per_user=True, per_chat=True,
)

exchange_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(exchange_start_t2c, pattern=r"^pm_start_exc_t2c:"), CallbackQueryHandler(exchange_start_c2t, pattern=r"^pm_start_exc_c2t:")],
    states={
        WAITING_FOR_EXCHANGE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_exchange_amount)],
        ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_process)]
    },
    fallbacks=[CommandHandler("cancel", cancel_process)],
    conversation_timeout=60, allow_reentry=True, per_user=True, per_chat=True,
)

buy_conv = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex(r'^/start buy_tokens$'), start_buy_menu),
        CommandHandler("buy", buy_command_pm)
    ],
    states={
        WAITING_FOR_BUY_PRODUCT: [
            CallbackQueryHandler(buy_product_callback, pattern='^(buy_prod_tokens|buy_prod_coins|buy_prod_chars|buy_char:.*|buy_cancel|buy_back_main)$'),
        ],
        WAITING_FOR_BUY_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, ask_buy_amount),
            CallbackQueryHandler(cancel_buy_callback, pattern='^buy_cancel$')
        ],
        WAITING_FOR_BUY_SCREENSHOT: [
            MessageHandler(filters.PHOTO, receive_buy_screenshot),
            CallbackQueryHandler(cancel_buy_callback, pattern='^buy_cancel$')
        ],
        ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_process)]
    },
    fallbacks=[CommandHandler("cancel", cancel_process)],
    conversation_timeout=120, allow_reentry=True, per_user=True, per_chat=True,
)

application.add_handler(sell_conv, group=-1)
application.add_handler(exchange_conv, group=-2)
application.add_handler(buy_conv, group=-3) 

application.add_handler(CommandHandler(["pmarket", "shop"], pmarket_command, block=False), group=0)
application.add_handler(CommandHandler("toggle_exchange", toggle_exchange_cmd, block=False), group=0)
application.add_handler(CommandHandler("set_exchange_limit", set_exchange_limit_cmd, block=False), group=0)
application.add_handler(CommandHandler("forcedelist", force_delist_cmd, block=False), group=0)

# RARITY COMMANDS
application.add_handler(CommandHandler("mrarity_on", mrarity_on, block=False), group=0)
application.add_handler(CommandHandler("mrarity_off", mrarity_off, block=False), group=0)

application.add_handler(CallbackQueryHandler(pmarket_callbacks, pattern='^(pm_m|pm_b|pm_r|pm_s|pm_v|pm_buy|pm_sm|pm_delist|pm_exc_conf|pm_exc_menu):', block=False), group=0)

# Global Callback handler for admin confirm/cancel
application.add_handler(CallbackQueryHandler(admin_buy_callback, pattern='^(bcnf|bcan):', block=False), group=0)

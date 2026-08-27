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
        if res:
            return res
    return None

# --- CONVERSATION STATES ---
WAITING_FOR_CHARACTER_ID, WAITING_FOR_PRICE = 1, 2
WAITING_FOR_EXCHANGE_AMOUNT = 3
WAITING_FOR_BUY_PRODUCT = 4
WAITING_FOR_BUY_CHAR_ID = 5
WAITING_FOR_BUY_AMOUNT = 6
WAITING_FOR_BUY_SCREENSHOT = 7

# --- SMALL CAPS CONVERTER HELPERS ---
SMALL_CAPS_TRANS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
)

def to_small_caps(text: str) -> str:
    if not text:
        return ""
    return str(text).translate(SMALL_CAPS_TRANS)

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

CHAR_PRICES_COINS = {
    "common": 1000, "rare": 3200, "medium": 2900, "legendary": 5000, 
    "celestial": 70000, "spicy": 59000, "exclusive": 12000, "mythic": 180000, 
    "premium edition": 250000, "sweet": 52000, "valentine": 90000, "winter": 55000, 
    "neon": 67000, "summer": 60000, "cosmic": 640000
}

def get_normalized_rarity(rarity_str):
    if not rarity_str: return "common"
    r = rarity_str.lower().strip()
    if "premium" in r: return "premium edition"
    if "spicy" in r or "erotic" in r: return "spicy"
    if "medium" in r or "special" in r: return "medium"
    if "summer" in r or "pearl" in r: return "summer"
    return r

def chunk(items: list, size: int) -> list:
    return [items[i:i + size] for i in range(0, len(items), size)]

async def update_menu(query, text, keyboard):
    if query.message.photo or query.message.video:
        await query.message.delete()
        await query.message.reply_html(text, reply_markup=keyboard)
    else:
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')

# --- PMARKET KEYBOARD GENERATOR HELPER ---
async def get_pmarket_keyboard(user_id, bot_username=""):
    settings = await bot_settings_collection.find_one({'_id': 'pmarket_settings'})
    exchange_enabled = settings.get('exchange_enabled', True) if settings else True
    
    keyboard = []
    if exchange_enabled:
        keyboard.append([InlineKeyboardButton("♻️ ᴇxᴄʜᴀɴɢᴇ", callback_data=f"pm_exc_menu:{user_id}")])
    
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
    bot_username = context.bot.username
    keyboard = await get_pmarket_keyboard(user_id, bot_username)
    
    await update.message.reply_text(
        "<b><tg-emoji emoji-id=\"5278702045883292456\">🛍</tg-emoji> P2P ᴍᴀʀᴋᴇᴛᴘʟᴀᴄᴇ</b>\n\n"
        "<i>ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ.</i>",
        reply_markup=keyboard,
        parse_mode='HTML'
    )

async def toggle_exchange_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: return
    settings = await bot_settings_collection.find_one({'_id': 'pmarket_settings'})
    new_state = not (settings.get('exchange_enabled', True) if settings else True)
    await bot_settings_collection.update_one({'_id': 'pmarket_settings'}, {'$set': {'exchange_enabled': new_state}}, upsert=True)
    await update.message.reply_html(f"<b>PMarket ᴇxᴄʜᴀɴɢᴇ ʙᴜᴛᴛᴏɴ ʜᴀs ʙᴇᴇɴ {'ᴇɴᴀʙʟᴇᴅ ✅' if new_state else 'ᴅɪsᴀʙʟᴇᴅ ❌'}.</b>")

async def set_exchange_limit_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: return
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("⚠️ <b>Iɴᴠᴀʟɪᴅ ғᴏʀᴍᴀᴛ.</b>\nUsaɢᴇ: <code>/set_exchange_limit <amount></code>", parse_mode="HTML")
    new_limit = int(context.args[0])
    await bot_settings_collection.update_one({'_id': 'pmarket_settings'}, {'$set': {'daily_token_limit': new_limit}}, upsert=True)
    await update.message.reply_html(f"✅ <b>Dᴀɪʟʏ ᴇxᴄʜᴀɴɢᴇ ʟɪᴍɪᴛ ʜᴀs ʙᴇᴇɴ ᴜᴘᴅᴀᴛᴇᴅ ᴛᴏ <code>{new_limit}</code> ᴛᴏᴋᴇɴs!</b>")

async def force_delist_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: return
    if not context.args:
        return await update.message.reply_text("⚠️ <b>Iɴᴠᴀʟɪᴅ ғᴏʀᴍᴀᴛ.</b>\nUsaɢᴇ: <code>/forcedelist <character_id></code>", parse_mode="HTML")
        
    char_id = context.args[0]
    query = {'$or': [{'character.id': char_id}, {'character.id': int(char_id) if char_id.isdigit() else char_id}]}
    listings = await market_collection.find(query).to_list(length=None)
    
    if not listings: return await update.message.reply_html(f"⚠️ <b>Nᴏ ᴀᴄᴛɪᴠᴇ ʟɪsᴛɪɴɢs ғᴏᴜɴᴅ ғᴏʀ ᴄʜᴀʀᴀᴄᴛᴇʀ ID <code>{char_id}</code> ᴏɴ ᴛʜᴇ ᴍᴀʀᴋᴇᴛ.</b>")
    
    tasks, market_ids, count = [], [], 0
    for item in listings:
        seller_id, char = item['seller_id'], item['character']
        market_ids.append(item['_id'])
        tasks.append(user_collection.update_one({'id': seller_id}, {'$push': {'characters': char}}))
        count += 1
        seller_mention = f"<a href='tg://user?id={seller_id}'>{seller_id}</a>"
        log_details = (
            f"🛡️ <b>Aᴅᴍɪɴ Fᴏʀᴄᴇ Dᴇʟɪsᴛ</b>\n"
            f"👤 <b>Sᴇʟʟᴇʀ:</b> {seller_mention}\n"
            f"🎭 <b>Cʜᴀʀᴀᴄᴛᴇʀ:</b> {char.get('name')} (<code>{char.get('id')}</code>)\n"
            f"❌ <b>Aᴄᴛɪᴏɴ:</b> Rᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ ᴍᴀʀᴋᴇᴛ ʙʏ Bᴏᴛ Oᴡɴᴇʀ."
        )
        tasks.append(send_market_log(context, "📉 FORCE DELISTED", log_details))
    
    await asyncio.gather(*tasks)
    await market_collection.delete_many({'_id': {'$in': market_ids}})
    await update.message.reply_html(f"✅ <b>Sᴜᴄᴄᴇssғᴜʟʟʏ ʀᴇᴍᴏᴠᴇᴅ <code>{count}</code> ʟɪsᴛɪɴɢ(s) ғᴏʀ ᴄʜᴀʀᴀᴄᴛᴇʀ ID <code>{char_id}</code> ᴀɴᴅ ʀᴇᴛᴜʀɴᴇᴅ ᴛᴏ ᴛʜᴇɪʀ ᴏᴡɴᴇʀs.</b>")

# ========================
# RARITY TOGGLES COMMANDS
# ========================
async def mrarity_on_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: return
    if not context.args:
        return await update.message.reply_html("<b>⚠️ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ʀᴀʀɪᴛʏ ɴᴀᴍᴇ. ᴇxᴀᴍᴘʟᴇ: <code>/mrarity_on common</code></b>")
    r = " ".join(context.args).lower()
    if r not in CHAR_PRICES_COINS:
        return await update.message.reply_html("<b>⚠️ ɪɴᴠᴀʟɪᴅ ʀᴀʀɪᴛʏ!</b>")
    await bot_settings_collection.update_one({'_id': 'market_rarity_settings'}, {'$set': {f'enabled.{r}': True}}, upsert=True)
    await update.message.reply_html(f"<b>✅ {to_small_caps(r)} ʀᴀʀɪᴛʏ ɪs ɴᴏᴡ ᴇɴᴀʙʟᴇᴅ ғᴏʀ ᴘᴜʀᴄʜᴀsᴇ!</b>")

async def mrarity_off_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: return
    if not context.args:
        return await update.message.reply_html("<b>⚠️ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ʀᴀʀɪᴛʏ ɴᴀᴍᴇ. ᴇxᴀᴍᴘʟᴇ: <code>/mrarity_off common</code></b>")
    r = " ".join(context.args).lower()
    if r not in CHAR_PRICES_COINS:
        return await update.message.reply_html("<b>⚠️ ɪɴᴠᴀʟɪᴅ ʀᴀʀɪᴛʏ!</b>")
    await bot_settings_collection.update_one({'_id': 'market_rarity_settings'}, {'$set': {f'enabled.{r}': False}}, upsert=True)
    await update.message.reply_html(f"<b>❌ {to_small_caps(r)} ʀᴀʀɪᴛʏ ɪs ɴᴏᴡ ᴅɪsᴀʙʟᴇᴅ ғᴏʀ ᴘᴜʀᴄʜᴀsᴇ.</b>")

# ========================
# BUY TOKENS/COINS/CHARS MENU
# ========================
async def buy_command_pm(update: Update, context: CallbackContext):
    if update.effective_chat.type != "private":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 ʙᴜʏ ʜᴇʀᴇ", url=f"https://t.me/{context.bot.username}?start=buy_tokens")]])
        await update.message.reply_html("<b>⚠️ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴏɴʟʏ ᴡᴏʀᴋs ɪɴ ᴘᴍ (ᴘʀɪᴠᴀᴛᴇ ᴍᴇssᴀɢᴇs). ᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ᴛᴏ ʙᴜʏ.</b>", reply_markup=kb)
        return ConversationHandler.END
    return await start_buy_menu(update, context)

async def start_buy_menu(update: Update, context: CallbackContext):
    order_id = uuid.uuid4().hex[:8]
    context.user_data['buy_order_id'] = order_id

    await send_buy_log(context, "🚀 STARTED", update.effective_user, f"🆔 <b>ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n💬 <b>Aᴄᴛɪᴏɴ:</b> Iɴɪᴛɪᴀᴛᴇᴅ Bᴜʏ Mᴇɴᴜ")

    text = (
        f"<b>✅ ᴏʀᴅᴇʀ sᴇssɪᴏɴ ᴄʀᴇᴀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n"
        f"<b>ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n\n"
        f"<b>sᴇʟᴇᴄᴛ ᴛʜᴇ ᴘʀᴏᴅᴜᴄᴛ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʙᴜʏ:</b>"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("ᴛᴏᴋᴇɴs", callback_data="buy_prod_t"), InlineKeyboardButton("ᴄᴏɪɴs", callback_data="buy_prod_c")],
        [InlineKeyboardButton("ᴄʜᴀʀᴀᴄᴛᴇʀs", callback_data="buy_prod_char")],
        [InlineKeyboardButton("ᴄᴀɴᴄᴇʟ", callback_data="buy_cancel")]
    ])

    if update.message: await update.message.reply_html(text, reply_markup=keyboard)
    elif update.callback_query: await update.callback_query.message.reply_html(text, reply_markup=keyboard)
    return WAITING_FOR_BUY_PRODUCT

async def buy_product_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    
    if context.user_data.get('buy_prompt_active'):
        await query.answer("⚠️ ʏᴏᴜ ᴀʀᴇ ᴀʟʀᴇᴀᴅʏ ɪɴ ᴛʜᴇ ᴘʀᴏᴄᴇss! ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ʀᴇǫᴜɪʀᴇᴅ ɪɴғᴏ ᴏʀ ᴛʏᴘᴇ /cancel.", show_alert=True)
        # Determine the current state based on what they were asked
        if context.user_data.get('buy_product') == 'char' and not context.user_data.get('buy_char_id'):
            return WAITING_FOR_BUY_CHAR_ID
        return WAITING_FOR_BUY_AMOUNT
    
    await query.answer()
    context.user_data['buy_prompt_active'] = True
    context.user_data['buy_product'] = query.data.replace('buy_prod_', '')

    order_id = context.user_data.get('buy_order_id', 'UNKNOWN')
    
    if query.data == "buy_prod_t":
        text = "<b>sᴇɴᴅ ᴛʜᴇ ᴀᴍᴏᴜɴᴛ ᴏғ ᴛᴏᴋᴇɴs ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʙᴜʏ (ᴍɪɴ: 10, ᴍᴀx: 1000).</b>\n\n<b>ʀᴀᴛᴇ: 10 ᴛᴏᴋᴇɴs ғᴏʀ 5 ɪɴʀ.</b>"
        next_state = WAITING_FOR_BUY_AMOUNT
    elif query.data == "buy_prod_c":
        text = "<b>sᴇɴᴅ ᴛʜᴇ ᴀᴍᴏᴜɴᴛ ᴏғ ᴄᴏɪɴs ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʙᴜʏ (ᴍɪɴ: 50,000, ᴍᴀx: 2,500,000).</b>\n\n<b>ʀᴀᴛᴇ: 5,000 ᴄᴏɪɴs ғᴏʀ 1 ɪɴʀ.</b>"
        next_state = WAITING_FOR_BUY_AMOUNT
    elif query.data == "buy_prod_char":
        text = "<b>sᴇɴᴅ ᴛʜᴇ ᴄʜᴀʀᴀᴄᴛᴇʀ ɪᴅ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʙᴜʏ:</b>\n<i>(ᴛʜᴇ ʙᴏᴛ ᴡɪʟʟ ᴀᴜᴛᴏ-ᴅᴇᴛᴇᴄᴛ ɪᴛs ʀᴀʀɪᴛʏ ᴀɴᴅ ᴘʀɪᴄᴇ ɪᴛ ᴀᴄᴄᴏʀᴅɪɴɢʟʏ.)</i>"
        next_state = WAITING_FOR_BUY_CHAR_ID

    await send_buy_log(context, "📦 SELECTED", query.from_user, f"🆔 <b>ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n💬 <b>Aᴄᴛɪᴏɴ:</b> Sᴇʟᴇᴄᴛᴇᴅ <b>{query.data}</b>")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("ᴄᴀɴᴄᴇʟ", callback_data="buy_cancel")]])
    await query.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    return next_state

async def ask_buy_char_id(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    if not text: return WAITING_FOR_BUY_CHAR_ID

    live_char = await get_live_character_doc(text)
    if not live_char:
        await update.message.reply_html("<b>⚠️ ᴄʜᴀʀᴀᴄᴛᴇʀ ɴᴏᴛ ғᴏᴜɴᴅ! ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴀ ᴠᴀʟɪᴅ ᴄʜᴀʀᴀᴄᴛᴇʀ ɪᴅ.</b>")
        return WAITING_FOR_BUY_CHAR_ID

    r = get_normalized_rarity(live_char.get('rarity'))
    if r not in CHAR_PRICES_COINS:
        await update.message.reply_html(f"<b>⚠️ ᴛʜɪs ᴄʜᴀʀᴀᴄᴛᴇʀ's ʀᴀʀɪᴛʏ ({to_small_caps(live_char.get('rarity', 'Unknown'))}) ɪs ɴᴏᴛ sᴜᴘᴘᴏʀᴛᴇᴅ ғᴏʀ ᴘᴜʀᴄʜᴀsᴇ!</b>")
        return WAITING_FOR_BUY_CHAR_ID

    settings = await bot_settings_collection.find_one({'_id': 'market_rarity_settings'})
    enabled_dict = settings.get('enabled', {}) if settings else {}
    if not enabled_dict.get(r, True):
        await update.message.reply_html(f"<b>⚠️ ᴛʜᴇ ʀᴀʀɪᴛʏ ({to_small_caps(r)}) ɪs ᴄᴜʀʀᴇɴᴛʟʏ ᴅɪsᴀʙʟᴇᴅ ғᴏʀ ᴘᴜʀᴄʜᴀsᴇ!</b>")
        return WAITING_FOR_BUY_CHAR_ID

    context.user_data['buy_char_id'] = live_char['id']
    context.user_data['buy_char_name'] = live_char.get('name')
    context.user_data['buy_char_rarity'] = r

    coin_price = CHAR_PRICES_COINS[r]
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("ᴄᴀɴᴄᴇʟ", callback_data="buy_cancel")]])
    await update.message.reply_html(
        f"<b>✅ ᴄʜᴀʀᴀᴄᴛᴇʀ ғᴏᴜɴᴅ: {to_small_caps(live_char.get('name'))}</b>\n"
        f"<b>ʀᴀʀɪᴛʏ: {to_small_caps(r)} (Vᴀʟᴜᴇ: {coin_price:,} ᴄᴏɪɴs)</b>\n\n"
        f"<b>sᴇɴᴅ ᴛʜᴇ ǫᴜᴀɴᴛɪᴛʏ ᴏғ ᴛʜɪs ᴄʜᴀʀᴀᴄᴛᴇʀ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʙᴜʏ (ᴍɪɴ: 1, ᴍᴀx: 100).</b>",
        reply_markup=kb
    )
    return WAITING_FOR_BUY_AMOUNT

async def ask_buy_amount(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0: return WAITING_FOR_BUY_AMOUNT
    
    amount = int(text)
    prod = context.user_data.get('buy_product')
    
    if prod == 't':
        if amount < 10 or amount > 1000:
            await update.message.reply_html("<b>⚠️ ᴀᴍᴏᴜɴᴛ ᴍᴜsᴛ ʙᴇ ʙᴇᴛᴡᴇᴇɴ 10 ᴀɴᴅ 1000 ᴛᴏᴋᴇɴs.</b>")
            return WAITING_FOR_BUY_AMOUNT
        price_inr = (amount / 10) * 5
        disp_txt = f"{amount} ᴛᴏᴋᴇɴs"
        
    elif prod == 'c':
        if amount < 50000 or amount > 2500000:
            await update.message.reply_html("<b>⚠️ ᴀᴍᴏᴜɴᴛ ᴍᴜsᴛ ʙᴇ ʙᴇᴛᴡᴇᴇɴ 50,000 ᴀɴᴅ 2,500,000 ᴄᴏɪɴs.</b>")
            return WAITING_FOR_BUY_AMOUNT
        price_inr = amount / 5000
        disp_txt = f"{amount:,} ᴄᴏɪɴs"
        
    elif prod == 'char':
        if amount < 1 or amount > 100:
            await update.message.reply_html("<b>⚠️ ǫᴜᴀɴᴛɪᴛʏ ᴍᴜsᴛ ʙᴇ ʙᴇᴛᴡᴇᴇɴ 1 ᴀɴᴅ 100 ᴄᴏᴘɪᴇs.</b>")
            return WAITING_FOR_BUY_AMOUNT
        r = context.user_data['buy_char_rarity']
        coin_price = CHAR_PRICES_COINS[r]
        price_inr = (amount * coin_price) / 5000
        disp_txt = f"{amount}x {to_small_caps(context.user_data.get('buy_char_name'))}"

    order_id = context.user_data.get('buy_order_id', 'UNKNOWN')
    context.user_data['buy_amount'] = amount
    context.user_data['buy_price'] = price_inr

    await send_buy_log(context, "🪙 AMOUNT ENTERED", update.message.from_user, f"🆔 <b>ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n🪙 <b>Iᴛᴇᴍs:</b> {disp_txt}\n💸 <b>Pʀɪᴄᴇ:</b> {price_inr:.2f} INR")

    caption = (
        f"<b>✅ ᴏʀᴅᴇʀ ᴜᴘᴅᴀᴛᴇᴅ!</b>\n"
        f"<b>ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n\n"
        f"<b>Iᴛᴇᴍ(s):</b> {disp_txt}\n"
        f"<b>Tᴏᴛᴀʟ ᴘʀɪᴄᴇ: {price_inr:.2f} ɪɴʀ</b>\n\n"
        f"<b>ᴘᴀʏ ɪɴʀ ᴛᴏ ᴛʜᴇ ғᴏʟʟᴏᴡɪɴɢ ᴜᴘɪ ᴏʀ ǫʀ ɪɴ ᴛʜᴇ ɪᴍᴀɢᴇ:</b>\n<b>UPI</b> <code>sasuke72@ptyes</code>\n\n"
        f"<b>⚠️ ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ᴘᴀʏᴍᴇɴᴛ sᴄʀᴇᴇɴsʜᴏᴛ ʙᴇʟᴏᴡ ᴛᴏ ᴄᴏɴғɪʀᴍ ʏᴏᴜʀ ᴏʀᴅᴇʀ.</b>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("ᴄᴀɴᴄᴇʟ", callback_data="buy_cancel")]])

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
    
    # Store order safely in DB to bypass callback size limit
    order_doc = {
        '_id': f"buy_{order_id}",
        'user_id': user_id,
        'user_name': update.message.from_user.first_name,
        'prod': context.user_data.get('buy_product'),
        'amount': context.user_data.get('buy_amount'),
        'price_inr': context.user_data.get('buy_price'),
        'char_id': context.user_data.get('buy_char_id'),
        'char_name': context.user_data.get('buy_char_name'),
        'status': 'pending'
    }
    await bot_settings_collection.update_one({'_id': f"buy_{order_id}"}, {'$set': order_doc}, upsert=True)

    prod = context.user_data.get('buy_product')
    amount = context.user_data.get('buy_amount')
    price_inr = context.user_data.get('buy_price')
    
    disp_txt = f"<code>{amount}</code>"
    if prod == 't': disp_txt += " <b>ᴛᴏᴋᴇɴs</b>"
    elif prod == 'c': disp_txt += " <b>ᴄᴏɪɴs</b>"
    elif prod == 'char': disp_txt += f"x <b>{to_small_caps(context.user_data.get('buy_char_name'))}</b>"

    admin_text = (
        f"<b>🛒 ɴᴇᴡ ᴘᴜʀᴄʜᴀsᴇ ʀᴇǫᴜᴇsᴛ</b>\n"
        f"<b>👤 ᴜsᴇʀ:</b> <a href='tg://user?id={user_id}'>{html.escape(update.message.from_user.first_name)}</a> (<code>{user_id}</code>)\n"
        f"<b>🆔 ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n"
        f"<b>📦 ɪᴛᴇᴍ:</b> {disp_txt}\n"
        f"<b>💸 ᴘᴀʏᴀʙʟᴇ:</b> <b>{price_inr:.2f} ɪɴʀ</b>"
    )
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❮", callback_data=f"b_adj:-1:{order_id}"),
            InlineKeyboardButton(f"{amount:,}", callback_data="ignore"),
            InlineKeyboardButton("❯", callback_data=f"b_adj:+1:{order_id}")
        ],
        [InlineKeyboardButton("✅ ᴄᴏɴғɪʀᴍ", callback_data=f"b_cnf:{order_id}")],
        [InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data=f"b_can:{order_id}")]
    ])
    
    await context.bot.send_photo(chat_id=BUY_LOG_GROUP_ID, photo=photo_id, caption=admin_text, reply_markup=kb, parse_mode='HTML')
    await update.message.reply_html("<b>✅ ʏᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ sᴄʀᴇᴇɴsʜᴏᴛ ʜᴀs ʙᴇᴇɴ sᴇɴᴛ ᴛᴏ ᴛʜᴇ ᴀᴅᴍɪɴ. ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ғᴏʀ ᴄᴏɴғɪʀᴍᴀᴛɪᴏɴ. ɪᴛᴇᴍs ᴡɪʟʟ ʙᴇ ᴀᴅᴅᴇᴅ ᴛᴏ ʏᴏᴜʀ ᴡᴀʟʟᴇᴛ sʜᴏʀᴛʟʏ.</b>")

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_buy_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    if query.message.photo: await query.message.edit_caption("<b>❌ ᴏʀᴅᴇʀ ᴄᴀɴᴄᴇʟʟᴇᴅ.</b>", parse_mode='HTML')
    else: await query.message.edit_text("<b>❌ ᴏʀᴅᴇʀ ᴄᴀɴᴄᴇʟʟᴇᴅ.</b>", parse_mode='HTML')
        
    order_id = context.user_data.get('buy_order_id', 'UNKNOWN')
    await send_buy_log(context, "❌ CANCELLED", query.from_user, f"🆔 <b>ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n💬 <b>Aᴄᴛɪᴏɴ:</b> Usᴇʀ ᴄᴀɴᴄᴇʟʟᴇᴅ ᴛʜᴇ ᴘʀᴏᴄᴇss")
    context.user_data.clear()
    return ConversationHandler.END

async def admin_buy_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    if query.data == "ignore": return await query.answer()
    if query.from_user.id != OWNER_ID: return await query.answer("⚠️ ᴏɴʟʏ ᴏᴡɴᴇʀ ᴄᴀɴ ᴀᴘᴘʀᴏᴠᴇ ᴛʜɪs!", show_alert=True)

    data = query.data.split(':')
    action = data[0]
    order_id = data[-1]
    
    order = await bot_settings_collection.find_one({'_id': f"buy_{order_id}"})
    if not order: return await query.answer("⚠️ ᴏʀᴅᴇʀ ᴅᴀᴛᴀ ɴᴏᴛ ғᴏᴜɴᴅ!", show_alert=True)
    target_user_id = order['user_id']
    
    if action == "b_can":
        await query.edit_message_caption(caption=f"{query.message.caption_html}\n\n<b>❌ ʀᴇᴊᴇᴄᴛᴇᴅ ʙʏ ᴀᴅᴍɪɴ</b>", parse_mode='HTML')
        try:
            await context.bot.send_message(chat_id=target_user_id, text=f"<b>❌ ʏᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ ғᴏʀ ᴏʀᴅᴇʀ ɪᴅ <code>{order_id}</code> ᴡᴀs ʀᴇᴊᴇᴄᴛᴇᴅ ʙʏ ᴀᴅᴍɪɴ. ᴘʟᴇᴀsᴇ ᴄᴏɴᴛᴀᴄᴛ sᴜᴘᴘᴏʀᴛ ɪғ ᴛʜɪs ᴡᴀs ᴀ ᴍɪsᴛᴀᴋᴇ.</b>", parse_mode='HTML')
        except Exception: pass
        return

    if action == "b_adj":
        cmd = data[1]
        new_amt = order['amount'] + (1 if cmd == '+1' else -1)
        if new_amt < 1: new_amt = 1
        
        if order['prod'] == 't':
            new_price = (new_amt / 10) * 5
            disp_txt = f"<code>{new_amt}</code> <b>ᴛᴏᴋᴇɴs</b>"
        elif order['prod'] == 'c':
            new_price = new_amt / 5000
            disp_txt = f"<code>{new_amt:,}</code> <b>ᴄᴏɪɴs</b>"
        elif order['prod'] == 'char':
            live_char = await get_live_character_doc(order['char_id'])
            r = get_normalized_rarity(live_char.get('rarity') if live_char else '')
            new_price = (new_amt * CHAR_PRICES_COINS.get(r, 1000)) / 5000
            disp_txt = f"<code>{new_amt}</code>x <b>{to_small_caps(order['char_name'])}</b>"
            
        await bot_settings_collection.update_one({'_id': f"buy_{order_id}"}, {'$set': {'amount': new_amt, 'price_inr': new_price}})
        
        new_caption = (
            f"<b>🛒 ɴᴇᴡ ᴘᴜʀᴄʜᴀsᴇ ʀᴇǫᴜᴇsᴛ</b>\n"
            f"<b>👤 ᴜsᴇʀ:</b> <a href='tg://user?id={target_user_id}'>{html.escape(order['user_name'])}</a> (<code>{target_user_id}</code>)\n"
            f"<b>🆔 ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n"
            f"<b>📦 ɪᴛᴇᴍ:</b> {disp_txt}\n"
            f"<b>💸 ᴘᴀʏᴀʙʟᴇ:</b> <b>{new_price:.2f} ɪɴʀ</b>"
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("❮", callback_data=f"b_adj:-1:{order_id}"),
                InlineKeyboardButton(f"{new_amt:,}", callback_data="ignore"),
                InlineKeyboardButton("❯", callback_data=f"b_adj:+1:{order_id}")
            ],
            [InlineKeyboardButton("✅ ᴄᴏɴғɪʀᴍ", callback_data=f"b_cnf:{order_id}")],
            [InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data=f"b_can:{order_id}")]
        ])
        if query.message.caption_html != new_caption:
            await query.edit_message_caption(caption=new_caption, reply_markup=kb, parse_mode='HTML')
        else:
            await query.answer()
        return

    if action == "b_cnf":
        amount = order['amount']
        prod = order['prod']
        msg_out = ""

        if prod == "t":
            today_str = get_ist_now().strftime('%Y-%m-%d')
            await eco_collection.update_one({'id': target_user_id}, {'$inc': {'tokens': amount}}, upsert=True)
            user = await eco_collection.find_one({'id': target_user_id})
            if user and user.get('last_buy_date') == today_str:
                await eco_collection.update_one({'id': target_user_id}, {'$inc': {'daily_buy_limit_used': amount}})
            else:
                await eco_collection.update_one({'id': target_user_id}, {'$set': {'daily_buy_limit_used': amount, 'last_buy_date': today_str}})
            msg_out = f"<code>{amount}</code> ᴛᴏᴋᴇɴs"
        
        elif prod == "c":
            await eco_collection.update_one({'id': target_user_id}, {'$inc': {'balance': amount}}, upsert=True)
            msg_out = f"<code>{amount:,}</code> ᴄᴏɪɴs"

        elif prod == "char":
            char_doc = await get_live_character_doc(order['char_id'])
            if char_doc:
                copies = [char_doc for _ in range(amount)]
                await user_collection.update_one({'id': target_user_id}, {'$push': {'characters': {'$each': copies}}}, upsert=True)
            msg_out = f"<code>{amount}</code>x <b>{to_small_caps(order['char_name'])}</b>"

        await query.edit_message_caption(caption=f"{query.message.caption_html}\n\n<b>✅ ᴄᴏɴғɪʀᴍᴇᴅ & ᴅᴇʟɪᴠᴇʀᴇᴅ</b>", parse_mode='HTML')
        await bot_settings_collection.delete_one({'_id': f"buy_{order_id}"})

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"<b>🎉 ᴘᴀʏᴍᴇɴᴛ ᴄᴏɴғɪʀᴍᴇᴅ!</b>\n\n<b>{msg_out} ʜᴀᴠᴇ ʙᴇᴇɴ sᴜᴄᴄᴇssғᴜʟʟʏ ᴀᴅᴅᴇᴅ ᴛᴏ ʏᴏᴜʀ ᴡᴀʟʟᴇᴛ. ᴛʜᴀɴᴋ ʏᴏᴜ ғᴏʀ ʏᴏᴜʀ ᴘᴜʀᴄʜᴀsᴇ!</b>\n\n<b>ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>",
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
        await query.answer("⚠️ ʏᴏᴜ ᴄᴀɴɴᴏᴛ ɪɴᴛᴇʀᴀᴄᴛ ᴡɪᴛʜ ᴛʜɪs ᴍᴇɴᴜ! ᴘʟᴇᴀsᴇ ᴏᴘᴇɴ ʏᴏᴜʀ ᴏᴡɴ ᴍᴀʀᴋᴇᴛ ᴠɪᴀ /pmarket", show_alert=True)
        return

    action = parts[0]

    if action == "pm_b":
        buttons = []
        for key, (db_emoji, _, name) in RARITIES.items():
            buttons.append(InlineKeyboardButton(f"{db_emoji} {to_small_caps(name)}", callback_data=f"pm_r:{key}:{user_id}"))
        
        keyboard = chunk(buttons, 2)
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_m:{user_id}")])
        
        await update_menu(query, "<b><tg-emoji emoji-id=\"5312361253610475399\">🛒</tg-emoji> ʙᴜʏ ᴄʜᴀʀᴀᴄᴛᴇʀs ғʀᴏᴍ ᴍᴀʀᴋᴇᴛ</b>\n\n<i>sᴇʟᴇᴄᴛ ᴀ ʀᴀʀɪᴛʏ ᴛᴏ ᴠɪᴇᴡ ᴘʀᴏᴅᴜᴄᴛs.</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_m":
        bot_username = context.bot.username
        keyboard = await get_pmarket_keyboard(user_id, bot_username)
        await update_menu(query, "<b><tg-emoji emoji-id=\"5278702045883292456\">🛍</tg-emoji> P2P ᴍᴀʀᴋᴇᴛᴘʟᴀᴄᴇ</b>\n\n<i>ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ.</i>", keyboard)

    # --- EXCHANGE SUB-MENU ---
    elif action == "pm_exc_menu":
        global_limit, used_today, _ = await get_token_limit_info(user_id)
        limit_text = f"♾️" if user_id == OWNER_ID else f"{global_limit - used_today} ʟᴇғᴛ ᴛᴏᴅᴀʏ"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("ɢᴇᴛ ᴄᴏɪɴs", callback_data=f"pm_start_exc_t2c:{user_id}"),
             InlineKeyboardButton("ɢᴇᴛ ᴛᴏᴋᴇɴ", callback_data=f"pm_start_exc_c2t:{user_id}")],
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

    # 🔥 OPTIMIZED SORTING METHOD 🔥
    elif action == "pm_s":
        rarity_key = parts[1]
        order = parts[2]
        sort_order = 1 if order == "asc" else -1
        
        db_emoji, prem_emoji, name = RARITIES.get(rarity_key, RARITIES["common"])
        
        search_terms = [name, rarity_key]
        if rarity_key == "premium":
            search_terms.extend(["Premium Edition", "Premium"])

        regex_pattern = "|".join([re.escape(term) for term in search_terms])
        
        cursor = market_collection.find({
            'character.rarity': {'$regex': regex_pattern, '$options': 'i'}
        }).sort('price', sort_order).limit(10)
        
        market_items = await cursor.to_list(length=10)

        if not market_items:
            await query.answer("ɴᴏ ᴄʜᴀʀᴀᴄᴛᴇʀs ᴀʀᴇ ᴄᴜʀʀᴇɴᴛʟʏ ғᴏʀ sᴀʟᴇ ɪɴ ᴛʜɪs ʀᴀʀɪᴛʏ!", show_alert=True)
            return

        keyboard = []
        for item in market_items:
            char = item['character']
            char_name = char.get('name', 'Unknown')
            price = item['price']
            market_id = str(item['_id'])
            
            btn_text = f"{db_emoji} {to_small_caps(char_name)} - 💸 {price:,}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pm_v:{market_id}:{user_id}")])
        
        sort_text = "ʟᴏᴡ ᴛᴏ ʜɪɢʜ" if order == "asc" else "ʜɪɢʜ ᴛᴏ ʟᴏᴡ"
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_r:{rarity_key}:{user_id}")])

        await update_menu(query, f"<b>{prem_emoji} ᴄʜᴀʀᴀᴄᴛᴇʀs ғᴏʀ sᴀʟᴇ</b>\n\n<i>sᴏʀᴛᴇᴅ ʙʏ ᴘʀɪᴄᴇ ({sort_text})</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_v":
        market_id = parts[1]
        item = await market_collection.find_one({'_id': ObjectId(market_id)})
        
        if not item:
            await query.answer("ᴏᴏᴘs! ᴛʜɪs ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀs ᴀʟʀᴇᴀᴅʏ ʙᴇᴇɴ sᴏʟᴅ ᴏʀ ʀᴇᴍᴏᴠᴇᴅ!", show_alert=True)
            return

        char = item['character']
        seller_id = item['seller_id']
        price = item['price']
        char_name = char.get('name')
        char_id = char.get('id')
        
        live_char = await get_live_character_doc(char_id)
        if not live_char and char_name:
            tasks = [db[col_name].find_one({'name': char_name}) for col_name in ['anime_characters_lol', 'characters', 'collection']]
            results = await asyncio.gather(*tasks)
            live_char = next((r for r in results if r), None)
            
        display_char = live_char if live_char else char
        char_rarity_str = str(display_char.get('rarity', '')).strip()

        prem_emoji = '<tg-emoji emoji-id="6093722470265658964">🟢</tg-emoji>'
        name = char_rarity_str if char_rarity_str else "Common"
        
        matched = False
        for k, (d_emoji, p_emoji, r_name) in RARITIES.items():
            if r_name.lower() == char_rarity_str.lower() or k.lower() == char_rarity_str.lower() or (k == "premium" and "edition" in char_rarity_str.lower()):
                prem_emoji = p_emoji
                name = r_name
                matched = True
                break
                
        if not matched:
            for k, (d_emoji, p_emoji, r_name) in RARITIES.items():
                if r_name.lower() in char_rarity_str.lower() or k.lower() in char_rarity_str.lower():
                    prem_emoji = p_emoji
                    name = r_name
                    break

        caption = (
            f"<b>{prem_emoji} {to_small_caps(display_char.get('name', 'Unknown'))}</b>\n\n"
            f"<b><tg-emoji emoji-id=\"6312254267461739671\">⛩</tg-emoji> ᴀɴɪᴍᴇ:</b> {to_small_caps(display_char.get('anime', 'Unknown'))}\n"
            f"<b><tg-emoji emoji-id=\"5260426225599405269\">🪄</tg-emoji> ʀᴀʀɪᴛʏ:</b> {prem_emoji} {to_small_caps(name)}\n"
            f"<b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> ᴘʀɪᴄᴇ:</b> <code>{price:,}</code>\n"
            f"<b><tg-emoji emoji-id=\"6332443074769196273\">🆔</tg-emoji> sᴇʟʟᴇʀ:</b> <code>{seller_id}</code>"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 ʙᴜʏ ɴᴏᴡ", callback_data=f"pm_buy:{market_id}:{user_id}")],
            [InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_b:{user_id}")]
        ])

        await query.message.delete()
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=display_char.get('img_url', 'https://files.catbox.moe/0qjgih.png'), 
            caption=caption,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

    elif action == "pm_buy":
        market_id = parts[1]
        
        item = await market_collection.find_one({'_id': ObjectId(market_id)})
        if not item:
            await query.answer("ᴛᴏᴏ ʟᴀᴛᴇ! ᴛʜɪs ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀs ᴀʟʀᴇᴀᴅʏ ʙᴇᴇɴ ʙᴏᴜɢʜᴛ ʙʏ sᴏᴍᴇᴏɴᴇ ᴇʟsᴇ.", show_alert=True)
            return

        price = item['price']
        seller_id = item['seller_id']
        char = item['character']
        
        if seller_id == user_id:
            await query.answer("ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʙᴜʏ ʏᴏᴜʀ ᴏᴡɴ ᴄʜᴀʀᴀᴄᴛᴇʀ!", show_alert=True)
            return

        eco_buyer = await eco_collection.find_one_and_update(
            {'id': user_id, 'balance': {'$gte': price}},
            {'$inc': {'balance': -price}}
        )

        if not eco_buyer:
            await query.answer(f"ɪɴsᴜғғɪᴄɪᴇɴᴛ ғᴜɴᴅs! ʏᴏᴜ ɴᴇᴇᴅ 💸 {price:,} ʙᴀʟᴀɴᴄᴇ.", show_alert=True)
            return

        deleted_item = await market_collection.find_one_and_delete({'_id': ObjectId(market_id)})
        
        if not deleted_item:
            await eco_collection.update_one({'id': user_id}, {'$inc': {'balance': price}})
            await query.answer("ᴛᴏᴏ ʟᴀᴛᴇ! ᴛʜɪs ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀs ᴀʟʀᴇᴀᴅʏ ʙᴇᴇɴ ʙᴏᴜɢʜᴛ ʙʏ sᴏᴍᴇᴏɴᴇ ᴇʟsᴇ.", show_alert=True)
            return

        await asyncio.gather(
            user_collection.update_one({'id': user_id}, {'$push': {'characters': char}}),
            eco_collection.update_one({'id': seller_id}, {'$inc': {'balance': price}})
        )

        seller = await eco_collection.find_one({'id': seller_id})
        
        buyer_name = eco_buyer.get('first_name', 'Unknown')
        seller_name = seller.get('first_name', 'Unknown') if seller else 'Unknown'
        
        buyer_mention = f"<a href='tg://user?id={user_id}'>{html.escape(buyer_name)}</a>"
        seller_mention = f"<a href='tg://user?id={seller_id}'>{html.escape(seller_name)}</a>"

        log_details = (
            f"👤 <b>Bᴜʏᴇʀ:</b> {buyer_mention}\n"
            f"🏪 <b>Sᴇʟʟᴇʀ:</b> {seller_mention}\n"
            f"🎭 <b>Cʜᴀʀᴀᴄᴛᴇʀ:</b> {char.get('name')} (<code>{char.get('id')}</code>)\n"
            f"💰 <b>Pʀɪᴄᴇ:</b> {price:,} ᴄᴏɪɴs"
        )
        await send_market_log(context, "🛒 CHARACTER SOLD", log_details)

        await query.message.edit_caption(
            caption=f"<b>🎉 ᴄᴏɴɢʀᴀᴛᴜʟᴀᴛɪᴏɴs! ʏᴏᴜ sᴜᴄssғᴜʟʟʏ ʙᴏᴜɢʜᴛ {to_small_caps(char.get('name'))} ғᴏʀ <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {price:,}.</b>",
            parse_mode='HTML'
        )

    # --------------------------
    # SELL (MY LISTINGS) MENU
    # --------------------------
    elif action == "pm_sm":
        # Optimizing limit to 50 so that long button list doesnt break API response time
        cursor = market_collection.find({'seller_id': user_id}).limit(50)
        listings = await cursor.to_list(length=50)
        
        keyboard = [[InlineKeyboardButton("➕ ʟɪsᴛ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ", callback_data=f"pm_start_s:{user_id}")]]
        
        for item in listings:
            char_name = to_small_caps(item['character'].get('name', 'Unknown'))
            price = item['price']
            market_id = str(item['_id'])
            btn_text = f"ᴄᴀɴᴄᴇʟ | {char_name} - 💸 {price:,}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pm_delist:{market_id}:{user_id}")])
            
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_m:{user_id}")])
        
        await update_menu(query, "<b>💸 ʏᴏᴜʀ ᴀᴄᴛɪᴠᴇ ʟɪsᴛɪɴɢs</b>\n\n<i>ᴍᴀɴᴀɢᴇ ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ʟɪsᴛɪɴɢs ᴏʀ ᴀᴅᴅ ᴀ ɴᴇᴡ ᴏɴᴇ.</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_delist":
        market_id = parts[1]
        item = await market_collection.find_one({'_id': ObjectId(market_id)})
        
        if not item:
            await query.answer("⚠️ ᴛʜɪs ɪᴛᴇᴍ ɪs ɴᴏ ʟᴏɴɢᴇʀ ᴏɴ ᴛʜᴇ ᴍᴀʀᴋᴇᴛ.", show_alert=True)
        else:
            char = item['character']
            await asyncio.gather(
                user_collection.update_one({'id': user_id}, {'$push': {'characters': char}}),
                market_collection.delete_one({'_id': ObjectId(market_id)})
            )
            
            user_name = update.effective_user.first_name
            seller_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"
            
            log_details = (
                f"👤 <b>Sᴇʟʟᴇʀ:</b> {seller_mention}\n"
                f"🎭 <b>Cʜᴀʀᴀᴄᴛᴇʀ:</b> {char.get('name')} (<code>{char.get('id')}</code>)\n"
                f"❌ <b>Aᴄᴛɪᴏɴ:</b> Rᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ ᴍᴀʀᴋᴇᴛ."
            )
            await send_market_log(context, "📉 CHARACTER DELISTED", log_details)

            await query.answer(f"✅ sᴜᴄssғᴜʟʟʏ ʀᴇᴍᴏᴠᴇᴅ ᴀɴᴅ ʀᴇᴛᴜʀɴᴇᴅ ᴛᴏ ɪɴᴠᴇɴᴛᴏʀʏ!", show_alert=True)
        
        cursor = market_collection.find({'seller_id': user_id}).limit(50)
        listings = await cursor.to_list(length=50)
        keyboard = [[InlineKeyboardButton("➕ ʟɪsᴛ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ", callback_data=f"pm_start_s:{user_id}")]]
        for item in listings:
            char_name = to_small_caps(item['character'].get('name', 'Unknown'))
            price = item['price']
            m_id = str(item['_id'])
            btn_text = f"ᴄᴀɴᴄᴇʟ | {char_name} - 💸 {price:,}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pm_delist:{m_id}:{user_id}")])
            
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_m:{user_id}")])
        await update_menu(query, "<b>ʏᴏᴜʀ ᴀᴄᴛɪᴠᴇ ʟɪsᴛɪɴɢs</b>\n\n<i>ᴍᴀɴᴀɢᴇ ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ʟɪsᴛɪɴɢs ᴏʀ ᴀᴅᴅ ᴀ ɴᴇᴡ ᴏɴᴇ.</i>", InlineKeyboardMarkup(keyboard))

    # --------------------------
    # EXCHANGE CONFIRM LOGIC
    # --------------------------
    elif action == "pm_exc_conf":
        exc_type = parts[1]  
        amount = int(parts[2]) 
        
        global_limit, used_today, today_str = await get_token_limit_info(user_id)
        if user_id != OWNER_ID:
            if amount + used_today > global_limit:
                available = max(0, global_limit - used_today)
                await query.answer(f"⚠️ Dᴀɪʟʏ ʟɪᴍɪᴛ ʀᴇᴀᴄʜᴇᴅ! Yᴏᴜ ᴄᴀɴ ᴏɴʟʏ ᴇxᴄʜᴀɴɢᴇ {available} ᴍᴏʀᴇ ᴛᴏᴋᴇɴs ᴛᴏᴅᴀʏ.", show_alert=True)
                return

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_exc_menu:{user_id}")]])

        user_name = update.effective_user.first_name
        user_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"

        if exc_type == "t2c":
            coins_to_add = amount * 2500
            eco_user = await eco_collection.find_one_and_update(
                {'id': user_id, 'tokens': {'$gte': amount}},
                {'$inc': {'tokens': -amount, 'balance': coins_to_add}}
            )
            if not eco_user:
                await query.answer("⚠️ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴇɴᴏᴜɢʜ ᴛᴏᴋᴇɴs ᴀɴʏᴍᴏʀᴇ!", show_alert=True)
                return
                
            msg = f"<b>✅ Sᴜᴄᴄᴇssғᴜʟʟʏ ᴇxᴄʜᴀɴɢᴇᴅ <code>{amount}</code> ᴛᴏᴋᴇɴs ғᴏʀ <code>{coins_to_add:,}</code> ᴄᴏɪɴs!</b>"
            log_action = "🔄 TOKENS TO COINS"
            log_details = f"👤 <b>Usᴇʀ:</b> {user_mention}\n📉 <b>Sᴏʟᴅ:</b> {amount} ᴛᴏᴋᴇɴs\n📈 <b>Rᴇᴄᴇɪᴠᴇᴅ:</b> {coins_to_add:,} ᴄᴏɪɴs"

        elif exc_type == "c2t":
            coins_to_deduct = amount * 2500
            eco_user = await eco_collection.find_one_and_update(
                {'id': user_id, 'balance': {'$gte': coins_to_deduct}},
                {'$inc': {'balance': -coins_to_deduct, 'tokens': amount}}
            )
            if not eco_user:
                await query.answer("⚠️ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴇɴᴏᴜɢʜ ᴄᴏɪɴs ᴀɴʏᴍᴏʀᴇ!", show_alert=True)
                return
            
            msg = f"<b>✅ Sᴜᴄᴄᴇssғᴜʟʟʏ sᴘᴇɴᴛ <code>{coins_to_deduct:,}</code> ᴄᴏɪɴs ᴛᴏ ʙᴜʏ <code>{amount}</code> ᴛᴏᴋᴇɴs!</b>"
            log_action = "🔄 COINS TO TOKENS"
            log_details = f"👤 <b>Usᴇʀ:</b> {user_mention}\n📉 <b>Sᴘᴇɴᴛ:</b> {coins_to_deduct:,} ᴄᴏɪɴs\n📈 <b>Rᴇᴄᴇɪᴠᴇᴅ:</b> {amount} ᴛᴏᴋᴇɴs"

        if user_id != OWNER_ID:
            user_fresh = await eco_collection.find_one({'id': user_id})
            last_date = user_fresh.get('last_token_exchange_date', '')
            
            if last_date != today_str:
                await eco_collection.update_one({'id': user_id}, {'$set': {'daily_token_limit_used': amount, 'last_token_exchange_date': today_str}})
            else:
                await eco_collection.update_one({'id': user_id}, {'$inc': {'daily_token_limit_used': amount}})

        await send_market_log(context, log_action, log_details)
        await update_menu(query, msg, kb)


# ========================
# CONVERSATION HANDLERS
# ========================

# --- CANCEL AND TIMEOUT METHODS ---
async def cancel_process(update: Update, context: CallbackContext):
    context.user_data.pop('sell_owner_id', None)
    context.user_data.pop('sell_character', None)
    context.user_data.pop('exc_owner_id', None)
    context.user_data.pop('exc_type', None)
    context.user_data.pop('buy_prompt_active', None)
    await update.message.reply_text("<b>❌ ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟʟᴇᴅ.</b>", parse_mode='HTML')
    return ConversationHandler.END

async def timeout_process(update: Update, context: CallbackContext):
    context.user_data.pop('sell_owner_id', None)
    context.user_data.pop('sell_character', None)
    context.user_data.pop('exc_owner_id', None)
    context.user_data.pop('exc_type', None)
    context.user_data.pop('buy_prompt_active', None)
    
    msg = "<b>⌛ sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ ᴅᴜᴇ ᴛᴏ ɪɴᴀᴄᴛɪᴠɪᴛʏ (60s Timeout). ᴘʟᴇᴀsᴇ sᴛᴀʀᴛ ᴀɢᴀɪɴ.</b>"
    if update.message:
        await update.message.reply_text(msg, parse_mode='HTML')
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(msg, parse_mode='HTML')
    return ConversationHandler.END

# --- 1. SELL CONVERSATION ---
async def sell_start(update: Update, context: CallbackContext):
    query = update.callback_query
    parts = query.data.split(':')
    owner_id = int(parts[-1])
    
    if query.from_user.id != owner_id:
        await query.answer("⚠️ ʏᴏᴜ ᴄᴀɴɴᴏᴛ ɪɴᴛᴇʀᴀᴄᴛ ᴡɪᴛʜ ᴛʜɪs ᴍᴇɴᴜ!", show_alert=True)
        return ConversationHandler.END
        
    # --- SPAM BLOCKER FOR SELL ---
    if context.user_data.get('sell_owner_id'):
        await query.answer("⚠️ ʏᴏᴜ ᴀʀᴇ ᴀʟʀᴇᴀᴅʏ ɪɴ ᴛʜᴇ ᴘʀᴏᴄᴇss! ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ᴄʜᴀʀᴀᴄᴛᴇʀ ɪᴅ ᴏʀ ᴛʏᴘᴇ /cancel.", show_alert=True)
        return WAITING_FOR_CHARACTER_ID

    await query.answer()
    context.user_data['sell_owner_id'] = owner_id

    await query.message.reply_text(
        "💸 <b>sᴇɴᴅ ᴛʜᴇ ᴄʜᴀʀᴀᴄᴛᴇʀ ID ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ sᴇʟʟ:</b>\n\n(ᴛʏᴘᴇ /cancel ᴛᴏ ᴀʙᴏʀᴛ ᴛʜᴇ ᴘʀᴏᴄᴇss)",
        parse_mode="HTML"
    )
    return WAITING_FOR_CHARACTER_ID

async def ask_character_id(update: Update, context: CallbackContext):
    if not update.message or not update.message.text: return WAITING_FOR_CHARACTER_ID
    user_id = update.message.from_user.id
    expected_owner = context.user_data.get('sell_owner_id')
    if expected_owner and user_id != expected_owner: return WAITING_FOR_CHARACTER_ID

    char_id = update.message.text.strip()
    user_data = await user_collection.find_one({'id': user_id})
    
    # --- SILENT IGNORE ---
    if not user_data or 'characters' not in user_data:
        return WAITING_FOR_CHARACTER_ID

    character = next((c for c in user_data.get('characters', []) if str(c.get('id')) == str(char_id)), None)
    
    # --- SILENT IGNORE ---
    if not character:
        return WAITING_FOR_CHARACTER_ID

    context.user_data['sell_character'] = character
    await update.message.reply_text(
        f"✅ <b>ᴄʜᴀʀᴀᴄᴛᴇʀ ғᴏᴜɴᴅ! ɴᴏᴡ sᴇɴᴅ ᴘʀɪᴄᴇ</b>\n\n"
        f"Sᴇʟᴇᴄᴛᴇᴅ: <b>{to_small_caps(character.get('name'))}</b>\n"
        f"<i>Eɴᴛᴇʀ ᴛʜᴇ ᴘʀɪᴄᴇ (ɪɴ <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>) ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ sᴇʟʟ ɪᴛ ғᴏʀ.</i>",
        parse_mode='HTML'
    )
    return WAITING_FOR_PRICE

async def ask_price(update: Update, context: CallbackContext):
    if not update.message or not update.message.text: return WAITING_FOR_PRICE
    user_id = update.message.from_user.id
    expected_owner = context.user_data.get('sell_owner_id')
    if expected_owner and user_id != expected_owner: return WAITING_FOR_PRICE

    price_text = update.message.text.strip()
    
    # --- SILENT IGNORE ---
    if not price_text.isdigit() or int(price_text) <= 0:
        return WAITING_FOR_PRICE

    price = int(price_text)
    
    if price > 1000000:
        await update.message.reply_text("<b>⚠️ ᴍᴀxɪᴍᴜᴍ ᴘʀɪᴄᴇ ʟɪᴍɪᴛ ɪs 1,000,000 ᴄᴏɪɴs. ᴘʟᴇᴀsᴇ ᴇɴᴛᴇʀ ᴀ ʟᴏᴡᴇʀ ᴀᴍᴏᴜɴᴛ.</b>", parse_mode='HTML')
        return WAITING_FOR_PRICE

    character = context.user_data.get('sell_character')

    if not character:
        await update.message.reply_text("<b>sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ. ᴘʟᴇᴀsᴇ sᴛᴀʀᴛ ᴀɢᴀɪɴ ᴠɪᴀ /pmarket</b>", parse_mode='HTML')
        return ConversationHandler.END

    char_id_val = character['id']
    live_char = await get_live_character_doc(char_id_val)
    final_character = live_char if live_char else character

    user_doc = await user_collection.find_one({'id': user_id})
    if user_doc and 'characters' in user_doc:
        chars_list = user_doc['characters']
        
        for i, c in enumerate(chars_list):
            if str(c.get('id')) == str(char_id_val):
                del chars_list[i]
                break
                
        await user_collection.update_one({'id': user_id}, {'$set': {'characters': chars_list}})

    await market_collection.insert_one({'seller_id': user_id, 'price': price, 'character': final_character})

    user_name = update.message.from_user.first_name
    user_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"

    log_details = (
        f"👤 <b>Sᴇʟʟᴇʀ:</b> {user_mention}\n"
        f"🎭 <b>Cʜᴀʀᴀᴄᴛᴇʀ:</b> {final_character.get('name')} (<code>{final_character.get('id')}</code>)\n"
        f"💰 <b>Pʀɪᴄᴇ Sᴇᴛ:</b> {price:,} ᴄᴏɪɴs"
    )
    await send_market_log(context, "📈 CHARACTER LISTED", log_details)

    context.user_data.pop('sell_character', None)
    context.user_data.pop('sell_owner_id', None)
    
    await update.message.reply_text(
        f"<b>🎉 {to_small_caps(final_character.get('name'))} ʜᴀs ʙᴇᴇɴ sᴜᴄssғᴜʟʟʏ ʟɪsᴛᴇᴅ ᴏɴ ᴛʜᴇ ᴍᴀʀᴋᴇᴛ ғᴏʀ <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {price:,}!</b>",
        parse_mode='HTML'
    )
    return ConversationHandler.END

# --- 2. EXCHANGE CONVERSATION (T2C and C2T) ---
async def exchange_start_t2c(update: Update, context: CallbackContext):
    query = update.callback_query
    parts = query.data.split(':')
    owner_id = int(parts[-1])
    
    if query.from_user.id != owner_id:
        await query.answer("⚠️ ʏᴏᴜ ᴄᴀɴɴᴏᴛ ɪɴᴛᴇʀᴀᴄᴛ ᴡɪᴛʜ ᴛʜɪs ᴍᴇɴᴜ!", show_alert=True)
        return ConversationHandler.END
        
    # --- SPAM BLOCKER FOR T2C ---
    if context.user_data.get('exc_owner_id'):
        await query.answer("⚠️ ʏᴏᴜ ᴀʀᴇ ᴀʟʀᴇᴀᴅʏ ɪɴ ᴛʜᴇ ᴘʀᴏᴄᴇss! ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ᴀᴍᴏᴜɴᴛ ᴏʀ ᴛʏᴘᴇ /cancel.", show_alert=True)
        return WAITING_FOR_EXCHANGE_AMOUNT

    await query.answer()
    context.user_data['exc_owner_id'] = owner_id
    context.user_data['exc_type'] = 't2c'
    
    user = await eco_collection.find_one({'id': owner_id})
    tokens = user.get('tokens', 0) if user else 0

    await query.message.reply_text(
        f"<b>💱 ʜᴏᴡ ᴍᴀɴʏ ᴛᴏᴋᴇɴs ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ sᴇʟʟ ғᴏʀ ᴄᴏɪɴs?</b>\n\n"
        f"<i>1 ᴛᴏᴋᴇɴ = 2,500 ᴄᴏɪɴs.</i>\n"
        f"<b>ʏᴏᴜ ʜᴀᴠᴇ:</b> <code>{tokens:,}</code> ᴛᴏᴋᴇɴs\n\n"
        f"(Eɴᴛᴇʀ ᴛʜᴇ ɴᴜᴍʙᴇʀ ᴏғ ᴛᴏᴋᴇɴs, ᴇ.ɢ. ᴛʏᴘᴇ <b>1</b> ᴛᴏ ɢᴇᴛ 2500 ᴄᴏɪɴs)\n"
        f"(ᴛʏᴘᴇ /cancel ᴛᴏ ᴀʙᴏʀᴛ ᴛʜᴇ ᴘʀᴏᴄᴇss)",
        parse_mode="HTML"
    )
    return WAITING_FOR_EXCHANGE_AMOUNT

async def exchange_start_c2t(update: Update, context: CallbackContext):
    query = update.callback_query
    parts = query.data.split(':')
    owner_id = int(parts[-1])
    
    if query.from_user.id != owner_id:
        await query.answer("⚠️ ʏᴏᴜ ᴄᴀɴɴᴏᴛ ɪɴᴛᴇʀᴀᴄᴛ ᴡɪᴛʜ ᴛʜɪs ᴍᴇɴᴜ!", show_alert=True)
        return ConversationHandler.END
        
    # --- SPAM BLOCKER FOR C2T ---
    if context.user_data.get('exc_owner_id'):
        await query.answer("⚠️ ʏᴏᴜ ᴀʀᴇ ᴀʟʀᴇᴀᴅʏ ɪɴ ᴛʜᴇ ᴘʀᴏᴄᴇss! ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ᴀᴍᴏᴜɴᴛ ᴏʀ ᴛʏᴘᴇ /cancel.", show_alert=True)
        return WAITING_FOR_EXCHANGE_AMOUNT

    await query.answer()
    context.user_data['exc_owner_id'] = owner_id
    context.user_data['exc_type'] = 'c2t'
    
    user = await eco_collection.find_one({'id': owner_id})
    coins = user.get('balance', 0) if user else 0

    await query.message.reply_text(
        f"<b>💱 ʜᴏᴡ ᴍᴀɴʏ ᴛᴏᴋᴇɴs ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʙᴜʏ ᴡɪᴛʜ ᴄᴏɪɴs?</b>\n\n"
        f"<i>2,500 ᴄᴏɪɴs = 1 ᴛᴏᴋᴇɴ.</i>\n"
        f"<b>ʏᴏᴜ ʜᴀᴠᴇ:</b> <code>{coins:,}</code> ᴄᴏɪɴs\n\n"
        f"(Eɴᴛᴇʀ ᴛʜᴇ ɴᴜᴍʙᴇʀ ᴏғ ᴛᴏᴋᴇɴs, ᴇ.ɢ. ᴛʏᴘᴇ <b>1</b> ᴛᴏ sᴘᴇɴᴅ 2500 ᴄᴏɪɴs)\n"
        f"(ᴛʏᴘᴇ /cancel ᴛᴏ ᴀʙᴏʀᴛ ᴛʜᴇ ᴘʀᴏᴄᴇss)",
        parse_mode="HTML"
    )
    return WAITING_FOR_EXCHANGE_AMOUNT

async def ask_exchange_amount(update: Update, context: CallbackContext):
    if not update.message or not update.message.text: return WAITING_FOR_EXCHANGE_AMOUNT
    user_id = update.message.from_user.id
    expected_owner = context.user_data.get('exc_owner_id')
    exc_type = context.user_data.get('exc_type')
    if expected_owner and user_id != expected_owner: return WAITING_FOR_EXCHANGE_AMOUNT

    amount_text = update.message.text.strip()
    
    # --- SILENT IGNORE ---
    if not amount_text.isdigit() or int(amount_text) <= 0:
        return WAITING_FOR_EXCHANGE_AMOUNT

    amount = int(amount_text)
    
    global_limit, used_today, _ = await get_token_limit_info(user_id)
    if user_id != OWNER_ID:
        if amount + used_today > global_limit:
            available = max(0, global_limit - used_today)
            await update.message.reply_text(
                f"⚠️ <b>Dᴀɪʟʏ Lɪᴍɪᴛ Exᴄᴇᴇᴅᴇᴅ!</b>\n"
                f"Yᴏᴜ ᴄᴀɴ ᴏɴʟʏ ᴇxᴄʜᴀɴɢᴇ <code>{global_limit}</code> ᴛᴏᴋᴇɴs ᴘᴇʀ ᴅᴀʏ.\n"
                f"Yᴏᴜ ʜᴀᴠᴇ <code>{available}</code> ᴛᴏᴋᴇɴs ʟᴇғᴛ ғᴏʀ ᴛᴏᴅᴀʏ.", 
                parse_mode='HTML'
            )
            return WAITING_FOR_EXCHANGE_AMOUNT

    user = await eco_collection.find_one({'id': user_id})
    tokens = user.get('tokens', 0) if user else 0
    coins = user.get('balance', 0) if user else 0
    
    if exc_type == 't2c':
        if amount > tokens:
            await update.message.reply_text(f"<b>ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴇɴᴏᴜɢʜ ᴛᴏᴋᴇɴs! ʏᴏᴜ ᴏɴʟʏ ʜᴀᴠᴇ <code>{tokens:,}</code> ᴛᴏᴋᴇɴs.</b>", parse_mode='HTML')
            return WAITING_FOR_EXCHANGE_AMOUNT
        total_coins = amount * 2500
        text_msg = f"<i>ᴀʀᴇ ʏᴏᴜ sᴜʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴇxᴄʜᴀɴɢᴇ <code>{amount}</code> ᴛᴏᴋᴇɴs ᴛᴏ ɢᴇᴛ <code>{total_coins:,}</code> ᴄᴏɪɴs?</i>"
        
    elif exc_type == 'c2t':
        cost = amount * 2500
        if cost > coins:
            await update.message.reply_text(f"<b>ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴇɴᴏᴜɢʜ ᴄᴏɪɴs! ʏᴏᴜ ᴏɴʟʏ ʜᴀᴠᴇ <code>{coins:,}</code> ᴄᴏɪɴs.</b>\n<i>(ʏᴏᴜ ɴᴇᴇᴅ <code>{cost:,}</code> ᴄᴏɪɴs ᴛᴏ ʙᴜʏ <code>{amount}</code> ᴛᴏᴋᴇɴs)</i>", parse_mode='HTML')
            return WAITING_FOR_EXCHANGE_AMOUNT
        text_msg = f"<i>ᴀʀᴇ ʏᴏᴜ sᴜʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ sᴘᴇɴᴅ <code>{cost:,}</code> ᴄᴏɪɴs ᴛᴏ ɢᴇᴛ <code>{amount}</code> ᴛᴏᴋᴇɴs?</i>"
        
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("ᴄᴏɴғɪʀᴍ", callback_data=f"pm_exc_conf:{exc_type}:{amount}:{user_id}")],
        [InlineKeyboardButton("ᴄᴀɴᴄᴇʟ", callback_data=f"pm_exc_menu:{user_id}")]
    ])
    
    await update.message.reply_text(
        f"<b>ᴄᴏɴғɪʀᴍ ᴇxᴄʜᴀɴɢᴇ</b>\n\n{text_msg}",
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    
    context.user_data.pop('exc_owner_id', None)
    context.user_data.pop('exc_type', None)
    return ConversationHandler.END


sell_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(sell_start, pattern=r"^pm_start_s:")],
    states={
        WAITING_FOR_CHARACTER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_character_id)],
        WAITING_FOR_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_price)],
        ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_process)]
    },
    fallbacks=[CommandHandler("cancel", cancel_process)],
    conversation_timeout=60,
    allow_reentry=True,
    per_user=True,
    per_chat=True,
)

exchange_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(exchange_start_t2c, pattern=r"^pm_start_exc_t2c:"),
        CallbackQueryHandler(exchange_start_c2t, pattern=r"^pm_start_exc_c2t:")
    ],
    states={
        WAITING_FOR_EXCHANGE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_exchange_amount)],
        ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_process)]
    },
    fallbacks=[CommandHandler("cancel", cancel_process)],
    conversation_timeout=60,
    allow_reentry=True,
    per_user=True,
    per_chat=True,
)

buy_conv = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex(r'^/start buy_tokens$'), start_buy_menu),
        CommandHandler("buy", buy_command_pm)
    ],
    states={
        WAITING_FOR_BUY_PRODUCT: [
            CallbackQueryHandler(buy_product_callback, pattern='^(buy_prod_t|buy_prod_c|buy_prod_char)$'),
            CallbackQueryHandler(cancel_buy_callback, pattern='^buy_cancel$')
        ],
        WAITING_FOR_BUY_CHAR_ID: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, ask_buy_char_id),
            CallbackQueryHandler(cancel_buy_callback, pattern='^buy_cancel$')
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
    conversation_timeout=120,
    allow_reentry=True,
    per_user=True,
    per_chat=True,
)

application.add_handler(sell_conv, group=-1)
application.add_handler(exchange_conv, group=-2)
application.add_handler(buy_conv, group=-3) 

application.add_handler(CommandHandler(["pmarket", "shop"], pmarket_command, block=False), group=0)
application.add_handler(CommandHandler("toggle_exchange", toggle_exchange_cmd, block=False), group=0)
application.add_handler(CommandHandler("set_exchange_limit", set_exchange_limit_cmd, block=False), group=0)
application.add_handler(CommandHandler("forcedelist", force_delist_cmd, block=False), group=0)
application.add_handler(CommandHandler("mrarity_on", mrarity_on_cmd, block=False), group=0)
application.add_handler(CommandHandler("mrarity_off", mrarity_off_cmd, block=False), group=0)

application.add_handler(CallbackQueryHandler(pmarket_callbacks, pattern='^(pm_m|pm_b|pm_r|pm_s|pm_v|pm_buy|pm_sm|pm_delist|pm_exc_conf|pm_exc_menu):', block=False), group=0)

# Global Callback handler for admin confirm/cancel/adjust 
application.add_handler(CallbackQueryHandler(admin_buy_callback, pattern='^(b_adj|b_cnf|b_can|ignore)', block=False), group=0)

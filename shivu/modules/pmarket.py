import asyncio
import html
import uuid
import re
import math
import time
from datetime import datetime, timedelta
from bson import ObjectId
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, filters, TypeHandler
from shivu import application, db

# 🔥 NAYA IMPORT: Dual Database Sync Ke Liye
from shivu.Database.db import eco_collection

# --- PREMIUM EMOJIS ---
E_TICK = '<tg-emoji emoji-id="6105024010985152856">✅</tg-emoji>'
E_CROSS = '<tg-emoji emoji-id="6105159401239225894">❌</tg-emoji>'
E_WARN = '<tg-emoji emoji-id="6105189427355589893">⚠️</tg-emoji>'
E_EXC = '<tg-emoji emoji-id="5377336227533969892">💱</tg-emoji>'
E_WAIT = '<tg-emoji emoji-id="6104853200135791744">⏳</tg-emoji>'
E_PARTY = '<tg-emoji emoji-id="5436040291507247633">🎉</tg-emoji>'
E_INF = '<tg-emoji emoji-id="6105158430576616482">♾</tg-emoji>'
E_MONEY = '<tg-emoji emoji-id="5472030678633684592">💸</tg-emoji>'
E_TIME = '<tg-emoji emoji-id="6307488052059053932">🕐</tg-emoji>'

# --- CONFIGURATION ---
LOG_GROUP_ID = -1003893927065
BUY_LOG_GROUP_ID = -1003757326893  
OWNER_ID = 7657218453

# --- DATABASE COLLECTIONS ---
user_collection = db['user_collection_lmaoooo'] 
market_collection = db['market_collection'] 
bot_settings_collection = db['bot_settings'] 
delete_collection = db['auto_delete_queue'] # 🔥 Yaddasht ke liye nayi collection

# --- HELPER: GET INDIAN STANDARD TIME (IST) ---
def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# 🔥 PERMANENT AUTO DELETE SYSTEM 🔥
_worker_started = False

async def background_delete_worker(bot):
    """Ye worker background me chalega aur restart hone par bhi database check karke delete karega"""
    try:
        await delete_collection.create_index("delete_at")
    except Exception:
        pass
        
    while True:
        try:
            now = time.time()
            cursor = delete_collection.find({'delete_at': {'$lte': now}})
            async for doc in cursor:
                try:
                    await bot.delete_message(chat_id=doc['chat_id'], message_id=doc['message_id'])
                except Exception:
                    pass 
                finally:
                    await delete_collection.delete_one({'_id': doc['_id']})
        except Exception:
            pass
        await asyncio.sleep(30)

# --- HELPER: AUTO DELETE MESSAGE LATER ---
async def delete_message_later(bot, chat_id, message_id, delay):
    if not bot or not chat_id or not message_id: return
        
    global _worker_started
    if not _worker_started:
        _worker_started = True
        asyncio.create_task(background_delete_worker(bot))

    delete_at = time.time() + delay

    # MongoDB me save karega taki bot crash/restart hone par mission na bhule
    await delete_collection.insert_one({
        'chat_id': chat_id,
        'message_id': message_id,
        'delete_at': delete_at
    })

    # Memory worker taaki smoothly delete ho jaye agar bot chalu rahe to
    async def memory_delete():
        await asyncio.sleep(delay)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            await delete_collection.delete_one({'chat_id': chat_id, 'message_id': message_id})
        except Exception:
            pass

    asyncio.create_task(memory_delete())

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
    except Exception:
        pass

# 🔥 HELPER: SEND BUY LOGS TO THE NEW GROUP
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
    except Exception:
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


# 🔥 HELPER TO GET LIVE CHARACTER (1, 01, 001 SAB MATCH HOGA)
async def get_live_character_doc(char_id):
    if char_id is None:
        return None
    
    char_str = str(char_id).strip()
    query_conditions = [{'id': char_str}]
    
    if char_str.isdigit():
        num = int(char_str)
        query_conditions.extend([
            {'id': num}, 
            {'id': str(num)}, 
            {'id': f"{num:02d}"}
        ])
        
    query = {'$or': query_conditions}
    
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

sc = to_small_caps

# --- RARITIES & PRICES ---
RARITIES = {
    "common": ("🟢", '<tg-emoji emoji-id="6093865707424980866">🟢</tg-emoji>', "Common"), 
    "rare": ("🟠", '<tg-emoji emoji-id="5339390195768774311">🟠</tg-emoji>', "Rare"), 
    "legendary": ("🟡", '<tg-emoji emoji-id="6084550327086883643">🟡</tg-emoji>', "Legendary"),
    "special": ("🔴", '<tg-emoji emoji-id="6093741664474504699">🔴</tg-emoji>', "Medium"), 
    "celestial": ("🪽", '<tg-emoji emoji-id="5434121252874756456">🪽</tg-emoji>', "Celestial"), 
    "erotic": ("🥵", '<tg-emoji emoji-id="6093490292923574796">🥵</tg-emoji>', "Spicy"),
    "exclusive": ("💮", '<tg-emoji emoji-id="6100567406889935797">💮</tg-emoji>', "Exclusive"), 
    "cosmic": ("🌌", '<tg-emoji emoji-id="5431783411981228752">🌌</tg-emoji>', "Cosmic"), 
    "mythic": ("💎", '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>', "Mythic"),
    "sweet": ("🍭", '<tg-emoji emoji-id="6222115531122546353">🍭</tg-emoji>', "Sweet"), 
    "valentine": ("💞", '<tg-emoji emoji-id="5255861796350224063">💞</tg-emoji>', "Valentine"), 
    "winter": ("❄️", '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>', "Winter"),
    "neon": ("⚡", '<tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>', "Neon"), 
    "pearl": ("🏝️", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"), 
    "premium": ("🔮", '<tg-emoji emoji-id="6093919703753831564">🔮</tg-emoji>', "Premium Edition"), 
}

CHAR_PRICES_COINS = {
    "common": 1000, "rare": 10000, "medium": 8000, 
    "legendary": 15000, "celestial": 70000, "spicy": 99000, 
    "exclusive": 30000, "mythic": 180000, "premium edition": 250000, 
    "sweet": 62000, "valentine": 90000, "winter": 59000, 
    "neon": 67000, "summer": 65000, "cosmic": 740000
}

def get_normalized_rarity(rarity_str):
    if not rarity_str: return "common"
    r = str(rarity_str).lower().strip()
    
    if "premium" in r: return "premium edition"
    if "spicy" in r or "erotic" in r: return "spicy"
    if "medium" in r or "special" in r: return "medium"
    if "summer" in r or "pearl" in r: return "summer"
    
    for key in CHAR_PRICES_COINS.keys():
        if key in r: return key
        
    for key, val in RARITIES.items():
        if val[2].lower() in r:
            return key if key in CHAR_PRICES_COINS else "common"
            
    return "common"

def chunk(items: list, size: int) -> list:
    return [items[i:i + size] for i in range(0, len(items), size)]

async def update_menu(query, text, keyboard):
    bot = query.message.get_bot()
    if query.message.photo or query.message.video:
        chat_id = query.message.chat_id
        try:
            await query.message.delete()
        except Exception:
            pass
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')

async def clear_existing_states(context: CallbackContext):
    keys = ['sell_owner_id', 'sell_character', 'sell_active', 'sell_step', 'exc_owner_id', 'exc_type', 'buy_prompt_active', 'buy_product', 'buy_char_id', 'buy_amount', 'buy_price', 'qr_msg_id']
    for k in keys:
        context.user_data.pop(k, None)

async def get_pmarket_keyboard(user_id, bot_username=""):
    settings = await bot_settings_collection.find_one({'_id': 'pmarket_settings'})
    exchange_enabled = settings.get('exchange_enabled', True) if settings else True
    
    keyboard = []
    if exchange_enabled:
        keyboard.append([InlineKeyboardButton(sc("ᴇxᴄʜᴀɴɢᴇ"), callback_data=f"pm_exc_menu:{user_id}", icon_custom_emoji_id="5377336227533969892")])
    
    keyboard.append([
        InlineKeyboardButton(sc("ʙᴜʏ"), callback_data=f"pm_b:{user_id}", icon_custom_emoji_id="5312361253610475399"),
        InlineKeyboardButton(sc("sᴇʟʟ"), callback_data=f"pm_sm:{user_id}", icon_custom_emoji_id="5472030678633684592")
    ])
    
    if bot_username:
        keyboard.append([InlineKeyboardButton(sc("ʙᴜʏ ᴛᴏᴋᴇɴs/ᴄᴏɪɴs"), url=f"https://t.me/{bot_username}?start=buy_tokens", icon_custom_emoji_id="5445353829304387411")])
        
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
    await update.message.reply_html(f"<b>ᴘᴍᴀʀᴋᴇᴛ ᴇxᴄʜᴀɴɢᴇ ʙᴜᴛᴛᴏɴ ʜᴀs ʙᴇᴇɴ {'ᴇɴᴀʙʟᴇᴅ ' + E_TICK if new_state else 'ᴅɪsᴀʙʟᴇᴅ ' + E_CROSS}.</b>")

async def set_exchange_limit_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: return
    if not context.args or not context.args[0].isdigit():
        return await update.message.reply_text(f"{E_WARN} <b>{sc('invalid format.')}</b>\n{sc('usage:')} /set_exchange_limit <amount>", parse_mode="HTML")
    new_limit = int(context.args[0])
    await bot_settings_collection.update_one({'_id': 'pmarket_settings'}, {'$set': {'daily_token_limit': new_limit}}, upsert=True)
    await update.message.reply_html(f"{E_TICK} <b>{sc('daily exchange limit has been updated to')} <code>{new_limit}</code> {sc('tokens!')}</b>")

async def force_delist_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: return
    if not context.args:
        return await update.message.reply_text(f"{E_WARN} <b>{sc('invalid format.')}</b>\n{sc('usage:')} /forcedelist <character_id>", parse_mode="HTML")
        
    char_id = context.args[0]
    query = {'$or': [{'character.id': char_id}, {'character.id': int(char_id) if char_id.isdigit() else char_id}]}
    listings = await market_collection.find(query).to_list(length=None)
    
    if not listings: return await update.message.reply_html(f"{E_WARN} <b>{sc('no active listings found for character id')} <code>{char_id}</code> {sc('on the market.')}</b>")
    
    tasks, market_ids, count = [], [], 0
    for item in listings:
        seller_id, char = item['seller_id'], item['character']
        market_ids.append(item['_id'])
        count += 1
        seller_mention = f"<a href='tg://user?id={seller_id}'>{seller_id}</a>"
        log_details = (
            f"🛡️ <b>Aᴅᴍɪɴ Fᴏʀᴄᴇ Dᴇʟɪsᴛ</b>\n"
            f"👤 <b>Sᴇʟʟᴇʀ:</b> {seller_mention}\n"
            f"🎭 <b>Cʜᴀʀᴀᴄᴛᴇʀ:</b> {char.get('name')} (<code>{char.get('id')}</code>)\n"
            f"{E_CROSS} <b>Aᴄᴛɪᴏɴ:</b> Rᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ ᴍᴀʀᴋᴇᴛ ʙʏ Bᴏᴛ Oᴡɴᴇʀ."
        )
        tasks.append(send_market_log(context, "📉 FORCE DELISTED", log_details))
    
    await asyncio.gather(*tasks)
    await market_collection.delete_many({'_id': {'$in': market_ids}})
    await update.message.reply_html(f"{E_TICK} <b>{sc('successfully removed')} <code>{count}</code> {sc('listing(s) for character id')} <code>{char_id}</code>.</b>")

# ========================
# RARITY TOGGLES COMMANDS
# ========================
async def mrarity_on_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: return
    if not context.args:
        return await update.message.reply_html(f"<b>{E_WARN} {sc('please provide a rarity name. example:')} /mrarity_on common</b>")
    r = " ".join(context.args).lower()
    await bot_settings_collection.update_one({'_id': 'market_rarity_settings'}, {'$set': {f'enabled.{r}': True}}, upsert=True)
    await update.message.reply_html(f"<b>{E_TICK} {sc(r)} {sc('rarity is now enabled for purchase!')}</b>")

async def mrarity_off_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: return
    if not context.args:
        return await update.message.reply_html(f"<b>{E_WARN} {sc('please provide a rarity name. example:')} /mrarity_off common</b>")
    r = " ".join(context.args).lower()
    await bot_settings_collection.update_one({'_id': 'market_rarity_settings'}, {'$set': {f'enabled.{r}': False}}, upsert=True)
    await update.message.reply_html(f"<b>{E_CROSS} {sc(r)} {sc('rarity is now disabled for purchase.')}</b>")

# ========================
# BUY TOKENS/COINS/CHARS MENU
# ========================
async def buy_command_pm(update: Update, context: CallbackContext):
    if update.effective_chat.type != "private":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(sc("buy here"), url=f"https://t.me/{context.bot.username}?start=buy_tokens", icon_custom_emoji_id="5445353829304387411")]])
        await update.message.reply_html(f"<b>{E_WARN} {sc('this command only works in pm (private messages).')}\n{sc('click below to buy.')}</b>", reply_markup=kb)
        return ConversationHandler.END
    return await start_buy_menu(update, context)

async def start_buy_menu(update: Update, context: CallbackContext):
    await clear_existing_states(context)

    order_id = uuid.uuid4().hex[:8]
    context.user_data['buy_order_id'] = order_id

    text = (
        f"<b>{E_TICK} {sc('order session created successfully!')}</b>\n"
        f"<b>{sc('order id:')}</b> <code>{order_id}</code>\n\n"
        f"<b>{sc('select the product you want to buy:')}</b>"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(sc("tokens"), callback_data="buy_prod_t", icon_custom_emoji_id="5377336227533969892"), InlineKeyboardButton(sc("coins"), callback_data="buy_prod_c", icon_custom_emoji_id="5472030678633684592")],
        [InlineKeyboardButton(sc("characters"), callback_data="buy_prod_char")],
        [InlineKeyboardButton(sc("cancel"), callback_data="buy_cancel", icon_custom_emoji_id="6105159401239225894")]
    ])

    if update.callback_query: 
        await update.callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await send_buy_log(context, "🔄 BACK TO MENU", update.effective_user, f"🆔 <b>ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n💬 <b>Aᴄᴛɪᴏɴ:</b> Rᴇᴛᴜʀɴᴇᴅ ᴛᴏ Bᴜʏ Mᴇɴᴜ")
    else:
        await update.message.reply_html(text, reply_markup=keyboard)
        await send_buy_log(context, "🚀 STARTED", update.effective_user, f"🆔 <b>ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n💬 <b>Aᴄᴛɪᴏɴ:</b> Iɴɪᴛɪᴀᴛᴇᴅ Bᴜʏ Mᴇɴᴜ")
        
    return WAITING_FOR_BUY_PRODUCT

async def buy_back_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    context.user_data.pop('buy_product', None)
    context.user_data.pop('buy_char_id', None)
    context.user_data.pop('buy_prompt_active', None)
    return await start_buy_menu(update, context)

async def buy_product_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    
    if context.user_data.get('buy_prompt_active'):
        await query.answer(f"⚠️ {sc('you are already in the process! please send the required info or type')} /cancel.", show_alert=True)
        if context.user_data.get('buy_product') == 'char' and not context.user_data.get('buy_char_id'):
            return WAITING_FOR_BUY_CHAR_ID
        return WAITING_FOR_BUY_AMOUNT
    
    await query.answer()
    context.user_data['buy_prompt_active'] = True
    context.user_data['buy_product'] = query.data.replace('buy_prod_', '')

    order_id = context.user_data.get('buy_order_id', 'UNKNOWN')
    
    if query.data == "buy_prod_t":
        text = f"<b>{sc('send the amount of tokens you want to buy (min: 15, max: 1000).')}</b>\n\n<b>{sc('rate: 15 tokens for 5 inr.')}</b>"
        next_state = WAITING_FOR_BUY_AMOUNT
    elif query.data == "buy_prod_c":
        text = f"<b>{sc('send the amount of coins you want to buy (min: 37,500, max: 2,500,000).')}</b>\n\n<b>{sc('rate: 37,500 coins for 5 inr.')}</b>"
        next_state = WAITING_FOR_BUY_AMOUNT
    elif query.data == "buy_prod_char":
        text = f"<b>{sc('send the character id you want to buy:')}</b>\n<i>({sc('the bot will auto-detect its rarity and price it accordingly.')})</i>"
        next_state = WAITING_FOR_BUY_CHAR_ID

    await send_buy_log(context, "📦 SELECTED", query.from_user, f"🆔 <b>ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n💬 <b>Aᴄᴛɪᴏɴ:</b> Sᴇʟᴇᴄᴛᴇᴅ <b>{query.data}</b>")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(sc("back"), callback_data="buy_back"), InlineKeyboardButton(sc("cancel"), callback_data="buy_cancel", icon_custom_emoji_id="6105159401239225894")]
    ])
    await query.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    return next_state

async def ask_buy_char_id(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    if not text: return WAITING_FOR_BUY_CHAR_ID

    live_char = await get_live_character_doc(text)
    if not live_char:
        await update.message.reply_html(f"<b>{E_WARN} {sc('character not found! please send a valid character id.')}</b>")
        return WAITING_FOR_BUY_CHAR_ID

    r = get_normalized_rarity(live_char.get('rarity'))
    
    settings = await bot_settings_collection.find_one({'_id': 'market_rarity_settings'})
    enabled_dict = settings.get('enabled', {}) if settings else {}
    
    if not enabled_dict.get(r, True):
        await update.message.reply_html(f"<b>{E_WARN} {sc('the rarity')} ({to_small_caps(r)}) {sc('is currently disabled for purchase!')}</b>")
        return WAITING_FOR_BUY_CHAR_ID

    coin_price = CHAR_PRICES_COINS.get(r, 1000)

    context.user_data['buy_char_id'] = live_char['id']
    context.user_data['buy_char_name'] = live_char.get('name')
    context.user_data['buy_char_rarity'] = r

    min_qty = max(1, math.ceil(37500 / coin_price))

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(sc("back"), callback_data="buy_back"), InlineKeyboardButton(sc("cancel"), callback_data="buy_cancel", icon_custom_emoji_id="6105159401239225894")]
    ])
    await update.message.reply_html(
        f"<b>{E_TICK} {sc('character found:')} {sc(live_char.get('name'))}</b>\n"
        f"<b>{sc('rarity:')} {sc(r)} ({sc('value:')} {coin_price:,} {sc('coins')})</b>\n\n"
        f"<b>{sc(f'send the quantity of this character you want to buy (min: {min_qty}, max: 100).')}</b>\n"
        f"<i>({sc('note: minimum purchase value is 5 inr / 37,500 coins')})</i>",
        reply_markup=kb
    )
    return WAITING_FOR_BUY_AMOUNT

async def ask_buy_amount(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0: return WAITING_FOR_BUY_AMOUNT
    
    amount = int(text)
    prod = context.user_data.get('buy_product')
    
    if prod == 't':
        if amount < 15 or amount > 1000:
            await update.message.reply_html(f"<b>{E_WARN} {sc('amount must be between 15 and 1000 tokens.')}</b>")
            return WAITING_FOR_BUY_AMOUNT
        price_inr = amount / 3
        disp_txt = f"{amount} {sc('tokens')}"
        
    elif prod == 'c':
        if amount < 37500 or amount > 2500000:
            await update.message.reply_html(f"<b>{E_WARN} {sc('amount must be between 37,500 and 2,500,000 coins.')}</b>")
            return WAITING_FOR_BUY_AMOUNT
        price_inr = amount / 7500
        disp_txt = f"{amount:,} {sc('coins')}"
        
    elif prod == 'char':
        r = context.user_data['buy_char_rarity']
        coin_price = CHAR_PRICES_COINS.get(r, 1000)
        min_qty = max(1, math.ceil(37500 / coin_price))
        
        if amount < min_qty or amount > 100:
            await update.message.reply_html(f"<b>{E_WARN} {sc(f'quantity must be between {min_qty} and 100 copies for this rarity.')}</b>")
            return WAITING_FOR_BUY_AMOUNT
            
        price_inr = (amount * coin_price) / 7500
        disp_txt = f"{amount}x {sc(context.user_data.get('buy_char_name'))}"

    order_id = context.user_data.get('buy_order_id', 'UNKNOWN')
    context.user_data['buy_amount'] = amount
    context.user_data['buy_price'] = price_inr

    await send_buy_log(context, "🪙 AMOUNT ENTERED", update.message.from_user, f"🆔 <b>ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n🪙 <b>Iᴛᴇᴍs:</b> {disp_txt}\n{E_MONEY} <b>Pʀɪᴄᴇ:</b> {price_inr:.2f} INR")

    caption = (
        f"<b>{E_TICK} {sc('order updated!')}</b>\n"
        f"<b>{sc('order id:')}</b> <code>{order_id}</code>\n\n"
        f"<b>{sc('item(s):')}</b> {disp_txt}\n"
        f"<b>{sc('total price:')} {price_inr:.2f} ɪɴʀ</b>\n\n"
        f"<b>{sc('pay inr to the following upi or qr in the image:')}</b>\n<b>UPI</b> <code>sasuke72@ptyes</code>\n\n"
        f"<b>{E_WAIT} {sc('please send the payment screenshot below to confirm your order.')}</b>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(sc("back"), callback_data="buy_back"), InlineKeyboardButton(sc("cancel"), callback_data="buy_cancel", icon_custom_emoji_id="6105159401239225894")]
    ])

    msg = await context.bot.send_photo(
        chat_id=update.message.chat_id,
        photo="https://files.catbox.moe/0qjgih.png",
        caption=caption, reply_markup=kb, parse_mode='HTML'
    )
    context.user_data['qr_msg_id'] = msg.message_id
    return WAITING_FOR_BUY_SCREENSHOT

async def receive_buy_screenshot(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if not update.message.photo: return WAITING_FOR_BUY_SCREENSHOT

    qr_msg_id = context.user_data.get('qr_msg_id')
    if qr_msg_id:
        try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=qr_msg_id)
        except Exception: pass

    photo_id = update.message.photo[-1].file_id
    order_id = context.user_data.get('buy_order_id', 'UNKNOWN')
    
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
    elif prod == 'char': disp_txt += f"x <b>{sc(context.user_data.get('buy_char_name'))}</b>"

    admin_text = (
        f"<b>🛒 ɴᴇᴡ ᴘᴜʀᴄʜᴀsᴇ ʀᴇǫᴜᴇsᴛ</b>\n"
        f"<b>👤 ᴜsᴇʀ:</b> <a href='tg://user?id={user_id}'>{html.escape(update.message.from_user.first_name)}</a> (<code>{user_id}</code>)\n"
        f"<b>🆔 ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n"
        f"<b>📦 ɪᴛᴇᴍ:</b> {disp_txt}\n"
        f"<b>{E_MONEY} ᴘᴀʏᴀʙʟᴇ:</b> <b>{price_inr:.2f} ɪɴʀ</b>"
    )
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❮", callback_data=f"b_adj:-1:{order_id}"),
            InlineKeyboardButton(f"{amount:,}", callback_data="ignore"),
            InlineKeyboardButton("❯", callback_data=f"b_adj:+1:{order_id}")
        ],
        [InlineKeyboardButton("ᴄᴏɴғɪʀᴍ", callback_data=f"b_cnf:{order_id}", icon_custom_emoji_id="6105024010985152856")],
        [InlineKeyboardButton("ᴄᴀɴᴄᴇʟ", callback_data=f"b_can:{order_id}", icon_custom_emoji_id="6105159401239225894")]
    ])
    
    await context.bot.send_photo(chat_id=BUY_LOG_GROUP_ID, photo=photo_id, caption=admin_text, reply_markup=kb, parse_mode='HTML')
    await update.message.reply_html(f"<b>{E_TICK} {sc('your payment screenshot has been sent to the admin. please wait for confirmation. items will be added to your wallet shortly.')}</b>")

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_buy_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.message.photo: 
        await query.message.delete()
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"<b>{E_CROSS} {sc('order cancelled.')}</b>", parse_mode='HTML')
    else: 
        await query.message.edit_text(f"<b>{E_CROSS} {sc('order cancelled.')}</b>", parse_mode='HTML')
        
    order_id = context.user_data.get('buy_order_id', 'UNKNOWN')
    await send_buy_log(context, "❌ CANCELLED", query.from_user, f"🆔 <b>ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n💬 <b>Aᴄᴛɪᴏɴ:</b> Usᴇʀ ᴄᴀɴᴄᴇʟʟᴇᴅ ᴛʜᴇ ᴘʀᴏᴄᴇss")
    context.user_data.clear()
    return ConversationHandler.END

async def admin_buy_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    if query.data == "ignore": return await query.answer()
    if query.from_user.id != OWNER_ID: return await query.answer(f"⚠️ {sc('only owner can approve this!')}", show_alert=True)

    data = query.data.split(':')
    action = data[0]
    order_id = data[-1]
    
    order = await bot_settings_collection.find_one({'_id': f"buy_{order_id}"})
    if not order: return await query.answer("⚠️ Order data not found!", show_alert=True)
    target_user_id = order['user_id']
    
    if action == "b_can":
        await query.edit_message_caption(caption=f"{query.message.caption_html}\n\n<b>{E_CROSS} ʀᴇᴊᴇᴄᴛᴇᴅ ʙʏ ᴀᴅᴍɪɴ</b>", parse_mode='HTML')
        try:
            await context.bot.send_message(chat_id=target_user_id, text=f"<b>{E_CROSS} {sc('your payment for order id')} <code>{order_id}</code> {sc('was rejected by admin. please contact support if this was a mistake.')}</b>", parse_mode='HTML')
        except Exception: pass
        return

    if action == "b_adj":
        cmd = data[1]
        new_amt = order['amount'] + (1 if cmd == '+1' else -1)
        if new_amt < 1: new_amt = 1
        
        if order['prod'] == 't':
            new_price = new_amt / 3
            disp_txt = f"<code>{new_amt}</code> <b>ᴛᴏᴋᴇɴs</b>"
        elif order['prod'] == 'c':
            new_price = new_amt / 7500
            disp_txt = f"<code>{new_amt:,}</code> <b>ᴄᴏɪɴs</b>"
        elif order['prod'] == 'char':
            live_char = await get_live_character_doc(order['char_id'])
            r = get_normalized_rarity(live_char.get('rarity') if live_char else '')
            new_price = (new_amt * CHAR_PRICES_COINS.get(r, 1000)) / 7500
            disp_txt = f"<code>{new_amt}</code>x <b>{sc(order['char_name'])}</b>"
            
        await bot_settings_collection.update_one({'_id': f"buy_{order_id}"}, {'$set': {'amount': new_amt, 'price_inr': new_price}})
        
        new_caption = (
            f"<b>🛒 ɴᴇᴡ ᴘᴜʀᴄʜᴀsᴇ ʀᴇǫᴜᴇsᴛ</b>\n"
            f"<b>👤 ᴜsᴇʀ:</b> <a href='tg://user?id={target_user_id}'>{html.escape(order['user_name'])}</a> (<code>{target_user_id}</code>)\n"
            f"<b>🆔 ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n"
            f"<b>📦 ɪᴛᴇᴍ:</b> {disp_txt}\n"
            f"<b>{E_MONEY} ᴘᴀʏᴀʙʟᴇ:</b> <b>{new_price:.2f} ɪɴʀ</b>"
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("❮", callback_data=f"b_adj:-1:{order_id}"),
                InlineKeyboardButton(f"{new_amt:,}", callback_data="ignore"),
                InlineKeyboardButton("❯", callback_data=f"b_adj:+1:{order_id}")
            ],
            [InlineKeyboardButton("ᴄᴏɴғɪʀᴍ", callback_data=f"b_cnf:{order_id}", icon_custom_emoji_id="6105024010985152856")],
            [InlineKeyboardButton("ᴄᴀɴᴄᴇʟ", callback_data=f"b_can:{order_id}", icon_custom_emoji_id="6105159401239225894")]
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
            msg_out = f"<code>{amount}</code> {sc('tokens')}"
        
        elif prod == "c":
            await eco_collection.update_one({'id': target_user_id}, {'$inc': {'balance': amount}}, upsert=True)
            msg_out = f"<code>{amount:,}</code> {sc('coins')}"

        elif prod == "char":
            char_doc = await get_live_character_doc(order['char_id'])
            if char_doc:
                copies = [char_doc for _ in range(amount)]
                await user_collection.update_one({'id': target_user_id}, {'$push': {'characters': {'$each': copies}}}, upsert=True)
            msg_out = f"<code>{amount}</code>x <b>{sc(order['char_name'])}</b>"

        await query.edit_message_caption(caption=f"{query.message.caption_html}\n\n<b>{E_TICK} ᴄᴏɴғɪʀᴍᴇᴅ & ᴅᴇʟɪᴠᴇʀᴇᴅ</b>", parse_mode='HTML')
        await bot_settings_collection.delete_one({'_id': f"buy_{order_id}"})

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"<b>{E_PARTY} {sc('payment confirmed!')}</b>\n\n<b>{msg_out} {sc('have been successfully added to your wallet. thank you for your purchase!')}</b>\n\n<b>{sc('order id:')}</b> <code>{order_id}</code>",
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
        await query.answer(f"⚠️ {sc('you cannot interact with this menu!')}\n{sc('please open your own market via')} /pmarket", show_alert=True)
        return

    action = parts[0]

    if action == "pm_b":
        buttons = []
        for key, (db_emoji, prem_html, name) in RARITIES.items():
            match = re.search(r'emoji-id="(\d+)"', prem_html)
            emoji_id = match.group(1) if match else None
            buttons.append(InlineKeyboardButton(f"{sc(name)}", callback_data=f"pm_r:{key}:{user_id}", icon_custom_emoji_id=emoji_id))
        
        keyboard = chunk(buttons, 2)
        keyboard.append([InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_m:{user_id}")])
        
        await update_menu(query, f"<b><tg-emoji emoji-id=\"5312361253610475399\">🛒</tg-emoji> {sc('buy characters from market')}</b>\n\n<i>{sc('select a rarity to view products.')}</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_m":
        bot_username = context.bot.username
        keyboard = await get_pmarket_keyboard(user_id, bot_username)
        await update_menu(query, f"<b><tg-emoji emoji-id=\"5278702045883292456\">🛍</tg-emoji> P2P ᴍᴀʀᴋᴇᴛᴘʟᴀᴄᴇ</b>\n\n<i>{sc('choose an option to proceed.')}</i>", keyboard)

    elif action == "pm_exc_menu":
        global_limit, used_today, _ = await get_token_limit_info(user_id)
        limit_text = f"{E_INF}" if user_id == OWNER_ID else f"{global_limit - used_today} {sc('left today')}"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(sc("get coins"), callback_data=f"pm_start_exc_t2c:{user_id}", icon_custom_emoji_id="5472030678633684592"),
             InlineKeyboardButton(sc("get token"), callback_data=f"pm_start_exc_c2t:{user_id}", icon_custom_emoji_id="5377336227533969892")],
            [InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_m:{user_id}")]
        ])
        await update_menu(query, f"<b>{E_EXC} {sc('exchange menu')}</b>\n\n<i>{sc('daily limit:')} {limit_text}</i>\n<i>{sc('what would you like to do?')}</i>", keyboard)

    elif action == "pm_r":
        rarity_key = parts[1]
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(sc("price low to high"), callback_data=f"pm_s:{rarity_key}:asc:{user_id}")],
            [InlineKeyboardButton(sc("price high to low"), callback_data=f"pm_s:{rarity_key}:desc:{user_id}")],
            [InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_b:{user_id}")]
        ])
        
        _, prem_emoji, name = RARITIES.get(rarity_key, RARITIES["common"])
        await update_menu(query, f"<b>{prem_emoji} {sc(name)} {sc('characters')}</b>\n\n<i>{sc('how do you want to sort them?')}</i>", keyboard)

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
            await query.answer(f"⚠️ {sc('no characters are currently for sale in this rarity!')}", show_alert=True)
            return

        keyboard = []
        for item in market_items:
            char = item['character']
            char_name = char.get('name', 'Unknown')
            price = item['price']
            market_id = str(item['_id'])
            
            char_rarity_str = str(char.get('rarity', '')).strip()
            rarity_key_for_char = get_normalized_rarity(char_rarity_str)
            _, prem_html, _ = RARITIES.get(rarity_key_for_char, RARITIES["common"])
            match = re.search(r'emoji-id="(\d+)"', prem_html)
            emoji_id = match.group(1) if match else None
            
            btn_text = f"{sc(char_name)} - {price:,}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pm_v:{market_id}:{order}:{user_id}", icon_custom_emoji_id=emoji_id)])
        
        sort_text = sc("low to high") if order == "asc" else sc("high to low")
        keyboard.append([InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_r:{rarity_key}:{user_id}")])

        await update_menu(query, f"<b>{prem_emoji} {sc('characters for sale')}</b>\n\n<i>{sc('sorted by price (')} {sort_text} {sc(')')}</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_v":
        market_id = parts[1]
        order = parts[2]
        
        item = await market_collection.find_one({'_id': ObjectId(market_id)})
        
        if not item:
            await query.answer(f"❌ {sc('oops! this character has already been sold or removed!')}", show_alert=True)
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

        rarity_key = get_normalized_rarity(char_rarity_str)

        caption = (
            f"<b>{prem_emoji} {sc(display_char.get('name', 'Unknown'))}</b>\n\n"
            f"<b><tg-emoji emoji-id=\"6314494724266796319\">🟠</tg-emoji> ᴀɴɪᴍᴇ:</b> {sc(display_char.get('anime', 'Unknown'))}\n"
            f"<b><tg-emoji emoji-id=\"5260426225599405269\">🪄</tg-emoji> ʀᴀʀɪᴛʏ:</b> {prem_emoji} {sc(name)}\n"
            f"<b>{E_MONEY} ᴘʀɪᴄᴇ:</b> <code>{price:,}</code>\n"
            f"<b><tg-emoji emoji-id=\"6332443074769196273\">🆔</tg-emoji> sᴇʟʟᴇʀ:</b> <code>{seller_id}</code>"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(sc("buy now"), callback_data=f"pm_buy:{market_id}:{user_id}", icon_custom_emoji_id="5312361253610475399")],
            [InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_s:{rarity_key}:{order}:{user_id}")]
        ])

        try:
            await query.message.delete()
        except Exception:
            pass

        msg = await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=display_char.get('img_url', 'https://files.catbox.moe/0qjgih.png'), 
            caption=caption,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        # Auto delete exactly after 20 minutes (1200 seconds) silently
        asyncio.create_task(delete_message_later(context.bot, msg.chat_id, msg.message_id, 1200))

    elif action == "pm_buy":
        market_id = parts[1]
        
        item = await market_collection.find_one({'_id': ObjectId(market_id)})
        if not item:
            await query.answer(f"⚠️ {sc('too late! this character has already been bought by someone else.')}", show_alert=True)
            return

        price = item['price']
        seller_id = item['seller_id']
        char = item['character']
        
        if seller_id == user_id:
            await query.answer(f"⚠️ {sc('you cannot buy your own character!')}", show_alert=True)
            return

        eco_buyer = await eco_collection.find_one_and_update(
            {'id': user_id, 'balance': {'$gte': price}},
            {'$inc': {'balance': -price}}
        )

        if not eco_buyer:
            await query.answer(f"⚠️ {sc('insufficient funds! you need')} {price:,} {sc('balance.')}", show_alert=True)
            return

        # 🔥 SMART LAZY-DELETE SYSTEM: Check seller's inventory BEFORE buying 🔥
        seller_doc = await user_collection.find_one({'id': seller_id})
        seller_chars = seller_doc.get('characters', []) if seller_doc else []
        
        char_found_idx = -1
        for i, c in enumerate(seller_chars):
            if str(c.get('id')) == str(char.get('id')):
                char_found_idx = i
                break
                
        if char_found_idx == -1:
            # Revert buyer's money
            await eco_collection.update_one({'id': user_id}, {'$inc': {'balance': price}})
            # Delete invalid listing
            await market_collection.delete_one({'_id': ObjectId(market_id)})
            await query.answer(f"⚠️ {sc('the seller no longer owns this character! listing has been automatically removed.')}", show_alert=True)
            return

        # Everything is valid, delete from market collection
        deleted_item = await market_collection.find_one_and_delete({'_id': ObjectId(market_id)})
        
        if not deleted_item:
            # Edge case handling if someone bought at exactly same millisecond
            await eco_collection.update_one({'id': user_id}, {'$inc': {'balance': price}})
            await query.answer(f"⚠️ {sc('too late! this character has already been bought by someone else.')}", show_alert=True)
            return

        # Remove EXACTLY ONE copy from seller's collection
        del seller_chars[char_found_idx]

        await asyncio.gather(
            user_collection.update_one({'id': user_id}, {'$push': {'characters': char}}),
            user_collection.update_one({'id': seller_id}, {'$set': {'characters': seller_chars}}),
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
            caption=f"<b>{E_PARTY} {sc('congratulations! you successfully bought')} {sc(char.get('name'))} {sc('for')} {E_MONEY} {price:,}.</b>",
            parse_mode='HTML'
        )

    elif action == "pm_sm":
        cursor = market_collection.find({'seller_id': user_id}).limit(50)
        listings = await cursor.to_list(length=50)
        
        keyboard = [[InlineKeyboardButton(sc("list new character"), callback_data=f"pm_start_s:{user_id}", icon_custom_emoji_id="6109452611893601414")]]
        
        for item in listings:
            char_name = sc(item['character'].get('name', 'Unknown'))
            price = item['price']
            market_id = str(item['_id'])
            
            btn_text = f"{sc('cancel')} | {char_name} - {price:,}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pm_delist:{market_id}:{user_id}", icon_custom_emoji_id="5472030678633684592")])
            
        keyboard.append([InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_m:{user_id}")])
        
        await update_menu(query, f"<b>{E_MONEY} {sc('your active listings')}</b>\n\n<i>{sc('manage your current listings or add a new one.')}</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_delist":
        market_id = parts[1]
        item = await market_collection.find_one({'_id': ObjectId(market_id)})
        
        if not item:
            await query.answer(f"⚠️ {sc('this item is no longer on the market.')}", show_alert=True)
        else:
            char = item['character']
            await market_collection.delete_one({'_id': ObjectId(market_id)})
            
            user_name = update.effective_user.first_name
            seller_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"
            
            log_details = (
                f"👤 <b>Sᴇʟʟᴇʀ:</b> {seller_mention}\n"
                f"🎭 <b>Cʜᴀʀᴀᴄᴛᴇʀ:</b> {char.get('name')} (<code>{char.get('id')}</code>)\n"
                f"❌ <b>Aᴄᴛɪᴏɴ:</b> Rᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ ᴍᴀʀᴋᴇᴛ."
            )
            await send_market_log(context, "📉 CHARACTER DELISTED", log_details)

            await query.answer(f"✅ {sc('successfully removed from market!')}", show_alert=True)
        
        cursor = market_collection.find({'seller_id': user_id}).limit(50)
        listings = await cursor.to_list(length=50)
        keyboard = [[InlineKeyboardButton(sc("list new character"), callback_data=f"pm_start_s:{user_id}", icon_custom_emoji_id="6109452611893601414")]]
        for item in listings:
            char_name = sc(item['character'].get('name', 'Unknown'))
            price = item['price']
            m_id = str(item['_id'])
            
            btn_text = f"{sc('cancel')} | {char_name} - {price:,}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pm_delist:{m_id}:{user_id}", icon_custom_emoji_id="5472030678633684592")])
            
        keyboard.append([InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_m:{user_id}")])
        await update_menu(query, f"<b>{sc('your active listings')}</b>\n\n<i>{sc('manage your current listings or add a new one.')}</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_exc_conf":
        exc_type = parts[1]  
        amount = int(parts[2]) 
        
        global_limit, used_today, today_str = await get_token_limit_info(user_id)
        if user_id != OWNER_ID:
            if amount + used_today > global_limit:
                available = max(0, global_limit - used_today)
                await query.answer(f"⚠️ {sc('daily limit reached! you can only exchange')} {available} {sc('more tokens today.')}", show_alert=True)
                return

        kb = InlineKeyboardMarkup([[InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_exc_menu:{user_id}")]])

        user_name = update.effective_user.first_name
        user_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"

        if exc_type == "t2c":
            coins_to_add = amount * 2500
            eco_user = await eco_collection.find_one_and_update(
                {'id': user_id, 'tokens': {'$gte': amount}},
                {'$inc': {'tokens': -amount, 'balance': coins_to_add}}
            )
            if not eco_user:
                await query.answer(f"⚠️ {sc('you do not have enough tokens anymore!')}", show_alert=True)
                return
                
            msg = f"<b>{E_TICK} {sc('successfully exchanged')} <code>{amount}</code> {sc('tokens into')} <code>{coins_to_add:,}</code> {sc('coins!')}</b>"
            log_action = "🔄 TOKENS TO COINS"
            log_details = f"👤 <b>Usᴇʀ:</b> {user_mention}\n📉 <b>Sᴏʟᴅ:</b> {amount} ᴛᴏᴋᴇɴs\n📈 <b>Rᴇᴄᴇɪᴠᴇᴅ:</b> {coins_to_add:,} ᴄᴏɪɴs"

        elif exc_type == "c2t":
            coins_to_deduct = amount * 2500
            eco_user = await eco_collection.find_one_and_update(
                {'id': user_id, 'balance': {'$gte': coins_to_deduct}},
                {'$inc': {'balance': -coins_to_deduct, 'tokens': amount}}
            )
            if not eco_user:
                await query.answer(f"⚠️ {sc('you do not have enough coins anymore!')}", show_alert=True)
                return
            
            msg = f"<b>{E_TICK} {sc('successfully spent')} <code>{coins_to_deduct:,}</code> {sc('coins to buy')} <code>{amount}</code> {sc('tokens!')}</b>"
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
async def cancel_process(update: Update, context: CallbackContext):
    qr_msg_id = context.user_data.get('qr_msg_id')
    if qr_msg_id:
        try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=qr_msg_id)
        except Exception: pass

    await clear_existing_states(context)
    await update.message.reply_text(f"<b>{E_CROSS} {sc('process cancelled.')}</b>", parse_mode='HTML')
    return ConversationHandler.END

async def timeout_process(update: Update, context: CallbackContext):
    qr_msg_id = context.user_data.get('qr_msg_id')
    if qr_msg_id:
        try:
            chat_id = update.effective_chat.id if update.effective_chat else update.callback_query.message.chat_id
            await context.bot.delete_message(chat_id=chat_id, message_id=qr_msg_id)
        except Exception: pass

    await clear_existing_states(context)
    
    msg = f"<b>{E_TIME} {sc('session expired due to inactivity. please start again.')}</b>"
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
        await query.answer(f"⚠️ {sc('you cannot interact with this menu!')}", show_alert=True)
        return ConversationHandler.END
        
    if context.user_data.get('sell_active'):
        await query.answer(f"⚠️ {sc('already started your process! complete it or type')} /cancel {sc('first.')}", show_alert=True)
        return context.user_data.get('sell_step', WAITING_FOR_CHARACTER_ID)
        
    await clear_existing_states(context)
    await query.answer()
    
    context.user_data['sell_owner_id'] = owner_id
    context.user_data['sell_active'] = True
    context.user_data['sell_step'] = WAITING_FOR_CHARACTER_ID

    await query.message.reply_text(
        f"{E_MONEY} <b>{sc('send the character id you want to sell:')}</b>\n\n({sc('type')} /cancel {sc('to abort the process')})",
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
    
    if not user_data or 'characters' not in user_data:
        return WAITING_FOR_CHARACTER_ID

    character = None
    for c in user_data.get('characters', []):
        db_id = str(c.get('id')).strip()
        if db_id == char_id or (db_id.isdigit() and char_id.isdigit() and int(db_id) == int(char_id)):
            character = c
            break
            
    if not character:
        return WAITING_FOR_CHARACTER_ID

    context.user_data['sell_character'] = character
    context.user_data['sell_step'] = WAITING_FOR_PRICE
    
    await update.message.reply_text(
        f"{E_TICK} <b>{sc('character found! now send price')}</b>\n\n"
        f"{sc('selected:')} <b>{sc(character.get('name'))}</b>\n"
        f"<i>{sc('enter the price (in')} {E_MONEY}{sc(') you want to sell it for.')}</i>",
        parse_mode='HTML'
    )
    return WAITING_FOR_PRICE

async def ask_price(update: Update, context: CallbackContext):
    if not update.message or not update.message.text: return WAITING_FOR_PRICE
    user_id = update.message.from_user.id
    expected_owner = context.user_data.get('sell_owner_id')
    if expected_owner and user_id != expected_owner: return WAITING_FOR_PRICE

    price_text = update.message.text.strip()
    if not price_text.isdigit() or int(price_text) <= 0:
        return WAITING_FOR_PRICE

    price = int(price_text)
    if price > 1000000:
        await update.message.reply_text(f"<b>{E_WARN} {sc('maximum price limit is 1,000,000 coins. please enter a lower amount.')}</b>", parse_mode='HTML')
        return WAITING_FOR_PRICE

    character = context.user_data.get('sell_character')
    if not character:
        await update.message.reply_text(f"<b>{sc('session expired. please start again via')} /pmarket</b>", parse_mode='HTML')
        return ConversationHandler.END

    char_id_val = str(character['id'])
    live_char = await get_live_character_doc(char_id_val)
    final_character = live_char if live_char else character

    # 🔥 DUPLICATE LISTING LOGIC CHECK 🔥
    user_doc = await user_collection.find_one({'id': user_id})
    owned_count = 0
    if user_doc and 'characters' in user_doc:
        for c in user_doc['characters']:
            if str(c.get('id')) == char_id_val:
                owned_count += 1
                
    listed_count = await market_collection.count_documents({
        'seller_id': user_id, 
        '$or': [{'character.id': char_id_val}, {'character.id': int(char_id_val) if char_id_val.isdigit() else char_id_val}]
    })
    
    if listed_count >= owned_count:
        await update.message.reply_text(f"⚠️ <b>{sc('you have already listed all your copies of this character on the market!')}</b>", parse_mode='HTML')
        await clear_existing_states(context)
        return ConversationHandler.END

    # Add to market BUT NOT remove from inventory (Lazy sync logic)
    await market_collection.insert_one({'seller_id': user_id, 'price': price, 'character': final_character})

    user_name = update.message.from_user.first_name
    user_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"

    log_details = (
        f"👤 <b>Sᴇʟʟᴇʀ:</b> {user_mention}\n"
        f"🎭 <b>Cʜᴀʀᴀᴄᴛᴇʀ:</b> {final_character.get('name')} (<code>{final_character.get('id')}</code>)\n"
        f"💰 <b>Pʀɪᴄᴇ Sᴇᴛ:</b> {price:,} ᴄᴏɪɴs"
    )
    await send_market_log(context, "📈 CHARACTER LISTED", log_details)

    await clear_existing_states(context)
    
    await update.message.reply_text(
        f"<b>{E_PARTY} {sc(final_character.get('name'))} {sc('has been successfully listed on the market for')} {E_MONEY} {price:,}!</b>",
        parse_mode='HTML'
    )
    return ConversationHandler.END


# --- 2. EXCHANGE CONVERSATION (T2C and C2T) ---
async def exchange_start_t2c(update: Update, context: CallbackContext):
    query = update.callback_query
    parts = query.data.split(':')
    owner_id = int(parts[-1])
    
    if query.from_user.id != owner_id:
        await query.answer(f"⚠️ {sc('you cannot interact with this menu!')}", show_alert=True)
        return ConversationHandler.END
        
    await clear_existing_states(context)
    await query.answer()
    context.user_data['exc_owner_id'] = owner_id
    context.user_data['exc_type'] = 't2c'
    
    user = await eco_collection.find_one({'id': owner_id})
    tokens = user.get('tokens', 0) if user else 0

    await query.message.reply_text(
        f"<b>{E_EXC} {sc('how many tokens do you want to sell for coins?')}</b>\n\n"
        f"<i>{sc('1 token = 2,500 coins.')}</i>\n"
        f"<b>{sc('you have:')}</b> <code>{tokens:,}</code> {sc('tokens')}\n\n"
        f"({sc('enter the number of tokens, e.g. type')} <b>1</b> {sc('to get 2500 coins')})\n"
        f"({sc('type')} /cancel {sc('to abort the process')})",
        parse_mode="HTML"
    )
    return WAITING_FOR_EXCHANGE_AMOUNT

async def exchange_start_c2t(update: Update, context: CallbackContext):
    query = update.callback_query
    parts = query.data.split(':')
    owner_id = int(parts[-1])
    
    if query.from_user.id != owner_id:
        await query.answer(f"⚠️ {sc('you cannot interact with this menu!')}", show_alert=True)
        return ConversationHandler.END
        
    await clear_existing_states(context)
    await query.answer()
    context.user_data['exc_owner_id'] = owner_id
    context.user_data['exc_type'] = 'c2t'
    
    user = await eco_collection.find_one({'id': owner_id})
    coins = user.get('balance', 0) if user else 0

    await query.message.reply_text(
        f"<b>{E_EXC} {sc('how many tokens do you want to buy with coins?')}</b>\n\n"
        f"<i>{sc('2,500 coins = 1 token.')}</i>\n"
        f"<b>{sc('you have:')}</b> <code>{coins:,}</code> {sc('coins')}\n\n"
        f"({sc('enter the number of tokens, e.g. type')} <b>1</b> {sc('to spend 2500 coins')})\n"
        f"({sc('type')} /cancel {sc('to abort the process')})",
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
    if not amount_text.isdigit() or int(amount_text) <= 0:
        return WAITING_FOR_EXCHANGE_AMOUNT

    amount = int(amount_text)
    global_limit, used_today, _ = await get_token_limit_info(user_id)
    if user_id != OWNER_ID:
        if amount + used_today > global_limit:
            available = max(0, global_limit - used_today)
            await update.message.reply_text(
                f"{E_WARN} <b>{sc('daily limit exceeded!')}</b>\n"
                f"{sc('you can only exchange')} <code>{global_limit}</code> {sc('tokens per day.')}\n"
                f"{sc('you have')} <code>{available}</code> {sc('tokens left for today.')}", 
                parse_mode='HTML'
            )
            return WAITING_FOR_EXCHANGE_AMOUNT

    user = await eco_collection.find_one({'id': user_id})
    tokens = user.get('tokens', 0) if user else 0
    coins = user.get('balance', 0) if user else 0
    
    if exc_type == 't2c':
        if amount > tokens:
            await update.message.reply_text(f"<b>{sc('you do not have enough tokens! you only have')} <code>{tokens:,}</code> {sc('tokens.')}</b>", parse_mode='HTML')
            return WAITING_FOR_EXCHANGE_AMOUNT
        total_coins = amount * 2500
        text_msg = f"<i>{sc('are you sure you want to exchange')} <code>{amount}</code> {sc('tokens to get')} <code>{total_coins:,}</code> {sc('coins?')}</i>"
        
    elif exc_type == 'c2t':
        cost = amount * 2500
        if cost > coins:
            await update.message.reply_text(f"<b>{sc('you do not have enough coins! you only have')} <code>{coins:,}</code> {sc('coins.')}</b>\n<i>({sc('you need')} <code>{cost:,}</code> {sc('coins to buy')} <code>{amount}</code> {sc('tokens')})</i>", parse_mode='HTML')
            return WAITING_FOR_EXCHANGE_AMOUNT
        text_msg = f"<i>{sc('are you sure you want to spend')} <code>{cost:,}</code> {sc('coins to get')} <code>{amount}</code> {sc('tokens?')}</i>"
        
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(sc("confirm"), callback_data=f"pm_exc_conf:{exc_type}:{amount}:{user_id}", icon_custom_emoji_id="6105024010985152856")],
        [InlineKeyboardButton(sc("cancel"), callback_data=f"pm_exc_menu:{user_id}", icon_custom_emoji_id="6105159401239225894")]
    ])
    
    await update.message.reply_text(
        f"<b>{sc('confirm exchange')}</b>\n\n{text_msg}",
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    
    await clear_existing_states(context)
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
            CallbackQueryHandler(buy_back_callback, pattern='^buy_back$'),
            CallbackQueryHandler(cancel_buy_callback, pattern='^buy_cancel$')
        ],
        WAITING_FOR_BUY_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, ask_buy_amount),
            CallbackQueryHandler(buy_back_callback, pattern='^buy_back$'),
            CallbackQueryHandler(cancel_buy_callback, pattern='^buy_cancel$')
        ],
        WAITING_FOR_BUY_SCREENSHOT: [
            MessageHandler(filters.PHOTO, receive_buy_screenshot),
            CallbackQueryHandler(buy_back_callback, pattern='^buy_back$'),
            CallbackQueryHandler(cancel_buy_callback, pattern='^buy_cancel$')
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_process), CommandHandler("buy", buy_command_pm)],
    allow_reentry=True,
    per_user=True,
    per_chat=True,
)

application.add_handler(sell_conv, group=-1)
application.add_handler(exchange_conv, group=-2)
application.add_handler(buy_conv, group=-3) 

application.add_handler(CommandHandler(["pmarket", "exchange", "shop"], pmarket_command, block=False), group=0)
application.add_handler(CommandHandler("toggle_exchange", toggle_exchange_cmd, block=False), group=0)
application.add_handler(CommandHandler("set_exchange_limit", set_exchange_limit_cmd, block=False), group=0)
application.add_handler(CommandHandler("forcedelist", force_delist_cmd, block=False), group=0)
application.add_handler(CommandHandler("mrarity_on", mrarity_on_cmd, block=False), group=0)
application.add_handler(CommandHandler("mrarity_off", mrarity_off_cmd, block=False), group=0)

application.add_handler(CallbackQueryHandler(pmarket_callbacks, pattern='^(pm_m|pm_b|pm_r|pm_s|pm_v|pm_buy|pm_sm|pm_delist|pm_exc_conf|pm_exc_menu):', block=False), group=0)

# Global Callback handler for admin confirm/cancel/adjust 
application.add_handler(CallbackQueryHandler(admin_buy_callback, pattern='^(b_adj|b_cnf|b_can|ignore)', block=False), group=0)

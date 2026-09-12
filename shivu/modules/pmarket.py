import asyncio
import html
import uuid
import re
import math
import time
from datetime import datetime, timedelta
from bson import ObjectId
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update, InputMediaPhoto, InputMediaVideo, InputMediaAnimation
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, filters, TypeHandler
from shivu import application, db

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
SHOP_IMG = "https://files.catbox.moe/qormfi.png"
SHOP_AUTO_DELETE_SECONDS = 20 * 60
PER_PAGE = 8  # 🔥 chars per page everywhere

# --- DATABASE COLLECTIONS ---
user_collection = db['user_collection_lmaoooo']
market_collection = db['market_collection']
bot_settings_collection = db['bot_settings']
delete_collection = db['auto_delete_queue']

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

_worker_started = False

async def background_delete_worker(bot):
    try:
        await delete_collection.create_index("delete_at")
        await delete_collection.create_index([("chat_id", 1), ("message_id", 1)])
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
        await asyncio.sleep(10)

async def ensure_delete_worker(bot):
    global _worker_started
    if not bot:
        return
    if not _worker_started:
        _worker_started = True
        asyncio.create_task(background_delete_worker(bot))

async def delete_message_later(bot, chat_id, message_id, delay=SHOP_AUTO_DELETE_SECONDS):
    if not bot or not chat_id or not message_id:
        return
    await ensure_delete_worker(bot)
    delete_at = time.time() + delay
    try:
        await delete_collection.update_one(
            {'chat_id': chat_id, 'message_id': message_id},
            {'$set': {'chat_id': chat_id, 'message_id': message_id, 'delete_at': delete_at}},
            upsert=True
        )
    except Exception:
        pass

async def schedule_shop_autodelete(bot, chat_id, message_id):
    await delete_message_later(bot, chat_id, message_id, SHOP_AUTO_DELETE_SECONDS)

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

async def get_live_character_doc(char_id):
    if char_id is None:
        return None
    char_str = str(char_id).strip()
    query_conditions = [{'id': char_str}]
    if char_str.isdigit():
        num = int(char_str)
        query_conditions.extend([{'id': num}, {'id': str(num)}, {'id': f"{num:02d}"}])
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

SMALL_CAPS_TRANS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
)

def to_small_caps(text: str) -> str:
    if not text:
        return ""
    return str(text).translate(SMALL_CAPS_TRANS)

sc = to_small_caps

# ============================================================
# 🔥 UNIFIED RARITY MAP (keys now MATCH CHAR_PRICES_COINS) 🔥
# ============================================================
RARITIES = {
    "common":          ("🟢", '<tg-emoji emoji-id="6093865707424980866">🟢</tg-emoji>', "Common"),
    "rare":            ("🟠", '<tg-emoji emoji-id="5339390195768774311">🟠</tg-emoji>', "Rare"),
    "legendary":       ("🟡", '<tg-emoji emoji-id="6084550327086883643">🟡</tg-emoji>', "Legendary"),
    "medium":          ("🔴", '<tg-emoji emoji-id="6093741664474504699">🔴</tg-emoji>', "Medium"),
    "celestial":       ("🪽", '<tg-emoji emoji-id="5434121252874756456">🪽</tg-emoji>', "Celestial"),
    "spicy":           ("🥵", '<tg-emoji emoji-id="6093490292923574796">🥵</tg-emoji>', "Spicy"),
    "exclusive":       ("💮", '<tg-emoji emoji-id="6100567406889935797">💮</tg-emoji>', "Exclusive"),
    "cosmic":          ("🌌", '<tg-emoji emoji-id="5431783411981228752">🌌</tg-emoji>', "Cosmic"),
    "mythic":          ("💎", '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>', "Mythic"),
    "sweet":           ("🍭", '<tg-emoji emoji-id="6222115531122546353">🍭</tg-emoji>', "Sweet"),
    "valentine":       ("💞", '<tg-emoji emoji-id="5255861796350224063">💞</tg-emoji>', "Valentine"),
    "winter":          ("❄️", '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>', "Winter"),
    "neon":            ("⚡", '<tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>', "Neon"),
    "summer":          ("🏝️", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"),
    "premium edition": ("🔮", '<tg-emoji emoji-id="6093919703753831564">🔮</tg-emoji>', "Premium Edition"),
}

CHAR_PRICES_COINS = {
    "common": 1000, "rare": 10000, "medium": 8000,
    "legendary": 15000, "celestial": 70000, "spicy": 99000,
    "exclusive": 30000, "mythic": 180000, "premium edition": 250000,
    "sweet": 62000, "valentine": 90000, "winter": 59000,
    "neon": 67000, "summer": 65000, "cosmic": 740000
}

# 🔥 Keyword-based detection (handles emoji-spelled + old DB names) 🔥
RARITY_KEYWORDS = {
    "premium edition": ["premium edition", "premium", "🔮"],
    "spicy":           ["spicy", "erotic", "🥵"],
    "medium":          ["medium", "special", "🔴"],
    "summer":          ["summer", "pearl", "🏝", "🏖"],
    "cosmic":          ["cosmic", "🌌"],
    "celestial":       ["celestial", "🪽"],
    "mythic":          ["mythic", "💎"],
    "exclusive":       ["exclusive", "💮"],
    "legendary":       ["legendary", "🟡"],
    "sweet":           ["sweet", "🍭"],
    "valentine":       ["valentine", "💞"],
    "winter":          ["winter", "❄️"],
    "neon":            ["neon", "⚡"],
    "rare":            ["rare", "🟠"],
    "common":          ["common", "🟢"],
}

def get_normalized_rarity(rarity_str):
    """Robust: matches emoji + DB names + old keywords. Never falsely returns common."""
    if not rarity_str:
        return "common"
    r = str(rarity_str).lower().strip()
    # match longest keys first (premium edition before premium, etc.)
    for key in sorted(RARITY_KEYWORDS.keys(), key=lambda x: -len(x)):
        for kw in RARITY_KEYWORDS[key]:
            if kw.lower() in r:
                return key
    return "common"

def get_rarity_display(rarity_str):
    """Returns (db_emoji, premium_html_emoji, display_name)"""
    key = get_normalized_rarity(rarity_str)
    return RARITIES.get(key, RARITIES["common"])

def chunk(items: list, size: int) -> list:
    return [items[i:i + size] for i in range(0, len(items), size)]

def extract_emoji_id(prem_html):
    match = re.search(r'emoji-id="(\d+)"', prem_html)
    return match.group(1) if match else None

async def update_menu(query, text, keyboard, change_media=False, photo_url=SHOP_IMG, is_video=False):
    try:
        if change_media:
            media_str = str(photo_url).lower()
            if is_video or media_str.endswith(('.mp4', '.mkv', '.webm')):
                try:
                    await query.edit_message_media(media=InputMediaVideo(media=photo_url, caption=text, parse_mode='HTML'), reply_markup=keyboard)
                except Exception:
                    await query.edit_message_media(media=InputMediaAnimation(media=photo_url, caption=text, parse_mode='HTML'), reply_markup=keyboard)
            elif media_str.endswith('.gif'):
                try:
                    await query.edit_message_media(media=InputMediaAnimation(media=photo_url, caption=text, parse_mode='HTML'), reply_markup=keyboard)
                except Exception:
                    await query.edit_message_media(media=InputMediaVideo(media=photo_url, caption=text, parse_mode='HTML'), reply_markup=keyboard)
            else:
                try:
                    await query.edit_message_media(media=InputMediaPhoto(media=photo_url, caption=text, parse_mode='HTML'), reply_markup=keyboard)
                except Exception:
                    try:
                        await query.edit_message_media(media=InputMediaVideo(media=photo_url, caption=text, parse_mode='HTML'), reply_markup=keyboard)
                    except Exception:
                        await query.edit_message_media(media=InputMediaAnimation(media=photo_url, caption=text, parse_mode='HTML'), reply_markup=keyboard)
        else:
            if query.message.photo or query.message.video or query.message.animation or query.message.document:
                await query.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode='HTML')
            else:
                await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    except Exception:
        pass
    finally:
        try:
            await query.answer()
        except:
            pass
        try:
            bot = None
            try:
                bot = query.get_bot()
            except Exception:
                bot = None
            if bot is None and query.message is not None:
                try:
                    bot = query.message.get_bot()
                except Exception:
                    bot = None
            if bot and query.message:
                await schedule_shop_autodelete(bot, query.message.chat_id, query.message.message_id)
        except Exception:
            pass

async def clear_existing_states(context: CallbackContext):
    keys = ['sell_owner_id', 'sell_character', 'sell_active', 'sell_step', 'exc_owner_id', 'exc_type',
            'buy_prompt_active', 'buy_product', 'buy_char_id', 'buy_amount', 'buy_price', 'qr_msg_id']
    for k in keys:
        context.user_data.pop(k, None)

# --- BUY SESSION PERSISTENCE ---
BUY_SESSION_KEYS = [
    'buy_order_id', 'buy_product', 'buy_char_id', 'buy_char_name',
    'buy_char_rarity', 'buy_amount', 'buy_price', 'buy_prompt_active',
    'qr_msg_id', 'shop_msg_id', 'buy_chat_id'
]

def _buy_session_id(user_id):
    return f'buy_session_{user_id}'

async def save_buy_session(user_id, context: CallbackContext, state):
    if not user_id:
        return
    data = {k: context.user_data.get(k) for k in BUY_SESSION_KEYS}
    data['state'] = state
    data['user_id'] = user_id
    data['updated_at'] = time.time()
    try:
        await bot_settings_collection.update_one({'_id': _buy_session_id(user_id)}, {'$set': data}, upsert=True)
    except Exception:
        pass

async def load_buy_session(user_id):
    if not user_id:
        return None
    try:
        return await bot_settings_collection.find_one({'_id': _buy_session_id(user_id)})
    except Exception:
        return None

async def clear_buy_session(user_id):
    if not user_id:
        return
    try:
        await bot_settings_collection.delete_one({'_id': _buy_session_id(user_id)})
    except Exception:
        pass

def apply_buy_session(context: CallbackContext, session):
    if not session:
        return
    for k in BUY_SESSION_KEYS:
        if session.get(k) is not None:
            context.user_data[k] = session[k]

async def ensure_buy_user_data(context: CallbackContext, user_id):
    if context.user_data.get('buy_order_id'):
        return True
    session = await load_buy_session(user_id)
    if not session:
        return False
    apply_buy_session(context, session)
    return True

async def get_pmarket_keyboard(user_id, bot_username=""):
    settings = await bot_settings_collection.find_one({'_id': 'pmarket_settings'})
    exchange_enabled = settings.get('exchange_enabled', True) if settings else True
    keyboard = []
    if exchange_enabled:
        keyboard.append([InlineKeyboardButton(sc("ᴇxᴄʜᴀɴɢᴇ"), callback_data=f"pm_exc_menu:{user_id}", icon_custom_emoji_id="5377336227533969892")])
    keyboard.append([
        InlineKeyboardButton(sc("ʙᴜʏ"), callback_data=f"pm_b:{user_id}", icon_custom_emoji_id="5312361253610475399"),
        InlineKeyboardButton(sc("sᴇʟʟ"), callback_data=f"pm_sm:0:{user_id}", icon_custom_emoji_id="5472030678633684592")
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
    msg = await update.message.reply_photo(
        photo=SHOP_IMG,
        caption="<b><tg-emoji emoji-id=\"5278702045883292456\">🛍</tg-emoji> P2P ᴍᴀʀᴋᴇᴛᴘʟᴀᴄᴇ</b>\n\n<i>ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ.</i>",
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    context.user_data['shop_msg_id'] = msg.message_id
    await schedule_shop_autodelete(context.bot, update.effective_chat.id, msg.message_id)

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
# BUY TOKENS/COINS/CHARS
# ========================
async def buy_command_pm(update: Update, context: CallbackContext):
    if update.effective_chat.type != "private":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(sc("DIRECT SHOP ACCESS"), url=f"https://t.me/{context.bot.username}?start=buy_tokens", icon_custom_emoji_id="5445353829304387411")]])
        await update.message.reply_photo(
            photo=SHOP_IMG,
            caption=(
                f"<b><tg-emoji emoji-id=\"5445353829304387411\">💳</tg-emoji> {sc('DIRECT SHOP ACCESS')}</b>\n\n"
                f"<b><tg-emoji emoji-id=\"6093400141560030185\">💎</tg-emoji> {sc('Characters Tokens Coins')}</b>\n"
                f"<b><tg-emoji emoji-id=\"6100264379767332185\">⛈</tg-emoji> {sc('Buy instantly no tasks required!')}</b>\n\n"
                f"<b><tg-emoji emoji-id=\"5443127283898405358\">📥</tg-emoji> {sc('Tap below to shop')}</b>"
            ),
            reply_markup=kb, parse_mode='HTML'
        )
        return ConversationHandler.END
    return await start_buy_menu(update, context)

async def start_buy_menu(update: Update, context: CallbackContext):
    await clear_existing_states(context)
    order_id = uuid.uuid4().hex[:8]
    context.user_data['buy_order_id'] = order_id
    if update.effective_chat:
        context.user_data['buy_chat_id'] = update.effective_chat.id
    text = (
        f"<b>{E_TICK} {sc('order session created successfully!')}</b>\n"
        f"<b>{sc('order id:')}</b> <code>{order_id}</code>\n\n"
        f"<b>{sc('select the product you want to buy:')}</b>"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(sc("tokens"), callback_data="buy_prod_t", icon_custom_emoji_id="6109593993627050230"),
         InlineKeyboardButton(sc("coins"), callback_data="buy_prod_c", icon_custom_emoji_id="5472030678633684592")],
        [InlineKeyboardButton(sc("characters"), callback_data="buy_prod_char", icon_custom_emoji_id="6093434630147415641")],
        [InlineKeyboardButton(sc("cancel"), callback_data="buy_cancel", icon_custom_emoji_id="5260342697075416641")]
    ])
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await send_buy_log(context, "🔄 BACK TO MENU", update.effective_user, f"🆔 <b>ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n💬 <b>Aᴄᴛɪᴏɴ:</b> Rᴇᴛᴜʀɴᴇᴅ ᴛᴏ Bᴜʏ Mᴇɴᴜ")
    else:
        await update.message.reply_html(text, reply_markup=keyboard)
        await send_buy_log(context, "🚀 STARTED", update.effective_user, f"🆔 <b>ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n💬 <b>Aᴄᴛɪᴏɴ:</b> Iɴɪᴛɪᴀᴛᴇᴅ Bᴜʏ Mᴇɴᴜ")
    await save_buy_session(update.effective_user.id, context, WAITING_FOR_BUY_PRODUCT)
    return WAITING_FOR_BUY_PRODUCT

async def buy_back_callback(update: Update, context: CallbackContext):
    if context.user_data.get('last_processed_update_id') == update.update_id: return
    context.user_data['last_processed_update_id'] = update.update_id
    query = update.callback_query
    await query.answer()
    context.user_data.pop('buy_product', None)
    context.user_data.pop('buy_char_id', None)
    context.user_data.pop('buy_prompt_active', None)
    return await start_buy_menu(update, context)

async def buy_product_callback(update: Update, context: CallbackContext):
    if context.user_data.get('last_processed_update_id') == update.update_id: return
    context.user_data['last_processed_update_id'] = update.update_id
    query = update.callback_query
    await ensure_buy_user_data(context, query.from_user.id)
    if not context.user_data.get('buy_order_id'):
        await query.answer()
        return ConversationHandler.END
    if context.user_data.get('buy_prompt_active'):
        await query.answer(f"{sc('you are already in the process! please send the required info or type')} /cancel.", show_alert=True)
        if context.user_data.get('buy_product') == 'char' and not context.user_data.get('buy_char_id'):
            return WAITING_FOR_BUY_CHAR_ID
        return WAITING_FOR_BUY_AMOUNT
    await query.answer()
    context.user_data['buy_prompt_active'] = True
    context.user_data['buy_product'] = query.data.replace('buy_prod_', '')
    if query.message:
        context.user_data['buy_chat_id'] = query.message.chat_id
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
    else:
        return ConversationHandler.END
    await send_buy_log(context, "📦 SELECTED", query.from_user, f"🆔 <b>ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n💬 <b>Aᴄᴛɪᴏɴ:</b> Sᴇʟᴇᴄᴛᴇᴅ <b>{query.data}</b>")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(sc("back"), callback_data="buy_back", icon_custom_emoji_id="5258236805890710909"),
         InlineKeyboardButton(sc("cancel"), callback_data="buy_cancel", icon_custom_emoji_id="5260342697075416641")]
    ])
    await query.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    await save_buy_session(query.from_user.id, context, next_state)
    return next_state

async def ask_buy_char_id(update: Update, context: CallbackContext):
    context.user_data['last_processed_update_id'] = update.update_id
    await ensure_buy_user_data(context, update.message.from_user.id)
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
        [InlineKeyboardButton(sc("back"), callback_data="buy_back", icon_custom_emoji_id="5258236805890710909"),
         InlineKeyboardButton(sc("cancel"), callback_data="buy_cancel", icon_custom_emoji_id="5260342697075416641")]
    ])
    await update.message.reply_html(
        f"<b>{E_TICK} {sc('character found:')} {sc(live_char.get('name'))}</b>\n"
        f"<b>{sc('rarity:')} {sc(r)} ({sc('value:')} {coin_price:,} {sc('coins')})</b>\n\n"
        f"<b>{sc(f'send the quantity of this character you want to buy (min: {min_qty}, max: 100).')}</b>\n"
        f"<i>({sc('note: minimum purchase value is 5 inr / 37,500 coins')})</i>",
        reply_markup=kb
    )
    await save_buy_session(update.message.from_user.id, context, WAITING_FOR_BUY_AMOUNT)
    return WAITING_FOR_BUY_AMOUNT

async def ask_buy_amount(update: Update, context: CallbackContext):
    context.user_data['last_processed_update_id'] = update.update_id
    await ensure_buy_user_data(context, update.message.from_user.id)
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
        [InlineKeyboardButton(sc("cancel"), callback_data="buy_cancel", icon_custom_emoji_id="5260342697075416641")]
    ])
    msg = await context.bot.send_photo(
        chat_id=update.message.chat_id,
        photo="https://files.catbox.moe/0qjgih.png",
        caption=caption, reply_markup=kb, parse_mode='HTML'
    )
    context.user_data['qr_msg_id'] = msg.message_id
    await save_buy_session(update.message.from_user.id, context, WAITING_FOR_BUY_SCREENSHOT)
    return WAITING_FOR_BUY_SCREENSHOT

async def receive_buy_screenshot(update: Update, context: CallbackContext):
    context.user_data['last_processed_update_id'] = update.update_id
    user_id = update.message.from_user.id
    if not update.message.photo: return WAITING_FOR_BUY_SCREENSHOT
    await ensure_buy_user_data(context, user_id)
    if not context.user_data.get('buy_order_id') or context.user_data.get('buy_amount') is None:
        session = await load_buy_session(user_id)
        if not session or session.get('state') != WAITING_FOR_BUY_SCREENSHOT:
            return WAITING_FOR_BUY_SCREENSHOT
        apply_buy_session(context, session)
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
        [InlineKeyboardButton("ᴄᴀɴᴄᴇʟ", callback_data=f"b_can:{order_id}", icon_custom_emoji_id="5260342697075416641")]
    ])
    await context.bot.send_photo(chat_id=BUY_LOG_GROUP_ID, photo=photo_id, caption=admin_text, reply_markup=kb, parse_mode='HTML')
    await update.message.reply_html(f"<b>{E_TICK} {sc('your payment screenshot has been sent to the admin. please wait for confirmation. items will be added to your wallet shortly.')}</b>")
    await clear_buy_session(user_id)
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_buy_callback(update: Update, context: CallbackContext):
    if context.user_data.get('last_processed_update_id') == update.update_id: return
    context.user_data['last_processed_update_id'] = update.update_id
    query = update.callback_query
    await query.answer()
    await ensure_buy_user_data(context, query.from_user.id)
    if query.message.photo:
        await query.message.delete()
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"<b>{E_CROSS} {sc('order cancelled.')}</b>", parse_mode='HTML')
    else:
        await query.message.edit_text(f"<b>{E_CROSS} {sc('order cancelled.')}</b>", parse_mode='HTML')
    order_id = context.user_data.get('buy_order_id', 'UNKNOWN')
    await send_buy_log(context, "❌ CANCELLED", query.from_user, f"🆔 <b>ᴏʀᴅᴇʀ ɪᴅ:</b> <code>{order_id}</code>\n💬 <b>Aᴄᴛɪᴏɴ:</b> Usᴇʀ ᴄᴀɴᴄᴇʟʟᴇᴅ ᴛʜᴇ ᴘʀᴏᴄᴇss")
    await clear_buy_session(query.from_user.id)
    context.user_data.clear()
    return ConversationHandler.END

async def admin_buy_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    if query.data == "ignore": return await query.answer()
    if query.from_user.id != OWNER_ID: return await query.answer(f"{sc('only owner can approve this!')}", show_alert=True)
    data = query.data.split(':')
    action = data[0]
    order_id = data[-1]
    order = await bot_settings_collection.find_one({'_id': f"buy_{order_id}"})
    if not order: return await query.answer("Order data not found!", show_alert=True)
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
            [InlineKeyboardButton("ᴄᴀɴᴄᴇʟ", callback_data=f"b_can:{order_id}", icon_custom_emoji_id="5260342697075416641")]
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
    context.user_data['shop_msg_id'] = query.message.message_id
    owner_id = int(parts[-1])
    if user_id != owner_id:
        await query.answer(f"{sc('you cannot interact with this menu!')}\n{sc('please open your own via')} /shop", show_alert=True)
        return
    action = parts[0]

    if action == "pm_b":
        buttons = []
        for key, (db_emoji, prem_html, name) in RARITIES.items():
            emoji_id = extract_emoji_id(prem_html)
            buttons.append(InlineKeyboardButton(f"{sc(name)}", callback_data=f"pm_r:{key}:{user_id}", icon_custom_emoji_id=emoji_id))
        keyboard = chunk(buttons, 2)
        keyboard.append([InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_m:{user_id}")])
        await update_menu(query, f"<b><tg-emoji emoji-id=\"5312361253610475399\">🛒</tg-emoji> {sc('buy characters from market')}</b>\n\n<i>{sc('select a rarity to view products.')}</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_m":
        bot_username = context.bot.username
        keyboard = await get_pmarket_keyboard(user_id, bot_username)
        caption = f"<b><tg-emoji emoji-id=\"5278702045883292456\">🛍</tg-emoji> P2P ᴍᴀʀᴋᴇᴛᴘʟᴀᴄᴇ</b>\n\n<i>{sc('choose an option to proceed.')}</i>"
        await update_menu(query, caption, keyboard, change_media=True, photo_url=SHOP_IMG)

    elif action == "pm_exc_menu":
        global_limit, used_today, _ = await get_token_limit_info(user_id)
        limit_text = f"{E_INF}" if user_id == OWNER_ID else f"{global_limit - used_today} {sc('left today')}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(sc("get coins"), callback_data=f"pm_start_exc_t2c:{user_id}", icon_custom_emoji_id="5472030678633684592"),
             InlineKeyboardButton(sc("get token"), callback_data=f"pm_start_exc_c2t:{user_id}", icon_custom_emoji_id="6109593993627050230")],
            [InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_m:{user_id}")]
        ])
        await update_menu(query, f"<b>{E_EXC} {sc('exchange menu')}</b>\n\n<i>{sc('daily limit:')} {limit_text}</i>\n<i>{sc('what would you like to do?')}</i>", keyboard)

    elif action == "pm_r":
        rarity_key = parts[1]
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(sc("price low to high"), callback_data=f"pm_s:{rarity_key}:asc:0:{user_id}")],
            [InlineKeyboardButton(sc("price high to low"), callback_data=f"pm_s:{rarity_key}:desc:0:{user_id}")],
            [InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_b:{user_id}")]
        ])
        _, prem_emoji, name = RARITIES.get(rarity_key, RARITIES["common"])
        await update_menu(query, f"<b>{prem_emoji} {sc(name)} {sc('characters')}</b>\n\n<i>{sc('how do you want to sort them?')}</i>", keyboard)

    elif action == "pm_s":
        rarity_key = parts[1]
        order = parts[2]
        try: page = int(parts[3])
        except: page = 0
        sort_order = 1 if order == "asc" else -1
        db_emoji, prem_emoji, name = RARITIES.get(rarity_key, RARITIES["common"])
        # Search by keyword for the specific rarity
        keywords = RARITY_KEYWORDS.get(rarity_key, [rarity_key])
        regex_parts = [re.escape(k) for k in keywords if len(k) > 1]
        regex_pattern = "|".join(regex_parts) if regex_parts else re.escape(rarity_key)
        query_filter = {'character.rarity': {'$regex': regex_pattern, '$options': 'i'}}
        total_count = await market_collection.count_documents(query_filter)
        total_pages = max(1, math.ceil(total_count / PER_PAGE))
        if page < 0: page = 0
        if page >= total_pages: page = total_pages - 1
        cursor = market_collection.find(query_filter).sort('price', sort_order).skip(page * PER_PAGE).limit(PER_PAGE)
        market_items = await cursor.to_list(length=PER_PAGE)
        if not market_items:
            await query.answer(f"{sc('no characters are currently for sale in this rarity!')}", show_alert=True)
            return
        keyboard = []
        for item in market_items:
            char = item['character']
            char_name = char.get('name', 'Unknown')
            price = item['price']
            market_id = str(item['_id'])
            char_rarity_str = str(char.get('rarity', '')).strip()
            _, prem_html, _ = get_rarity_display(char_rarity_str)
            emoji_id = extract_emoji_id(prem_html)
            btn_text = f"{sc(char_name)} - {price:,}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pm_v:{market_id}:{rarity_key}:{order}:{page}:{user_id}", icon_custom_emoji_id=emoji_id)])
        # Pagination
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(sc("◀ prev"), callback_data=f"pm_s:{rarity_key}:{order}:{page-1}:{user_id}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="ignore"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(sc("next ▶"), callback_data=f"pm_s:{rarity_key}:{order}:{page+1}:{user_id}"))
        keyboard.append(nav)
        keyboard.append([InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_r:{rarity_key}:{user_id}")])
        sort_text = sc("low to high") if order == "asc" else sc("high to low")
        await update_menu(query, f"<b>{prem_emoji} {sc('characters for sale')}</b>\n\n<i>{sc('sorted by price (')} {sort_text} {sc(')')}</i>", InlineKeyboardMarkup(keyboard), change_media=True, photo_url=SHOP_IMG)

    elif action == "pm_v":
        market_id = parts[1]
        rarity_key = parts[2] if len(parts) > 2 else "common"
        order = parts[3] if len(parts) > 3 else "asc"
        try: page = int(parts[4]) if len(parts) > 4 else 0
        except: page = 0
        item = await market_collection.find_one({'_id': ObjectId(market_id)})
        if not item:
            await query.answer(f"{sc('oops! this character has already been sold or removed!')}", show_alert=True)
            return
        char = item['character']
        seller_id = item['seller_id']
        price = item['price']
        char_name = char.get('name')
        char_id = char.get('id')
        live_char = await get_live_character_doc(char_id)
        if not live_char and char_name:
            tasks = [db[col].find_one({'name': char_name}) for col in ['anime_characters_lol', 'characters', 'collection']]
            results = await asyncio.gather(*tasks)
            live_char = next((r for r in results if r), None)
        display_char = live_char if live_char else char
        char_rarity_str = str(display_char.get('rarity', '')).strip()
        prem_emoji, _, name = get_rarity_display(char_rarity_str)
        # convert to premium html
        _, prem_html, name = get_rarity_display(char_rarity_str)
        caption = (
            f"<b>{prem_html} {sc(display_char.get('name', 'Unknown'))}</b>\n\n"
            f"<b><tg-emoji emoji-id=\"6314494724266796319\">🟠</tg-emoji> ᴀɴɪᴍᴇ:</b> {sc(display_char.get('anime', 'Unknown'))}\n"
            f"<b><tg-emoji emoji-id=\"5260426225599405269\">🪄</tg-emoji> ʀᴀʀɪᴛʏ:</b> {prem_html} {sc(name)}\n"
            f"<b>{E_MONEY} ᴘʀɪᴄᴇ:</b> <code>{price:,}</code>\n"
            f"<b><tg-emoji emoji-id=\"6332443074769196273\">🆔</tg-emoji> sᴇʟʟᴇʀ:</b> <code>{seller_id}</code>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(sc("buy now"), callback_data=f"pm_buy:{market_id}:{user_id}", icon_custom_emoji_id="5312361253610475399")],
            [InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_s:{rarity_key}:{order}:{page}:{user_id}")]
        ])
        is_video = display_char.get('is_video', False)
        await update_menu(query, caption, keyboard, change_media=True, photo_url=display_char.get('img_url', SHOP_IMG), is_video=is_video)

    elif action == "pm_buy":
        market_id = parts[1]
        item = await market_collection.find_one({'_id': ObjectId(market_id)})
        if not item:
            await query.answer(f"{sc('too late! this character has already been bought by someone else.')}", show_alert=True)
            return
        price = item['price']
        seller_id = item['seller_id']
        char = item['character']
        if seller_id == user_id:
            await query.answer(f"{sc('you cannot buy your own character!')}", show_alert=True)
            return
        eco_buyer = await eco_collection.find_one_and_update(
            {'id': user_id, 'balance': {'$gte': price}},
            {'$inc': {'balance': -price}}
        )
        if not eco_buyer:
            await query.answer(f"{sc('insufficient funds! you need')} {price:,} {sc('balance.')}", show_alert=True)
            return
        seller_doc = await user_collection.find_one({'id': seller_id})
        seller_chars = seller_doc.get('characters', []) if seller_doc else []
        char_found_idx = -1
        for i, c in enumerate(seller_chars):
            if str(c.get('id')) == str(char.get('id')):
                char_found_idx = i
                break
        if char_found_idx == -1:
            await eco_collection.update_one({'id': user_id}, {'$inc': {'balance': price}})
            await market_collection.delete_one({'_id': ObjectId(market_id)})
            await query.answer(f"{sc('the seller no longer owns this character! listing has been automatically removed.')}", show_alert=True)
            return
        deleted_item = await market_collection.find_one_and_delete({'_id': ObjectId(market_id)})
        if not deleted_item:
            await eco_collection.update_one({'id': user_id}, {'$inc': {'balance': price}})
            await query.answer(f"{sc('too late! this character has already been bought by someone else.')}", show_alert=True)
            return
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

        # 🔔 SELLER NOTIFICATION (name only, no mention) 🔔
        _, prem_html, _ = get_rarity_display(char.get('rarity', ''))
        try:
            await context.bot.send_message(
                chat_id=seller_id,
                text=(
                    f"<b>{E_PARTY} {sc('character sold!')}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"<b>🎭 {sc('character:')}</b> {prem_html} <b>{sc(char.get('name', 'Unknown'))}</b>\n"
                    f"<b>🆔 {sc('id:')}</b> <code>{char.get('id')}</code>\n"
                    f"<b>{E_MONEY} {sc('sold for:')}</b> <b><code>{price:,}</code> {sc('coins')}</b>\n"
                    f"<b>👤 {sc('buyer:')}</b> <b>{sc(buyer_name)}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"<b>{E_TICK} {sc('the amount has been added to your balance!')}</b>"
                ),
                parse_mode='HTML'
            )
        except Exception:
            pass

        kb = InlineKeyboardMarkup([[InlineKeyboardButton(sc("↻ back to shop"), callback_data=f"pm_m:{user_id}")]])
        await update_menu(
            query,
            f"<b>{E_PARTY} {sc('congratulations! you successfully bought')} {sc(char.get('name'))} {sc('for')} {E_MONEY} {price:,}.</b>",
            kb
        )

    elif action == "pm_sm":
        try: page = int(parts[1])
        except: page = 0
        total_count = await market_collection.count_documents({'seller_id': user_id})
        total_pages = max(1, math.ceil(total_count / PER_PAGE))
        if page < 0: page = 0
        if page >= total_pages: page = total_pages - 1
        cursor = market_collection.find({'seller_id': user_id}).sort('_id', -1).skip(page * PER_PAGE).limit(PER_PAGE)
        listings = await cursor.to_list(length=PER_PAGE)
        keyboard = [[InlineKeyboardButton(sc("list new character"), callback_data=f"pm_start_s:{user_id}", icon_custom_emoji_id="6109452611893601414")]]
        for item in listings:
            char_name = char.get('name') if False else item['character'].get('name', 'Unknown')
            market_id = str(item['_id'])
            # 🔥 2 buttons in one row: [character name] [cancel] 🔥
            keyboard.append([
                InlineKeyboardButton(sc(char_name), callback_data=f"pm_view_listing:{market_id}:{page}:{user_id}", icon_custom_emoji_id="6093434630147415641"),
                InlineKeyboardButton(sc("cancel"), callback_data=f"pm_delist:{market_id}:{page}:{user_id}", icon_custom_emoji_id="5472030678633684592")
            ])
        # Pagination
        if total_count > 0:
            nav = []
            if page > 0:
                nav.append(InlineKeyboardButton(sc("◀ prev"), callback_data=f"pm_sm:{page-1}:{user_id}"))
            nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="ignore"))
            if page < total_pages - 1:
                nav.append(InlineKeyboardButton(sc("next ▶"), callback_data=f"pm_sm:{page+1}:{user_id}"))
            keyboard.append(nav)
        keyboard.append([InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_m:{user_id}")])
        await update_menu(query, f"<b>{E_MONEY} {sc('your active listings')}</b>\n\n<i>{sc('manage your current listings or add a new one.')}</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_view_listing":
        market_id = parts[1]
        try: page = int(parts[2])
        except: page = 0
        item = await market_collection.find_one({'_id': ObjectId(market_id)})
        if not item or item.get('seller_id') != user_id:
            await query.answer(f"{sc('this listing is no longer available!')}", show_alert=True)
            return
        char = item['character']
        price = item['price']
        char_id = char.get('id')
        live_char = await get_live_character_doc(char_id)
        if not live_char and char.get('name'):
            tasks = [db[col].find_one({'name': char.get('name')}) for col in ['anime_characters_lol', 'characters', 'collection']]
            results = await asyncio.gather(*tasks)
            live_char = next((r for r in results if r), None)
        display_char = live_char if live_char else char
        char_rarity_str = str(display_char.get('rarity', '')).strip()
        _, prem_html, name = get_rarity_display(char_rarity_str)
        caption = (
            f"<b>{prem_html} {sc(display_char.get('name', 'Unknown'))}</b>\n\n"
            f"<b><tg-emoji emoji-id=\"6314494724266796319\">🟠</tg-emoji> ᴀɴɪᴍᴇ:</b> {sc(display_char.get('anime', 'Unknown'))}\n"
            f"<b><tg-emoji emoji-id=\"5260426225599405269\">🪄</tg-emoji> ʀᴀʀɪᴛʏ:</b> {prem_html} {sc(name)}\n"
            f"<b>{E_MONEY} ʏᴏᴜʀ ᴘʀɪᴄᴇ:</b> <code>{price:,}</code>\n"
            f"<b><tg-emoji emoji-id=\"6332443074769196273\">🆔</tg-emoji> ᴄʜᴀʀ ɪᴅ:</b> <code>{display_char.get('id')}</code>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(sc("cancel listing"), callback_data=f"pm_delist:{market_id}:{page}:{user_id}", icon_custom_emoji_id="5472030678633684592")],
            [InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_sm:{page}:{user_id}")]
        ])
        is_video = display_char.get('is_video', False)
        await update_menu(query, caption, keyboard, change_media=True, photo_url=display_char.get('img_url', SHOP_IMG), is_video=is_video)

    elif action == "pm_delist":
        market_id = parts[1]
        try: page = int(parts[2])
        except: page = 0
        item = await market_collection.find_one({'_id': ObjectId(market_id)})
        if not item:
            await query.answer(f"{sc('this item is no longer on the market.')}", show_alert=True)
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
        # Refresh the listings page (same page, but clamp)
        total_count = await market_collection.count_documents({'seller_id': user_id})
        total_pages = max(1, math.ceil(total_count / PER_PAGE))
        if page >= total_pages: page = total_pages - 1
        if page < 0: page = 0
        cursor = market_collection.find({'seller_id': user_id}).sort('_id', -1).skip(page * PER_PAGE).limit(PER_PAGE)
        listings = await cursor.to_list(length=PER_PAGE)
        keyboard = [[InlineKeyboardButton(sc("list new character"), callback_data=f"pm_start_s:{user_id}", icon_custom_emoji_id="6109452611893601414")]]
        for item in listings:
            char_name = item['character'].get('name', 'Unknown')
            m_id = str(item['_id'])
            keyboard.append([
                InlineKeyboardButton(sc(char_name), callback_data=f"pm_view_listing:{m_id}:{page}:{user_id}", icon_custom_emoji_id="6093434630147415641"),
                InlineKeyboardButton(sc("cancel"), callback_data=f"pm_delist:{m_id}:{page}:{user_id}", icon_custom_emoji_id="5472030678633684592")
            ])
        if total_count > 0:
            nav = []
            if page > 0:
                nav.append(InlineKeyboardButton(sc("◀ prev"), callback_data=f"pm_sm:{page-1}:{user_id}"))
            nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="ignore"))
            if page < total_pages - 1:
                nav.append(InlineKeyboardButton(sc("next ▶"), callback_data=f"pm_sm:{page+1}:{user_id}"))
            keyboard.append(nav)
        keyboard.append([InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_m:{user_id}")])
        await update_menu(query, f"<b>{E_MONEY} {sc('your active listings')}</b>\n\n<i>{sc('manage your current listings or add a new one.')}</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_exc_conf":
        exc_type = parts[1]
        amount = int(parts[2])
        global_limit, used_today, today_str = await get_token_limit_info(user_id)
        if user_id != OWNER_ID:
            if amount + used_today > global_limit:
                available = max(0, global_limit - used_today)
                await query.answer(f"{sc('daily limit reached! you can only exchange')} {available} {sc('more tokens today.')}", show_alert=True)
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
                await query.answer(f"{sc('you do not have enough tokens anymore!')}", show_alert=True)
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
                await query.answer(f"{sc('you do not have enough coins anymore!')}", show_alert=True)
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
# CONVERSATION HELPERS
# ========================
async def cancel_process(update: Update, context: CallbackContext):
    context.user_data['last_processed_update_id'] = update.update_id
    qr_msg_id = context.user_data.get('qr_msg_id')
    if qr_msg_id:
        try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=qr_msg_id)
        except Exception: pass
    shop_msg_id = context.user_data.get('shop_msg_id')
    if shop_msg_id:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(sc("↻ back to shop"), callback_data=f"pm_m:{update.effective_user.id}")]])
        try: await context.bot.edit_message_caption(chat_id=update.effective_chat.id, message_id=shop_msg_id, caption=f"<b>{E_CROSS} {sc('process cancelled.')}</b>", reply_markup=kb, parse_mode='HTML')
        except Exception: pass
    if update.message:
        try: await update.message.delete()
        except: pass
    if update.effective_user and (
        context.user_data.get('buy_order_id')
        or context.user_data.get('buy_prompt_active')
        or context.user_data.get('qr_msg_id')
        or context.user_data.get('buy_product')
    ):
        await clear_buy_session(update.effective_user.id)
    await clear_existing_states(context)
    return ConversationHandler.END

async def timeout_process(update: Update, context: CallbackContext):
    context.user_data['last_processed_update_id'] = update.update_id
    qr_msg_id = context.user_data.get('qr_msg_id')
    chat_id = update.effective_chat.id if update.effective_chat else update.callback_query.message.chat_id
    if qr_msg_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=qr_msg_id)
        except Exception: pass
    shop_msg_id = context.user_data.get('shop_msg_id')
    if shop_msg_id:
        try:
            await context.bot.edit_message_caption(chat_id=chat_id, message_id=shop_msg_id, caption=f"<b>{E_TIME} {sc('session expired due to inactivity. please start again.')}</b>", parse_mode='HTML')
        except Exception: pass
    await clear_existing_states(context)
    return ConversationHandler.END

# --- 1. SELL CONVERSATION ---
async def sell_start(update: Update, context: CallbackContext):
    query = update.callback_query
    parts = query.data.split(':')
    owner_id = int(parts[-1])
    if query.from_user.id != owner_id:
        await query.answer(f"{sc('you cannot interact with this menu!')}", show_alert=True)
        return ConversationHandler.END
    if context.user_data.get('sell_active'):
        await query.answer(f"{sc('already started your process! complete it or type')} /cancel {sc('first.')}", show_alert=True)
        return context.user_data.get('sell_step', WAITING_FOR_CHARACTER_ID)
    await clear_existing_states(context)
    await query.answer()
    context.user_data['sell_owner_id'] = owner_id
    context.user_data['sell_active'] = True
    context.user_data['sell_step'] = WAITING_FOR_CHARACTER_ID
    context.user_data['shop_msg_id'] = query.message.message_id
    text = f"{E_MONEY} <b>{sc('send the character id you want to sell:')}</b>\n\n({sc('type')} /cancel {sc('to abort the process')})"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_sm:0:{owner_id}")]])
    await update_menu(query, text, kb)
    return WAITING_FOR_CHARACTER_ID

async def sell_back_handler(update: Update, context: CallbackContext):
    """Just end the sell conversation; the global handler will show the listings."""
    await clear_existing_states(context)
    return ConversationHandler.END

async def ask_character_id(update: Update, context: CallbackContext):
    if not update.message or not update.message.text: return WAITING_FOR_CHARACTER_ID
    user_id = update.message.from_user.id
    expected_owner = context.user_data.get('sell_owner_id')
    if expected_owner and user_id != expected_owner: return WAITING_FOR_CHARACTER_ID
    shop_msg_id = context.user_data.get('shop_msg_id')
    chat_id = update.effective_chat.id
    char_id = update.message.text.strip()
    if not char_id.isdigit():
        return WAITING_FOR_CHARACTER_ID
    # 🔥 NO LONGER DELETING USER'S MESSAGE 🔥
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_sm:0:{user_id}")]])
    user_data = await user_collection.find_one({'id': user_id})
    if not user_data or 'characters' not in user_data:
        if shop_msg_id:
            try: await context.bot.edit_message_caption(chat_id=chat_id, message_id=shop_msg_id, caption=f"⚠️ <b>{sc('character not found in your inventory! try again.')}</b>", reply_markup=back_kb, parse_mode='HTML')
            except: pass
        return WAITING_FOR_CHARACTER_ID
    character = None
    for c in user_data.get('characters', []):
        db_id = str(c.get('id')).strip()
        if db_id == char_id or (db_id.isdigit() and char_id.isdigit() and int(db_id) == int(char_id)):
            character = c
            break
    if not character:
        if shop_msg_id:
            try: await context.bot.edit_message_caption(chat_id=chat_id, message_id=shop_msg_id, caption=f"⚠️ <b>{sc('character not found in your inventory! try again.')}</b>", reply_markup=back_kb, parse_mode='HTML')
            except: pass
        return WAITING_FOR_CHARACTER_ID
    context.user_data['sell_character'] = character
    context.user_data['sell_step'] = WAITING_FOR_PRICE
    text = f"{E_TICK} <b>{sc('character found! now send price')}</b>\n\n{sc('selected:')} <b>{sc(character.get('name'))}</b>\n<i>{sc('enter the price (in')} {E_MONEY}{sc(') you want to sell it for.')}</i>"
    if shop_msg_id:
        try: await context.bot.edit_message_caption(chat_id=chat_id, message_id=shop_msg_id, caption=text, reply_markup=back_kb, parse_mode='HTML')
        except: pass
    return WAITING_FOR_PRICE

async def ask_price(update: Update, context: CallbackContext):
    if not update.message or not update.message.text: return WAITING_FOR_PRICE
    user_id = update.message.from_user.id
    expected_owner = context.user_data.get('sell_owner_id')
    if expected_owner and user_id != expected_owner: return WAITING_FOR_PRICE
    shop_msg_id = context.user_data.get('shop_msg_id')
    chat_id = update.effective_chat.id
    price_text = update.message.text.strip()
    if not price_text.isdigit():
        return WAITING_FOR_PRICE
    # 🔥 NO LONGER DELETING USER'S MESSAGE 🔥
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_sm:0:{user_id}")]])
    price = int(price_text)
    if price <= 0:
        if shop_msg_id:
            try: await context.bot.edit_message_caption(chat_id=chat_id, message_id=shop_msg_id, caption=f"<b>{sc('invalid price! enter a positive number.')}</b>", reply_markup=back_kb, parse_mode='HTML')
            except: pass
        return WAITING_FOR_PRICE
    if price > 2500000:
        if shop_msg_id:
            try: await context.bot.edit_message_caption(chat_id=chat_id, message_id=shop_msg_id, caption=f"<b>{E_WARN} {sc('maximum price limit is 2,500,000 coins. please enter a lower amount.')}</b>", reply_markup=back_kb, parse_mode='HTML')
            except: pass
        return WAITING_FOR_PRICE
    character = context.user_data.get('sell_character')
    if not character:
        await clear_existing_states(context)
        return ConversationHandler.END
    char_id_val = str(character['id'])
    live_char = await get_live_character_doc(char_id_val)
    final_character = live_char if live_char else character
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
        if shop_msg_id:
            try: await context.bot.edit_message_caption(chat_id=chat_id, message_id=shop_msg_id, caption=f"⚠️ <b>{sc('you have already listed all your copies of this character on the market!')}</b>", reply_markup=back_kb, parse_mode='HTML')
            except: pass
        await clear_existing_states(context)
        return ConversationHandler.END
    await market_collection.insert_one({'seller_id': user_id, 'price': price, 'character': final_character})
    user_name = update.message.from_user.first_name
    user_mention = f"<a href='tg://user?id={user_id}'>{html.escape(user_name)}</a>"
    log_details = (
        f"👤 <b>Sᴇʟʟᴇʀ:</b> {user_mention}\n"
        f"🎭 <b>Cʜᴀʀᴀᴄᴛᴇʀ:</b> {final_character.get('name')} (<code>{final_character.get('id')}</code>)\n"
        f"💰 <b>Pʀɪᴄᴇ Sᴇᴛ:</b> {price:,} ᴄᴏɪɴs"
    )
    await send_market_log(context, "📈 CHARACTER LISTED", log_details)
    main_kb = InlineKeyboardMarkup([[InlineKeyboardButton(sc("↻ back to shop"), callback_data=f"pm_m:{user_id}")]])
    text = f"<b>{E_PARTY} {sc(final_character.get('name'))} {sc('has been successfully listed on the market for')} {E_MONEY} {price:,}!</b>"
    if shop_msg_id:
        try: await context.bot.edit_message_caption(chat_id=chat_id, message_id=shop_msg_id, caption=text, reply_markup=main_kb, parse_mode='HTML')
        except: pass
    await clear_existing_states(context)
    return ConversationHandler.END

sell_conv = ConversationHandler(
    name="pmarket_sell_conv",
    persistent=True,
    entry_points=[CallbackQueryHandler(sell_start, pattern=r"^pm_start_s:")],
    states={
        WAITING_FOR_CHARACTER_ID: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, ask_character_id),
            CallbackQueryHandler(sell_back_handler, pattern=r"^pm_sm:")
        ],
        WAITING_FOR_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, ask_price),
            CallbackQueryHandler(sell_back_handler, pattern=r"^pm_sm:")
        ],
        ConversationHandler.TIMEOUT: [TypeHandler(Update, timeout_process)]
    },
    fallbacks=[CommandHandler("cancel", cancel_process)],
    conversation_timeout=120,
    allow_reentry=True,
    per_user=True,
    per_chat=True,
)

# --- 2. EXCHANGE CONVERSATION ---
async def exchange_start_t2c(update: Update, context: CallbackContext):
    query = update.callback_query
    parts = query.data.split(':')
    owner_id = int(parts[-1])
    if query.from_user.id != owner_id:
        await query.answer(f"{sc('you cannot interact with this menu!')}", show_alert=True)
        return ConversationHandler.END
    await clear_existing_states(context)
    await query.answer()
    context.user_data['exc_owner_id'] = owner_id
    context.user_data['exc_type'] = 't2c'
    context.user_data['shop_msg_id'] = query.message.message_id
    user = await eco_collection.find_one({'id': owner_id})
    tokens = user.get('tokens', 0) if user else 0
    text = (
        f"<b>{E_EXC} {sc('how many tokens do you want to sell for coins?')}</b>\n\n"
        f"<i>{sc('1 token = 2,500 coins.')}</i>\n"
        f"<b>{sc('you have:')}</b> <code>{tokens:,}</code> {sc('tokens')}\n\n"
        f"({sc('enter the number of tokens, e.g. type')} <b>1</b> {sc('to get 2500 coins')})\n"
        f"({sc('type')} /cancel {sc('to abort the process')})"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_exc_menu:{owner_id}")]])
    await update_menu(query, text, kb)
    return WAITING_FOR_EXCHANGE_AMOUNT

async def exchange_start_c2t(update: Update, context: CallbackContext):
    query = update.callback_query
    parts = query.data.split(':')
    owner_id = int(parts[-1])
    if query.from_user.id != owner_id:
        await query.answer(f"{sc('you cannot interact with this menu!')}", show_alert=True)
        return ConversationHandler.END
    await clear_existing_states(context)
    await query.answer()
    context.user_data['exc_owner_id'] = owner_id
    context.user_data['exc_type'] = 'c2t'
    context.user_data['shop_msg_id'] = query.message.message_id
    user = await eco_collection.find_one({'id': owner_id})
    coins = user.get('balance', 0) if user else 0
    text = (
        f"<b>{E_EXC} {sc('how many tokens do you want to buy with coins?')}</b>\n\n"
        f"<i>{sc('2,500 coins = 1 token.')}</i>\n"
        f"<b>{sc('you have:')}</b> <code>{coins:,}</code> {sc('coins')}\n\n"
        f"({sc('enter the number of tokens, e.g. type')} <b>1</b> {sc('to spend 2500 coins')})\n"
        f"({sc('type')} /cancel {sc('to abort the process')})"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_exc_menu:{owner_id}")]])
    await update_menu(query, text, kb)
    return WAITING_FOR_EXCHANGE_AMOUNT

async def exchange_back_handler(update: Update, context: CallbackContext):
    """End the exchange conversation; the global handler shows the exchange menu."""
    await clear_existing_states(context)
    return ConversationHandler.END

async def ask_exchange_amount(update: Update, context: CallbackContext):
    if not update.message or not update.message.text: return WAITING_FOR_EXCHANGE_AMOUNT
    user_id = update.message.from_user.id
    expected_owner = context.user_data.get('exc_owner_id')
    exc_type = context.user_data.get('exc_type')
    if expected_owner and user_id != expected_owner: return WAITING_FOR_EXCHANGE_AMOUNT
    shop_msg_id = context.user_data.get('shop_msg_id')
    chat_id = update.effective_chat.id
    amount_text = update.message.text.strip()
    if not re.fullmatch(r'\d+', amount_text) or int(amount_text) <= 0:
        return WAITING_FOR_EXCHANGE_AMOUNT
    # 🔥 NO LONGER DELETING USER'S MESSAGE 🔥
    amount = int(amount_text)
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(sc("↻ back"), callback_data=f"pm_exc_menu:{user_id}")]])
    global_limit, used_today, _ = await get_token_limit_info(user_id)
    if user_id != OWNER_ID:
        if amount + used_today > global_limit:
            available = max(0, global_limit - used_today)
            if shop_msg_id:
                try: await context.bot.edit_message_caption(chat_id=chat_id, message_id=shop_msg_id, caption=f"{E_WARN} <b>{sc('daily limit exceeded!')}</b>\n{sc('you can only exchange')} <code>{global_limit}</code> {sc('tokens per day.')}\n{sc('you have')} <code>{available}</code> {sc('tokens left for today.')}", reply_markup=back_kb, parse_mode='HTML')
                except: pass
            return WAITING_FOR_EXCHANGE_AMOUNT
    user = await eco_collection.find_one({'id': user_id})
    tokens = user.get('tokens', 0) if user else 0
    coins = user.get('balance', 0) if user else 0
    if exc_type == 't2c':
        if amount > tokens:
            if shop_msg_id:
                try: await context.bot.edit_message_caption(chat_id=chat_id, message_id=shop_msg_id, caption=f"<b>{sc('you do not have enough tokens! you only have')} <code>{tokens:,}</code> {sc('tokens.')}</b>", reply_markup=back_kb, parse_mode='HTML')
                except: pass
            return WA

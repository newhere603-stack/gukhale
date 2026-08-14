import asyncio
from bson import ObjectId
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from shivu import application, db

# --- DATABASE COLLECTIONS ---
user_collection = db['user_collection_lmaoooo']
market_collection = db['market_collection'] 

# --- HELPER TO GET LIVE CHARACTER FROM ANY COLLECTION ---
async def get_live_character_doc(char_id):
    if char_id is None:
        return None
    for col_name in ['anime_characters_lol', 'characters', 'collection']:
        col = db[col_name]
        doc = await col.find_one({
            '$or': [{'id': char_id}, {'id': str(char_id)}, {'id': int(char_id) if str(char_id).isdigit() else None}]
        })
        if doc:
            return doc
    return None

# --- CONVERSATION STATES ---
WAITING_FOR_CHARACTER_ID, WAITING_FOR_PRICE = 1, 2

# --- SMALL CAPS CONVERTER HELPERS ---
SMALL_CAPS_TRANS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
)

def to_small_caps(text: str) -> str:
    if not text:
        return ""
    return str(text).translate(SMALL_CAPS_TRANS)

# --- RARITIES (Cosmic & Premium Edition swapped) ---
RARITIES = {
    "common": ("🟢", '<tg-emoji emoji-id="6093722470265658964">🟢</tg-emoji>', "Common"), 
    "rare": ("🟠", '<tg-emoji emoji-id="5339390195768774311">🟠</tg-emoji>', "Rare"), 
    "legendary": ("🟡", '<tg-emoji emoji-id="6334705977073337764">🟡</tg-emoji>', "Legendary"),
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
    "pearl": ("🐚", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"), 
    "premium": ("🔮", '<tg-emoji emoji-id="6093919703753831564">🔮</tg-emoji>', "Premium Edition"), 
}

def chunk(items: list, size: int) -> list:
    return [items[i:i + size] for i in range(0, len(items), size)]

async def update_menu(query, text, keyboard):
    if query.message.photo or query.message.video:
        await query.message.delete()
        await query.message.reply_html(text, reply_markup=keyboard)
    else:
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')

# ========================
# MAIN COMMAND
# ========================
async def pmarket_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 ʙᴜʏ", callback_data=f"pm_b:{user_id}")],
        [InlineKeyboardButton("💸 sᴇʟʟ", callback_data=f"pm_sm:{user_id}")]
    ])
    await update.message.reply_text(
        "<b><tg-emoji emoji-id=\"5278702045883292456\">🛍</tg-emoji> P2P ᴍᴀʀᴋᴇᴛᴘʟᴀᴄᴇ</b>\n\n"
        "<i>ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ.</i>",
        reply_markup=keyboard,
        parse_mode='HTML'
    )

# ========================
# BUY & MARKET CALLBACKS
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
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 ʙᴜʏ", callback_data=f"pm_b:{user_id}")],
            [InlineKeyboardButton("💸 sᴇʟʟ", callback_data=f"pm_sm:{user_id}")]
        ])
        await update_menu(query, "<b><tg-emoji emoji-id=\"5278702045883292456\">🛍</tg-emoji> ᴘ2ᴘ ᴍᴀʀᴋᴇᴛᴘʟᴀᴄᴇ</b>\n\n<i>ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ.</i>", keyboard)

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
        rarity_key = parts[1]
        order = parts[2]
        sort_order = 1 if order == "asc" else -1
        
        db_emoji, prem_emoji, name = RARITIES.get(rarity_key, RARITIES["common"])
        
        search_terms = [name, rarity_key]
        if rarity_key == "premium":
            search_terms.extend(["Premium Edition", "Premium"])

        # Fetch matching character IDs from all possible character collections
        char_ids = []
        for col_name in ['anime_characters_lol', 'characters', 'collection']:
            col = db[col_name]
            matching_chars = await col.find({
                '$or': [{'rarity': {"$regex": term, "$options": "i"}} for term in search_terms]
            }).to_list(length=None)
            
            for c in matching_chars:
                cid = c.get('id')
                if cid is not None:
                    char_ids.append(cid)
                    if isinstance(cid, int):
                        char_ids.append(str(cid))
                    elif isinstance(cid, str) and cid.isdigit():
                        char_ids.append(int(cid))

        if not char_ids:
            await query.answer("ɴᴏ ᴄʜᴀʀᴀᴄᴛᴇʀs ᴀʀᴇ ᴄᴜʀʀᴇɴᴛʟʏ ғᴏʀ sᴀʟᴇ ɪɴ ᴛʜɪs ʀᴀʀɪᴛʏ!", show_alert=True)
            return

        cursor = market_collection.find({
            'character.id': {'$in': list(set(char_ids))}
        }).sort('price', sort_order).limit(10)
        
        market_items = await cursor.to_list(length=10)

        if not market_items:
            await query.answer("ɴᴏ ᴄʜᴀʀᴀᴄᴛᴇʀs ᴀʀᴇ ᴄᴜʀʀᴇɴᴛʟʏ ғᴏʀ sᴀʟᴇ ɪɴ ᴛʜɪs ʀᴀʀɪᴛʏ!", show_alert=True)
            return

        keyboard = []
        for item in market_items:
            char = item['character']
            char_id = char.get('id')
            
            live_char = await get_live_character_doc(char_id)
            display_char = live_char if live_char else char
            char_name = display_char.get('name', 'Unknown')
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
        
        # --- ABSOLUTE LIVE RARITY & DATA FETCHING ---
        char_id = char.get('id')
        char_name = char.get('name')
        
        live_char = await get_live_character_doc(char_id)
        if not live_char and char_name:
            for col_name in ['anime_characters_lol', 'characters', 'collection']:
                live_char = await db[col_name].find_one({'name': char_name})
                if live_char:
                    break
            
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
            photo=display_char.get('img_url'), 
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

        buyer = await user_collection.find_one({'id': user_id})
        buyer_balance = buyer.get('balance', 0) if buyer else 0

        if buyer_balance < price:
            await query.answer(f"ɪɴsᴜғғɪᴄɪᴇɴᴛ ғᴜɴᴅs! ʏᴏᴜ ɴᴇᴇᴅ 💸 {price:,} ʙᴀʟᴀɴᴄᴇ.", show_alert=True)
            return

        await user_collection.update_one({'id': user_id}, {'$inc': {'balance': -price}, '$push': {'characters': char}})
        await user_collection.update_one({'id': seller_id}, {'$inc': {'balance': price}})
        await market_collection.delete_one({'_id': ObjectId(market_id)})

        await query.message.edit_caption(
            caption=f"🎉 <b>ᴄᴏɴɢʀᴀᴛᴜʟᴀᴛɪᴏɴs!</b> ʏᴏᴜ sᴜᴄᴄᴇssғᴜʟʟʏ ʙᴏᴜɢʜᴛ <b>{to_small_caps(char.get('name'))}</b> ғᴏʀ <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {price:,}.",
            parse_mode='HTML'
        )

    # --------------------------
    # SELL (MY LISTINGS) MENU
    # --------------------------
    elif action == "pm_sm":
        cursor = market_collection.find({'seller_id': user_id})
        listings = await cursor.to_list(length=None)
        
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
            await user_collection.update_one({'id': user_id}, {'$push': {'characters': char}})
            await market_collection.delete_one({'_id': ObjectId(market_id)})
            await query.answer(f"✅ sᴜᴄᴄᴇssғᴜʟʟʏ ʀᴇᴍᴏᴠᴇᴅ ᴀɴᴅ ʀᴇᴛᴜʀɴᴇᴅ ᴛᴏ ɪɴᴠᴇɴᴛᴏʀʏ!", show_alert=True)
        
        cursor = market_collection.find({'seller_id': user_id})
        listings = await cursor.to_list(length=None)
        keyboard = [[InlineKeyboardButton("➕ ʟɪsᴛ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ", callback_data=f"pm_start_s:{user_id}")]]
        for item in listings:
            char_name = to_small_caps(item['character'].get('name', 'Unknown'))
            price = item['price']
            m_id = str(item['_id'])
            btn_text = f"ᴄᴀɴᴄᴇʟ | {char_name} - 💸 {price:,}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pm_delist:{m_id}:{user_id}")])
            
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_m:{user_id}")])
        await update_menu(query, "<b>ʏᴏᴜʀ ᴀᴄᴛɪᴠᴇ ʟɪsᴛɪɴɢs</b>\n\n<i>ᴍᴀɴᴀɢᴇ ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ʟɪsᴛɪɴɢs ᴏʀ ᴀᴅᴅ ᴀ ɴᴇᴡ ᴏɴᴇ.</i>", InlineKeyboardMarkup(keyboard))

# ========================
# CONVERSATION HANDLER FOR SELLING
# ========================
async def sell_start(update: Update, context: CallbackContext):
    query = update.callback_query
    parts = query.data.split(':')
    owner_id = int(parts[-1])
    
    if query.from_user.id != owner_id:
        await query.answer("⚠️ ʏᴏᴜ ᴄᴀɴɴᴏᴛ ɪɴᴛᴇʀᴀᴄᴛ ᴡɪᴛʜ ᴛʜɪs ᴍᴇɴᴜ! ᴘʟᴇᴀsᴇ ᴏᴘᴇɴ ʏᴏᴜʀ ᴏᴡɴ ᴍᴀʀᴋᴇᴛ ᴠɪᴀ /pmarket", show_alert=True)
        return ConversationHandler.END
        
    await query.answer()
    context.user_data['sell_owner_id'] = owner_id

    await query.message.reply_text(
        "💸 <b>Sᴇɴᴅ ᴛʜᴇ ᴄʜᴀʀᴀᴄᴛᴇʀ ID ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ sᴇʟʟ:</b>\n\n(ᴛʏᴘᴇ /cancel ᴛᴏ ᴀʙᴏʀᴛ ᴛʜᴇ ᴘʀᴏᴄᴇss)",
        parse_mode="HTML"
    )

    return WAITING_FOR_CHARACTER_ID

async def ask_character_id(update: Update, context: CallbackContext):
    if not update.message or not update.message.text:
        return WAITING_FOR_CHARACTER_ID

    user_id = update.message.from_user.id
    expected_owner = context.user_data.get('sell_owner_id')
    
    if expected_owner and user_id != expected_owner:
        return WAITING_FOR_CHARACTER_ID

    char_id = update.message.text.strip()
    
    user_data = await user_collection.find_one({'id': user_id})
    if not user_data or 'characters' not in user_data:
        await update.message.reply_text("<b>ʏᴏᴜ ᴅᴏɴ'ᴛ ᴏᴡɴ ᴀɴʏ ᴄʜᴀʀᴀᴄᴛᴇʀs ʏᴇᴛ!</b>", parse_mode='HTML')
        return WAITING_FOR_CHARACTER_ID

    characters = user_data.get('characters', [])
    character = next((c for c in characters if str(c.get('id')) == str(char_id)), None)
    
    if not character:
        await update.message.reply_text(
            "<b>ʏᴏᴜ ᴅᴏɴ'ᴛ ᴏᴡɴ ᴀ ᴄʜᴀʀᴀᴄᴛᴇʀ ᴡɪᴛʜ ᴛʜɪs ɪᴅ!</b> ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴀ ᴠᴀʟɪᴅ ɪᴅ ᴏʀ /cancel.",
            parse_mode='HTML'
        )
        return WAITING_FOR_CHARACTER_ID

    context.user_data['sell_character'] = character
    
    await update.message.reply_text(
        f"✅ <b>Character found! Now send price</b>\n\n"
        f"Selected: <b>{to_small_caps(character.get('name'))}</b>\n"
        f"<i>Enter the price (in <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>) you want to sell it for.</i>",
        parse_mode='HTML'
    )
    return WAITING_FOR_PRICE

async def ask_price(update: Update, context: CallbackContext):
    if not update.message or not update.message.text:
        return WAITING_FOR_PRICE

    user_id = update.message.from_user.id
    expected_owner = context.user_data.get('sell_owner_id')
    
    if expected_owner and user_id != expected_owner:
        return WAITING_FOR_PRICE

    price_text = update.message.text.strip()

    if not price_text.isdigit() or int(price_text) <= 0:
        await update.message.reply_text("<b>ᴘʟᴇᴀsᴇ ᴇɴᴛᴇʀ ᴀ ᴠᴀʟɪᴅ ᴘᴏsɪᴛɪᴠᴇ ɴᴜᴍʙᴇʀ.</b>", parse_mode='HTML')
        return WAITING_FOR_PRICE

    price = int(price_text)
    character = context.user_data.get('sell_character')

    if not character:
        await update.message.reply_text("<b>sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ. ᴘʟᴇᴀsᴇ sᴛᴀʀᴛ ᴀɢᴀɪɴ ᴠɪᴀ /pmarket</b>", parse_mode='HTML')
        return ConversationHandler.END

    char_id_val = character['id']
    
    # Fetch latest live data from correct character collection upon listing
    live_char = await get_live_character_doc(char_id_val)
    final_character = live_char if live_char else character

    await user_collection.update_one(
        {'id': user_id}, 
        {'$pull': {'characters': {'id': char_id_val}}}
    )

    market_item = {
        'seller_id': user_id,
        'price': price,
        'character': final_character
    }
    await market_collection.insert_one(market_item)

    context.user_data.pop('sell_character', None)
    context.user_data.pop('sell_owner_id', None)
    
    await update.message.reply_text(
        f"🎉 <b>{to_small_caps(final_character.get('name'))}</b> ʜᴀs ʙᴇᴇɴ sᴜᴄᴄᴇssғᴜʟʟʏ ʟɪsᴛᴇᴅ ᴏɴ ᴛʜᴇ ᴍᴀʀᴋᴇᴛ ғᴏʀ <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {price:,}!",
        parse_mode='HTML'
    )
    return ConversationHandler.END

async def cancel_sell(update: Update, context: CallbackContext):
    context.user_data.pop('sell_character', None)
    context.user_data.pop('sell_owner_id', None)
    await update.message.reply_text("<b>sᴇʟʟ ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟʟᴇᴅ.</b>", parse_mode='HTML')
    return ConversationHandler.END

# ========================
# HANDLERS SETUP
# ========================
sell_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(
            sell_start,
            pattern=r"^pm_start_s:"
        )
    ],

    states={
        WAITING_FOR_CHARACTER_ID: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                ask_character_id
            )
        ],

        WAITING_FOR_PRICE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                ask_price
            )
        ],
    },

    fallbacks=[
        CommandHandler("cancel", cancel_sell)
    ],

    allow_reentry=True,
    per_user=True,
    per_chat=True,
)

# SELL CONVERSATION — MUST BE BEFORE OTHER MESSAGE HANDLERS
application.add_handler(sell_conv, group=-1)

# PMARKET COMMAND
application.add_handler(
    CommandHandler(["pmarket", "shop"], pmarket_command),
    group=0
)

application.add_handler(CallbackQueryHandler(pmarket_callbacks, pattern='^(pm_m|pm_b|pm_r|pm_s|pm_v|pm_buy|pm_sm|pm_delist):'), group=0)

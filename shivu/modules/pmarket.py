import asyncio
from bson import ObjectId
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from shivu import user_collection, application, db

# IMPORTANT: market_collection yahan explicitly define kar raha hu db se
market_collection = db['market_collection'] 

# --- SMALL CAPS CONVERTER HELPERS ---
SMALL_CAPS_TRANS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
)

def to_small_caps(text: str) -> str:
    if not text:
        return ""
    return str(text).translate(SMALL_CAPS_TRANS)

# --- NEW RARITIES DICT ---
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

# Helper Function to chunk lists for perfect button alignments
def chunk(items: list, size: int) -> list:
    return [items[i:i + size] for i in range(0, len(items), size)]

# Conversation States for Selling
WAITING_FOR_WAIFU_ID, WAITING_FOR_PRICE = 1, 2

# Helper function to prevent "edit_text" errors on photos
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
        [InlineKeyboardButton("💰 ᴍʏ ʟɪsᴛɪɴɢs & sᴇʟʟ", callback_data=f"pm_sm:{user_id}")]
    ])
    await update.message.reply_text(
        "<b><tg-emoji emoji-id=\"6334705977073337764\">🟡</tg-emoji> ᴘ2ᴘ ᴍᴀʀᴋᴇᴛᴘʟᴀᴄᴇ</b>\n\n"
        "<i>ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ.</i>",
        reply_markup=keyboard,
        parse_mode='HTML'
    )

# ========================
# BUY FLOW & CALLBACKS
# ========================
async def pmarket_callbacks(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    parts = data.split(':')
    user_id = query.from_user.id
    
    owner_id = int(parts[-1])
    if user_id != owner_id:
        await query.answer("⚠️ ʏᴏᴜ ᴄᴀɴɴᴏᴛ ɪɴᴛᴇʀᴀᴄᴛ ᴡɪᴛʜ ᴛʜɪs ᴍᴇɴᴜ!", show_alert=True)
        return

    action = parts[0]

    if action == "pm_b":
        buttons = []
        for key, (db_emoji, _, name) in RARITIES.items():
            # Apply to_small_caps directly on the rarity name here!
            buttons.append(InlineKeyboardButton(f"{db_emoji} {to_small_caps(name)}", callback_data=f"pm_r:{key}:{user_id}"))
        
        keyboard = chunk(buttons, 2)
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_m:{user_id}")])
        
        await update_menu(query, "<b>🛒 ʙᴜʏ ᴡᴀɪғᴜs ғʀᴏᴍ ᴍᴀʀᴋᴇᴛ</b>\n\n<i>sᴇʟᴇᴄᴛ ᴀ ʀᴀʀɪᴛʏ ᴛᴏ ᴠɪᴇᴡ ᴘʀᴏᴅᴜᴄᴛs.</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_m":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 ʙᴜʏ", callback_data=f"pm_b:{user_id}")],
            [InlineKeyboardButton("💰 ᴍʏ ʟɪsᴛɪɴɢs & sᴇʟʟ", callback_data=f"pm_sm:{user_id}")]
        ])
        await update_menu(query, "<b><tg-emoji emoji-id=\"6334705977073337764\">🟡</tg-emoji> ᴘ2ᴘ ᴍᴀʀᴋᴇᴛᴘʟᴀᴄᴇ</b>\n\n<i>ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ.</i>", keyboard)

    elif action == "pm_r":
        rarity_key = parts[1]
        db_emoji, prem_emoji, name = RARITIES.get(rarity_key, RARITIES["common"])
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("ᴘʀɪᴄᴇ ʟᴏᴡ ᴛᴏ ʜɪɢʜ", callback_data=f"pm_s:{rarity_key}:asc:{user_id}")],
            [InlineKeyboardButton("ᴘʀɪᴄᴇ ʜɪɢʜ ᴛᴏ ʟᴏᴡ", callback_data=f"pm_s:{rarity_key}:desc:{user_id}")],
            [InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_b:{user_id}")]
        ])
        
        await update_menu(query, f"<b>{prem_emoji} {to_small_caps(name)} ᴡᴀɪғᴜs</b>\n\n<i>ʜᴏᴡ ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ sᴏʀᴛ ᴛʜᴇᴍ?</i>", keyboard)

    elif action == "pm_s":
        rarity_key = parts[1]
        order = parts[2]
        sort_order = 1 if order == "asc" else -1
        
        db_emoji, prem_emoji, name = RARITIES.get(rarity_key, RARITIES["common"])
        
        cursor = market_collection.find({'character.rarity': {"$regex": name, "$options": "i"}}).sort('price', sort_order).limit(10)
        market_items = await cursor.to_list(length=10)

        if not market_items:
            await query.answer("ɴᴏ ᴡᴀɪғᴜs ᴀʀᴇ ᴄᴜʀʀᴇɴᴛʟʏ ғᴏʀ sᴀʟᴇ ɪɴ ᴛʜɪs ʀᴀʀɪᴛʏ!", show_alert=True)
            return

        keyboard = []
        for item in market_items:
            char_name = item['character'].get('name', 'Unknown')
            price = item['price']
            market_id = str(item['_id'])
            
            btn_text = f"{db_emoji} {to_small_caps(char_name)} - 💸 {price:,}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pm_v:{market_id}:{user_id}")])
        
        sort_text = "ʟᴏᴡ ᴛᴏ ʜɪɢʜ" if order == "asc" else "ʜɪɢʜ ᴛᴏ ʟᴏᴡ"
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_r:{rarity_key}:{user_id}")])

        await update_menu(query, f"<b>{prem_emoji} ᴡᴀɪғᴜs ғᴏʀ sᴀʟᴇ</b>\n\n<i>sᴏʀᴛᴇᴅ ʙʏ ᴘʀɪᴄᴇ ({sort_text})</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_v":
        market_id = parts[1]
        item = await market_collection.find_one({'_id': ObjectId(market_id)})
        
        if not item:
            await query.answer("ᴏᴏᴘs! ᴛʜɪs ᴡᴀɪғᴜ ʜᴀs ᴀʟʀᴇᴀᴅʏ ʙᴇᴇɴ sᴏʟᴅ ᴏʀ ʀᴇᴍᴏᴠᴇᴅ!", show_alert=True)
            return

        char = item['character']
        seller_id = item['seller_id']
        price = item['price']
        
        char_rarity_str = char.get('rarity', '')
        prem_emoji = '<tg-emoji emoji-id="6093722470265658964">🟢</tg-emoji>'
        name = "Common"
        
        for k, (d_emoji, p_emoji, r_name) in RARITIES.items():
            if r_name.lower() in char_rarity_str.lower():
                prem_emoji = p_emoji
                name = r_name
                break

        caption = (
            f"<b>{prem_emoji} {to_small_caps(char.get('name', 'Unknown'))}</b>\n\n"
            f"<b><tg-emoji emoji-id=\"6312254267461739671\">⛩</tg-emoji> ᴀɴɪᴍᴇ:</b> {to_small_caps(char.get('anime', 'Unknown'))}\n"
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
            photo=char.get('img_url'), 
            caption=caption,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

    elif action == "pm_buy":
        market_id = parts[1]
        item = await market_collection.find_one({'_id': ObjectId(market_id)})
        
        if not item:
            await query.answer("ᴛᴏᴏ ʟᴀᴛᴇ! ᴛʜɪs ᴡᴀɪғᴜ ʜᴀs ᴀʟʀᴇᴀᴅʏ ʙᴇᴇɴ ʙᴏᴜɢʜᴛ ʙʏ sᴏᴍᴇᴏɴᴇ ᴇʟsᴇ.", show_alert=True)
            return

        price = item['price']
        seller_id = item['seller_id']
        char = item['character']
        
        if seller_id == user_id:
            await query.answer("ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʙᴜʏ ʏᴏᴜʀ ᴏᴡɴ ᴡᴀɪғᴜ!", show_alert=True)
            return

        buyer = await user_collection.find_one({'id': user_id})
        buyer_balance = buyer.get('balance', 0)

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
        
        keyboard = [[InlineKeyboardButton("➕ ʟɪsᴛ ɴᴇᴡ ᴡᴀɪғᴜ", callback_data=f"pm_start_s:{user_id}")]]
        
        for item in listings:
            char_name = to_small_caps(item['character'].get('name', 'Unknown'))
            price = item['price']
            market_id = str(item['_id'])
            btn_text = f"❌ ᴄᴀɴᴄᴇʟ | {char_name} - 💸 {price:,}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pm_delist:{market_id}:{user_id}")])
            
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_m:{user_id}")])
        
        await update_menu(query, "<b>💰 ʏᴏᴜʀ ᴀᴄᴛɪᴠᴇ ʟɪsᴛɪɴɢs</b>\n\n<i>ᴍᴀɴᴀɢᴇ ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ʟɪsᴛɪɴɢs ᴏʀ ᴀᴅᴅ ᴀ ɴᴇᴡ ᴏɴᴇ.</i>", InlineKeyboardMarkup(keyboard))

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
        keyboard = [[InlineKeyboardButton("➕ ʟɪsᴛ ɴᴇᴡ ᴡᴀɪғᴜ", callback_data=f"pm_start_s:{user_id}")]]
        for item in listings:
            char_name = to_small_caps(item['character'].get('name', 'Unknown'))
            price = item['price']
            m_id = str(item['_id'])
            btn_text = f"❌ ᴄᴀɴᴄᴇʟ | {char_name} - 💸 {price:,}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pm_delist:{m_id}:{user_id}")])
            
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_m:{user_id}")])
        await update_menu(query, "<b>💸 ʏᴏᴜʀ ᴀᴄᴛɪᴠᴇ ʟɪsᴛɪɴɢs</b>\n\n<i>ᴍᴀɴᴀɢᴇ ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ʟɪsᴛɪɴɢs ᴏʀ ᴀᴅᴅ ᴀ ɴᴇᴡ ᴏɴᴇ.</i>", InlineKeyboardMarkup(keyboard))


# ========================
# NEW SELL FLOW (Conversation)
# ========================
async def sell_start(update: Update, context: CallbackContext):
    query = update.callback_query
    if query:
        parts = query.data.split(':')
        owner_id = int(parts[-1])
        if query.from_user.id != owner_id:
            await query.answer("⚠️ ʏᴏᴜ ᴄᴀɴɴᴏᴛ ɪɴᴛᴇʀᴀᴄᴛ ᴡɪᴛʜ ᴛʜɪs ᴍᴇɴᴜ!", show_alert=True)
            return ConversationHandler.END

        await query.answer()
        await query.message.edit_text(
            "<b>💸 sᴇʟʟ ʏᴏᴜʀ ᴡᴀɪғᴜ ᴏɴ ᴍᴀʀᴋᴇᴛ</b>\n\n"
            "<i>Sᴛᴇᴘ 1: ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴏɴʟʏ ᴛʜᴇ <b>ᴡᴀɪғᴜ ɪᴅ</b> ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ sᴇʟʟ.</i>\n\n"
            "(ᴛʏᴘᴇ /cancel ᴛᴏ ᴀʙᴏʀᴛ ᴛʜᴇ ᴘʀᴏᴄᴇss)",
            parse_mode='HTML'
        )
    return WAITING_FOR_WAIFU_ID

async def ask_waifu_id(update: Update, context: CallbackContext):
    # .strip() added to avoid accidental spaces from mobile keyboards
    waifu_id = update.message.text.strip()
    user_id = update.message.from_user.id
    
    user_data = await user_collection.find_one({'id': user_id})
    characters = user_data.get('characters', [])
    
    waifu = next((c for c in characters if str(c.get('id')) == str(waifu_id)), None)
    
    if not waifu:
        await update.message.reply_text(
            "<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ʏᴏᴜ ᴅᴏɴ'ᴛ ᴏᴡɴ ᴀ ᴡᴀɪғᴜ ᴡɪᴛʜ ᴛʜɪs ɪᴅ!</b> ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴀ ᴠᴀʟɪᴅ ɪᴅ ᴏʀ /cancel.",
            parse_mode='HTML'
        )
        return WAITING_FOR_WAIFU_ID

    context.user_data['sell_waifu'] = waifu
    
    await update.message.reply_text(
        f"✅ ʏᴏᴜ sᴇʟᴇᴄᴛᴇᴅ <b>{to_small_caps(waifu.get('name'))}</b>.\n\n"
        f"<i>Sᴛᴇᴘ 2: ɴᴏᴡ, ᴇɴᴛᴇʀ ᴛʜᴇ ᴘʀɪᴄᴇ (ɪɴ <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>) ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ sᴇʟʟ ɪᴛ ғᴏʀ.</i>\n\n(E.g., 5000)",
        parse_mode='HTML'
    )
    return WAITING_FOR_PRICE

async def ask_price(update: Update, context: CallbackContext):
    price_text = update.message.text.strip()
    user_id = update.message.from_user.id

    if not price_text.isdigit() or int(price_text) <= 0:
        await update.message.reply_text("<b>ᴘʟᴇᴀsᴇ ᴇɴᴛᴇʀ ᴀ ᴠᴀʟɪᴅ ᴘᴏsɪᴛɪᴠᴇ ɴᴜᴍʙᴇʀ ᴡɪᴛʜᴏᴜᴛ sᴘᴀᴄᴇs ᴏʀ ʟᴇᴛᴛᴇʀs.</b>", parse_mode='HTML')
        return WAITING_FOR_PRICE

    price = int(price_text)
    waifu = context.user_data.get('sell_waifu')

    # Remove waifu from user's inventory
    await user_collection.update_one(
        {'id': user_id}, 
        {'$pull': {'characters': {'id': waifu['id']}}}
    )

    # Add to market collection
    market_item = {
        'seller_id': user_id,
        'price': price,
        'character': waifu
    }
    await market_collection.insert_one(market_item)

    context.user_data.pop('sell_waifu', None)
    
    await update.message.reply_text(
        f"🎉 <b>{to_small_caps(waifu.get('name'))}</b> ʜᴀs ʙᴇᴇɴ sᴜᴄᴄᴇssғᴜʟʟʏ ʟɪsᴛᴇᴅ ᴏɴ ᴛʜᴇ ᴘ2ᴘ ᴍᴀʀᴋᴇᴛ ғᴏʀ <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {price:,}!\n\n"
        f"<i>(ʏᴏᴜ ᴄᴀɴ ᴠɪᴇᴡ ᴏʀ ᴄᴀɴᴄᴇʟ ᴛʜɪs ʟɪsᴛɪɴɢ ɪɴ ᴛʜᴇ /pmarket -> 'Mʏ Lɪsᴛɪɴɢs' ᴍᴇɴᴜ)</i>",
        parse_mode='HTML'
    )
    return ConversationHandler.END

async def cancel_sell(update: Update, context: CallbackContext):
    await update.message.reply_text("<b>sᴇʟʟ ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟʟᴇᴅ.</b>", parse_mode='HTML')
    return ConversationHandler.END

# ========================
# HANDLERS SETUP
# ========================
sell_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(sell_start, pattern='^pm_start_s:')],
    states={
        WAITING_FOR_WAIFU_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_waifu_id)],
        WAITING_FOR_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_price)]
    },
    fallbacks=[CommandHandler('cancel', cancel_sell)],
    per_message=False,
    allow_reentry=True,  # YEH LINE ZAROORI HAI! Taki agar stuck ho, to refresh ho sake.
    block=False
)

application.add_handler(CommandHandler("pmarket", pmarket_command, block=False))
application.add_handler(sell_conv_handler)
application.add_handler(CallbackQueryHandler(pmarket_callbacks, pattern='^(pm_m|pm_b|pm_r|pm_s|pm_v|pm_buy|pm_sm|pm_delist):', block=False))

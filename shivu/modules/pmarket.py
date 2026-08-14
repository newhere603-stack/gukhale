import asyncio
from bson import ObjectId
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler
from shivu import application, db

# --- DATABASE COLLECTIONS ---
user_collection = db['user_collection_lmaoooo']
market_collection = db['market_collection'] 

# --- IN-MEMORY STATES FOR SELLING ---
selling_states = {}

# --- SMALL CAPS CONVERTER HELPERS ---
SMALL_CAPS_TRANS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
)

def to_small_caps(text: str) -> str:
    if not text:
        return ""
    return str(text).translate(SMALL_CAPS_TRANS)

# --- RARITIES ---
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
    "pearl": ("🏖️", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"), 
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
    selling_states.pop(user_id, None)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 ʙᴜʏ", callback_data=f"pm_b:{user_id}")],
        [InlineKeyboardButton("💸 sᴇʟʟ", callback_data=f"pm_sm:{user_id}")]
    ])
    await update.message.reply_text(
        "<b><tg-emoji emoji-id=\"6334705977073337764\">🟡</tg-emoji> ᴘ2ᴘ ᴍᴀʀᴋᴇᴛᴘʟᴀᴄᴇ</b>\n\n"
        "<i>ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ.</i>",
        reply_markup=keyboard,
        parse_mode='HTML'
    )

# ========================
# CANCEL COMMAND
# ========================
async def cancel_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in selling_states:
        selling_states.pop(user_id, None)
        await update.message.reply_text("<b>❌ sᴇʟʟ ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟʟᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ.</b>", parse_mode='HTML')
    else:
        await update.message.reply_text("<b>⚠️ ɴᴏ ᴀᴄᴛɪᴠᴇ sᴇʟʟɪɴɢ ᴘʀᴏᴄᴇss ғᴏᴜɴᴅ.</b>", parse_mode='HTML')

# ========================
# CALLBACKS HANDLER
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
            buttons.append(InlineKeyboardButton(f"{db_emoji} {to_small_caps(name)}", callback_data=f"pm_r:{key}:{user_id}"))
        
        keyboard = chunk(buttons, 2)
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_m:{user_id}")])
        
        await update_menu(query, "<b>🛒 ʙᴜʏ ᴡᴀɪғᴜs ғʀᴏᴍ ᴍᴀʀᴋᴇᴛ</b>\n\n<i>sᴇʟᴇᴄᴛ ᴀ ʀᴀʀɪᴛʏ ᴛᴏ ᴠɪᴇᴡ ᴘʀᴏᴅᴜᴄᴛs.</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_m":
        selling_states.pop(user_id, None)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 ʙᴜʏ", callback_data=f"pm_b:{user_id}")],
            [InlineKeyboardButton("💸 sᴇʟʟ", callback_data=f"pm_sm:{user_id}")]
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
        selling_states.pop(user_id, None)
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
        
        await update_menu(query, "<b>💰 ʏᴏᴜʀ ᴀᴄᴛɪᴠᴇ ʟɪsᴛɪɴɢs</b>\n\n<i>ᴍᴀɴᴀɢᴇ ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ʟɪsᴛɪɴɢs ᴏʀ ᴀᴅⴷ ᴀ ɴᴇᴡ ᴏɴᴇ.</i>", InlineKeyboardMarkup(keyboard))

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
        await update_menu(query, "<b>ʏᴏᴜʀ ᴀᴄᴛɪᴠᴇ ʟɪsᴛɪɴɢs</b>\n\n<i>ᴍᴀɴᴀɢᴇ ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ʟɪsᴛɪɴɢs ᴏʀ ᴀᴅᴅ ᴀ ɴᴇᴡ ᴏɴᴇ.</i>", InlineKeyboardMarkup(keyboard))

    elif action == "pm_start_s":
        user_data = await user_collection.find_one({'id': user_id})
        if not user_data or not user_data.get('characters'):
            await query.answer("❌ ʏᴏᴜ ᴅᴏɴ'ᴛ ᴏᴡɴ ᴀɴʏ ᴄʜᴀʀᴀᴄᴛᴇʀs ʏᴇᴛ!", show_alert=True)
            return

        await query.answer()
        # Inventory characters will be displayed as buttons directly!
        characters = user_data.get('characters', [])[:12] # Limit to 12 buttons for smooth UI
        buttons = []
        for c in characters:
            c_id = str(c.get('id'))
            c_name = to_small_caps(c.get('name', 'Unknown'))
            buttons.append([InlineKeyboardButton(f"🌸 {c_name} (ID: {c_id})", callback_data=f"pm_sel_c:{c_id}:{user_id}")])

        buttons.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_sm:{user_id}")])
        await update_menu(query, "<b>💸 sᴇʟʟ ʏᴏᴜʀ ᴡᴀɪғᴜ ᴏɴ ᴍᴀʀᴋᴇᴛ</b>\n\n<i>sᴇʟᴇᴄᴛ ᴛʜᴇ ᴡᴀɪғᴜ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ sᴇʟʟ ғʀᴏᴍ ʏᴏᴜʀ ɪɴᴠᴇɴᴛᴏʀʏ:</i>", InlineKeyboardMarkup(buttons))

    elif action == "pm_sel_c":
        waifu_id = parts[1]
        user_data = await user_collection.find_one({'id': user_id})
        characters = user_data.get('characters', []) if user_data else []
        waifu = next((c for c in characters if str(c.get('id')) == str(waifu_id)), None)

        if not waifu:
            await query.answer("⚠️ ʏᴏᴜ ᴅᴏɴ'ᴛ ᴏᴡɴ ᴛʜɪs ᴡᴀɪғᴜ ᴀɴʏᴍᴏʀᴇ!", show_alert=True)
            return

        # Price presets ke buttons de rahe hain taaki user ko type na karna pade!
        selling_states[user_id] = {"waifu": waifu}
        await query.answer()
        
        char_name = to_small_caps(waifu.get('name', 'Unknown'))
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💸 1,000", callback_data=f"pm_prc:1000:{user_id}"),
                InlineKeyboardButton("💸 5,000", callback_data=f"pm_prc:5000:{user_id}"),
                InlineKeyboardButton("💸 10,000", callback_data=f"pm_prc:10000:{user_id}")
            ],
            [
                InlineKeyboardButton("💸 25,000", callback_data=f"pm_prc:25000:{user_id}"),
                InlineKeyboardButton("💸 50,000", callback_data=f"pm_prc:50000:{user_id}"),
                InlineKeyboardButton("💸 100,000", callback_data=f"pm_prc:100000:{user_id}")
            ],
            [InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data=f"pm_sm:{user_id}")]
        ])
        
        await update_menu(query, f"✅ sᴇʟᴇᴄᴛᴇᴅ: <b>{char_name}</b>\n\n<i>sᴇʟᴇᴄᴛ ᴛʜᴇ sᴇʟʟɪɴɢ ᴘʀɪᴄᴇ ʙᴇʟᴏᴡ:</i>", keyboard)

    elif action == "pm_prc":
        price = int(parts[1])
        state_data = selling_states.get(user_id)
        
        if not state_data or "waifu" not in state_data:
            await query.answer("⚠️ sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ. ᴘʟᴇᴀsᴇ sᴛᴀʀᴛ ᴀɢᴀɪɴ!", show_alert=True)
            return

        waifu = state_data["waifu"]

        # Double check inventory
        user_data = await user_collection.find_one({'id': user_id})
        characters = user_data.get('characters', []) if user_data else []
        exists = any(str(c.get('id')) == str(waifu['id']) for c in characters)

        if not exists:
            selling_states.pop(user_id, None)
            await query.answer("ʏᴏᴜ ᴅᴏ ɴᴏᴛ oᴡɴ ᴛʜɪs ᴡᴀɪғᴜ ᴀɴʏᴍᴏʀᴇ!", show_alert=True)
            return

        # Remove from inventory and push to market
        await user_collection.update_one(
            {'id': user_id}, 
            {'$pull': {'characters': {'id': waifu['id']}}}
        )

        market_item = {
            'seller_id': user_id,
            'price': price,
            'character': waifu
        }
        await market_collection.insert_one(market_item)
        selling_states.pop(user_id, None)

        success_text = f"🎉 <b>{to_small_caps(waifu.get('name'))}</b> ʜᴀs ʙᴇᴇɴ sᴜᴄᴄᴇssғᴜʟʟʏ ʟɪsᴛᴇᴅ ᴏɴ ᴛʜᴇ ᴘ2ᴘ ᴍᴀʀᴋᴇᴛ ғᴏʀ <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {price:,}!"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛍 ᴠɪᴇᴡ ᴍᴀʀᴋᴇᴛ", callback_data=f"pm_m:{user_id}")]])
        
        await update_menu(query, success_text, keyboard)

# ========================
# HANDLERS SETUP
# ========================
application.add_handler(CommandHandler("pmarket", pmarket_command, block=False))
application.add_handler(CommandHandler("cancel", cancel_command, block=False))
application.add_handler(CallbackQueryHandler(pmarket_callbacks, pattern='^(pm_m|pm_b|pm_r|pm_s|pm_v|pm_buy|pm_sm|pm_delist|pm_start_s|pm_sel_c|pm_prc):', block=False))

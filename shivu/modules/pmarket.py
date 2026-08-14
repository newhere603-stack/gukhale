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
    """Converts regular text to Small Caps font matching your style."""
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
    "premium": ("🔮", '<tg-emoji emoji-id="6093919703753831564">🔮</tg-emoji>', "Premium Edition"),
    "mythic": ("💎", '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>', "Mythic"),
    "sweet": ("🍭", '<tg-emoji emoji-id="6222115531122546353">🍭</tg-emoji>', "Sweet"),
    "valentine": ("💞", '<tg-emoji emoji-id="5255861796350224063">❤️</tg-emoji>', "Valentine"),
    "winter": ("❄️", '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>', "Winter"),
    "neon": ("⚡", '<tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>', "Neon"),
    "pearl": ("🐚", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"),
    "cosmic": ("🌌", '<tg-emoji emoji-id="5431783411981228752">🎆</tg-emoji>', "Cosmic"),
}

# Helper Function to chunk lists for perfect button alignments
def chunk(items: list, size: int) -> list:
    return [items[i:i + size] for i in range(0, len(items), size)]

# Conversation States for Selling
WAITING_FOR_WAIFU_ID, WAITING_FOR_PRICE = 1, 2

# ========================
# MAIN COMMAND
# ========================
async def pmarket_command(update: Update, context: CallbackContext):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 ʙᴜʏ", callback_data="pm_buy_menu")],
        [InlineKeyboardButton("💸 sᴇʟʟ", callback_data="pm_sell_start")]
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
    user_id = query.from_user.id

    if data == "pm_buy_menu":
        buttons = []
        for key, (db_emoji, _, name) in RARITIES.items():
            # Buttons mein DB Emoji use karna padega kyunki Telegram HTML format allow nahi karta idhar
            buttons.append(InlineKeyboardButton(f"{db_emoji} {name}", callback_data=f"pm_rarity_{key}"))
        
        keyboard = chunk(buttons, 2)
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data="pm_main")])
        
        await query.message.edit_text(
            "<b>🛒 ʙᴜʏ ᴡᴀɪғᴜs ғʀᴏᴍ ᴍᴀʀᴋᴇᴛ</b>\n\n<i>sᴇʟᴇᴄᴛ ᴀ ʀᴀʀɪᴛʏ ᴛᴏ ᴠɪᴇᴡ ᴘʀᴏᴅᴜᴄᴛs.</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

    elif data == "pm_main":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 ʙᴜʏ", callback_data="pm_buy_menu")],
            [InlineKeyboardButton("💸 sᴇʟʟ", callback_data="pm_sell_start")]
        ])
        await query.message.edit_text(
            "<b><tg-emoji emoji-id=\"6334705977073337764\">🟡</tg-emoji> ᴘ2ᴘ ᴍᴀʀᴋᴇᴛᴘʟᴀᴄᴇ</b>\n\n"
            "<i>ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ.</i>",
            reply_markup=keyboard,
            parse_mode='HTML'
        )

    elif data.startswith("pm_rarity_"):
        rarity_key = data.split("_")[2]
        db_emoji, prem_emoji, name = RARITIES.get(rarity_key, RARITIES["common"])
        
        keyboard = [
            [InlineKeyboardButton("ᴘʀɪᴄᴇ ʟᴏᴡ ᴛᴏ ʜɪɢʜ", callback_data=f"pm_sort_{rarity_key}_asc")],
            [InlineKeyboardButton("ᴘʀɪᴄᴇ ʜɪɢʜ ᴛᴏ ʟᴏᴡ", callback_data=f"pm_sort_{rarity_key}_desc")],
            [InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data="pm_buy_menu")]
        ]
        
        await query.message.edit_text(
            f"<b>{prem_emoji} {to_small_caps(name)} ᴡᴀɪғᴜs</b>\n\n<i>ʜᴏᴡ ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ sᴏʀᴛ ᴛʜᴇᴍ?</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

    elif data.startswith("pm_sort_"):
        _, _, rarity_key, order = data.split("_")
        sort_order = 1 if order == "asc" else -1
        
        db_emoji, prem_emoji, name = RARITIES.get(rarity_key, RARITIES["common"])
        
        # Regex search se database query optimize kar rahe hai
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
            
            # DB Emoji for inline button text
            btn_text = f"{db_emoji} {to_small_caps(char_name)} - 💸 {price:,}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pm_view_{market_id}")])
        
        sort_text = "ʟᴏᴡ ᴛᴏ ʜɪɢʜ" if order == "asc" else "ʜɪɢʜ ᴛᴏ ʟᴏᴡ"
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"pm_rarity_{rarity_key}")])

        await query.message.edit_text(
            f"<b>{prem_emoji} ᴡᴀɪғᴜs ғᴏʀ sᴀʟᴇ</b>\n\n<i>sᴏʀᴛᴇᴅ ʙʏ ᴘʀɪᴄᴇ ({sort_text})</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )

    elif data.startswith("pm_view_"):
        market_id = data.split("_")[2]
        item = await market_collection.find_one({'_id': ObjectId(market_id)})
        
        if not item:
            await query.answer("ᴏᴏᴘs! ᴛʜɪs ᴡᴀɪғᴜ ʜᴀs ᴀʟʀᴇᴀᴅʏ ʙᴇᴇɴ sᴏʟᴅ ᴏʀ ʀᴇᴍᴏᴠᴇᴅ!", show_alert=True)
            return

        char = item['character']
        seller_id = item['seller_id']
        price = item['price']
        
        # Get rarity info safely, finding it based on character's stored rarity string
        char_rarity_str = char.get('rarity', '')
        prem_emoji = '<tg-emoji emoji-id="6093722470265658964">🟢</tg-emoji>' # Default
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
            [InlineKeyboardButton("🛒 ʙᴜʏ ɴᴏᴡ", callback_data=f"pm_buy_{market_id}")],
            [InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data="pm_buy_menu")]
        ])

        await query.message.delete()
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=char.get('img_url'), 
            caption=caption,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

    elif data.startswith("pm_buy_"):
        market_id = data.split("_")[2]
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

        # Transaction Successful - Balance update
        await user_collection.update_one({'id': user_id}, {'$inc': {'balance': -price}, '$push': {'characters': char}})
        await user_collection.update_one({'id': seller_id}, {'$inc': {'balance': price}})
        await market_collection.delete_one({'_id': ObjectId(market_id)})

        await query.message.edit_caption(
            caption=f"🎉 <b>ᴄᴏɴɢʀᴀᴛᴜʟᴀᴛɪᴏɴs!</b> ʏᴏᴜ sᴜᴄᴄᴇssғᴜʟʟʏ ʙᴏᴜɢʜᴛ <b>{to_small_caps(char.get('name'))}</b> ғᴏʀ <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {price:,}.",
            parse_mode='HTML'
        )


# ========================
# SELL FLOW
# ========================
async def sell_start(update: Update, context: CallbackContext):
    query = update.callback_query
    if query:
        await query.answer()
        await query.message.reply_text(
            "<b>💸 sᴇʟʟ ʏᴏᴜʀ ᴡᴀɪғᴜ ᴏɴ ᴍᴀʀᴋᴇᴛ</b>\n\n"
            "<i>ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ᴡᴀɪғᴜ ɪᴅ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ sᴇʟʟ.</i>\n"
            "(ᴛʏᴘᴇ /cancel ᴛᴏ ᴀʙᴏʀᴛ ᴛʜᴇ ᴘʀᴏᴄᴇss)",
            parse_mode='HTML'
        )
    return WAITING_FOR_WAIFU_ID

async def ask_waifu_id(update: Update, context: CallbackContext):
    waifu_id = update.message.text
    user_id = update.message.from_user.id
    
    if waifu_id.lower() == '/cancel':
        await update.message.reply_text("<b>sᴇʟʟ ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟʟᴇᴅ.</b>", parse_mode='HTML')
        return ConversationHandler.END

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
        f"ʏᴏᴜ sᴇʟᴇᴄᴛᴇᴅ <b>{to_small_caps(waifu.get('name'))}</b>.\n\n"
        f"<i>ɴᴏᴡ, ᴇɴᴛᴇʀ ᴛʜᴇ ᴘʀɪᴄᴇ (ɪɴ <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>) ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ sᴇʟʟ ɪᴛ ғᴏʀ.</i>",
        parse_mode='HTML'
    )
    return WAITING_FOR_PRICE

async def ask_price(update: Update, context: CallbackContext):
    price_text = update.message.text
    user_id = update.message.from_user.id
    
    if price_text.lower() == '/cancel':
        await update.message.reply_text("<b>sᴇʟʟ ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟʟᴇᴅ.</b>", parse_mode='HTML')
        return ConversationHandler.END

    if not price_text.isdigit() or int(price_text) <= 0:
        await update.message.reply_text("<b>ᴘʟᴇᴀsᴇ ᴇɴᴛᴇʀ ᴀ ᴠᴀʟɪᴅ ᴘᴏsɪᴛɪᴠᴇ ɴᴜᴍʙᴇʀ.</b>", parse_mode='HTML')
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
        f"✅ <b>{to_small_caps(waifu.get('name'))}</b> ʜᴀs ʙᴇᴇɴ sᴜᴄᴄᴇssғᴜʟʟʏ ʟɪsᴛᴇᴅ ᴏɴ ᴛʜᴇ ᴘ2ᴘ ᴍᴀʀᴋᴇᴛ ғᴏʀ <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {price:,}!",
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
    entry_points=[CallbackQueryHandler(sell_start, pattern='^pm_sell_start$')],
    states={
        WAITING_FOR_WAIFU_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_waifu_id)],
        WAITING_FOR_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_price)]
    },
    fallbacks=[CommandHandler('cancel', cancel_sell)],
    per_message=False,
    block=False
)

application.add_handler(CommandHandler("pmarket", pmarket_command, block=False))
application.add_handler(sell_conv_handler)
application.add_handler(CallbackQueryHandler(pmarket_callbacks, pattern='^pm_', block=False))

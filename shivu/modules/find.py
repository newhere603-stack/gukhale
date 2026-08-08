import random
import traceback
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from shivu import application, db, user_collection

# --- Databases ---
try:
    from shivu import collection
except ImportError:
    collection = db['anime_characters_lol'] 

try:
    auction_collection = db['auctions']
except ImportError:
    pass

OWNER_ID = 7657218453

DEFAULT_PRICES = {
    "🟢 Common": 1000, "🟠 Rare": 3200, "🔵 Medium": 2900, 
    "🟡 Legendary": 5000, "🪽 Celestial": 70000, "🥵 Spicy": 15000, 
    "💮 Exclusive": 12000, "💎 Mythic": 35000, "🔮 Premium Edition": 20000, 
    "🍭 Sweet": 52000, "💞 Valentine": 90000, "❄️ Winter": 55000, 
    "⚡ Neon": 67000, "🐚 Summer": 60000, "🌌 Cosmic": 90000
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


# --- Set Price Command (Owner Only) ---
async def set_mp_price(update: Update, context: CallbackContext):
    try:
        if update.effective_user.id != OWNER_ID:
            return # Silent for non-owners
        
        if len(context.args) != 2:
            msg = "Usage: /setprice [char_id] [price]\nExample: /setprice 7742 15000"
            await update.message.reply_text(f"<blockquote>{bold_sc(msg)}</blockquote>", parse_mode='HTML')
            return
            
        raw_char_id = context.args[0]
        try:
            price = int(context.args[1])
        except ValueError:
            await update.message.reply_text(bold_sc("Price must be in numbers."), parse_mode='HTML')
            return
            
        query = {'$or': [{'id': raw_char_id}, {'id': int(raw_char_id)}]} if raw_char_id.isdigit() else {'id': raw_char_id}
        result = await collection.update_many(query, {'$set': {'mp_price': price}})
            
        if result.modified_count > 0 or result.matched_count > 0:
            await update.message.reply_text(bold_sc(f"Character ID {raw_char_id} marketplace price set to {price:,}."), parse_mode='HTML')
        else:
            await update.message.reply_text(bold_sc("Character ID not found."), parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"Error in setprice: {str(e)}")


# --- Generate/Load User Deals ---
async def load_user_deals(user_id):
    user = await user_collection.find_one({'id': user_id})
    if not user:
        return None
        
    current_day = get_current_mp_day()
    mp_data = user.get('mp_data', {})
    
    if mp_data.get('day') != current_day or not mp_data.get('chars'):
        # Sirf normal characters pick karna (auction exclusive ko chhod kar)
        total_chars = await collection.count_documents({'auction_exclusive': {'$ne': True}})
        if total_chars < 2:
            return None
            
        indices = random.sample(range(total_chars), 2)
        char1 = await collection.find_one({'auction_exclusive': {'$ne': True}}, skip=indices[0])
        char2 = await collection.find_one({'auction_exclusive': {'$ne': True}}, skip=indices[1])
        
        chars = [char1, char2]
        formatted_chars = []
        
        for c in chars:
            if not c: continue
            orig = get_price(c)
            disc = random.randint(2, 15)
            sale = int(orig - (orig * (disc / 100)))
            formatted_chars.append({
                'id': c.get('id'),
                'mp_orig': orig,
                'mp_disc': disc,
                'mp_sale': sale,
                'is_sold': False
            })
            
        mp_data = {'day': current_day, 'chars': formatted_chars}
        await user_collection.update_one({'id': user_id}, {'$set': {'mp_data': mp_data}})
        user['mp_data'] = mp_data

    updated_chars = []
    need_db_update = False
    
    for item in user['mp_data']['chars']:
        char_id = item.get('id')
        query = {'$or': [{'id': char_id}, {'id': str(char_id)}]} if str(char_id).isdigit() else {'id': char_id}
        db_char = await collection.find_one(query)
        
        if db_char:
            orig = get_price(db_char)
            disc = item.get('mp_disc', 10)
            sale = int(orig - (orig * (disc / 100)))
            
            db_char['mp_orig'] = orig
            db_char['mp_disc'] = disc
            db_char['mp_sale'] = sale
            db_char['is_sold'] = item.get('is_sold', False)
            updated_chars.append(db_char)

            if item.get('mp_orig') != orig:
                item['mp_orig'] = orig
                item['mp_sale'] = sale
                need_db_update = True
                
    if need_db_update:
        await user_collection.update_one({'id': user_id}, {'$set': {'mp_data': user['mp_data']}})

    user['mp_data']['chars'] = updated_chars
    return user


# --- UI Renderer ---
async def render_mp_message(update_obj, user, index, is_edit=False):
    chars = user['mp_data']['chars']
    if index >= len(chars): index = 0
    
    char = chars[index]
    user_id = user['id'] 
    owned_count = len([c for c in user.get('characters', []) if str(c.get('id')) == str(char.get('id'))])
    
    name = str(char.get('name', 'Unknown')).upper()
    anime = str(char.get('anime', 'Unknown')).upper()
    char_id = char.get('id', 'N/A')
    rarity = str(char.get('rarity', 'Unknown'))
    
    status_text = f"❌ {bold_sc('SOLD')}" if char.get('is_sold') else f"🛒 {bold_sc('AVAILABLE')}"

    caption = f"""🏪 {bold_sc(f'DAILY DEALS ({index+1}/2)')}

🌸 {bold_sc('NAME:')} {bold_sc(name)}
🎞️ {bold_sc('SERIES:')} {bold_sc(anime)}
🆔 {bold_sc('ID:')} {bold_sc(str(char_id))}
💫 {bold_sc('RARITY:')} {bold_sc(rarity)}
💸 {bold_sc('ORIGINAL:')} {bold_sc(f"{char['mp_orig']:,}")}
🏷️ {bold_sc('SALE PRICE:')} {bold_sc(f"{char['mp_sale']:,}")}
📊 {bold_sc('DISCOUNT:')} {bold_sc(f"{char['mp_disc']}%")}
📋 {bold_sc('STATUS:')} {status_text}
🗂️ {bold_sc('OWNED:')} {bold_sc(str(owned_count))}"""

    nav_index = 1 if index == 0 else 0

    buttons = [
        [
            InlineKeyboardButton("⋞", callback_data=f"mp_nav_{user_id}_{nav_index}"),
            InlineKeyboardButton(to_small_caps("Buy"), callback_data=f"mp_buy_{user_id}_{index}"),
            InlineKeyboardButton("⋟", callback_data=f"mp_nav_{user_id}_{nav_index}")
        ],
        [InlineKeyboardButton(f"🍃 {to_small_caps('Auction')}", callback_data=f"mp_auc_{user_id}")],
        [InlineKeyboardButton(to_small_caps("Refresh (30,000 💸)"), callback_data=f"mp_ref_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    img_url = char.get('img_url')

    if is_edit:
        try:
            if update_obj.message.photo and img_url and str(img_url).startswith("http"):
                try:
                    await update_obj.edit_message_media(
                        media=InputMediaPhoto(media=img_url, caption=caption, parse_mode='HTML'),
                        reply_markup=reply_markup
                    )
                except Exception:
                    await update_obj.edit_message_caption(caption=caption, reply_markup=reply_markup, parse_mode='HTML')
            else:
                try:
                    await update_obj.edit_message_caption(caption=caption, reply_markup=reply_markup, parse_mode='HTML')
                except Exception:
                    await update_obj.edit_message_text(text=caption, reply_markup=reply_markup, parse_mode='HTML')
        except Exception:
            await update_obj.edit_message_text(text=caption, reply_markup=reply_markup, parse_mode='HTML')
    else:
        sent_as_photo = False
        if img_url and str(img_url).startswith("http"):
            try:
                await update_obj.message.reply_photo(photo=img_url, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
                sent_as_photo = True
            except Exception:
                sent_as_photo = False
        
        if not sent_as_photo:
            await update_obj.message.reply_text(text=caption, reply_markup=reply_markup, parse_mode='HTML')


# --- Marketplace Command ---
async def marketplace(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        user = await load_user_deals(user_id)
        
        if not user:
            await update.message.reply_text(bold_sc("Please /start the bot first to create an account."), parse_mode='HTML')
            return
            
        await render_mp_message(update, user, 0, is_edit=False)
    except Exception as e:
        await update.message.reply_text(f"Error Command: {str(e)}")


# --- Combined Callbacks (Deals & Auction Buttons) ---
async def marketplace_callbacks(update: Update, context: CallbackContext):
    try:
        query = update.callback_query
        clicker_id = query.from_user.id
        data = query.data
        parts = data.split("_")
        
        # Marketplace Deals Navigation & Buy Logic
        if data.startswith("mp_"):
            owner_id = int(parts[2])
            if clicker_id != owner_id:
                await query.answer(to_small_caps("This is not your marketplace! Type /mp to open yours."), show_alert=True)
                return
                
            user_id = owner_id
            user = await load_user_deals(user_id)
            if not user:
                await query.answer(to_small_caps("Account not found!"), show_alert=True)
                return

            if data.startswith("mp_nav_"):
                index = int(parts[3])
                await render_mp_message(query, user, index, is_edit=True)
                await query.answer()
                return

            if data.startswith("mp_buy_"):
                index = int(parts[3])
                chars = user['mp_data']['chars']
                char = chars[index]
                
                if char.get('is_sold'):
                    await query.answer(to_small_caps("You have already purchased this character!"), show_alert=True)
                    return
                    
                user_balance = user.get('balance', 0)
                price = char['mp_sale']
                
                if user_balance < price:
                    await query.answer(to_small_caps(f"Low balance! (Required: {price:,} | Yours: {user_balance:,})"), show_alert=True)
                    return
                    
                char['is_sold'] = True
                clean_char = {k: v for k, v in char.items() if k not in ['mp_orig', 'mp_disc', 'mp_sale', 'is_sold']}
                
                raw_mp_chars = []
                for c in user['mp_data']['chars']:
                    raw_mp_chars.append({
                        'id': c.get('id'), 'mp_orig': c.get('mp_orig'), 'mp_disc': c.get('mp_disc'), 
                        'mp_sale': c.get('mp_sale'), 'is_sold': c.get('is_sold', False)
                    })
                
                await user_collection.update_one(
                    {'id': user_id},
                    {'$inc': {'balance': -price}, '$push': {'characters': clean_char}, '$set': {'mp_data.chars': raw_mp_chars}}
                )
                
                await query.answer(to_small_caps(f"✅ Transaction successful! You bought {char.get('name')}."), show_alert=True)
                await render_mp_message(query, user, index, is_edit=True)
                return

            if data.startswith("mp_ref_"):
                user_balance = user.get('balance', 0)
                cost = 30000
                
                if user_balance < cost:
                    await query.answer(to_small_caps("Not enough coins to refresh! (Required: 30,000)"), show_alert=True)
                    return
                    
                await user_collection.update_one({'id': user_id}, {'$inc': {'balance': -cost}, '$set': {'mp_data.day': "FORCE_REFRESH"}})
                new_user = await load_user_deals(user_id)
                await render_mp_message(query, new_user, 0, is_edit=True)
                await query.answer(to_small_caps("Marketplace successfully refreshed!"), show_alert=False)
                return

            # Opens Live Auction UI
            if data.startswith("mp_auc_"):
                active_auc = await auction_collection.find_one({'status': 'active'})
                
                if not active_auc:
                    await query.answer(to_small_caps("There is no active auction right now!"), show_alert=True)
                    return
                    
                caption = f"""🍃 {bold_sc('LIVE AUCTION')} 🍃

🌸 {bold_sc('NAME:')} {bold_sc(active_auc['char_name'])}
🎞️ {bold_sc('SERIES:')} {bold_sc(active_auc['anime'])}
💫 {bold_sc('RARITY:')} {bold_sc(active_auc['rarity'])}

👑 {bold_sc('TOP BIDDER:')} {bold_sc(active_auc['highest_bidder_name'])}
💰 {bold_sc('CURRENT BID:')} {bold_sc(f"{active_auc['highest_bid']:,} 💸")}"""

                buttons = [
                    [
                        InlineKeyboardButton(to_small_caps("+ 1,000"), callback_data="auc_bid_1000"),
                        InlineKeyboardButton(to_small_caps("+ 5,000"), callback_data="auc_bid_5000"),
                        InlineKeyboardButton(to_small_caps("+ 10,000"), callback_data="auc_bid_10000")
                    ],
                    [InlineKeyboardButton(to_small_caps("🔙 Back to Deals"), callback_data=f"mp_back_{user_id}")]
                ]
                
                reply_markup = InlineKeyboardMarkup(buttons)
                img_url = active_auc.get('img_url')

                try:
                    if update.callback_query.message.photo and img_url:
                        await query.edit_message_media(
                            media=InputMediaPhoto(media=img_url, caption=caption, parse_mode='HTML'),
                            reply_markup=reply_markup
                        )
                    else:
                        await query.edit_message_caption(caption=caption, reply_markup=reply_markup, parse_mode='HTML')
                except Exception:
                    await query.edit_message_text(text=caption, reply_markup=reply_markup, parse_mode='HTML')
                return

            # Back button from Auction
            if data.startswith("mp_back_"):
                await render_mp_message(query, user, 0, is_edit=True)
                return

        # Auction Bidding Logic
        if data.startswith("auc_bid_"):
            increment = int(parts[2])
            user_name = query.from_user.first_name
            
            active_auc = await auction_collection.find_one({'status': 'active'})
            if not active_auc:
                await query.answer(to_small_caps("Auction has already ended!"), show_alert=True)
                return
                
            new_bid = active_auc['highest_bid'] + increment
            
            user = await user_collection.find_one({'id': clicker_id})
            if not user or user.get('balance', 0) < new_bid:
                await query.answer(to_small_caps(f"Low balance! You need at least {new_bid:,} 💸"), show_alert=True)
                return
                
            if active_auc.get('highest_bidder_id') == clicker_id:
                await query.answer(to_small_caps("You are already the highest bidder!"), show_alert=True)
                return
                
            await auction_collection.update_one(
                {'_id': active_auc['_id']},
                {'$set': {'highest_bid': new_bid, 'highest_bidder_id': clicker_id, 'highest_bidder_name': user_name}}
            )
            
            await query.answer(to_small_caps(f"✅ Bid placed! New highest bid: {new_bid:,}"), show_alert=True)
            
            new_caption = f"""🍃 {bold_sc('LIVE AUCTION')} 🍃

🌸 {bold_sc('NAME:')} {bold_sc(active_auc['char_name'])}
🎞️ {bold_sc('SERIES:')} {bold_sc(active_auc['anime'])}
💫 {bold_sc('RARITY:')} {bold_sc(active_auc['rarity'])}

👑 {bold_sc('TOP BIDDER:')} {bold_sc(user_name)}
💰 {bold_sc('CURRENT BID:')} {bold_sc(f"{new_bid:,} 💸")}"""

            buttons = [
                [
                    InlineKeyboardButton(to_small_caps("+ 1,000"), callback_data="auc_bid_1000"),
                    InlineKeyboardButton(to_small_caps("+ 5,000"), callback_data="auc_bid_5000"),
                    InlineKeyboardButton(to_small_caps("+ 10,000"), callback_data="auc_bid_10000")
                ],
                # Yahan wapas mp_back ke andar current clicker ki ID pass karenge kyunki usne khola hai
                [InlineKeyboardButton(to_small_caps("🔙 Back to Deals"), callback_data=f"mp_back_{clicker_id}")]
            ]
            
            try:
                await query.edit_message_caption(caption=new_caption, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')
            except Exception:
                pass # Already updated

    except Exception as e:
        if update.callback_query:
            await update.callback_query.answer(f"Error: {str(e)}", show_alert=True)


# --- AUCTION OWNER COMMANDS ---
async def start_auction(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return # Silent fail for non-owner
    
    if len(context.args) < 2:
        await update.message.reply_text(bold_sc("Usage: /startauction [char_id] [starting_bid]"), parse_mode='HTML')
        return
        
    char_id = context.args[0]
    try:
        starting_bid = int(context.args[1])
    except ValueError:
        await update.message.reply_text(bold_sc("Bid amount must be a number."), parse_mode='HTML')
        return
        
    query = {'$or': [{'id': char_id}, {'id': str(char_id)}, {'id': int(char_id)}]}
    char = await collection.find_one(query)
    
    if not char:
        await update.message.reply_text(bold_sc("Character not found!"), parse_mode='HTML')
        return
        
    active_auc = await auction_collection.find_one({'status': 'active'})
    if active_auc:
        await update.message.reply_text(bold_sc("An auction is already running! /endauction first."), parse_mode='HTML')
        return
        
    # Exclude permanently from standard spawns/marketplace
    await collection.update_one(query, {'$set': {'auction_exclusive': True}})
    
    auction_data = {
        'char_id': char.get('id'),
        'char_name': char.get('name', 'Unknown'),
        'anime': char.get('anime', 'Unknown'),
        'rarity': char.get('rarity', 'Unknown'),
        'img_url': char.get('img_url'),
        'highest_bid': starting_bid,
        'highest_bidder_id': None,
        'highest_bidder_name': 'None',
        'status': 'active'
    }
    await auction_collection.insert_one(auction_data)
    
    msg = f"🎉 AUCTION STARTED! 🎉\n\nCHARACTER: {char.get('name')}\nSTARTING BID: {starting_bid:,} 💸\n\nPLAYERS CAN NOW BID FROM THE /mp MENU!"
    
    if char.get('img_url'):
        await update.message.reply_photo(photo=char.get('img_url'), caption=bold_sc(msg), parse_mode='HTML')
    else:
        await update.message.reply_text(bold_sc(msg), parse_mode='HTML')


async def end_auction(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return # Silent fail for non-owner
        
    active_auc = await auction_collection.find_one({'status': 'active'})
    if not active_auc:
        await update.message.reply_text(bold_sc("No active auction to end."), parse_mode='HTML')
        return
        
    await auction_collection.update_one({'_id': active_auc['_id']}, {'$set': {'status': 'ended'}})
    
    bidder_id = active_auc.get('highest_bidder_id')
    if not bidder_id:
        await update.message.reply_text(bold_sc("Auction ended! No one placed a bid."), parse_mode='HTML')
        return
        
    bidder = await user_collection.find_one({'id': bidder_id})
    char_query = {'$or': [{'id': active_auc['char_id']}, {'id': str(active_auc['char_id'])}, {'id': int(active_auc['char_id'])}]}
    char = await collection.find_one(char_query)
    
    if bidder and char:
        clean_char = {k: v for k, v in char.items() if k not in ['auction_exclusive', 'mp_orig', 'mp_disc', 'mp_sale', 'is_sold']}
        
        await user_collection.update_one(
            {'id': bidder_id},
            {
                '$inc': {'balance': -active_auc['highest_bid']},
                '$push': {'characters': clean_char}
            }
        )
        
        msg = f"🎊 AUCTION ENDED! 🎊\n\nWINNER: {active_auc['highest_bidder_name']}\nWINNING BID: {active_auc['highest_bid']:,} 💸\n\nCHARACTER HAS BEEN SENT TO THE WINNER!"
        await update.message.reply_text(bold_sc(msg), parse_mode='HTML')


# --- Handler Registrations ---
application.add_handler(CommandHandler(["mp", "marketplace"], marketplace, block=False))
application.add_handler(CommandHandler("setprice", set_mp_price, block=False))
application.add_handler(CommandHandler("startauction", start_auction, block=False))
application.add_handler(CommandHandler("endauction", end_auction, block=False))

# Combined pattern for all marketplace and auction buttons
application.add_handler(CallbackQueryHandler(marketplace_callbacks, pattern="^(mp_|auc_bid_)", block=False))

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
            return 
        
        if len(context.args) != 2:
            msg = "Usage: /setprice [char_id] [price]"
            await update.message.reply_text(f"<blockquote>{bold_sc(msg)}</blockquote>", parse_mode='HTML')
            return
            
        raw_char_id = context.args[0]
        price = int(context.args[1])
        query = {'$or': [{'id': raw_char_id}, {'id': int(raw_char_id)}]} if raw_char_id.isdigit() else {'id': raw_char_id}
        result = await collection.update_many(query, {'$set': {'mp_price': price}})
            
        if result.modified_count > 0 or result.matched_count > 0:
            await update.message.reply_text(bold_sc(f"Price set to {price:,}."), parse_mode='HTML')
    except Exception as e:
        pass


# --- Deals Loader ---
async def load_user_deals(user_id):
    user = await user_collection.find_one({'id': user_id})
    if not user: return None
        
    current_day = get_current_mp_day()
    mp_data = user.get('mp_data', {})
    
    if mp_data.get('day') != current_day or not mp_data.get('chars'):
        total_chars = await collection.count_documents({'auction_exclusive': {'$ne': True}})
        if total_chars < 2: return None
            
        indices = random.sample(range(total_chars), 2)
        char1 = await collection.find_one({'auction_exclusive': {'$ne': True}}, skip=indices[0])
        char2 = await collection.find_one({'auction_exclusive': {'$ne': True}}, skip=indices[1])
        
        formatted_chars = []
        for c in [char1, char2]:
            if not c: continue
            orig = get_price(c)
            disc = random.randint(2, 15)
            sale = int(orig - (orig * (disc / 100)))
            formatted_chars.append({'id': c.get('id'), 'mp_orig': orig, 'mp_disc': disc, 'mp_sale': sale, 'is_sold': False})
            
        mp_data = {'day': current_day, 'chars': formatted_chars}
        await user_collection.update_one({'id': user_id}, {'$set': {'mp_data': mp_data}})
        user['mp_data'] = mp_data

    updated_chars = []
    for item in user['mp_data']['chars']:
        char_id = item.get('id')
        query = {'$or': [{'id': char_id}, {'id': str(char_id)}]} if str(char_id).isdigit() else {'id': char_id}
        db_char = await collection.find_one(query)
        if db_char:
            orig = get_price(db_char)
            db_char['mp_orig'] = orig
            db_char['mp_disc'] = item.get('mp_disc', 10)
            db_char['mp_sale'] = int(orig - (orig * (db_char['mp_disc'] / 100)))
            db_char['is_sold'] = item.get('is_sold', False)
            updated_chars.append(db_char)

    user['mp_data']['chars'] = updated_chars
    return user


# --- UIs ---
async def render_mp_message(update_obj, user, index, is_edit=False):
    chars = user['mp_data']['chars']
    if index >= len(chars): index = 0
    char = chars[index]
    user_id = user['id'] 
    
    status_text = f"❌ {bold_sc('SOLD')}" if char.get('is_sold') else f"🛒 {bold_sc('AVAILABLE')}"

    caption = f"""🏪 {bold_sc(f'DAILY DEALS ({index+1}/2)')}

🌸 {bold_sc('NAME:')} {bold_sc(str(char.get('name', 'Unknown')).upper())}
🎞️ {bold_sc('SERIES:')} {bold_sc(str(char.get('anime', 'Unknown')).upper())}
🆔 {bold_sc('ID:')} {bold_sc(str(char.get('id', 'N/A')))}
💫 {bold_sc('RARITY:')} {bold_sc(str(char.get('rarity', 'Unknown')))}
💸 {bold_sc('ORIGINAL:')} {bold_sc(f"{char['mp_orig']:,}")}
🏷️ {bold_sc('SALE PRICE:')} {bold_sc(f"{char['mp_sale']:,}")}
📊 {bold_sc('DISCOUNT:')} {bold_sc(f"{char['mp_disc']}%")}
📋 {bold_sc('STATUS:')} {status_text}"""

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
            if update_obj.message.photo and img_url:
                await update_obj.edit_message_media(media=InputMediaPhoto(media=img_url, caption=caption, parse_mode='HTML'), reply_markup=reply_markup)
            else:
                await update_obj.edit_message_caption(caption=caption, reply_markup=reply_markup, parse_mode='HTML')
        except Exception:
            pass
    else:
        if img_url:
            await update_obj.message.reply_photo(photo=img_url, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update_obj.message.reply_text(text=caption, reply_markup=reply_markup, parse_mode='HTML')


async def render_auction_ui(query, active_auc, user_id, proposed_bid=None):
    min_bid = active_auc['highest_bid'] + 1000
    if proposed_bid is None or proposed_bid < min_bid:
        proposed_bid = min_bid

    # Top 3 Bids Logic
    top_bids = active_auc.get('top_bids', [])
    top_3_text = f"\n\n🏆 {bold_sc('TOP BIDS:')}\n"
    
    if top_bids:
        for i, b in enumerate(top_bids[:3]):
            medal = ["🥇", "🥈", "🥉"][i]
            # Normal font for user name, HTML safe
            clean_name = str(b['name']).replace('<', '&lt;').replace('>', '&gt;')
            
            # 🔥 BUG FIX: Variable banakar f-string mein daala taaki SyntaxError na aaye
            bid_amount = b['bid']
            top_3_text += f"{medal} {clean_name}: {bold_sc(f'{bid_amount:,} 💸')}\n"
    else:
        top_3_text += f"👻 {bold_sc('No bids placed yet!')}\n"

    caption = f"""🍃 {bold_sc('LIVE AUCTION')} 🍃

🌸 {bold_sc('NAME:')} {bold_sc(active_auc['char_name'])}
🎞️ {bold_sc('SERIES:')} {bold_sc(active_auc['anime'])}
💫 {bold_sc('RARITY:')} {bold_sc(active_auc['rarity'])}{top_3_text}"""

    buttons = [
        [
            InlineKeyboardButton("⋞", callback_data=f"auc_adj_{user_id}_-1000_{proposed_bid}"),
            InlineKeyboardButton(f"{proposed_bid:,}", callback_data=f"auc_none_{user_id}"),
            InlineKeyboardButton("⋟", callback_data=f"auc_adj_{user_id}_1000_{proposed_bid}")
        ],
        [InlineKeyboardButton(to_small_caps("Confirm Bid"), callback_data=f"auc_conf_{user_id}_{proposed_bid}")],
        [InlineKeyboardButton(to_small_caps("Cancel Bid"), callback_data=f"auc_can_{user_id}")],
        [InlineKeyboardButton(to_small_caps("⟲ Back"), callback_data=f"mp_back_{user_id}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(buttons)
    img_url = active_auc.get('img_url')
    
    try:
        if query.message.photo and img_url:
            await query.edit_message_media(media=InputMediaPhoto(media=img_url, caption=caption, parse_mode='HTML'), reply_markup=reply_markup)
        else:
            await query.edit_message_caption(caption=caption, reply_markup=reply_markup, parse_mode='HTML')
    except Exception:
        pass


# --- Commands & Callbacks ---
async def marketplace(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user = await load_user_deals(user_id)
    if not user:
        await update.message.reply_text(bold_sc("Please /start the bot first."), parse_mode='HTML')
        return
    await render_mp_message(update, user, 0, is_edit=False)


async def marketplace_callbacks(update: Update, context: CallbackContext):
    query = update.callback_query
    clicker_id = query.from_user.id
    data = query.data
    parts = data.split("_")
    
    try:
        if len(parts) >= 3:
            owner_id = int(parts[2])
            if clicker_id != owner_id:
                await query.answer(to_small_caps("This is not your menu! Type /mp to open yours."), show_alert=True)
                return
            user_id = owner_id
        else:
            return

        # ---------------- AUCTION LOGIC ----------------
        if data.startswith("auc_"):
            if data.startswith("auc_none_"):
                await query.answer(to_small_caps("Use left/right arrows to adjust bid!"), show_alert=False)
                return
                
            active_auc = await auction_collection.find_one({'status': 'active'})
            if not active_auc:
                await query.answer(to_small_caps("There is no active auction!"), show_alert=True)
                return

            if data.startswith("auc_adj_"):
                increment = int(parts[3])
                current_proposed = int(parts[4])
                new_proposed = current_proposed + increment
                await render_auction_ui(query, active_auc, user_id, new_proposed)
                return

            if data.startswith("auc_conf_"):
                proposed = int(parts[3])
                
                if proposed <= active_auc['highest_bid'] and active_auc.get('top_bids'):
                    await query.answer(to_small_caps(f"Bid must be higher than {active_auc['highest_bid']:,}!"), show_alert=True)
                    await render_auction_ui(query, active_auc, user_id, active_auc['highest_bid'] + 1000)
                    return
                    
                user_db = await user_collection.find_one({'id': clicker_id})
                if not user_db or user_db.get('balance', 0) < proposed:
                    await query.answer(to_small_caps(f"Low balance! You need {proposed:,} 💸"), show_alert=True)
                    return
                
                top_bids = active_auc.get('top_bids', [])
                
                # Remove this user's old bid if exists
                top_bids = [b for b in top_bids if b['id'] != clicker_id]
                
                # Add new bid and sort
                top_bids.append({'id': clicker_id, 'name': query.from_user.first_name, 'bid': proposed})
                top_bids = sorted(top_bids, key=lambda x: x['bid'], reverse=True)
                    
                await auction_collection.update_one(
                    {'_id': active_auc['_id']},
                    {'$set': {'highest_bid': top_bids[0]['bid'], 'top_bids': top_bids}}
                )
                
                await query.answer(to_small_caps(f"✅ Bid of {proposed:,} placed successfully!"), show_alert=True)
                
                active_auc['highest_bid'] = top_bids[0]['bid']
                active_auc['top_bids'] = top_bids
                await render_auction_ui(query, active_auc, user_id, top_bids[0]['bid'] + 1000)
                return

            if data.startswith("auc_can_"):
                top_bids = active_auc.get('top_bids', [])
                has_bid = any(b['id'] == clicker_id for b in top_bids)
                
                if not has_bid:
                    await query.answer(to_small_caps("You haven't placed any bid yet!"), show_alert=True)
                    return
                    
                # Remove user from top bids
                top_bids = [b for b in top_bids if b['id'] != clicker_id]
                top_bids = sorted(top_bids, key=lambda x: x['bid'], reverse=True)
                
                highest_bid = top_bids[0]['bid'] if top_bids else active_auc.get('starting_bid', 1000)
                
                await auction_collection.update_one(
                    {'_id': active_auc['_id']},
                    {'$set': {'highest_bid': highest_bid, 'top_bids': top_bids}}
                )
                
                await query.answer(to_small_caps("✅ Your bid has been cancelled! Coins are safe."), show_alert=True)
                
                active_auc['highest_bid'] = highest_bid
                active_auc['top_bids'] = top_bids
                await render_auction_ui(query, active_auc, user_id, highest_bid + 1000)
                return

        # ---------------- DEALS LOGIC ----------------
        elif data.startswith("mp_"):
            user = await load_user_deals(user_id)
            if not user: return
            
            if data.startswith("mp_nav_"):
                index = int(parts[3])
                await render_mp_message(query, user, index, is_edit=True)

            elif data.startswith("mp_buy_"):
                index = int(parts[3])
                char = user['mp_data']['chars'][index]
                if char.get('is_sold'):
                    await query.answer(to_small_caps("Already purchased!"), show_alert=True)
                    return
                    
                if user.get('balance', 0) < char['mp_sale']:
                    await query.answer(to_small_caps("Low balance!"), show_alert=True)
                    return
                    
                char['is_sold'] = True
                clean_char = {k: v for k, v in char.items() if k not in ['mp_orig', 'mp_disc', 'mp_sale', 'is_sold']}
                
                raw_mp_chars = [{k: v for k, v in c.items() if k in ['id', 'mp_orig', 'mp_disc', 'mp_sale', 'is_sold']} for c in user['mp_data']['chars']]
                await user_collection.update_one(
                    {'id': user_id},
                    {'$inc': {'balance': -char['mp_sale']}, '$push': {'characters': clean_char}, '$set': {'mp_data.chars': raw_mp_chars}}
                )
                await query.answer(to_small_caps("✅ Transaction successful!"), show_alert=True)
                await render_mp_message(query, user, index, is_edit=True)

            elif data.startswith("mp_auc_"):
                active_auc = await auction_collection.find_one({'status': 'active'})
                if not active_auc:
                    await query.answer(to_small_caps("There is no active auction right now!"), show_alert=True)
                    return
                await render_auction_ui(query, active_auc, user_id)

            elif data.startswith("mp_ref_"):
                if user.get('balance', 0) < 30000:
                    await query.answer(to_small_caps("Not enough coins!"), show_alert=True)
                    return
                await user_collection.update_one({'id': user_id}, {'$inc': {'balance': -30000}, '$set': {'mp_data.day': "FORCE_REFRESH"}})
                new_user = await load_user_deals(user_id)
                await render_mp_message(query, new_user, 0, is_edit=True)

            elif data.startswith("mp_back_"):
                await render_mp_message(query, user, 0, is_edit=True)

    except Exception as e:
        await query.answer(to_small_caps("An error occurred."), show_alert=False)


# --- AUCTION OWNER COMMANDS ---
async def start_auction(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: return 
    
    if len(context.args) < 2:
        return
        
    char_id = context.args[0]
    starting_bid = int(context.args[1])
        
    query = {'$or': [{'id': char_id}, {'id': str(char_id)}, {'id': int(char_id)}]}
    char = await collection.find_one(query)
    
    if not char: return
        
    active_auc = await auction_collection.find_one({'status': 'active'})
    if active_auc: return
        
    await collection.update_one(query, {'$set': {'auction_exclusive': True}})
    
    auction_data = {
        'char_id': char.get('id'), 'char_name': char.get('name', 'Unknown'),
        'anime': char.get('anime', 'Unknown'), 'rarity': char.get('rarity', 'Unknown'),
        'img_url': char.get('img_url'), 'starting_bid': starting_bid, 'highest_bid': starting_bid,
        'top_bids': [], 'status': 'active'
    }
    await auction_collection.insert_one(auction_data)
    
    msg = f"🎉 AUCTION STARTED! 🎉\n\nCHARACTER: {char.get('name')}\nSTARTING BID: {starting_bid:,} 💸"
    if char.get('img_url'):
        await update.message.reply_photo(photo=char.get('img_url'), caption=bold_sc(msg), parse_mode='HTML')
    else:
        await update.message.reply_text(bold_sc(msg), parse_mode='HTML')


async def end_auction(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: return 
        
    active_auc = await auction_collection.find_one({'status': 'active'})
    if not active_auc: return
        
    await auction_collection.update_one({'_id': active_auc['_id']}, {'$set': {'status': 'ended'}})
    
    top_bids = active_auc.get('top_bids', [])
    if not top_bids:
        await update.message.reply_text(bold_sc("Auction ended! No one placed a bid."), parse_mode='HTML')
        return
        
    winner = top_bids[0]
    bidder_id = winner['id']
    winning_bid = winner['bid']
    
    # Safe name format
    winner_name = str(winner['name']).replace('<', '&lt;').replace('>', '&gt;')
    
    bidder = await user_collection.find_one({'id': bidder_id})
    char_query = {'$or': [{'id': active_auc['char_id']}, {'id': str(active_auc['char_id'])}, {'id': int(active_auc['char_id'])}]}
    char = await collection.find_one(char_query)
    
    if bidder and char:
        clean_char = {k: v for k, v in char.items() if k not in ['auction_exclusive', 'mp_orig', 'mp_disc', 'mp_sale', 'is_sold']}
        await user_collection.update_one({'id': bidder_id}, {'$inc': {'balance': -winning_bid}, '$push': {'characters': clean_char}})
        
        msg = f"🎊 AUCTION ENDED! 🎊\n\nWINNER: {winner_name}\nWINNING BID: {winning_bid:,} 💸"
        await update.message.reply_text(bold_sc(msg), parse_mode='HTML')

# --- Handlers ---
application.add_handler(CommandHandler(["mp", "marketplace"], marketplace, block=False))
application.add_handler(CommandHandler("setprice", set_mp_price, block=False))
application.add_handler(CommandHandler("startauction", start_auction, block=False))
application.add_handler(CommandHandler("endauction", end_auction, block=False))
application.add_handler(CallbackQueryHandler(marketplace_callbacks, pattern="^(mp_|auc_)", block=False))

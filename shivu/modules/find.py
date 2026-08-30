import asyncio
import random
import traceback
import logging
import re
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo, InputMediaAnimation
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from telegram.error import BadRequest
from shivu import application, db, user_collection

# 🔥 Economy database se connect karne ke liye
from shivu.Database.db import eco_collection

# 🔥 Sahi anime database collection
collection = db['anime_characters_lol'] 

try:
    auction_collection = db['auctions']
    mp_config = db['mp_config'] 
except ImportError:
    pass

OWNER_ID = 7657218453

DEFAULT_PRICES = {
    "common": 1000, "rare": 3200, "medium": 2900, 
    "legendary": 5000, "celestial": 70000, "spicy": 59000, 
    "exclusive": 12000, "mythic": 180000, "premium edition": 250000, 
    "sweet": 52000, "valentine": 90000, "winter": 55000, 
    "neon": 67000, "summer": 60000, "cosmic": 640000
}

PREMIUM_RARITIES = {
    "common": '<tg-emoji emoji-id="6093865707424980866">🟢</tg-emoji>',
    "rare": '<tg-emoji emoji-id="5339390195768774311">🟠</tg-emoji>',
    "medium": '<tg-emoji emoji-id="6093741664474504699">🔴</tg-emoji>',
    "legendary": '<tg-emoji emoji-id="6084550327086883643">🔥</tg-emoji>',
    "celestial": '<tg-emoji emoji-id="5434121252874756456">🕊</tg-emoji>',
    "spicy": '<tg-emoji emoji-id="6093490292923574796">❤️‍🔥</tg-emoji>',
    "exclusive": '<tg-emoji emoji-id="5764869176736880220">👑</tg-emoji>',
    "mythic": '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>',
    "premium edition": '<tg-emoji emoji-id="6093919703753831564">🔮</tg-emoji>',
    "sweet": '<tg-emoji emoji-id="6222115531122546353">🍭</tg-emoji>',
    "valentine": '<tg-emoji emoji-id="5255861796350224063">❤️</tg-emoji>',
    "winter": '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>',
    "neon": '<tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>',
    "summer": '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>',
    "cosmic": '<tg-emoji emoji-id="5431783411981228752">🎆</tg-emoji>'
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

def extract_rarity_name(r_str: str) -> str:
    text_part = ""
    for i, c in enumerate(r_str):
        if c.isalpha():
            text_part = r_str[i:]
            break
    return text_part.strip() if text_part else r_str.strip()

def get_rarity_emoji_and_name(r_str: str):
    r_str = str(r_str)
    name_part = extract_rarity_name(r_str)
    name_lower = name_part.lower()
    emoji = PREMIUM_RARITIES.get(name_lower, '<tg-emoji emoji-id="6093611479720795757">💫</tg-emoji>')
    return emoji, name_part

def get_price(char):
    if 'mp_price' in char and char['mp_price'] is not None:
        return char['mp_price']
    r_str = str(char.get('rarity', 'Unknown'))
    name_part = extract_rarity_name(r_str).lower()
    return DEFAULT_PRICES.get(name_part, 50000)

def get_current_mp_day():
    IST = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(IST)
    if now.hour < 4:
        return (now - timedelta(days=1)).strftime('%Y-%m-%d')
    return now.strftime('%Y-%m-%d')

def get_media_info(char_doc):
    if char_doc.get('cached_photo_id'):
        return char_doc['cached_photo_id'], InputMediaPhoto, 'photo'
    elif char_doc.get('cached_video_id'):
        return char_doc['cached_video_id'], InputMediaVideo, 'video'
    elif char_doc.get('cached_anim_id'):
        return char_doc['cached_anim_id'], InputMediaAnimation, 'animation'
    
    img_url = char_doc.get('img_url')
    is_video = img_url and str(img_url).lower().endswith(('.mp4', '.gif'))
    return img_url, (InputMediaVideo if is_video else InputMediaPhoto), 'url'


# --- Set Price & Toggle Command (Owner Only) ---
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
    except Exception:
        pass

async def toggle_rarity(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return
    if not context.args:
        msg = "Usage: /togglerarity [rarity_name]\nExample: /togglerarity common"
        await update.message.reply_text(f"<blockquote>{bold_sc(msg)}</blockquote>", parse_mode='HTML')
        return
        
    rarity = " ".join(context.args).lower()
    config = await mp_config.find_one({'_id': 'settings'})
    if not config:
        config = {'_id': 'settings', 'disabled_rarities': []}
        await mp_config.insert_one(config)
        
    disabled = config.get('disabled_rarities', [])
    if rarity in disabled:
        disabled.remove(rarity)
        status = "ENABLED"
    else:
        disabled.append(rarity)
        status = "DISABLED"
        
    await mp_config.update_one({'_id': 'settings'}, {'$set': {'disabled_rarities': disabled}})
    await update.message.reply_text(bold_sc(f"Rarity '{rarity}' has been {status} in Marketplace."), parse_mode='HTML')


# --- SUPER FAST DEALS LOADER ---
async def load_user_deals(user_id):
    user = await user_collection.find_one({'id': user_id}, {'id': 1, 'mp_data': 1})
    if not user: return None
        
    current_day = get_current_mp_day()
    mp_data = user.get('mp_data', {})
    
    if mp_data.get('day') != current_day or not mp_data.get('chars'):
        config = await mp_config.find_one({'_id': 'settings'})
        disabled_rarities = config.get('disabled_rarities', []) if config else []
        
        base_query = {'auction_exclusive': {'$ne': True}}
        if disabled_rarities:
            pattern = "|".join([re.escape(r) for r in disabled_rarities])
            base_query['rarity'] = {'$not': {'$regex': pattern, '$options': 'i'}}
            
        pipeline = [{"$match": base_query}, {"$sample": {"size": 2}}]
        random_chars = await collection.aggregate(pipeline).to_list(length=2)
        
        if len(random_chars) < 2: 
            return None 
        
        formatted_chars = []
        for c in random_chars:
            orig = get_price(c)
            disc = random.randint(2, 15)
            sale = int(orig - (orig * (disc / 100)))
            formatted_chars.append({
                'id': str(c.get('id')), 
                'mp_orig': orig, 
                'mp_disc': disc, 
                'mp_sale': sale, 
                'is_sold': False
            })
            
        mp_data = {'day': current_day, 'chars': formatted_chars}
        await user_collection.update_one({'id': user_id}, {'$set': {'mp_data': mp_data}})
        user['mp_data'] = mp_data

    search_ids = []
    for item in user['mp_data']['chars']:
        cid = str(item.get('id'))
        search_ids.append(cid)
        if cid.isdigit(): search_ids.append(int(cid))
        
    db_chars = await collection.find({'id': {'$in': search_ids}}).to_list(length=2)
    db_char_map = {str(c['id']): c for c in db_chars}

    updated_chars = []
    for item in user['mp_data']['chars']:
        cid = str(item.get('id'))
        if cid in db_char_map:
            db_char = db_char_map[cid]
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
    chars = user.get('mp_data', {}).get('chars', [])
    
    if not chars:
        text = f"<b><tg-emoji emoji-id=\"6323595854456298870\">⚠️</tg-emoji> {bold_sc('marketplace is currently empty!')}</b>"
        if is_edit:
            try:
                return await update_obj.edit_message_text(text=text, parse_mode='HTML')
            except BadRequest:
                return await update_obj.message.reply_text(text=text, parse_mode='HTML')
        else:
            return await update_obj.message.reply_text(text=text, parse_mode='HTML')

    if index >= len(chars): index = 0
    char = chars[index]
    user_id = user['id'] 
    
    # 🔥 LIVE UPDATE: Turant global database se connect karke latest details nikalega
    search_ids = [str(char.get('id'))]
    if str(char.get('id')).isdigit():
        search_ids.append(int(char.get('id')))
        
    live_char = await collection.find_one({'id': {'$in': search_ids}})
    if live_char:
        char.update({k: v for k, v in live_char.items() if k in ['name', 'anime', 'rarity', 'img_url', 'is_video', 'cached_photo_id', 'cached_video_id', 'cached_anim_id']})
    
    r_emoji, r_name = get_rarity_emoji_and_name(char.get('rarity', 'Unknown'))
    status_text = f"<tg-emoji emoji-id=\"6323595854456298870\">⚠️</tg-emoji> {bold_sc('SOLD')}" if char.get('is_sold') else f"<tg-emoji emoji-id=\"5312361253610475399\">🛒</tg-emoji> {bold_sc('AVAILABLE')}"

    caption = f"""<tg-emoji emoji-id="5278702045883292456">🛍</tg-emoji> {bold_sc(f'DAILY DEALS ({index+1}/2)')}

<tg-emoji emoji-id="6336972134962697188">🌸</tg-emoji> {bold_sc('NAME:')} {bold_sc(str(char.get('name', 'Unknown')).upper())}
<tg-emoji emoji-id="6314494724266796319">🟠</tg-emoji> {bold_sc('SERIES:')} {bold_sc(str(char.get('anime', 'Unknown')).upper())}
<tg-emoji emoji-id="6332443074769196273">🆔</tg-emoji> {bold_sc('ID:')} {bold_sc(str(char.get('id', 'N/A')))}
{r_emoji} {bold_sc('RARITY:')} {bold_sc(r_name)}
<tg-emoji emoji-id="5472030678633684592">💸</tg-emoji> {bold_sc('ORIGINAL:')} {bold_sc(f"{char['mp_orig']:,}")}
<tg-emoji emoji-id="5240228673738527951">🏷</tg-emoji> {bold_sc('SALE PRICE:')} {bold_sc(f"{char['mp_sale']:,}")}
<tg-emoji emoji-id="6093521568875420685">🛍</tg-emoji> {bold_sc('DISCOUNT:')} {bold_sc(f"{char['mp_disc']}%")}
<tg-emoji emoji-id="5197269100878907942">✍️</tg-emoji> {bold_sc('STATUS:')} {status_text}"""

    nav_index = 1 if index == 0 else 0
    buttons = [
        [
            InlineKeyboardButton("⋞", callback_data=f"mp_nav_{user_id}_{nav_index}"),
            InlineKeyboardButton(to_small_caps("Buy"), callback_data=f"mp_buy_{user_id}_{index}"),
            InlineKeyboardButton("⋟", callback_data=f"mp_nav_{user_id}_{nav_index}")
        ],
        [InlineKeyboardButton(f"{to_small_caps('Auction')}", callback_data=f"mp_auc_{user_id}")],
        [InlineKeyboardButton(to_small_caps("Refresh (30,000 💸)"), callback_data=f"mp_ref_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    media_source, media_class, media_type = get_media_info(char)
    img_url = char.get('img_url')

    msg = None
    if is_edit:
        try:
            if update_obj.message.photo or update_obj.message.video or update_obj.message.animation:
                if media_source:
                    try:
                        msg = await update_obj.edit_message_media(
                            media=media_class(media=media_source, caption=caption, parse_mode='HTML'), 
                            reply_markup=reply_markup
                        )
                    except BadRequest as e:
                        if "message is not modified" in str(e).lower():
                            msg = update_obj.message
                        elif media_type == 'url' and ("video" in str(e).lower() or "animation" in str(e).lower()):
                            msg = await update_obj.edit_message_media(
                                media=InputMediaVideo(media=media_source, caption=caption, parse_mode='HTML'), 
                                reply_markup=reply_markup
                            )
                        else:
                            raise e
                else:
                    msg = await update_obj.edit_message_caption(caption=caption, reply_markup=reply_markup, parse_mode='HTML')
            else:
                msg = await update_obj.edit_message_text(text=caption, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest as e:
            if "message is not modified" in str(e).lower():
                msg = update_obj.message
            else:
                pass
        except Exception:
            pass
    else:
        if media_source:
            try:
                if media_type == 'photo':
                    msg = await update_obj.message.reply_photo(photo=media_source, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
                elif media_type in ['video', 'animation']:
                    msg = await update_obj.message.reply_video(video=media_source, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
                else:
                    is_video = img_url and str(img_url).lower().endswith(('.mp4', '.gif'))
                    if is_video:
                        msg = await update_obj.message.reply_video(video=media_source, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
                    else:
                        msg = await update_obj.message.reply_photo(photo=media_source, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
            except BadRequest as e:
                if "video" in str(e).lower() or "animation" in str(e).lower():
                    try:
                        msg = await update_obj.message.reply_video(video=media_source, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
                    except BadRequest:
                        msg = await update_obj.message.reply_animation(animation=media_source, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
                else:
                    raise e
        else:
            msg = await update_obj.message.reply_text(text=caption, reply_markup=reply_markup, parse_mode='HTML')
            
    if msg and media_type == 'url' and img_url:
        update_data = {}
        if msg.photo: update_data['cached_photo_id'] = msg.photo[-1].file_id
        elif msg.video: update_data['cached_video_id'] = msg.video.file_id
        elif msg.animation: update_data['cached_anim_id'] = msg.animation.file_id
        
        if update_data:
            await collection.update_one({'id': char.get('id')}, {'$set': update_data})
            char.update(update_data)


async def render_auction_ui(update_obj, active_auc, user_id, add_amount=1000, is_edit=False):
    add_amount = max(1000, add_amount)

    # 🔥 LIVE UPDATE FOR AUCTIONS
    search_ids = [str(active_auc.get('char_id'))]
    if str(active_auc.get('char_id')).isdigit():
        search_ids.append(int(active_auc.get('char_id')))
        
    live_auc_char = await collection.find_one({'id': {'$in': search_ids}})
    if live_auc_char:
        active_auc['char_name'] = live_auc_char.get('name', active_auc.get('char_name'))
        active_auc['anime'] = live_auc_char.get('anime', active_auc.get('anime'))
        active_auc['rarity'] = live_auc_char.get('rarity', active_auc.get('rarity'))
        active_auc['img_url'] = live_auc_char.get('img_url', active_auc.get('img_url'))

    top_bids = active_auc.get('top_bids', [])
    # 🔥 TOP 20 LIST WITH 1-3 MEDALS
    top_list_text = f"\n\n<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> 𝗧𝗢𝗣 𝗕𝗜𝗗𝗗𝗘𝗥𝗦:\n"
    
    if top_bids:
        for i, b in enumerate(top_bids[:20]):
            if i == 0: medal = '<tg-emoji emoji-id="5440539497383087970">🥇</tg-emoji>'
            elif i == 1: medal = '<tg-emoji emoji-id="5447203607294265305">🥈</tg-emoji>'
            elif i == 2: medal = '<tg-emoji emoji-id="5453902265922376865">🥉</tg-emoji>'
            else: medal = f"<b>{i+1}.</b>"
            
            clean_name = str(b['name']).replace('<', '&lt;').replace('>', '&gt;')
            mention_link = f"<b><a href='tg://user?id={b['id']}'>{clean_name}</a></b>"
            bid_amount = b['bid']
            top_list_text += f"{medal} {mention_link}: {bold_sc(f'{bid_amount:,}')} <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>\n"
    else:
        top_list_text += f"<tg-emoji emoji-id=\"6093837944756379538\">👻</tg-emoji> {bold_sc('No bids placed yet!')}\n"

    r_emoji, r_name = get_rarity_emoji_and_name(active_auc['rarity'])

    caption = f"""<tg-emoji emoji-id="6093447592358714412">▶️</tg-emoji> 𝗟𝗜𝗩𝗘 𝗔𝗨𝗖𝗧𝗜𝗢𝗡 <tg-emoji emoji-id="6093447592358714412">▶️</tg-emoji>

<tg-emoji emoji-id="6336972134962697188">🌸</tg-emoji> {bold_sc('NAME:')} {bold_sc(active_auc['char_name'])}
<tg-emoji emoji-id="6314494724266796319">🟠</tg-emoji> {bold_sc('SERIES:')} {bold_sc(active_auc['anime'])}
{r_emoji} {bold_sc('RARITY:')} {bold_sc(r_name)}{top_list_text}"""

    # 🔥 Adding Amount Buttons 
    buttons = [
        [
            InlineKeyboardButton("⋞", callback_data=f"auc_adj_{user_id}_-1000_{add_amount}"),
            InlineKeyboardButton(f"+ {add_amount:,}", callback_data=f"auc_none_{user_id}"),
            InlineKeyboardButton("⋟", callback_data=f"auc_adj_{user_id}_1000_{add_amount}")
        ],
        [InlineKeyboardButton(to_small_caps("Confirm Bid"), callback_data=f"auc_conf_{user_id}_{add_amount}")],
        [
            InlineKeyboardButton(to_small_caps("⟲ Back"), callback_data=f"mp_back_{user_id}"),
            InlineKeyboardButton(to_small_caps("Cancel ⟳"), callback_data=f"auc_can_{user_id}")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(buttons)
    media_source, media_class, media_type = get_media_info(active_auc)
    img_url = active_auc.get('img_url')
    
    msg = None
    if is_edit:
        query = update_obj
        try:
            if query.message.photo or query.message.video or query.message.animation:
                if media_source:
                    try:
                        msg = await query.edit_message_media(
                            media=media_class(media=media_source, caption=caption, parse_mode='HTML'), 
                            reply_markup=reply_markup
                        )
                    except BadRequest as e:
                        if "message is not modified" in str(e).lower():
                            msg = query.message
                        elif media_type == 'url' and ("video" in str(e).lower() or "animation" in str(e).lower()):
                            msg = await query.edit_message_media(
                                media=InputMediaVideo(media=media_source, caption=caption, parse_mode='HTML'), 
                                reply_markup=reply_markup
                            )
                        else:
                            raise e
                else:
                    msg = await query.edit_message_caption(caption=caption, reply_markup=reply_markup, parse_mode='HTML')
            else:
                msg = await query.edit_message_text(text=caption, reply_markup=reply_markup, parse_mode='HTML')
        except BadRequest as e:
            if "message is not modified" not in str(e).lower():
                pass
        except Exception:
            pass
    else:
        # Initial call via /auction command
        message = update_obj.message
        if media_source:
            try:
                if media_type == 'photo':
                    msg = await message.reply_photo(photo=media_source, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
                elif media_type in ['video', 'animation']:
                    msg = await message.reply_video(video=media_source, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
                else:
                    is_video = img_url and str(img_url).lower().endswith(('.mp4', '.gif'))
                    if is_video:
                        msg = await message.reply_video(video=media_source, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
                    else:
                        msg = await message.reply_photo(photo=media_source, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
            except BadRequest as e:
                if "video" in str(e).lower() or "animation" in str(e).lower():
                    try:
                        msg = await message.reply_video(video=media_source, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
                    except BadRequest:
                        msg = await message.reply_animation(animation=media_source, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
                else:
                    raise e
        else:
            msg = await message.reply_text(text=caption, reply_markup=reply_markup, parse_mode='HTML')

        
    if msg and media_type == 'url' and img_url:
        update_data = {}
        if msg.photo: update_data['cached_photo_id'] = msg.photo[-1].file_id
        elif msg.video: update_data['cached_video_id'] = msg.video.file_id
        elif msg.animation: update_data['cached_anim_id'] = msg.animation.file_id
        
        if update_data:
            await auction_collection.update_one({'_id': active_auc['_id']}, {'$set': update_data})
            await collection.update_one({'id': active_auc['char_id']}, {'$set': update_data})
            active_auc.update(update_data)


# --- Commands & Callbacks ---
async def marketplace(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user = await load_user_deals(user_id)
    if not user:
        await update.message.reply_text(bold_sc("Please /start the bot first or Not enough characters matching the allowed rarities."), parse_mode='HTML')
        return
    await render_mp_message(update, user, 0, is_edit=False)


# 🔥 NAYA AUCTION COMMAND (Direct Entry)
async def auction_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    active_auc = await auction_collection.find_one({'status': 'active'})
    if not active_auc:
        await update.message.reply_text(bold_sc("There is no active auction right now!"), parse_mode='HTML')
        return
    await render_auction_ui(update, active_auc, user_id, 1000, is_edit=False)


# 🔥 NAYA BID COMMAND (Any Amount Add)
async def place_bid_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(bold_sc("Usage: /bid [amount]"), parse_mode='HTML')
        return
        
    add_amount = int(context.args[0])
    if add_amount <= 0:
        await update.message.reply_text(bold_sc("Bid amount must be greater than 0!"), parse_mode='HTML')
        return
        
    active_auc = await auction_collection.find_one({'status': 'active'})
    if not active_auc:
        await update.message.reply_text(bold_sc("No active auction right now!"), parse_mode='HTML')
        return
        
    top_bids = active_auc.get('top_bids', [])
    existing_bid = next((b['bid'] for b in top_bids if b['id'] == user_id), 0)
    new_total = existing_bid + add_amount
    
    # Fast Projection
    eco_user = await eco_collection.find_one({'id': user_id}, {'balance': 1})
    if not eco_user or eco_user.get('balance', 0) < new_total:
        await update.message.reply_text(bold_sc(f"Low balance! You need {new_total:,} 💸 for this total bid."), parse_mode='HTML')
        return
        
    top_bids = [b for b in top_bids if b['id'] != user_id]
    top_bids.append({'id': user_id, 'name': update.effective_user.first_name, 'bid': new_total})
    top_bids = sorted(top_bids, key=lambda x: x['bid'], reverse=True)
    highest_bid = top_bids[0]['bid']
    
    await auction_collection.update_one(
        {'_id': active_auc['_id']},
        {'$set': {'highest_bid': highest_bid, 'top_bids': top_bids}}
    )
    
    await update.message.reply_text(bold_sc(f"✅ Added {add_amount:,} to your bid! Total bid: {new_total:,}"), parse_mode='HTML')
    
    # Re-render to show updated board
    active_auc['highest_bid'] = highest_bid
    active_auc['top_bids'] = top_bids
    await render_auction_ui(update, active_auc, user_id, 1000, is_edit=False)


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
                await query.answer(to_small_caps("Use left/right arrows to adjust bid amount!"), show_alert=False)
                return
                
            active_auc = await auction_collection.find_one({'status': 'active'})
            if not active_auc:
                await query.answer(to_small_caps("There is no active auction!"), show_alert=True)
                return

            if data.startswith("auc_adj_"):
                increment = int(parts[3])
                current_add = int(parts[4])
                new_add = current_add + increment
                if new_add < 1000: new_add = 1000
                await query.answer() 
                await render_auction_ui(query, active_auc, user_id, new_add, is_edit=True)
                return

            if data.startswith("auc_conf_"):
                add_amount = int(parts[3])
                
                top_bids = active_auc.get('top_bids', [])
                existing_bid = next((b['bid'] for b in top_bids if b['id'] == clicker_id), 0)
                new_total = existing_bid + add_amount
                
                # 🔥 PROJECTION: Faster coin fetch
                eco_user = await eco_collection.find_one({'id': clicker_id}, {'balance': 1})
                if not eco_user or eco_user.get('balance', 0) < new_total:
                    await query.answer(to_small_caps(f"Low balance! You need {new_total:,} 💸 total."), show_alert=True)
                    return
                
                top_bids = [b for b in top_bids if b['id'] != clicker_id]
                top_bids.append({'id': clicker_id, 'name': query.from_user.first_name, 'bid': new_total})
                top_bids = sorted(top_bids, key=lambda x: x['bid'], reverse=True)
                highest_bid = top_bids[0]['bid']
                    
                await auction_collection.update_one(
                    {'_id': active_auc['_id']},
                    {'$set': {'highest_bid': highest_bid, 'top_bids': top_bids}}
                )
                
                await query.answer(to_small_caps(f"✅ Added {add_amount:,} successfully!"), show_alert=True)
                
                active_auc['highest_bid'] = highest_bid
                active_auc['top_bids'] = top_bids
                await render_auction_ui(query, active_auc, user_id, 1000, is_edit=True)
                return

            if data.startswith("auc_can_"):
                top_bids = active_auc.get('top_bids', [])
                has_bid = any(b['id'] == clicker_id for b in top_bids)
                
                if not has_bid:
                    await query.answer(to_small_caps("You haven't placed any bid yet!"), show_alert=True)
                    return
                    
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
                await render_auction_ui(query, active_auc, user_id, 1000, is_edit=True)
                return

        # ---------------- DEALS LOGIC ----------------
        elif data.startswith("mp_"):
            user = await load_user_deals(user_id)
            if not user: return
            
            if data.startswith("mp_nav_"):
                index = int(parts[3])
                await query.answer()
                await render_mp_message(query, user, index, is_edit=True)
                return

            elif data.startswith("mp_buy_"):
                index = int(parts[3])
                chars = user.get('mp_data', {}).get('chars', [])
                if not chars or index >= len(chars):
                    await query.answer(to_small_caps("Character not found or expired!"), show_alert=True)
                    return
                char = chars[index]
                
                mark_sold = await user_collection.update_one(
                    {'id': user_id, f'mp_data.chars.{index}.is_sold': {'$ne': True}},
                    {'$set': {f'mp_data.chars.{index}.is_sold': True}}
                )
                if mark_sold.modified_count == 0:
                    await query.answer(to_small_caps("Already purchased or processing!"), show_alert=True)
                    return
                
                eco_user = await eco_collection.find_one_and_update(
                    {'id': user_id, 'balance': {'$gte': char['mp_sale']}},
                    {'$inc': {'balance': -char['mp_sale']}},
                    projection={'balance': 1} 
                )
                
                if not eco_user:
                    await user_collection.update_one({'id': user_id}, {'$set': {f'mp_data.chars.{index}.is_sold': False}})
                    await query.answer(to_small_caps("Low balance!"), show_alert=True)
                    return
                    
                char['is_sold'] = True
                clean_char = {k: v for k, v in char.items() if k not in ['mp_orig', 'mp_disc', 'mp_sale', 'is_sold']}
                
                await user_collection.update_one({'id': user_id}, {'$push': {'characters': clean_char}})
                
                try:
                    from shivu.modules.check import clear_char_cache
                    clear_char_cache(str(char.get('id')))
                except ImportError:
                    pass
                
                await query.answer(to_small_caps("✅ Transaction successful!"), show_alert=True)
                await render_mp_message(query, user, index, is_edit=True)
                return

            elif data.startswith("mp_auc_"):
                active_auc = await auction_collection.find_one({'status': 'active'})
                if not active_auc:
                    await query.answer(to_small_caps("There is no active auction right now!"), show_alert=True)
                    return
                await query.answer() 
                await render_auction_ui(query, active_auc, user_id, 1000, is_edit=True)
                return

            elif data.startswith("mp_ref_"):
                eco_user = await eco_collection.find_one_and_update(
                    {'id': user_id, 'balance': {'$gte': 30000}},
                    {'$inc': {'balance': -30000}},
                    projection={'balance': 1}
                )
                if not eco_user:
                    await query.answer(to_small_caps("Not enough coins!"), show_alert=True)
                    return
                    
                await user_collection.update_one({'id': user_id}, {'$set': {'mp_data.day': "FORCE_REFRESH"}})
                new_user = await load_user_deals(user_id)
                await query.answer(to_small_caps("Deals Refreshed!"), show_alert=False)
                await render_mp_message(query, new_user, 0, is_edit=True)
                return

            elif data.startswith("mp_back_"):
                await query.answer() 
                await render_mp_message(query, user, 0, is_edit=True)
                return

    except Exception:
        await query.answer(to_small_caps("An error occurred."), show_alert=False)


# --- AUCTION OWNER COMMANDS ---
async def start_auction(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: 
        return 
    
    if len(context.args) < 2:
        await update.message.reply_text(bold_sc("Usage: /startauction [char_id] [starting_bid]"), parse_mode='HTML')
        return
        
    char_id = context.args[0]
    try:
        starting_bid = int(context.args[1])
    except ValueError:
        await update.message.reply_text(bold_sc("Starting bid must be a valid number!"), parse_mode='HTML')
        return
        
    query = {'$or': [{'id': char_id}, {'id': str(char_id)}, {'id': int(char_id) if char_id.isdigit() else char_id}]}
    char = await collection.find_one(query)
    
    if not char:
        await update.message.reply_text(bold_sc("Character ID not found in database!"), parse_mode='HTML')
        return
        
    active_auc = await auction_collection.find_one({'status': 'active'}, {'status': 1})
    if active_auc:
        await update.message.reply_text(bold_sc("An auction is already active! End it first using /endauction."), parse_mode='HTML')
        return
        
    await collection.update_one(query, {'$set': {'auction_exclusive': True}})
    
    auction_data = {
        'char_id': char.get('id'), 
        'char_name': char.get('name', 'Unknown'),
        'anime': char.get('anime', 'Unknown'), 
        'rarity': char.get('rarity', 'Unknown'),
        'img_url': char.get('img_url'), 
        'starting_bid': starting_bid, 
        'highest_bid': starting_bid,
        'top_bids': [], 
        'status': 'active'
    }
    
    if char.get('cached_photo_id'): auction_data['cached_photo_id'] = char['cached_photo_id']
    elif char.get('cached_video_id'): auction_data['cached_video_id'] = char['cached_video_id']
    elif char.get('cached_anim_id'): auction_data['cached_anim_id'] = char['cached_anim_id']
        
    await auction_collection.insert_one(auction_data)
    
    text_msg = (
        f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> {bold_sc('AUCTION STARTED!')} <tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji>\n\n"
        f"{bold_sc('CHARACTER:')} {bold_sc(char.get('name'))}\n"
        f"{bold_sc('STARTING BID:')} {bold_sc(f'{starting_bid:,}')} <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>"
    )
    
    media_source, media_class, media_type = get_media_info(auction_data)
    img_url = auction_data.get('img_url')
    
    msg = None
    if media_source:
        try:
            if media_type == 'photo':
                msg = await update.message.reply_photo(photo=media_source, caption=text_msg, parse_mode='HTML')
            elif media_type in ['video', 'animation']:
                msg = await update.message.reply_video(video=media_source, caption=text_msg, parse_mode='HTML')
            else:
                is_video = img_url and str(img_url).lower().endswith(('.mp4', '.gif'))
                if is_video:
                    msg = await update.message.reply_video(video=media_source, caption=text_msg, parse_mode='HTML')
                else:
                    msg = await update.message.reply_photo(photo=media_source, caption=text_msg, parse_mode='HTML')
        except BadRequest as e:
            if "video" in str(e).lower() or "animation" in str(e).lower():
                try:
                    msg = await update.message.reply_video(video=media_source, caption=text_msg, parse_mode='HTML')
                except BadRequest:
                    msg = await update.message.reply_animation(animation=media_source, caption=text_msg, parse_mode='HTML')
            else:
                raise e
    else:
        msg = await update.message.reply_text(text_msg, parse_mode='HTML')
        
    if msg and media_type == 'url' and img_url:
        update_data = {}
        if msg.photo: update_data['cached_photo_id'] = msg.photo[-1].file_id
        elif msg.video: update_data['cached_video_id'] = msg.video.file_id
        elif msg.animation: update_data['cached_anim_id'] = msg.animation.file_id
        
        if update_data:
            await auction_collection.update_one({'_id': auction_data['_id']}, {'$set': update_data})
            await collection.update_one({'id': char.get('id')}, {'$set': update_data})


async def end_auction(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID: 
        return 
        
    active_auc = await auction_collection.find_one({'status': 'active'})
    if not active_auc:
        await update.message.reply_text(bold_sc("No active auction found to end."), parse_mode='HTML')
        return
        
    await auction_collection.update_one({'_id': active_auc['_id']}, {'$set': {'status': 'ended'}})
    
    top_bids = active_auc.get('top_bids', [])
    if not top_bids:
        await update.message.reply_text(bold_sc("Auction ended! No one placed a bid."), parse_mode='HTML')
        return
        
    winner = top_bids[0]
    bidder_id = winner['id']
    winning_bid = winner['bid']
    
    clean_winner_name = str(winner['name']).replace('<', '&lt;').replace('>', '&gt;')
    winner_mention = f"<b><a href='tg://user?id={bidder_id}'>{to_small_caps(clean_winner_name)}</a></b>"
    
    eco_user = await eco_collection.find_one_and_update(
        {'id': bidder_id, 'balance': {'$gte': winning_bid}},
        {'$inc': {'balance': -winning_bid}},
        projection={'balance': 1}
    )
    
    char_query = {'$or': [{'id': active_auc['char_id']}, {'id': str(active_auc['char_id'])}, {'id': int(active_auc['char_id']) if str(active_auc['char_id']).isdigit() else active_auc['char_id']}]}
    char = await collection.find_one(char_query)
    
    if eco_user and char:
        clean_char = {k: v for k, v in char.items() if k not in ['auction_exclusive', 'mp_orig', 'mp_disc', 'mp_sale', 'is_sold']}
        await user_collection.update_one({'id': bidder_id}, {'$push': {'characters': clean_char}})
        
        header = f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> {bold_sc('AUCTION ENDED!')} <tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji>\n\n{bold_sc('WINNER: ')}"
        footer = f"\n{bold_sc('WINNING BID:')} {bold_sc(f'{winning_bid:,}')} <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>"
        msg = f"{header}{winner_mention}{footer}"
        
        await update.message.reply_text(msg, parse_mode='HTML')
    else:
        header = f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> {bold_sc('AUCTION ENDED WITH ERROR!')}\n\n"
        msg = f"{header}{winner_mention} {bold_sc('did not have enough coins to pay the bid!')}\n{bold_sc('Auction has been cancelled.')}"
        await update.message.reply_text(msg, parse_mode='HTML')

# --- Handlers ---
application.add_handler(CommandHandler(["mp", "marketplace"], marketplace, block=False))
application.add_handler(CommandHandler("auction", auction_cmd, block=False))
application.add_handler(CommandHandler("bid", place_bid_cmd, block=False))
application.add_handler(CommandHandler("setprice", set_mp_price, block=False))
application.add_handler(CommandHandler("startauction", start_auction, block=False))
application.add_handler(CommandHandler("endauction", end_auction, block=False))
application.add_handler(CommandHandler("togglerarity", toggle_rarity, block=False))
application.add_handler(CallbackQueryHandler(marketplace_callbacks, pattern="^(mp_|auc_)", block=False))

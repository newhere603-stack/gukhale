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
    "common": 1000, "rare": 10000, "medium": 8000, 
    "legendary": 15000, "celestial": 70000, "spicy": 99000, 
    "exclusive": 30000, "mythic": 180000, "premium edition": 250000, 
    "sweet": 62000, "valentine": 90000, "winter": 59000, 
    "neon": 67000, "summer": 65000, "cosmic": 740000
}

PREMIUM_RARITIES = {
    "common": '<tg-emoji emoji-id="6093865707424980866">🟢</tg-emoji>',
    "rare": '<tg-emoji emoji-id="5339390195768774311">🟠</tg-emoji>',
    "medium": '<tg-emoji emoji-id="6093741664474504699">🔴</tg-emoji>',
    "legendary": '<tg-emoji emoji-id="6084550327086883643">🔥</tg-emoji>',
    "celestial": '<tg-emoji emoji-id="5434121252874756456">🕊</tg-emoji>',
    "spicy": '<tg-emoji emoji-id="6093490292923574796">❤️‍🔥</tg-emoji>',
    "exclusive": '<tg-emoji emoji-id="6100567406889935797">🤴</tg-emoji>',
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
    img_url = char_doc.get('img_url')
    cached_url = char_doc.get('cached_img_url')
    
    if not img_url:
        if char_doc.get('cached_photo_id'):
            return char_doc['cached_photo_id'], InputMediaPhoto, 'photo'
        elif char_doc.get('cached_video_id'):
            return char_doc['cached_video_id'], InputMediaVideo, 'video'
        elif char_doc.get('cached_anim_id'):
            return char_doc['cached_anim_id'], InputMediaAnimation, 'animation'
        return None, InputMediaPhoto, 'url'
        
    if cached_url == img_url:
        if char_doc.get('cached_photo_id'):
            return char_doc['cached_photo_id'], InputMediaPhoto, 'photo'
        elif char_doc.get('cached_video_id'):
            return char_doc['cached_video_id'], InputMediaVideo, 'video'
        elif char_doc.get('cached_anim_id'):
            return char_doc['cached_anim_id'], InputMediaAnimation, 'animation'

    is_video = str(img_url).lower().endswith(('.mp4', '.gif'))
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
        
    db_chars = await collection.find({'id': {'$in': search_ids}}).to_list(length=4)
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
            
    # Auto-Delete Logic for new MP message
    if not is_edit and msg:
        async def auto_delete():
            await asyncio.sleep(1200) # 20 mins
            try:
                await msg.delete()
            except Exception:
                pass
        asyncio.create_task(auto_delete())
            
    if msg and media_type == 'url' and img_url:
        update_data = {'cached_img_url': img_url}
        if msg.photo: update_data['cached_photo_id'] = msg.photo[-1].file_id
        elif msg.video: update_data['cached_video_id'] = msg.video.file_id
        elif msg.animation: update_data['cached_anim_id'] = msg.animation.file_id
        
        if len(update_data) > 1:
            await collection.update_one({'id': char.get('id')}, {'$set': update_data})
            char.update(update_data)


async def render_auction_ui(update_obj, active_auc, user_id, add_amount=1000, is_edit=False):
    add_amount = max(1000, add_amount)

    search_ids = [str(active_auc.get('char_id'))]
    if str(active_auc.get('char_id')).isdigit():
        search_ids.append(int(active_auc.get('char_id')))
        
    live_auc_char = await collection.find_one({'id': {'$in': search_ids}})
    if live_auc_char:
        active_auc['char_name'] = live_auc_char.get('name', active_auc.get('char_name'))
        active_auc['anime'] = live_auc_char.get('anime', active_auc.get('anime'))
        active_auc['rarity'] = live_auc_char.get('rarity', active_auc.get('rarity'))
        active_auc['img_url'] = live_auc_char.get('img_url', active_auc.get('img_url'))
        
        for cache_key in ['cached_img_url', 'cached_photo_id', 'cached_video_id', 'cached_anim_id']:
            if cache_key in live_auc_char:
                active_auc[cache_key] = live_auc_char[cache_key]
            else:
                active_auc.pop(cache_key, None)

    top_bids = active_auc.get('top_bids', [])
    top_list_text = f"\n\n<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> 𝗧𝗢𝗣 𝗕𝗜𝗗𝗗𝗘𝗥𝗦:\n"
    
    if top_bids:
        for i, b in enumerate(top_bids[:20]):
            if i == 0: medal = '<tg-emoji emoji-id="5440539497383087970">🥇</tg-emoji>'
            elif i == 1: medal = '<tg-emoji emoji-id="5447203607294265305">🥈</tg-emoji>'
            elif i == 2: medal = '<tg-emoji emoji-id="54539022659

import asyncio
import random
import math
from html import escape
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from cachetools import TTLCache

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.error import TelegramError

from shivu import application, db, user_collection

collection = db['anime_characters_lol']

# --- OWNER OR SUDO CHECK ---
OWNER_ID = 7657218453
SUDO_USERS = [7657218453]

def is_authorized(user_id):
    return user_id == OWNER_ID or user_id in SUDO_USERS
# ---------------------------

# 🔥 Faster Updates: Caches tuned for speed
char_cache = TTLCache(maxsize=2000, ttl=60)
anime_cache = TTLCache(maxsize=1000, ttl=60)
user_cache = TTLCache(maxsize=2000, ttl=60) # Increased maxsize slightly for caching owners

USERS_PER_PAGE = 10

# 🔥 UNIFIED RARITY DICTIONARY
RARITIES = {
    "mythic": ("💎", '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>', "Mythic"),
    "cosmic": ("🌌", '<tg-emoji emoji-id="5431783411981228752">🎆</tg-emoji>', "Cosmic"),
    "celestial": ("🪽", '<tg-emoji emoji-id="5434121252874756456">🕊</tg-emoji>', "Celestial"),
    "exclusive": ("💮", '<tg-emoji emoji-id="5262772355779809182">💮</tg-emoji>', "Exclusive"),
    "legendary": ("🟡", '<tg-emoji emoji-id="6084550327086883643">🔥</tg-emoji>', "Legendary"),
    "premium": ("🔮", '<tg-emoji emoji-id="6093919703753831564">🔮</tg-emoji>', "Premium Edition"),
    "neon": ("⚡", '<tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>', "Neon"),
    "summer": ("🏖️", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"),
    "sweet": ("🍭", '<tg-emoji emoji-id="6222115531122546353">🍭</tg-emoji>', "Sweet"),
    "special": ("🔵", '<tg-emoji emoji-id="5393592081748877575">🔵</tg-emoji>', "Medium"),
    "valentine": ("💞", '<tg-emoji emoji-id="5255861796350224063">❤️</tg-emoji>', "Valentine"),
    "winter": ("❄️", '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>', "Winter"),
    "erotic": ("🥵", '<tg-emoji emoji-id="6093490292923574796">❤️‍🔥</tg-emoji>', "Spicy"),
    "rare": ("🟠", '<tg-emoji emoji-id="5339390195768774311">🟠</tg-emoji>', "Rare"),
    "common": ("🟢", '<tg-emoji emoji-id="6093722470265658964">🟢</tg-emoji>', "Common")
}

# 🔥 POWERFUL RARITY MATCHER
def get_base_rarity(rarity_str: str) -> str:
    if not rarity_str or not isinstance(rarity_str, str):
        return "common"
    r_lower = rarity_str.lower().strip()
    
    # 1. Exact Match Check
    for key, (_, _, name) in RARITIES.items():
        if key == r_lower or name.lower() == r_lower:
            return key

    # 2. Substring Match Check
    for key, (db_emoji, _, name) in RARITIES.items():
        if key in r_lower or name.lower() in r_lower or db_emoji in r_lower:
            return key
            
    return "common"

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

@dataclass
class Char:
    id: str
    name: str
    anime: str
    rarity: str
    img_url: str
    is_video: bool = False
    price: int = 0

    @classmethod
    def from_dict(cls, d: Dict) -> 'Char':
        return cls(str(d.get('id', '??')), d.get('name', 'Unknown'), d.get('anime', 'Unknown'),
                    d.get('rarity', '🟢 Common'), d.get('img_url', ''), d.get('is_video', False),
                    d.get('price', 0))

def rarity_parts(rarity) -> Tuple[str, str]:
    base_key = get_base_rarity(rarity)
    _, tg_emoji, name = RARITIES[base_key]
    return tg_emoji, name

async def silent_auto_delete(message, delay_seconds: int = 1200):
    """Silently deletes a message after a specified number of seconds."""
    await asyncio.sleep(delay_seconds)
    try:
        await message.delete()
    except Exception:
        pass # Silently ignore if already deleted or bot lacks permission

async def get_char(cid: str) -> Optional[Char]:
    if cid in char_cache:
        return char_cache[cid]
    search_ids = [str(cid)]
    if str(cid).isdigit():
        search_ids.append(int(cid))
    d = await collection.find_one({'id': {'$in': search_ids}})
    if d:
        char_obj = Char.from_dict(d)
        char_cache[cid] = char_obj
        return char_obj
    return None

async def find_by_anime(anime: str) -> List[Dict]:
    key = anime.lower()
    if key in anime_cache:
        return anime_cache[key]
    res = await collection.find({'anime': {'$regex': anime, '$options': 'i'}}).to_list(length=None)
    if res:
        anime_cache[key] = res
    return res

async def global_count(cid: str) -> int:
    key = f"c_{cid}"
    if key in user_cache:
        return user_cache[key]
    try:
        search_ids = [str(cid)]
        if str(cid).isdigit():
            search_ids.append(int(cid))
        n = await user_collection.count_documents({'characters.id': {'$in': search_ids}})
    except Exception:
        n = 0
    user_cache[key] = n
    return n

# 🔥 MEGA FIX: Aggregation Pipeline for SUPER FAST owner fetching
async def get_owners(cid: str) -> List[Dict]:
    key = f"o_{cid}"
    if key in user_cache:
        return user_cache[key]
        
    search_ids = [str(cid)]
    if str(cid).isdigit():
        search_ids.append(int(cid))
        
    try:
        pipeline = [
            {'$match': {'characters.id': {'$in': search_ids}}},
            {'$project': {
                '_id': 0,
                'id': 1,
                'first_name': 1,
                'count': {
                    '$size': {
                        '$filter': {
                            'input': '$characters',
                            'as': 'c',
                            'cond': {'$in': ['$$c.id', search_ids]}
                        }
                    }
                }
            }},
            {'$sort': {'count': -1}},
            {'$limit': 100}
        ]
        owners = await user_collection.aggregate(pipeline).to_list(length=100)
    except Exception:
        owners = []
        
    user_cache[key] = owners
    return owners

def clear_char_cache(cid: str) -> None:
    owner_key = f"o_{cid}"
    count_key = f"c_{cid}"
    if owner_key in user_cache:
        del user_cache[owner_key]
    if count_key in user_cache:
        del user_cache[count_key]

def process_search(chars: List[Dict]) -> Dict:
    names, data, rarities = {}, {}, {}
    for c in chars:
        n = c.get('name', 'Unknown')
        if n not in names:
            names[n] = 0
            data[n] = c
        names[n] += 1
        e, _ = rarity_parts(c.get('rarity', '🟢 Common'))
        rarities[e] = rarities.get(e, 0) + 1
    return {'names': names, 'data': data, 'rarities': rarities, 'unique': len(names), 'total': len(chars)}

def card_caption(char: Char, gcount: int) -> str:
    emoji, text = rarity_parts(char.rarity)
    return (
        f"<b><tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> {to_small_caps('ultimate w-h info')} <tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji></b>\n"
        "\n"
        f"<tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji> 𝗡𝗔𝗠𝗘: <b>{escape(char.name)}</b>\n"
        f"{emoji} 𝗥𝗔𝗥𝗜𝗧𝗬: <b>{escape(text)}</b>\n"
        f"<tg-emoji emoji-id=\"6314494724266796319\">🟠</tg-emoji> 𝗦𝗢𝗨𝗥𝗖𝗘: <b>{escape(char.anime)}</b>\n"
        f"<tg-emoji emoji-id=\"6332443074769196273\">🆔</tg-emoji> 𝗖𝗛𝗥 𝗜𝗗: <code>{char.id}</code>\n"
        "\n"
        f"<tg-emoji emoji-id=\"5224450179368767019\">🌎</tg-emoji> {bold_sc('globally grabbed :')} <code>{gcount}x</code>"
    )

def owners_caption(char: Char, owners: List[Dict], page: int, gcount: int) -> str:
    start, end = page * USERS_PER_PAGE, page * USERS_PER_PAGE + USERS_PER_PAGE
    total_pages = max(1, (len(owners) + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    lines = [f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> {bold_sc('character owners')} <tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji>\n"]
    for i, o in enumerate(owners[start:end], start + 1):
        medal = {
            1: '<tg-emoji emoji-id="5440539497383087970">🥇</tg-emoji>', 
            2: '<tg-emoji emoji-id="5447203607294265305">🥈</tg-emoji>', 
            3: '<tg-emoji emoji-id="5453902265922376865">🥉</tg-emoji>'
        }.get(i, f"<b>{i}.</b>")
        link = f"<b><a href='tg://user?id={o['id']}'>{escape(o.get('first_name', 'Unknown'))}</a></b>"
        lines.append(f"{medal} {link} - <b>x{o['count']}</b>")
    lines.append(f"\n<tg-emoji emoji-id=\"5197269100878907942\">✍️</tg-emoji> {bold_sc(f'page {page+1}/{total_pages}')} • <tg-emoji emoji-id=\"5224450179368767019\">🌎</tg-emoji> {bold_sc('total:')} <code>{gcount}x</code>")
    return "\n".join(lines)

def pagination_kb(cid: str, page: int, total: int, back=False) -> InlineKeyboardMarkup:
    kb = []
    if back:
        if total > 1:
            row = []
            if page > 0: row.append(InlineKeyboardButton(to_small_caps("⋞ prev"), callback_data=f"owners_{cid}_{page-1}"))
            if page < total - 1: row.append(InlineKeyboardButton(to_small_caps("next ⋟"), callback_data=f"owners_{cid}_{page+1}"))
            if row: kb.append(row)
        kb.append([InlineKeyboardButton(to_small_caps("⟲ back to info"), callback_data=f"back_{cid}")])
    else:
        # User jab "owners" dabaayega sirf tab owners load honge!
        kb.append([InlineKeyboardButton(to_small_caps("owners"), callback_data=f"owners_{cid}_0")])
    return InlineKeyboardMarkup(kb)

def find_caption(query: str, r: Dict, page: int, show_all: bool) -> Tuple[str, int]:
    total_pages = 1 if show_all else max(1, (r['unique'] + 15 - 1) // 15)
    lines = [
        f"{bold_sc('anime search results')}",
        f"<tg-emoji emoji-id=\"5433653135799228968\">📁</tg-emoji> {bold_sc('query ⬡')} <b><i>{to_small_caps(escape(query))}</i></b>",
        f"<tg-emoji emoji-id=\"6330041629704985188\">📊</tg-emoji> {bold_sc('total ⬡')} <code>{r['total']}</code> | {bold_sc('unique ⬡')} <code>{r['unique']}</code>",
        "\n"
    ]
    items = sorted(r['names'].items())
    s, e = (0, len(items)) if show_all else (page * 15, page * 15 + 15)
    for i, (name, cnt) in enumerate(items[s:e], s + 1):
        c = r['data'][name]
        emoji, text = rarity_parts(c.get('rarity', '🟢 Common'))
        lines.append(f"<b>{i}.</b> <code>{to_small_caps(escape(name))}</code> ⦅<code>{c.get('id','??')}</code>⦆ {emoji} <b><i>{to_small_caps(text)}</i></b>"
                      + (f" <b>(x{cnt})</b>" if cnt > 1 else ""))
    if not show_all and total_pages > 1:
        lines.append(f"\n<tg-emoji emoji-id=\"5240228673738527951\">🏷</tg-emoji> {bold_sc(f'page {page+1}/{total_pages}')}")
    return "\n".join(lines), total_pages

async def send_media(update: Update, char: Char, caption: str, kb=None) -> None:
    sent_message = None
    try:
        kwargs = {'caption': caption, 'parse_mode': ParseMode.HTML}
        if kb:
            kwargs['reply_markup'] = kb
        if char.is_video:
            sent_message = await update.message.reply_video(video=char.img_url, **kwargs)
        else:
            try:
                sent_message = await update.message.reply_photo(photo=char.img_url, **kwargs)
            except TelegramError:
                sent_message = await update.message.reply_document(document=char.img_url, **kwargs)
    except TelegramError as e:
        sent_message = await update.message.reply_text(
            f"{caption}\n\n<tg-emoji emoji-id=\"6323595854456298870\">⚠️</tg-emoji> {bold_sc('media error:')} {bold_sc(escape(str(e)))}",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
        
    if sent_message:
        asyncio.create_task(silent_auto_delete(sent_message))

# 🔥 CHECK CHARACTER COMMAND (AB OWNERS FETCH NAHI KAREGA = EXTREMELY FAST)
async def check_character(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        msg = await update.message.reply_text(f"<tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> {bold_sc('usage:')} <code>/check <id></code>", parse_mode=ParseMode.HTML)
        asyncio.create_task(silent_auto_delete(msg))
        return
    
    char = await get_char(context.args[0])
    if not char:
        msg = await update.message.reply_text(f"<tg-emoji emoji-id=\"6323595854456298870\">⚠️</tg-emoji> {bold_sc('character not found in database!')}", parse_mode=ParseMode.HTML)
        asyncio.create_task(silent_auto_delete(msg))
        return
    
    gcount = await global_count(char.id)
    # Owners block removed from here! Fast load now!
    await send_media(update, char, card_caption(char, gcount), pagination_kb(char.id, 0, 1, back=False))

# 🔥 FIND ANIME COMMAND
async def find_anime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        msg = await update.message.reply_text(f"<tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> {bold_sc('usage:')} <code>/anime <name></code>", parse_mode=ParseMode.HTML)
        asyncio.create_task(silent_auto_delete(msg))
        return
        
    name = ' '.join(context.args)
    chars = await find_by_anime(name)
    if not chars:
        msg = await update.message.reply_text(f"<tg-emoji emoji-id=\"6323595854456298870\">⚠️</tg-emoji> {bold_sc('no characters found from')} <b><i>{to_small_caps(escape(name))}</i></b>", parse_mode=ParseMode.HTML)
        asyncio.create_task(silent_auto_delete(msg))
        return
        
    r = process_search(chars)
    text, _ = find_caption(name, r, 0, True)
    msg = await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    asyncio.create_task(silent_auto_delete(msg))

# 🔥 GET ID COMMAND
async def get_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID:
        return 

    if not update.message or not update.message.reply_to_message:
        msg = await update.message.reply_text(f"⚠️ {bold_sc('error: reply to a high-quality photo or video with')} <code>/getid</code>.", parse_mode=ParseMode.HTML)
        asyncio.create_task(silent_auto_delete(msg))
        return

    reply_msg = update.message.reply_to_message
    instruction = bold_sc("copy this id and paste it in mongodb as 'img_url'!")

    msg = None
    if reply_msg.photo:
        file_id = reply_msg.photo[-1].file_id
        msg = await update.message.reply_text(f"📸 {bold_sc('photo file id:')}\n<code>{file_id}</code>\n\n{instruction}", parse_mode=ParseMode.HTML)
    elif reply_msg.video:
        file_id = reply_msg.video.file_id
        msg = await update.message.reply_text(f"🎥 {bold_sc('video file id:')}\n<code>{file_id}</code>\n\n{instruction}", parse_mode=ParseMode.HTML)
    elif reply_msg.document:
        file_id = reply_msg.document.file_id
        msg = await update.message.reply_text(f"📁 {bold_sc('document file id:')}\n<code>{file_id}</code>\n\n{instruction}", parse_mode=ParseMode.HTML)
    else:
        msg = await update.message.reply_text(f"⚠️ {bold_sc('invalid media: this is not a proper photo or video.')}", parse_mode=ParseMode.HTML)
        
    if msg:
        asyncio.create_task(silent_auto_delete(msg))

# 🔥 FIX RARITY COMMAND
async def fixrarity_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        requester_id = update.effective_user.id
        if not is_authorized(requester_id):
            return 

        if not context.args:
            msg = await update.message.reply_text(f"<b>⚠️ {to_small_caps('usage:')}</b> <code>/fixrarity [char_id]</code>", parse_mode=ParseMode.HTML)
            asyncio.create_task(silent_auto_delete(msg))
            return

        char_id_input = str(context.args[0])
        
        search_ids = [char_id_input]
        if char_id_input.isdigit():
            search_ids.append(int(char_id_input))      

        global_char = await collection.find_one({'id': {'$in': search_ids}})
        
        if not global_char:
            msg = await update.message.reply_text(f"<b>❌ {to_small_caps('character id')} <code>{char_id_input}</code> {to_small_caps('not found in database!')}</b>", parse_mode=ParseMode.HTML)
            asyncio.create_task(silent_auto_delete(msg))
            return

        current_rarity = global_char.get('rarity', 'Unknown')
        current_name = global_char.get('name', 'Unknown')

        users_cursor = user_collection.find({"characters.id": {"$in": search_ids}})
        affected_count = 0
        
        async for user in users_cursor:
            updated_chars = []
            modified = False
            for c in user.get('characters', []):
                if c.get('id') in search_ids:
                    c['rarity'] = current_rarity
                    c['name'] = current_name
                    modified = True
                updated_chars.append(c)
            
            if modified:
                await user_collection.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"characters": updated_chars}}
                )
                affected_count += 1
                
        clear_char_cache(char_id_input)

        success_msg = (
            f"<b>✅ {to_small_caps('database updated successfully!')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>🆔 {to_small_caps('char id:')}</b> <code>{char_id_input}</code>\n"
            f"<b>📝 {to_small_caps('char name:')}</b> <code>{to_small_caps(current_name)}</code>\n"
            f"<b>✨ {to_small_caps('current rarity:')}</b> <code>{to_small_caps(current_rarity)}</code>\n"
            f"<b>👥 {to_small_caps('users affected:')}</b> <code>{affected_count}</code> {to_small_caps('players')}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        msg = await update.message.reply_text(success_msg, parse_mode=ParseMode.HTML)
        asyncio.create_task(silent_auto_delete(msg))

    except Exception as e:
        msg = await update.message.reply_text(f"<b>⚠️ {to_small_caps('error:')}</b> <code>{escape(str(e))}</code>", parse_mode=ParseMode.HTML)
        asyncio.create_task(silent_auto_delete(msg))

# 🔥 PAGINATION HANDLERS (Owners fetch ab yahan hoga)
async def handle_owners_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    _, cid, page = q.data.split('_')
    page = int(page)
    char = await get_char(cid)
    
    if not char:
        return await q.answer(to_small_caps("character not found"), show_alert=True)
        
    owners = await get_owners(cid) # Fast aggregation used!
    gcount = await global_count(cid)
    
    total_pages = max(1, (len(owners) + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    
    # FIX APPLIED HERE: Replaced cmd_owners_caption with owners_caption
    await q.edit_message_caption(
        caption=owners_caption(char, owners, page, gcount), 
        reply_markup=pagination_kb(cid, page, total_pages, back=True),
        parse_mode=ParseMode.HTML
    )

async def handle_back_to_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    cid = q.data.split('_')[1]
    
    char = await get_char(cid)
    if not char:
        return await q.answer(to_small_caps("character not found"), show_alert=True)
        
    gcount = await global_count(cid)
    # Owners block removed from here! Fast load now!
    
    await q.edit_message_caption(
        caption=card_caption(char, gcount),
        reply_markup=pagination_kb(cid, 0, 1, back=False),
        parse_mode=ParseMode.HTML
    )

# --- HANDLER REGISTRATIONS ---
application.add_handler(CommandHandler("check", check_character, block=False))
application.add_handler(CommandHandler("anime", find_anime, block=False))
application.add_handler(CommandHandler("getid", get_file_id, block=False))
application.add_handler(CommandHandler("fixrarity", fixrarity_cmd, block=False))
application.add_handler(CallbackQueryHandler(handle_owners_pagination, pattern=r"^owners_", block=False))
application.add_handler(CallbackQueryHandler(handle_back_to_card, pattern=r"^back_", block=False))

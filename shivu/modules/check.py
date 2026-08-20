from html import escape
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from cachetools import TTLCache

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.error import TelegramError

from shivu import application, collection, user_collection

char_cache = TTLCache(maxsize=2000, ttl=600)
anime_cache = TTLCache(maxsize=1000, ttl=900)
user_cache = TTLCache(maxsize=500, ttl=300)

USERS_PER_PAGE = 10

# --- ✨ RARITIES MAPPING FOR CUSTOM EMOJIS ---
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
    "pearl": ("🏖️", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"), 
    "cosmic": ("🌌", '<tg-emoji emoji-id="5431783411981228752">🎆</tg-emoji>', "Cosmic"),
}

def get_rarity_key(rarity_str):
    if not isinstance(rarity_str, str):
        return None
    rarity_str = rarity_str.strip()
    db_emoji, name = (rarity_str.split(' ', 1) + [''])[:2] if ' ' in rarity_str else (rarity_str, '')
    name = name.strip().lower()
    for key, (r_db_emoji, _, r_name) in RARITIES.items():
        if rarity_str.lower() == key or db_emoji == r_db_emoji or name == r_name.lower():
            return key
    return None


# --- ✨ UNIVERSAL SMALL CAPS CONVERTER ---
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
    id: str; name: str; anime: str; rarity: str; img_url: str
    is_video: bool = False; price: int = 0

    @classmethod
    def from_dict(cls, d: Dict) -> 'Char':
        return cls(str(d.get('id', '??')), d.get('name', 'Unknown'), d.get('anime', 'Unknown'),
                    d.get('rarity', '🟢 Common'), d.get('img_url', ''), d.get('is_video', False),
                    d.get('price', 0))


def rarity_parts(rarity) -> Tuple[str, str]:
    r_key = get_rarity_key(rarity)
    if r_key and r_key in RARITIES:
        _, display_emoji, name = RARITIES[r_key]
        return display_emoji, name
    if isinstance(rarity, str):
        p = rarity.split(' ', 1)
        return (p[0], p[1] if len(p) > 1 else 'Common')
    return '🟢', 'Common'


async def get_char(cid: str) -> Optional[Char]:
    if cid in char_cache:
        return char_cache[cid]
    
    # 🔥 FIX: String aur Integer dono formats prepare karenge type mismatch rokne ke liye
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
        # Check both string and int in user harem collection
        search_ids = [str(cid)]
        if str(cid).isdigit():
            search_ids.append(int(cid))
        n = await user_collection.count_documents({'characters.id': {'$in': search_ids}})
    except Exception:
        n = 0
    user_cache[key] = n
    return n


async def get_owners(cid: str) -> List[Dict]:
    key = f"o_{cid}"
    if key in user_cache:
        return user_cache[key]
    
    search_ids = [str(cid)]
    if str(cid).isdigit():
        search_ids.append(int(cid))

    users = await user_collection.find(
        {'characters.id': {'$in': search_ids}}, {'_id': 0, 'id': 1, 'first_name': 1, 'username': 1, 'characters': 1}
    ).to_list(length=None)
    
    owners = []
    for u in users:
        cnt = sum(1 for c in u.get('characters', []) if str(c.get('id')) in [str(x) for x in search_ids])
        if cnt:
            owners.append({'id': u['id'], 'first_name': u.get('first_name', 'Unknown'),
                            'username': u.get('username'), 'count': cnt})
    owners.sort(key=lambda x: x['count'], reverse=True)
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
        f"<tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji> {bold_sc('name ⬡')} <b>{escape(char.name)}</b>\n"
        f"<tg-emoji emoji-id=\"6093611479720795757\">💫</tg-emoji> {bold_sc('rarity ⬡')} {emoji} <b>{escape(text)}</b>\n"
        f"<tg-emoji emoji-id=\"6314494724266796319\">🟠</tg-emoji> {bold_sc('anime ⬡')} <b>{escape(char.anime)}</b>\n"
        f"<tg-emoji emoji-id=\"6332443074769196273\">🆔</tg-emoji> {bold_sc('char id ⬡')} <code>{char.id}</code>\n"
        "\n"
        f"<tg-emoji emoji-id=\"5224450179368767019\">🌎</tg-emoji> {bold_sc('globally grabbed :')} <code>{gcount}x</code>"
    )


def owners_caption(char: Char, owners: List[Dict], page: int, gcount: int) -> str:
    start, end = page * USERS_PER_PAGE, page * USERS_PER_PAGE + USERS_PER_PAGE
    total_pages = max(1, (len(owners) + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    
    lines = [
        f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> {bold_sc('character owners')} <tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji>\n"
    ]
    
    for i, o in enumerate(owners[start:end], start + 1):
        medal = {
            1: '<tg-emoji emoji-id="5440539497383087970">🥇</tg-emoji>', 
            2: '<tg-emoji emoji-id="5447203607294265305">🥈</tg-emoji>', 
            3: '<tg-emoji emoji-id="5453902265922376865">🥉</tg-emoji>'
        }.get(i, f"<b>{i}.</b>")
        
        link = f"<b><a href='tg://user?id={o['id']}'>{escape(o['first_name'])}</a></b>"
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
    try:
        kwargs = {'caption': caption, 'parse_mode': ParseMode.HTML}
        if kb:
            kwargs['reply_markup'] = kb
        
        if char.is_video:
            await update.message.reply_video(video=char.img_url, **kwargs)
        else:
            try:
                await update.message.reply_photo(photo=char.img_url, **kwargs)
            except TelegramError:
                await update.message.reply_document(document=char.img_url, **kwargs)
                
    except TelegramError as e:
        await update.message.reply_text(
            f"{caption}\n\n<tg-emoji emoji-id=\"6323595854456298870\">⚠️</tg-emoji> {bold_sc('media error:')} {bold_sc(escape(str(e)))}",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )


async def get_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != 7657218453:
        return 

    if not update.message.reply_to_message:
        return await update.message.reply_text(f"⚠️ {bold_sc('error: reply to a high-quality photo or video with')} <code>/getid</code>.", parse_mode=ParseMode.HTML)

    reply_msg = update.message.reply_to_message
    instruction = bold_sc("copy this id and paste it in mongodb as 'img_url'!")

    if reply_msg.photo:
        file_id = reply_msg.photo[-1].file_id
        await update.message.reply_text(f"📸 {bold_sc('photo file id:')}\n<code>{file_id}</code>\n\n{instruction}", parse_mode=ParseMode.HTML)
        
    elif reply_msg.video:
        file_id = reply_msg.video.file_id
        await update.message.reply_text(f"🎥 {bold_sc('video file id:')}\n<code>{file_id}</code>\n\n{instruction}", parse_mode=ParseMode.HTML)
        
    elif reply_msg.document:
        file_id = reply_msg.document.file_id
        await update.message.reply_text(f"📁 {bold_sc('document file id:')}\n<code>{file_id}</code>\n\n{instruction}", parse_mode=ParseMode.HTML)
        
    else:
        await update.message.reply_text(f"⚠️ {bold_sc('invalid media: this is not a proper photo or video.')}", parse_mode=ParseMode.HTML)


async def check_character(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        return await update.message.reply_text(f"<tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> {bold_sc('usage:')} <code>/check &lt;id&gt;</code>", parse_mode=ParseMode.HTML)
    char = await get_char(context.args[0])
    if not char:
        return await update.message.reply_text(f"<tg-emoji emoji-id=\"6323595854456298870\">⚠️</tg-emoji> {bold_sc('character not found in database!')}", parse_mode=ParseMode.HTML)
    gcount = await global_count(char.id)
    owners = await get_owners(char.id)
    total_pages = max(1, (len(owners) + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    await send_media(update, char, card_caption(char, gcount), pagination_kb(char.id, 0, total_pages, back=False))


async def find_anime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        return await update.message.reply_text(f"<tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> {bold_sc('usage:')} <code>/anime &lt;name&gt;</code>", parse_mode=ParseMode.HTML)
    name = ' '.join(context.args)
    chars = await find_by_anime(name)
    if not chars:
        return await update.message.reply_text(f"<tg-emoji emoji-id=\"6323595854456298870\">⚠️</tg-emoji> {bold_sc('no characters found from')} <b><i>{to_small_caps(escape(name))}</i></b>", parse_mode=ParseMode.HTML)
    r = process_search(chars)
    text, _ = find_caption(name, r, 0, True)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def handle_owners_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    _, cid, page = q.data.split('_')
    page = int(page)
    char = await get_char(cid)
    owners = await get_owners(cid)
    if not char:
        return await q.answer(to_small_caps("character not found"), show_alert=True)
    gcount = await global_count(cid)
    total_pages = max(1, (len(owners) + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    
    await q.edit_message_caption(
        caption=owners_caption(char, owners, page, gcount),
        reply_markup=pagination_kb(cid, page, total_pages, back=True),
.        parse_mode=ParseMode.HTML
    )


async def handle_back_to_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    cid = q.data.split('_')[1]
    char = await get_char(cid)
    if not char:
        return await q.answer(to_small_caps("character not found"), show_alert=True)
    gcount = await global_count(cid)
    owners = await get_owners(cid)
    total_pages = max(1, (len(owners) + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    
    await q.edit_message_caption(
        caption=card_caption(char, gcount),
        reply_markup=pagination_kb(cid, 0, total_pages, back=False),
        parse_mode=ParseMode.HTML
    )


application.add_handler(CommandHandler("check", check_character, block=False))
application.add_handler(CommandHandler("anime", find_anime, block=False))
application.add_handler(CommandHandler("getid", get_file_id, block=False))
application.add_handler(CallbackQueryHandler(handle_owners_pagination, pattern=r"^owners_", block=False))
application.add_handler(CallbackQueryHandler(handle_back_to_card, pattern=r"^back_", block=False))

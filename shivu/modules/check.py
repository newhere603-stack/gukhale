import re
import time
import hashlib
import logging
from html import escape
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from cachetools import TTLCache, LRUCache
from pymongo import ASCENDING, TEXT
from functools import lru_cache

from telegram import Update, InlineQueryResultPhoto, InlineQueryResultVideo, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import InlineQueryHandler, CallbackQueryHandler, ChosenInlineResultHandler, ContextTypes, CommandHandler
from telegram.constants import ParseMode
from telegram.error import TelegramError

from shivu import application, db, user_collection

LOGGER = logging.getLogger(__name__)

collection = db['anime_characters_lol']

# --- OWNER OR SUDO CHECK ---
OWNER_ID = 7657218453
SUDO_USERS = [7657218453]

def is_authorized(user_id):
    return user_id == OWNER_ID or user_id in SUDO_USERS
# ---------------------------

@dataclass
class Rarity:
    emoji: str
    name: str
    value: int

# 🔥 UNIFIED RARITIES DICTIONARY (Single Source of Truth)
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
    "summer": ("🏖️", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"), 
    "cosmic": ("🌌", '<tg-emoji emoji-id="5431783411981228752">🎆</tg-emoji>', "Cosmic"),
}

SORT_VALUES = {
    "mythic": 1, "cosmic": 2, "celestial": 3, "exclusive": 4,
    "legendary": 5, "premium": 6, "neon": 7, "summer": 8, "sweet": 9,
    "special": 10, "valentine": 11, "winter": 12, "erotic": 13,
    "rare": 14, "common": 15
}

try:
    collection.create_index([('id', ASCENDING)], unique=True, background=True)
    collection.create_index([('rarity', ASCENDING), ('anime', ASCENDING)], background=True)
    user_collection.create_index([('id', ASCENDING)], unique=True, background=True)
    user_collection.create_index([('characters.id', ASCENDING)], background=True, sparse=True)
except Exception: 
    pass

# 🔥 Caches tuned for fast response but quick refresh on edits (300s instead of 3600s)
char_cache = TTLCache(maxsize=100000, ttl=300) 
anime_cache = TTLCache(maxsize=1000, ttl=300)
user_cache = TTLCache(maxsize=60000, ttl=300) 
query_cache = TTLCache(maxsize=20000, ttl=30) 
count_cache = TTLCache(maxsize=40000, ttl=300)
feedback_cache = TTLCache(maxsize=15000, ttl=4800)
wishlist_cache = TTLCache(maxsize=8000, ttl=2400)

CAPS = str.maketrans('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', 'ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ')

@lru_cache(maxsize=65536)
def sc(t: str) -> str: 
    return t.translate(CAPS)

def to_small_caps(text: str) -> str:
    return sc(str(text))

def bold_sc(text: str) -> str:
    return f"<b>{sc(text)}</b>"

# 🔥 THE MEGA FIX: Perfect Rarity Matcher Function
def get_base_rarity(rarity_str: str) -> str:
    if not rarity_str or not isinstance(rarity_str, str):
        return "common"
    r_lower = rarity_str.lower().strip()

    # 1. Check exact matches first
    for key, (_, _, name) in RARITIES.items():
        if key == r_lower or name.lower() == r_lower:
            return key

    # 2. Check substring if exact match fails
    for key, (db_emoji, _, name) in RARITIES.items():
        if key in r_lower or name.lower() in r_lower or db_emoji in r_lower:
            return key

    return "common"

# Used for Inline Sort & Display
@lru_cache(maxsize=32768)
def parse_rar(r: str) -> Rarity:
    base_key = get_base_rarity(r)
    val = SORT_VALUES.get(base_key, 15)
    db_emoji, _, name = RARITIES[base_key]
    return Rarity(db_emoji, sc(name), val)

# Used for /check and /anime display
def rarity_parts(rarity) -> Tuple[str, str]:
    base_key = get_base_rarity(rarity)
    _, tg_emoji, name = RARITIES[base_key]
    return tg_emoji, name

def trunc(t: str, l: int = 22) -> str: 
    return t[:l-2] + '..' if len(t) > l else t

def cache_key(*args) -> str: 
    return hashlib.md5(str(args).encode()).hexdigest()

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

async def get_user(uid: int) -> Optional[Dict]:
    k = f"u{uid}"
    if k in user_cache: 
        return user_cache[k]
    u = await user_collection.find_one({'id': uid}, {'_id': 0})
    if u: 
        user_cache[k] = u
    return u

async def get_owners(cid: str, lim: int = 100) -> List[Dict]:
    k = f"o{cid}{lim}"
    if k in count_cache: 
        return count_cache[k]
    try:
        pipe = [
            {'$match': {'characters.id': cid}},
            {'$project': {'id': 1, 'first_name': 1, 'username': 1, 'characters': {'$filter': {'input': '$characters', 'as': 'c', 'cond': {'$eq': ['$$c.id', cid]}}}}},
            {'$addFields': {'count': {'$size': '$characters'}}},
            {'$sort': {'count': -1}},
            {'$limit': lim},
            {'$project': {'characters': 0}}
        ]
        owners = await user_collection.aggregate(pipe).to_list(length=lim)
        count_cache[k] = owners
        return owners
    except Exception:
        return []

async def search_chars(q: str, lim: int = 1000) -> List[Dict]:
    k = cache_key('search', q, lim)
    if k in query_cache: 
        return query_cache[k]
    try:
        if q:
            rx = re.compile(re.escape(q), re.IGNORECASE)
            chars = await collection.find({'$or': [{'name': rx}, {'anime': rx}, {'id': q}, {'rarity': rx}]}, {'_id': 0}).limit(lim).to_list(length=lim)
        else:
            chars = await collection.find({}, {'_id': 0}).limit(lim).to_list(length=lim)
        query_cache[k] = chars
        return chars
    except Exception as e:
        LOGGER.error(f"Search error: {e}")
        return []

async def filter_chars(chars: List[Dict], mode: str, uid: int = None) -> List[Dict]:
    if mode == 'rare': 
        return [c for c in chars if parse_rar(c.get('rarity', '')).value <= 9]
    elif mode == 'video': 
        return [c for c in chars if c.get('is_video', False)]
    elif mode == 'new': 
        return sorted(chars, key=lambda x: str(x.get('_id', '')), reverse=True)
    elif mode == 'trending':
        ids = [c.get('id') for c in chars if c.get('id')]
        if ids:
            picks = {cid: feedback_cache.get(f'pick_{cid}', 0) for cid in ids if feedback_cache.get(f'pick_{cid}', 0) > 0}
            return sorted(chars, key=lambda x: picks.get(x.get('id'), 0), reverse=True)
    elif mode == 'owned' and uid:
        usr = await get_user(uid)
        if usr:
            owned = {c.get('id') for c in usr.get('characters', []) if isinstance(c, dict) and c.get('id')}
            return [c for c in chars if c.get('id') in owned]
    elif mode == 'notowned' and uid:
        usr = await get_user(uid)
        if usr:
            owned = {c.get('id') for c in usr.get('characters', []) if isinstance(c, dict) and c.get('id')}
            return [c for c in chars if c.get('id') not in owned]
    elif mode == 'wishlist' and uid:
        wl = wishlist_cache.get(f'wl_{uid}', set())
        return [c for c in chars if c.get('id') in wl]
    return chars

def dedupe(chars: List[Dict]) -> List[Dict]:
    seen, result = set(), []
    for c in chars:
        cid = c.get('id')
        if cid and cid not in seen:
            seen.add(cid)
            result.append(c)
    return result

def minimal_caption(ch: Dict, fav: bool = False, uid: int = None) -> str:
    cid, nm, an = ch.get('id', '??'), ch.get('name', 'Unknown'), ch.get('anime', 'Unknown')
    r = parse_rar(ch.get('rarity', ''))
    
    cap = (
        f"<b>{sc('Character Info ✨')}</b>\n\n"
        f"<b>{escape(sc(an))}</b>\n"
        f"<b>{cid}: {escape(sc(nm))}</b>\n"
        f"({r.emoji}<b>{sc('RARITY:')}</b> {r.name})"
    )
    return cap

def owners_caption_msg(ch: Dict, owners: List[Dict]) -> str:
    nm = ch.get('name', 'Unknown')
    total = sum(o.get('count', 0) for o in owners)
    cap = f"<b>{escape(sc(nm))}</b>\n\n<b>🏆 {len(owners)} {sc('owners')} • {total}× {sc('grabbed')}</b>\n\n"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, o in enumerate(owners[:30], 1):
        medal = medals.get(i, f"{i}.")
        fn = escape(trunc(o.get('first_name', 'User'), 18))
        uid = o.get('id')
        cap += f"{medal} <a href=\"tg://user?id={uid}\"><b>{fn}</b></a> • <code>×{o.get('count', 0)}</code>\n"
    return cap

def stats_caption(ch: Dict, owners: List[Dict]) -> str:
    nm = ch.get('name', 'Unknown')
    total = sum(o.get('count', 0) for o in owners)
    avg = round(total / len(owners), 1) if owners else 0
    cap = f"<b>{escape(sc(nm))}</b>\n\n📊 <b>{sc('statistics')}</b>\n🎯 <code>{total}×</code> {sc('grabbed')}\n🏆 <code>{len(owners)}</code> {sc('owners')}\n📈 <code>{avg}×</code> {sc('avg')}\n"
    if owners:
        cap += f"\n🏆 <b>{sc('top collectors')}</b>\n"
        for i, o in enumerate(owners[:10], 1):
            fn = escape(trunc(o.get('first_name', 'User'), 18))
            uid = o.get('id')
            cap += f"{i}. <a href=\"tg://user?id={uid}\"><b>{fn}</b></a> • <code>×{o.get('count', 0)}</code>\n"
    return cap

def create_kbd(cid: str, uid: int = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(sc("♔ owners"), callback_data=f"o.{cid}"),
            InlineKeyboardButton(sc("stats ⑆"), callback_data=f"s.{cid}")
        ],
        [
            InlineKeyboardButton(sc("⤿ share"), switch_inline_query=cid)
        ]
    ])

async def inlinequery(update: Update, context) -> None:
    query = update.inline_query
    q, off, uid, qid = query.query, int(query.offset) if query.offset else 0, query.from_user.id, query.id
    try:
        is_coll, usr, sq, fm = False, None, q, None
        
        if q.startswith('collection.'):
            is_coll = True
            parts = q.split(' ', 1)
            tid = parts[0].split('.')[1]
            sq = parts[1].strip() if len(parts) > 1 else ''
            for m in ['rare', 'video', 'new', 'trending', 'owned', 'notowned', 'wishlist']:
                if sq.startswith(f'-{m}'):
                    fm = m
                    sq = sq.replace(f'-{m}', '').strip()
                    break
            if not tid.isdigit():
                await query.answer([], cache_time=5)
                return
            tuid = int(tid)
            usr = await get_user(tuid)
            if not usr:
                await query.answer([InlineQueryResultArticle(id="nouser", title=sc("no collection"), description=sc("start your journey"), input_message_content=InputTextMessageContent(f"<b>🎮 {sc('start collecting!')}</b>", parse_mode=ParseMode.HTML))], cache_time=5)
                return
            cd = {c['id']: c for c in usr.get('characters', []) if isinstance(c, dict) and c.get('id')}
            all_chars = list(cd.values())
            if sq:
                rx = re.compile(re.escape(sq), re.IGNORECASE)
                all_chars = [c for c in all_chars if rx.search(c.get('name', '')) or rx.search(c.get('anime', '')) or str(c.get('id', '')) == sq or rx.search(c.get('rarity', ''))]
            if fm: 
                all_chars = await filter_chars(all_chars, fm, tuid)
            fav = usr.get('favorites')
            if fav and not sq and not fm:
                fid = fav.get('id') if isinstance(fav, dict) else fav
                fc = next((c for c in all_chars if c.get('id') == fid), None)  
                if fc:
                    all_chars = [c for c in all_chars if c.get('id') != fid]
                    all_chars.insert(0, fc)
            if not fm or fm not in ['new', 'trending']:
                all_chars.sort(key=lambda x: parse_rar(x.get('rarity', '')).value)
        else:
            for m in ['rare', 'video', 'new', 'trending', 'owned', 'notowned', 'wishlist']:
                if sq.startswith(f'-{m}'):
                    fm = m
                    sq = sq.replace(f'-{m}', '').strip()
                    break
            am = re.search(r'-anime:(\S+)', sq)
            if am:
                anime_filter = am.group(1)
                sq = sq.replace(am.group(0), '').strip()
                all_chars = await search_chars(sq, lim=1000)
                rx = re.compile(re.escape(anime_filter), re.IGNORECASE)
                all_chars = [c for c in all_chars if rx.search(c.get('anime', ''))]
            else:
                all_chars = await search_chars(sq, lim=1000)
            if fm: 
                all_chars = await filter_chars(all_chars, fm, uid)
            if not fm or fm not in ['new', 'trending']:
                all_chars.sort(key=lambda x: parse_rar(x.get('rarity', '')).value)
        
        all_chars = dedupe(all_chars)
        chars = all_chars[off:off+50]
        has_more = len(all_chars) > off + 50
        noff = str(off + 50) if has_more else ""

        live_ids = [c.get('id') for c in chars if c.get('id')]
        if live_ids:
            live_docs = await collection.find({'id': {'$in': live_ids}}, {'_id': 0}).to_list(length=50)
            live_map = {d['id']: d for d in live_docs}
            for ch in chars:
                cid = ch.get('id')
                if cid and cid in live_map:
                    ch.update(live_map[cid]) 
        
        results = []
        for ch in chars:
            cid = ch.get('id')
            if not cid: 
                continue
            nm, an, img, vid = ch.get('name', '?'), ch.get('anime', '?'), ch.get('img_url', ''), ch.get('is_video', False)
            r = parse_rar(ch.get('rarity', ''))
            fav = False
            if is_coll and usr:
                fv = usr.get('favorites')
                fid = fv.get('id') if isinstance(fv, dict) else fv
                fav = (fid == cid)
            
            cap = minimal_caption(ch, fav, uid=uid)
            kbd = create_kbd(cid, uid)
            rid = f"{cid}{off}{qid[:8]}"
            title = f"{'💖 ' if fav else ''}{r.emoji} {trunc(nm, 28)}"
            desc = f"{r.name} • {trunc(an, 20)}"
            
            if vid:
                results.append(InlineQueryResultVideo(id=rid, video_url=img, mime_type="video/mp4", thumbnail_url=img, title=title, description=desc, caption=cap, parse_mode=ParseMode.HTML, reply_markup=kbd))
            else:
                results.append(InlineQueryResultPhoto(id=rid, photo_url=img, thumbnail_url=img, title=title, description=desc, caption=cap, parse_mode=ParseMode.HTML, reply_markup=kbd))
        
        await query.answer(results, next_offset=noff, cache_time=5, is_personal=is_coll)
    except Exception as e:
        LOGGER.error(f"Inline query error: {e}")
        try:
            await update.inline_query.answer([], cache_time=5)
        except Exception:
            pass

async def chosen_inline_result(update: Update, context) -> None:
    result = update.chosen_inline_result
    cid = result.result_id
    cp = cid.split('][')
    cidc = cp[0][:20] if cp else cid[:20]
    cidc = ''.join(filter(str.isalnum, cidc))
    fk = f'pick_{cidc}'
    feedback_cache[fk] = feedback_cache.get(fk, 0) + 1
    qk = f'query_{result.from_user.id}'
    feedback_cache[qk] = result.query

async def show_owners(update: Update, context) -> None:
    q = update.callback_query
    await q.answer()
    try:
        cid = q.data.split('.', 1)[1]
        ch = await collection.find_one({'id': cid}, {'_id': 0})
        if not ch:
            await q.answer(sc("not found"), show_alert=True)
            return
        owners = await get_owners(cid, 100)
        if not owners:
            await q.answer(sc("no owners"), show_alert=True)
            return
        cap = owners_caption_msg(ch, owners)
        kbd = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(sc("⟲ back"), callback_data=f"b.{cid}"), 
                InlineKeyboardButton(sc("stats ⑆"), callback_data=f"s.{cid}")
            ], 
            [
                InlineKeyboardButton(sc("⤿ share"), switch_inline_query=cid)
            ]
        ])
        await q.edit_message_caption(caption=cap, parse_mode=ParseMode.HTML, reply_markup=kbd)
    except Exception:
        await q.answer(sc("error"), show_alert=True)

async def back_card(update: Update, context) -> None:
    q = update.callback_query
    await q.answer()
    try:
        cid = q.data.split('.', 1)[1]
        ch = await collection.find_one({'id': cid}, {'_id': 0})
        if not ch:
            await q.answer(sc("not found"), show_alert=True)
            return
        uid = q.from_user.id
        cap = minimal_caption(ch, uid=uid)
        kbd = create_kbd(cid, uid)
        await q.edit_message_caption(caption=cap, parse_mode=ParseMode.HTML, reply_markup=kbd)
    except Exception:
        await q.answer(sc("error"), show_alert=True)

async def show_stats(update: Update, context) -> None:
    q = update.callback_query
    await q.answer()
    try:
        cid = q.data.split('.', 1)[1]
        ch = await collection.find_one({'id': cid}, {'_id': 0})
        if not ch:
            await q.answer(sc("not found"), show_alert=True)
            return
        owners = await get_owners(cid, 100)
        cap = stats_caption(ch, owners)
        kbd = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(sc("⟲ back"), callback_data=f"b.{cid}"), 
                InlineKeyboardButton(sc("owners ♔"), callback_data=f"o.{cid}")
            ], 
            [
                InlineKeyboardButton(sc("⤿ share"), switch_inline_query=cid)
            ]
        ])
        await q.edit_message_caption(caption=cap, parse_mode=ParseMode.HTML, reply_markup=kbd)
    except Exception:
        await q.answer(sc("error"), show_alert=True)

# -----------------
# CHECK & COMMANDS
# -----------------
USERS_PER_PAGE = 10

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
    if key in count_cache:
        return count_cache[key]
    try:
        search_ids = [str(cid)]
        if str(cid).isdigit():
            search_ids.append(int(cid))
        n = await user_collection.count_documents({'characters.id': {'$in': search_ids}})
    except Exception:
        n = 0
    count_cache[key] = n
    return n

def clear_char_cache(cid: str) -> None:
    owner_key = f"o_{cid}"
    count_key = f"c_{cid}"
    if owner_key in count_cache:
        del count_cache[owner_key]
    if count_key in count_cache:
        del count_cache[count_key]
    if cid in char_cache:
        del char_cache[cid]

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

# 🔥 CHECK CHARACTER COMMAND
async def check_character(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        return await update.message.reply_text(f"<tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> {bold_sc('usage:')} <code>/check <id></code>", parse_mode=ParseMode.HTML)
    char = await get_char(context.args[0])
    if not char:
        return await update.message.reply_text(f"<tg-emoji emoji-id=\"6323595854456298870\">⚠️</tg-emoji> {bold_sc('character not found in database!')}", parse_mode=ParseMode.HTML)
    gcount = await global_count(char.id)
    owners = await get_owners(char.id)
    total_pages = max(1, (len(owners) + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    await send_media(update, char, card_caption(char, gcount), pagination_kb(char.id, 0, total_pages, back=False))

# 🔥 FIND ANIME COMMAND
async def find_anime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        return await update.message.reply_text(f"<tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> {bold_sc('usage:')} <code>/anime <name></code>", parse_mode=ParseMode.HTML)
    name = ' '.join(context.args)
    chars = await find_by_anime(name)
    if not chars:
        return await update.message.reply_text(f"<tg-emoji emoji-id=\"6323595854456298870\">⚠️</tg-emoji> {bold_sc('no characters found from')} <b><i>{to_small_caps(escape(name))}</i></b>", parse_mode=ParseMode.HTML)
    r = process_search(chars)
    text, _ = find_caption(name, r, 0, True)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

# 🔥 GET ID COMMAND
async def get_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID:
        return 

    if not update.message or not update.message.reply_to_message:
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

# 🔥 FIX RARITY COMMAND
async def fixrarity_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        requester_id = update.effective_user.id
        if not is_authorized(requester_id):
            return 

        if not context.args:
            await update.message.reply_text(f"<b>⚠️ {to_small_caps('usage:')}</b> <code>/fixrarity [char_id]</code>", parse_mode=ParseMode.HTML)
            return

        char_id_input = str(context.args[0])
        
        search_ids = [char_id_input]
        if char_id_input.isdigit():
            search_ids.append(int(char_id_input))      

        global_char = await collection.find_one({'id': {'$in': search_ids}})
        
        if not global_char:
            await update.message.reply_text(f"<b>❌ {to_small_caps('character id')} <code>{char_id_input}</code> {to_small_caps('not found in database!')}</b>", parse_mode=ParseMode.HTML)
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
        await update.message.reply_text(success_msg, parse_mode=ParseMode.HTML)

    except Exception as e:
        await update.message.reply_text(f"<b>⚠️ {to_small_caps('error:')}</b> <code>{escape(str(e))}</code>", parse_mode=ParseMode.HTML)

# 🔥 PAGINATION HANDLERS
async def handle_owners_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    _, cid, page = q.data.split('_')
    page = int(page)
    char = await get_char(cid)
    owners = await get_owners(cid, 100) # Ensure pagination works fast
    if not char:
        return await q.answer(to_small_caps("character not found"), show_alert=True)
    gcount = await global_count(cid)
    total_pages = max(1, (len(owners) + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
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
    owners = await get_owners(cid, 100)
    total_pages = max(1, (len(owners) + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    await q.edit_message_caption(
        caption=card_caption(char, gcount),
        reply_markup=pagination_kb(cid, 0, total_pages, back=False),
        parse_mode=ParseMode.HTML
    )

# --- HANDLER REGISTRATIONS ---
application.add_handler(InlineQueryHandler(inlinequery, block=False))
application.add_handler(ChosenInlineResultHandler(chosen_inline_result, block=False))
application.add_handler(CallbackQueryHandler(show_owners, pattern=r'^o\.', block=False))
application.add_handler(CallbackQueryHandler(back_card, pattern=r'^b\.', block=False))
application.add_handler(CallbackQueryHandler(show_stats, pattern=r'^s\.', block=False))

application.add_handler(CommandHandler("check", check_character, block=False))
application.add_handler(CommandHandler("anime", find_anime, block=False))
application.add_handler(CommandHandler("getid", get_file_id, block=False))
application.add_handler(CommandHandler("fixrarity", fixrarity_cmd, block=False))
application.add_handler(CallbackQueryHandler(handle_owners_pagination, pattern=r"^owners_", block=False))
application.add_handler(CallbackQueryHandler(handle_back_to_card, pattern=r"^back_", block=False))

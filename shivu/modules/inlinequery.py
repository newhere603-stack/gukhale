import asyncio
import re
import hashlib
import logging
from html import escape
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from cachetools import TTLCache
from pymongo import ASCENDING, DESCENDING

from telegram import (
    Update, InlineQueryResultPhoto, InlineQueryResultVideo,
    InlineQueryResultCachedPhoto, InlineQueryResultCachedVideo,
    InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQueryResultArticle, InputTextMessageContent,
)
from telegram.ext import (
    InlineQueryHandler, CallbackQueryHandler, ChosenInlineResultHandler,
)
from telegram.constants import ParseMode

from shivu import application, db

LOGGER = logging.getLogger(__name__)

collection = db['anime_characters_lol']
user_collection = db['user_collection_lmaoooo']

# =========================================================
# Rarity System
# =========================================================
@dataclass
class Rarity:
    emoji: str
    premium: str
    name: str
    value: int

RARITIES = {
    "mythic":    ("💎", '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>', "Mythic", 1),
    "cosmic":    ("🌌", '<tg-emoji emoji-id="5431783411981228752">🌌</tg-emoji>', "Video Edition", 2),
    "celestial": ("🪽", '<tg-emoji emoji-id="5434121252874756456">🪽</tg-emoji>', "Celestial", 3),
    "exclusive": ("💮", '<tg-emoji emoji-id="6100567406889935797">💮</tg-emoji>', "Exclusive", 4),
    "legendary": ("🟡", '<tg-emoji emoji-id="6084550327086883643">🟡</tg-emoji>', "Legendary", 5),
    "premium":   ("🔮", '<tg-emoji emoji-id="6093919703753831564">🔮</tg-emoji>', "Premium Edition", 6),
    "neon":      ("⚡", '<tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>', "Neon", 7),
    "summer":    ("🏖️", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer", 8),
    "sweet":     ("🍭", '<tg-emoji emoji-id="6222115531122546353">🍭</tg-emoji>', "Sweet", 9),
    "special":   ("🔴", '<tg-emoji emoji-id="6093741664474504699">🔴</tg-emoji>', "Medium", 10),
    "valentine": ("💞", '<tg-emoji emoji-id="5255861796350224063">💞</tg-emoji>', "Valentine", 11),
    "winter":    ("❄️", '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>', "Winter", 12),
    "erotic":    ("🥵", '<tg-emoji emoji-id="6093490292923574796">🥵</tg-emoji>', "Spicy", 13),
    "rare":      ("🟠", '<tg-emoji emoji-id="5339390195768774311">🟠</tg-emoji>', "Rare", 14),
    "common":    ("🟢", '<tg-emoji emoji-id="6093865707424980866">🟢</tg-emoji>', "Common", 15),
}

RARITY_ALIASES = {
    "cosmic": "cosmic", "video": "cosmic", "video edition": "cosmic",
    "videoedition": "cosmic", "video editing": "cosmic", "videoediting": "cosmic",
    "video edit": "cosmic", "videoedit": "cosmic", "video edits": "cosmic",
    "videoedits": "cosmic",
}

def get_base_rarity(rarity_str: str) -> str:
    if not rarity_str or not isinstance(rarity_str, str):
        return "common"
    r_lower = rarity_str.lower().strip()
    alias = RARITY_ALIASES.get(r_lower)
    if alias: return alias
    for key, (_, _, name, _) in RARITIES.items():
        if key == r_lower or name.lower() == r_lower: return key
    for key, (db_emoji, _, name, _) in RARITIES.items():
        if key in r_lower or name.lower() in r_lower or db_emoji in r_lower: return key
    return "common"

# =========================================================
# DB Indexes (Optimized for Fast Search)
# =========================================================
try:
    collection.create_index([('id', ASCENDING)], unique=True, background=True)
    # Text index for blazing fast name/anime searches
    collection.create_index([('name', 'text'), ('anime', 'text')], background=True)
    user_collection.create_index([('id', ASCENDING)], unique=True, background=True)
except Exception as e:
    LOGGER.warning(f"Index creation warning: {e}")

# =========================================================
# Caches (Only for frequent/small queries, NOT whole DB)
# =========================================================
user_cache     = TTLCache(maxsize=10000, ttl=300)
count_cache    = TTLCache(maxsize=10000, ttl=180)
feedback_cache = TTLCache(maxsize=5000,  ttl=4800)
wishlist_cache = TTLCache(maxsize=5000,  ttl=2400)
result_id_map  = TTLCache(maxsize=10000, ttl=1800)

CAPS = str.maketrans('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
                     'ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ')

def sc(t: str) -> str:
    return t.translate(CAPS)

def parse_rar(r: str) -> Rarity:
    base_key = get_base_rarity(r)
    db_emoji, premium_emoji, name, val = RARITIES[base_key]
    return Rarity(db_emoji, premium_emoji, sc(name), val)

def trunc(t: str, l: int = 22) -> str:
    return t[:l - 2] + '..' if len(t) > l else t

def _id_key(cid) -> str:
    return str(cid).strip() if cid is not None else ''

# =========================================================
# Media Detection
# =========================================================
_IMG_FIELDS = ('img_url', 'image_url', 'img', 'photo', 'photo_url', 'file_id', 'url')
_VIDEO_EXTS = ('.mp4', '.mov', '.webm', '.mkv', '.m4v')

def _extract_media(v) -> Tuple[str, str]:
    if isinstance(v, str):
        v = v.strip()
        if v.startswith(('http://', 'https://')): return v, 'url'
        if len(v) >= 20 and not any(c.isspace() for c in v): return v, 'file_id'
    elif isinstance(v, list) and v:
        return _extract_media(v[0])
    return "", ""

def _media_of(ch: Dict) -> Tuple[str, str]:
    if not isinstance(ch, dict): return "", ""
    for k in _IMG_FIELDS:
        if v := ch.get(k):
            r, kind = _extract_media(v)
            if r: return r, kind
    return "", ""

def _is_video(ch: Dict, media: str, kind: str) -> bool:
    if not media: return False
    if ch.get('is_video') or ch.get('type') == 'video': return True
    if kind == 'url' and media.lower().split('?')[0].endswith(_VIDEO_EXTS): return True
    if kind == 'file_id' and media.startswith(('BAAC', 'CgAC')): return True
    return False

def _rarity_sort_key(c: Dict):
    return (parse_rar(c.get('rarity', '')).value, _id_key(c.get('id')))

# =========================================================
# Database Queries (DIRECT TO DB, NO RAM BLOAT)
# =========================================================
async def get_user(uid: int) -> dict:
    k = f"u{uid}"
    if k in user_cache: return user_cache[k]
    u = await user_collection.find_one({'id': uid}, {'_id': 0})
    if u: user_cache[k] = u
    return u or {}

async def _db_fetch_by_id(cid) -> Optional[Dict]:
    for val in (cid, int(cid) if str(cid).isdigit() else None, str(cid)):
        if val is not None and (doc := await collection.find_one({'id': val})):
            return doc
    return None

async def build_mongo_query(q: str, fm: str, uid: int) -> dict:
    match = {}
    conds = []
    
    # Text / Search Query
    if q:
        if q.isdigit():
            conds.extend([{'id': q}, {'id': int(q)}])
        
        rx = re.compile(re.escape(q), re.IGNORECASE)
        conds.extend([{'name': rx}, {'anime': rx}])
        
        alias = RARITY_ALIASES.get(q.lower())
        if alias and alias in RARITIES:
            conds.append({'rarity': re.compile(re.escape(alias), re.IGNORECASE)})
            conds.append({'rarity': re.compile(re.escape(RARITIES[alias][2]), re.IGNORECASE)})
            
        match['$or'] = conds

    # Filters applied directly in DB (Lightning Fast)
    if fm == 'rare':
        rare_names = [re.compile(r[2], re.IGNORECASE) for r in RARITIES.values() if r[3] <= 9]
        rare_keys = [re.compile(k, re.IGNORECASE) for k, r in RARITIES.items() if r[3] <= 9]
        match['rarity'] = {'$in': rare_names + rare_keys}
    
    elif fm in ('owned', 'notowned'):
        usr = await get_user(uid)
        owned = [c.get('id') for c in usr.get('characters', []) if isinstance(c, dict) and c.get('id')]
        match['id'] = {'$in': owned} if fm == 'owned' else {'$nin': owned}
        
    elif fm == 'wishlist':
        wl = wishlist_cache.get(f'wl_{uid}', set())
        match['id'] = {'$in': list(wl)}
        
    elif fm == 'video':
        match['$or'] = match.get('$or', []) + [{'is_video': True}, {'type': 'video'}, {'rarity': re.compile('cosmic', re.IGNORECASE)}]

    return match

# =========================================================
# Captions & Keyboards
# =========================================================
def minimal_caption(ch: Dict, fav: bool = False, uid: int = None) -> str:
    cid, nm, an = escape(str(ch.get('id', '??'))), escape(sc(str(ch.get('name', '?')))), escape(sc(str(ch.get('anime', '?'))))
    r = parse_rar(ch.get('rarity', ''))
    return f"<b>{sc('Character Info ')}✨</b>\n\n<b>{an}</b>\n<b>{cid}: {nm}</b>\n({r.premium} <b>{sc('RARITY:')}</b> {r.name})"

def create_kbd(cid: str, uid: int = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(sc("♔ owners"), callback_data=f"o.{cid}:0"),
             InlineKeyboardButton(sc("stats ⑆"), callback_data=f"s.{cid}")]]
    if len(str(cid)) <= 200 and not any(c.isspace() for c in str(cid)):
        rows.append([InlineKeyboardButton(sc("⤿ inline"), switch_inline_query_current_chat=str(cid))])
    return InlineKeyboardMarkup(rows)

# =========================================================
# The Core Inline Engine (Pagination + Instant Speed)
# =========================================================
async def _build_results(query, off: int, uid: int, qid: str):
    q = query.query.strip()
    limit = 50 
    results = []
    
    is_coll = q.startswith('collection.')
    fm = None
    sq = q
    
    # Extract Filter
    if is_coll:
        parts = q.split(' ', 1)
        sq = parts[1].strip() if len(parts) > 1 else ''
        tid = parts[0].split('.', 1)[1]
    
    for m in ('rare', 'video', 'new', 'trending', 'owned', 'notowned', 'wishlist'):
        if f"-{m}" in sq:
            fm = m
            sq = sq.replace(f"-{m}", "").strip()
            break

    # Extract Anime filter
    anime_filter = None
    if not is_coll:
        am = re.search(r'-anime:(\S+)', sq)
        if am:
            anime_filter = am.group(1).lower()
            sq = sq.replace(am.group(0), '').strip()

    all_chars = []
    fav_id = None
    
    # --- ROUTE 1: User Collection Search ---
    if is_coll and tid.isdigit():
        tuid = int(tid)
        usr = await get_user(tuid)
        if not usr:
            return [InlineQueryResultArticle(
                id=hashlib.md5(f"nouser{qid}".encode()).hexdigest(),
                title=sc("no collection"), description=sc("start your journey"),
                input_message_content=InputTextMessageContent(f"<b>🧩 {sc('start collecting!')}</b>", parse_mode=ParseMode.HTML)
            )], ""
            
        fav = usr.get('favorites')
        fav_id = _id_key(fav.get('id') if isinstance(fav, dict) else fav)
        
        # Unique chars only
        cd = {_id_key(c.get('id')): c for c in usr.get('characters', []) if isinstance(c, dict) and c.get('id')}
        all_chars = list(cd.values())
        
        # Python filters for User Collection (since lists are small)
        if sq:
            ql = sq.lower()
            all_chars = [c for c in all_chars if ql in str(c.get('name', '')).lower() or ql in str(c.get('anime', '')).lower() or ql == str(c.get('id'))]
        
        if fm == 'rare': all_chars = [c for c in all_chars if parse_rar(c.get('rarity', '')).value <= 9]
        elif fm == 'video': all_chars = [c for c in all_chars if _is_video(c, *_media_of(c)) or parse_rar(c.get('rarity')).value == 2]

        all_chars.sort(key=_rarity_sort_key)
        
        # Put Fav first
        if fav_id and not sq and not fm:
            fc = next((c for c in all_chars if _id_key(c.get('id')) == fav_id), None)
            if fc:
                all_chars = [c for c in all_chars if _id_key(c.get('id')) != fav_id]
                all_chars.insert(0, fc)

        page_chars = all_chars[off:off + limit]
        has_more = len(all_chars) > off + limit
        
    # --- ROUTE 2: Global Database Search (SUPER FAST) ---
    else:
        db_query = await build_mongo_query(sq, fm, uid)
        if anime_filter:
            db_query['anime'] = re.compile(re.escape(anime_filter), re.IGNORECASE)

        cursor = collection.find(db_query)
        
        # Sorting
        if fm == 'new':
            cursor = cursor.sort('_id', DESCENDING)
        elif not sq and not fm:
            # Default sorting to avoid lag on empty query
            cursor = cursor.sort('_id', DESCENDING)
            
        # Fetch only what's needed for this page! (Limit + 1 to check if next page exists)
        page_chars = await cursor.skip(off).limit(limit + 1).to_list(length=limit + 1)
        has_more = len(page_chars) > limit
        if has_more: page_chars = page_chars[:limit]

    noff = str(off + limit) if has_more else ""

    # --- Build Results Layout ---
    for i, ch in enumerate(page_chars):
        try:
            cid = ch.get('id')
            if not cid: continue
            
            media, kind = _media_of(ch)
            nm, an = str(ch.get('name', '?')), str(ch.get('anime', '?'))
            r = parse_rar(ch.get('rarity', ''))
            is_fav = (_id_key(cid) == fav_id) if fav_id else False
            
            cap = minimal_caption(ch, is_fav, uid=uid)
            kbd = create_kbd(cid, uid)
            rid = hashlib.md5(f"{_id_key(cid)}|{off}|{i}|{qid}".encode()).hexdigest()
            result_id_map[rid] = _id_key(cid)
            
            title = f"{'💖 ' if is_fav else ''}{r.emoji} {trunc(nm, 28)}"
            desc = f"{r.name} • {trunc(an, 20)}"
            
            if not media:
                results.append(InlineQueryResultArticle(id=rid, title=title, description=desc, input_message_content=InputTextMessageContent(cap, parse_mode=ParseMode.HTML), reply_markup=kbd))
                continue
                
            vid = _is_video(ch, media, kind)
            if kind == 'url':
                if vid: results.append(InlineQueryResultVideo(id=rid, video_url=media, mime_type="video/mp4", thumbnail_url=media, title=title, description=desc, caption=cap, parse_mode=ParseMode.HTML, reply_markup=kbd))
                else: results.append(InlineQueryResultPhoto(id=rid, photo_url=media, thumbnail_url=media, title=title, description=desc, caption=cap, parse_mode=ParseMode.HTML, reply_markup=kbd))
            elif kind == 'file_id':
                if vid: results.append(InlineQueryResultCachedVideo(id=rid, video_file_id=media, title=title, description=desc, caption=cap, parse_mode=ParseMode.HTML, reply_markup=kbd))
                else: results.append(InlineQueryResultCachedPhoto(id=rid, photo_file_id=media, title=title, description=desc, caption=cap, parse_mode=ParseMode.HTML, reply_markup=kbd))
        except Exception as e:
            continue

    return results, noff

async def inlinequery(update: Update, context) -> None:
    query = update.inline_query
    uid = query.from_user.id
    qid = query.id
    off = int(query.offset) if query.offset else 0

    try:
        # Fast query timeout check
        results, noff = await asyncio.wait_for(_build_results(query, off, uid, qid), timeout=4.0)
        
        if not results:
            results = [InlineQueryResultArticle(
                id=hashlib.md5(f"empty{qid}".encode()).hexdigest(),
                title=sc("no results"), description=sc("try another keyword"),
                input_message_content=InputTextMessageContent(f"<b>{sc('no characters found')}</b>", parse_mode=ParseMode.HTML)
            )]
            
        await query.answer(results, cache_time=3, is_personal=True, next_offset=noff)
    except Exception as e:
        LOGGER.exception(f"[INLINE ERROR]: {e}")
        try: await query.answer([], cache_time=1, is_personal=True)
        except: pass

async def chosen_inline_result(update: Update, context):
    try:
        rid = update.chosen_inline_result.result_id
        if cid := result_id_map.get(rid):
            feedback_cache[f'pick_{cid}'] = feedback_cache.get(f'pick_{cid}', 0) + 1
    except: pass

# =========================================================
# Missing Handlers (Owners / Stats) Note: Keep your old callback functions here if needed.
# =========================================================
# Main registration
application.add_handler(InlineQueryHandler(inlinequery))
application.add_handler(ChosenInlineResultHandler(chosen_inline_result, block=False))

# NOTE: Main Callbacks for Stats and Owners are omitted to keep code clean, 
# you can use your exact old ones for that since they weren't causing the issue.

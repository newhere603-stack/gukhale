import asyncio
import re
import time
import hashlib
import logging
from html import escape
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from cachetools import TTLCache
from pymongo import ASCENDING
from functools import lru_cache

from telegram import (
    Update, InlineQueryResultPhoto, InlineQueryResultVideo,
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
    if alias:
        return alias

    for key, (_, _, name, _) in RARITIES.items():
        if key == r_lower or name.lower() == r_lower:
            return key

    for key, (db_emoji, _, name, _) in RARITIES.items():
        if key in r_lower or name.lower() in r_lower or db_emoji in r_lower:
            return key

    return "common"


# =========================================================
# DB Indexes
# =========================================================
try:
    collection.create_index([('id', ASCENDING)], unique=True, background=True)
    collection.create_index([('rarity', ASCENDING), ('anime', ASCENDING)], background=True)
    user_collection.create_index([('id', ASCENDING)], unique=True, background=True)
    user_collection.create_index([('characters.id', ASCENDING)], background=True, sparse=True)
except Exception as e:
    LOGGER.warning(f"Index creation: {e}")


# =========================================================
# Caches
# =========================================================
char_cache     = TTLCache(maxsize=200000, ttl=600)
user_cache     = TTLCache(maxsize=100000, ttl=300)
query_cache    = TTLCache(maxsize=100000, ttl=300)
count_cache    = TTLCache(maxsize=80000,  ttl=180)
feedback_cache = TTLCache(maxsize=30000,  ttl=4800)
view_cache     = TTLCache(maxsize=8000,   ttl=900)
wishlist_cache = TTLCache(maxsize=8000,   ttl=2400)
result_id_map  = TTLCache(maxsize=50000,  ttl=1800)   # rid -> cid

CAPS = str.maketrans(
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
    'ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ',
)


@lru_cache(maxsize=65536)
def sc(t: str) -> str:
    return t.translate(CAPS)


@lru_cache(maxsize=32768)
def parse_rar(r: str) -> Rarity:
    base_key = get_base_rarity(r)
    db_emoji, premium_emoji, name, val = RARITIES[base_key]
    return Rarity(db_emoji, premium_emoji, sc(name), val)


def trunc(t: str, l: int = 22) -> str:
    return t[:l - 2] + '..' if len(t) > l else t


def cache_key(*args) -> str:
    return hashlib.md5(str(args).encode()).hexdigest()


# =========================================================
# URL / Media extraction  (*** MOST ROBUST ***)
# =========================================================
_IMG_FIELDS = (
    'img_url', 'image_url', 'img', 'photo', 'photo_url',
    'url', 'thumbnail', 'thumbnail_url', 'image', 'picture',
    'pic', 'link', 'media_url', 'file_url', 'video_url',
    'preview_url', 'src', 'href',
)
_NESTED_KEYS = ('url', 'src', 'link', 'href', 'image', 'img_url', 'image_url')


def _valid_url(u) -> bool:
    if not u or not isinstance(u, str):
        return False
    u = u.strip()
    return u.startswith('https://') or u.startswith('http://')


def _extract_url(v) -> str:
    """Extract a valid URL from any structure (str, list, dict)."""
    if _valid_url(v):
        return v.strip()

    if isinstance(v, list):
        for item in v:
            r = _extract_url(item)
            if r:
                return r
        return ""

    if isinstance(v, dict):
        for k in _NESTED_KEYS:
            r = _extract_url(v.get(k))
            if r:
                return r
        # last resort: any value in dict
        for vv in v.values():
            if _valid_url(vv):
                return vv.strip()
        return ""

    return ""


def _img_of(ch: Dict) -> str:
    """Find ANY usable image/video URL from a character document."""
    if not isinstance(ch, dict):
        return ""
    for k in _IMG_FIELDS:
        v = ch.get(k)
        if not v:
            continue
        r = _extract_url(v)
        if r:
            return r
    return ""


_VIDEO_EXTS = ('.mp4', '.mov', '.webm', '.mkv', '.m4v', '.gif')


def _is_video(ch: Dict, url: str) -> bool:
    if not url:
        return False
    ul = url.lower().split('?', 1)[0].split('#', 1)[0]
    if ul.endswith(_VIDEO_EXTS):
        return True
    return bool(ch.get('is_video', False)) and ul.endswith(('.mp4', '.mov', '.webm'))


# =========================================================
# In-memory char cache  (*** FETCH FULL DOCS — no projection ***)
# =========================================================
_ALL_CHARS: Optional[List[Dict]] = None
_ALL_CHARS_LOADED_AT: float = 0.0
_ALL_CHARS_LOCK = asyncio.Lock()
_ALL_CHARS_TTL = 900
_LOAD_TASK: Optional[asyncio.Task] = None


async def _load_all_chars() -> List[Dict]:
    global _ALL_CHARS, _ALL_CHARS_LOADED_AT
    async with _ALL_CHARS_LOCK:
        try:
            t0 = time.time()
            # *** NO PROJECTION — fetch everything, miss kuch nahi hoga ***
            chars = await collection.find({}).to_list(length=None)
            _ALL_CHARS = chars or []
            _ALL_CHARS_LOADED_AT = time.time()

            # diagnostics: count how many have usable images
            with_img = sum(1 for c in _ALL_CHARS if _img_of(c))
            LOGGER.info(
                f"[INLINE] Loaded {len(_ALL_CHARS)} chars "
                f"({with_img} with image) in {time.time()-t0:.2f}s"
            )
        except Exception as e:
            LOGGER.error(f"[INLINE] Cache load error: {e}")
            if _ALL_CHARS is None:
                _ALL_CHARS = []
        return _ALL_CHARS


def _schedule_load():
    global _LOAD_TASK
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if _LOAD_TASK is None or _LOAD_TASK.done():
        _LOAD_TASK = loop.create_task(_load_all_chars())


# =========================================================
# User / Owners
# =========================================================
async def get_user(uid: int) -> Optional[Dict]:
    k = f"u{uid}"
    cached = user_cache.get(k)
    if cached is not None:
        return cached
    try:
        u = await user_collection.find_one({'id': uid}, {'_id': 0})
    except Exception as e:
        LOGGER.error(f"get_user: {e}")
        return None
    if u:
        user_cache[k] = u
    return u


async def get_owners(cid: str, lim: int = 100) -> List[Dict]:
    k = f"o{cid}{lim}"
    cached = count_cache.get(k)
    if cached is not None:
        return cached
    try:
        pipe = [
            {'$match': {'characters.id': cid}},
            {'$project': {
                'id': 1, 'first_name': 1, 'username': 1,
                'characters': {'$filter': {
                    'input': '$characters', 'as': 'c',
                    'cond': {'$eq': ['$$c.id', cid]},
                }},
            }},
            {'$addFields': {'count': {'$size': '$characters'}}},
            {'$sort': {'count': -1}},
            {'$limit': lim},
            {'$project': {'characters': 0}},
        ]
        owners = await user_collection.aggregate(pipe).to_list(length=lim)
        count_cache[k] = owners
        return owners
    except Exception as e:
        LOGGER.error(f"get_owners: {e}")
        return []


# =========================================================
# Direct DB search fallback  (no projection = no miss)
# =========================================================
async def _db_search(q: str, lim: int = 200) -> List[Dict]:
    try:
        if not q:
            return await collection.find({}).limit(lim).to_list(lim)

        conds = []
        if q.isdigit():
            conds.append({'id': q})
            try:
                conds.append({'id': int(q)})
            except Exception:
                pass

        rx = re.compile(re.escape(q), re.IGNORECASE)
        conds.append({'name': rx})
        conds.append({'anime': rx})
        conds.append({'rarity': rx})

        alias = RARITY_ALIASES.get(q.lower().strip())
        if alias:
            conds.append({'rarity': re.compile(re.escape(alias), re.IGNORECASE)})
            conds.append({'rarity': re.compile(re.escape(RARITIES[alias][2]), re.IGNORECASE)})

        return await collection.find({'$or': conds}).limit(lim).to_list(lim)
    except Exception as e:
        LOGGER.error(f"_db_search: {e}")
        return []


# =========================================================
# Search (memory-first)
# =========================================================
async def search_chars(q: str, lim: int = 200) -> List[Dict]:
    k = cache_key('search', q, lim)
    cached = query_cache.get(k)
    if cached is not None:
        return cached

    all_chars = _ALL_CHARS

    # first-time: load synchronously so no "not found"
    if all_chars is None:
        try:
            await asyncio.wait_for(_load_all_chars(), timeout=8.0)
        except asyncio.TimeoutError:
            LOGGER.warning("[INLINE] Initial load timeout — DB fallback")
            chars = await _db_search(q, lim)
            query_cache[k] = chars
            return chars
        all_chars = _ALL_CHARS or []

    # stale: refresh in background, don't block
    elif (time.time() - _ALL_CHARS_LOADED_AT) > _ALL_CHARS_TTL:
        _schedule_load()

    if not q:
        result = all_chars[:lim]
        query_cache[k] = result
        return result

    ql = q.lower().strip()
    alias_key = RARITY_ALIASES.get(ql)
    is_digit = q.isdigit()
    qnum = int(q) if is_digit else None

    result = []
    for c in all_chars:
        cid = c.get('id')
        cid_str = str(cid) if cid is not None else ''
        matched = False

        if is_digit:
            # match id: try str and int
            if cid_str == q:
                matched = True
            else:
                try:
                    if int(cid_str) == qnum:
                        matched = True
                except Exception:
                    pass
        if not matched and cid_str == q:
            matched = True
        if not matched:
            if (ql in str(c.get('name', '')).lower()
                    or ql in str(c.get('anime', '')).lower()
                    or ql in str(c.get('rarity', '')).lower()):
                matched = True
            elif alias_key and get_base_rarity(c.get('rarity', '')) == alias_key:
                matched = True

        if matched:
            result.append(c)
            if len(result) >= lim:
                break

    query_cache[k] = result
    return result


async def filter_chars(chars: List[Dict], mode: str, uid: int = None) -> List[Dict]:
    if mode == 'rare':
        return [c for c in chars if parse_rar(c.get('rarity', '')).value <= 9]

    elif mode == 'video':
        out = []
        for c in chars:
            if c.get('is_video', False):
                out.append(c)
                continue
            if get_base_rarity(c.get('rarity', '')) == "cosmic":
                out.append(c)
        return out

    elif mode == 'new':
        return sorted(chars, key=lambda x: str(x.get('_id', '')), reverse=True)

    elif mode == 'trending':
        ids = [c.get('id') for c in chars if c.get('id')]
        if ids:
            picks = {cid: feedback_cache.get(f'pick_{cid}', 0)
                     for cid in ids
                     if feedback_cache.get(f'pick_{cid}', 0) > 0}
            return sorted(chars, key=lambda x: picks.get(x.get('id'), 0), reverse=True)

    elif mode == 'owned' and uid:
        usr = await get_user(uid)
        if usr:
            owned = {c.get('id') for c in usr.get('characters', [])
                     if isinstance(c, dict) and c.get('id')}
            return [c for c in chars if c.get('id') in owned]

    elif mode == 'notowned' and uid:
        usr = await get_user(uid)
        if usr:
            owned = {c.get('id') for c in usr.get('characters', [])
                     if isinstance(c, dict) and c.get('id')}
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


# =========================================================
# Captions
# =========================================================
def minimal_caption(ch: Dict, fav: bool = False, uid: int = None) -> str:
    cid = escape(str(ch.get('id', '??')))
    nm = escape(sc(str(ch.get('name', 'Unknown'))))
    an = escape(sc(str(ch.get('anime', 'Unknown'))))
    r = parse_rar(ch.get('rarity', ''))

    return (
        f"<b>{sc('Character Info ')}"
        f"<tg-emoji emoji-id=\"6093637923834438402\">✨</tg-emoji></b>\n\n"
        f"<b>{an}</b>\n"
        f"<b>{cid}: {nm}</b>\n"
        f"({r.premium} <b>{sc('RARITY:')}</b> {r.name})"
    )


def owners_caption(ch: Dict, owners: List[Dict], page: int) -> str:
    nm = escape(sc(str(ch.get('name', 'Unknown'))))
    total = sum(o.get('count', 0) for o in owners)
    cap = (
        f"<b>{nm}</b>\n\n"
        f"<b><tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> "
        f"{len(owners)} {sc('owners')} • {total}× {sc('grabbed')}</b>\n\n"
    )

    medals = {
        1: "<tg-emoji emoji-id=\"5440539497383087970\">🥇</tg-emoji>",
        2: "<tg-emoji emoji-id=\"5447203607294265305\">🥈</tg-emoji>",
        3: "<tg-emoji emoji-id=\"5453902265922376865\">🥉</tg-emoji>",
    }

    UPP = 10
    start = page * UPP
    end = start + UPP
    total_pages = max(1, (len(owners) + UPP - 1) // UPP)

    for i, o in enumerate(owners[start:end], start + 1):
        medal = medals.get(i, f"<b>{i}.</b>")
        fn = escape(trunc(str(o.get('first_name', 'User')), 18))
        uid = o.get('id')
        cap += (f"{medal} <a href=\"tg://user?id={uid}\">"
                f"<b>{fn}</b></a> • <code>×{o.get('count', 0)}</code>\n")

    cap += (f"\n<tg-emoji emoji-id=\"5197269100878907942\">✍️</tg-emoji> "
            f"<b>{sc(f'page {page+1}/{total_pages}')}</b>")
    return cap


def stats_caption(ch: Dict, owners: List[Dict]) -> str:
    nm = escape(sc(str(ch.get('name', 'Unknown'))))
    total = sum(o.get('count', 0) for o in owners)
    avg = round(total / len(owners), 1) if owners else 0

    cap = (
        f"<b>{nm}</b>\n\n"
        f"<tg-emoji emoji-id=\"5231200819986047254\">📊</tg-emoji> "
        f"<b>{sc('statistics')}</b>\n"
        f"<tg-emoji emoji-id=\"5310278924616356636\">🎯</tg-emoji> "
        f"<code>{total}×</code> {sc('grabbed')}\n"
        f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> "
        f"<code>{len(owners)}</code> {sc('owners')}\n"
        f"<tg-emoji emoji-id=\"5028746137645876535\">📈</tg-emoji> "
        f"<code>{avg}×</code> {sc('avg')}\n"
    )

    medals = {
        1: "<tg-emoji emoji-id=\"5440539497383087970\">🥇</tg-emoji>",
        2: "<tg-emoji emoji-id=\"5447203607294265305\">🥈</tg-emoji>",
        3: "<tg-emoji emoji-id=\"5453902265922376865\">🥉</tg-emoji>",
    }

    if owners:
        cap += (f"\n<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> "
                f"<b>{sc('top collectors')}</b>\n")
        for i, o in enumerate(owners[:3], 1):
            fn = escape(trunc(str(o.get('first_name', 'User')), 18))
            uid = o.get('id')
            medal = medals.get(i, f"<b>{i}.</b>")
            cap += (f"{medal} <a href=\"tg://user?id={uid}\">"
                    f"<b>{fn}</b></a> • <code>×{o.get('count', 0)}</code>\n")
    return cap


def create_kbd(cid: str, uid: int = None) -> InlineKeyboardMarkup:
    cid = str(cid)
    rows = [
        [
            InlineKeyboardButton(sc("♔ owners"), callback_data=f"o.{cid}:0"),
            InlineKeyboardButton(sc("stats ⑆"), callback_data=f"s.{cid}"),
        ],
    ]
    if cid and len(cid) <= 200 and not any(ch.isspace() for ch in cid):
        rows.append([
            InlineKeyboardButton(sc("⤿ inline"),
                                 switch_inline_query_current_chat=cid),
        ])
    return InlineKeyboardMarkup(rows)


# =========================================================
# Inline Query
# =========================================================
async def _build_results(query, off: int, uid: int, qid: str):
    q = query.query or ""
    results = []
    noff = ""

    is_coll = False
    usr = None
    sq = q
    fm = None

    if q.startswith('collection.'):
        is_coll = True
        parts = q.split(' ', 1)
        tid = parts[0].split('.', 1)[1]
        sq = parts[1].strip() if len(parts) > 1 else ''

        for m in ('rare', 'video', 'new', 'trending',
                  'owned', 'notowned', 'wishlist'):
            if sq.startswith(f'-{m}'):
                fm = m
                sq = sq.replace(f'-{m}', '').strip()
                break

        if not tid.isdigit():
            return [], ""

        tuid = int(tid)
        usr = await get_user(tuid)
        if not usr:
            article = InlineQueryResultArticle(
                id=hashlib.md5(f"nouser{qid}".encode()).hexdigest(),
                title=sc("no collection"),
                description=sc("start your journey"),
                input_message_content=InputTextMessageContent(
                    f"<b><tg-emoji emoji-id=\"5265120027853481187\">🧩</tg-emoji> "
                    f"{sc('start collecting!')}</b>",
                    parse_mode=ParseMode.HTML,
                ),
            )
            return [article], ""

        cd = {c['id']: c for c in usr.get('characters', [])
              if isinstance(c, dict) and c.get('id')}
        all_chars = list(cd.values())

        if sq:
            sql = sq.lower().strip()
            alias_key = RARITY_ALIASES.get(sql)
            is_digit = sq.isdigit()
            qnum = int(sq) if is_digit else None

            filtered = []
            for c in all_chars:
                cid_str = str(c.get('id', ''))
                matched = False
                if is_digit and cid_str.isdigit() and int(cid_str) == qnum:
                    matched = True
                elif cid_str == sq:
                    matched = True
                else:
                    if (sql in str(c.get('name', '')).lower()
                            or sql in str(c.get('anime', '')).lower()
                            or sql in str(c.get('rarity', '')).lower()):
                        matched = True
                    elif alias_key and get_base_rarity(c.get('rarity', '')) == alias_key:
                        matched = True
                if matched:
                    filtered.append(c)
            all_chars = filtered

        if fm:
            all_chars = await filter_chars(all_chars, fm, tuid)

        fav = usr.get('favorites')
        if fav and not sq and not fm:
            fid = fav.get('id') if isinstance(fav, dict) else fav
            fc = next((c for c in all_chars if c.get('id') == fid), None)
            if fc:
                all_chars = [c for c in all_chars if c.get('id') != fid]
                all_chars.insert(0, fc)

        if not fm or fm not in ('new', 'trending'):
            all_chars.sort(key=lambda x: parse_rar(x.get('rarity', '')).value)

    else:
        for m in ('rare', 'video', 'new', 'trending',
                  'owned', 'notowned', 'wishlist'):
            if sq.startswith(f'-{m}'):
                fm = m
                sq = sq.replace(f'-{m}', '').strip()
                break

        am = re.search(r'-anime:(\S+)', sq)
        if am:
            anime_filter = am.group(1).lower()
            sq = sq.replace(am.group(0), '').strip()
            all_chars = await search_chars(sq, lim=500)
            all_chars = [c for c in all_chars
                         if anime_filter in str(c.get('anime', '')).lower()]
        else:
            all_chars = await search_chars(sq, lim=500)

        if fm:
            all_chars = await filter_chars(all_chars, fm, uid)

        if not fm or fm not in ('new', 'trending'):
            all_chars.sort(key=lambda x: parse_rar(x.get('rarity', '')).value)

    all_chars = dedupe(all_chars)
    page_chars = all_chars[off:off + 50]
    has_more = len(all_chars) > off + 50
    noff = str(off + 50) if has_more else ""

    fav_id = None
    if is_coll and usr:
        fv = usr.get('favorites')
        fav_id = fv.get('id') if isinstance(fv, dict) else fv

    for i, ch in enumerate(page_chars):
        try:
            cid = ch.get('id')
            if cid is None:
                continue

            img = _img_of(ch)
            if not img:
                LOGGER.warning(
                    f"[INLINE] skip cid={cid} no image. keys={list(ch.keys())[:20]}"
                )
                continue

            vid = _is_video(ch, img)
            nm = str(ch.get('name', '?'))
            an = str(ch.get('anime', '?'))
            r = parse_rar(ch.get('rarity', ''))
            fav = (fav_id == cid)

            cap = minimal_caption(ch, fav, uid=uid)
            kbd = create_kbd(cid, uid)

            rid = hashlib.md5(f"{cid}|{off}|{i}|{qid}".encode()).hexdigest()
            result_id_map[rid] = str(cid)

            title = f"{'💖 ' if fav else ''}{r.emoji} {trunc(nm, 28)}"
            desc = f"{r.name} • {trunc(an, 20)}"

            if vid:
                results.append(InlineQueryResultVideo(
                    id=rid, video_url=img, mime_type="video/mp4",
                    thumbnail_url=img, title=title, description=desc,
                    caption=cap, parse_mode=ParseMode.HTML,
                    reply_markup=kbd,
                ))
            else:
                results.append(InlineQueryResultPhoto(
                    id=rid, photo_url=img, thumbnail_url=img,
                    title=title, description=desc,
                    caption=cap, parse_mode=ParseMode.HTML,
                    reply_markup=kbd,
                ))
        except Exception as e:
            LOGGER.error(f"[INLINE] result build: {e}")
            continue

    return results, noff


async def inlinequery(update: Update, context) -> None:
    query = update.inline_query
    qid = query.id
    uid = query.from_user.id
    off = int(query.offset) if query.offset else 0

    results = []
    noff = ""

    try:
        try:
            results, noff = await asyncio.wait_for(
                _build_results(query, off, uid, qid), timeout=8.0,
            )
        except asyncio.TimeoutError:
            LOGGER.warning("[INLINE] build timeout — answering empty")
            results, noff = [], ""
        except Exception as e:
            LOGGER.exception(f"[INLINE] build error: {e}")
            results, noff = [], ""

        if not results:
            results = [InlineQueryResultArticle(
                id=hashlib.md5(f"empty{qid}".encode()).hexdigest(),
                title=sc("no results"),
                description=sc("try another keyword"),
                input_message_content=InputTextMessageContent(
                    f"<b>{sc('no characters found')}</b>",
                    parse_mode=ParseMode.HTML,
                ),
            )]

        kwargs = {
            'cache_time': 3,
            'is_personal': True,
        }
        if noff:
            kwargs['next_offset'] = noff

        await query.answer(results, **kwargs)

    except Exception as e:
        LOGGER.exception(f"[INLINE] answer failed: {e}")
        try:
            await query.answer([], cache_time=1, is_personal=True)
        except Exception:
            pass


async def chosen_inline_result(update: Update, context) -> None:
    try:
        result = update.chosen_inline_result
        rid = result.result_id
        cid = result_id_map.get(rid)
        if cid:
            fk = f'pick_{cid}'
            feedback_cache[fk] = feedback_cache.get(fk, 0) + 1
        qk = f'query_{result.from_user.id}'
        feedback_cache[qk] = result.query
    except Exception as e:
        LOGGER.error(f"chosen_inline_result: {e}")


# =========================================================
# Callbacks
# =========================================================
async def show_owners(update: Update, context) -> None:
    q = update.callback_query
    try:
        data = q.data.split('.', 1)[1]
        if ':' in data:
            cid, page_str = data.split(':', 1)
            page = int(page_str)
        else:
            cid = data
            page = 0

        ch = await collection.find_one({'id': cid})
        if not ch:
            try:
                if cid.isdigit():
                    ch = await collection.find_one({'id': int(cid)})
            except Exception:
                pass
        if not ch:
            await q.answer(sc("not found"), show_alert=True)
            return

        owners = await get_owners(cid, 100)
        if not owners:
            await q.answer(sc("no owners"), show_alert=True)
            return

        await q.answer()

        cap = owners_caption(ch, owners, page)
        UPP = 10
        total_pages = max(1, (len(owners) + UPP - 1) // UPP)

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(sc("⋞ prev"),
                                            callback_data=f"o.{cid}:{page-1}"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(sc("next ⋟"),
                                            callback_data=f"o.{cid}:{page+1}"))

        layout = []
        if nav:
            layout.append(nav)
        layout.append([
            InlineKeyboardButton(sc("⟲ back"), callback_data=f"b.{cid}"),
            InlineKeyboardButton(sc("stats ⑆"), callback_data=f"s.{cid}"),
        ])
        if cid and len(str(cid)) <= 200 and not any(ch.isspace() for ch in str(cid)):
            layout.append([
                InlineKeyboardButton(sc("⤿ inline"),
                                     switch_inline_query_current_chat=str(cid)),
            ])

        kbd = InlineKeyboardMarkup(layout)
        await q.edit_message_caption(
            caption=cap, parse_mode=ParseMode.HTML, reply_markup=kbd)
    except Exception as e:
        LOGGER.error(f"show_owners: {e}")
        try:
            await q.answer(sc("error"), show_alert=True)
        except Exception:
            pass


async def back_card(update: Update, context) -> None:
    q = update.callback_query
    try:
        cid = q.data.split('.', 1)[1]
        ch = await collection.find_one({'id': cid})
        if not ch:
            try:
                if cid.isdigit():
                    ch = await collection.find_one({'id': int(cid)})
            except Exception:
                pass
        if not ch:
            await q.answer(sc("not found"), show_alert=True)
            return

        await q.answer()
        uid = q.from_user.id
        cap = minimal_caption(ch, uid=uid)
        kbd = create_kbd(cid, uid)
        await q.edit_message_caption(
            caption=cap, parse_mode=ParseMode.HTML, reply_markup=kbd)
    except Exception as e:
        LOGGER.error(f"back_card: {e}")
        try:
            await q.answer(sc("error"), show_alert=True)
        except Exception:
            pass


async def show_stats(update: Update, context) -> None:
    q = update.callback_query
    try:
        cid = q.data.split('.', 1)[1]
        ch = await collection.find_one({'id': cid})
        if not ch:
            try:
                if cid.isdigit():
                    ch = await collection.find_one({'id': int(cid)})
            except Exception:
                pass
        if not ch:
            await q.answer(sc("not found"), show_alert=True)
            return

        owners = await get_owners(cid, 100)
        await q.answer()

        cap = stats_caption(ch, owners)
        layout = [[
            InlineKeyboardButton(sc("⟲ back"), callback_data=f"b.{cid}"),
            InlineKeyboardButton(sc("owners ♔"), callback_data=f"o.{cid}:0"),
        ]]
        if cid and len(str(cid)) <= 200 and not any(ch.isspace() for ch in str(cid)):
            layout.append([
                InlineKeyboardButton(sc("⤿ inline"),
                                     switch_inline_query_current_chat=str(cid)),
            ])

        kbd = InlineKeyboardMarkup(layout)
        await q.edit_message_caption(
            caption=cap, parse_mode=ParseMode.HTML, reply_markup=kbd)
    except Exception as e:
        LOGGER.error(f"show_stats: {e}")
        try:
            await q.answer(sc("error"), show_alert=True)
        except Exception:
            pass


# =========================================================
# Handler registration
# =========================================================
application.add_handler(InlineQueryHandler(inlinequery))
application.add_handler(ChosenInlineResultHandler(chosen_inline_result, block=False))
application.add_handler(CallbackQueryHandler(show_owners, pattern=r'^o\.', block=False))
application.add_handler(CallbackQueryHandler(back_card, pattern=r'^b\.', block=False))
application.add_handler(CallbackQueryHandler(show_stats, pattern=r'^s\.', block=False))


# =========================================================
# Background warm-up
# =========================================================
def _bootstrap_preload():
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_load_all_chars())
    except RuntimeError:
        pass


try:
    _bootstrap_preload()
except Exception:
    pass

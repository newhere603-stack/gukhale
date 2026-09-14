import asyncio
import re
import time
import hashlib
import logging
from html import escape
from typing import List, Dict, Optional, Tuple
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
user_cache     = TTLCache(maxsize=100000, ttl=300)
count_cache    = TTLCache(maxsize=80000,  ttl=180)
feedback_cache = TTLCache(maxsize=30000,  ttl=4800)
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
# URL / Media validation
# =========================================================
_IMG_FIELDS = ('img_url', 'image_url', 'img', 'photo', 'photo_url', 'url', 'thumbnail')

_CHAR_PROJECTION = {
    '_id': 1, 'id': 1, 'name': 1, 'anime': 1,
    'rarity': 1, 'img_url': 1, 'is_video': 1,
    'image_url': 1, 'img': 1, 'photo': 1,
    'photo_url': 1, 'url': 1, 'thumbnail': 1,
}


def _valid_url(u) -> bool:
    if not u or not isinstance(u, str):
        return False
    u = u.strip()
    return u.startswith('https://') or u.startswith('http://')


def _img_of(ch: Dict) -> str:
    if not isinstance(ch, dict):
        return ""
    for k in _IMG_FIELDS:
        v = ch.get(k)
        if _valid_url(v):
            return v.strip()
        if isinstance(v, list) and v:
            for item in v:
                if _valid_url(item):
                    return item.strip()
    return ""


_VIDEO_EXTS = ('.mp4', '.mov', '.webm', '.mkv', '.m4v')


def _is_video(ch: Dict, url: str) -> bool:
    if not url:
        return False
    ul = url.lower().split('?', 1)[0].split('#', 1)[0]
    if ul.endswith(_VIDEO_EXTS):
        return True
    return bool(ch.get('is_video', False)) and ul.endswith(_VIDEO_EXTS)


# =========================================================
# Global in-memory character store (superfast lookups)
# =========================================================
_ALL_CHARS: List[Dict] = []
_ALL_CHARS_TS: float = 0.0
_ALL_CHARS_LOCK = asyncio.Lock()
_ALL_CHARS_TTL = 300
_READY = asyncio.Event()
_REFRESH_TASK: Optional[asyncio.Task] = None


def _prep_char(c: Dict) -> Optional[Dict]:
    """Pre-process a raw Mongo doc into a lean search-optimized dict."""
    if not isinstance(c, dict):
        return None
    cid = c.get('id')
    if not cid:
        return None
    img = _img_of(c)
    if not img:
        return None

    name = str(c.get('name', ''))
    anime = str(c.get('anime', ''))
    rarity = str(c.get('rarity', ''))
    cid_str = str(cid)

    return {
        'id': cid,
        'name': name,
        'anime': anime,
        'rarity': rarity,
        '_nl': name.lower(),
        '_al': anime.lower(),
        '_rl': rarity.lower(),
        '_num': int(cid_str) if cid_str.isdigit() else None,
        '_base': get_base_rarity(rarity),
        '_img': img,
        '_vid': _is_video(c, img),
        '_rv': parse_rar(rarity).value,
        '_sid': c.get('_id'),
    }


async def _load_all_chars() -> None:
    """Load & prepare entire character database into memory. Non-blocking swap."""
    global _ALL_CHARS, _ALL_CHARS_TS
    async with _ALL_CHARS_LOCK:
        try:
            t0 = time.time()
            raw = await collection.find({}, _CHAR_PROJECTION).to_list(length=None)
            seen = set()
            prepped: List[Dict] = []
            for c in raw:
                cid = c.get('id')
                if cid is None or cid in seen:
                    continue
                p = _prep_char(c)
                if p is not None:
                    seen.add(cid)
                    prepped.append(p)
            # Atomic swap
            _ALL_CHARS = prepped
            _ALL_CHARS_TS = time.time()
            LOGGER.info(
                f"[INLINE] Loaded {len(prepped)} characters "
                f"in {time.time()-t0:.2f}s"
            )
        except Exception as e:
            LOGGER.error(f"[INLINE] Cache load error: {e}")
        finally:
            _READY.set()


async def _refresh_loop():
    """Background periodic refresh so cache never goes stale."""
    while True:
        try:
            await asyncio.sleep(_ALL_CHARS_TTL)
            await _load_all_chars()
        except asyncio.CancelledError:
            return
        except Exception as e:
            LOGGER.error(f"[INLINE] refresh loop: {e}")


def _start_refresh_loop():
    global _REFRESH_TASK
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if _REFRESH_TASK is None or _REFRESH_TASK.done():
        _REFRESH_TASK = loop.create_task(_refresh_loop())


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
# Search (pure in-memory, millisecond)
# =========================================================
def search_chars(q: str, lim: int = 200) -> List[Dict]:
    chars = _ALL_CHARS
    if not chars:
        return []

    if not q:
        return chars[:lim]

    ql = q.lower().strip()
    alias_key = RARITY_ALIASES.get(ql)
    is_digit = q.isdigit()
    qnum = int(q) if is_digit else None

    result: List[Dict] = []
    for c in chars:
        if is_digit and c['_num'] == qnum:
            result.append(c)
        elif c['_nl'] == ql or c['_al'] == ql or c['_rl'] == ql:
            result.append(c)
        elif ql in c['_nl'] or ql in c['_al'] or ql in c['_rl']:
            result.append(c)
        elif alias_key and c['_base'] == alias_key:
            result.append(c)
        else:
            continue
        if len(result) >= lim:
            break
    return result


def filter_chars(chars: List[Dict], mode: str, uid: int = None) -> List[Dict]:
    if mode == 'rare':
        return [c for c in chars if c['_rv'] <= 9]

    if mode == 'video':
        return [c for c in chars if c['_vid'] or c['_base'] == 'cosmic']

    if mode == 'new':
        return sorted(chars, key=lambda x: x['_sid'] or 0, reverse=True)

    if mode == 'trending':
        picks = []
        for c in chars:
            n = feedback_cache.get(f"pick_{c['id']}", 0)
            if n > 0:
                picks.append((n, c))
        if picks:
            picks.sort(key=lambda x: x[0], reverse=True)
            return [c for _, c in picks]
        return chars

    return chars


async def filter_user(chars: List[Dict], mode: str, uid: int) -> List[Dict]:
    if mode in ('owned', 'notowned'):
        usr = await get_user(uid)
        if not usr:
            return []
        owned = {c.get('id') for c in usr.get('characters', [])
                 if isinstance(c, dict) and c.get('id')}
        if mode == 'owned':
            return [c for c in chars if c['id'] in owned]
        return [c for c in chars if c['id'] not in owned]

    if mode == 'wishlist':
        wl = wishlist_cache.get(f'wl_{uid}')
        if not wl:
            return []
        return [c for c in chars if c['id'] in wl]

    return chars


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
def _build_results_sync(q: str, off: int, uid: int) -> Tuple[List, str, List[str]]:
    """Pure in-memory result builder — must be fast."""
    results: List = []
    noff = ""
    char_ids: List[str] = []

    is_coll = False
    usr = None
    sq = q
    fm = None

    # ---- Parse command flags ----
    if q.startswith('collection.'):
        is_coll = True
        parts = q.split(' ', 1)
        tid = parts[0].split('.', 1)[1]
        sq = parts[1].strip() if len(parts) > 1 else ''
        if not tid.isdigit():
            return [], "", []
        # We'll resolve user later (async) — stash the parsed info
        _pending_coll_uid = int(tid)
    else:
        _pending_coll_uid = None

    for m in ('rare', 'video', 'new', 'trending',
              'owned', 'notowned', 'wishlist'):
        if sq.startswith(f'-{m}'):
            fm = m
            sq = sq.replace(f'-{m}', '', 1).strip()
            break

    # Handle inline -anime: filter
    anime_filter = None
    if not is_coll:
        am = re.search(r'-anime:(\S+)', sq)
        if am:
            anime_filter = am.group(1).lower()
            sq = sq.replace(am.group(0), '', 1).strip()

    return (is_coll, _pending_coll_uid, sq, fm, anime_filter), noff, char_ids


async def _build_results(query, off: int, uid: int, qid: str):
    q = query.query or ""
    results: List = []
    noff = ""

    is_coll = False
    usr = None
    sq = q
    fm = None
    anime_filter = None
    coll_uid = None

    # ---- Parse ----
    if q.startswith('collection.'):
        is_coll = True
        parts = q.split(' ', 1)
        tid = parts[0].split('.', 1)[1]
        sq = parts[1].strip() if len(parts) > 1 else ''
        if not tid.isdigit():
            return [], ""
        coll_uid = int(tid)

    for m in ('rare', 'video', 'new', 'trending',
              'owned', 'notowned', 'wishlist'):
        if sq.startswith(f'-{m}'):
            fm = m
            sq = sq.replace(f'-{m}', '', 1).strip()
            break

    if not is_coll:
        am = re.search(r'-anime:(\S+)', sq)
        if am:
            anime_filter = am.group(1).lower()
            sq = sq.replace(am.group(0), '', 1).strip()

    # ---- Fetch candidate list ----
    if is_coll:
        usr = await get_user(coll_uid)
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

        # Use the master _ALL_CHARS store for up-to-date info
        master = {c['id']: c for c in _ALL_CHARS}
        all_chars: List[Dict] = []
        for cid in cd.keys():
            m = master.get(cid)
            if m is not None:
                all_chars.append(m)
            else:
                # Fallback: build a minimal entry
                p = _prep_char(cd[cid])
                if p is not None:
                    all_chars.append(p)

        # Filter by search term
        if sq:
            sql = sq.lower().strip()
            alias_key = RARITY_ALIASES.get(sql)
            is_digit = sq.isdigit()
            qnum = int(sq) if is_digit else None
            filtered = []
            for c in all_chars:
                if is_digit and c['_num'] == qnum:
                    filtered.append(c)
                elif sql in c['_nl'] or sql in c['_al'] or sql in c['_rl']:
                    filtered.append(c)
                elif alias_key and c['_base'] == alias_key:
                    filtered.append(c)
            all_chars = filtered

        # Favorites pinned to top
        fav = usr.get('favorites')
        if fav and not sq and not fm:
            fid = fav.get('id') if isinstance(fav, dict) else fav
            fc = next((c for c in all_chars if c['id'] == fid), None)
            if fc is not None:
                all_chars = [c for c in all_chars if c['id'] != fid]
                all_chars.insert(0, fc)

        # User-scoped filters
        if fm in ('owned', 'notowned', 'wishlist'):
            all_chars = await filter_user(all_chars, fm, coll_uid)
        elif fm:
            all_chars = filter_chars(all_chars, fm, coll_uid)
        else:
            all_chars = sorted(all_chars, key=lambda x: x['_rv'])

    else:
        all_chars = search_chars(sq, lim=500)
        if anime_filter:
            all_chars = [c for c in all_chars if anime_filter in c['_al']]

        if fm in ('owned', 'notowned', 'wishlist'):
            all_chars = await filter_user(all_chars, fm, uid)
        elif fm:
            all_chars = filter_chars(all_chars, fm, uid)
        else:
            all_chars = sorted(all_chars, key=lambda x: x['_rv'])

    # Dedupe by id (paranoia — should already be unique)
    seen = set()
    deduped = []
    for c in all_chars:
        cid = c['id']
        if cid in seen:
            continue
        seen.add(cid)
        deduped.append(c)
    all_chars = deduped

    # ---- Paginate ----
    page_chars = all_chars[off:off + 50]
    has_more = len(all_chars) > off + 50
    noff = str(off + 50) if has_more else ""

    # ---- Favorites check for caption ----
    fav_id = None
    if is_coll and usr:
        fv = usr.get('favorites')
        fav_id = fv.get('id') if isinstance(fv, dict) else fv

    # ---- Build results ----
    for i, ch in enumerate(page_chars):
        try:
            cid = ch['id']
            img = ch['_img']
            vid = ch['_vid']
            nm = ch['name']
            an = ch['anime']
            r = parse_rar(ch['rarity'])
            fav = (fav_id == cid)

            cap = minimal_caption(ch, fav, uid=uid)
            kbd = create_kbd(cid, uid)

            rid = hashlib.md5(f"{cid}|{off}|{i}".encode()).hexdigest()
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
        # Wait briefly for cache to be ready on very first query
        if not _READY.is_set():
            try:
                await asyncio.wait_for(_READY.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pass

        try:
            results, noff = await asyncio.wait_for(
                _build_results(query, off, uid, qid), timeout=6.0,
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
            'cache_time': 5,
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

        ch = await collection.find_one({'id': cid}, _CHAR_PROJECTION)
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
        ch = await collection.find_one({'id': cid}, _CHAR_PROJECTION)
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
        ch = await collection.find_one({'id': cid}, _CHAR_PROJECTION)
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
# Background warm-up (non-blocking, at import)
# =========================================================
def _bootstrap_preload():
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_load_all_chars())
        _start_refresh_loop()
    except RuntimeError:
        pass


try:
    _bootstrap_preload()
except Exception:
    pass

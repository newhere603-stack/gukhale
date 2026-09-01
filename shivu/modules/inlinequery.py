import re
import time
import hashlib
import logging
from html import escape
from typing import List, Dict, Optional
from dataclasses import dataclass
from cachetools import TTLCache, LRUCache
from pymongo import ASCENDING, TEXT
from functools import lru_cache

from telegram import Update, InlineQueryResultPhoto, InlineQueryResultVideo, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import InlineQueryHandler, CallbackQueryHandler, ChosenInlineResultHandler
from telegram.constants import ParseMode

from shivu import application, db

LOGGER = logging.getLogger(__name__)

collection = db['anime_characters_lol']
user_collection = db['user_collection_lmaoooo']

# 🔥 Rarity Dataclass updated to support both normal and premium emojis
@dataclass
class Rarity:
    emoji: str
    premium: str
    name: str
    value: int

# 🔥 UNIFIED RARITY DICTIONARY WITH PREMIUM EMOJIS & SORTING VALUES
RARITIES = {
    "mythic": ("💎", '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>', "Mythic", 1),
    "cosmic": ("🌌", '<tg-emoji emoji-id="5431783411981228752">🎆</tg-emoji>', "Cosmic", 2),
    "celestial": ("🪽", '<tg-emoji emoji-id="5434121252874756456">🕊</tg-emoji>', "Celestial", 3),
    "exclusive": ("💮", '<tg-emoji emoji-id="6100567406889935797">💮</tg-emoji>', "Exclusive", 4),
    "legendary": ("🟡", '<tg-emoji emoji-id="6084550327086883643">🔥</tg-emoji>', "Legendary", 5),
    "premium": ("🔮", '<tg-emoji emoji-id="6093919703753831564">🔮</tg-emoji>', "Premium Edition", 6),
    "neon": ("⚡", '<tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>', "Neon", 7),
    "summer": ("🏖️", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer", 8),
    "sweet": ("🍭", '<tg-emoji emoji-id="6222115531122546353">🍭</tg-emoji>', "Sweet", 9),
    "special": ("🔴", '<tg-emoji emoji-id="6093741664474504699">🔴</tg-emoji>', "Medium", 10),
    "valentine": ("💞", '<tg-emoji emoji-id="5255861796350224063">❤️</tg-emoji>', "Valentine", 11),
    "winter": ("❄️", '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>', "Winter", 12),
    "erotic": ("🥵", '<tg-emoji emoji-id="6093490292923574796">❤️‍🔥</tg-emoji>', "Spicy", 13),
    "rare": ("🟠", '<tg-emoji emoji-id="5339390195768774311">🟠</tg-emoji>', "Rare", 14),
    "common": ("🟢", '<tg-emoji emoji-id="6093865707424980866">🟢</tg-emoji>', "Common", 15)
}

# 🔥 POWERFUL RARITY MATCHER
def get_base_rarity(rarity_str: str) -> str:
    if not rarity_str or not isinstance(rarity_str, str):
        return "common"
    r_lower = rarity_str.lower().strip()
    
    # 1. Exact Match Check
    for key, (_, _, name, _) in RARITIES.items():
        if key == r_lower or name.lower() == r_lower:
            return key

    # 2. Substring Match Check
    for key, (db_emoji, _, name, _) in RARITIES.items():
        if key in r_lower or name.lower() in r_lower or db_emoji in r_lower:
            return key
            
    return "common"

try:
    collection.create_index([('id', ASCENDING)], unique=True, background=True)
    collection.create_index([('rarity', ASCENDING), ('anime', ASCENDING)], background=True)
    user_collection.create_index([('id', ASCENDING)], unique=True, background=True)
    user_collection.create_index([('characters.id', ASCENDING)], background=True, sparse=True)
except Exception: 
    pass

# 🔥 Faster Updates
char_cache = TTLCache(maxsize=100000, ttl=60)
user_cache = TTLCache(maxsize=60000, ttl=60) 
query_cache = TTLCache(maxsize=20000, ttl=30) 
count_cache = TTLCache(maxsize=40000, ttl=60)
feedback_cache = TTLCache(maxsize=15000, ttl=4800)
view_cache = TTLCache(maxsize=8000, ttl=900)
wishlist_cache = TTLCache(maxsize=8000, ttl=2400)

CAPS = str.maketrans('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', 'ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ')

@lru_cache(maxsize=65536)
def sc(t: str) -> str: 
    return t.translate(CAPS)

@lru_cache(maxsize=32768)
def parse_rar(r: str) -> Rarity:
    base_key = get_base_rarity(r)
    db_emoji, premium_emoji, name, val = RARITIES[base_key]
    return Rarity(db_emoji, premium_emoji, sc(name), val)

def trunc(t: str, l: int = 22) -> str: 
    return t[:l-2] + '..' if len(t) > l else t

def cache_key(*args) -> str: 
    return hashlib.md5(str(args).encode()).hexdigest()

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
            
            # 🔥 Smart ID Matcher System
            or_conditions = [{'name': rx}, {'anime': rx}, {'rarity': rx}]
            
            if q.isdigit():
                clean_num = int(q)
                id_rx = re.compile(rf"^0*{clean_num}$")
                or_conditions.append({'id': id_rx})
                or_conditions.append({'id': str(clean_num)})
                or_conditions.append({'id': clean_num})
            else:
                or_conditions.append({'id': q})
                
            chars = await collection.find({'$or': or_conditions}, {'_id': 0}).limit(lim).to_list(length=lim)
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
    
    # Yahan humne normal emoji ki jagah premium (r.premium) laga diya hai
    cap = (
        f"<b>{sc('Character Info ')}<tg-emoji emoji-id=\"6093637923834438402\">✨</tg-emoji></b>\n\n"
        f"<b>{escape(sc(an))}</b>\n"
        f"<b>{cid}: {escape(sc(nm))}</b>\n"
        f"({r.premium} <b>{sc('RARITY:')}</b> {r.name})"
    )
    return cap

def owners_caption(ch: Dict, owners: List[Dict], page: int) -> str:
    nm = ch.get('name', 'Unknown')
    total = sum(o.get('count', 0) for o in owners)
    cap = f"<b>{escape(sc(nm))}</b>\n\n<b><tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> {len(owners)} {sc('owners')} • {total}× {sc('grabbed')}</b>\n\n"
    
    medals = {
        1: "<tg-emoji emoji-id=\"5440539497383087970\">🥇</tg-emoji>", 
        2: "<tg-emoji emoji-id=\"5447203607294265305\">🥈</tg-emoji>", 
        3: "<tg-emoji emoji-id=\"5453902265922376865\">🥉</tg-emoji>"
    }
    
    USERS_PER_PAGE = 10
    start = page * USERS_PER_PAGE
    end = start + USERS_PER_PAGE
    total_pages = max(1, (len(owners) + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    
    for i, o in enumerate(owners[start:end], start + 1):
        medal = medals.get(i, f"{i}.")
        fn = escape(trunc(o.get('first_name', 'User'), 18))
        uid = o.get('id')
        cap += f"{medal} <a href=\"tg://user?id={uid}\"><b>{fn}</b></a> • <code>×{o.get('count', 0)}</code>\n"
        
    cap += f"\n<tg-emoji emoji-id=\"5197269100878907942\">✍️</tg-emoji> <b>{sc(f'page {page+1}/{total_pages}')}</b>"
    return cap

def stats_caption(ch: Dict, owners: List[Dict]) -> str:
    nm = ch.get('name', 'Unknown')
    total = sum(o.get('count', 0) for o in owners)
    avg = round(total / len(owners), 1) if owners else 0
    cap = (
        f"<b>{escape(sc(nm))}</b>\n\n"
        f"<tg-emoji emoji-id=\"5231200819986047254\">📊</tg-emoji> <b>{sc('statistics')}</b>\n"
        f"<tg-emoji emoji-id=\"5310278924616356636\">🎯</tg-emoji> <code>{total}×</code> {sc('grabbed')}\n"
        f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <code>{len(owners)}</code> {sc('owners')}\n"
        f"<tg-emoji emoji-id=\"5028746137645876535\">📈</tg-emoji> <code>{avg}×</code> {sc('avg')}\n"
    )
    if owners:
        cap += f"\n<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>{sc('top collectors')}</b>\n"
        for i, o in enumerate(owners[:3], 1):
            fn = escape(trunc(o.get('first_name', 'User'), 18))
            uid = o.get('id')
            cap += f"{i}. <a href=\"tg://user?id={uid}\"><b>{fn}</b></a> • <code>×{o.get('count', 0)}</code>\n"
    return cap

def create_kbd(cid: str, uid: int = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(sc("♔ owners"), callback_data=f"o.{cid}:0"),
            InlineKeyboardButton(sc("stats ⑆"), callback_data=f"s.{cid}")
        ],
        [
            InlineKeyboardButton(sc("⤿ inline"), switch_inline_query_current_chat=cid)
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
                await query.answer([InlineQueryResultArticle(id="nouser", title=sc("no collection"), description=sc("start your journey"), input_message_content=InputTextMessageContent(f"<b><tg-emoji emoji-id=\"5265120027853481187\">🧩</tg-emoji> {sc('start collecting!')}</b>", parse_mode=ParseMode.HTML))], cache_time=5)
                return
            cd = {c['id']: c for c in usr.get('characters', []) if isinstance(c, dict) and c.get('id')}
            all_chars = list(cd.values())
            
            if sq:
                rx = re.compile(re.escape(sq), re.IGNORECASE)
                def match_char(c):
                    cid_str = str(c.get('id', ''))
                    if sq.isdigit() and cid_str.isdigit():
                        if int(sq) == int(cid_str):
                            return True
                    else:
                        if cid_str == sq:
                            return True
                    if rx.search(c.get('name', '')) or rx.search(c.get('anime', '')) or rx.search(c.get('rarity', '')):
                        return True
                    return False
                
                all_chars = [c for c in all_chars if match_char(c)]
                
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
        for i, ch in enumerate(chars):
            cid = ch.get('id')
            img = ch.get('img_url', '')
            vid = ch.get('is_video', False)
            
            if not cid or not img: 
                continue
                
            nm, an = ch.get('name', '?'), ch.get('anime', '?')
            r = parse_rar(ch.get('rarity', ''))
            fav = False
            
            if is_coll and usr:
                fv = usr.get('favorites')
                fid = fv.get('id') if isinstance(fv, dict) else fv
                fav = (fid == cid)
            
            cap = minimal_caption(ch, fav, uid=uid)
            kbd = create_kbd(cid, uid)
            
            rid = f"{cid}_{off}_{i}_{qid[:8]}"
            # Yahan r.emoji hi use hoga taaki inline results title me normal emoji dikhe (HTML support nahi karta title)
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
    cp = cid.split('_')
    cidc = ''.join(filter(str.isalnum, cp[0]))
    fk = f'pick_{cidc}'
    feedback_cache[fk] = feedback_cache.get(fk, 0) + 1
    qk = f'query_{result.from_user.id}'
    feedback_cache[qk] = result.query

async def show_owners(update: Update, context) -> None:
    q = update.callback_query
    await q.answer()
    try:
        data = q.data.split('.', 1)[1]
        
        if ':' in data:
            cid, page_str = data.split(':')
            page = int(page_str)
        else:
            cid = data
            page = 0
            
        ch = await collection.find_one({'id': cid}, {'_id': 0})
        if not ch:
            await q.answer(sc("not found"), show_alert=True)
            return
            
        owners = await get_owners(cid, 100)
        if not owners:
            await q.answer(sc("no owners"), show_alert=True)
            return
            
        cap = owners_caption(ch, owners, page)
        
        USERS_PER_PAGE = 10
        total_pages = max(1, (len(owners) + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
        
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(sc("⋞ prev"), callback_data=f"o.{cid}:{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(sc("next ⋟"), callback_data=f"o.{cid}:{page+1}"))
            
        kbd_layout = []
        if nav_buttons:
            kbd_layout.append(nav_buttons)
            
        kbd_layout.append([
            InlineKeyboardButton(sc("⟲ back"), callback_data=f"b.{cid}"), 
            InlineKeyboardButton(sc("stats ⑆"), callback_data=f"s.{cid}")
        ])
        kbd_layout.append([
            InlineKeyboardButton(sc("⤿ inline"), switch_inline_query_current_chat=cid)
        ])
        
        kbd = InlineKeyboardMarkup(kbd_layout)
        await q.edit_message_caption(caption=cap, parse_mode=ParseMode.HTML, reply_markup=kbd)
    except Exception as e:
        LOGGER.error(f"Error in show_owners: {e}")
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
                InlineKeyboardButton(sc("owners ♔"), callback_data=f"o.{cid}:0")
            ], 
            [
                InlineKeyboardButton(sc("⤿ inline"), switch_inline_query_current_chat=cid)
            ]
        ])
        await q.edit_message_caption(caption=cap, parse_mode=ParseMode.HTML, reply_markup=kbd)
    except Exception:
        await q.answer(sc("error"), show_alert=True)

application.add_handler(InlineQueryHandler(inlinequery, block=False))
application.add_handler(ChosenInlineResultHandler(chosen_inline_result, block=False))
application.add_handler(CallbackQueryHandler(show_owners, pattern=r'^o\.', block=False))
application.add_handler(CallbackQueryHandler(back_card, pattern=r'^b\.', block=False))
application.add_handler(CallbackQueryHandler(show_stats, pattern=r'^s\.', block=False))

import asyncio
import random
import math
from html import escape
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler
from telegram.error import TelegramError
from shivu import db, application, LOGGER

# --- SMALL CAPS CONVERTER HELPERS ---
SMALL_CAPS_TRANS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
)

def to_small_caps(text: str) -> str:
    if not text:
        return ""
    return str(text).translate(SMALL_CAPS_TRANS)

# 🔥 GLOBAL CACHE FOR INSANE SPEED & INSTANT DATA SYNC
ANIME_COUNTS_CACHE: Dict[str, int] = {}
GLOBAL_CHAR_CACHE: Dict[str, Optional[Dict[str, str]]] = {}

# 🔥 UNIFIED RARITY DICTIONARY
RARITIES = {
    "mythic": ("💎", '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>', "Mythic"),
    "cosmic": ("🌌", '<tg-emoji emoji-id="5431783411981228752">🎆</tg-emoji>', "Cosmic"),
    "celestial": ("🪽", '<tg-emoji emoji-id="5434121252874756456">🕊</tg-emoji>', "Celestial"),
    "exclusive": ("💮", '<tg-emoji emoji-id="6100567406889935797">🤴</tg-emoji>', "Exclusive"),
    "legendary": ("🟡", '<tg-emoji emoji-id="6084550327086883643">🔥</tg-emoji>', "Legendary"),
    "premium": ("🔮", '<tg-emoji emoji-id="6093919703753831564">🔮</tg-emoji>', "Premium Edition"),
    "neon": ("⚡", '<tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>', "Neon"),
    "summer": ("🏖️", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"),
    "sweet": ("🍭", '<tg-emoji emoji-id="6222115531122546353">🍭</tg-emoji>', "Sweet"),
    "special": ("🔴", '<tg-emoji emoji-id="6093741664474504699">🔴</tg-emoji>', "Medium"),
    "valentine": ("💞", '<tg-emoji emoji-id="5255861796350224063">❤️</tg-emoji>', "Valentine"),
    "winter": ("❄️", '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>', "Winter"),
    "erotic": ("🥵", '<tg-emoji emoji-id="6093490292923574796">❤️‍🔥</tg-emoji>', "Spicy"),
    "rare": ("🟠", '<tg-emoji emoji-id="5339390195768774311">🟠</tg-emoji>', "Rare"),
    "common": ("🟢", '<tg-emoji emoji-id="6093865707424980866">🟢</tg-emoji>', "Common")
}

def get_base_rarity(rarity_str: str) -> str:
    if not rarity_str or not isinstance(rarity_str, str): return "common"
    r_lower = rarity_str.lower().strip()
    for key, (_, _, name) in RARITIES.items():
        if key == r_lower or name.lower() == r_lower: return key
    for key, (db_emoji, _, name) in RARITIES.items():
        if key in r_lower or name.lower() in r_lower or db_emoji in r_lower: return key
    return "common"

def rarity_display(key: str) -> str:
    db_emoji, _, name = RARITIES.get(key, RARITIES["common"])
    return f"{db_emoji} {name}"

def get_prem_emoji(rarity_text: str) -> str:
    return RARITIES[get_base_rarity(rarity_text)][1]

def chunk(items: list, size: int) -> list:
    return [items[i:i + size] for i in range(0, len(items), size)]

@dataclass
class Character:
    id: str
    name: str
    anime: str
    rarity: str
    img_url: Optional[str] = None
    is_video: bool = False
    event_emoji: Optional[str] = None
    gender: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional['Character']:
        if not isinstance(data, dict): return None
        return cls(
            id=str(data.get('id', '')),
            name=data.get('name', 'Unknown'),
            anime=data.get('anime', 'Unknown'),
            rarity=data.get('rarity', '🟢 Common'),
            img_url=data.get('img_url'),
            is_video=data.get('is_video', False),
            event_emoji=data.get('event_emoji') or data.get('event'),
            gender=data.get('gender')
        )

@dataclass
class DisplayOptions:
    show_url: bool = False
    video_support: bool = True
    preview_image: bool = True
    show_rarity_full: bool = False
    compact_mode: bool = False

# 🔥 EXACT STYLE WITH "⚋" LINES ON BOTH SIDES
DEFAULT_STYLE = {
    'header': "<b>{user_mention}'s Harem</b>\n\n",
    'anime_header': "<b><tg-emoji emoji-id=\"6314494724266796319\">🟠</tg-emoji> {anime} {user_count}/{total_count}</b>\n",
    'separator': "⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋\n",
    'character': "➥ {id} | {rarity} | {name}{event} x{count}\n",
    'footer': "⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋⚋\n\n",
}
DEFAULT_OPTIONS = DisplayOptions()

@dataclass
class UserCollection:
    user_id: int
    characters: List[Character] = field(default_factory=list)
    favorite: Optional[Character] = None
    filter_mode: str = "default"

    def get_filtered_characters(self) -> List[Character]:
        mode = str(self.filter_mode)
        chars = self.characters
        
        # 🔥 Step 1: Remove duplicates perfectly by normalizing IDs (9 == 09)
        unique_chars_dict = {}
        if mode == "latest":
            for c in reversed(chars):
                c_clean = str(c.id).strip().lstrip('0') or '0'
                if c_clean not in unique_chars_dict:
                    unique_chars_dict[c_clean] = c
            unique_list = list(unique_chars_dict.values())
        else:
            for c in chars:
                c_clean = str(c.id).strip().lstrip('0') or '0'
                if c_clean not in unique_chars_dict:
                    unique_chars_dict[c_clean] = c
            unique_list = list(unique_chars_dict.values())
        
        # 🔥 Step 2: Apply filters on correctly synced unique characters
        if mode.startswith("anime:"):
            target_anime = mode.split(":", 1)[1]
            filtered = [c for c in unique_list if c.anime == target_anime]
            return sorted(filtered, key=lambda c: c.id)
        if mode.startswith("char:"):
            target_char_name = mode.split(":", 1)[1]
            filtered = [c for c in unique_list if c.name == target_char_name]
            return sorted(filtered, key=lambda c: (c.anime, c.id))
        if mode in RARITIES:
            target_key = mode.lower()
            filtered = [c for c in unique_list if get_base_rarity(c.rarity) == target_key]
            return sorted(filtered, key=lambda c: (c.anime, c.id))
        if mode == "latest":
            return unique_list
            
        return sorted(unique_list, key=lambda c: (c.anime, c.id))

    def count_by_id(self, characters: List[Character]) -> Dict[str, int]:
        counts = {}
        for char in characters: 
            c_clean = str(char.id).strip().lstrip('0') or '0'
            counts[c_clean] = counts.get(c_clean, 0) + 1
        return counts

    def group_by_anime(self, characters: List[Character]) -> Dict[str, List[Character]]:
        grouped = {}
        for char in characters:
            key = (char.anime or "Unknown").strip().upper()
            grouped.setdefault(key, []).append(char)
        return grouped

class MediaHelper:
    VIDEO_EXT = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v')
    GLOBAL_FALLBACK = "https://files.catbox.moe/sgo9in.png"

    @staticmethod
    def is_video_url(url: Optional[str]) -> bool:
        return bool(url) and str(url).lower().split('?')[0].endswith(MediaHelper.VIDEO_EXT)

    @staticmethod
    async def send_media_message(message, media_url_or_urls, caption: str,
                                  reply_markup, is_video_or_videos = False,
                                  display_options: Optional[DisplayOptions] = None):
        opts = display_options or DisplayOptions()
        urls = media_url_or_urls if isinstance(media_url_or_urls, list) else [media_url_or_urls]
        vids = is_video_or_videos if isinstance(is_video_or_videos, list) else [is_video_or_videos] * len(urls)

        valid_pairs = [(u, v) for u, v in zip(urls, vids) if u and str(u).strip()]

        if not valid_pairs or not opts.preview_image:
            return await message.reply_text(caption, reply_markup=reply_markup, parse_mode='HTML')

        for url, vid in valid_pairs:
            is_vid = opts.video_support and (vid or MediaHelper.is_video_url(url))
            try:
                if is_vid:
                    try:
                        return await message.reply_video(video=url, caption=caption, reply_markup=reply_markup, parse_mode='HTML', supports_streaming=True, read_timeout=120, write_timeout=120)
                    except TelegramError as e:
                        if "caption" in str(e).lower() or "too long" in str(e).lower(): raise e
                        return await message.reply_photo(photo=url, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
                else:
                    try:
                        return await message.reply_photo(photo=url, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
                    except TelegramError as e:
                        if "caption" in str(e).lower() or "too long" in str(e).lower(): raise e 
                        return await message.reply_video(video=url, caption=caption, reply_markup=reply_markup, parse_mode='HTML', supports_streaming=True, read_timeout=120, write_timeout=120)
                        
            except TelegramError as e:
                err_msg = str(e).lower()
                LOGGER.warning(f"Media rejected. URL: {url}, Error: {e}")
                
                if "caption" in err_msg or "too long" in err_msg:
                    try:
                        if is_vid:
                            await message.reply_video(video=url, caption="<b>✨ Harem Collection ✨</b>", parse_mode='HTML', supports_streaming=True)
                        else:
                            await message.reply_photo(photo=url, caption="<b>✨ Harem Collection ✨</b>", parse_mode='HTML')
                        
                        return await message.reply_text(caption, reply_markup=reply_markup, parse_mode='HTML')
                    except Exception:
                        pass
                continue 
                
        try:
            return await message.reply_photo(photo=MediaHelper.GLOBAL_FALLBACK, caption=caption, reply_markup=reply_markup, parse_mode='HTML')
        except TelegramError:
            return await message.reply_text(caption, reply_markup=reply_markup, parse_mode='HTML')

class HaremMessageBuilder:
    def __init__(self, collection: UserCollection, page: int, total_pages: int,
                 style: Dict, options: DisplayOptions, user_name: str, user_id: int):
        self.collection = collection
        self.page = page
        self.total_pages = total_pages
        self.style = style
        self.options = options
        self.user_name = user_name
        self.user_id = user_id

    def build_message(self, characters: List[Character], anime_counts: Dict[str, int]) -> str:
        user_mention = f'<a href="tg://user?id={self.user_id}">{escape(self.user_name)}</a>'
        message = self.style['header'].format(user_mention=user_mention)
        grouped = self.collection.group_by_anime(characters)
        counts = self.collection.count_by_id(self.collection.characters)

        for anime_key, chars in grouped.items():
            display_anime = chars[0].anime or "Unknown"
            
            user_unique = {
                str(c.id).strip().lstrip('0') or '0' 
                for c in self.collection.characters 
                if (c.anime or "Unknown").strip().upper() == anime_key
            }
            user_count = len(user_unique)
            total_count = anime_counts.get(display_anime, 0)

            message += self.style['anime_header'].format(
                anime=escape(to_small_caps(display_anime)), user_count=user_count, total_count=total_count
            )
            message += self.style['separator']

            for char in chars:
                c_clean = str(char.id).strip().lstrip('0') or '0'
                message += self._format_character(char, counts.get(c_clean, 1))
            message += self.style['footer']
        return message

    def _format_character(self, char: Character, count: int) -> str:
        c_clean = str(char.id).strip().lstrip('0') or '0'
        char_id = c_clean.zfill(3)
        r_emoji = get_prem_emoji(char.rarity)
        event_str = f" [{char.event_emoji}]" if char.event_emoji else ""
        return self.style['character'].format(
            id=char_id, rarity=r_emoji, name=escape(to_small_caps(char.name)), event=event_str, count=count
        )

class HaremHandler:
    CHARACTERS_PER_PAGE = 12

    def __init__(self):
        self.collection_db = db['anime_characters_lol']
        self.user_db = db['user_collection_lmaoooo']

    # 🔥 INSTANT DATA SYNC METHOD (Solves Anime Grouping & Typos Mismatch Issue!)
    async def sync_user_characters_with_live_data(self, characters: List[Character]):
        global GLOBAL_CHAR_CACHE
        if not characters: return
        
        missing_ids = set()
        for c in characters:
            c_clean = str(c.id).strip().lstrip('0') or '0'
            if c_clean not in GLOBAL_CHAR_CACHE:
                missing_ids.add(c_clean)
                
        if missing_ids:
            query_ids = list(missing_ids)
            int_ids = [int(mid) for mid in missing_ids if mid.isdigit()]
            
            cursor = self.collection_db.find(
                {"id": {"$in": query_ids + int_ids}}, 
                {"id": 1, "name": 1, "anime": 1, "rarity": 1}
            )
            docs = await cursor.to_list(length=None)
            
            for doc in docs:
                c_clean = str(doc.get('id', '')).strip().lstrip('0') or '0'
                if c_clean:
                    GLOBAL_CHAR_CACHE[c_clean] = {
                        "name": doc.get('name', 'Unknown'),
                        "anime": doc.get('anime', 'Unknown'),
                        "rarity": doc.get('rarity', '🟢 Common')
                    }
                    
            for mid in missing_ids:
                if mid not in GLOBAL_CHAR_CACHE:
                    GLOBAL_CHAR_CACHE[mid] = None 
                    
        # Replace outdated user db names/animes with global perfectly synced ones!
        for c in characters:
            c_clean = str(c.id).strip().lstrip('0') or '0'
            live_data = GLOBAL_CHAR_CACHE.get(c_clean)
            if live_data:
                c.name = live_data['name']
                c.anime = live_data['anime']
                c.rarity = live_data['rarity']

    async def load_user_collection(self, user_id: int) -> Optional[UserCollection]:
        user = await self.user_db.find_one({'id': user_id})
        if not user: return None

        characters = [c for c in (Character.from_dict(char) for char in user.get('characters', [])) if c]
        
        # 🔥 PERFECT SYNC: Sync memory with Global Live Data so it groups correctly every time
        await self.sync_user_characters_with_live_data(characters)
        
        fav_data = user.get('favorites')
        favorite = None
        if fav_data:
            fav_id_clean = ""
            if isinstance(fav_data, dict):
                fav_id_clean = str(fav_data.get('id', '')).strip().lstrip('0') or '0'
                favorite = Character.from_dict(fav_data)
            else:
                fav_id_clean = str(fav_data).strip().lstrip('0') or '0'
                
            if not favorite:
                for c in characters:
                    if (str(c.id).strip().lstrip('0') or '0') == fav_id_clean:
                        favorite = Character(id=c.id, name=c.name, anime=c.anime, rarity=c.rarity, img_url=c.img_url, is_video=c.is_video, event_emoji=c.event_emoji)
                        break

        return UserCollection(
            user_id=user_id, characters=characters, favorite=favorite,
            filter_mode=user.get('hmode', 'default')
        )

    async def _auto_delete_message(self, message, delay_seconds: int = 1200):
        await asyncio.sleep(delay_seconds)
        try: await message.delete()
        except Exception: pass 

    async def update_live_data_all(self, characters: List[Character]):
        if not characters: return
            
        query_ids = set()
        for c in characters:
            c_clean = str(c.id).strip().lstrip('0') or '0'
            query_ids.update([str(c.id).strip(), c_clean])
            if c_clean.isdigit():
                val = int(c_clean)
                query_ids.update([val, f"{val:02d}", f"{val:03d}", f"{val:04d}"])
        
        # Ye sirf media laane ke liye current page par use hoga
        cursor = self.collection_db.find(
            {"id": {"$in": list(query_ids)}},
            {"id": 1, "img_url": 1, "is_video": 1, "gender": 1}
        )
        live_docs = await cursor.to_list(length=None)
            
        live_map = {}
        for doc in live_docs:
            doc_id_str = str(doc.get('id')).strip()
            live_map[doc_id_str] = doc
            live_map[doc_id_str.lstrip('0') or '0'] = doc
            
        for c in characters:
            c_clean = str(c.id).strip().lstrip('0') or '0'
            doc = live_map.get(str(c.id).strip()) or live_map.get(c_clean)
            if doc:
                if doc.get('img_url'): c.img_url = doc.get('img_url')
                c.is_video = doc.get('is_video', c.is_video)
                c.gender = doc.get('gender', c.gender)

    async def get_anime_counts(self, anime_list: List[str]) -> Dict[str, int]:
        global ANIME_COUNTS_CACHE
        if not anime_list: return {}
        counts = {}
        missing = []
        for anime in anime_list:
            if anime in ANIME_COUNTS_CACHE: counts[anime] = ANIME_COUNTS_CACHE[anime]
            else: missing.append(anime)
        if missing:
            pipeline = [{"$match": {"anime": {"$in": missing}}}, {"$group": {"_id": "$anime", "count": {"$sum": 1}}}]
            cursor = self.collection_db.aggregate(pipeline)
            docs = await cursor.to_list(length=None)
            found_animes = set()
            for doc in docs:
                ANIME_COUNTS_CACHE[doc['_id']] = counts[doc['_id']] = doc['count']
                found_animes.add(doc['_id'])
            for m in missing:
                if m not in found_animes:
                    ANIME_COUNTS_CACHE[m] = counts[m] = 0
        return counts

    def _build_keyboard(self, page: int, total_pages: int, total_chars: int, user_id: int, step: int = 1) -> InlineKeyboardMarkup:
        keyboard = [[InlineKeyboardButton(f"✨ ʜᴀʀᴇᴍ ({total_chars})", switch_inline_query_current_chat=f"collection.{user_id}")]]
        if total_pages > 1:
            nav = []
            if page > 0: nav.append(InlineKeyboardButton("❮", callback_data=f"harem_page:{max(0, page - step)}:{user_id}:{step}"))
            nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="harem_ignore"))
            if page < total_pages - 1: nav.append(InlineKeyboardButton("❯", callback_data=f"harem_page:{min(total_pages - 1, page + step)}:{user_id}:{step}"))
            if nav: keyboard.append(nav)

            if total_pages > 2:
                skip_val = 2 if step == 1 else 1
                keyboard.append([InlineKeyboardButton(f"⭆ {skip_val}x sᴋɪᴘ", callback_data=f"harem_2x:{page}:{user_id}:{skip_val}")])

        keyboard.append([InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data=f"harem_close:{user_id}")])
        return InlineKeyboardMarkup(keyboard)

    async def show_harem(self, update: Update, context: CallbackContext, page: int = 0, edit: bool = False, step: int = 1):
        user = update.effective_user
        user_id = user.id
        user_name = user.first_name
        message = update.message or update.callback_query.message

        collection = await self.load_user_collection(user_id)
        if not collection: return await message.reply_text("<b><tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> ʏᴏᴜ ɴᴇᴇᴅ ᴛᴏ ɢʀᴀʙ ᴀ ᴄʜᴀʀᴀᴄᴛᴇʀ ғɪʀsᴛ ᴜsɪɴɢ /grab ᴄᴏᴍᴍᴀɴᴅ!</b>", parse_mode='HTML')
        if not collection.characters: return await message.reply_text("<b><tg-emoji emoji-id=\"5433653135799228968\">📁</tg-emoji> ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ᴄʜᴀʀᴀᴄᴛᴇʀs ʏᴇᴛ! ᴜsᴇ /grab ᴛᴏ ᴄᴀᴛᴄʜ sᴏᴍᴇ.</b>", parse_mode='HTML')

        display_order = collection.get_filtered_characters()
        if not display_order: return await message.reply_text(f"<b>ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ᴄʜᴀʀᴀᴄᴛᴇʀs ɪɴ ᴛʜɪs ᴍᴏᴅᴇ.</b>\n<b><tg-emoji emoji-id=\"5422439311196834318\">💡</tg-emoji> ᴄʜᴀɴɢᴇ ᴍᴏᴅᴇ ᴜsɪɴɢ /hmode</b>", parse_mode='HTML')

        total_pages = math.ceil(len(display_order) / self.CHARACTERS_PER_PAGE)
        page = max(0, min(page, total_pages - 1))
        start = page * self.CHARACTERS_PER_PAGE
        current = display_order[start:start + self.CHARACTERS_PER_PAGE]

        display_char = collection.favorite
        if not display_char:
            display_char = current[0] if current else collection.characters[0]

        if display_char:
            c_clean = str(display_char.id).strip().lstrip('0') or '0'
            q_ids = [str(display_char.id).strip(), c_clean]
            if c_clean.isdigit(): 
                val = int(c_clean)
                q_ids.extend([val, f"{val:02d}", f"{val:03d}", f"{val:04d}"])
            
            doc = await self.collection_db.find_one({"id": {"$in": q_ids}, "img_url": {"$nin": [None, ""]}})
            if doc:
                display_char.img_url = doc.get("img_url")
                display_char.is_video = doc.get("is_video", False)

        chars_to_update = current.copy()
        if display_char and display_char not in chars_to_update:
            chars_to_update.append(display_char)
        await self.update_live_data_all(chars_to_update)

        media_urls = []
        is_videos = []

        if display_char and getattr(display_char, 'img_url', None):
            media_urls.append(display_char.img_url)
            is_videos.append(getattr(display_char, 'is_video', False))

        for c in current:
            if getattr(c, 'img_url', None) and c.img_url not in media_urls:
                media_urls.append(c.img_url)
                is_videos.append(getattr(c, 'is_video', False))

        if not media_urls:
            db_query_ids = set()
            for c in collection.characters[:30]:
                c_clean = str(c.id).strip().lstrip('0') or '0'
                db_query_ids.update([str(c.id).strip(), c_clean])
                if c_clean.isdigit():
                    val = int(c_clean)
                    db_query_ids.update([val, f"{val:02d}", f"{val:03d}", f"{val:04d}"])
                
            valid_docs = await self.collection_db.find({
                "id": {"$in": list(db_query_ids)},
                "img_url": {"$type": "string", "$ne": ""}
            }).to_list(length=10)
            
            for doc in valid_docs:
                url = doc.get("img_url")
                if url and url not in media_urls:
                    media_urls.append(url)
                    is_videos.append(doc.get("is_video", False))

        style, options = DEFAULT_STYLE, DEFAULT_OPTIONS
        anime_counts = await self.get_anime_counts(list({c.anime for c in current}))
        builder = HaremMessageBuilder(collection, page, total_pages, style, options, user_name, user_id)
        text = builder.build_message(current, anime_counts)
        markup = self._build_keyboard(page, total_pages, len(display_order), user_id, step)

        if edit:
            try:
                if message.photo or message.video or message.animation or message.document:
                    await message.edit_caption(caption=text, reply_markup=markup, parse_mode='HTML')
                else:
                    await message.edit_text(text=text, reply_markup=markup, parse_mode='HTML')
                return
            except TelegramError as e:
                err_msg = str(e).lower()
                if "not modified" in err_msg: return
                if "too long" in err_msg or "caption" in err_msg:
                    await message.delete()
                    sent_msg = await MediaHelper.send_media_message(
                        message=message, media_url_or_urls=media_urls, caption=text, 
                        reply_markup=markup, is_video_or_videos=is_videos, display_options=options
                    )
                    if sent_msg: asyncio.create_task(self._auto_delete_message(sent_msg, 1200))
                return 

        sent_msg = await MediaHelper.send_media_message(
            message=message, media_url_or_urls=media_urls, caption=text, 
            reply_markup=markup, is_video_or_videos=is_videos, display_options=options
        )
            
        if sent_msg:
            asyncio.create_task(self._auto_delete_message(sent_msg, 1200))

class ModeHandler:
    IMG = "https://files.catbox.moe/sgo9in.png"
    LABELS = {"default": "ᴅᴇғᴀᴜʟᴛ", "latest": "ʟᴀᴛᴇsᴛ", "animes": "ᴀɴɪᴍᴇs", "waifus": "ᴡᴀɪғᴜs"}

    def __init__(self): self.user_db = db['user_collection_lmaoooo']

    async def _current_mode(self, user_id: int) -> str:
        user = await self.user_db.find_one({'id': user_id})
        return user.get('hmode', 'default') if user else 'default'

    def _keyboard(self, current: str, user_id: int) -> InlineKeyboardMarkup:
        def label(key, text):
            if key == "default" and current == "default": return f"{text} ✓"
            if key == "latest" and current == "latest": return f"{text} ✓"
            if key == "rarity" and current in RARITIES: return f"{text} ✓"
            if key == "animes" and str(current).startswith("anime:"): return f"{text} ✓"
            if key == "waifus" and str(current).startswith("char:"): return f"{text} ✓"
            return text

        rarity_label = label("rarity", "ʀᴀʀɪᴛʏ") 
        rows = [
            [InlineKeyboardButton(label("default", "ᴅᴇғᴀᴜʟᴛ"), callback_data=f"harem_mode:default:{user_id}"),
             InlineKeyboardButton(rarity_label, callback_data=f"harem_mode:rarity:{user_id}")],
            [InlineKeyboardButton(label("latest", "ʟᴀᴛᴇsᴛ"), callback_data=f"harem_mode:latest:{user_id}"),
             InlineKeyboardButton(label("animes", "ᴀɴɪᴍᴇs"), callback_data=f"harem_mode:animes:{user_id}")],
            [InlineKeyboardButton(label("waifus", "ᴡᴀɪғᴜs"), callback_data=f"harem_mode:waifus:{user_id}"),
             InlineKeyboardButton("⤬", callback_data=f"harem_mode:close:{user_id}")],
        ]
        return InlineKeyboardMarkup(rows)

    async def show_mode_menu(self, update: Update, user_id: int):
        markup = self._keyboard(await self._current_mode(user_id), user_id)
        caption = "<b>ᴄʜᴏᴏsᴇ ᴏɴᴇ ᴏғ ᴡᴀʏs ᴛᴏ sᴏʀᴛ ʏᴏᴜʀ ʜᴀʀᴇᴍ</b>"
        if update.callback_query: await update.callback_query.edit_message_caption(caption=caption, reply_markup=markup, parse_mode='HTML')
        else: await update.message.reply_photo(self.IMG, caption=caption, reply_markup=markup, parse_mode='HTML')

    async def show_rarity_menu(self, query, user_id: int):
        buttons = [InlineKeyboardButton(db_emoji, callback_data=f"harem_mode:{key}:{user_id}") for key, (db_emoji, _, _) in RARITIES.items()]
        keyboard = chunk(buttons, 3) + [[InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"harem_mode:back:{user_id}")]]
        await query.edit_message_caption(caption="<b><tg-emoji emoji-id=\"5260426225599405269\">🪄</tg-emoji> sᴇʟᴇᴄᴛ ᴀ ʀᴀʀɪᴛʏ ᴛᴏ ғɪʟᴛᴇʀ:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    # 🔥 FIX: Perfectly handle None cache fallback for animes menu
    async def show_anime_menu(self, query, user_id: int, page: int):
        user = await self.user_db.find_one({'id': user_id})
        chars = user.get('characters', []) if user else []
        await harem_handler.sync_user_characters_with_live_data([Character.from_dict(c) for c in chars if c])
        
        unique_animes = sorted(list({ (GLOBAL_CHAR_CACHE.get(str(c.get('id', '')).strip().lstrip('0') or '0') or {}).get('anime', c.get('anime', 'Unknown')) for c in chars }))
        if not unique_animes: return await query.answer("ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ᴀɴɪᴍᴇs ʏᴇᴛ!", show_alert=True)

        total_pages = math.ceil(len(unique_animes) / 10)
        page = max(0, min(page, total_pages - 1))
        start = page * 10
        current_animes = unique_animes[start:start+10]

        keyboard = []
        for i, anime in enumerate(current_animes):
            idx = start + i
            display_anime = to_small_caps(anime[:30] + "..." if len(anime) > 30 else anime)
            keyboard.append([InlineKeyboardButton(display_anime, callback_data=f"harem_mode:set_a:{user_id}:{idx}")])

        nav = []
        if page > 0: nav.append(InlineKeyboardButton("❮", callback_data=f"harem_mode:alist:{user_id}:{page-1}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="harem_ignore"))
        if page < total_pages - 1: nav.append(InlineKeyboardButton("❯", callback_data=f"harem_mode:alist:{user_id}:{page+1}"))
        if nav: keyboard.append(nav)
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"harem_mode:back:{user_id}")])
        await query.edit_message_caption(caption="<b><tg-emoji emoji-id=\"6314494724266796319\">🟠</tg-emoji> sᴇʟᴇᴄᴛ ᴀɴ ᴀɴɪᴍᴇ ᴛᴏ ғɪʟᴛᴇʀ:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    # 🔥 FIX: Perfectly handle None cache fallback for waifus menu
    async def show_char_menu(self, query, user_id: int, page: int):
        user = await self.user_db.find_one({'id': user_id})
        chars = user.get('characters', []) if user else []
        await harem_handler.sync_user_characters_with_live_data([Character.from_dict(c) for c in chars if c])

        unique_names = sorted(list({ (GLOBAL_CHAR_CACHE.get(str(c.get('id', '')).strip().lstrip('0') or '0') or {}).get('name', c.get('name', 'Unknown')) for c in chars }))
        if not unique_names: return await query.answer("ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ᴄʜᴀʀᴀᴄᴛᴇʀs ʏᴇᴛ!", show_alert=True)

        total_pages = math.ceil(len(unique_names) / 10)
        page = max(0, min(page, total_pages - 1))
        start = page * 10
        current_chars = unique_names[start:start+10]

        keyboard = []
        for i, cname in enumerate(current_chars):
            idx = start + i
            display_name = to_small_caps(cname[:28] + "..." if len(cname) > 28 else cname)
            keyboard.append([InlineKeyboardButton(display_name, callback_data=f"harem_mode:set_c:{user_id}:{idx}")])

        nav = []
        if page > 0: nav.append(InlineKeyboardButton("❮", callback_data=f"harem_mode:clist:{user_id}:{page-1}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="harem_ignore"))
        if page < total_pages - 1: nav.append(InlineKeyboardButton("❯", callback_data=f"harem_mode:clist:{user_id}:{page+1}"))
        if nav: keyboard.append(nav)
        keyboard.append([InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data=f"harem_mode:back:{user_id}")])
        await query.edit_message_caption(caption="<b><tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> sᴇʟᴇᴄᴛ ᴀ ᴄʜᴀʀᴀᴄᴛᴇʀ ᴛᴏ ғɪʟᴛᴇʀ:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    async def set_mode(self, user_id: int, mode: str):
        await self.user_db.update_one({'id': user_id}, {'$set': {'hmode': mode}}, upsert=True)

    async def handle_mode_callback(self, update: Update, context: CallbackContext):
        query = update.callback_query
        parts = query.data.split(':')
        if len(parts) < 3: return await query.answer("ɪɴᴠᴀʟɪᴅ ᴅᴀᴛᴀ", show_alert=True)
            
        action, owner_id_str = parts[1], parts[2]
        user_id = await verify_owner(query, owner_id_str, "ʙᴀᴋᴀ! ᴏᴘᴇɴ ʏᴏᴜʀ ᴏᴡɴ ʜᴍᴏᴅᴇ ᴜsɪɴɢ /hmode !")
        if user_id is None: return

        if action == "rarity": await query.answer(); return await self.show_rarity_menu(query, user_id)
        if action == "animes": await query.answer(); return await self.show_anime_menu(query, user_id, 0)
        if action == "waifus": await query.answer(); return await self.show_char_menu(query, user_id, 0)
        if action == "back": await query.answer(); return await self.show_mode_menu(update, user_id)
        if action == "close": await query.answer(); return await query.message.delete()

        # 🔥 FIX: Query properly answered before navigating so the button loader doesn't get stuck!
        if action == "alist": 
            await query.answer()
            return await self.show_anime_menu(query, user_id, int(parts[3]))
        if action == "clist": 
            await query.answer()
            return await self.show_char_menu(query, user_id, int(parts[3]))

        # 🔥 FIX: Same safe fallback for None handling here
        if action == "set_a":
            idx = int(parts[3])
            user = await self.user_db.find_one({'id': user_id})
            chars = user.get('characters', []) if user else []
            await harem_handler.sync_user_characters_with_live_data([Character.from_dict(c) for c in chars if c])
            unique_animes = sorted(list({ (GLOBAL_CHAR_CACHE.get(str(c.get('id', '')).strip().lstrip('0') or '0') or {}).get('anime', c.get('anime', 'Unknown')) for c in chars }))
            
            if idx < len(unique_animes):
                await self.set_mode(user_id, f"anime:{unique_animes[idx]}")
                safe_name = unique_animes[idx][:20] + "..." if len(unique_animes[idx]) > 20 else unique_animes[idx]
                await query.answer(f"✓ {safe_name} sᴇʟᴇᴄᴛᴇᴅ")
            else: await query.answer("ᴇʀʀᴏʀ sᴇʟᴇᴄᴛɪɴɢ ᴀɴɪᴍᴇ", show_alert=True)
            return await self.show_mode_menu(update, user_id)

        if action == "set_c":
            idx = int(parts[3])
            user = await self.user_db.find_one({'id': user_id})
            chars = user.get('characters', []) if user else []
            await harem_handler.sync_user_characters_with_live_data([Character.from_dict(c) for c in chars if c])
            unique_names = sorted(list({ (GLOBAL_CHAR_CACHE.get(str(c.get('id', '')).strip().lstrip('0') or '0') or {}).get('name', c.get('name', 'Unknown')) for c in chars }))
            
            if idx < len(unique_names):
                await self.set_mode(user_id, f"char:{unique_names[idx]}")
                safe_name = unique_names[idx][:20] + "..." if len(unique_names[idx]) > 20 else unique_names[idx]
                await query.answer(f"✓ {safe_name} sᴇʟᴇᴄᴛᴇᴅ")
            else: await query.answer("ᴇʀʀᴏʀ sᴇʟᴇᴄᴛɪɴɢ ᴄʜᴀʀᴀᴄᴛᴇʀ", show_alert=True)
            return await self.show_mode_menu(update, user_id)

        label = self.LABELS.get(action) or (RARITIES[action][2] if action in RARITIES else None)
        if not label: return await query.answer("ɪɴᴠᴀʟɪᴅ ᴏᴘᴛɪᴏɴ", show_alert=True)
        await self.set_mode(user_id, action)
        await query.answer(f"✓ {label} sᴇʟᴇᴄᴛᴇᴅ")
        await self.show_mode_menu(update, user_id)

class UnfavHandler:
    def __init__(self): self.user_db = db['user_collection_lmaoooo']

    async def show_unfav_prompt(self, update: Update):
        user_id = update.effective_user.id
        user = await self.user_db.find_one({'id': user_id})
        if not user: return await update.message.reply_text('<b><tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> ʏᴏᴜ ʜᴀᴠᴇ ɴᴏᴛ ɢᴏᴛ ᴀɴʏ ᴄʜᴀʀᴀᴄᴛᴇʀ ʏᴇᴛ!</b>', parse_mode='HTML')

        fav_data = user.get('favorites')
        fav = None
        if fav_data:
            if isinstance(fav_data, dict):
                fav = Character.from_dict(fav_data)
            else:
                characters = [c for c in (Character.from_dict(char) for char in user.get('characters', [])) if c]
                fav_id_clean = str(fav_data).strip().lstrip('0') or '0'
                for c in characters:
                    if (str(c.id).strip().lstrip('0') or '0') == fav_id_clean:
                        fav = c
                        break
        
        if not fav: return await update.message.reply_text("<b><tg-emoji emoji-id=\"5278454020111887994\">💔</tg-emoji> ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀ ғᴀᴠᴏʀɪᴛᴇ ᴄʜᴀʀᴀᴄᴛᴇʀ sᴇᴛ!</b>", parse_mode='HTML')

        buttons = [[InlineKeyboardButton("✓ ʏᴇs", callback_data=f"harem_unfav_yes:{user_id}"), InlineKeyboardButton("⤬ ɴᴏ", callback_data=f"harem_unfav_no:{user_id}")]]
        caption = f"<b><tg-emoji emoji-id=\"5278454020111887994\">💔</tg-emoji> ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʀᴇᴍᴏᴠᴇ ᴛʜɪs ғᴀᴠᴏʀɪᴛᴇ?</b>\n\n<b><tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> ɴᴀᴍᴇ:</b> <code>{escape(to_small_caps(fav.name))}</code>\n<b><tg-emoji emoji-id=\"6312254267461739671\">⛩</tg-emoji> ᴀɴɪᴍᴇ:</b> <code>{escape(to_small_caps(fav.anime))}</code>\n<b><tg-emoji emoji-id=\"6332443074769196273\">🆔</tg-emoji> ɪᴅ:</b> <code>{fav.id}</code>"
        
        c_clean = str(fav.id).strip().lstrip('0') or '0'
        q_ids = [str(fav.id).strip(), c_clean]
        if c_clean.isdigit(): 
            val = int(c_clean)
            q_ids.extend([val, f"{val:02d}", f"{val:03d}", f"{val:04d}"])
        live_doc = await db['anime_characters_lol'].find_one({"id": {"$in": q_ids}})
        if live_doc and live_doc.get('img_url'):
            fav.img_url = live_doc.get('img_url')
            fav.is_video = live_doc.get('is_video', False)

        await MediaHelper.send_media_message(message=update.message, media_url_or_urls=getattr(fav, 'img_url', None) or MediaHelper.GLOBAL_FALLBACK, caption=caption, reply_markup=InlineKeyboardMarkup(buttons), is_video_or_videos=getattr(fav, 'is_video', False), display_options=DEFAULT_OPTIONS)

    async def handle_unfav_callback(self, update: Update):
        query = update.callback_query
        action, _, user_id_str = query.data.partition(':')
        user_id = await verify_owner(query, user_id_str)
        if user_id is None: return
        await query.answer()

        if action == 'harem_unfav_yes':
            user = await self.user_db.find_one({'id': user_id})
            if not user or not user.get('favorites'): return await query.answer("ɴᴏ ғᴀᴠᴏʀɪᴛᴇ ғᴏᴜɴᴅ!", show_alert=True)
            await self.user_db.update_one({'id': user_id}, {'$unset': {'favorites': ""}})
            await query.edit_message_caption(caption=f"<b><tg-emoji emoji-id=\"5278454020111887994\">💔</tg-emoji> ғᴀᴠᴏʀɪᴛᴇ ʀᴇᴍᴏᴠᴇᴅ!</b>\n\n<b><i><tg-emoji emoji-id=\"5276239041052828276\">🎭</tg-emoji> ʏᴏᴜ ᴄᴀɴ sᴇᴛ ᴀ ɴᴇᴡ ғᴀᴠᴏʀɪᴛᴇ ᴜsɪɴɢ /fav</i></b>", parse_mode='HTML')
        elif action == 'harem_unfav_no': await query.edit_message_caption(caption="<b>ᴀᴄᴛɪᴏɴ ᴄᴀɴᴄᴇʟᴇᴅ. ғᴀᴠᴏʀɪᴛᴇ ᴋᴇᴘᴛ.</b>", parse_mode='HTML')


async def verify_owner(query, user_id_str: str, error_msg: str = "ᴛʜɪs ɪs ɴᴏᴛ ʏᴏᴜʀ ᴄᴏʟʟᴇᴄᴛɪᴏɴ ʙᴀᴋᴀ!") -> Optional[int]:
    try: owner_id = int(user_id_str)
    except ValueError: await query.answer("ɪɴᴠᴀʟɪᴅ ᴅᴀᴛᴀ!", show_alert=True); return None
    if query.from_user.id != owner_id:
        await query.answer(error_msg, show_alert=True)
        return None
    return owner_id

harem_handler = HaremHandler()
mode_handler = ModeHandler()
unfav_handler = UnfavHandler()

async def harem_command(update: Update, context: CallbackContext):
    try: await harem_handler.show_harem(update, context)
    except TelegramError as e:
        LOGGER.error(f"Error in harem_command: {e}", exc_info=True)
        await update.message.reply_text("<b><tg-emoji emoji-id=\"6307488052059053932\">🕐</tg-emoji> ʟᴏᴀᴅɪɴɢ ʜᴀʀᴇᴍ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.</b>", parse_mode='HTML')

async def harem_page_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    try:
        parts = query.data.split(':')
        if await verify_owner(query, parts[2]) is None: return
        await query.answer()
        await harem_handler.show_harem(update, context, int(parts[1]), edit=True, step=int(parts[3]) if len(parts) > 3 else 1)
    except Exception as e:
        LOGGER.error(f"Error in harem_page_callback: {e}", exc_info=True)
        await query.answer("ᴇʀʀᴏʀ ʟᴏᴀᴅɪɴɢ ᴘᴀɢᴇ", show_alert=True)

async def hmode_command(update: Update, context: CallbackContext):
    try: await mode_handler.show_mode_menu(update, update.effective_user.id)
    except TelegramError as e: LOGGER.error(f"Error in hmode_command: {e}", exc_info=True)

async def mode_callback(update: Update, context: CallbackContext):
    try: await mode_handler.handle_mode_callback(update, context)
    except TelegramError as e: LOGGER.error(f"Error in mode_callback: {e}", exc_info=True)

async def unfav_command(update: Update, context: CallbackContext):
    try: await unfav_handler.show_unfav_prompt(update)
    except TelegramError as e: LOGGER.error(f"Error in unfav_command: {e}", exc_info=True)

async def unfav_callback(update: Update, context: CallbackContext):
    try: await unfav_handler.handle_unfav_callback(update)
    except TelegramError as e: LOGGER.error(f"Error in unfav_callback: {e}", exc_info=True)

async def harem_2x_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    try:
        parts = query.data.split(':')
        if await verify_owner(query, parts[2]) is None: return
        target_step = int(parts[3]) if len(parts) > 3 else 2
        await query.answer("2x ᴘᴀɢᴇ sᴋɪᴘ ᴏɴ" if target_step == 2 else "1x (ɴᴏʀᴍᴀʟ) sᴋɪᴘ ᴏɴ")
        await harem_handler.show_harem(update, context, int(parts[1]) + target_step, edit=True, step=target_step)
    except Exception as e: LOGGER.error(f"Error in harem_2x_callback: {e}", exc_info=True)

async def harem_close_callback(update: Update, context: CallbackContext):
    if await verify_owner(update.callback_query, update.callback_query.data.partition(':')[2]) is not None:
        await update.callback_query.answer()
        await update.callback_query.message.delete()
    
async def ignore_callback(update: Update, context: CallbackContext):
    await update.callback_query.answer()

application.add_handler(CommandHandler(["harem", "collection"], harem_command, block=False))
application.add_handler(CommandHandler("hmode", hmode_command, block=False))
application.add_handler(CommandHandler("unfav", unfav_command, block=False))
application.add_handler(CallbackQueryHandler(harem_page_callback, pattern='^harem_page:', block=False))
application.add_handler(CallbackQueryHandler(mode_callback, pattern='^harem_mode:', block=False))
application.add_handler(CallbackQueryHandler(unfav_callback, pattern="^harem_unfav_", block=False))
application.add_handler(CallbackQueryHandler(harem_2x_callback, pattern='^harem_2x:', block=False))
application.add_handler(CallbackQueryHandler(harem_close_callback, pattern='^harem_close:', block=False))
application.add_handler(CallbackQueryHandler(ignore_callback, pattern='^harem_ignore$', block=False))

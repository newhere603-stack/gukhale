#siya method v3 - Custom Symbols + Small Caps Font

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
    """Converts regular text to Small Caps font matching your style."""
    if not text:
        return ""
    return str(text).translate(SMALL_CAPS_TRANS)

# Dictionary updated to hold 3 values (Database Emoji, Premium Emoji, Name)
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
    "pearl": ("🐚", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"),
    "cosmic": ("🌌", '<tg-emoji emoji-id="5431783411981228752">🎆</tg-emoji>', "Cosmic"),
}


def rarity_display(key: str) -> str:
    db_emoji, _, name = RARITIES.get(key, RARITIES["common"])
    return f"{db_emoji} {name}"

def rarity_premium_display(key: str) -> str:
    _, prem_emoji, name = RARITIES.get(key, RARITIES["common"])
    return f"{prem_emoji} {name}"

def rarity_emoji(display: str) -> str:
    if not display:
        return '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>'
    db_emoji = display.split(' ', 1)[0] if ' ' in display else display
    for key, (db_e, prem_e, name) in RARITIES.items():
        if db_emoji == db_e:
            return prem_e
    return db_emoji


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
        if not isinstance(data, dict):
            return None
        return cls(
            id=str(data.get('id', '')),
            name=data.get('name', 'Unknown'),
            anime=data.get('anime', 'Unknown'),
            rarity=data.get('rarity', rarity_display('common')),
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


DEFAULT_STYLE = {
    'header': "<b>{user_mention}'s ʜᴀʀᴇᴍ - ᴘᴀɢᴇ {page}/{total_pages}</b>\n\n",
    'anime_header': "<b><tg-emoji emoji-id=\"6312254267461739671\">⛩</tg-emoji> {anime}</b> ({user_count}/{total_count})\n",
    'separator': "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n",
    'character': "<b>➥ {id} | {rarity} | {name}{event} x{count}</b>\n",
    'footer': "\n",
}
DEFAULT_OPTIONS = DisplayOptions()


@dataclass
class UserCollection:
    user_id: int
    characters: List[Character] = field(default_factory=list)
    favorite: Optional[Character] = None
    filter_mode: str = "default"

    def get_filtered_characters(self) -> List[Character]:
        mode = self.filter_mode
        chars = self.characters
        
        # Rarity Filter
        if mode in RARITIES:
            target_name = RARITIES[mode][2].lower()
            # Matching target name to avoid DB emoji mismatches
            return [c for c in chars if target_name in c.rarity.lower()]
            
        # Latest Mode
        if mode == "latest":
            return list(reversed(chars))
            
        # Animes Mode
        if mode == "animes":
            return sorted(chars, key=lambda c: (c.anime, c.id))
            
        # Waifus Mode
        if mode == "waifus":
            return [c for c in chars if c.gender and c.gender.lower() in ['female', 'f', 'girl']]
            
        # Default Mode (Chronological from DB)
        return chars

    def count_by_id(self, characters: List[Character]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for char in characters:
            counts[char.id] = counts.get(char.id, 0) + 1
        return counts

    def group_by_anime(self, characters: List[Character]) -> Dict[str, List[Character]]:
        grouped: Dict[str, List[Character]] = {}
        for char in characters:
            grouped.setdefault(char.anime, []).append(char)
        return grouped


class MediaHelper:
    VIDEO_EXT = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v')

    @staticmethod
    def is_video_url(url: Optional[str]) -> bool:
        return bool(url) and url.lower().split('?')[0].endswith(MediaHelper.VIDEO_EXT)

    @staticmethod
    async def send_media_message(message, media_url: Optional[str], caption: str,
                                  reply_markup, is_video: bool = False,
                                  display_options: Optional[DisplayOptions] = None):
        opts = display_options or DisplayOptions()

        if opts.show_url and media_url:
            caption += f"\n\n🔗 <code>{media_url}</code>"

        is_video = opts.video_support and (is_video or MediaHelper.is_video_url(media_url))

        if not opts.preview_image or not media_url:
            return await message.reply_text(caption, reply_markup=reply_markup, parse_mode='HTML')

        try:
            if is_video:
                return await message.reply_video(
                    video=media_url, caption=caption, reply_markup=reply_markup,
                    parse_mode='HTML', supports_streaming=True,
                    read_timeout=120, write_timeout=120
                )
            return await message.reply_photo(
                photo=media_url, caption=caption, reply_markup=reply_markup, parse_mode='HTML'
            )
        except TelegramError as e:
            LOGGER.warning(f"Media send failed, falling back to text: {e}")
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

        message = self.style['header'].format(
            user_mention=user_mention,
            page=self.page + 1,
            total_pages=self.total_pages
        )

        grouped = self.collection.group_by_anime(characters)
        counts = self.collection.count_by_id(self.collection.characters)
        seen = set()

        for anime, chars in grouped.items():
            user_count = sum(1 for c in self.collection.characters if c.anime == anime)
            
            formatted_anime = to_small_caps(escape(anime))
            message += self.style['anime_header'].format(
                anime=formatted_anime,
                user_count=user_count,
                total_count=anime_counts.get(anime, 0)
            )
            message += self.style['separator']

            for char in chars:
                if char.id in seen:
                    continue
                message += self._format_character(char, counts.get(char.id, 1))
                seen.add(char.id)

            message += self.style['footer']

        return message

    def _format_character(self, char: Character, count: int) -> str:
        char_id = str(char.id).zfill(3)
        rarity = rarity_emoji(char.rarity)
        
        formatted_name = to_small_caps(escape(char.name))
        event_str = f" [{char.event_emoji}]" if char.event_emoji else ""

        return self.style['character'].format(
            id=char_id,
            rarity=rarity,
            name=formatted_name,
            event=event_str,
            count=count
        )


class HaremHandler:
    CHARACTERS_PER_PAGE = 10

    def __init__(self):
        self.collection_db = db['anime_characters_lol']
        self.user_db = db['user_collection_lmaoooo']

    async def load_user_collection(self, user_id: int) -> Optional[UserCollection]:
        user = await self.user_db.find_one({'id': user_id})
        if not user:
            return None

        characters = [c for c in (Character.from_dict(char) for char in user.get('characters', [])) if c]
        favorite = Character.from_dict(user.get('favorites')) if user.get('favorites') else None

        if favorite and not any(c.id == favorite.id for c in characters):
            asyncio.create_task(self.user_db.update_one({'id': user_id}, {'$unset': {'favorites': ""}}))
            favorite = None

        return UserCollection(
            user_id=user_id, characters=characters, favorite=favorite,
            filter_mode=user.get('smode', 'default')
        )

    async def update_live_data(self, characters: List[Character]):
        if not characters:
            return
        unique_ids = list({c.id for c in characters})
        live_cursor = self.collection_db.find({"id": {"$in": unique_ids}})
        live_docs = await live_cursor.to_list(length=None)
        live_map = {str(doc.get('id')): doc for doc in live_docs}
        
        for c in characters:
            if c.id in live_map:
                doc = live_map[c.id]
                c.name = doc.get('name', c.name)
                c.anime = doc.get('anime', c.anime)
                c.rarity = doc.get('rarity', c.rarity) 
                if doc.get('img_url'):
                    c.img_url = doc.get('img_url')
                c.is_video = doc.get('is_video', c.is_video)
                c.gender = doc.get('gender', c.gender)

    async def get_anime_counts(self, anime_list: List[str]) -> Dict[str, int]:
        if not anime_list:
            return {}
        
        pipeline = [
            {"$match": {"anime": {"$in": anime_list}}},
            {"$group": {"_id": "$anime", "count": {"$sum": 1}}}
        ]
        
        counts = {}
        cursor = self.collection_db.aggregate(pipeline)
        docs = await cursor.to_list(length=None)
        
        for doc in docs:
            counts[doc['_id']] = doc['count']
        return counts

    def _build_keyboard(self, page: int, total_pages: int, total_chars: int, user_id: int, step: int = 1) -> InlineKeyboardMarkup:
        keyboard = [[InlineKeyboardButton(
            f"✨ ʜᴀʀᴇᴍ ({total_chars})", switch_inline_query_current_chat=f"collection.{user_id}"
        )]]

        nav = []
        if page > 0:
            prev_page = max(0, page - step)
            nav.append(InlineKeyboardButton("ᴘʀᴇᴠ", callback_data=f"harem_page:{prev_page}:{user_id}:{step}"))
        if page < total_pages - 1:
            next_page = min(total_pages - 1, page + step)
            nav.append(InlineKeyboardButton("ɴᴇxᴛ", callback_data=f"harem_page:{next_page}:{user_id}:{step}"))
        if nav:
            keyboard.append(nav)

        # Skip button setup with Toggle logic
        if total_pages > 2:
            if step == 1:
                keyboard.append([InlineKeyboardButton("⭆ 2x", callback_data=f"harem_2x:{page}:{user_id}:2")])
            else:
                keyboard.append([InlineKeyboardButton("⭆ 1x", callback_data=f"harem_2x:{page}:{user_id}:1")])

        keyboard.append([InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data=f"harem_close:{user_id}")])
        return InlineKeyboardMarkup(keyboard)

    async def show_harem(self, update: Update, context: CallbackContext, page: int = 0, edit: bool = False, step: int = 1):
        user = update.effective_user
        user_id = user.id
        user_name = user.first_name
        message = update.message or update.callback_query.message

        collection = await self.load_user_collection(user_id)
        if not collection:
            await message.reply_text("<b><tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> ʏᴏᴜ ɴᴇᴇᴅ ᴛᴏ ɢʀᴀʙ ᴀ ᴄʜᴀʀᴀᴄᴛᴇʀ ғɪʀsᴛ ᴜsɪɴɢ /grab ᴄᴏᴍᴍᴀɴᴅ!</b>", parse_mode='HTML')
            return
        if not collection.characters:
            await message.reply_text("<b><tg-emoji emoji-id=\"5433653135799228968\">📁</tg-emoji> ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ᴄʜᴀʀᴀᴄᴛᴇʀs ʏᴇᴛ! ᴜsᴇ /grab ᴛᴏ ᴄᴀᴛᴄʜ sᴏᴍᴇ.</b>", parse_mode='HTML')
            return

        display_order = collection.get_filtered_characters()
        if not display_order:
            await message.reply_text(
                f"<b>ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ᴄʜᴀʀᴀᴄᴛᴇʀs ᴡɪᴛʜ ᴛʜɪs ᴍᴏᴅᴇ: {rarity_premium_display(collection.filter_mode) if collection.filter_mode in RARITIES else collection.filter_mode}</b>\n"
                f"<b><tg-emoji emoji-id=\"5422439311196834318\">💡</tg-emoji> ᴄʜᴀɴɢᴇ ᴍᴏᴅᴇ ᴜsɪɴɢ /smode</b>",
                parse_mode='HTML'
            )
            return

        total_pages = math.ceil(len(display_order) / self.CHARACTERS_PER_PAGE)
        page = max(0, min(page, total_pages - 1))

        start = page * self.CHARACTERS_PER_PAGE
        current = display_order[start:start + self.CHARACTERS_PER_PAGE]

        chars_to_update = list(current)
        display_char = collection.favorite if collection.favorite else (random.choice(display_order) if display_order else None)
        if display_char:
            chars_to_update.append(display_char)
            
        await self.update_live_data(chars_to_update)

        style, options = DEFAULT_STYLE, DEFAULT_OPTIONS
        anime_counts = await self.get_anime_counts(list({c.anime for c in current}))
        
        builder = HaremMessageBuilder(collection, page, total_pages, style, options, user_name, user_id)
        text = builder.build_message(current, anime_counts)
        markup = self._build_keyboard(page, total_pages, len(display_order), user_id, step)

        media_url = display_char.img_url if display_char else None
        is_video = display_char.is_video if display_char else False

        if media_url and edit:
            try:
                await message.edit_caption(caption=text, reply_markup=markup, parse_mode='HTML')
                return
            except TelegramError as e:
                # Ignored to prevent creating new duplicate harem messages
                if "not modified" in str(e).lower():
                    return
                LOGGER.warning(f"ᴇᴅɪᴛ ғᴀɪʟᴇᴅ, ʀᴇsᴇɴᴅɪɴɢ: {e}")

        if media_url:
            await MediaHelper.send_media_message(message, media_url, text, markup, is_video, options)
        elif edit:
            try:
                await message.edit_text(text=text, reply_markup=markup, parse_mode='HTML')
            except TelegramError as e:
                if "not modified" in str(e).lower():
                    return
                LOGGER.warning(f"ᴇᴅɪᴛ ᴛᴇxᴛ ғᴀɪʟᴇᴅ: {e}")
                await message.reply_text(text=text, reply_markup=markup, parse_mode='HTML')
        else:
            await message.reply_text(text=text, reply_markup=markup, parse_mode='HTML')


class ModeHandler:
    IMG = "https://files.catbox.moe/sgo9in.png"
    LABELS = {"default": "ᴅᴇғᴀᴜʟᴛ", "latest": "ʟᴀᴛᴇsᴛ", "animes": "ᴀɴɪᴍᴇs", "waifus": "ᴡᴀɪғᴜs"}

    def __init__(self):
        self.user_db = db['user_collection_lmaoooo']

    async def _current_mode(self, user_id: int) -> str:
        user = await self.user_db.find_one({'id': user_id})
        return user.get('smode', 'default') if user else 'default'

    def _keyboard(self, current: str) -> InlineKeyboardMarkup:
        def label(key, text):
            return f"{text} ✓" if key == current else text

        rarity_label = label("rarity", "ʀᴀʀɪᴛʏ") if current in RARITIES else "ʀᴀʀɪᴛʏ"
        rows = [
            [InlineKeyboardButton(label("default", "ᴅᴇғᴀᴜʟᴛ"), callback_data="harem_mode_default"),
             InlineKeyboardButton(rarity_label, callback_data="harem_mode_rarity")],
            [InlineKeyboardButton(label("latest", "ʟᴀᴛᴇsᴛ"), callback_data="harem_mode_latest"),
             InlineKeyboardButton(label("animes", "ᴀɴɪᴍᴇs"), callback_data="harem_mode_animes")],
            [InlineKeyboardButton(label("waifus", "ᴡᴀɪғᴜs"), callback_data="harem_mode_waifus"),
             InlineKeyboardButton("⤬", callback_data="harem_mode_close")],
        ]
        return InlineKeyboardMarkup(rows)

    async def show_mode_menu(self, update: Update, user_id: int):
        markup = self._keyboard(await self._current_mode(user_id))
        caption = "<b>ᴄʜᴏᴏsᴇ ᴏɴᴇ ᴏғ ᴡᴀʏs ᴛᴏ sᴏʀᴛ ʏᴏᴜʀ ʜᴀʀᴇᴍ</b>"
        if update.callback_query:
            await update.callback_query.edit_message_caption(caption=caption, reply_markup=markup, parse_mode='HTML')
        else:
            await update.message.reply_photo(self.IMG, caption=caption, reply_markup=markup, parse_mode='HTML')

    async def show_rarity_menu(self, query):
        buttons = [InlineKeyboardButton(db_emoji, callback_data=f"harem_mode_{key}") for key, (db_emoji, _, _) in RARITIES.items()]
        keyboard = chunk(buttons, 3) + [[InlineKeyboardButton("↻ ʙᴀᴄᴋ", callback_data="harem_mode_back")]]
        await query.edit_message_caption(
            caption="<b><tg-emoji emoji-id=\"5260426225599405269\">🪄</tg-emoji> sᴇʟᴇᴄᴛ ᴀ ʀᴀʀɪᴛʏ ᴛᴏ ғɪʟᴛᴇʀ ʏᴏᴜʀ ʜᴀʀᴇᴍ</b>",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML'
        )

    async def set_mode(self, user_id: int, mode: str):
        await self.user_db.update_one({'id': user_id}, {'$set': {'smode': mode}}, upsert=True)

    async def handle_mode_callback(self, update: Update, context: CallbackContext):
        query = update.callback_query
        user_id = query.from_user.id
        action = query.data.replace("harem_mode_", "")

        if action == "rarity":
            await query.answer()
            return await self.show_rarity_menu(query)

        if action == "back":
            await query.answer()
            return await self.show_mode_menu(update, user_id)

        if action == "close":
            await query.answer()
            return await query.message.delete()

        label = self.LABELS.get(action) or (RARITIES[action][2] if action in RARITIES else None)
        if not label:
            return await query.answer("ɪɴᴠᴀʟɪᴅ ᴏᴘᴛɪᴏɴ", show_alert=True)

        await self.set_mode(user_id, action)
        await query.answer(f"✓ {label} sᴇʟᴇᴄᴛᴇᴅ")
        await self.show_mode_menu(update, user_id)


class UnfavHandler:
    def __init__(self):
        self.user_db = db['user_collection_lmaoooo']

    async def show_unfav_prompt(self, update: Update):
        user_id = update.effective_user.id
        user = await self.user_db.find_one({'id': user_id})

        if not user:
            await update.message.reply_text('<b><tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> ʏᴏᴜ ʜᴀᴠᴇ ɴᴏᴛ ɢᴏᴛ ᴀɴʏ ᴄʜᴀʀᴀᴄᴛᴇʀ ʏᴇᴛ!</b>', parse_mode='HTML')
            return

        fav = Character.from_dict(user.get('favorites'))
        if not fav:
            await update.message.reply_text("<b><tg-emoji emoji-id=\"5278454020111887994\">💔</tg-emoji> ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀ ғᴀᴠᴏʀɪᴛᴇ ᴄʜᴀʀᴀᴄᴛᴇʀ sᴇᴛ!</b>", parse_mode='HTML')
            return

        buttons = [[
            InlineKeyboardButton("✓ ʏᴇs", callback_data=f"harem_unfav_yes:{user_id}"),
            InlineKeyboardButton("⤬ ɴᴏ", callback_data=f"harem_unfav_no:{user_id}")
        ]]
        caption = (
            f"<b><tg-emoji emoji-id=\"5278454020111887994\">💔</tg-emoji> ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʀᴇᴍᴏᴠᴇ ᴛʜɪs ғᴀᴠᴏʀɪᴛᴇ?</b>\n\n"
            f"<b><tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> ɴᴀᴍᴇ:</b> <code>{escape(to_small_caps(fav.name))}</code>\n"
            f"<b><tg-emoji emoji-id=\"6312254267461739671\">⛩</tg-emoji> ᴀɴɪᴍᴇ:</b> <code>{escape(to_small_caps(fav.anime))}</code>\n"
            f"<b><tg-emoji emoji-id=\"6332443074769196273\">🆔</tg-emoji> ɪᴅ:</b> <code>{fav.id}</code>"
        )
        await MediaHelper.send_media_message(
            update.message, fav.img_url, caption, InlineKeyboardMarkup(buttons), fav.is_video, DEFAULT_OPTIONS
        )

    async def handle_unfav_callback(self, update: Update):
        query = update.callback_query
        action, _, user_id_str = query.data.partition(':')
        user_id = await verify_owner(query, user_id_str)
        if user_id is None:
            return
        await query.answer()

        if action == 'harem_unfav_yes':
            user = await self.user_db.find_one({'id': user_id})
            fav = Character.from_dict(user.get('favorites')) if user else None
            if not fav:
                await query.answer("ɴᴏ ғᴀᴠᴏʀɪᴛᴇ ғᴏᴜɴᴅ!", show_alert=True)
                return

            await self.user_db.update_one({'id': user_id}, {'$unset': {'favorites': ""}})
            await query.edit_message_caption(
                caption=(
                    f"<b><tg-emoji emoji-id=\"5278454020111887994\">💔</tg-emoji> ғᴀᴠᴏʀɪᴛᴇ ʀᴇᴍᴏᴠᴇᴅ!</b>\n\n"
                    f"<b><tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> ɴᴀᴍᴇ:</b> <code>{escape(to_small_caps(fav.name))}</code>\n"
                    f"<b><tg-emoji emoji-id=\"6312254267461739671\">⛩</tg-emoji> ᴀɴɪᴍᴇ:</b> <code>{escape(to_small_caps(fav.anime))}</code>\n\n"
                    f"<b><i><tg-emoji emoji-id=\"5276239041052828276\">🎭</tg-emoji> ʏᴏᴜ ᴄᴀɴ sᴇᴛ ᴀ ɴᴇᴡ ғᴀᴠᴏʀɪᴛᴇ ᴜsɪɴɢ /fav</i></b>"
                ),
                parse_mode='HTML'
            )
        elif action == 'harem_unfav_no':
            await query.edit_message_caption(caption="<b>ᴀᴄᴛɪᴏɴ ᴄᴀɴᴄᴇʟᴇᴅ. ғᴀᴠᴏʀɪᴛᴇ ᴋᴇᴘᴛ.</b>", parse_mode='HTML')


async def verify_owner(query, user_id_str: str) -> Optional[int]:
    try:
        owner_id = int(user_id_str)
    except ValueError:
        await query.answer("ɪɴᴠᴀʟɪᴅ ᴅᴀᴛᴀ!", show_alert=True)
        return None
    if query.from_user.id != owner_id:
        await query.answer("ᴛʜɪs ɪs ɴᴏᴛ ʏᴏᴜʀ ᴄᴏʟʟᴇᴄᴛɪᴏɴ!", show_alert=True)
        return None
    return owner_id


harem_handler = HaremHandler()
mode_handler = ModeHandler()
unfav_handler = UnfavHandler()


async def harem_command(update: Update, context: CallbackContext):
    try:
        await harem_handler.show_harem(update, context)
    except TelegramError as e:
        LOGGER.error(f"Error in harem_command: {e}", exc_info=True)
        await update.message.reply_text("<b><tg-emoji emoji-id=\"6307488052059053932\">🕐</tg-emoji> ʟᴏᴀᴅɪɴɢ ʜᴀʀᴇᴍ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.</b>", parse_mode='HTML')


async def harem_page_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    try:
        # Step dynamically catch hoga yaha se
        parts = query.data.split(':')
        page_str = parts[1]
        user_id_str = parts[2]
        step = int(parts[3]) if len(parts) > 3 else 1
        
        user_id = await verify_owner(query, user_id_str)
        if user_id is None:
            return
        await query.answer()
        await harem_handler.show_harem(update, context, int(page_str), edit=True, step=step)
    except (ValueError, TelegramError) as e:
        LOGGER.error(f"Error in harem_page_callback: {e}", exc_info=True)
        await query.answer("ᴇʀʀᴏʀ ʟᴏᴀᴅɪɴɢ ᴘᴀɢᴇ", show_alert=True)


async def smode_command(update: Update, context: CallbackContext):
    try:
        await mode_handler.show_mode_menu(update, update.effective_user.id)
    except TelegramError as e:
        LOGGER.error(f"Error in smode_command: {e}", exc_info=True)
        await update.message.reply_text("<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ᴇʀʀᴏʀ ʟᴏᴀᴅɪɴɢ ᴍᴏᴅᴇ ᴍᴇɴᴜ.</b>", parse_mode='HTML')


async def mode_callback(update: Update, context: CallbackContext):
    try:
        await mode_handler.handle_mode_callback(update, context)
    except TelegramError as e:
        LOGGER.error(f"Error in mode_callback: {e}", exc_info=True)


async def unfav_command(update: Update, context: CallbackContext):
    try:
        await unfav_handler.show_unfav_prompt(update)
    except TelegramError as e:
        LOGGER.error(f"Error in unfav_command: {e}", exc_info=True)
        await update.message.reply_text("<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ᴇʀʀᴏʀ ᴘʀᴏᴄᴇssɪɴɢ ᴜɴғᴀᴠ ᴄᴏᴍᴍᴀɴᴅ.</b>", parse_mode='HTML')


async def unfav_callback(update: Update, context: CallbackContext):
    try:
        await unfav_handler.handle_unfav_callback(update)
    except TelegramError as e:
        LOGGER.error(f"Error in unfav_callback: {e}", exc_info=True)


async def harem_2x_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    try:
        parts = query.data.split(':')
        curr_page_str = parts[1]
        user_id_str = parts[2]
        target_step = int(parts[3]) if len(parts) > 3 else 2
        
        user_id = await verify_owner(query, user_id_str)
        if user_id is None:
            return
            
        curr_page = int(curr_page_str)
        target_page = curr_page + target_step
        
        msg = "2x ᴘᴀɢᴇ sᴋɪᴘ ᴏɴ" if target_step == 2 else "1x (ɴᴏʀᴍᴀʟ) sᴋɪᴘ ᴏɴ"
        await query.answer(msg)
        
        await harem_handler.show_harem(update, context, target_page, edit=True, step=target_step)
    except Exception as e:
        LOGGER.error(f"Error in harem_2x_callback: {e}", exc_info=True)


async def harem_close_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    _, _, user_id_str = query.data.partition(':')
    if await verify_owner(query, user_id_str) is None:
        return
    await query.answer()
    await query.message.delete()


application.add_handler(CommandHandler(["harem", "collection"], harem_command, block=False))
application.add_handler(CommandHandler("smode", smode_command, block=False))
application.add_handler(CommandHandler("unfav", unfav_command, block=False))
application.add_handler(CallbackQueryHandler(harem_page_callback, pattern='^harem_page:', block=False))
application.add_handler(CallbackQueryHandler(mode_callback, pattern='^harem_mode_', block=False))
application.add_handler(CallbackQueryHandler(unfav_callback, pattern="^harem_unfav_", block=False))
application.add_handler(CallbackQueryHandler(harem_2x_callback, pattern='^harem_2x:', block=False))
application.add_handler(CallbackQueryHandler(harem_close_callback, pattern='^harem_close:', block=False))

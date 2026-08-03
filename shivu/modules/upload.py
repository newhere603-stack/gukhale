""" v3 - Complete Upload, Update & Delete System """

import io
import os
import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Any
from functools import wraps, lru_cache
from contextlib import asynccontextmanager
import mimetypes

import aiohttp
from aiohttp import ClientSession, TCPConnector
from pymongo import ReturnDocument
from telegram import Update, InputFile, Message
from telegram.ext import CommandHandler, ContextTypes
from telegram.error import TelegramError

from shivu import application, collection, db, CHARA_CHANNEL_ID, SUPPORT_CHAT, sudo_users

logger = logging.getLogger(__name__)


class MediaType(Enum):
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    ANIMATION = "animation"

    @classmethod
    def from_mime(cls, mime_type: str) -> 'MediaType':
        if not mime_type:
            return cls.IMAGE

        mime_lower = mime_type.lower()
        if mime_lower.startswith('video'):
            return cls.VIDEO
        elif mime_lower.startswith('image/gif'):
            return cls.ANIMATION
        elif mime_lower.startswith('image'):
            return cls.IMAGE
        return cls.DOCUMENT


class RarityLevel(Enum):
    MYTHIC = (1, "🔮 Mythic")
    COSMIC = (2, "🌌 Cosmic")
    CELESTIAL = (3, "🪽 Celestial")
    EXCLUSIVE = (4, "🥴 Exclusive")
    LEGENDARY = (5, "🟠 Legendary")
    PREMIUM = (6, "💎 Premium Edition")
    NEON = (7, "⚡ Neon")
    PEARL = (8, "🐚 Pearl")
    SWEET = (9, "🍭 Sweet")
    SPECIAL_EDITION = (10, "🟡 Special Edition")
    VALENTINE = (11, "💋 Valentine")
    WINTER = (12, "❄️ Winter")
    EROTIC = (13, "🥵 Erotic")
    RARE = (14, "🔵 Rare")
    COMMON = (15, "🟢 Common")

    def __init__(self, level: int, display: str):
        self._level = level
        self._display = display

    @property
    def level(self) -> int:
        return self._level

    @property
    def display_name(self) -> str:
        return self._display

    @property
    def emoji(self) -> str:
        return self._display.split(' ', 1)[0]

    @property
    def name_only(self) -> str:
        return self._display.split(' ', 1)[1]

    @classmethod
    @lru_cache(maxsize=32)
    def from_number(cls, num: int) -> Optional['RarityLevel']:
        for rarity in cls:
            if rarity.level == num:
                return rarity
        return None


@dataclass(frozen=True)
class Config:
    MAX_FILE_SIZE: int = 100 * 1024 * 1024
    DOWNLOAD_TIMEOUT: int = 300
    UPLOAD_TIMEOUT: int = 300
    CHUNK_SIZE: int = 65536
    CONNECTION_LIMIT: int = 100


@dataclass
class MediaFile:
    url: str
    file_bytes: Optional[bytes] = None
    media_type: MediaType = MediaType.IMAGE
    filename: str = field(default="")
    mime_type: Optional[str] = None
    size: int = 0
    hash: str = field(default="")

    def __post_init__(self):
        if not self.filename:
            object.__setattr__(self, 'filename', self._generate_filename())

        if not self.mime_type:
            object.__setattr__(self, 'mime_type', self._detect_mime_type())

        if self.file_bytes and not self.size:
            object.__setattr__(self, 'size', len(self.file_bytes))

        if self.file_bytes and not self.hash:
            object.__setattr__(self, 'hash', self._compute_hash())

    def _generate_filename(self) -> str:
        ext = self._extract_extension()
        hash_part = hashlib.md5(self.url.encode() if self.url else os.urandom(8)).hexdigest()[:8]
        return f"file_{hash_part}{ext}"

    def _extract_extension(self) -> str:
        url_lower = self.url.lower() if self.url else ""

        video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'}
        for ext in video_exts:
            if url_lower.endswith(ext):
                object.__setattr__(self, 'media_type', MediaType.VIDEO)
                return ext

        if url_lower.endswith('.gif'):
            object.__setattr__(self, 'media_type', MediaType.ANIMATION)
            return '.gif'

        image_exts = {'.jpg', '.jpeg', '.png', '.webp'}
        for ext in image_exts:
            if url_lower.endswith(ext):
                return ext

        return '.jpg'

    def _detect_mime_type(self) -> str:
        mime, _ = mimetypes.guess_type(self.filename)
        return mime or 'application/octet-stream'

    def _compute_hash(self) -> str:
        return hashlib.sha256(self.file_bytes).hexdigest()

    @property
    def is_video(self) -> bool:
        return self.media_type == MediaType.VIDEO

    @property
    def is_valid_size(self) -> bool:
        return self.size <= Config.MAX_FILE_SIZE


@dataclass
class Character:
    character_id: str
    name: str
    anime: str
    rarity: RarityLevel
    media_file: MediaFile
    uploader_id: str
    uploader_name: str
    message_id: Optional[int] = None
    file_id: Optional[str] = None
    file_unique_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.character_id,
            'name': self.name,
            'anime': self.anime,
            'rarity': self.rarity.display_name,
            'img_url': self.media_file.url,
            'is_video': self.media_file.is_video,
            'message_id': self.message_id,
            'file_id': self.file_id,
            'file_unique_id': self.file_unique_id,
            'media_type': self.media_file.media_type.value,
            'file_hash': self.media_file.hash,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

    def get_caption(self, is_update: bool = False) -> str:
        media_type = {
            MediaType.VIDEO: "🎥 Video",
            MediaType.IMAGE: "🖼 Image",
            MediaType.ANIMATION: "🎬 Animation",
            MediaType.DOCUMENT: "📄 Document"
        }.get(self.media_file.media_type, "🖼 Image")

        action = "𝑼𝒑𝒅𝒂𝒕𝒆𝒅" if is_update else "𝑴𝒂𝒅𝒆"

        return (
            f'<b>{self.character_id}:</b> {self.name}\n'
            f'<b>{self.anime}</b>\n'
            f'<b>{self.rarity.emoji} 𝙍𝘼𝙍𝙄𝙏𝙔:</b> {self.rarity.name_only}\n'
            f'<b>Type:</b> {media_type}\n\n'
            f'{action} 𝑩𝒚 ➥ <a href="tg://user?id={self.uploader_id}">{self.uploader_name}</a>'
        )


class SessionManager:
    _session: Optional[ClientSession] = None
    _lock = asyncio.Lock()

    @classmethod
    @asynccontextmanager
    async def get_session(cls):
        async with cls._lock:
            if cls._session is None or cls._session.closed:
                connector = TCPConnector(limit=Config.CONNECTION_LIMIT, ttl_dns_cache=300)
                timeout = aiohttp.ClientTimeout(total=Config.DOWNLOAD_TIMEOUT)
                cls._session = ClientSession(connector=connector, timeout=timeout)
        try:
            yield cls._session
        finally:
            pass


class SequenceGenerator:
    _lock = asyncio.Lock()

    @classmethod
    async def get_next_id(cls, sequence_name: str) -> str:
        async with cls._lock:
            sequence_collection = db.sequences
            sequence_document = await sequence_collection.find_one_and_update(
                {'_id': sequence_name},
                {'$inc': {'sequence_value': 1}},
                return_document=ReturnDocument.AFTER,
                upsert=True
            )
            value = sequence_document.get('sequence_value', 0)
            return str(value).zfill(2)


class RobustUploader:
    @staticmethod
    async def _upload_telegraph(file_bytes: bytes, filename: str) -> Optional[str]:
        try:
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('file', io.BytesIO(file_bytes), filename=filename or 'file.jpg')
                async with session.post('https://telegra.ph/upload', data=data, timeout=30) as response:
                    if response.status == 200:
                        res = await response.json()
                        if isinstance(res, list) and len(res) > 0 and 'src' in res[0]:
                            return f"https://telegra.ph{res[0]['src']}"
        except Exception:
            pass
        return None

    @staticmethod
    async def _upload_pixeldrain(file_bytes: bytes, filename: str) -> Optional[str]:
        try:
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('file', io.BytesIO(file_bytes), filename=filename or 'file.bin')
                async with session.post("https://pixeldrain.com/api/file", data=data, timeout=60) as response:
                    if response.status in (200, 201):
                        res = await response.json()
                        if res.get('id'):
                            return f"https://pixeldrain.com/api/file/{res['id']}"
        except Exception:
            pass
        return None

    @staticmethod
    async def _upload_catbox(file_bytes: bytes, filename: str) -> Optional[str]:
        try:
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('reqtype', 'fileupload')
                data.add_field('fileToUpload', io.BytesIO(file_bytes), filename=filename or 'file.bin')
                headers = {'User-Agent': 'Mozilla/5.0'}
                async with session.post("https://catbox.moe/user/api.php", data=data, headers=headers, timeout=60) as response:
                    if response.status == 200:
                        text = (await response.text()).strip()
                        if text.startswith("https://files.catbox.moe/"):
                            return text
        except Exception:
            pass
        return None

    @classmethod
    async def upload_with_progress(cls, file_bytes: bytes, filename: str = "", callback=None) -> Optional[str]:
        total_size = len(file_bytes)
        if callback:
            await callback(0, total_size)

        url = await cls._upload_telegraph(file_bytes, filename)
        if not url:
            url = await cls._upload_pixeldrain(file_bytes, filename)
        if not url:
            url = await cls._upload_catbox(file_bytes, filename)

        if callback:
            await callback(total_size, total_size)

        return url


class FileDownloader:
    @staticmethod
    async def download_from_url(url: str, callback=None) -> Optional[bytes]:
        async with SessionManager.get_session() as session:
            headers = {'User-Agent': 'Mozilla/5.0'}
            async with session.get(url, headers=headers, allow_redirects=True) as response:
                if response.status != 200:
                    return None

                total_size = int(response.headers.get('content-length', 0))
                chunks = []
                downloaded = 0

                async for chunk in response.content.iter_chunked(Config.CHUNK_SIZE):
                    if not chunk:
                        break
                    chunks.append(chunk)
                    downloaded += len(chunk)
                    if callback and total_size > 0:
                        await callback(downloaded, total_size)

                return b"".join(chunks) if chunks else None


class TelegramUploader:
    @staticmethod
    async def upload_character(character: Character, context: ContextTypes.DEFAULT_TYPE, is_update: bool = False) -> None:
        caption = character.get_caption(is_update)

        if character.media_file.file_bytes:
            fp = io.BytesIO(character.media_file.file_bytes)
            fp.name = character.media_file.filename
            message = await TelegramUploader._send_media_bytes(fp, character.media_file.media_type, caption, context)
        else:
            message = await TelegramUploader._send_media_url(character.media_file.url, character.media_file.media_type, caption, context)

        TelegramUploader._update_character_from_message(character, message)
        await collection.insert_one(character.to_dict())

    @staticmethod
    def _update_character_from_message(character: Character, message: Message):
        character.message_id = message.message_id
        if message.video:
            character.file_id = message.video.file_id
            character.file_unique_id = message.video.file_unique_id
        elif message.photo:
            character.file_id = message.photo[-1].file_id
            character.file_unique_id = message.photo[-1].file_unique_id
        elif message.document:
            character.file_id = message.document.file_id
            character.file_unique_id = message.document.file_unique_id
        elif message.animation:
            character.file_id = message.animation.file_id
            character.file_unique_id = message.animation.file_unique_id

    @staticmethod
    async def _send_media_bytes(fp: io.BytesIO, media_type: MediaType, caption: str, context: ContextTypes.DEFAULT_TYPE) -> Message:
        send_kwargs = {'chat_id': CHARA_CHANNEL_ID, 'caption': caption, 'parse_mode': 'HTML'}
        try:
            if media_type == MediaType.VIDEO:
                return await context.bot.send_video(video=InputFile(fp), supports_streaming=True, **send_kwargs)
            elif media_type == MediaType.ANIMATION:
                return await context.bot.send_animation(animation=InputFile(fp), **send_kwargs)
            elif media_type == MediaType.IMAGE:
                return await context.bot.send_photo(photo=InputFile(fp), **send_kwargs)
            else:
                return await context.bot.send_document(document=InputFile(fp), **send_kwargs)
        except TelegramError:
            return await context.bot.send_document(document=InputFile(fp), **send_kwargs)

    @staticmethod
    async def _send_media_url(url: str, media_type: MediaType, caption: str, context: ContextTypes.DEFAULT_TYPE) -> Message:
        send_kwargs = {'chat_id': CHARA_CHANNEL_ID, 'caption': caption, 'parse_mode': 'HTML'}
        try:
            if media_type == MediaType.VIDEO:
                return await context.bot.send_video(video=url, supports_streaming=True, **send_kwargs)
            elif media_type == MediaType.ANIMATION:
                return await context.bot.send_animation(animation=url, **send_kwargs)
            elif media_type == MediaType.IMAGE:
                return await context.bot.send_photo(photo=url, **send_kwargs)
            else:
                return await context.bot.send_document(document=url, **send_kwargs)
        except TelegramError:
            return await context.bot.send_document(document=url, **send_kwargs)


class TextFormatter:
    @staticmethod
    def format_name(name: str) -> str:
        return name.replace('-', ' ').replace('_', ' ').title().strip()


class CharacterFactory:
    @staticmethod
    async def create_from_args(args: List[str], media_file: MediaFile, user_id: str, user_name: str) -> Optional[Character]:
        if len(args) < 3:
            return None

        character_name = TextFormatter.format_name(args[0])
        anime = TextFormatter.format_name(args[1])

        try:
            rarity_num = int(args[2])
            rarity = RarityLevel.from_number(rarity_num)
            if not rarity:
                return None
        except ValueError:
            return None

        char_id = await SequenceGenerator.get_next_id('character_id')

        from datetime import datetime
        timestamp = datetime.utcnow().isoformat()

        return Character(
            character_id=char_id,
            name=character_name,
            anime=anime,
            rarity=rarity,
            media_file=media_file,
            uploader_id=user_id,
            uploader_name=user_name,
            created_at=timestamp,
            updated_at=timestamp
        )


class ProgressTracker:
    def __init__(self, message: Message):
        self.message = message
        self.last_update = 0

    async def update(self, current: int, total: int):
        import time
        now = time.time()
        if now - self.last_update < 2 and current < total:
            return

        self.last_update = now
        percent = (current / total * 100) if total > 0 else 0
        progress_bar = '█' * int(10 * percent / 100) + '░' * (10 - int(10 * percent / 100))

        try:
            await self.message.edit_text(
                f'⏳ Progress: {progress_bar} {percent:.1f}%\n'
                f'📊 {current / 1048576:.2f} MB / {total / 1048576:.2f} MB'
            )
        except Exception:
            pass


class CharacterUploadHandler:
    @staticmethod
    async def handle_reply_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        reply_msg = update.message.reply_to_message
        if not (reply_msg.photo or reply_msg.video or reply_msg.document or reply_msg.animation):
            await update.message.reply_text('❌ Please reply to a photo, video, animation, or document!')
            return

        if len(context.args) != 3:
            await update.message.reply_text(
                '❌ Format: `/upload character-name anime-name rarity-number`\n'
                'Example: `/upload muzan-kibutsuji Demon-slayer 3`'
            )
            return

        processing_msg = await update.message.reply_text('⏳ Extracting media...')

        media_file = await CharacterUploadHandler._extract_media_from_reply(reply_msg, update)
        if not media_file:
            await processing_msg.edit_text('❌ Failed to extract media file.')
            return

        progress = ProgressTracker(processing_msg)
        await processing_msg.edit_text('⏳ Uploading file to server...')

        file_url = await RobustUploader.upload_with_progress(
            media_file.file_bytes,
            media_file.filename,
            progress.update
        )

        if not file_url:
            await processing_msg.edit_text('❌ Server upload failed! Please try again.')
            return

        object.__setattr__(media_file, 'url', file_url)
        await processing_msg.edit_text('✅ File uploaded!\n⏳ Saving character...')

        character = await CharacterFactory.create_from_args(
            context.args,
            media_file,
            str(update.effective_user.id),
            update.effective_user.first_name
        )

        if not character:
            await processing_msg.edit_text('❌ Invalid rarity number (1-15).')
            return

        await TelegramUploader.upload_character(character, context)

        await processing_msg.edit_text(
            f'✅ Character uploaded successfully!\n'
            f'🆔 ID: {character.character_id}\n'
            f'📁 Type: {character.media_file.media_type.value.title()}'
        )

    @staticmethod
    async def handle_url_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if len(context.args) != 4:
            await update.message.reply_text(
                '❌ Format: `/upload URL character-name anime-name rarity-number`\n'
                'Example: `/upload https://site.com/image.jpg muzan Demon-slayer 3`'
            )
            return

        media_url = context.args[0]
        processing_msg = await update.message.reply_text('⏳ Downloading from URL...')

        progress = ProgressTracker(processing_msg)
        file_bytes = await FileDownloader.download_from_url(media_url, progress.update)

        if not file_bytes:
            await processing_msg.edit_text('❌ Download failed. Make sure URL is direct & public!')
            return

        media_file = MediaFile(url=media_url, file_bytes=file_bytes)

        if not media_file.is_valid_size:
            await processing_msg.edit_text('❌ File exceeds limit (100MB)!')
            return

        await processing_msg.edit_text('⏳ Uploading file to server...')
        file_url = await RobustUploader.upload_with_progress(
            file_bytes,
            media_file.filename,
            progress.update
        )

        if not file_url:
            file_url = media_url

        object.__setattr__(media_file, 'url', file_url)
        await processing_msg.edit_text('✅ Uploaded!\n⏳ Saving character...')

        character = await CharacterFactory.create_from_args(
            context.args[1:],
            media_file,
            str(update.effective_user.id),
            update.effective_user.first_name
        )

        if not character:
            await processing_msg.edit_text('❌ Invalid rarity number (1-15).')
            return

        await TelegramUploader.upload_character(character, context)

        await processing_msg.edit_text(
            f'✅ Character uploaded successfully!\n'
            f'🆔 ID: {character.character_id}\n'
            f'📁 Type: {character.media_file.media_type.value.title()}'
        )

    @staticmethod
    async def _extract_media_from_reply(reply_msg, update: Update) -> Optional[MediaFile]:
        try:
            if reply_msg.photo:
                file = await reply_msg.photo[-1].get_file()
                filename = f"char_{update.effective_user.id}_{reply_msg.photo[-1].file_unique_id}.jpg"
                media_type = MediaType.IMAGE
                mime_type = 'image/jpeg'
            elif reply_msg.video:
                file = await reply_msg.video.get_file()
                filename = f"char_{update.effective_user.id}_{reply_msg.video.file_unique_id}.mp4"
                media_type = MediaType.VIDEO
                mime_type = reply_msg.video.mime_type
            elif reply_msg.animation:
                file = await reply_msg.animation.get_file()
                filename = f"char_{update.effective_user.id}_{reply_msg.animation.file_unique_id}.gif"
                media_type = MediaType.ANIMATION
                mime_type = reply_msg.animation.mime_type
            elif reply_msg.document:
                file = await reply_msg.document.get_file()
                filename = reply_msg.document.file_name or f"doc_{update.effective_user.id}_{reply_msg.document.file_unique_id}"
                mime_type = reply_msg.document.mime_type
                media_type = MediaType.from_mime(mime_type)
            else:
                return None

            file_bytes = bytes(await file.download_as_bytearray())
            return MediaFile(
                url="",
                file_bytes=file_bytes,
                media_type=media_type,
                filename=filename,
                mime_type=mime_type,
                size=len(file_bytes)
            )
        except Exception as e:
            logger.error(f"Error extracting media: {e}")
            return None


class CharacterDeletionHandler:
    @staticmethod
    async def delete_character(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if len(context.args) != 1:
            await update.message.reply_text('❌ Format: `/delete ID`\nExample: `/delete 01`')
            return

        char_id = context.args[0]
        processing_msg = await update.message.reply_text(f'⏳ Deleting character {char_id}...')

        character = await collection.find_one_and_delete({'id': char_id})
        if not character:
            await processing_msg.edit_text(f'❌ Character {char_id} not found.')
            return

        try:
            if character.get('message_id'):
                await context.bot.delete_message(chat_id=CHARA_CHANNEL_ID, message_id=character['message_id'])
        except Exception:
            pass

        await processing_msg.edit_text(
            f'✅ Character deleted successfully!\n'
            f'🆔 ID: {char_id}\n'
            f'📝 Name: {character.get("name", "Unknown")}'
        )


class CharacterUpdateHandler:
    VALID_FIELDS = {'img_url', 'name', 'anime', 'rarity'}

    @staticmethod
    async def update_character(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if len(context.args) != 3:
            await update.message.reply_text(
                '❌ Format: `/update ID field new_value`\n\n'
                'Valid fields: img_url, name, anime, rarity\n'
                'Example: `/update 01 name New-Name`'
            )
            return

        char_id, field, new_value = context.args

        if field not in CharacterUpdateHandler.VALID_FIELDS:
            await update.message.reply_text(f'❌ Invalid field. Valid fields: {", ".join(CharacterUpdateHandler.VALID_FIELDS)}')
            return

        character_data = await collection.find_one({'id': char_id})
        if not character_data:
            await update.message.reply_text(f'❌ Character {char_id} not found.')
            return

        processing_msg = await update.message.reply_text(f'⏳ Updating {field}...')

        try:
            update_data = {}
            if field in ['name', 'anime']:
                update_data[field] = TextFormatter.format_name(new_value)
            elif field == 'rarity':
                rarity = RarityLevel.from_number(int(new_value))
                if not rarity:
                    await processing_msg.edit_text('❌ Invalid rarity number (1-15).')
                    return
                update_data[field] = rarity.display_name
            elif field == 'img_url':
                file_bytes = await FileDownloader.download_from_url(new_value)
                if not file_bytes:
                    await processing_msg.edit_text('❌ Failed to download new image URL.')
                    return
                file_url = await RobustUploader.upload_with_progress(file_bytes)
                update_data['img_url'] = file_url or new_value

            from datetime import datetime
            update_data['updated_at'] = datetime.utcnow().isoformat()

            await collection.find_one_and_update({'id': char_id}, {'$set': update_data})
            await processing_msg.edit_text(f'✅ Character {char_id} updated successfully!')
        except Exception as e:
            await processing_msg.edit_text(f'❌ Update failed: {str(e)}')


def require_sudo(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if user_id not in sudo_users:
            await update.message.reply_text('❌ Access Denied: Sudo required.')
            return
        return await func(update, context)
    return wrapper


@require_sudo
async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if update.message.reply_to_message and len(context.args) == 3:
            await CharacterUploadHandler.handle_reply_upload(update, context)
        elif len(context.args) == 4:
            await CharacterUploadHandler.handle_url_upload(update, context)
        else:
            await update.message.reply_text(
                '❌ Invalid format!\n\n'
                '👉 Reply to media: `/upload name anime rarity`\n'
                '👉 Using URL: `/upload URL name anime rarity`'
            )
    except Exception as e:
        await update.message.reply_text(f'❌ Upload failed: {str(e)}')


@require_sudo
async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await CharacterDeletionHandler.delete_character(update, context)
    except Exception as e:
        await update.message.reply_text(f'❌ Deletion failed: {str(e)}')


@require_sudo
async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await CharacterUpdateHandler.update_character(update, context)
    except Exception as e:
        await update.message.reply_text(f'❌ Update failed: {str(e)}')


application.add_handler(CommandHandler('upload', upload_command, block=False))
application.add_handler(CommandHandler('delete', delete_command, block=False))
application.add_handler(CommandHandler('update', update_command, block=False))

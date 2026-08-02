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

USERS_PER_PAGE, CHARS_PER_PAGE = 10, 15


@dataclass
class Char:
    id: str; name: str; anime: str; rarity: str; img_url: str
    is_video: bool = False; price: int = 0

    @classmethod
    def from_dict(cls, d: Dict) -> 'Char':
        return cls(d.get('id', '??'), d.get('name', 'Unknown'), d.get('anime', 'Unknown'),
                    d.get('rarity', '🟢 Common'), d.get('img_url', ''), d.get('is_video', False),
                    d.get('price', 0))


def rarity_parts(rarity) -> Tuple[str, str]:
    if isinstance(rarity, str):
        p = rarity.split(' ', 1)
        return (p[0], p[1] if len(p) > 1 else 'Common')
    return '🟢', 'Common'


async def get_char(cid: str) -> Optional[Char]:
    if cid in char_cache:
        return char_cache[cid]
    d = await collection.find_one({'id': cid})
    if d:
        char_cache[cid] = Char.from_dict(d)
        return char_cache[cid]
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
        n = await user_collection.count_documents({'characters.id': cid})
    except Exception:
        n = 0
    user_cache[key] = n
    return n


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


# --- ✨ COOL & AESTHETIC CARD INFO DESIGN ---
def card_caption(char: Char, gcount: int) -> str:
    emoji, text = rarity_parts(char.rarity)
    return (
        "┏━━ <b>ᴜʟᴛɪᴍᴀᴛᴇ ᴡᴀɪғᴜ ɪɴғᴏ</b>\n"
        "┃\n"
        f"┣ ⚡ <b>ɴᴀᴍᴇ ⬡</b> <code>{escape(char.name)}</code>\n"
        f"┣ 🌟 <b>ʀᴀʀɪᴛʏ ⬡</b> {emoji} <b>{text}</b>\n"
        f"┣ 🎬 <b>ᴀɴɪᴍᴇ ⬡</b> <i>{escape(char.anime)}</i>\n"
        f"┣ 🆔 <b>ᴄʜᴀʀ ɪᴅ ⬡</b> <code>{char.id}</code>\n"
        "┃\n"
        f"┗━━ 🌍 <b>ɢʟᴏʙᴀʟʟʏ ɢʀᴀʙʙᴇᴅ : {gcount}x</b>"
    )


def find_caption(query: str, r: Dict, page: int, show_all: bool) -> Tuple[str, int]:
    total_pages = 1 if show_all else max(1, (r['unique'] + CHARS_PER_PAGE - 1) // CHARS_PER_PAGE)
    lines = [
        "╔══ 🔍 <b>ᴀɴɪᴍᴇ sᴇᴀʀᴄʜ ʀᴇsᴜʟᴛs</b> 🔍",
        "║",
        f"╠ 📂 <b>ǫᴜᴇʀʏ ⬡</b> <i>{escape(query)}</i>",
        f"╠ 📊 <b>ᴛᴏᴛᴀʟ ⬡</b> <code>{r['total']}</code> | <b>ᴜɴɪǫᴜᴇ ⬡</b> <code>{r['unique']}</code>",
        "╚═══════════════════════\n"
    ]
    items = sorted(r['names'].items())
    s, e = (0, len(items)) if show_all else (page * CHARS_PER_PAGE, page * CHARS_PER_PAGE + CHARS_PER_PAGE)
    for i, (name, cnt) in enumerate(items[s:e], s + 1):
        c = r['data'][name]
        emoji, text = rarity_parts(c.get('rarity', '🟢 Common'))
        lines.append(f"<b>{i}.</b> <code>{escape(name)}</code> ⦅<code>{c.get('id','??')}</code>⦆ {emoji} <i>{text}</i>"
                      + (f" <b>(x{cnt})</b>" if cnt > 1 else ""))
    if not show_all and total_pages > 1:
        lines.append(f"\n📄 <b>ᴘᴀɢᴇ {page+1}/{total_pages}</b>")
    return "\n".join(lines), total_pages


async def send_media(update: Update, char: Char, caption: str, kb=None) -> None:
    try:
        method = update.message.reply_video if char.is_video else update.message.reply_photo
        kwargs = {'caption': caption, 'parse_mode': ParseMode.HTML}
        if kb:
            kwargs['reply_markup'] = kb
        await method(video=char.img_url, **kwargs) if char.is_video else await method(photo=char.img_url, **kwargs)
    except TelegramError as e:
        await update.message.reply_text(f"{caption}\n\n⚠️ ᴍᴇᴅɪᴀ ᴇʀʀᴏʀ: {escape(str(e))}",
                                         reply_markup=kb, parse_mode=ParseMode.HTML)


async def check_character(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        return await update.message.reply_text("✨ <b>ᴜsᴀɢᴇ:</b> <code>/check &lt;ɪᴅ&gt;</code>", parse_mode=ParseMode.HTML)
    char = await get_char(context.args[0])
    if not char:
        return await update.message.reply_text("<b>ᴄʜᴀʀᴀᴄᴛᴇʀ ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ ᴅᴀᴛᴀʙᴀsᴇ!</b>", parse_mode=ParseMode.HTML)
    gcount = await global_count(char.id)
    await send_media(update, char, card_caption(char, gcount))


async def find_anime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        return await update.message.reply_text("✨ <b>ᴜsᴀɢᴇ:</b> <code>/anime &lt;ɴᴀᴍᴇ&gt;</code>", parse_mode=ParseMode.HTML)
    name = ' '.join(context.args)
    chars = await find_by_anime(name)
    if not chars:
        return await update.message.reply_text(f"<b>ɴᴏ ᴄʜᴀʀᴀᴄᴛᴇʀs ғᴏᴜɴᴅ ғʀᴏᴍ</b> <i>{escape(name)}</i>", parse_mode=ParseMode.HTML)
    r = process_search(chars)
    text, _ = find_caption(name, r, 0, True)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# --- ✨ REGISTERING ONLY CHECK & ANIME COMMANDS ---
application.add_handler(CommandHandler("check", check_character, block=False))
application.add_handler(CommandHandler("anime", find_anime, block=False))

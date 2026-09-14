import asyncio
import traceback
import time
from html import escape
from datetime import datetime, timezone
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode
from telegram.error import TelegramError

# ✨ Cache clear import for instant updates ✨
try:
    from shivu.modules.check import clear_char_cache
except ImportError:
    def clear_char_cache(cid): pass

from shivu import LOGGER, application, user_collection, collection, db

# Nayi collection auto-delete memory ke liye
delete_collection = db['auto_delete_queue']

# --- CONFIGURATION ---
LOG_CHANNEL_ID = -1003893927065
GIFT_TIMEOUT = 60
MAX_INVENTORY_SIZE = 1000 
pending_gifts = {}
gift_tasks = {}

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

# 🔥 UNIFIED RARITY DICTIONARY (cosmic → Video Edition)
RARITIES = {
    "mythic": ("💎", '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>', "Mythic"),
    "cosmic": ("🌌", '<tg-emoji emoji-id="5431783411981228752">🌌</tg-emoji>', "Video Edition"),
    "celestial": ("🪽", '<tg-emoji emoji-id="5434121252874756456">🪽</tg-emoji>', "Celestial"),
    "exclusive": ("💮", '<tg-emoji emoji-id="6100567406889935797">💮</tg-emoji>', "Exclusive"),
    "legendary": ("🟡", '<tg-emoji emoji-id="6084550327086883643">🟡</tg-emoji>', "Legendary"),
    "premium": ("🔮", '<tg-emoji emoji-id="6093919703753831564">🔮</tg-emoji>', "Premium Edition"),
    "neon": ("⚡", '<tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>', "Neon"),
    "summer": ("⛱️", '<tg-emoji emoji-id="5433645645376264953">⛱️</tg-emoji>', "Summer"),
    "sweet": ("🍭", '<tg-emoji emoji-id="6222115531122546353">🍭</tg-emoji>', "Sweet"),
    "special": ("🔴", '<tg-emoji emoji-id="6093741664474504699">🔴</tg-emoji>', "Medium"),
    "valentine": ("💞", '<tg-emoji emoji-id="5255861796350224063">💞</tg-emoji>', "Valentine"),
    "winter": ("❄️", '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>', "Winter"),
    "erotic": ("🥵", '<tg-emoji emoji-id="6093490292923574796">🥵</tg-emoji>', "Spicy"),
    "rare": ("🟠", '<tg-emoji emoji-id="5339390195768774311">🟠</tg-emoji>', "Rare"),
    "common": ("🟢", '<tg-emoji emoji-id="6093865707424980866">🟢</tg-emoji>', "Common")
}

# 🔥 SEARCH ALIASES — "cosmic"/"video"/"video edition" all resolve to same key
RARITY_ALIASES = {
    "cosmic": "cosmic",
    "video": "cosmic",
    "video edition": "cosmic",
    "videoedition": "cosmic",
    "video editing": "cosmic",
    "videoediting": "cosmic",
    "video edit": "cosmic",
    "videoedit": "cosmic",
    "video edits": "cosmic",
    "videoedits": "cosmic",
}

def canonical_rarity(name: str) -> str:
    """Returns canonical rarity key (lowercase). Aliases map to same key."""
    if not name:
        return "common"
    n = str(name).strip().lower()
    if n in RARITY_ALIASES:
        return RARITY_ALIASES[n]
    if n in RARITIES:
        return n
    for key, (_, _, disp) in RARITIES.items():
        if key in n or disp.lower() in n:
            return key
    return "common"

def get_rarity_display(rarity_str) -> str:
    """Returns full premium emoji + display name string for a rarity."""
    key = canonical_rarity(rarity_str)
    _, prem_emoji, disp_name = RARITIES[key]
    return f"{prem_emoji} <b>{to_small_caps(disp_name)}</b>"

# 🔥 NEW: Normalize ID (09 → 9) for perfect matching (check code jaisa)
def normalize_id(cid) -> str:
    cid_str = str(cid).strip()
    if cid_str.isdigit():
        return cid_str.lstrip('0') or '0'
    return cid_str

def get_search_ids(cid) -> list:
    """Generates all possible ID combos (string + int) to match DB perfectly."""
    cid_str = str(cid)
    search_ids = [cid_str]
    if cid_str.isdigit():
        cleaned = cid_str.lstrip('0') or '0'
        search_ids.extend([
            cleaned,              # "9"
            cleaned.zfill(2),     # "09"
            cleaned.zfill(3),     # "009"
            cleaned.zfill(4),     # "0009"
            int(cleaned)          # 9 (Integer)
        ])
    return list(set(search_ids))

# --- ✨ UPGRADED MODERN UI STYLES ---
class Style:
    GIFT = '<tg-emoji emoji-id="5255861796350224063">💖</tg-emoji> <b>' + to_small_caps("gift transfer hub") + '</b> <tg-emoji emoji-id="5255861796350224063">💖</tg-emoji>'
    TO = '<tg-emoji emoji-id="6337080578591956016">😆</tg-emoji> ' + to_small_caps("Rec ⬡")
    FROM = '<tg-emoji emoji-id="5305699699204837855">🍀</tg-emoji> ' + to_small_caps("sender ⬡")
    CHAR = '<tg-emoji emoji-id="6336972134962697188">🌸</tg-emoji> ' + to_small_caps("name ⬡")
    ID = '<tg-emoji emoji-id="6332443074769196273">🆔</tg-emoji> ' + to_small_caps("chr id ⬡")
    RARITY = '<tg-emoji emoji-id="6093611479720795757">💫</tg-emoji> ' + to_small_caps("rarity ⬡")
    STATUS = '<tg-emoji emoji-id="6093431129749070651">✨</tg-emoji> ' + to_small_caps("status ⬡")
    LINE = "──────────────────"
    SUCCESS = "✅ " + to_small_caps("success")

async def send_log(context: CallbackContext, text: str):
    try:
        await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        LOGGER.error(f"Log failed: {e}")

# 🔥 ADVANCED MEDIA HANDLER (Bulletproof with fallbacks + is_video hint support)
async def reply_media_message(message, media_url, caption, reply_markup=None, is_video_hint=None):
    if not media_url:
        try: return await message.reply_text(text=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        except Exception: return await message.chat.send_message(text=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    is_video_url = False
    if is_video_hint is True:
        is_video_url = True
    elif isinstance(media_url, str):
        url_lower = media_url.lower()
        if any(url_lower.endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v']) or any(pattern in url_lower for pattern in ['/video/', '/videos/', 'video=', 'v=', '.mp4?', '/stream/']):
            is_video_url = True

    try:
        if is_video_url: return await message.reply_video(video=media_url, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        else: return await message.reply_photo(photo=media_url, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except Exception:
        try:
            if not is_video_url: return await message.chat.send_video(video=media_url, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            else: return await message.chat.send_photo(photo=media_url, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        except Exception:
            try: return await message.chat.send_animation(animation=media_url, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            except Exception: return await message.chat.send_message(text=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# 🔥 PERMANENT AUTO DELETE SYSTEM 🔥
_worker_started = False

async def background_delete_worker(bot):
    global _worker_started
    if _worker_started: return
    _worker_started = True

    try: await delete_collection.create_index("delete_at")
    except Exception: pass

    while True:
        try:
            now = time.time()
            cursor = delete_collection.find({'delete_at': {'$lte': now}})
            async for doc in cursor:
                try: await bot.delete_message(chat_id=doc['chat_id'], message_id=doc['message_id'])
                except Exception: pass
                finally: await delete_collection.delete_one({'_id': doc['_id']})
        except Exception: pass
        await asyncio.sleep(20)

async def schedule_auto_delete(message, delay_seconds: int = 1200):
    if not message: return

    global _worker_started
    if not _worker_started:
        asyncio.create_task(background_delete_worker(message.get_bot()))

    chat_id = message.chat.id
    message_id = message.message_id
    delete_at = time.time() + delay_seconds

    await delete_collection.insert_one({'chat_id': chat_id, 'message_id': message_id, 'delete_at': delete_at})

    async def memory_delete():
        await asyncio.sleep(delay_seconds)
        try:
            await message.get_bot().delete_message(chat_id=chat_id, message_id=message_id)
            await delete_collection.delete_one({'chat_id': chat_id, 'message_id': message_id})
        except Exception: pass

    asyncio.create_task(memory_delete())

async def cleanup_pending_gift(sender_id: int, sent_msg=None):
    if sender_id in gift_tasks:
        gift_tasks[sender_id].cancel()
        gift_tasks.pop(sender_id, None)

    if sender_id in pending_gifts:
        if sent_msg:
            try:
                await sent_msg.delete()
                await delete_collection.delete_one({'chat_id': sent_msg.chat.id, 'message_id': sent_msg.message_id})
            except Exception: pass
        pending_gifts.pop(sender_id, None)

async def check_receiver_inventory_size(receiver_id: int) -> bool:
    # Hamesha True bypass unlimited ke liye
    return True

# --- 🔥 BULK GIFT CORE LOGIC (LIVE UPDATE FIX) ---
async def get_owned_char_and_global(sender_id, char_id_input_str, owned_map=None):
    """
    Step 1: Ownership validate karne ke liye owned_char dhoondo.
    Step 2: Display/Media ke liye ALWAYS fresh global collection se fetch karo
            (isliye photo/rarity/name change hote hi turant live update dikhega).
    """
    # ---------- STEP 1: Find owned_char (ownership only) ----------
    owned_char = None
    if owned_map and char_id_input_str in owned_map:
        owned_char = owned_map[char_id_input_str]
    else:
        char_id_input_int = int(char_id_input_str) if char_id_input_str.isdigit() else None
        sender_data = await user_collection.find_one({'id': sender_id})
        if not sender_data: return None, None

        for c in sender_data.get('characters', []):
            c_id = c.get('id')
            if str(c_id) == char_id_input_str:
                owned_char = c
                break
            if char_id_input_int is not None:
                try:
                    if int(c_id) == char_id_input_int:
                        owned_char = c
                        break
                except (ValueError, TypeError): pass

    if not owned_char: return None, None

    # ---------- STEP 2: ALWAYS fetch fresh display data from global collection ----------
    global_char = dict(owned_char)  # fallback if global missing
    try:
        search_ids = get_search_ids(char_id_input_str)
        db_char = await collection.find_one({'id': {'$in': search_ids}})
        if db_char:
            # Fresh global data use karo (live photo/name/rarity/anime update ke liye)
            global_char = dict(db_char)
    except Exception as e:
        LOGGER.error(f"Global char fetch failed: {e}")

    return owned_char, global_char

async def trigger_next_gift(sender_id, receiver_user, queue, chat_id, message_obj, owned_map):
    while queue:
        next_id_str = queue.pop(0)

        owned_char, global_char = await get_owned_char_and_global(sender_id, next_id_str, owned_map)

        if not owned_char:
            warning_text = f'<tg-emoji emoji-id="6309717264639726942">⚠️</tg-emoji> {bold_sc(f"you dont own character id {next_id_str}, skipping...")}'
            try: warning_msg = await message_obj.reply_text(warning_text, parse_mode=ParseMode.HTML)
            except Exception: warning_msg = await message_obj.chat.send_message(warning_text, parse_mode=ParseMode.HTML)
            await schedule_auto_delete(warning_msg, 15)
            continue

        is_receiver_valid = await check_receiver_inventory_size(receiver_user.id)
        if not is_receiver_valid:
            inv_text = f"receiver inventory is full. stopping bulk gift."
            try: stop_msg = await message_obj.reply_text(f"📦 {bold_sc(inv_text)}", parse_mode=ParseMode.HTML)
            except Exception: stop_msg = await message_obj.chat.send_message(f"📦 {bold_sc(inv_text)}", parse_mode=ParseMode.HTML)
            await schedule_auto_delete(stop_msg, 20)
            break

        pending_gifts[sender_id] = {
            'character': global_char,               # Fresh global data (live)
            'receiver_id': receiver_user.id,
            'receiver_name': receiver_user.first_name,
            'receiver_user': receiver_user,
            'message_id': None,
            'created_at': datetime.now(timezone.utc),
            'queue': queue,
            'chat_id': chat_id,
            'owned_map': owned_map
        }

        timeout_text = to_small_caps(f"confirm within {GIFT_TIMEOUT}s to send.")
        rarity_display = get_rarity_display(global_char.get('rarity', 'Unknown'))
        caption = (
            f"{Style.GIFT}\n"
            f"{Style.LINE}\n"
            f"<b>{Style.TO}</b> <a href='tg://user?id={receiver_user.id}'>{escape(receiver_user.first_name)}</a>\n"
            f"<b>{Style.CHAR}</b> <b>{escape(global_char.get('name', 'Unknown'))}</b>\n"
            f"<b>{Style.ID}</b> <code>{global_char.get('id')}</code>\n"
            f"<b>{Style.RARITY}</b> {rarity_display}\n"
            f"{Style.LINE}\n"
            f"<b><i><tg-emoji emoji-id='5451732530048802485'>⏳</tg-emoji> {timeout_text}</i></b>"
        )

        keyboard = [[
            InlineKeyboardButton(to_small_caps("confirm"), callback_data=f"gift_z:{sender_id}"),
            InlineKeyboardButton(to_small_caps("cancel"), callback_data=f"gift_v:{sender_id}")
        ]]

        # is_video hint bhi pass kar rahe hain (agar DB me set hai to)
        sent_msg = await reply_media_message(
            message_obj,
            global_char.get('img_url'),
            caption,
            InlineKeyboardMarkup(keyboard),
            is_video_hint=global_char.get('is_video')
        )

        if sent_msg:
            pending_gifts[sender_id]['message_id'] = sent_msg.message_id
            await schedule_auto_delete(sent_msg)

        async def expire():
            await asyncio.sleep(GIFT_TIMEOUT)
            if sender_id in pending_gifts: await cleanup_pending_gift(sender_id, sent_msg)

        gift_tasks[sender_id] = asyncio.create_task(expire())
        break

# --- HANDLERS ---
async def handle_gift_command(update: Update, context: CallbackContext):
    try:
        msg = update.message
        sender_id = msg.from_user.id

        if not msg.reply_to_message:
            sent_msg = await msg.reply_text(f'<tg-emoji emoji-id="6309717264639726942">⚠️</tg-emoji> {bold_sc("please reply to a user to send a gift.")}', parse_mode=ParseMode.HTML)
            await schedule_auto_delete(sent_msg)
            return

        receiver = msg.reply_to_message.from_user
        if sender_id == receiver.id or receiver.is_bot:
            sent_msg = await msg.reply_text(f'<tg-emoji emoji-id="6309717264639726942">⚠️</tg-emoji> {bold_sc("invalid user for gift.")}', parse_mode=ParseMode.HTML)
            await schedule_auto_delete(sent_msg)
            return

        if not context.args:
            sent_msg = await msg.reply_text(f'<tg-emoji emoji-id="5422439311196834318">💡</tg-emoji> {bold_sc("usage:")} <code>/gift &lt;id1&gt; &lt;id2&gt; ...</code>', parse_mode=ParseMode.HTML)
            await schedule_auto_delete(sent_msg)
            return

        char_ids = [str(arg) for arg in context.args][:30]

        if sender_id in pending_gifts:
            sent_msg = await msg.reply_text(f'<tg-emoji emoji-id="6309717264639726942">⚠️</tg-emoji> {bold_sc("one gift process is already in progress...")}', parse_mode=ParseMode.HTML)
            await schedule_auto_delete(sent_msg)
            return

        sender_data = await user_collection.find_one({'id': sender_id})
        if not sender_data:
            sent_msg = await msg.reply_text(f'<tg-emoji emoji-id="6309717264639726942">⚠️</tg-emoji> {bold_sc("you dont own any characters.")}', parse_mode=ParseMode.HTML)
            await schedule_auto_delete(sent_msg)
            return

        # 🔥 Owned map with powerful ID normalization (09, 9, 009 sab match)
        owned_map = {}
        for c in sender_data.get('characters', []):
            cid_raw = c.get('id')
            cid = str(cid_raw)
            owned_map[cid] = c
            if cid.isdigit():
                cleaned = cid.lstrip('0') or '0'
                owned_map[cleaned] = c
                owned_map[cleaned.zfill(2)] = c
                owned_map[cleaned.zfill(3)] = c
                owned_map[cleaned.zfill(4)] = c

        # Pre-validate all IDs (single warning for all invalid)
        valid_queue = []
        invalid_ids = []
        for arg in char_ids:
            if arg in owned_map:
                valid_queue.append(arg)
            else:
                invalid_ids.append(arg)

        if invalid_ids:
            warn_text = f'<tg-emoji emoji-id="6309717264639726942">⚠️</tg-emoji> {bold_sc("you dont own character id(s): " + ", ".join(invalid_ids) + ". skipping...")}'
            sent_msg = await msg.reply_text(warn_text, parse_mode=ParseMode.HTML)
            await schedule_auto_delete(sent_msg, 15)

        if not valid_queue:
            return

        await trigger_next_gift(sender_id, receiver, valid_queue, msg.chat.id, msg, owned_map)

    except Exception as e:
        LOGGER.error(f"Error in handle_gift_command: {e}\n{traceback.format_exc()}")

async def handle_gift_callback(update: Update, context: CallbackContext):
    query = update.callback_query

    try: await query.answer(to_small_caps("🔄 processing transfer..."), show_alert=False)
    except Exception: pass

    try:
        action, sender_id = query.data.split(':')
        sender_id = int(sender_id)
    except Exception: return

    if query.from_user.id != sender_id:
        return await query.answer(to_small_caps("⚠️ not your request!"), show_alert=True)

    gift_data = pending_gifts.pop(sender_id, None)
    if sender_id in gift_tasks:
        gift_tasks[sender_id].cancel()
        gift_tasks.pop(sender_id, None)

    if not gift_data:
        if query.message:
            try:
                await query.message.delete()
                await delete_collection.delete_one({'chat_id': query.message.chat.id, 'message_id': query.message.message_id})
            except: pass
        return await query.answer(to_small_caps("⏰ request expired."), show_alert=True)

    char = gift_data['character']
    receiver_id = gift_data['receiver_id']
    receiver_name = gift_data['receiver_name']
    receiver_user = gift_data.get('receiver_user')
    queue = gift_data.get('queue', [])
    chat_id = gift_data.get('chat_id')
    owned_map = gift_data.get('owned_map', {})

    char_id_str = str(char.get('id'))
    char_id_int = int(char_id_str) if char_id_str.isdigit() else None

    if action == "gift_z":
        if query.message:
            try: await query.edit_message_reply_markup(reply_markup=None)
            except Exception: pass

        try:
            sender_data = await user_collection.find_one({'id': sender_id})
            if not sender_data:
                if query.message: await query.message.delete()
                await query.answer(to_small_caps("❌ character no longer available."), show_alert=True)
                return

            user_characters = sender_data.get('characters', [])

            found = False
            owned_char = None
            for i, c in enumerate(user_characters):
                c_id = c.get('id')
                if str(c_id) == char_id_str:
                    owned_char = c
                    del user_characters[i]
                    found = True
                    break
                if char_id_int is not None:
                    try:
                        if int(c_id) == char_id_int:
                            owned_char = c
                            del user_characters[i]
                            found = True
                            break
                    except (ValueError, TypeError): pass

            if not found:
                if query.message: await query.message.delete()
                await query.answer(to_small_caps("❌ character no longer available."), show_alert=True)
                if queue and receiver_user and query.message:
                    await trigger_next_gift(sender_id, receiver_user, queue, chat_id, query.message, owned_map)
                return

            pull_result = await user_collection.update_one(
                {'id': sender_id},
                {'$set': {'characters': user_characters}}
            )

            if pull_result.modified_count == 0:
                if query.message: await query.message.delete()
                return await query.answer(to_small_caps("❌ gift failed. please try again."), show_alert=True)

            try:
                receiver_data = await user_collection.find_one({'id': receiver_id}, projection={'_id': 1, 'characters': 1})

                if receiver_data:
                    await user_collection.update_one({'id': receiver_id}, {'$push': {'characters': owned_char}})
                else:
                    await user_collection.insert_one({
                        'id': receiver_id, 'characters': [owned_char],
                        'created_at': datetime.now(timezone.utc), 'last_active': datetime.now(timezone.utc)
                    })

                try: clear_char_cache(owned_char['id'])
                except: pass

                rarity_display = get_rarity_display(char.get('rarity', 'Unknown'))
                final_caption = (
                    f'<tg-emoji emoji-id="5436040291507247633">🎉</tg-emoji> <b>{to_small_caps("gift successful")}</b> <tg-emoji emoji-id="5436040291507247633">🎉</tg-emoji>\n'
                    f"{Style.LINE}\n"
                    f"<b>{Style.TO}</b> <a href='tg://user?id={receiver_id}'>{escape(receiver_name)}</a>\n"
                    f"<b>{Style.CHAR}</b> <b>{escape(char.get('name', 'Unknown'))}</b>\n"
                    f"<b>{Style.ID}</b> <code>{char.get('id')}</code>\n"
                    f"<b>{Style.RARITY}</b> {rarity_display}\n"
                    f"{Style.LINE}\n"
                    f"<b><i>{to_small_caps('✓ character added to recipient harem.')}</i></b>"
                )
                if query.message:
                    try: await query.edit_message_caption(caption=final_caption, parse_mode=ParseMode.HTML)
                    except: pass

                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                log_msg = (
                    f"📢 <b>#ɢɪꜰᴛ_ʟᴏɢ</b>\n"
                    f"🕒 <b>ᴛɪᴍᴇꜱᴛᴀᴍᴘ:</b> <code>{timestamp}</code>\n"
                    f"{Style.LINE}\n"
                    f"<b>{Style.FROM}</b> {query.from_user.mention_html()}\n"
                    f"<b>{Style.TO}</b> <a href='tg://user?id={receiver_id}'>{escape(receiver_name)}</a>\n"
                    f"<b>{Style.CHAR}</b> {char.get('name')} (ɪᴅ: {char.get('id')})\n"
                    f"<b>{Style.RARITY}</b> {rarity_display}\n"
                    f"{Style.LINE}\n"
                    f"<b>{Style.STATUS}</b> {Style.SUCCESS}"
                )
                asyncio.create_task(send_log(context, log_msg))

                if queue and receiver_user and query.message:
                    await trigger_next_gift(sender_id, receiver_user, queue, chat_id, query.message, owned_map)

            except Exception as push_error:
                LOGGER.error(f"Push error during gift: {push_error}")
                await user_collection.update_one({'id': sender_id}, {'$push': {'characters': owned_char}})
                if query.message: await query.message.delete()
                await query.answer(to_small_caps("❌ inventory full or transfer failed."), show_alert=True)
                return

        except Exception as e:
            LOGGER.error(f"Callback gift_z error: {e}")
            if query.message:
                try: await query.message.delete()
                except: pass

    elif action == "gift_v":
        if query.message:
            try:
                await query.message.delete()
                await delete_collection.delete_one({'chat_id': query.message.chat.id, 'message_id': query.message.message_id})
            except: pass

# 🔥 SUPER INSTANT SPAM DELETE
async def instant_delete_spam(update: Update, context: CallbackContext):
    message = update.effective_message
    if not message: return

    text_parts = []
    if message.text: text_parts.append(message.text)
    if message.caption: text_parts.append(message.caption)
    if message.invoice:
        invoice = message.invoice
        if invoice.title: text_parts.append(invoice.title)
        if invoice.description: text_parts.append(invoice.description)

    if message.reply_markup:
        for row in message.reply_markup.inline_keyboard:
            for button in row:
                if button.text: text_parts.append(button.text)

    full_text = " ".join(text_parts).casefold()
    if not full_text: return

    spam_phrases = (
        "support our mission", "every donation makes a difference", "spread smiles",
        "contribute and make an impact", "click to contribute", "make a difference",
        "support our mission and spread smiles", "donate", "pay ⭐", "pay ⭐️",
    )

    detected = any(phrase.casefold() in full_text for phrase in spam_phrases)
    if not detected: return

    LOGGER.warning(f"🚨 STAR DONATION SPAM DETECTED | chat={message.chat.id} | message={message.message_id}")
    try:
        await message.delete()
        LOGGER.warning(f"✅ STAR DONATION SPAM DELETED | message={message.message_id}")
    except TelegramError as e:
        LOGGER.error(f"❌ DELETE FAILED | chat={message.chat.id} | message={message.message_id} | error={e}")

# --- HANDLERS REGISTRATION ---
application.add_handler(CommandHandler("gift", handle_gift_command))
application.add_handler(CallbackQueryHandler(handle_gift_callback, pattern='^gift_(z|v):'))
application.add_handler(MessageHandler(filters.ALL, instant_delete_spam), group=-100)

async def cleanup_stale_gifts():
    while True:
        try:
            now = datetime.now(timezone.utc)
            stale_senders = [sid for sid, data in pending_gifts.items() if (now - data['created_at']).total_seconds() > GIFT_TIMEOUT + 30]
            for sid in stale_senders: await cleanup_pending_gift(sid)
        except Exception: pass
        await asyncio.sleep(300)

async def on_bot_start():
    asyncio.create_task(cleanup_stale_gifts())
    try:
        bot = application.bot
        if bot: asyncio.create_task(background_delete_worker(bot))
    except Exception as e:
        LOGGER.error(f"Worker Auto-start failed on boot: {e}")

try:
    loop = asyncio.get_event_loop()
    if loop.is_running(): asyncio.create_task(on_bot_start())
    else: loop.run_until_complete(on_bot_start())
except Exception: pass

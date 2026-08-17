import asyncio
from html import escape
from datetime import datetime, timezone
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler
from telegram.constants import ParseMode
from telegram.error import TelegramError

# ✨ Cache clear import for instant updates ✨
try:
    from shivu.modules.check import clear_char_cache
except ImportError:
    def clear_char_cache(cid): pass 

from shivu import LOGGER, application, user_collection, collection

# --- CONFIGURATION ---
LOG_CHANNEL_ID = -1002900862232 
GIFT_TIMEOUT = 60
MAX_INVENTORY_SIZE = 1000  # Adjust as needed
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

# --- ✨ CUSTOM STYLES ---
class Style:
    GIFT = "🎁 " + to_small_caps("gift transfer")
    TO = "👤 " + to_small_caps("recipient :")
    FROM = "👤 " + to_small_caps("sender :")
    CHAR = "🍥 " + to_small_caps("character :")
    ID = "🆔 " + to_small_caps("id :")
    STATUS = "✨ " + to_small_caps("status :")
    LINE = "──────────────────"
    SUCCESS = "✅ " + to_small_caps("success")
    ERROR = to_small_caps("error")
    WARNING = to_small_caps("warning")
    INFO = to_small_caps("info")

# --- UTILS ---
def is_video_url(url):
    if not url: return False
    url_lower = url.lower()
    return any(url_lower.endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v']) or any(pattern in url_lower for pattern in ['/video/', '/videos/', 'video=', 'v=', '.mp4?', '/stream/'])

async def send_log(context: CallbackContext, text: str):
    try:
        await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        LOGGER.error(f"Log failed: {e}")

async def reply_media_message(message, media_url, caption, reply_markup=None):
    try:
        if is_video_url(media_url):
            return await message.reply_video(video=media_url, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        return await message.reply_photo(photo=media_url, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except Exception:
        return await message.reply_text(text=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def cleanup_pending_gift(sender_id: int, sent_msg=None):
    if sender_id in gift_tasks:
        gift_tasks[sender_id].cancel()
        gift_tasks.pop(sender_id, None)
    
    if sender_id in pending_gifts:
        if sent_msg:
            try:
                await sent_msg.delete()
            except Exception:
                pass
        pending_gifts.pop(sender_id, None)

async def check_receiver_inventory_size(receiver_id: int) -> bool:
    try:
        result = await user_collection.aggregate([
            {"$match": {"id": receiver_id}},
            {"$project": {"characters_count": {"$size": {"$ifNull": ["$characters", []]}}}}
        ]).to_list(length=1)
        if result and len(result) > 0:
            return result[0].get('characters_count', 0) < MAX_INVENTORY_SIZE
        return True
    except Exception:
        return False

# --- ATOMIC TRANSFER ---
async def atomic_transfer_character(sender_id: int, receiver_id: int, character: dict) -> bool:
    try:
        pull_result = await user_collection.update_one(
            {'id': sender_id, 'characters.id': character['id']},
            {'$pull': {'characters': {'id': character['id']}}}
        )
        if pull_result.modified_count == 0: return False
        
        try:
            receiver_data = await user_collection.find_one({'id': receiver_id})
            if receiver_data:
                if len(receiver_data.get('characters', [])) >= MAX_INVENTORY_SIZE:
                    raise Exception("Inventory full")
                await user_collection.update_one({'id': receiver_id}, {'$push': {'characters': character}})
            else:
                await user_collection.insert_one({
                    'id': receiver_id, 'characters': [character],
                    'created_at': datetime.now(timezone.utc), 'last_active': datetime.now(timezone.utc)
                })
            
            clear_char_cache(character['id'])
            return True
            
        except Exception as push_error:
            await user_collection.update_one({'id': sender_id}, {'$push': {'characters': character}})
            return False
    except Exception:
        return False

# --- HANDLERS ---
async def handle_gift_command(update: Update, context: CallbackContext):
    msg = update.message
    sender_id = msg.from_user.id

    if not msg.reply_to_message:
        return await msg.reply_text(f"❌ {bold_sc('please reply to a user to send a gift.')}", parse_mode=ParseMode.HTML)

    receiver = msg.reply_to_message.from_user
    if sender_id == receiver.id or receiver.is_bot:
        return await msg.reply_text(f"❌ {bold_sc('invalid user for gift.')}", parse_mode=ParseMode.HTML)

    if len(context.args) != 1:
        return await msg.reply_text(f"💡 {bold_sc('usage:')} <code>/gift &lt;id&gt;</code>", parse_mode=ParseMode.HTML)

    char_id = context.args[0]
    
    if sender_id in pending_gifts:
        return await msg.reply_text(f"⚠️ {bold_sc('one gift is already in progress...')}", parse_mode=ParseMode.HTML)
    
    if not await check_receiver_inventory_size(receiver.id):
        return await msg.reply_text(f"📦 {bold_sc(f'receiver inventory is full (max {MAX_INVENTORY_SIZE}).')}", parse_mode=ParseMode.HTML)

    sender_data = await user_collection.find_one({'id': sender_id})
    if not sender_data:
        return await msg.reply_text(f"❌ {bold_sc('you dont own this character.')}", parse_mode=ParseMode.HTML)
    
    character = next((c for c in sender_data.get('characters', []) if str(c.get('id')) == str(char_id)), None)
    if not character:
        return await msg.reply_text(f"❌ {bold_sc('you dont own this character.')}", parse_mode=ParseMode.HTML)
    
    global_char = await collection.find_one({'id': character['id']})
    if not global_char:
        return await msg.reply_text(f"❌ {bold_sc('character not found in global collection.')}", parse_mode=ParseMode.HTML)

    pending_gifts[sender_id] = {
        'character': character, 'receiver_id': receiver.id, 'receiver_name': receiver.first_name,
        'message_id': None, 'created_at': datetime.now(timezone.utc)
    }

    caption = (
        f"<b>{Style.GIFT}</b>\n"
        f"{Style.LINE}\n"
        f"<b>{Style.TO}</b> <a href='tg://user?id={receiver.id}'>{bold_sc(escape(receiver.first_name))}</a>\n"
        f"<b>{Style.CHAR}</b> <code>{bold_sc(escape(character['name']))}</code>\n"
        f"<b>{Style.ID}</b> <code>{character['id']}</code>\n"
        f"{Style.LINE}\n"
        f"<b><i>{to_small_caps(f'⏳ confirm within {GIFT_TIMEOUT}s to send.')}</i></b>"
    )

    keyboard = [[
        InlineKeyboardButton(to_small_caps("✅ confirm"), callback_data=f"gift_z:{sender_id}"),
        InlineKeyboardButton(to_small_caps("❌ cancel"), callback_data=f"gift_v:{sender_id}")
    ]]

    sent_msg = await reply_media_message(msg, character.get('img_url'), caption, InlineKeyboardMarkup(keyboard))
    if sent_msg: pending_gifts[sender_id]['message_id'] = sent_msg.message_id
    
    async def expire():
        await asyncio.sleep(GIFT_TIMEOUT)
        if sender_id in pending_gifts: await cleanup_pending_gift(sender_id, sent_msg)
    
    gift_tasks[sender_id] = asyncio.create_task(expire())

async def handle_gift_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    action, sender_id = query.data.split(':')
    sender_id = int(sender_id)

    if query.from_user.id != sender_id:
        return await query.answer(to_small_caps("⚠️ not your request!"), show_alert=True)

    gift_data = pending_gifts.pop(sender_id, None)
    if sender_id in gift_tasks:
        gift_tasks[sender_id].cancel()
        gift_tasks.pop(sender_id, None)

    if not gift_data:
        try: await query.message.delete()
        except: pass
        return await query.answer(to_small_caps("⏰ request expired."), show_alert=True)

    char, receiver_id, receiver_name = gift_data['character'], gift_data['receiver_id'], gift_data['receiver_name']

    if action == "gift_z":
        try: await query.edit_message_reply_markup(reply_markup=None)
        except Exception: pass
        
        try:
            final_check = await user_collection.find_one({'id': sender_id, 'characters.id': char['id']})
            if not final_check:
                await query.message.delete()
                return await query.answer(to_small_caps("❌ character no longer available."), show_alert=True)
            
            if await atomic_transfer_character(sender_id, receiver_id, char):
                final_caption = (
                    f"<b>🎊 {to_small_caps('gift delivered')} 🎊</b>\n"
                    f"{Style.LINE}\n"
                    f"<b>{Style.TO}</b> <a href='tg://user?id={receiver_id}'>{bold_sc(escape(receiver_name))}</a>\n"
                    f"<b>{Style.CHAR}</b> <code>{bold_sc(escape(char['name']))}</code>\n"
                    f"{Style.LINE}\n"
                    f"<b><i>{to_small_caps('✓ character successfully transferred.')}</i></b>"
                )
                await query.edit_message_caption(caption=final_caption, parse_mode=ParseMode.HTML)
                
                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                log_msg = (
                    f"📢 <b>#ɢɪꜰᴛ_ʟᴏɢ</b>\n"
                    f"🕒 <b>ᴛɪᴍᴇꜱᴛᴀᴍᴘ:</b> <code>{timestamp}</code>\n"
                    f"{Style.LINE}\n"
                    f"<b>{Style.FROM}</b> {query.from_user.mention_html()}\n"
                    f"<b>{Style.TO}</b> <a href='tg://user?id={receiver_id}'>{escape(receiver_name)}</a>\n"
                    f"<b>{Style.CHAR}</b> {char['name']} (ɪᴅ: {char['id']})\n"
                    f"{Style.LINE}\n"
                    f"<b>{Style.STATUS}</b> {Style.SUCCESS}"
                )
                asyncio.create_task(send_log(context, log_msg))
                    
            else:
                await query.message.delete()
                await query.answer(to_small_caps("❌ transfer failed. character not lost."), show_alert=True)
        
        except Exception as e:
            await query.message.delete()
            await query.answer(to_small_caps("❌ an unexpected error occurred."), show_alert=True)
    
    elif action == "gift_v":
        await query.message.delete()

application.add_handler(CommandHandler("gift", handle_gift_command, block=False))
application.add_handler(CallbackQueryHandler(handle_gift_callback, pattern='^gift_(z|v):', block=False))

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
    loop = asyncio.get_event_loop()
    if loop.is_running(): asyncio.create_task(on_bot_start())
    else: loop.run_until_complete(on_bot_start())
except Exception: pass

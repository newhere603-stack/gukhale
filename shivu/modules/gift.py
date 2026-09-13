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
MAX_INVENTORY_SIZE = 1000 # Ye ab kisi kaam ka nahi hai kyuki limit hata di hai
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

# --- ✨ UPGRADED MODERN UI STYLES ---
class Style:
    GIFT = '<tg-emoji emoji-id="5255861796350224063">💖</tg-emoji> <b>' + to_small_caps("gift transfer hub") + '</b> <tg-emoji emoji-id="5255861796350224063">💖</tg-emoji>'
    TO = '<tg-emoji emoji-id="6337080578591956016">😆</tg-emoji> ' + to_small_caps("Rec ⬡")
    FROM = '<tg-emoji emoji-id="5305699699204837855">🍀</tg-emoji> ' + to_small_caps("sender ⬡")
    CHAR = '<tg-emoji emoji-id="6336972134962697188">🌸</tg-emoji> ' + to_small_caps("name ⬡")
    ID = '<tg-emoji emoji-id="6332443074769196273">🆔</tg-emoji> ' + to_small_caps("chr id ⬡")
    STATUS = '<tg-emoji emoji-id="6093431129749070651">✨</tg-emoji> ' + to_small_caps("status ⬡")
    LINE = "──────────────────"
    SUCCESS = "✅ " + to_small_caps("success")

async def send_log(context: CallbackContext, text: str):
    try:
        await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        LOGGER.error(f"Log failed: {e}")

# 🔥 ADVANCED MEDIA HANDLER (Bulletproof with fallbacks)
async def reply_media_message(message, media_url, caption, reply_markup=None):
    if not media_url:
        try: return await message.reply_text(text=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        except Exception: return await message.chat.send_message(text=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
    is_video_url = False
    if isinstance(media_url, str):
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

# --- 🔥 BULK GIFT CORE LOGIC ---
async def get_owned_char_and_global(sender_id, char_id_input_str):
    char_id_input_int = int(char_id_input_str) if char_id_input_str.isdigit() else None
    sender_data = await user_collection.find_one({'id': sender_id})
    if not sender_data: return None, None
    
    owned_char = None
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
    
    global_char = owned_char
    if 'img_url' not in global_char or 'name' not in global_char:
        search_query = [{'id': char_id_input_str}]
        if char_id_input_int is not None:
            search_query.extend([{'id': char_id_input_int}, {'id': str(char_id_input_int)}])
        db_char = await collection.find_one({'$or': search_query})
        if db_char: global_char = db_char
    return owned_char, global_char

async def trigger_next_gift(sender_id, receiver_user, queue, chat_id, message_obj):
    while queue:
        next_id_str = queue.pop(0)
        
        owned_char, global_char = await get_owned_char_and_global(sender_id, next_id_str)
        
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
            'character': global_char, 
            'receiver_id': receiver_user.id, 
            'receiver_name': receiver_user.first_name,
            'receiver_user': receiver_user,
            'message_id': None, 
            'created_at': datetime.now(timezone.utc),
            'queue': queue,
            'chat_id': chat_id
        }
        
        timeout_text = to_small_caps(f"confirm within {GIFT_TIMEOUT}s to send.")
        caption = (
            f"{Style.GIFT}\n"
            f"{Style.LINE}\n"
            f"<b>{Style.TO}</b> <a href='tg://user?id={receiver_user.id}'>{escape(receiver_user.first_name)}</a>\n"
            f"<b>{Style.CHAR}</b> <b>{escape(global_char.get('name', 'Unknown'))}</b>\n"
            f"<b>{Style.ID}</b> <code>{global_char.get('id')}</code>\n"
            f"{Style.LINE}\n"
            f"<b><i><tg-emoji emoji-id='5451732530048802485'>⏳</tg-emoji> {timeout_text}</i></b>"
        )

        keyboard = [[
            InlineKeyboardButton(to_small_caps("confirm"), callback_data=f"gift_z:{sender_id}"),
            InlineKeyboardButton(to_small_caps("cancel"), callback_data=f"gift_v:{sender_id}")
        ]]

        sent_msg = await reply_media_message(message_obj, global_char.get('img_url'), caption, InlineKeyboardMarkup(keyboard))
        
        if sent_msg: 
            pending_gifts[sender_id]['message_id'] = sent_msg.message_id
            await schedule_auto_delete(sent_msg) 
        
        async def expire():
            await asyncio.sleep(GIFT_TIMEOUT)
            if sender_id in pending_gifts: await cleanup_pending_gift(sender_id, sent_msg)
        
        gift_tasks[sender_id] = asyncio.create_task(expire())
        break # Loop yahin rukega jab tak banda confirm ya cancel nahi karta!

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

        # Ek baari me maximum 30 gifts queue kar sakte hain
        char_ids = [str(arg) for arg in context.args][:30] 
        
        if sender_id in pending_gifts:
            sent_msg = await msg.reply_text(f'<tg-emoji emoji-id="6309717264639726942">⚠️</tg-emoji> {bold_sc("one gift process is already in progress...")}', parse_mode=ParseMode.HTML)
            await schedule_auto_delete(sent_msg)
            return
        
        # Parallel quick check
        sender_data, is_receiver_valid = await asyncio.gather(
            user_collection.find_one({'id': sender_id}),
            check_receiver_inventory_size(receiver.id)
        )

        if not is_receiver_valid:
            inv_text = f"receiver inventory is full."
            sent_msg = await msg.reply_text(f"📦 {bold_sc(inv_text)}", parse_mode=ParseMode.HTML)
            await schedule_auto_delete(sent_msg)
            return

        if not sender_data:
            sent_msg = await msg.reply_text(f'<tg-emoji emoji-id="6309717264639726942">⚠️</tg-emoji> {bold_sc("you dont own any characters.")}', parse_mode=ParseMode.HTML)
            await schedule_auto_delete(sent_msg)
            return
            
        # Bulk Gift Chain Start!
        await trigger_next_gift(sender_id, receiver, char_ids, msg.chat.id, msg)
        
    except Exception as e:
        # Silent Fail
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
                # Agar character id missing thi par aage queue bachi hai to aage badhao
                if queue and receiver_user and query.message:
                    await trigger_next_gift(sender_id, receiver_user, queue, chat_id, query.message)
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
                    # 1000 limit wala condition hata diya gaya hai
                    await user_collection.update_one({'id': receiver_id}, {'$push': {'characters': owned_char}})
                else:
                    await user_collection.insert_one({
                        'id': receiver_id, 'characters': [owned_char],
                        'created_at': datetime.now(timezone.utc), 'last_active': datetime.now(timezone.utc)
                    })
                
                try: clear_char_cache(owned_char['id'])
                except: pass
                
                final_caption = (
                    f'<tg-emoji emoji-id="5436040291507247633">🎉</tg-emoji> <b>{to_small_caps("gift successful")}</b> <tg-emoji emoji-id="5436040291507247633">🎉</tg-emoji>\n'
                    f"{Style.LINE}\n"
                    f"<b>{Style.TO}</b> <a href='tg://user?id={receiver_id}'>{escape(receiver_name)}</a>\n"
                    f"<b>{Style.CHAR}</b> <b>{escape(char.get('name', 'Unknown'))}</b>\n"
                    f"<b>{Style.ID}</b> <code>{char.get('id')}</code>\n"
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
                    f"{Style.LINE}\n"
                    f"<b>{Style.STATUS}</b> {Style.SUCCESS}"
                )
                asyncio.create_task(send_log(context, log_msg))
                
                # 🔥 Success hone ke baad check karega ki koi aur gift pending hai ya nahi
                if queue and receiver_user and query.message:
                    await trigger_next_gift(sender_id, receiver_user, queue, chat_id, query.message)
                    
            except Exception as push_error:
                LOGGER.error(f"Push error during gift: {push_error}")
                await user_collection.update_one({'id': sender_id}, {'$push': {'characters': owned_char}})
                if query.message: await query.message.delete()
                await query.answer(to_small_caps("❌ inventory full or transfer failed."), show_alert=True)
                return # Inventory full pe aage ka queue band
        
        except Exception as e:
            # Silent Fail
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
        # Cancel dabane par aage ka queue apne aap dead ho jayega!

# 🔥 SUPER INSTANT SPAM DELETE (Ab aur bhi aggressive aur strict hai)
async def instant_delete_spam(update: Update, context: CallbackContext):
    if not update.effective_message:
        return
        
    # List mein current message or replied message dono daal diye
    messages_to_check = [update.effective_message]
    if update.effective_message.reply_to_message:
        messages_to_check.append(update.effective_message.reply_to_message)
        
    for m in messages_to_check:
        text_parts = []
        
        if getattr(m, 'text', None): text_parts.append(m.text)
        if getattr(m, 'caption', None): text_parts.append(m.caption)
        
        if getattr(m, 'invoice', None):
            if getattr(m.invoice, 'title', None): text_parts.append(m.invoice.title)
            if getattr(m.invoice, 'description', None): text_parts.append(m.invoice.description)
            
        reply_markup = getattr(m, 'reply_markup', None)
        if reply_markup and hasattr(reply_markup, 'inline_keyboard'):
            for row in reply_markup.inline_keyboard:
                for button in row:
                    if getattr(button, 'text', None): text_parts.append(button.text)
                    
        full_text = " ".join(text_parts).lower() 
        
        # Expanded Spam Keywords - Ye screenshot wale message ko pakad lega
        spam_phrases = [
            "support our mission", "every donation makes a difference", 
            "spread smiles", "pay ⭐️", "pay ⭐", "donate", 
            "contribute and make an impact", "click to contribute",
            "make a difference", "support our mission and spread smiles"
        ]
        
        # Agar text match hua, ud jayega
        if any(phrase in full_text for phrase in spam_phrases):
            try: 
                await m.delete()
                LOGGER.info(f"Successfully deleted spam message {m.message_id} in {m.chat.id}")
            except TelegramError as e:
                # Ye error tab aayega jab bot admin nahi hoga ya permission nahi hogi
                LOGGER.error(f"Failed to delete spam message {m.message_id} in {m.chat.id}: {e}")
                try:
                    await context.bot.delete_message(chat_id=m.chat.id, message_id=m.message_id)
                except Exception as e2:
                    LOGGER.error(f"Fallback deletion failed: {e2}")

# --- HANDLERS REGISTRATION ---
application.add_handler(CommandHandler("gift", handle_gift_command))
application.add_handler(CallbackQueryHandler(handle_gift_callback, pattern='^gift_(z|v):'))
application.add_handler(MessageHandler(filters.ALL, instant_delete_spam), group=-99)

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

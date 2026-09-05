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

# 🔥 ADVANCED MEDIA HANDLER (Fixed File_id Video issue)
async def reply_media_message(message, media_url, caption, reply_markup=None):
    if not media_url:
        return await message.reply_text(text=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
    is_video_url = False
    if isinstance(media_url, str):
        url_lower = media_url.lower()
        if any(url_lower.endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v']) or any(pattern in url_lower for pattern in ['/video/', '/videos/', 'video=', 'v=', '.mp4?', '/stream/']):
            is_video_url = True

    try:
        if is_video_url:
            return await message.reply_video(video=media_url, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        else:
            return await message.reply_photo(photo=media_url, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except Exception as e:
        # Fallback 1: Agar photo fail hui (Kyunki wo shayad video file_id thi)
        try:
            if not is_video_url:
                return await message.reply_video(video=media_url, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            else:
                return await message.reply_photo(photo=media_url, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        except Exception as e2:
            # Fallback 2: Animation / GIF
            try:
                return await message.reply_animation(animation=media_url, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            except Exception as e3:
                LOGGER.error(f"Media fallback failed: {e3}")
                return await message.reply_text(text=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# 🔥 PERMANENT AUTO DELETE SYSTEM 🔥
_worker_started = False

async def background_delete_worker(bot):
    """Ye worker background me chalega aur restart hone par bhi database check karke delete karega"""
    global _worker_started
    if _worker_started:
        return
    _worker_started = True
    
    try:
        await delete_collection.create_index("delete_at")
    except Exception:
        pass
        
    while True:
        try:
            now = time.time()
            cursor = delete_collection.find({'delete_at': {'$lte': now}})
            async for doc in cursor:
                try:
                    await bot.delete_message(chat_id=doc['chat_id'], message_id=doc['message_id'])
                except Exception:
                    pass 
                finally:
                    await delete_collection.delete_one({'_id': doc['_id']})
        except Exception:
            pass
        await asyncio.sleep(20) # Check interval 20 sec kiya taaki accurate delete ho

async def schedule_auto_delete(message, delay_seconds: int = 1200):
    """Message ko database aur memory memory queue dono me daalta hai"""
    if not message: return
        
    global _worker_started
    if not _worker_started:
        asyncio.create_task(background_delete_worker(message.get_bot()))

    chat_id = message.chat.id
    message_id = message.message_id
    delete_at = time.time() + delay_seconds

    await delete_collection.insert_one({
        'chat_id': chat_id,
        'message_id': message_id,
        'delete_at': delete_at
    })

    async def memory_delete():
        await asyncio.sleep(delay_seconds)
        try:
            await message.get_bot().delete_message(chat_id=chat_id, message_id=message_id)
            await delete_collection.delete_one({'chat_id': chat_id, 'message_id': message_id})
        except Exception:
            pass

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
    except Exception as e:
        LOGGER.error(f"Inventory check error: {e}")
        return True

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

        if len(context.args) != 1:
            sent_msg = await msg.reply_text(f'<tg-emoji emoji-id="5422439311196834318">💡</tg-emoji> {bold_sc("usage:")} <code>/gift &lt;id&gt;</code>', parse_mode=ParseMode.HTML)
            await schedule_auto_delete(sent_msg)
            return

        char_id = str(context.args[0])
        
        if sender_id in pending_gifts:
            sent_msg = await msg.reply_text(f'<tg-emoji emoji-id="6309717264639726942">⚠️</tg-emoji> {bold_sc("one gift is already in progress...")}', parse_mode=ParseMode.HTML)
            await schedule_auto_delete(sent_msg)
            return
        
        if not await check_receiver_inventory_size(receiver.id):
            inv_text = f"receiver inventory is full (max {MAX_INVENTORY_SIZE})."
            sent_msg = await msg.reply_text(f"📦 {bold_sc(inv_text)}", parse_mode=ParseMode.HTML)
            await schedule_auto_delete(sent_msg)
            return

        sender_data = await user_collection.find_one({'id': sender_id})
        if not sender_data:
            sent_msg = await msg.reply_text(f'<tg-emoji emoji-id="6309717264639726942">⚠️</tg-emoji> {bold_sc("you dont own this character.")}', parse_mode=ParseMode.HTML)
            await schedule_auto_delete(sent_msg)
            return
        
        owned_char = next((c for c in sender_data.get('characters', []) if str(c.get('id')) == char_id), None)
        if not owned_char:
            sent_msg = await msg.reply_text(f'<tg-emoji emoji-id="6309717264639726942">⚠️</tg-emoji> {bold_sc("you dont own this character.")}', parse_mode=ParseMode.HTML)
            await schedule_auto_delete(sent_msg)
            return
        
        global_char = await collection.find_one({'$or': [{'id': char_id}, {'id': int(char_id) if char_id.isdigit() else None}]})
        if not global_char:
            global_char = owned_char

        pending_gifts[sender_id] = {
            'character': global_char, 'receiver_id': receiver.id, 'receiver_name': receiver.first_name,
            'message_id': None, 'created_at': datetime.now(timezone.utc)
        }

        timeout_text = to_small_caps(f"confirm within {GIFT_TIMEOUT}s to send.")
        caption = (
            f"{Style.GIFT}\n"
            f"{Style.LINE}\n"
            f"<b>{Style.TO}</b> <a href='tg://user?id={receiver.id}'>{escape(receiver.first_name)}</a>\n"
            f"<b>{Style.CHAR}</b> <b>{escape(global_char.get('name', 'Unknown'))}</b>\n"
            f"<b>{Style.ID}</b> <code>{global_char.get('id')}</code>\n"
            f"{Style.LINE}\n"
            f"<b><i><tg-emoji emoji-id='5451732530048802485'>⏳</tg-emoji> {timeout_text}</i></b>"
        )

        keyboard = [[
            InlineKeyboardButton(to_small_caps("confirm"), callback_data=f"gift_z:{sender_id}"),
            InlineKeyboardButton(to_small_caps("cancel"), callback_data=f"gift_v:{sender_id}")
        ]]

        sent_msg = await reply_media_message(msg, global_char.get('img_url'), caption, InlineKeyboardMarkup(keyboard))
        
        if sent_msg: 
            pending_gifts[sender_id]['message_id'] = sent_msg.message_id
            await schedule_auto_delete(sent_msg) 
        
        async def expire():
            await asyncio.sleep(GIFT_TIMEOUT)
            if sender_id in pending_gifts: await cleanup_pending_gift(sender_id, sent_msg)
        
        gift_tasks[sender_id] = asyncio.create_task(expire())
    except Exception as e:
        LOGGER.error(f"Error in handle_gift_command: {e}\n{traceback.format_exc()}")
        sent_msg = await update.message.reply_text("❌ An error occurred while processing the gift command.")
        await schedule_auto_delete(sent_msg)

async def handle_gift_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    
    try:
        await query.answer()
    except Exception as e:
        pass
    
    try:
        action, sender_id = query.data.split(':')
        sender_id = int(sender_id)
    except Exception:
        return

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

    char, receiver_id, receiver_name = gift_data['character'], gift_data['receiver_id'], gift_data['receiver_name']
    char_id_str = str(char.get('id'))

    if action == "gift_z":
        if query.message:
            try: await query.edit_message_reply_markup(reply_markup=None)
            except Exception: pass
        
        try:
            sender_data = await user_collection.find_one({'id': sender_id})
            if not sender_data:
                if query.message: await query.message.delete()
                return await query.answer(to_small_caps("❌ character no longer available."), show_alert=True)

            user_characters = sender_data.get('characters', [])
            
            found = False
            owned_char = None
            for i, c in enumerate(user_characters):
                if str(c.get('id')) == char_id_str:
                    owned_char = c
                    del user_characters[i]
                    found = True
                    break
            
            if not found:
                if query.message: await query.message.delete()
                return await query.answer(to_small_caps("❌ character no longer available."), show_alert=True)

            pull_result = await user_collection.update_one(
                {'id': sender_id},
                {'$set': {'characters': user_characters}}
            )

            if pull_result.modified_count == 0:
                if query.message: await query.message.delete()
                return await query.answer(to_small_caps("❌ gift failed. please try again."), show_alert=True)
            
            try:
                receiver_data = await user_collection.find_one({'id': receiver_id})
                if receiver_data:
                    if len(receiver_data.get('characters', [])) >= MAX_INVENTORY_SIZE:
                        raise Exception("Inventory full")
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
                    
            except Exception as push_error:
                LOGGER.error(f"Push error during gift: {push_error}")
                await user_collection.update_one({'id': sender_id}, {'$push': {'characters': owned_char}})
                if query.message: await query.message.delete()
                await query.answer(to_small_caps("❌ inventory full or transfer failed."), show_alert=True)
        
        except Exception as e:
            LOGGER.error(f"Callback gift_z error: {e}")
            if query.message:
                try: await query.message.delete()
                except: pass
            await query.answer(to_small_caps("❌ an unexpected error occurred."), show_alert=True)
    
    elif action == "gift_v":
        if query.message:
            try: 
                await query.message.delete()
                await delete_collection.delete_one({'chat_id': query.message.chat.id, 'message_id': query.message.message_id})
            except: pass

# 🔥 SUPER INSTANT SPAM DELETE
async def instant_delete_spam(update: Update, context: CallbackContext):
    msg = update.effective_message
    if not msg: 
        return
        
    text_parts = []
    
    if msg.text: text_parts.append(msg.text)
    if msg.caption: text_parts.append(msg.caption)
    
    if msg.invoice:
        if msg.invoice.title: text_parts.append(msg.invoice.title)
        if msg.invoice.description: text_parts.append(msg.invoice.description)
        
    if msg.reply_markup and msg.reply_markup.inline_keyboard:
        for row in msg.reply_markup.inline_keyboard:
            for button in row:
                if button.text: text_parts.append(button.text)
                
    full_text = " ".join(text_parts).lower() 
    
    if "donate 💝" in full_text or "support our mission" in full_text or "every donation makes a difference" in full_text:
        try:
            await msg.delete()
        except Exception as e:
            LOGGER.error(f"Spam delete failed (Check if bot is admin!): {e}")

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
    # Bot shuru hote hi Memory Auto-Delete background thread force start karega
    try:
        bot = application.bot
        if bot:
            asyncio.create_task(background_delete_worker(bot))
    except Exception as e:
        LOGGER.error(f"Worker Auto-start failed on boot: {e}")

try:
    loop = asyncio.get_event_loop()
    if loop.is_running(): asyncio.create_task(on_bot_start())
    else: loop.run_until_complete(on_bot_start())
except Exception: pass

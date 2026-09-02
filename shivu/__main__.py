import asyncio
import traceback
import importlib
import random
import time  
from html import escape
from shivu.modules import kill

# 🔥 Super-Fast Engine Setup (No text/font changes)
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

import shivu.modules.wordgrid
import wordle_game
import shivu.modules.gift
import shivu.modules.pmarket
import shivu.modules.balance
import shivu.modules.chatlog

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, CallbackContext, MessageHandler, filters
from telegram.error import BadRequest

from shivu import db, shivuu, application, LOGGER, user_totals_collection
from shivu.modules import ALL_MODULES

# 🔥 Economy DB sync ke liye
from shivu.Database.db import eco_collection

OWNER_ID = 7657218453
SUDO_USERS = [7657218453]

# 🔥 Authorization Check Upar Move Kiya Taaki Flood Control Mein Use Ho Sake
def is_authorized(user_id):
    return user_id == OWNER_ID or user_id in SUDO_USERS

collection = db['anime_characters_lol']
user_collection = db['user_collection_lmaoooo']
group_user_totals_collection = db['group_user_totalsssssss']
top_global_groups_collection = db['top_global_groups']
bot_settings_collection = db['bot_settings'] # 🔥 Persistent Settings ke liye
group_settings_collection = db['group_settings_db']
spawns_collection = db['active_spawns_db']
chat_message_counts_collection = db['chat_message_counts_db'] # 🔥 Naya DB Bot ki Yaddasht (Memory) ke liye

MESSAGE_FREQUENCY = 70
DESPAWN_TIME = 300  # (300 seconds)
AMV_ALLOWED_GROUP_ID = -1003100468240

RARITIES = {
    "common": ("🟢", '<tg-emoji emoji-id="6093865707424980866">🟢</tg-emoji>', "Common"), 
    "rare": ("🟠", '<tg-emoji emoji-id="5339390195768774311">🟠</tg-emoji>', "Rare"), 
    "legendary": ("🟡", '<tg-emoji emoji-id="6084550327086883643">🟡</tg-emoji>', "Legendary"),
    "special": ("🔴", '<tg-emoji emoji-id="6093741664474504699">🔴</tg-emoji>', "Medium"), 
    "celestial": ("🪽", '<tg-emoji emoji-id="5434121252874756456">🪽</tg-emoji>', "Celestial"), 
    "erotic": ("🥵", '<tg-emoji emoji-id="6093490292923574796">🥵</tg-emoji>', "Spicy"),
    "exclusive": ("💮", '<tg-emoji emoji-id="6100567406889935797">💮</tg-emoji>', "Exclusive"), 
    "premium": ("🔮", '<tg-emoji emoji-id="6093919703753831564">🔮</tg-emoji>', "Premium Edition"), 
    "mythic": ("💎", '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>', "Mythic"),
    "sweet": ("🍭", '<tg-emoji emoji-id="6222115531122546353">🍭</tg-emoji>', "Sweet"), 
    "valentine": ("💞", '<tg-emoji emoji-id="5255861796350224063">💞</tg-emoji>', "Valentine"), 
    "winter": ("❄️", '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>', "Winter"),
    "neon": ("⚡", '<tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>', "Neon"), 
    "pearl": ("🏖️", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"), 
    "cosmic": ("🌌", '<tg-emoji emoji-id="5431783411981228752">🌌</tg-emoji>', "Cosmic"),
}

# 🔥 SILENT AUTO-DELETE HELPER
async def auto_delete_msg(context, chat_id, message_id, delay: int):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass

disabled_rarities_cache = set()
group_settings_cache = {}  
locks, message_counts = {}, {}
sent_characters = {}

last_grabbed = {} 
grab_locks = {} 
active_spawns_cache = {} 

currently_spawning = {}

_cached_characters = []
_last_cache_time = 0

user_message_times = {}
blocked_users = {}

async def check_and_handle_flood(update: Update, context: CallbackContext) -> bool:
    user = update.effective_user
    if not user:
        return False
        
    user_id = user.id
    
    if is_authorized(user_id):
        return False

    now = time.time()
    
    if user_id in blocked_users:
        if now < blocked_users[user_id]:
            return True 
        else:
            del blocked_users[user_id]  
            user_message_times.pop(user_id, None)  
            
    user_message_times.setdefault(user_id, []).append(now)
    user_message_times[user_id] = [t for t in user_message_times[user_id] if now - t < 4]
    
    if len(user_message_times[user_id]) >= 7:
        blocked_users[user_id] = now + 600  
        safe_name = escape(user.first_name)
        mention = f'<a href="tg://user?id={user_id}">{safe_name}</a>'
        msg = f'<b><tg-emoji emoji-id="5420323339723881652">⚠️</tg-emoji> {mention} ɪs ғʟᴏᴏᴅɪɴɢ: ʙʟᴏᴄᴋᴇᴅ ғᴏʀ 𝟷𝟶 ᴍɪɴᴜᴛᴇs ғᴏʀ ᴜsɪɴɢ ᴛʜᴇ ʙᴏᴛ.</b>'
        try:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='HTML')
        except Exception:
            pass
        return True
        
    return False

async def setup_database_indexes():
    try:
        await collection.create_index("id", background=True)
        await user_collection.create_index("id", unique=True, background=True)
        await user_collection.create_index("characters.id", background=True)
        await eco_collection.create_index("id", unique=True, background=True)
        await group_user_totals_collection.create_index([("user_id", 1), ("group_id", 1)], background=True)
        await spawns_collection.create_index("chat_id", unique=True, background=True)
        await chat_message_counts_collection.create_index("chat_id", unique=True, background=True)
        LOGGER.info("⚡ Database Indexes Verified/Created Successfully!")
    except Exception as e:
        if "IndexKeySpecsConflict" not in str(e):
            LOGGER.error(f"Index creation failed: {e}")
        else:
            LOGGER.info("⚡ Existing database indexes verified successfully.")

async def get_cached_characters():
    global _cached_characters, _last_cache_time
    current_time = time.time()
    if not _cached_characters or (current_time - _last_cache_time) > 300:
        fetched_chars = await collection.find({'auction_exclusive': {'$ne': True}}).to_list(length=None)
        if fetched_chars:
            _cached_characters = fetched_chars
            _last_cache_time = current_time
    return _cached_characters

for module_name in ALL_MODULES:
    try:
        importlib.import_module("shivu.modules." + module_name)
    except Exception:
        LOGGER.exception(f"Failed loading module {module_name}")

def get_base_rarity(rarity_str):
    if not isinstance(rarity_str, str) or not rarity_str:
        return "common"
    
    rarity_str = rarity_str.lower().strip()
    
    for key, (r_db_emoji, _, r_name) in RARITIES.items():
        if key == rarity_str or r_name.lower() == rarity_str:
            return key

    for key, (r_db_emoji, _, r_name) in RARITIES.items():
        if key in rarity_str or r_name.lower() in rarity_str or r_db_emoji in rarity_str:
            return key
            
    return rarity_str

def format_time_taken(seconds):
    if seconds < 60:
        return f"{seconds}s"
    mins = seconds // 60
    secs = seconds % 60
    if secs == 0:
        return f"{mins}m"
    return f"{mins}m {secs}s"

async def load_rarity_status():
    global disabled_rarities_cache
    try:
        settings = await bot_settings_collection.find_one({'_id': 'game_settings'})
        if settings and 'disabled_rarities' in settings:
            disabled_rarities_cache = set(get_base_rarity(r) for r in settings['disabled_rarities'])
        else:
            disabled_rarities_cache = {"premium", "cosmic", "mythic"}
    except Exception:
        disabled_rarities_cache = {"premium", "cosmic", "mythic"}
    LOGGER.info(f"Loaded Disabled Rarities: {disabled_rarities_cache}")

async def get_group_setting(chat_id, setting_name, default=False):
    if chat_id not in group_settings_cache:
        doc = await group_settings_collection.find_one({'chat_id': chat_id})
        if doc:
            group_settings_cache[chat_id] = doc.get('settings', {})
        else:
            group_settings_cache[chat_id] = {}
    return group_settings_cache[chat_id].get(setting_name, default)

async def set_group_setting(chat_id, setting_name, value):
    if chat_id not in group_settings_cache:
        group_settings_cache[chat_id] = {}
    group_settings_cache[chat_id][setting_name] = value
    await group_settings_collection.update_one(
        {'chat_id': chat_id},
        {'$set': {f'settings.{setting_name}': value}},
        upsert=True
    )

async def is_admin(update: Update, context: CallbackContext) -> bool:
    user_id = update.effective_user.id
    if is_authorized(user_id):
        return True
    chat = update.effective_chat
    if chat.type in ('private'):
        return True
    member = await context.bot.get_chat_member(chat.id, user_id)
    return member.status in ('administrator', 'creator')

async def is_character_allowed(character, chat_id=None):
    if character.get('removed', False) or character.get('auction_exclusive', False):
        return False
        
    rarity = character.get('rarity', '🟢 Common')
    key = get_base_rarity(rarity)
    
    if key and key in disabled_rarities_cache:
        return False
        
    emoji = rarity.split(' ')[0] if isinstance(rarity, str) and ' ' in rarity else rarity
    if character.get('is_video', False) and emoji == '🎥':
        return chat_id == AMV_ALLOWED_GROUP_ID
        
    return True

async def _send_media(context, chat_id, character, caption):
    if character.get('is_video', False):
        return await context.bot.send_video(chat_id=chat_id, video=character.get('img_url'),
                                              caption=caption, parse_mode='HTML',
                                              supports_streaming=True)
    return await context.bot.send_photo(chat_id=chat_id, photo=character.get('img_url'),
                                         caption=caption, parse_mode='HTML')

async def load_spawns_and_counts(bot):
    global message_counts, active_spawns_cache
    
    try:
        counts = await chat_message_counts_collection.find({}).to_list(length=None)
        for doc in counts:
            message_counts[int(doc['chat_id'])] = doc.get('count', 0)
        LOGGER.info(f"⚡ [YADDASHT RESTORED] Message Counts loaded for {len(message_counts)} chats.")
        
        class DummyContext:
            def __init__(self, bot_instance):
                self.bot = bot_instance
                
        spawns = await spawns_collection.find({}).to_list(length=None)
        now = time.time()
        for spawn in spawns:
            chat_id = int(spawn['chat_id'])
            active_spawns_cache[chat_id] = spawn
            
            spawn_time = spawn.get('spawn_time', 0) 
            time_left = DESPAWN_TIME - (now - spawn_time)
            
            if time_left < 0:
                time_left = 2 
                
            asyncio.create_task(despawn_character(chat_id, spawn['message_id'], spawn['character'], DummyContext(bot), delay=time_left))
            
        LOGGER.info(f"⚡ [YADDASHT RESTORED] Loaded {len(active_spawns_cache)} Active Spawns.")
    except Exception as e:
        LOGGER.error(f"Memory restore failed: {e}")

async def despawn_character(chat_id, message_id, character, context, delay=DESPAWN_TIME):
    await asyncio.sleep(delay)
    try:
        active_spawns_cache.pop(chat_id, None) 
        
        active_spawn = await spawns_collection.find_one_and_delete({'chat_id': chat_id, 'message_id': message_id})
        
        if not active_spawn:
            return

        should_delete = await get_group_setting(chat_id, 'grab_delete', False)
        if should_delete:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except BadRequest:
                pass

        rarity_str = character.get('rarity', '🟢 Common')
        r_key = get_base_rarity(rarity_str)
        
        if r_key and r_key in RARITIES:
            _, r_display_emoji, r_name = RARITIES[r_key]
        else:
            r_display_emoji = rarity_str.split(' ')[0] if isinstance(rarity_str, str) and ' ' in rarity_str else '🟢'
            r_name = escape(rarity_str)

        caption = (
            f"<tg-emoji emoji-id=\"5413704112220949842\">⏰</tg-emoji> <b>ᴛɪᴍᴇ's ᴜᴘ! ʏᴏᴜ ᴀʟʟ ᴍɪssᴇᴅ ᴛʜɪs ᴡᴀɪғᴜ!</b>\n\n"
            f"<tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji> <b>ɴᴀᴍᴇ:</b> <b>{escape(character.get('name', 'Unknown'))}</b>\n"
            f"{r_display_emoji}<b> ʀᴀʀɪᴛʏ: {r_name}</b>\n"
            f"<tg-emoji emoji-id=\"6314494724266796319\">🟠</tg-emoji> <b>sᴏᴜʀᴄᴇ:</b> <b>{escape(character.get('anime', 'Unknown'))}</b>\n\n"
            f"<tg-emoji emoji-id=\"5278454020111887994\">💔</tg-emoji> <b>ʙᴇᴛᴛᴇʀ ʟᴜᴄᴋ ɴᴇxᴛ ᴛɪᴍᴇ!</b>"
        )
        missed_msg = await _send_media(context, chat_id, character, caption)
        
        asyncio.create_task(auto_delete_msg(context, chat_id, missed_msg.message_id, 1200))
        
        should_delete_miss = await get_group_setting(chat_id, 'miss_delete', False)
        if should_delete_miss:
            await asyncio.sleep(10)
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=missed_msg.message_id)
            except BadRequest:
                pass
    except Exception as e:
        LOGGER.error(f"despawn_character failed for chat={chat_id}: {e}")
    finally:
        currently_spawning.pop(chat_id, None)

async def message_counter(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or update.effective_chat.type not in ('group', 'supergroup'):
        return
    if not update.message and not update.edited_message:
        return

    chat_id = update.effective_chat.id 

    if await check_and_handle_flood(update, context):
        return

    # 🔥 Ghost Waifu Failsafe Engine (Agar error se character fass gaya hai memory me)
    if chat_id in active_spawns_cache:
        spawn_info = active_spawns_cache[chat_id]
        spawn_time = spawn_info.get('spawn_time', 0)
        if time.time() - spawn_time > DESPAWN_TIME:
            active_spawns_cache.pop(chat_id, None)
            # FIX: Await ki jagah pe create_task tha jo error de raha tha
            await spawns_collection.delete_one({'chat_id': chat_id})
            LOGGER.info(f"Ghost waifu cleared forcefully in Chat ID: {chat_id}")
        else:
            return # Waifu active hai sahi se, isliye message nahi ginega

    locks.setdefault(chat_id, asyncio.Lock())

    async with locks[chat_id]:
        # Double check in case cleared instantly
        if chat_id in active_spawns_cache:
            return
            
        if chat_id not in message_counts:
            try:
                doc = await chat_message_counts_collection.find_one({'chat_id': chat_id})
                if not doc:
                    doc = await chat_message_counts_collection.find_one({'chat_id': str(chat_id)})
                message_counts[chat_id] = doc.get('count', 0) if doc else 0
            except Exception:
                message_counts[chat_id] = 0

        message_counts[chat_id] += 1
        
        # FIX: Await lagaya taaki crash na ho
        await chat_message_counts_collection.update_one({'chat_id': chat_id}, {'$set': {'count': message_counts[chat_id]}}, upsert=True)
        
        try:
            chat_data = await user_totals_collection.find_one({'chat_id': chat_id})
            if not chat_data:
                chat_data = await user_totals_collection.find_one({'chat_id': str(chat_id)})
            
            target_frequency = chat_data.get('message_frequency', MESSAGE_FREQUENCY) if chat_data else MESSAGE_FREQUENCY
        except Exception:
            target_frequency = MESSAGE_FREQUENCY

        LOGGER.info(f"[LIVE LOG] Chat ID: {chat_id} | Message Count: {message_counts[chat_id]} / {target_frequency}")

        if message_counts[chat_id] >= target_frequency and not currently_spawning.get(chat_id):
            currently_spawning[chat_id] = True
            message_counts[chat_id] = 0
            
            # FIX: Yahan bhi await use hoga
            await chat_message_counts_collection.update_one({'chat_id': chat_id}, {'$set': {'count': 0}}, upsert=True)
            
            LOGGER.info(f"[SPAWN TRIGGERED] Target reached in Chat ID: {chat_id}. Starting send_image...")
            asyncio.create_task(send_image(update, context))

async def send_image(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    chat_id_str = str(chat_id)

    try:
        LOGGER.info(f"[SPAWN PROCESS] Fetching character details for Chat ID: {chat_id}")
        all_characters = await get_cached_characters()
        if not all_characters:
            LOGGER.warning(f"[SPAWN FAILED] Database me koi character nahi mila ya cache khali hai. Chat ID: {chat_id}")
            return

        sent_characters.setdefault(chat_id, [])
        if len(sent_characters[chat_id]) >= len(all_characters):
            sent_characters[chat_id] = []

        available = [c for c in all_characters if c.get('id') not in sent_characters[chat_id]] or all_characters
        allowed = [c for c in available if await is_character_allowed(c, chat_id)]

        if not allowed:
            LOGGER.warning(f"[SPAWN FAILED] Koi allowed character nahi mila (maybe sab rarities disabled hain). Chat ID: {chat_id}")
            return

        character = random.choice(allowed)
        sent_characters[chat_id].append(character['id'])

        caption = "<b><tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> ᴄʜᴀʀᴀᴄᴛᴇʀ ᴀᴘᴘᴇᴀʀᴇᴅ! <tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji>\nᴜsᴇ /grab (ɴᴀᴍᴇ) ᴛᴏ ᴄʟᴀɪᴍ ɪᴛ <tg-emoji emoji-id=\"6091214879379692751\">❤️‍🔥</tg-emoji></b>"
        
        LOGGER.info(f"[SPAWN ATTEMPT] Sending media for '{character.get('name')}' in Chat ID: {chat_id}")
        spawn_msg = await _send_media(context, chat_id, character, caption)
        
        LOGGER.info(f"[SPAWN SUCCESS] Character '{character.get('name')}' successfully spawned in Chat ID: {chat_id} (Message ID: {spawn_msg.message_id})")

        asyncio.create_task(auto_delete_msg(context, chat_id, spawn_msg.message_id, 1800))

        username = update.effective_chat.username
        spawn_message_link = (
            f"https://t.me/{username}/{spawn_msg.message_id}" if username
            else f"https://t.me/c/{chat_id_str.replace('-100', '')}/{spawn_msg.message_id}"
        )
        
        spawn_data = {
            'chat_id': chat_id,
            'character': character,
            'message_id': spawn_msg.message_id,
            'spawn_time': time.time(),
            'message_link': spawn_message_link
        }
        
        active_spawns_cache[chat_id] = spawn_data
        await spawns_collection.update_one({'chat_id': chat_id}, {'$set': spawn_data}, upsert=True)

        asyncio.create_task(despawn_character(chat_id, spawn_msg.message_id, character, context))

    except Exception as e:
        LOGGER.error(f"[SPAWN ERROR] Failed to spawn character in Chat ID: {chat_id}. Error: {e}")
    finally:
        currently_spawning[chat_id] = False

async def _bump_counter(coll, query, update_fields, inc_field='count', inc_by=1):
    doc = await coll.find_one(query)
    if doc:
        if update_fields:
            await coll.update_one(query, {'$set': update_fields})
        await coll.update_one(query, {'$inc': {inc_field: inc_by}})
    else:
        await coll.insert_one({**query, **update_fields, inc_field: inc_by})

async def guess(update: Update, context: CallbackContext) -> None:
    if await check_and_handle_flood(update, context):
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    grab_locks.setdefault(chat_id, asyncio.Lock())
    
    async with grab_locks[chat_id]:
        try:
            active_spawn = active_spawns_cache.get(chat_id)
            
            if not active_spawn:
                active_spawn = await spawns_collection.find_one({'chat_id': chat_id})
                if active_spawn:
                    active_spawns_cache[chat_id] = active_spawn

            if not active_spawn:
                if chat_id in last_grabbed and time.time() - last_grabbed[chat_id] < 60:
                    return await update.message.reply_html('<b>ᴡᴀɪғᴜ ᴀʟʀᴇᴀᴅʏ ɢʀᴀʙʙᴇᴅ ʙʏ sᴏᴍᴇᴏɴᴇ ᴇʟsᴇ <tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>.\nʙᴇᴛᴛᴇʀ ʟᴜᴄᴋ ɴᴇxᴛ ᴛɪᴍᴇ..!!</b>')
                return await update.message.reply_html('<b>ɴᴏ ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀs sᴘᴀᴡɴᴇᴅ ʏᴇᴛ!</b>')

            spawn_time = active_spawn.get('spawn_time', 0)
            if time.time() - spawn_time > DESPAWN_TIME:
                active_spawns_cache.pop(chat_id, None)
                await spawns_collection.delete_one({'chat_id': chat_id})
                return await update.message.reply_html('''<b><tg-emoji emoji-id="5413704112220949842">⏰</tg-emoji> ᴛɪᴍᴇ's ᴜᴘ! ʏᴏᴜ ᴀʟʟ ᴍɪssᴇᴅ ᴛʜɪs ᴡᴀɪғᴜ! (ᴇxᴘɪʀᴇᴅ)</b>''')

            guess_text = ' '.join(context.args).lower() if context.args else ''
            if not guess_text:
                return await update.message.reply_html('<b>ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ɴᴀᴍᴇ!</b>')
            if "()" in guess_text or "&" in guess_text:
                return await update.message.reply_html("<b>ɴᴀʜʜ ʏᴏᴜ ᴄᴀɴ'ᴛ ᴜsᴇ ᴛʜᴇsᴇ ᴛʏᴘᴇs ᴏғ ᴡᴏʀᴅs...<tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji></b>")

            character = active_spawn['character']
            char_name = character.get('name', '').lower()
            name_parts = char_name.split()
            
            is_correct = (
                sorted(name_parts) == sorted(guess_text.split())
                or guess_text in name_parts
                or guess_text == char_name
            )

            if not is_correct:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("ᴠɪᴇᴡ sᴘᴀᴡɴ ᴍᴇssᴀɢᴇ", url=active_spawn['message_link'])]])
                return await update.message.reply_html('<b>ᴘʟᴇᴀsᴇ ᴡʀɪᴛᴇ ᴀ ᴄᴏʀʀᴇᴄᴛ ɴᴀᴍᴇ..</b>', reply_markup=kb)

            active_spawns_cache.pop(chat_id, None)

            grabbed = await spawns_collection.find_one_and_delete({'chat_id': chat_id, 'message_id': active_spawn['message_id']})
            if not grabbed:
                return await update.message.reply_html('<b>ᴡᴀɪғᴜ ᴀʟʀᴇᴀᴅʏ ɢʀᴀʙʙᴇᴅ ʙʏ sᴏᴍᴇᴏɴᴇ ᴇʟsᴇ <tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>.\nʙᴇᴛᴛᴇʀ ʟᴜᴄᴋ ɴᴇxᴛ ᴛɪᴍᴇ..!!</b>')

            last_grabbed[chat_id] = time.time()  

            time_taken_seconds = round(time.time() - spawn_time)
            formatted_time = format_time_taken(time_taken_seconds)
                
            eu = update.effective_user
            user_fields = {'first_name': eu.first_name}
            if eu.username:
                user_fields['username'] = eu.username

            rarity_str = character.get('rarity', '🟢 Common')
            r_key = get_base_rarity(rarity_str)
            
            if r_key and r_key in RARITIES:
                _, r_display_emoji, r_name = RARITIES[r_key]
                r_name = escape(r_name)
            else:
                db_emoji, r_name = (rarity_str.split(' ', 1) + [''])[:2] if isinstance(rarity_str, str) and ' ' in rarity_str else (rarity_str, '')
                r_display_emoji = escape(db_emoji)
                r_name = escape(r_name)

            mention = f'<a href="tg://user?id={user_id}">{escape(eu.first_name)}</a>'

            success_message = (
                f"<tg-emoji emoji-id=\"6068790301076493707\">✅</tg-emoji> <b>{mention}, ᴄᴏɴɢʀᴀᴛs <tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji></b>\n"
                f"<b>ʏᴏᴜ ɢᴏᴛ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ <tg-emoji emoji-id=\"6093434630147415641\">🃏</tg-emoji></b>\n\n"
                f"<tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji> 𝗡𝗔𝗠𝗘:<b> {escape(character.get('name', 'Unknown'))}</b>\n"
                f"{r_display_emoji} 𝗥𝗔𝗥𝗜𝗧𝗬:<b> {r_name}</b>\n"
                f"<tg-emoji emoji-id=\"6314494724266796319\">🟠</tg-emoji> 𝗦𝗢𝗨𝗥𝗖𝗘:<b> {escape(character.get('anime', 'Unknown'))}</b>\n\n"
                f"<tg-emoji emoji-id=\"6307488052059053932\">🕐</tg-emoji> 𝗧𝗜𝗠𝗘 𝗧𝗔𝗞𝗘𝗡:<code> {formatted_time}</code>"
            )
            
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✨ ʜᴀʀᴇᴍ", switch_inline_query_current_chat=f"collection.{user_id}")]])
            
            await update.message.reply_text(success_message, parse_mode='HTML', reply_markup=kb)

            async def process_background_tasks(spawn_msg_id):
                try:
                    try:
                        reactions = ["🔥", "🍓", "❤️", "🎉", "😍", "🥰", "⚡", "🏆", "👏", "❤️‍🔥", "🍾", "💯", "💘", "👌", "🕊️", "🤩", "🐳"]
                        await update.message.set_reaction(reaction=random.choice(reactions))
                    except Exception:
                        pass

                    user = await user_collection.find_one({'id': user_id})
                    if user:
                        changed = {k: v for k, v in user_fields.items() if user.get(k) != v}
                        if changed:
                            await user_collection.update_one({'id': user_id}, {'$set': changed})
                        await user_collection.update_one({'id': user_id}, {'$push': {'characters': character}})
                    else:
                        await user_collection.insert_one({
                            'id': user_id, 
                            **user_fields, 
                            'characters': [character],
                            'bot_started': False
                        })

                    await eco_collection.update_one(
                        {'id': user_id},
                        {
                            '$set': user_fields,
                            '$setOnInsert': {'balance': 0, 'tokens': 0, 'bot_started': False}
                        },
                        upsert=True
                    )

                    try:
                        from shivu.modules.inline import user_cache, query_cache
                        user_cache.pop(f"u{user_id}", None)
                        query_cache.clear()
                    except Exception:
                        pass

                    should_delete = await get_group_setting(chat_id, 'grab_delete', False)
                    if should_delete and spawn_msg_id:
                        try:
                            await context.bot.delete_message(chat_id=chat_id, message_id=spawn_msg_id)
                        except BadRequest:
                            pass

                    await _bump_counter(group_user_totals_collection, {'user_id': user_id, 'group_id': chat_id}, user_fields)
                    await _bump_counter(top_global_groups_collection, {'group_id': chat_id}, {'group_name': update.effective_chat.title})

                except Exception as e:
                    LOGGER.error(f"Error in background grab process: {e}")

            asyncio.create_task(process_background_tasks(active_spawn['message_id']))

        except Exception as e:
            LOGGER.error(f"Guess Error: {e}")

async def toggle_grab_delete_cmd(update: Update, context: CallbackContext) -> None:
    if not await is_admin(update, context):
        return await update.message.reply_html('<b>ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ!</b>')
    chat_id = update.effective_chat.id
    if not context.args or context.args[0].lower() not in ('on', 'off'):
        return await update.message.reply_html('<b><tg-emoji emoji-id=\"5422439311196834318\">💡</tg-emoji> ᴜsᴀɢᴇ:</b> /grab_delete [on|off]')
    mode = context.args[0].lower() == 'on'
    await set_group_setting(chat_id, 'grab_delete', mode)
    state = "<b>ᴇɴᴀʙʟᴇᴅ (sᴘᴀᴡɴɪɴɢ ᴍsɢ ᴡɪʟʟ ᴅᴇʟᴇᴛᴇ ᴏɴ ɢʀᴀʙ)</b>" if mode else "<b>ᴅɪsᴀʙʟᴇᴅ (sᴘᴀᴡɴɪɴɢ ᴍsɢ ᴡᴏɴ'ᴛ ᴅᴇʟᴇᴛᴇ)</b>"
    await update.message.reply_html(f'<b><tg-emoji emoji-id="6307567066572396133\">⚙</tg-emoji> ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ᴏɴ ɢʀᴀʙ ɪs ɴᴏᴡ:</b> {state}')

async def toggle_miss_delete_cmd(update: Update, context: CallbackContext) -> None:
    if not await is_admin(update, context):
        return await update.message.reply_html('<b>ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ!</b>')
    chat_id = update.effective_chat.id
    if not context.args or context.args[0].lower() not in ('on', 'off'):
        return await update.message.reply_html('<b><tg-emoji emoji-id=\"5422439311196834318\">💡</tg-emoji> ᴜsᴀɢᴇ:</b> /miss_delete [on|off]')
    mode = context.args[0].lower() == 'on'
    await set_group_setting(chat_id, 'miss_delete', mode)
    state = "<b>ᴇɴᴀʙʟᴇᴅ (ᴍɪssᴇᴅ ᴍsɢs ᴡɪʟʟ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ)</b>" if mode else "<b>ᴅɪsᴀʙʟᴇᴅ (ᴍɪssᴇᴅ ᴍsɢs ᴡᴏɴ'ᴛ ᴅᴇʟᴇᴛᴇ)</b>"
    await update.message.reply_html(f'<b><tg-emoji emoji-id="6307567066572396133\">⚙</tg-emoji> ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ᴏɴ ᴍɪss ɪs ɴᴏᴡ:</b> {state}')

async def rarity_status_cmd(update: Update, context: CallbackContext) -> None:
    global disabled_rarities_cache
    lines = ["<b><tg-emoji emoji-id=\"5256131095094652290\">🎯</tg-emoji> ʀᴀʀɪᴛʏ sᴘᴀᴡɴ sᴛᴀᴛᴜs</b>\n"]
    for key, (_, display_emoji, name) in RARITIES.items():
        is_on = key not in disabled_rarities_cache
        state = "<tg-emoji emoji-id=\"6118676380579274277\">✅</tg-emoji> ᴏɴ" if is_on else "<tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ᴏғғ"
        lines.append(f"{display_emoji} <b>{escape(name)}</b> (<code>{key}</code>) — {state}")
    lines.append("\n<b>ᴜsᴇ /rarity_on &lt;key&gt; ᴏʀ /rarity_off &lt;key&gt; ᴛᴏ ᴄʜᴀɴɢᴇ.</b>")
    await update.message.reply_html("\n".join(lines))

async def _rarity_toggle_cmd(update: Update, context: CallbackContext, enable: bool) -> None:
    global disabled_rarities_cache
    if not is_authorized(update.effective_user.id):
        return  
    if not context.args:
        cmd = "/rarity_on" if enable else "/rarity_off"
        return await update.message.reply_html(f'<b><tg-emoji emoji-id=\"5422439311196834318\">💡</tg-emoji> ᴜsᴀɢᴇ:</b> {cmd} &lt;rarity_key&gt;')
        
    raw_input = " ".join(context.args)
    base_key = get_base_rarity(raw_input)

    if not base_key or base_key not in RARITIES:
        return await update.message.reply_html(f'<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ᴜɴᴋɴᴏᴡɴ ʀᴀʀɪᴛʏ:</b> <code>{escape(raw_input)}</code>')

    _, display_emoji, name = RARITIES[base_key]

    if enable: 
        if base_key in disabled_rarities_cache:
            disabled_rarities_cache.remove(base_key)
            await bot_settings_collection.update_one({'_id': 'game_settings'}, {'$set': {'disabled_rarities': list(disabled_rarities_cache)}}, upsert=True)
            await update.message.reply_html(f"✅ <b>ʀᴀʀɪᴛʏ '{escape(name)}' ʜᴀs ʙᴇᴇɴ ᴇɴᴀʙʟᴇᴅ.</b>")
        else:
            await update.message.reply_html(f"⚠️ <b>ʀᴀʀɪᴛʏ '{escape(name)}' ɪs ᴀʟʀᴇᴀᴅʏ ᴇɴᴀʙʟᴇᴅ.</b>")
    else:
        if base_key not in disabled_rarities_cache:
            disabled_rarities_cache.add(base_key)
            await bot_settings_collection.update_one({'_id': 'game_settings'}, {'$set': {'disabled_rarities': list(disabled_rarities_cache)}}, upsert=True)
            await update.message.reply_html(f"❌ <b>ʀᴀʀɪᴛʏ '{escape(name)}' ʜᴀs ʙᴇᴇɴ ᴅɪsᴀʙʟᴇᴅ.</b>")
        else:
            await update.message.reply_html(f"⚠️ <b>ʀᴀʀɪᴛʏ '{escape(name)}' ɪs ᴀʟʀᴇᴀᴅʏ ᴅɪsᴀʙʟᴇᴅ.</b>")

async def rarity_on_cmd(update, context):
    await _rarity_toggle_cmd(update, context, True)

async def rarity_off_cmd(update, context):
    await _rarity_toggle_cmd(update, context, False)

async def name_cmd(update: Update, context: CallbackContext) -> None:
    if not is_authorized(update.effective_user.id):
        return  
    chat_id = update.effective_chat.id
    
    active_spawn = active_spawns_cache.get(chat_id)
    if not active_spawn:
        active_spawn = await spawns_collection.find_one({'chat_id': chat_id})
        
    if not active_spawn:
        return await update.message.reply_html('<b>ɴᴏ ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀs sᴘᴀᴡɴᴇᴅ ʏᴇᴛ!</b>')
        
    c = active_spawn['character']
    rarity_str = c.get('rarity', '🟢 Common')
    r_key = get_base_rarity(rarity_str)
    
    if r_key and r_key in RARITIES:
        _, r_display_emoji, r_name = RARITIES[r_key]
        display_rarity = f"{r_display_emoji} {escape(r_name)}"
    else:
        display_rarity = escape(rarity_str)
        
    text = (
        "<b><tg-emoji emoji-id=\"5359441070201513074\">🎭</tg-emoji> ᴄᴜʀʀᴇɴᴛ sᴘᴀᴡɴᴇᴅ ᴄʜᴀʀᴀᴄᴛᴇʀ:</b>\n\n"
        f"<b><tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji> ɴᴀᴍᴇ:</b><code> {escape(c.get('name', 'Unknown'))} </code>\n"
        f"<b><tg-emoji emoji-id=\"6314494724266796319\">🟠</tg-emoji> ᴀɴɪᴍᴇ:</b><code> {escape(c.get('anime', 'Unknown'))} </code>\n"
        f"{r_display_emoji} <b>ʀᴀʀɪᴛʏ:</b><code> {r_name} </code>\n"
        f"<b><tg-emoji emoji-id=\"6093857216274635770\">🔖</tg-emoji> ɪᴅ:</b><code> {escape(str(c.get('id', 'Unknown')))} </code>\n\n"
        "<b><tg-emoji emoji-id=\"5422439311196834318\">💡</tg-emoji> ᴜsᴇ /grab (ɴᴀᴍᴇ) ᴛᴏ ᴀᴅᴅ ɪᴛ ᴛᴏ ʏᴏᴜʀ ʜᴀʀᴇᴍ!</b>"
    )
    await update.message.reply_html(text)

async def main():
    try:
        await setup_database_indexes()
        await load_rarity_status()
        
        await load_spawns_and_counts(application.bot)
        
        await shivuu.start()

        application.add_handler(CommandHandler(["grab", "g"], guess, block=False))
        application.add_handler(CommandHandler(["grab_delete"], toggle_grab_delete_cmd, block=False))
        application.add_handler(CommandHandler(["miss_delete"], toggle_miss_delete_cmd, block=False))
        application.add_handler(CommandHandler(["rarity_status"], rarity_status_cmd, block=False))
        application.add_handler(CommandHandler(["rarity_on"], rarity_on_cmd, block=False))
        application.add_handler(CommandHandler(["rarity_off"], rarity_off_cmd, block=False))
        application.add_handler(CommandHandler(["name"], name_cmd, block=False))

        # 🔥 FIX: Priority super high set kar di (-999) taaki koi module message aage rok na paye
        application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, message_counter, block=False), group=-999)

        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

        LOGGER.info("✅ ʀᴀɴᴅɪ ʙᴏᴛ sᴛᴀʀᴛᴇᴅ")

        try:
            from shivu.modules.chatlog import send_log_to_group, create_log_message
            bot_info = await application.bot.get_me()
            data = {
                "Bot": f"<b>@{bot_info.username}</b>",
                "Status": "<b>Online & Ready <tg-emoji emoji-id=\"6093708348413189642\">⚡️</tg-emoji></b>"
            }
            log_msg = create_log_message("˹ Bot Restarted ˼ <tg-emoji emoji-id=\"6093679829830344586\">🔝</tg-emoji>", data)
            asyncio.create_task(send_log_to_group(log_msg))
        except Exception as e:
            LOGGER.error(f"Failed to queue startup log: {e}")

        await asyncio.Event().wait()

    except Exception:
        LOGGER.exception("Bot crashed!")
        traceback.print_exc()

    finally:
        LOGGER.info("Stopping bot...")
        for coro in (application.updater.stop, application.stop, application.shutdown, shivuu.stop):
            try:
                await coro()
            except Exception:
                pass

if __name__ == "__main__":
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()

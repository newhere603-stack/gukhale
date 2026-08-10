import asyncio
import shivu.modules.balance
import shivu.modules.chatlog
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

import importlib
import random
import time  
import traceback
from html import escape
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, CallbackContext, MessageHandler, filters
from telegram.error import BadRequest

from shivu import db, shivuu, application, LOGGER, user_totals_collection
from shivu.modules import ALL_MODULES

OWNER_ID = 7657218453
SUDO_USERS = [7657218453]

collection = db['anime_characters_lol']
user_collection = db['user_collection_lmaoooo']
group_user_totals_collection = db['group_user_totalsssssss']
top_global_groups_collection = db['top_global_groups']
rarity_status_collection = db['rarity_status_settings']
group_settings_collection = db['group_settings_db']

MESSAGE_FREQUENCY = 70
DESPAWN_TIME = 180  # 3 minutes (180 seconds)
AMV_ALLOWED_GROUP_ID = -1003100468240

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
    "pearl": ("🏖️", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"), 
    "cosmic": ("🌌", '<tg-emoji emoji-id="5431783411981228752">🎆</tg-emoji>', "Cosmic"),
}

rarity_status_cache = {}
group_settings_cache = {}  
locks, message_counts = {}, {}
sent_characters, last_characters = {}, {}
first_correct_guesses, spawn_messages, spawn_message_links = {}, {}, {}
currently_spawning = {}
spawn_times = {}  
grabbed_spawns = set()  

_cached_characters = []
_last_cache_time = 0

async def get_cached_characters():
    global _cached_characters, _last_cache_time
    current_time = time.time()
    if not _cached_characters or (current_time - _last_cache_time) > 300:
        _cached_characters = await collection.find({'auction_exclusive': {'$ne': True}}).to_list(length=None)
        _last_cache_time = current_time
    return _cached_characters

for module_name in ALL_MODULES:
    try:
        importlib.import_module("shivu.modules." + module_name)
    except Exception:
        LOGGER.exception(f"Failed loading module {module_name}")


def get_rarity_key(rarity_str):
    if not isinstance(rarity_str, str):
        return None
    rarity_str = rarity_str.strip()
    db_emoji, name = (rarity_str.split(' ', 1) + [''])[:2] if ' ' in rarity_str else (rarity_str, '')
    name = name.strip().lower()
    for key, (r_db_emoji, _, r_name) in RARITIES.items():
        if rarity_str.lower() == key or db_emoji == r_db_emoji or name == r_name.lower():
            return key
    return None


# 🔥 Time Formatter Helper Function (e.g., 65s -> 1m 5s)
def format_time_taken(seconds):
    if seconds < 60:
        return f"{seconds}s"
    mins = seconds // 60
    secs = seconds % 60
    if secs == 0:
        return f"{mins}m"
    return f"{mins}m {secs}s"


async def load_rarity_status():
    try:
        doc = await rarity_status_collection.find_one({'_id': 'settings'})
        saved = doc.get('status', {}) if doc else {}
    except Exception:
        saved = {}
    for key in RARITIES:
        rarity_status_cache[key] = saved.get(key, True)
    LOGGER.info(f"Rarity status loaded: {rarity_status_cache}")


async def set_rarity_status(key, enabled):
    rarity_status_cache[key] = enabled
    await rarity_status_collection.update_one(
        {'_id': 'settings'}, {'$set': {f'status.{key}': enabled}}, upsert=True
    )


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


def is_authorized(user_id):
    return user_id == OWNER_ID or user_id in SUDO_USERS


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
    emoji = rarity.split(' ')[0] if isinstance(rarity, str) and ' ' in rarity else rarity
    key = get_rarity_key(rarity)
    
    if key is not None and not rarity_status_cache.get(key, True):
        return False
        
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


async def despawn_character(chat_id, message_id, character, context):
    await asyncio.sleep(DESPAWN_TIME)
    try:
        if message_id in grabbed_spawns:
            grabbed_spawns.discard(message_id) 
            return

        should_delete = await get_group_setting(chat_id, 'grab_delete', False)
        if should_delete:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except BadRequest:
                pass

        rarity_str = character.get('rarity', '🟢 Common')
        r_key = get_rarity_key(rarity_str)
        
        if r_key and r_key in RARITIES:
            _, r_display_emoji, r_name = RARITIES[r_key]
        else:
            r_display_emoji = rarity_str.split(' ')[0] if isinstance(rarity_str, str) and ' ' in rarity_str else '🟢'
            r_name = escape(rarity_str)

        caption = (
            f"<tg-emoji emoji-id=\"5413704112220949842\">⏰</tg-emoji> <b>ᴛɪᴍᴇ's ᴜ𝙥! ʏᴏᴜ ᴀʟʟ ᴍɪssᴇᴅ ᴛʜɪs ᴡᴀɪғᴜ!</b>\n\n"
            f"<tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji> <b>ɴᴀᴍᴇ:</b> <b>{escape(character.get('name', 'Unknown'))}</b>\n"
            f"{r_display_emoji}<b> ʀᴀʀɪᴛʏ: {r_name}</b>\n"
            f"<tg-emoji emoji-id=\"6312254267461739671\">⛩</tg-emoji> <b>ᴀɴɪᴍᴇ:</b> <b>{escape(character.get('anime', 'Unknown'))}</b>\n\n"
            f"<tg-emoji emoji-id=\"5278454020111887994\">💔</tg-emoji> <b>ʙᴇᴛᴛᴇʀ ʟᴜᴄᴋ ɴᴇxᴛ ᴛɪᴍᴇ!</b>"
        )
        missed_msg = await _send_media(context, chat_id, character, caption)
        
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
        if spawn_messages.get(chat_id) == message_id:
            last_characters.pop(chat_id, None)
            spawn_messages.pop(chat_id, None)
            spawn_message_links.pop(chat_id, None)
            currently_spawning.pop(str(chat_id), None)
            spawn_times.pop(chat_id, None)
            first_correct_guesses.pop(chat_id, None)


async def message_counter(update: Update, context: CallbackContext) -> None:
    if update.effective_chat.type not in ('group', 'supergroup'):
        return
    if not update.message and not update.edited_message:
        return

    chat_id = str(update.effective_chat.id)
    locks.setdefault(chat_id, asyncio.Lock())

    async with locks[chat_id]:
        message_counts[chat_id] = message_counts.get(chat_id, 0) + 1
        
        try:
            chat_data = await user_totals_collection.find_one({'chat_id': chat_id})
            target_frequency = chat_data.get('message_frequency', MESSAGE_FREQUENCY) if chat_data else MESSAGE_FREQUENCY
        except Exception:
            target_frequency = MESSAGE_FREQUENCY

        if message_counts[chat_id] >= target_frequency and not currently_spawning.get(chat_id):
            currently_spawning[chat_id] = True
            message_counts[chat_id] = 0
            asyncio.create_task(send_image(update, context))


async def send_image(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    chat_id_str = str(chat_id)

    try:
        all_characters = await get_cached_characters()
        if not all_characters:
            return

        sent_characters.setdefault(chat_id, [])
        if len(sent_characters[chat_id]) >= len(all_characters):
            sent_characters[chat_id] = []

        available = [c for c in all_characters if c.get('id') not in sent_characters[chat_id]] or all_characters
        allowed = [c for c in available if await is_character_allowed(c, chat_id)]

        if not allowed:
            return

        character = random.choice(allowed)
        sent_characters[chat_id].append(character['id'])
        last_characters[chat_id] = character
        first_correct_guesses.pop(chat_id, None)

        caption = "<b><tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> ᴄʜᴀʀᴀᴄᴛᴇʀ ᴀᴘᴘᴇᴀʀᴇᴅ! <tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji>\nᴜsᴇ /grab (ɴᴀᴍᴇ) ᴛᴏ ᴄʟᴀɪᴍ ɪᴛ <tg-emoji emoji-id=\"6091214879379692751\">❤️‍🔥</tg-emoji></b>"
        spawn_msg = await _send_media(context, chat_id, character, caption)

        spawn_messages[chat_id] = spawn_msg.message_id
        spawn_times[chat_id] = time.time()  
        username = update.effective_chat.username
        spawn_message_links[chat_id] = (
            f"https://t.me/{username}/{spawn_msg.message_id}" if username
            else f"https://t.me/c/{chat_id_str.replace('-100', '')}/{spawn_msg.message_id}"
        )
        asyncio.create_task(despawn_character(chat_id, spawn_msg.message_id, character, context))

    except Exception:
        pass
    finally:
        currently_spawning[chat_id_str] = False


async def _bump_counter(coll, query, update_fields, inc_field='count', inc_by=1):
    doc = await coll.find_one(query)
    if doc:
        if update_fields:
            await coll.update_one(query, {'$set': update_fields})
        await coll.update_one(query, {'$inc': {inc_field: inc_by}})
    else:
        await coll.insert_one({**query, **update_fields, inc_field: inc_by})


async def guess(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    try:
        if chat_id not in last_characters:
            return await update.message.reply_html('<b>ɴᴏ ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀs sᴘᴀᴡɴᴇᴅ ʏᴇᴛ!</b>')

        if chat_id in first_correct_guesses:
            return await update.message.reply_html(
                '<b>ᴡᴀɪғᴜ ᴀʟʀᴇᴀᴅʏ ɢʀᴀʙʙᴇᴅ ʙʏ sᴏᴍᴇᴏɴᴇ ᴇʟsᴇ <tg-emoji emoji-id="6093708348413189642\">⚡️</tg-emoji>. ʙᴇᴛᴛᴇʀ ʟᴜᴄᴋ ɴᴇxᴛ ᴛɪᴍᴇ..!!</b>'
            )

        guess_text = ' '.join(context.args).lower() if context.args else ''
        if not guess_text:
            return await update.message.reply_html('<b>ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ɴᴀᴍᴇ!</b>')
        if "()" in guess_text or "&" in guess_text:
            return await update.message.reply_html("<b>ɴᴀʜʜ ʏᴏᴜ ᴄᴀɴ'ᴛ ᴜsᴇ ᴛʜɪs ᴛʏᴘᴇs ᴏғ ᴡᴏʀᴅs...<tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji></b>")

        character = last_characters[chat_id]
        char_name = character.get('name', '').lower()
        name_parts = char_name.split()
        is_correct = (
            sorted(name_parts) == sorted(guess_text.split())
            or guess_text in name_parts
            or guess_text == char_name
        )

        if not is_correct:
            kb = None
            if chat_id in spawn_message_links:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("ᴠɪᴇᴡ sᴘᴀᴡɴ ᴍᴇssᴀɢᴇ", url=spawn_message_links[chat_id])]])
            return await update.message.reply_html('<b>ᴘʟᴇᴀsᴇ ᴡʀɪᴛᴇ ᴀ ᴄᴏʀʀᴇᴄᴛ ɴᴀᴍᴇ..</b>', reply_markup=kb)

        time_taken_seconds = 0
        if chat_id in spawn_times:
            time_taken_seconds = round(time.time() - spawn_times[chat_id])
        
        # Format time using helper function
        formatted_time = format_time_taken(time_taken_seconds)
            
        spawn_msg_id = spawn_messages.get(chat_id)
        if spawn_msg_id:
            grabbed_spawns.add(spawn_msg_id)
            
        first_correct_guesses[chat_id] = user_id
        
        should_delete = await get_group_setting(chat_id, 'grab_delete', False)
        if should_delete and spawn_msg_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=spawn_msg_id)
            except BadRequest:
                pass
            spawn_messages.pop(chat_id, None)

        eu = update.effective_user
        user_fields = {'first_name': eu.first_name}
        if eu.username:
            user_fields['username'] = eu.username

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
                'balance': 500,
                'bot_started': False
            })

        try:
            from shivu.modules.inline import user_cache, query_cache
            user_cache.pop(f"u{user_id}", None)
            query_cache.clear()
        except Exception:
            pass

        await _bump_counter(group_user_totals_collection, {'user_id': user_id, 'group_id': chat_id}, user_fields)
        await _bump_counter(top_global_groups_collection, {'group_id': chat_id}, {'group_name': update.effective_chat.title})

        rarity_str = character.get('rarity', '🟢 Common')
        r_key = get_rarity_key(rarity_str)
        
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
            f"<tg-emoji emoji-id=\"6314494724266796319\">🟠</tg-emoji> 𝗔𝗡𝗜𝗠𝗘:<b> {escape(character.get('anime', 'Unknown'))}</b>\n\n"
            f"<tg-emoji emoji-id=\"6307488052059053932\">🕐</tg-emoji> 𝗧𝗜𝗠𝗘 𝗧𝗔𝗞𝗘𝗡:<code> {formatted_time}</code>"
        )
        
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✨ ʜᴀʀᴇᴍ", switch_inline_query_current_chat=f"collection.{user_id}")]])
        await update.message.reply_text(success_message, parse_mode='HTML', reply_markup=kb)
        
        spawn_message_links.pop(chat_id, None)
        spawn_times.pop(chat_id, None)

    except Exception:
        pass


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
    lines = ["<b><tg-emoji emoji-id=\"5256131095094652290\">🎯</tg-emoji> ʀᴀʀɪᴛʏ sᴘᴀᴡɴ sᴛᴀᴛᴜs</b>\n"]
    for key, (_, display_emoji, name) in RARITIES.items():
        state = "<tg-emoji emoji-id=\"6118676380579274277\">✅</tg-emoji> ᴏɴ" if rarity_status_cache.get(key, True) else "<tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ᴏғғ"
        lines.append(f"{display_emoji} <b>{escape(name)}</b> (<code>{key}</code>) — {state}")
    lines.append("\n<b>ᴜsᴇ /rarity_on <key> ᴏʀ /rarity_off <key> ᴛᴏ ᴄʜᴀɴɢᴇ.</b>")
    await update.message.reply_html("\n".join(lines))


async def _rarity_toggle_cmd(update: Update, context: CallbackContext, enable: bool) -> None:
    if not is_authorized(update.effective_user.id):
        return  
    if not context.args:
        cmd = "/rarity_on" if enable else "/rarity_off"
        return await update.message.reply_html(f'<b><tg-emoji emoji-id=\"5422439311196834318\">💡</tg-emoji> ᴜsᴀɢᴇ:</b> {cmd} &lt;rarity_key&gt;')
    key = context.args[0].lower()
    if key not in RARITIES:
        return await update.message.reply_html(f'<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ᴜɴᴋɴᴏᴡɴ ʀᴀʀɪᴛʏ ᴋᴇʏ:</b> <code>{escape(key)}</code>')
    await set_rarity_status(key, enable)
    _, display_emoji, name = RARITIES[key]
    state = "ᴇɴᴀʙʟᴇᴅ ᴀɴᴅ ᴄᴀɴ sᴘᴀᴡɴ" if enable else "ᴅɪsᴀʙʟᴇᴅ ᴀɴᴅ ᴡɪʟʟ ɴᴏᴛ sᴘᴀᴡɴ"
    icon = "<tg-emoji emoji-id=\"6118676380579274277\">✅</tg-emoji>" if enable else "<tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji>"
    await update.message.reply_html(f'<b>{icon} {display_emoji} {escape(name)} ʀᴀʀɪᴛʏ ɪs ɴᴏᴡ {state}.</b>')


async def rarity_on_cmd(update, context):
    await _rarity_toggle_cmd(update, context, True)


async def rarity_off_cmd(update, context):
    await _rarity_toggle_cmd(update, context, False)


async def name_cmd(update: Update, context: CallbackContext) -> None:
    if not is_authorized(update.effective_user.id):
        return  
    chat_id = update.effective_chat.id
    if chat_id not in last_characters:
        return await update.message.reply_html('<b>ɴᴏ ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀs sᴘᴀᴡɴᴇᴅ ʏᴇᴛ!</b>')
    c = last_characters[chat_id]
    rarity_str = c.get('rarity', '🟢 Common')
    r_key = get_rarity_key(rarity_str)
    if r_key and r_key in RARITIES:
        _, r_display_emoji, r_name = RARITIES[r_key]
        display_rarity = f"{r_display_emoji} {escape(r_name)}"
    else:
        display_rarity = escape(rarity_str)
    text = (
        "<b><tg-emoji emoji-id=\"5359441070201513074\">🎭</tg-emoji> ᴄᴜʀʀᴇɴᴛ sᴘᴀᴡɴᴇᴅ ᴄʜᴀʀᴀᴄᴛᴇʀ:</b>\n\n"
        f"<b><tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji> ɴᴀᴍᴇ:</b> {escape(c.get('name', 'Unknown'))}\n"
        f"<b><tg-emoji emoji-id=\"6312254267461739671\">⛩</tg-emoji> ᴀɴɪᴍᴇ:</b> {escape(c.get('anime', 'Unknown'))}\n"
        f"{display_rarity} <b>ʀᴀʀɪᴛʏ:</b>\n"
        f"<b><tg-emoji emoji-id=\"6093857216274635770\">🔖</tg-emoji> ɪᴅ:</b> {escape(str(c.get('id', 'Unknown')))}\n\n"
        "<b><tg-emoji emoji-id=\"5422439311196834318\">💡</tg-emoji> ᴜsᴇ /grab (ɴᴀᴍᴇ) ᴛᴏ ᴀᴅᴅ ɪᴛ ᴛᴏ ʏᴏᴜʀ ʜᴀʀᴇᴍ!</b>"
    )
    await update.message.reply_html(text)


async def main():
    try:
        await load_rarity_status()
        await shivuu.start()

        application.add_handler(CommandHandler(["grab", "g"], guess, block=False))
        application.add_handler(CommandHandler(["grab_delete"], toggle_grab_delete_cmd, block=False))
        application.add_handler(CommandHandler(["miss_delete"], toggle_miss_delete_cmd, block=False))
        application.add_handler(CommandHandler(["rarity_status"], rarity_status_cmd, block=False))
        application.add_handler(CommandHandler(["rarity_on"], rarity_on_cmd, block=False))
        application.add_handler(CommandHandler(["rarity_off"], rarity_off_cmd, block=False))
        application.add_handler(CommandHandler(["name"], name_cmd, block=False))

        application.add_handler(MessageHandler(filters.ALL, message_counter, block=False), group=1)

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

import asyncio
import math
import random
import traceback
import logging
import re
import time
import html
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo, InputMediaAnimation
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from telegram.constants import ParseMode
from telegram.error import RetryAfter, BadRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from shivu import application, user_collection, db
from shivu.Database.db import eco_collection

collection = db['anime_characters_lol']

# Database collections games ko hamesha yaad rakhne ke liye
tic_collection = db['tic_games']
mines_collection = db['mines_games']
settings_collection = db['bot_settings'] # Settings collection for rarity toggles

# 🔥 Nayi collection Yaddasht (Auto-Delete) ke liye
delete_collection = db['auto_delete_queue']

LOG_GROUP_ID = -1003893927065
IST = timezone(timedelta(hours=5, minutes=30))
OWNER_ID = 7657218453 # Added Owner ID

# Anti-spam & Fast Queue locks
active_claims = set()
play_again_cooldowns = {} 
mines_locks = {}
tic_locks = {}

RARITIES = {
    "common": ("🟢", '<tg-emoji emoji-id="6093865707424980866">🟢</tg-emoji>', "Common"), 
    "rare": ("🟠", '<tg-emoji emoji-id="5339390195768774311">🟠</tg-emoji>', "Rare"), 
    "legendary": ("🟡", '<tg-emoji emoji-id="6084550327086883643">🔥</tg-emoji>', "Legendary"),
    "special": ("🔴", '<tg-emoji emoji-id="6093741664474504699">🔴</tg-emoji>', "Medium"), 
    "celestial": ("🪽", '<tg-emoji emoji-id="5434121252874756456">🕊</tg-emoji>', "Celestial"), 
    "erotic": ("🥵", '<tg-emoji emoji-id="6093490292923574796">❤️‍🔥</tg-emoji>', "Spicy"),
    "exclusive": ("💮", '<tg-emoji emoji-id="6100567406889935797">🤴</tg-emoji>', "Exclusive"), 
    "premium": ("🔮", '<tg-emoji emoji-id="6093919703753831564">🔮</tg-emoji>', "Premium Edition"), 
    "mythic": ("💎", '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>', "Mythic"),
    "sweet": ("🍭", '<tg-emoji emoji-id="6222115531122546353">🍭</tg-emoji>', "Sweet"), 
    "valentine": ("💞", '<tg-emoji emoji-id="5255861796350224063">❤️</tg-emoji>', "Valentine"), 
    "winter": ("❄️", '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>', "Winter"),
    "neon": ("⚡", '<tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>', "Neon"), 
    "pearl": ("🏖️", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"), 
    "cosmic": ("🌌", '<tg-emoji emoji-id="5431783411981228752">🎆</tg-emoji>', "Cosmic"),
}

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

def to_small_caps(text: str) -> str:
    if not text:
        return "ᴜɴᴋɴᴏᴡɴ"
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    tr = str.maketrans(normal, small)
    return str(text).translate(tr)

sc = to_small_caps

def create_log_message(title: str, data: dict) -> str:
    timestamp = datetime.now(IST).strftime("%I:%M %p • %d/%m/%y")
    base = f"<b>{title}</b>\n\n"
    items = list(data.items())
    for i, (key, value) in enumerate(items):
        prefix = "<b>╰</b>" if i == len(items) - 1 else "<b>├</b>"
        base += f"{prefix} <b>{key} :</b> {value}\n"
    base += f"\n<b>⌚ ᴛɪᴍᴇ :</b> <b>{timestamp}</b>"
    return base

async def send_log(context: CallbackContext, text: str):
    try:
        await context.bot.send_message(
            chat_id=LOG_GROUP_ID,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Log error: {e}")

_worker_started = False

async def background_delete_worker(bot):
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
        await asyncio.sleep(30)

async def silent_auto_delete(message, delay_seconds: int = 1200):
    if not message: return
        
    global _worker_started
    if not _worker_started:
        _worker_started = True
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


def can_claim_today(last_claim_utc) -> bool:
    if not last_claim_utc:
        return True
    
    if last_claim_utc.tzinfo is None:
        last_claim_utc = last_claim_utc.replace(tzinfo=timezone.utc)
    
    last_claim_ist = last_claim_utc.astimezone(IST)
    now_ist = datetime.now(IST)
    
    today_4am = now_ist.replace(hour=4, minute=0, second=0, microsecond=0)
    
    if now_ist < today_4am:
        reset_threshold = today_4am - timedelta(days=1)
    else:
        reset_threshold = today_4am
        
    return last_claim_ist < reset_threshold

async def get_allowed_rarities():
    config = await settings_collection.find_one({'setting': 'swaifu_rarities'})
    if config and 'allowed' in config:
        return config['allowed']
    return ["celestial", "exclusive", "legendary", "sweet", "special edition", "rare", "common"]

async def swaifu(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in active_claims:
        return
    active_claims.add(user_id)
    
    try:
        raw_first_name = update.effective_user.first_name or "User"
        safe_first_name = html.escape(raw_first_name)
        now_utc = datetime.now(timezone.utc)
        user_data = await user_collection.find_one({'id': user_id})
        
        if user_data and 'last_swaifu_claim' in user_data:
            last_claim = user_data['last_swaifu_claim']
            if not can_claim_today(last_claim):
                msg = f"<b>{sc('You have already claimed your waifu today! Come back tomorrow.')}</b>"
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
                return

        allowed_rarities = await get_allowed_rarities()
        cursor = collection.find({})
        all_chars = await cursor.to_list(length=None)

        valid_chars = []
        for c in all_chars:
            rarity_str = str(c.get('rarity', '')).strip().lower()
            if any(allowed in rarity_str for allowed in allowed_rarities):
                valid_chars.append(c)

        if not valid_chars:
            await update.message.reply_text(f"<b>{sc('No characters found with specified rarities!')}</b>", parse_mode=ParseMode.HTML)
            return

        character = random.choice(valid_chars)
        char_name = html.escape(sc(character.get('name', 'Unknown')))
        anime = html.escape(sc(character.get('anime', 'Unknown')))
        rarity_str = character.get('rarity', '🟢 Common')
        r_key = get_rarity_key(rarity_str)
        
        if r_key and r_key in RARITIES:
            _, r_display_emoji, r_name = RARITIES[r_key]
            rarity = f"{r_display_emoji} <b>{html.escape(sc(r_name))}</b>"
        else:
            rarity = html.escape(sc(rarity_str))

        img_url = character.get('img_url', '')

        await user_collection.update_one(
            {'id': user_id},
            {
                '$push': {'characters': character},
                '$set': {'last_swaifu_claim': now_utc, 'first_name': raw_first_name}
            },
            upsert=True
        )

        caption = (
            f"<b>{sc('Congratulations')} <tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji>\n{safe_first_name}! {sc('You won')}<tg-emoji emoji-id=\"6091214879379692751\">❤️‍🔥</tg-emoji></b>\n"
            f"<b>◈ {sc('Name')}: {char_name}</b>\n"
            f"<b>◈ {sc('Rarity')}: {rarity}</b>\n"
            f"<b>◈ {sc('Anime')}: {anime}</b>"
        )

        try:
            if img_url:
                sent_msg = await update.message.reply_photo(photo=img_url, caption=caption, parse_mode=ParseMode.HTML)
            else:
                sent_msg = await update.message.reply_text(caption, parse_mode=ParseMode.HTML)
            
            asyncio.create_task(silent_auto_delete(sent_msg, delay_seconds=1200))

        except Exception as img_err:
            logger.warning(f"Image send failed: {img_err}")
            sent_msg = await update.message.reply_text(caption, parse_mode=ParseMode.HTML)
            asyncio.create_task(silent_auto_delete(sent_msg, delay_seconds=1200))

        log_data = {
            sc("ᴜsᴇʀ"): f"<b><a href='tg://user?id={user_id}'>{raw_first_name}</a></b>",
            sc("ɪᴅ"): f"<code>{user_id}</code>",
            sc("ᴄʜᴀʀᴀᴄᴛᴇʀ"): f"<b>{character.get('name', 'Unknown')}</b>",
            sc("ʀᴀʀɪᴛʏ"): f"<b>{character.get('rarity', 'Common')}</b>"
        }
        asyncio.create_task(send_log(context, create_log_message(f"˹ {sc('sᴡᴀɪꜰᴜ ᴄʟᴀɪᴍᴇᴅ')} ˼ <tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji>", log_data)))

    except Exception as e:
        logger.error(f"Swaifu Error: {e}", exc_info=True)
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> {sc('An error occurred! Try again later.')}</b>", parse_mode=ParseMode.HTML)
    finally:
        active_claims.discard(user_id)


async def daily_claim_coins(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in active_claims:
        return
    active_claims.add(user_id)
    
    try:
        raw_first_name = update.effective_user.first_name or "User"
        now_utc = datetime.now(timezone.utc)
        user_data = await eco_collection.find_one({'id': user_id})
        
        if user_data and 'last_coin_claim' in user_data:
            last_claim = user_data['last_coin_claim']
            if not can_claim_today(last_claim):
                msg = f"<b>{sc('You have already claimed your daily coins!')}</b>"
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
                return

        coins_won = random.randint(1000, 10000)
        await eco_collection.update_one(
            {'id': user_id},
            {
                '$inc': {'balance': coins_won},
                '$set': {'last_coin_claim': now_utc, 'first_name': raw_first_name}
            },
            upsert=True
        )

        msg_text = (
            f"<b><tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji> {sc('Daily Reward Claimed!')} <tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji></b>\n\n"
            f"<b><tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> {sc('Your dedication pays off!')}</b>\n"
            f"<b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {sc('You just received')} {coins_won} {sc('coins!')}</b>\n\n"
            f"<b><tg-emoji emoji-id=\"5264895611517300926\">🏦</tg-emoji> {sc('These have been securely added to your vault.')}</b>\n"
            f"<b><tg-emoji emoji-id=\"5438496463044752972\">⭐️</tg-emoji> {sc('Keep coming back daily to grow your empire!')}</b>"
        )

        await update.message.reply_text(msg_text, parse_mode=ParseMode.HTML)
        
        log_data = {
            sc("ᴜsᴇʀ"): f"<b><a href='tg://user?id={user_id}'>{raw_first_name}</a></b>",
            sc("ɪᴅ"): f"<code>{user_id}</code>",
            sc("ʀᴇᴡᴀʀᴅ"): f"<b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {coins_won:,} ᴄᴏɪɴs</b>"
        }
        asyncio.create_task(send_log(context, create_log_message(f"˹ {sc('ᴅᴀɪʟʏ ᴄʟᴀɪᴍ sᴜᴄᴄᴇssғᴜʟ')} ˼ <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>", log_data)))

    except Exception as e:
        logger.error(f"Claim Error: {e}", exc_info=True)
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> {sc('An error occurred! Try again later.')}</b>", parse_mode=ParseMode.HTML)
    finally:
        active_claims.discard(user_id)


# ==========================================
# 🎮 TIC-TAC-TOE GAME HANDLERS
# ==========================================

PREMIUM_GAME = '<tg-emoji emoji-id="6311820827952162567">🎮</tg-emoji>'
PREMIUM_USER = '<tg-emoji emoji-id="6104892988712820269">👤</tg-emoji>'
PREMIUM_WAIT = '<tg-emoji emoji-id="6161365177225712754">⏳</tg-emoji>'
PREMIUM_TURN = '<tg-emoji emoji-id="6102908426059258223">👉</tg-emoji>'
PREMIUM_WIN  = '<tg-emoji emoji-id="6053140037250323814">🏆</tg-emoji>'
PREMIUM_DRAW = '<tg-emoji emoji-id="6053383162464050605">🤝</tg-emoji>'
PREMIUM_CRY  = '<tg-emoji emoji-id="5922641759518593935">😭</tg-emoji>'

PREMIUM_P1 = '<tg-emoji emoji-id="6093865707424980866">🟢</tg-emoji>' 
PREMIUM_P2 = '<tg-emoji emoji-id="6093741664474504699">🔴</tg-emoji>'

SYMBOL_P1 = '🟢'
SYMBOL_P2 = '🔴'
EMPTY = '\u200b'  # 🔥 ZERO-WIDTH SPACE: Button height/width badhega nahi, ekdum perfect chhota box banega!

def get_tic_board(game):
    if game['status'] == 'waiting':
        btn_text = sc("Join Game")
        return InlineKeyboardMarkup([[InlineKeyboardButton(f"{btn_text}", callback_data="tic_join")]])

    board = game['board']
    keyboard = []
    for i in range(0, 9, 3):
        row = []
        for j in range(3):
            val = board[i+j]
            cb_data = f"tic_move_{i+j}" if game['status'] == 'playing' else "tic_ignore"
            
            if val == SYMBOL_P1:
                row.append(InlineKeyboardButton(EMPTY, callback_data=cb_data, icon_custom_emoji_id="6093865707424980866"))
            elif val == SYMBOL_P2:
                row.append(InlineKeyboardButton(EMPTY, callback_data=cb_data, icon_custom_emoji_id="6093741664474504699"))
            else:
                row.append(InlineKeyboardButton(EMPTY, callback_data=cb_data))
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

def check_win(board):
    win_combos = [(0,1,2), (3,4,5), (6,7,8), (0,3,6), (1,4,7), (2,5,8), (0,4,8), (2,4,6)]
    for a, b, c in win_combos:
        if board[a] == board[b] == board[c] and board[a] != EMPTY:
            return board[a]
    if EMPTY not in board: return "Draw"
    return None

async def start_tic(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    safe_name = html.escape(update.effective_user.first_name or "User")

    game = {
        'player_1_id': user_id,
        'player_1_name': safe_name,
        'player_1_sym': SYMBOL_P1,
        'player_2_id': None,
        'player_2_name': None,
        'player_2_sym': SYMBOL_P2,
        'board': [EMPTY] * 9,
        'turn': user_id,
        'status': 'waiting'
    }

    text = (
        f"{PREMIUM_GAME} <b>{sc('Tic-Tac-Toe')}</b>\n\n"
        f"{PREMIUM_USER} <b>{PREMIUM_P1} : {game['player_1_name']}</b>\n\n"
        f"{PREMIUM_WAIT} <i><b>{sc('Waiting for Player 2 to join...')}</b></i>"
    )

    msg = await update.message.reply_text(text, reply_markup=get_tic_board(game), parse_mode=ParseMode.HTML)
    key = f"{update.effective_chat.id}_{msg.message_id}"
    game['key'] = key
    await tic_collection.insert_one(game)

async def tic_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    if data == "tic_ignore":
        await query.answer()
        return

    if data == "tic_play_again":
        now = datetime.now(IST)
        if user_id in play_again_cooldowns:
            time_passed = (now - play_again_cooldowns[user_id]).total_seconds()
            if time_passed < 10:
                remaining = int(10 - time_passed)
                await query.answer(sc(f"Please wait {remaining} seconds before playing again!"), show_alert=True)
                return
        
        await query.answer(sc("New game started below!")) 
        play_again_cooldowns[user_id] = now
        safe_name = html.escape(query.from_user.first_name or "User")

        game = {
            'player_1_id': user_id,
            'player_1_name': safe_name,
            'player_1_sym': SYMBOL_P1,
            'player_2_id': None,
            'player_2_name': None,
            'player_2_sym': SYMBOL_P2,
            'board': [EMPTY] * 9,
            'turn': user_id,
            'status': 'waiting'
        }

        text = (
            f"{PREMIUM_GAME} <b>{sc('Tic-Tac-Toe')}</b>\n\n"
            f"{PREMIUM_USER} <b>{PREMIUM_P1} : {game['player_1_name']}</b>\n\n"
            f"{PREMIUM_WAIT} <i><b>{sc('Waiting for Player 2 to join...')}</b></i>"
        )

        msg = await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=get_tic_board(game),
            parse_mode=ParseMode.HTML
        )
        game['key'] = f"{msg.chat_id}_{msg.message_id}"
        await tic_collection.insert_one(game)
        return

    key = f"{query.message.chat.id}_{query.message.message_id}"
    
    if key not in tic_locks:
        tic_locks[key] = asyncio.Lock()
        
    async with tic_locks[key]:
        game = await tic_collection.find_one({'key': key})
        if not game:
            await query.answer(sc("This game session has expired!"), show_alert=False)
            return

        if data == "tic_join":
            if user_id == game['player_1_id']:
                await query.answer(sc("You cannot join your own game as Player 2!"), show_alert=True)
                return
            if game['status'] != 'waiting':
                await query.answer(sc("The game has already started!"), show_alert=True)
                return

            await query.answer(sc("✅ You have joined the game!")) 
            game['player_2_id'] = user_id
            game['player_2_name'] = html.escape(query.from_user.first_name or "User")
            game['status'] = 'playing'

            text = (
                f"{PREMIUM_GAME} <b>{sc('Tic-Tac-Toe')}</b>\n\n"
                f"{PREMIUM_P1} <b>{game['player_1_name']}</b>\n"
                f"{PREMIUM_P2} <b>{game['player_2_name']}</b>\n\n"
                f"{PREMIUM_TURN} <b>{sc('Turn')}: {game['player_1_name']} ({PREMIUM_P1})</b>"
            )
            
            try:
                await query.edit_message_text(text, reply_markup=get_tic_board(game), parse_mode=ParseMode.HTML)
            except Exception: pass
            
            game_data = game.copy()
            game_data.pop('_id', None)
            asyncio.create_task(tic_collection.update_one({'key': key}, {'$set': game_data}))
            return

        if data.startswith("tic_move_"):
            if game['status'] != 'playing':
                await query.answer(sc("The game is already over!"), show_alert=True)
                return
            if user_id not in [game['player_1_id'], game['player_2_id']]:
                await query.answer(sc("You are not a player in this game!"), show_alert=True)
                return
            if user_id != game['turn']:
                await query.answer("⏳ " + sc("It is not your turn yet! Please wait."), show_alert=True)
                return

            index = int(data.split("_")[2])
            if game['board'][index] != EMPTY:
                await query.answer(sc("This box is already filled!"), show_alert=True)
                return

            await query.answer() 
            
            symbol = game['player_1_sym'] if user_id == game['player_1_id'] else game['player_2_sym']
            game['board'][index] = symbol
            winner = check_win(game['board'])
            
            if winner:
                game['status'] = 'finished'
                if winner == "Draw":
                    text = (
                        f"{PREMIUM_GAME} <b>{sc('Tic-Tac-Toe')}</b>\n\n"
                        f"{PREMIUM_P1} <b>{game['player_1_name']}</b>\n"
                        f"{PREMIUM_P2} <b>{game['player_2_name']}</b>\n\n"
                        f"{PREMIUM_DRAW} <b>{sc('Game Draw! Well played both.')}</b>"
                    )
                else:
                    if winner == game['player_1_sym']:
                        win_name, lose_name = game['player_1_name'], game['player_2_name']
                        win_sym, lose_sym = PREMIUM_P1, PREMIUM_P2
                    else:
                        win_name, lose_name = game['player_2_name'], game['player_1_name']
                        win_sym, lose_sym = PREMIUM_P2, PREMIUM_P1

                    text = (
                        f"{PREMIUM_GAME} <b>{sc('Tic-Tac-Toe')}</b>\n\n"
                        f"{win_sym} <b>{win_name}</b> {PREMIUM_WIN}\n"
                        f"{lose_sym} <b>{lose_name}</b> {PREMIUM_CRY}\n\n"
                        f"{PREMIUM_WIN} <b>{sc('Winner')}: {win_name}</b>"
                    )

                replay_markup = InlineKeyboardMarkup([[InlineKeyboardButton(f"{sc('Play Again')} ⟳", callback_data="tic_play_again")]])
                
                try:
                    await query.edit_message_text(text, reply_markup=replay_markup, parse_mode=ParseMode.HTML)
                except Exception: pass
                
                asyncio.create_task(tic_collection.delete_one({'key': key}))
                tic_locks.pop(key, None) 
                return

            if user_id == game['player_1_id']:
                game['turn'], next_turn_name, next_symbol = game['player_2_id'], game['player_2_name'], PREMIUM_P2
            else:
                game['turn'], next_turn_name, next_symbol = game['player_1_id'], game['player_1_name'], PREMIUM_P1

            text = (
                f"{PREMIUM_GAME} <b>{sc('Tic-Tac-Toe')}</b>\n\n"
                f"{PREMIUM_P1} <b>{game['player_1_name']}</b>\n"
                f"{PREMIUM_P2} <b>{game['player_2_name']}</b>\n\n"
                f"{PREMIUM_TURN} <b>{sc('Turn')}: {next_turn_name} ({next_symbol})</b>"
            )
            
            try:
                await query.edit_message_text(text, reply_markup=get_tic_board(game), parse_mode=ParseMode.HTML)
            except Exception: pass
            
            game_data = game.copy()
            game_data.pop('_id', None)
            asyncio.create_task(tic_collection.update_one({'key': key}, {'$set': game_data}))


# ==========================================
# 💣 MINES GAME HANDLERS
# ==========================================

def get_mines_multiplier(found_cash: int, mines: int, total: int = 25) -> float:
    if found_cash == 0 or found_cash > (total - mines): return 1.00
    total_combs = math.comb(total, found_cash)
    safe_combs = math.comb(total - mines, found_cash)
    if safe_combs == 0: return 1.00
    return round(max(1.0, (total_combs / safe_combs) * 0.95), 2)

def get_mines_keyboard(game: dict, show_all: bool = False):
    keyboard = []
    board = game['board']
    revealed = game['revealed']
    
    # Generate 5x5 grid with premium emojis exactly as your original code had
    for i in range(0, 25, 5):
        row = []
        for j in range(5):
            idx = i + j
            cb_data = f"mines_click_{idx}" if game['status'] == 'playing' and not revealed[idx] else "mines_ignore"
            
            if show_all or revealed[idx]:
                if board[idx] == 'mine':
                    row.append(InlineKeyboardButton("\u200b", callback_data=cb_data, icon_custom_emoji_id="5469654973308476699"))
                else:
                    row.append(InlineKeyboardButton("\u200b", callback_data=cb_data, icon_custom_emoji_id="5472030678633684592"))
            else:
                row.append(InlineKeyboardButton("\u200b", callback_data=cb_data))
        keyboard.append(row)
    
    if game['status'] == 'playing' and game['found'] > 0:
        mult = get_mines_multiplier(game['found'], mines=game['mines_count'])
        win_amount = int(game['bet'] * mult)
        btn_text = f"{sc('Cash Out')} ({mult}x | {win_amount})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data="mines_cashout", icon_custom_emoji_id="5472030678633684592")])
        
    return InlineKeyboardMarkup(keyboard)

async def start_mines(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not context.args or not context.args[0].isdigit():
        msg = (
            f"<b><tg-emoji emoji-id=\"5258500400918587241\">✍️</tg-emoji> {sc('Usage')}</b>\n"
            f"<code>/mines &lt;bet&gt; [mines(optional)]</code>\n"
            f"<i><b>{sc('Example')}: /mines 20 3</b></i>"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        return
        
    bet = int(context.args[0])
    if bet < 10 or bet > 20000:
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> {sc('Bet amount must be between 10 and 20,000 coins!')}</b>", parse_mode=ParseMode.HTML)
        return

    mines_count = 5
    if len(context.args) > 1 and context.args[1].isdigit():
        mines_count = int(context.args[1])
        if mines_count < 3 or mines_count > 10:
            await update.message.reply_text(f"<b><tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> {sc('Mines count must be between 3 and 10!')}</b>", parse_mode=ParseMode.HTML)
            return

    eco_user = await eco_collection.find_one_and_update(
        {'id': user_id, 'balance': {'$gte': bet}},
        {'$inc': {'balance': -bet}}
    )
    if not eco_user:
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> {sc('You do not have enough coins!')}</b>", parse_mode=ParseMode.HTML)
        return

    board = ['mine'] * mines_count + ['safe'] * (25 - mines_count)
    random.shuffle(board)

    game = {
        'user_id': user_id,
        'user_name': html.escape(update.effective_user.first_name or "User"),
        'bet': bet,
        'board': board,
        'revealed': [False] * 25,
        'status': 'playing',
        'found': 0,
        'mines_count': mines_count
    }

    # 🔥 EXACT ORIGINAL TEXT with Blockquote added, and Invisible Space Padding to fix "patla" UI issue
    text = (
        f"<b><tg-emoji emoji-id=\"6091632796877463207\">🧩</tg-emoji> {sc('Mines Game Active!')}</b>\n"
        f"<blockquote><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>{sc('Bet')}:</b> {bet}\n"
        f"<tg-emoji emoji-id=\"5469654973308476699\">💣</tg-emoji> <b>{sc('Mines')}:</b> {mines_count}\n"
        f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>{sc('Found')}:</b> 0\n"
        f"<tg-emoji emoji-id=\"6091566211999474713\">📈</tg-emoji> <b>{sc('Multiplier')}:</b> 1.00x\n\n"
        f"<b>{sc('Potential Winnings')}:</b> <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {bet}</blockquote>\n"
        f"{'\u3164' * 25}"
    )

    photo_url = "https://files.catbox.moe/ewtw4l.png"
    try:
        msg = await update.message.reply_photo(
            photo=photo_url, caption=text, reply_markup=get_mines_keyboard(game), parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Failed to send photo: {e}")
        await eco_collection.update_one({'id': user_id}, {'$inc': {'balance': bet}})
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> {sc('Error loading image. Your bet has been refunded.')}</b>", parse_mode=ParseMode.HTML)
        return

    key = f"{update.effective_chat.id}_{msg.message_id}"
    game['key'] = key
    await mines_collection.insert_one(game)

    chat_title = update.effective_chat.title if update.effective_chat.title else "Private Chat"
    
    board_grid = ""
    for i in range(0, 25, 5):
        row = board[i:i+5]
        board_grid += " ".join(["💣" if x == 'mine' else "💸" for x in row]) + "\n"
        
    log_data = {
        sc("ᴜsᴇʀ"): f"<b><a href='tg://user?id={user_id}'>{game['user_name']}</a></b>",
        sc("ɪᴅ"): f"<code>{user_id}</code>",
        sc("ᴄʜᴀᴛ"): f"<b>{html.escape(chat_title)}</b>",
        sc("ᴄʜᴀᴛ ɪᴅ"): f"<code>{update.effective_chat.id}</code>",
        sc("ʙᴇᴛ"): f"<b>{bet} ᴄᴏɪɴs</b>",
        sc("ᴍɪɴᴇs"): f"<b>{mines_count}</b>",
        sc("ʙᴏᴀʀᴅ ʟᴀʏᴏᴜᴛ"): f"\n{board_grid}"
    }
    
    asyncio.create_task(send_log(context, create_log_message(f"˹ {sc('ᴍɪɴᴇs ɢᴀᴍᴇ ʟᴀʏᴏᴜᴛ')} ˼ 💣", log_data)))


async def mines_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    if data == "mines_ignore":
        await query.answer()
        return

    key = f"{query.message.chat.id}_{query.message.message_id}"
    
    if key not in mines_locks:
        mines_locks[key] = asyncio.Lock()
        
    async with mines_locks[key]:
        # 🔥 FETCH LATEST GAME STATE FROM DB
        game = await mines_collection.find_one({'key': key})
        
        if not game:
            await query.answer() 
            return
            
        if user_id != game['user_id']:
            await query.answer(sc("You cannot play someone else's game!"), show_alert=True)
            return
        if game['status'] != 'playing':
            await query.answer(sc("This game is already over!"), show_alert=True)
            return

        if data == "mines_cashout":
            await query.answer("Cashed out! 💸", show_alert=False) 
            
            mult = get_mines_multiplier(game['found'], mines=game['mines_count'])
            win_amount = int(game['bet'] * mult)
            game['status'] = 'cashed_out'
            
            text = (
                f"<b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {sc('Cashed Out!')} <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji></b>\n"
                f"<blockquote><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>{sc('Original Bet')}:</b> {game['bet']}\n"
                f"<tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji> <b>{sc('Final Multiplier')}:</b> {mult}x\n"
                f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>{sc('Winnings')}:</b> {win_amount} {sc('coins!')}\n\n"
                f"<b>{sc('Final Board')}:</b></blockquote>\n"
                f"{'\u3164' * 25}"
            )
            
            try:
                await query.edit_message_caption(caption=text, reply_markup=get_mines_keyboard(game, show_all=True), parse_mode=ParseMode.HTML)
            except Exception: pass
            
            asyncio.create_task(eco_collection.update_one({'id': user_id}, {'$inc': {'balance': win_amount}}))
            asyncio.create_task(mines_collection.delete_one({'key': key}))
            mines_locks.pop(key, None) 
            return

        if data.startswith("mines_click_"):
            idx = int(data.split("_")[2])
            
            # 🔥 PREVENT DOUBLE CLICK GLITCH
            if game['revealed'][idx]:
                await query.answer(sc("Already clicked!"), show_alert=False)
                return

            if game['board'][idx] == 'mine':
                await query.answer("BOOM! You lost the bet. 💥", show_alert=True) 
                
                game['status'] = 'busted'
                game['revealed'][idx] = True
                
                text = (
                    f"<tg-emoji emoji-id=\"5276032951342088188\">💥</tg-emoji> <b>{sc('BOOM! You hit a mine!')} <tg-emoji emoji-id=\"5276032951342088188\">💥</tg-emoji></b>\n"
                    f"<blockquote><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>{sc('Lost Bet')}:</b> {game['bet']} {sc('coins')}\n"
                    f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>{sc('Found before boom')}:</b> {game['found']}\n\n"
                    f"<b>{sc('Final Board')}:</b></blockquote>\n"
                    f"{'\u3164' * 25}"
                )
                
                try:
                    await query.edit_message_caption(caption=text, reply_markup=get_mines_keyboard(game, show_all=True), parse_mode=ParseMode.HTML)
                except Exception: pass
                
                asyncio.create_task(mines_collection.delete_one({'key': key}))
                mines_locks.pop(key, None) 
                return
                
            else:
                await query.answer("Safe! 💸", show_alert=False) 
                
                # 🔥 FIX: UPDATE REVEALED LIST IN-PLACE AND PUSH DIRECTLY TO DB TO PERSIST STATE
                revealed_list = game['revealed']
                revealed_list[idx] = True
                
                game['found'] += 1
                mult = get_mines_multiplier(game['found'], mines=game['mines_count'])
                win_amount = int(game['bet'] * mult)
                
                # 🔥 ATOMIC UPDATE TO MONGODB SO NO STATE IS LOST ON RAPID CLICKS
                await mines_collection.update_one(
                    {'key': key}, 
                    {'$set': {'revealed': revealed_list, 'found': game['found']}}
                )
                
                if game['found'] == (25 - game['mines_count']):
                    game['status'] = 'cashed_out'
                    
                    text = (
                        f"<b><tg-emoji emoji-id=\"6091375330767938412\">🎉</tg-emoji> {sc('PERFECT GAME!')} <tg-emoji emoji-id=\"6091375330767938412\">🎉</tg-emoji></b>\n"
                        f"<blockquote><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>{sc('Original Bet')}:</b> {game['bet']}\n"
                        f"<tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji> <b>{sc('Final Multiplier')}:</b> {mult}x\n"
                        f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>{sc('Winnings')}:</b> {win_amount} {sc('coins!')}\n\n"
                        f"<b>{sc('Final Board')}:</b></blockquote>\n"
                        f"{'\u3164' * 25}"
                    )
                    
                    try:
                        await query.edit_message_caption(caption=text, reply_markup=get_mines_keyboard(game, show_all=True), parse_mode=ParseMode.HTML)
                    except Exception: pass
                        
                    asyncio.create_task(eco_collection.update_one({'id': user_id}, {'$inc': {'balance': win_amount}}))
                    asyncio.create_task(mines_collection.delete_one({'key': key}))
                    mines_locks.pop(key, None) 
                    return

                text = (
                    f"<b><tg-emoji emoji-id=\"6091632796877463207\">🧩</tg-emoji> {sc('Mines Game Active!')}</b>\n"
                    f"<blockquote><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>{sc('Bet')}:</b> {game.get('bet', 0)}\n"
                    f"<tg-emoji emoji-id=\"5469654973308476699\">💣</tg-emoji> <b>{sc('Mines')}:</b> {game['mines_count']}\n"
                    f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>{sc('Found')}:</b> {game['found']}\n"
                    f"<tg-emoji emoji-id=\"6091566211999474713\">📈</tg-emoji> <b>{sc('Multiplier')}:</b> {mult}x\n\n"
                    f"<b>{sc('Potential Winnings')}:</b> <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {win_amount}</blockquote>\n"
                    f"{'\u3164' * 25}"
                )
                
                try:
                    await query.edit_message_caption(caption=text, reply_markup=get_mines_keyboard(game), parse_mode=ParseMode.HTML)
                except Exception: pass


# ==========================================
# 👑 ADMIN RARITY TOGGLE HANDLERS
# ==========================================

async def drarity_on(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return
        
    if not context.args:
        msg = (
            f"<b><tg-emoji emoji-id=\"5258500400918587241\">✍️</tg-emoji> {sc('Usage')}</b>\n"
            f"<code>/drarity_on &lt;rarity_name&gt;</code>\n"
            f"<i><b>{sc('Example')}: /drarity_on common</b></i>"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        return
        
    target_rarity = " ".join(context.args).lower()
    current_allowed = await get_allowed_rarities()
    
    if target_rarity not in current_allowed:
        current_allowed.append(target_rarity)
        await settings_collection.update_one({'setting': 'swaifu_rarities'}, {'$set': {'allowed': current_allowed}}, upsert=True)
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji> {sc('Successfully ENABLED')} '{target_rarity}' {sc('in swaifu!')}</b>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> '{target_rarity}' {sc('is already enabled.')}</b>", parse_mode=ParseMode.HTML)

async def drarity_off(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return
        
    if not context.args:
        msg = (
            f"<b><tg-emoji emoji-id=\"5258500400918587241\">✍️</tg-emoji> {sc('Usage')}</b>\n"
            f"<code>/drarity_off &lt;rarity_name&gt;</code>\n"
            f"<i><b>{sc('Example')}: /drarity_off common</b></i>"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        return
        
    target_rarity = " ".join(context.args).lower()
    current_allowed = await get_allowed_rarities()
    
    if target_rarity in current_allowed:
        current_allowed.remove(target_rarity)
        await settings_collection.update_one({'setting': 'swaifu_rarities'}, {'$set': {'allowed': current_allowed}}, upsert=True)
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> {sc('Successfully DISABLED')} '{target_rarity}' {sc('in swaifu!')}</b>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> '{target_rarity}' {sc('is already disabled or not in the list.')}</b>", parse_mode=ParseMode.HTML)


# ==========================================
# 🛑 HANDLER REGISTRATIONS
# ==========================================
application.add_handler(CommandHandler("swaifu", swaifu, block=False))
application.add_handler(CommandHandler("claim", daily_claim_coins, block=False))

# 🎮 TIC TAC TOE HANDLERS
application.add_handler(CommandHandler(["tic", "tictactoe"], start_tic, block=False))
application.add_handler(CallbackQueryHandler(tic_callback, pattern="^tic_", block=False))

# 💣 MINES HANDLERS
application.add_handler(CommandHandler("mines", start_mines, block=False))
application.add_handler(CallbackQueryHandler(mines_callback, pattern="^mines_", block=False))

# 👑 ADMIN HANDLERS
application.add_handler(CommandHandler("drarity_on", drarity_on, block=False))
application.add_handler(CommandHandler("drarity_off", drarity_off, block=False))

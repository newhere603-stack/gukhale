import random
import html
import logging
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tweak imports according to your main file
from shivu import application, user_collection, collection

LOG_GROUP_ID = -1003893927065

# Indian Standard Time (IST -> UTC +5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def to_small_caps(text: str) -> str:
    if not text:
        return "ᴜɴᴋɴᴏᴡɴ"
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    tr = str.maketrans(normal, small)
    return str(text).translate(tr)

def get_safe_time(dt):
    if dt is None:
        return None
    if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
        return dt.astimezone(IST).replace(tzinfo=None)
    return dt

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

def can_claim_today(last_claim_dt) -> bool:
    if not last_claim_dt:
        return True
    
    now = datetime.now(IST)
    
    if last_claim_dt.tzinfo is None:
        last_claim_dt = last_claim_dt.replace(tzinfo=IST)
    else:
        last_claim_dt = last_claim_dt.astimezone(IST)
    
    today_4am = now.replace(hour=4, minute=0, second=0, microsecond=0)
    
    if now < today_4am:
        reset_threshold = today_4am - timedelta(days=1)
    else:
        reset_threshold = today_4am
        
    return last_claim_dt < reset_threshold


# ==========================================
# SWAIFU & CLAIM HANDLERS
# ==========================================

async def swaifu(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        raw_first_name = update.effective_user.first_name or "User"
        safe_first_name = html.escape(to_small_caps(raw_first_name))
        
        now = datetime.now(IST)
        user_data = await user_collection.find_one({'id': user_id})
        
        if user_data and 'last_swaifu_claim' in user_data:
            last_claim = get_safe_time(user_data['last_swaifu_claim'])
            if not can_claim_today(last_claim):
                msg = f"<b>{to_small_caps('You have already claimed your waifu today! Come back tomorrow.')}</b>"
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
                return

        allowed_rarities = [
            "celestial", "exclusive", "legendary", 
            "sweet", "special edition", "rare", "common"
        ]

        cursor = collection.find({})
        all_chars = await cursor.to_list(length=None)

        valid_chars = []
        for c in all_chars:
            rarity_str = str(c.get('rarity', '')).strip().lower()
            if any(allowed in rarity_str for allowed in allowed_rarities):
                valid_chars.append(c)

        if not valid_chars:
            await update.message.reply_text(f"<b>{to_small_caps('No characters found with specified rarities!')}</b>", parse_mode=ParseMode.HTML)
            return

        character = random.choice(valid_chars)
        
        char_name = html.escape(to_small_caps(character.get('name', 'Unknown')))
        anime = html.escape(to_small_caps(character.get('anime', 'Unknown')))
        rarity = html.escape(to_small_caps(character.get('rarity', ' MEDIUM 🔵')))
        img_url = character.get('img_url', '')

        await user_collection.update_one(
            {'id': user_id},
            {
                '$push': {'characters': character},
                '$set': {
                    'last_swaifu_claim': now,
                    'first_name': raw_first_name
                }
            },
            upsert=True
        )

        caption = (
            f"<b>{to_small_caps('Congratulations 🎉')}\n {safe_first_name}! {to_small_caps('You won')}🔥</b>\n"
            f"<b>◈ {to_small_caps('Name')}: {char_name}</b>\n"
            f"<b>◈ {to_small_caps('Rarity')}: {rarity}</b>\n"
            f"<b>◈ {to_small_caps('Anime')}: {anime}</b>"
        )

        try:
            if img_url:
                await update.message.reply_photo(photo=img_url, caption=caption, parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text(caption, parse_mode=ParseMode.HTML)
        except Exception as img_err:
            logger.warning(f"Image send failed, falling back to text: {img_err}")
            await update.message.reply_text(caption, parse_mode=ParseMode.HTML)

        log_data = {
            "ᴜsᴇʀ": f"<b><a href='tg://user?id={user_id}'>{raw_first_name}</a></b>",
            "ɪᴅ": f"<code>{user_id}</code>",
            "ᴄʜᴀʀᴀᴄᴛᴇʀ": f"<b>{character.get('name', 'Unknown')}</b>",
            "ʀᴀʀɪᴛʏ": f"<b>{character.get('rarity', 'Common')}</b>"
        }
        await send_log(context, create_log_message("˹ sᴡᴀɪꜰᴜ ᴄʟᴀɪᴍᴇᴅ ˼ 🌸", log_data))

    except Exception as e:
        logger.error(f"Swaifu Error: {e}", exc_info=True)
        await update.message.reply_text(f"<b>⚠️ {to_small_caps('An error occurred! Try again later.')}</b>", parse_mode=ParseMode.HTML)


async def daily_claim_coins(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        raw_first_name = update.effective_user.first_name or "User"
        now = datetime.now(IST)

        user_data = await user_collection.find_one({'id': user_id})
        
        if user_data and 'last_coin_claim' in user_data:
            last_claim = get_safe_time(user_data['last_coin_claim'])
            if not can_claim_today(last_claim):
                msg = f"<b>{to_small_caps('You have already claimed your daily coins!')}</b>"
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
                return

        coins_won = random.randint(1000, 10000)

        await user_collection.update_one(
            {'id': user_id},
            {
                '$inc': {'balance': coins_won},
                '$set': {
                    'last_coin_claim': now,
                    'first_name': raw_first_name
                }
            },
            upsert=True
        )

        msg_text = (
            f"<b>🎉 {to_small_caps('Daily Reward Claimed!')} 🎉</b>\n\n"
            f"<b>✨ {to_small_caps('Your dedication pays off!')}</b>\n"
            f"<b>💸 {to_small_caps('You just received')} {coins_won} {to_small_caps('coins!')}</b>\n\n"
            f"<b>🏦 {to_small_caps('These have been securely added to your vault.')}</b>\n"
            f"<b>🌟 {to_small_caps('Keep coming back daily to grow your empire!')}</b>"
        )

        await update.message.reply_text(msg_text, parse_mode=ParseMode.HTML)
        
        log_data = {
            "ᴜsᴇʀ": f"<b><a href='tg://user?id={user_id}'>{raw_first_name}</a></b>",
            "ɪᴅ": f"<code>{user_id}</code>",
            "ʀᴇᴡᴀʀᴅ": f"<b>💸 {coins_won:,} ᴄᴏɪɴs</b>"
        }
        await send_log(context, create_log_message("˹ ᴅᴀɪʟʏ ᴄʟᴀɪᴍ sᴜᴄᴄᴇssғᴜʟ ˼ 💸", log_data))

    except Exception as e:
        logger.error(f"Claim Error: {e}", exc_info=True)
        await update.message.reply_text(f"<b>⚠️ {to_small_caps('An error occurred! Try again later.')}</b>", parse_mode=ParseMode.HTML)


# ==========================================
# TIC-TAC-TOE GAME HANDLERS
# ==========================================

active_tic_games = {}

# Custom Premium Emoji Tags
PREMIUM_GAME = '<tg-emoji emoji-id="6311820827952162567">🎮</tg-emoji>'
PREMIUM_USER = '<tg-emoji emoji-id="6104892988712820269">👤</tg-emoji>'
PREMIUM_WAIT = '<tg-emoji emoji-id="6161365177225712754">⏳</tg-emoji>'
PREMIUM_O    = '<tg-emoji emoji-id="6093741664474504699">🔴</tg-emoji>'
PREMIUM_X    = '<tg-emoji emoji-id="5465665476971471368">❌</tg-emoji>'
PREMIUM_TURN = '<tg-emoji emoji-id="6102908426059258223">👉</tg-emoji>'
PREMIUM_WIN  = '<tg-emoji emoji-id="6053140037250323814">🏆</tg-emoji>'
PREMIUM_DRAW = '<tg-emoji emoji-id="6053383162464050605">🤝</tg-emoji>'
PREMIUM_CRY  = '<tg-emoji emoji-id="5922641759518593935">😭</tg-emoji>'

def get_tic_board(game):
    if game['status'] == 'waiting':
        btn_text = to_small_caps("Join Game")
        return InlineKeyboardMarkup([[InlineKeyboardButton(f"🎮 {btn_text}", callback_data="tic_join")]])

    board = game['board']
    keyboard = []
    for i in range(0, 9, 3):
        row = []
        for j in range(3):
            val = board[i+j]
            text = val if val != " " else "⬜️"
            cb_data = f"tic_move_{i+j}" if game['status'] == 'playing' else "tic_ignore"
            row.append(InlineKeyboardButton(text, callback_data=cb_data))
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

def check_win(board):
    win_combos = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8), 
        (0, 3, 6), (1, 4, 7), (2, 5, 8), 
        (0, 4, 8), (2, 4, 6)             
    ]
    for a, b, c in win_combos:
        if board[a] == board[b] == board[c] and board[a] != " ":
            return board[a]
    if " " not in board:
        return "Draw"
    return None

async def start_tic(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    # Note: Using direct name, removing small caps to fix font issue
    safe_name = html.escape(update.effective_user.first_name or "User")

    game = {
        'player_1_id': user_id,
        'player_1_name': safe_name,
        'player_1_sym': '🔴',
        'player_1_tg_sym': PREMIUM_O,
        
        'player_2_id': None,
        'player_2_name': None,
        'player_2_sym': '❌',
        'player_2_tg_sym': PREMIUM_X,
        
        'board': [" "] * 9,
        'turn': user_id,
        'status': 'waiting'
    }

    text = (
        f"{PREMIUM_GAME} <b>{to_small_caps('Tic-Tac-Toe Game Started!')}</b>\n\n"
        f"{PREMIUM_USER} <b>{to_small_caps('Player 1')} ({PREMIUM_O}): {game['player_1_name']}</b>\n"
        f"{PREMIUM_WAIT} <i><b>{to_small_caps('Waiting for Player 2 to join...')}</b></i>"
    )

    msg = await update.message.reply_text(text, reply_markup=get_tic_board(game), parse_mode=ParseMode.HTML)
    key = f"{update.effective_chat.id}_{msg.message_id}"
    active_tic_games[key] = game


async def tic_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    
    if query.data == "tic_ignore":
        await query.answer()
        return

    # Handle Play Again Action (Fresh Game in New Message)
    if query.data == "tic_play_again":
        safe_name = html.escape(query.from_user.first_name or "User")

        game = {
            'player_1_id': user_id,
            'player_1_name': safe_name,
            'player_1_sym': '🔴',
            'player_1_tg_sym': PREMIUM_O,
            'player_2_id': None,
            'player_2_name': None,
            'player_2_sym': '❌',
            'player_2_tg_sym': PREMIUM_X,
            'board': [" "] * 9,
            'turn': user_id,
            'status': 'waiting'
        }

        text = (
            f"{PREMIUM_GAME} <b>{to_small_caps('Tic-Tac-Toe Game Started!')}</b>\n\n"
            f"{PREMIUM_USER} <b>{to_small_caps('Player 1')} ({PREMIUM_O}): {game['player_1_name']}</b>\n"
            f"{PREMIUM_WAIT} <i><b>{to_small_caps('Waiting for Player 2 to join...')}</b></i>"
        )

        msg = await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=get_tic_board(game),
            parse_mode=ParseMode.HTML
        )
        
        new_key = f"{msg.chat_id}_{msg.message_id}"
        active_tic_games[new_key] = game
        await query.answer(to_small_caps("New game started below!"))
        return

    key = f"{query.message.chat.id}_{query.message.message_id}"

    if key not in active_tic_games:
        await query.answer(to_small_caps("This game session has expired!"), show_alert=True)
        return

    game = active_tic_games[key]

    # Handle join
    if query.data == "tic_join":
        if user_id == game['player_1_id']:
            await query.answer(to_small_caps("You cannot join your own game as Player 2!"), show_alert=True)
            return
        if game['status'] != 'waiting':
            await query.answer(to_small_caps("The game has already started!"), show_alert=True)
            return

        game['player_2_id'] = user_id
        game['player_2_name'] = html.escape(query.from_user.first_name or "User")
        game['status'] = 'playing'

        text = (
            f"{PREMIUM_GAME} <b>{to_small_caps('Tic-Tac-Toe')}</b>\n\n"
            f"{PREMIUM_O} <b>{game['player_1_name']}</b>\n"
            f"{PREMIUM_X} <b>{game['player_2_name']}</b>\n\n"
            f"{PREMIUM_TURN} <b>{to_small_caps('Turn')}: {game['player_1_name']} ({PREMIUM_O})</b>"
        )
        await query.message.edit_text(text, reply_markup=get_tic_board(game), parse_mode=ParseMode.HTML)
        await query.answer(to_small_caps("✅ You have joined the game!"))
        return

    # Handle moves
    if query.data.startswith("tic_move_"):
        if game['status'] != 'playing':
            await query.answer(to_small_caps("The game is already over!"), show_alert=True)
            return

        if user_id not in [game['player_1_id'], game['player_2_id']]:
            await query.answer(to_small_caps("You are not a player in this game!"), show_alert=True)
            return

        if user_id != game['turn']:
            await query.answer(to_small_caps("⏳ It is not your turn yet! Please wait."), show_alert=True)
            return

        index = int(query.data.split("_")[2])
        
        if game['board'][index] != " ":
            await query.answer(to_small_caps("This box is already filled!"), show_alert=True)
            return

        # Mark the move with the correct standard emoji for the array
        symbol = game['player_1_sym'] if user_id == game['player_1_id'] else game['player_2_sym']
        game['board'][index] = symbol

        winner = check_win(game['board'])
        
        if winner:
            game['status'] = 'finished'
            
            if winner == "Draw":
                text = (
                    f"{PREMIUM_GAME} <b>{to_small_caps('Tic-Tac-Toe')}</b>\n\n"
                    f"{PREMIUM_O} <b>{game['player_1_name']}</b>\n"
                    f"{PREMIUM_X} <b>{game['player_2_name']}</b>\n\n"
                    f"{PREMIUM_DRAW} <b>{to_small_caps('Game Draw! Well played both.')}</b>"
                )
            else:
                # Find out who won and lost for displaying custom emojis
                if winner == game['player_1_sym']:
                    win_name = game['player_1_name']
                    lose_name = game['player_2_name']
                    win_sym = PREMIUM_O
                    lose_sym = PREMIUM_X
                else:
                    win_name = game['player_2_name']
                    lose_name = game['player_1_name']
                    win_sym = PREMIUM_X
                    lose_sym = PREMIUM_O

                text = (
                    f"{PREMIUM_GAME} <b>{to_small_caps('Tic-Tac-Toe')}</b>\n\n"
                    f"{win_sym} <b>{win_name}</b> {PREMIUM_WIN}\n"
                    f"{lose_sym} <b>{lose_name}</b> {PREMIUM_CRY}\n\n"
                    f"{PREMIUM_WIN} <b>{to_small_caps('Winner')}: {win_name}</b>"
                )

            # Replaces the grid with a single Play Again button
            replay_markup = InlineKeyboardMarkup([[InlineKeyboardButton(f"{to_small_caps('Play Again')} ⟳", callback_data="tic_play_again")]])
            
            await query.message.edit_text(text, reply_markup=replay_markup, parse_mode=ParseMode.HTML)
            del active_tic_games[key]
            await query.answer(to_small_caps("Game Over!"))
            return

        # Switch Turn Logic
        if user_id == game['player_1_id']:
            game['turn'] = game['player_2_id']
            next_turn_name = game['player_2_name']
            next_symbol = PREMIUM_X
        else:
            game['turn'] = game['player_1_id']
            next_turn_name = game['player_1_name']
            next_symbol = PREMIUM_O

        text = (
            f"{PREMIUM_GAME} <b>{to_small_caps('Tic-Tac-Toe')}</b>\n\n"
            f"{PREMIUM_O} <b>{game['player_1_name']}</b>\n"
            f"{PREMIUM_X} <b>{game['player_2_name']}</b>\n\n"
            f"{PREMIUM_TURN} <b>{to_small_caps('Turn')}: {next_turn_name} ({next_symbol})</b>"
        )
        await query.message.edit_text(text, reply_markup=get_tic_board(game), parse_mode=ParseMode.HTML)
        await query.answer()

# ==========================================
# HANDLER REGISTRATION
# ==========================================

application.add_handler(CommandHandler("swaifu", swaifu))
application.add_handler(CommandHandler("claim", daily_claim_coins))
application.add_handler(CommandHandler("tic", start_tic))
application.add_handler(CallbackQueryHandler(tic_callback, pattern="^tic_"))

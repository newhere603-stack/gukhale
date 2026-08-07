import random
import html
import logging
import math
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
            f"<b>{to_small_caps('Congratulations')} <tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji>\n{safe_first_name}! {to_small_caps('You won')}<tg-emoji emoji-id=\"6091214879379692751\">❤️‍🔥</tg-emoji></b>\n"
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
        await send_log(context, create_log_message("˹ sᴡᴀɪꜰᴜ ᴄʟᴀɪᴍᴇᴅ ˼ <tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji>", log_data))

    except Exception as e:
        logger.error(f"Swaifu Error: {e}", exc_info=True)
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> {to_small_caps('An error occurred! Try again later.')}</b>", parse_mode=ParseMode.HTML)


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
            f"<b><tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji> {to_small_caps('Daily Reward Claimed!')} <tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji></b>\n\n"
            f"<b><tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> {to_small_caps('Your dedication pays off!')}</b>\n"
            f"<b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {to_small_caps('You just received')} {coins_won} {to_small_caps('coins!')}</b>\n\n"
            f"<b><tg-emoji emoji-id=\"5264895611517300926\">🏦</tg-emoji> {to_small_caps('These have been securely added to your vault.')}</b>\n"
            f"<b><tg-emoji emoji-id=\"5438496463044752972\">⭐️</tg-emoji> {to_small_caps('Keep coming back daily to grow your empire!')}</b>"
        )

        await update.message.reply_text(msg_text, parse_mode=ParseMode.HTML)
        
        log_data = {
            "ᴜsᴇʀ": f"<b><a href='tg://user?id={user_id}'>{raw_first_name}</a></b>",
            "ɪᴅ": f"<code>{user_id}</code>",
            "ʀᴇᴡᴀʀᴅ": f"<b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {coins_won:,} ᴄᴏɪɴs</b>"
        }
        await send_log(context, create_log_message("˹ ᴅᴀɪʟʏ ᴄʟᴀɪᴍ sᴜᴄᴄᴇssғᴜʟ ˼ <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>", log_data))

    except Exception as e:
        logger.error(f"Claim Error: {e}", exc_info=True)
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> {to_small_caps('An error occurred! Try again later.')}</b>", parse_mode=ParseMode.HTML)


# ==========================================
# TIC-TAC-TOE GAME HANDLERS
# ==========================================

active_tic_games = {}
play_again_cooldowns = {} 

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
        return InlineKeyboardMarkup([[InlineKeyboardButton(f"{btn_text}", callback_data="tic_join")]])

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
        f"{PREMIUM_USER} <b>Player 1 ({PREMIUM_O}): {game['player_1_name']}</b>\n\n"
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

    if query.data == "tic_play_again":
        now = datetime.now(IST)
        
        if user_id in play_again_cooldowns:
            time_passed = (now - play_again_cooldowns[user_id]).total_seconds()
            if time_passed < 10:
                remaining = int(10 - time_passed)
                await query.answer(to_small_caps(f"Please wait {remaining} seconds before playing again!"), show_alert=True)
                return
        
        play_again_cooldowns[user_id] = now
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
            f"{PREMIUM_USER} <b>Player 1 ({PREMIUM_O}): {game['player_1_name']}</b>\n\n"
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
            f"{PREMIUM_TURN} <b>Turn: {game['player_1_name']} ({PREMIUM_O})</b>"
        )
        await query.message.edit_text(text, reply_markup=get_tic_board(game), parse_mode=ParseMode.HTML)
        await query.answer(to_small_caps("✅ You have joined the game!"))
        return

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

            replay_markup = InlineKeyboardMarkup([[InlineKeyboardButton(f"{to_small_caps('Play Again')} ⟳", callback_data="tic_play_again")]])
            
            await query.message.edit_text(text, reply_markup=replay_markup, parse_mode=ParseMode.HTML)
            del active_tic_games[key]
            await query.answer(to_small_caps("Game Over!"))
            return

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
            f"{PREMIUM_TURN} <b>Turn: {next_turn_name} ({next_symbol})</b>"
        )
        await query.message.edit_text(text, reply_markup=get_tic_board(game), parse_mode=ParseMode.HTML)
        await query.answer()

# ==========================================
# MINES GAME HANDLERS
# ==========================================

active_mines_games = {}

def get_mines_multiplier(found_cash: int, mines=5, total=25) -> float:
    """Calculate dynamic multiplier based on cash tiles found."""
    if found_cash == 0:
        return 1.00
    
    total_combs = math.comb(total, found_cash)
    safe_combs = math.comb(total - mines, found_cash)
    odds = total_combs / safe_combs
    
    multiplier = odds * 0.95
    return round(max(1.0, multiplier), 2)

def get_mines_keyboard(game: dict, show_all: bool = False):
    keyboard = []
    board = game['board']
    revealed = game['revealed']
    
    for i in range(0, 25, 5):
        row = []
        for j in range(5):
            idx = i + j
            if show_all or revealed[idx]:
                if board[idx] == 'mine':
                    text = "💣"
                else:
                    text = "💸"
            else:
                text = "ㅤㅤ" 
            
            cb_data = f"mines_click_{idx}" if game['status'] == 'playing' and not revealed[idx] else "mines_ignore"
            row.append(InlineKeyboardButton(text, callback_data=cb_data))
        keyboard.append(row)
    
    if game['status'] == 'playing' and game['found'] > 0:
        mult = get_mines_multiplier(game['found'])
        win_amount = int(game['bet'] * mult)
        btn_text = f"{to_small_caps('Cash Out')} ({mult}x | 💸 {win_amount})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data="mines_cashout")])
        
    return InlineKeyboardMarkup(keyboard)

async def start_mines(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not context.args or not context.args[0].isdigit():
        msg = f"<b><tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> {to_small_caps('Usage:')} /mines [bet_amount]</b>\n<i>Example: /mines 20</i>"
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        return
        
    bet = int(context.args[0])
    if bet < 10:
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> {to_small_caps('Minimum bet is 10 coins!')}</b>", parse_mode=ParseMode.HTML)
        return

    user_data = await user_collection.find_one({'id': user_id})
    balance = user_data.get('balance', 0) if user_data else 0

    if balance < bet:
        await update.message.reply_text(f"<b>{to_small_caps('You do not have enough coins!')}</b>\n<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> Balance: {balance}", parse_mode=ParseMode.HTML)
        return

    await user_collection.update_one({'id': user_id}, {'$inc': {'balance': -bet}})

    board = ['mine'] * 5 + ['safe'] * 20
    random.shuffle(board)

    game = {
        'user_id': user_id,
        'user_name': html.escape(update.effective_user.first_name or "User"),
        'bet': bet,
        'board': board,
        'revealed': [False] * 25,
        'status': 'playing',
        'found': 0,
        'mines_count': 5
    }

    text = (
        f"<b><tg-emoji emoji-id=\"6091632796877463207\">🧩</tg-emoji> {to_small_caps('Mines Game Active!')}</b>\n\n"
        f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>{to_small_caps('Bet')}:</b> {bet}\n"
        f"<tg-emoji emoji-id=\"5469654973308476699\">💣</tg-emoji> <b>{to_small_caps('Mines')}:</b> 5\n"
        f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>{to_small_caps('Found')}:</b> 0\n"
        f"<tg-emoji emoji-id=\"6091566211999474713\">📈</tg-emoji> <b>{to_small_caps('Multiplier')}:</b> 1.00x\n\n"
        f"<b>{to_small_caps('Potential Winnings')}:</b> <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {bet}"
    )

    # GIF aur text ek hi message mein caption ke taur par send honge
    msg = await update.message.reply_animation(
        animation="https://files.catbox.moe/81en6g.mp4",
        caption=text,
        reply_markup=get_mines_keyboard(game),
        parse_mode=ParseMode.HTML
    )
    key = f"{update.effective_chat.id}_{msg.message_id}"
    active_mines_games[key] = game

async def mines_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    if data == "mines_ignore":
        await query.answer()
        return

    key = f"{query.message.chat.id}_{query.message.message_id}"
    
    if key not in active_mines_games:
        await query.answer(to_small_caps("This game session has expired!"), show_alert=True)
        return
        
    game = active_mines_games[key]
    
    if user_id != game['user_id']:
        await query.answer(to_small_caps("You cannot play someone else's game!"), show_alert=True)
        return
        
    if game['status'] != 'playing':
        await query.answer(to_small_caps("This game is already over!"), show_alert=True)
        return

    if data == "mines_cashout":
        mult = get_mines_multiplier(game['found'])
        win_amount = int(game['bet'] * mult)
        
        await user_collection.update_one({'id': user_id}, {'$inc': {'balance': win_amount}})
        game['status'] = 'cashed_out'
        
        text = (
            f"<b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {to_small_caps('Cashed Out!')} <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji></b>\n\n"
            f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>{to_small_caps('Original Bet')}:</b> {game['bet']}\n"
            f"<tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji> <b>{to_small_caps('Final Multiplier')}:</b> {mult}x\n"
            f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>{to_small_caps('Winnings')}:</b> {win_amount} coins!\n\n"
            f"<b>{to_small_caps('Final Board')}:</b>"
        )
        
        await query.message.edit_caption(caption=text, reply_markup=get_mines_keyboard(game, show_all=True), parse_mode=ParseMode.HTML)
        del active_mines_games[key]
        await query.answer(f"Cashed out {win_amount} coins! 💸")
        return

    if data.startswith("mines_click_"):
        idx = int(data.split("_")[2])
        
        if game['board'][idx] == 'mine':
            game['status'] = 'busted'
            game['revealed'][idx] = True
            
            text = (
                f"<b><tg-emoji emoji-id=\"5276032951342088188\">💥</tg-emoji> {to_small_caps('BOOM! You hit a mine!')} <tg-emoji emoji-id=\"5276032951342088188\">💥</tg-emoji></b>\n\n"
                f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>{to_small_caps('Lost Bet')}:</b> {game['bet']} coins\n"
                f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>{to_small_caps('Found before boom')}:</b> {game['found']}\n\n"
                f"<b>{to_small_caps('Final Board')}:</b>"
            )
            await query.message.edit_caption(caption=text, reply_markup=get_mines_keyboard(game, show_all=True), parse_mode=ParseMode.HTML)
            del active_mines_games[key]
            await query.answer("BOOM! You lost the bet. 💥")
            return
            
        else:
            game['revealed'][idx] = True
            game['found'] += 1
            mult = get_mines_multiplier(game['found'])
            win_amount = int(game['bet'] * mult)
            
            if game['found'] == 20:
                await user_collection.update_one({'id': user_id}, {'$inc': {'balance': win_amount}})
                game['status'] = 'cashed_out'
                text = (
                    f"<b><tg-emoji emoji-id=\"6091375330767938412\">🎉</tg-emoji> {to_small_caps('PERFECT GAME!')} <tg-emoji emoji-id=\"6091375330767938412\">🎉</tg-emoji></b>\n\n"
                    f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>{to_small_caps('Original Bet')}:</b> {game['bet']}\n"
                    f"<tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji> <b>{to_small_caps('Final Multiplier')}:</b> {mult}x\n"
                    f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>{to_small_caps('Winnings')}:</b> {win_amount} coins!\n\n"
                    f"<b>{to_small_caps('Final Board')}:</b>"
                )
                await query.message.edit_caption(caption=text, reply_markup=get_mines_keyboard(game, show_all=True), parse_mode=ParseMode.HTML)
                del active_mines_games[key]
                await query.answer("Incredible! You found all the money! 💸")
                return

            text = (
                f"<b><tg-emoji emoji-id=\"6091632796877463207\">🧩</tg-emoji> {to_small_caps('Mines Game Active!')}</b>\n\n"
                f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>{to_small_caps('Bet')}:</b> {game['bet']}\n"
                f"<tg-emoji emoji-id=\"5469654973308476699\">💣</tg-emoji> <b>{to_small_caps('Mines')}:</b> 5\n"
                f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> <b>{to_small_caps('Found')}:</b> {game['found']}\n"
                f"<tg-emoji emoji-id=\"6091566211999474713\">📈</tg-emoji> <b>{to_small_caps('Multiplier')}:</b> {mult}x\n\n"
                f"<b>{to_small_caps('Potential Winnings')}:</b> <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {win_amount}"
            )
            await query.message.edit_caption(caption=text, reply_markup=get_mines_keyboard(game), parse_mode=ParseMode.HTML)
            await query.answer("Safe! 💸")

# ==========================================
# HANDLER REGISTRATION
# ==========================================

application.add_handler(CommandHandler("swaifu", swaifu))
application.add_handler(CommandHandler("claim", daily_claim_coins))
application.add_handler(CommandHandler("tic", start_tic))
application.add_handler(CallbackQueryHandler(tic_callback, pattern="^tic_"))
application.add_handler(CommandHandler("mines", start_mines))
application.add_handler(CallbackQueryHandler(mines_callback, pattern="^mines_"))

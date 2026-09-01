import math
import asyncio
import random
import time
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, List

from pymongo import ReturnDocument
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, CallbackContext

from shivu import application
from shivu.Database.db import eco_collection as user_collection

# 🔥 SETTINGS
MAX_BET_LIMIT = 1000000

@dataclass(frozen=True)
class GameConfig:
    cooldown: int = 5
    riddle_timeout: int = 15
    # Sabhi win rates 2% kam hain (0.02 minus)
    stour_entry_fee: int = 300
    stour_success_rate: float = 0.08       
    basket_base_win_rate: float = 0.18      
    dart_bullseye_rate: float = 0.08        
    dart_hit_rate: float = 0.18             
    gamble_win_rate: float = 0.18           
    
    coinflip_multiplier: int = 2
    dice_multiplier: int = 2
    gamble_multiplier: int = 2
    basket_multiplier: int = 2
    dart_hit_multiplier: int = 2
    dart_bullseye_multiplier: int = 4


class GameType(Enum):
    COINFLIP = "sbet"
    DICE = "roll"
    GAMBLE = "gamble"
    BASKET = "basket"
    DART = "dart"
    CONTRACT = "stour"
    RIDDLE = "riddle"


@dataclass
class GameResult:
    won: bool
    amount_changed: int
    bonus_coins: int = 0
    tokens_gained: int = 0
    message: str = ""
    display_outcome: Optional[str] = None


@dataclass
class PendingRiddle:
    answer: str
    expires_at: float
    message_id: int
    chat_id: int
    question: str
    reward_coins: int = 50
    reward_tokens: int = 1


@dataclass
class GameState:
    cooldowns: Dict[int, datetime] = field(default_factory=dict)
    riddles: Dict[int, PendingRiddle] = field(default_factory=dict)
    stats: Dict[int, Dict[str, int]] = field(default_factory=dict)

    def check_cooldown(self, user_id: int) -> Optional[float]:
        if last := self.cooldowns.get(user_id):
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            if elapsed < CONFIG.cooldown:
                return CONFIG.cooldown - elapsed
        return None

    def set_cooldown(self, user_id: int):
        self.cooldowns[user_id] = datetime.now(timezone.utc)

    def record_play(self, user_id: int, game: str):
        if user_id not in self.stats:
            self.stats[user_id] = {}
        self.stats[user_id][game] = self.stats[user_id].get(game, 0) + 1


CONFIG = GameConfig()
game_state = GameState()

GAME_EMOJIS = {
    GameType.COINFLIP: '<tg-emoji emoji-id="5379600444098093058">🪙</tg-emoji>', 
    GameType.DICE: '<tg-emoji emoji-id="6055198348787324579">🎲</tg-emoji>', 
    GameType.GAMBLE: '<tg-emoji emoji-id="5235989279024373566">🎰</tg-emoji>',
    GameType.BASKET: '<tg-emoji emoji-id="5384088040677319401">🏀</tg-emoji>', 
    GameType.DART: '<tg-emoji emoji-id="5350460637182993292">🎯</tg-emoji>', 
    GameType.CONTRACT: '<tg-emoji emoji-id="6332514633219315005">🤝</tg-emoji>',
    GameType.RIDDLE: '<tg-emoji emoji-id="5265120027853481187">🧩</tg-emoji>'
}


# 🔥 SUPERFAST MEMORY CACHE SYSTEM
class UserDB:
    BALANCE_FIELDS = ['balance', 'coins', 'wallet', 'money', 'gold']
    FIELD_CACHE = {}

    @staticmethod
    async def get_target_field(user_id: int) -> str:
        # Cache check for instant speed
        if user_id in UserDB.FIELD_CACHE:
            return UserDB.FIELD_CACHE[user_id]
        
        # Fast direct indexed query
        user = await user_collection.find_one({'id': user_id})
        if not user:
            return 'balance'
            
        for field in UserDB.BALANCE_FIELDS:
            if field in user and user[field] is not None:
                UserDB.FIELD_CACHE[user_id] = field
                return field
                
        UserDB.FIELD_CACHE[user_id] = 'balance'
        return 'balance'


class GameUI:
    @staticmethod
    def play_again(command: str, args: str = "") -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("ᴘʟᴀʏ ᴀɢᴀɪɴ ⟳", callback_data=f"games:repeat:{command}:{args or '_'}")
        ]])

    @staticmethod
    def menu() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("ᴄᴏɪɴ ғʟɪᴘ", callback_data="games:info:sbet"),
             InlineKeyboardButton("ᴅɪᴄᴇ ʀᴏʟʟ", callback_data="games:info:roll")],
            [InlineKeyboardButton("ɢᴀᴍʙʟᴇ", callback_data="games:info:gamble"),
             InlineKeyboardButton("ʙᴀsᴋᴇᴛʙᴀʟʟ", callback_data="games:info:basket")],
            [InlineKeyboardButton("ᴅᴀʀᴛs", callback_data="games:info:dart"),
             InlineKeyboardButton("ᴄᴏɴᴛʀᴀᴄᴛ", callback_data="games:info:stour")],
            [InlineKeyboardButton("ʀɪᴅᴅʟᴇ", callback_data="games:info:riddle")]
        ])

    @staticmethod
    def format_result(result: GameResult, emoji: str) -> str:
        status = "<b><tg-emoji emoji-id=\"6100179962185129743\">✅</tg-emoji> ᴡɪɴ</b>" if result.won else "<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ʟᴏsᴇ</b>"
        msg = f"<b>{emoji} ɢᴀᴍᴇ ʀᴇsᴜʟᴛ</b>\n{status}\n"
        if result.display_outcome:
            msg += f"<b>ᴏᴜᴛᴄᴏᴍᴇ: {result.display_outcome}</b>\n"
        msg += f"<b>{result.message}</b>"
        
        if result.won:
            rewards = []
            if result.bonus_coins > 0:
                rewards.append(f"+{result.bonus_coins} ᴄᴏɪɴs")
            if result.tokens_gained > 0:
                rewards.append(f"+{result.tokens_gained} ᴛᴏᴋᴇɴ")
            
            if rewards:
                msg += f"\n<tg-emoji emoji-id=\"5199749070830197566\">🎁</tg-emoji> <b>ʙᴏɴᴜs: {' | '.join(rewards)}</b>"
                
        return msg


class GameLogic:
    @staticmethod
    def _get_random_rewards() -> tuple[int, int]:
        chance = random.random()
        if chance < 0.80:
            return random.randint(50, 150), 0
        else:
            return 0, 1

    @staticmethod
    def coinflip(guess: str, amount: int) -> GameResult:
        won = random.random() < 0.48
        outcome = guess if won else ('tails' if guess == 'heads' else 'heads')
        
        if won:
            bonus_c, bonus_t = GameLogic._get_random_rewards()
            win = amount * CONFIG.coinflip_multiplier
            return GameResult(True, win, bonus_coins=bonus_c, tokens_gained=bonus_t, message=f"ʏᴏᴜ ᴡᴏɴ {win:,} ᴄᴏɪɴs", display_outcome=outcome.upper())
        return GameResult(False, 0, message=f"ʏᴏᴜ ʟᴏsᴛ {amount:,} ᴄᴏɪɴs", display_outcome=outcome.upper())

    @staticmethod
    def dice_roll(choice: str, amount: int) -> GameResult:
        won = random.random() < 0.48
        if won:
            dice = random.choice([1, 3, 5] if choice == 'odd' else [2, 4, 6])
        else:
            dice = random.choice([2, 4, 6] if choice == 'odd' else [1, 3, 5])
            
        result = 'odd' if dice % 2 else 'even'
        res_str = 'ᴏᴅᴅ' if result == 'odd' else 'ᴇᴠᴇɴ'
        
        if won:
            bonus_c, bonus_t = GameLogic._get_random_rewards()
            win = amount * CONFIG.dice_multiplier
            return GameResult(True, win, bonus_coins=bonus_c, tokens_gained=bonus_t, message=f"ʀᴏʟʟᴇᴅ {dice} ({res_str})\nʏᴏᴜ ᴡᴏɴ {win:,} ᴄᴏɪɴs", display_outcome=f'<tg-emoji emoji-id="6055198348787324579">🎲</tg-emoji> {dice}')
        return GameResult(False, 0, message=f"ʀᴏʟʟᴇᴅ {dice} ({res_str})\nʏᴏᴜ ʟᴏsᴛ {amount:,} ᴄᴏɪɴs", display_outcome=f'<tg-emoji emoji-id="6055198348787324579">🎲</tg-emoji> {dice}')

    @staticmethod
    def gamble(pick: str, amount: int) -> GameResult:
        won = random.random() < CONFIG.gamble_win_rate
        if won:
            bonus_c, bonus_t = GameLogic._get_random_rewards()
            win = amount * CONFIG.gamble_multiplier
            display = random.choice(['L', 'R'])
            return GameResult(True, win, bonus_coins=bonus_c, tokens_gained=bonus_t, message=f"ʏᴏᴜ ᴡᴏɴ {win:,} ᴄᴏɪɴs", display_outcome="ʟᴇғᴛ" if display == 'L' else "ʀɪɢʜᴛ")
        display = 'R' if pick == 'l' else 'L'
        return GameResult(False, 0, message=f"ʏᴏᴜ ʟᴏsᴛ {amount:,} ᴄᴏɪɴs", display_outcome="ʟᴇғᴛ" if display == 'L' else "ʀɪɢʜᴛ")

    @staticmethod
    def basketball(amount: int) -> GameResult:
        win_chance = min(0.6, CONFIG.basket_base_win_rate + math.log1p(amount) / 50)
        won = random.random() < win_chance
        if won:
            bonus_c, bonus_t = GameLogic._get_random_rewards()
            win = amount * CONFIG.basket_multiplier
            return GameResult(True, win, bonus_coins=bonus_c, tokens_gained=bonus_t, message=f"ᴘᴇʀғᴇᴄᴛ sʜᴏᴛ! ʏᴏᴜ sᴄᴏʀᴇᴅ {win:,} ᴄᴏɪɴs")
        return GameResult(False, 0, message=f"ᴍɪssᴇᴅ! ʏᴏᴜ ʟᴏsᴛ {amount:,} ᴄᴏɪɴs")

    @staticmethod
    def darts(amount: int) -> GameResult:
        roll = random.random()
        if roll < CONFIG.dart_bullseye_rate:
            bonus_c, bonus_t = GameLogic._get_random_rewards()
            win = amount * CONFIG.dart_bullseye_multiplier
            return GameResult(True, win, bonus_coins=bonus_c, tokens_gained=bonus_t, message=f"ʙᴜʟʟsᴇʏᴇ! ʏᴏᴜ ᴡᴏɴ {win:,} ᴄᴏɪɴs", display_outcome='<tg-emoji emoji-id="5350460637182993292">🎯</tg-emoji> ʙᴜʟʟsᴇʏᴇ')
        elif roll < (CONFIG.dart_bullseye_rate + CONFIG.dart_hit_rate):
            bonus_c, bonus_t = GameLogic._get_random_rewards()
            win = amount * CONFIG.dart_hit_multiplier
            return GameResult(True, win, bonus_coins=bonus_c, tokens_gained=bonus_t, message=f"ɢᴏᴏᴅ ʜɪᴛ! ʏᴏᴜ ᴡᴏɴ {win:,} ᴄᴏɪɴs", display_outcome="ᴛᴀʀɢᴇᴛ ʜɪᴛ")
        return GameResult(False, 0, message=f"ᴍɪssᴇᴅ! ʏᴏᴜ ʟᴏsᴛ {amount:,} ᴄᴏɪɴs", display_outcome="ᴍɪss")

    @staticmethod
    def contract() -> GameResult:
        if random.random() < CONFIG.stour_success_rate:
            bonus_c, bonus_t = GameLogic._get_random_rewards()
            reward = random.randint(100, 600)
            return GameResult(True, reward, bonus_coins=bonus_c, tokens_gained=bonus_t, message=f"ᴄᴏɴᴛʀᴀᴄᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ! ʏᴏᴜ ᴇᴀʀɴᴇᴅ {reward:,} ᴄᴏɪɴs")
        return GameResult(False, 0, message=f"ᴄᴏɴᴛʀᴀᴄᴛ ғᴀɪʟᴇᴅ! ʏᴏᴜ ʟᴏsᴛ {CONFIG.stour_entry_fee:,} ᴄᴏɪɴs")

    @staticmethod
    def generate_riddle() -> tuple[str, str]:
        a, b = random.randint(2, 50), random.randint(1, 50)
        op = random.choice(['+', '-', '*'])
        ans = a + b if op == '+' else (a - b if op == '-' else a * b)
        return f"{a} {op} {b}", str(ans)


async def send_or_edit_response(update: Update, text: str, markup=None):
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
            return
        except Exception:
            pass
    
    msg = update.callback_query.message if update.callback_query else update.message
    return await msg.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def check_cooldown(update: Update, user_id: int) -> bool:
    if remaining := game_state.check_cooldown(user_id):
        if update.callback_query:
            await update.callback_query.answer(
                f"⏱️ ᴡᴀɪᴛ {remaining:.1f}s ʙᴇғᴏʀᴇ ᴘʟᴀʏɪɴɢ ᴀɢᴀɪɴ!", 
                show_alert=True
            )
        else:
            await send_or_edit_response(
                update, 
                f"<b><tg-emoji emoji-id=\"6307488052059053932\">🕐</tg-emoji> ᴄᴏᴏʟᴅᴏᴡɴ ᴀᴄᴛɪᴠᴇ</b>\n<b>ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ {remaining:.1f}s ʙᴇғᴏʀᴇ ᴘʟᴀʏɪɴɢ ᴀɢᴀɪɴ.</b>"
            )
        return True
    return False

def validate_bet_amount(amount: int) -> Optional[str]:
    if amount <= 0:
        return "<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ɪɴᴠᴀʟɪᴅ ᴀᴍᴏᴜɴᴛ</b>\n<b>ᴀᴍᴏᴜɴᴛ ᴍᴜsᴛ ʙᴇ ᴘᴏsɪᴛɪᴠᴇ.</b>"
    if amount > MAX_BET_LIMIT:
        return f"<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ᴍᴀx ʙᴇᴛ ʟɪᴍɪᴛ ᴇxᴄᴇᴇᴅᴇᴅ</b>\n<b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʙᴇᴛ ᴍᴏʀᴇ ᴛʜᴀɴ {MAX_BET_LIMIT:,} ᴄᴏɪɴs.</b>"
    return None

# 🔥 SUPERFAST SINGLE ATOMIC DB UPDATE
async def execute_game_atomic(update: Update, user_id: int, game_type: GameType, amount: int, result: GameResult, extra: str = ""):
    game_state.set_cooldown(user_id) 
    
    target_field = await UserDB.get_target_field(user_id)
    
    net_coins = -amount
    if result.won:
        net_coins += (result.amount_changed + result.bonus_coins)
    net_tokens = result.tokens_gained if result.won else 0
    
    query = {'id': user_id, target_field: {'$gte': amount}}
    inc_data = {target_field: net_coins}
    if net_tokens > 0:
        inc_data['tokens'] = net_tokens
        
    updated_user = await user_collection.find_one_and_update(
        query,
        {'$inc': inc_data},
        return_document=ReturnDocument.AFTER
    )
    
    if not updated_user:
        game_state.cooldowns.pop(user_id, None) 
        user = await user_collection.find_one({'id': user_id})
        
        if not user:
            await send_or_edit_response(update, "<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ᴀᴄᴄᴏᴜɴᴛ ɴᴏᴛ ғᴏᴜɴᴅ</b>\n<b>ᴘʟᴇᴀsᴇ ʀᴇɢɪsᴛᴇʀ/ɢᴜᴇss ғɪʀsᴛ!</b>")
        else:
            bal = int(user.get(target_field, 0))
            await send_or_edit_response(update, f"<b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> ɪɴsᴜғғɪᴄɪᴇɴᴛ ʙᴀʟᴀɴᴄᴇ</b>\n<b>ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴇɴᴏᴜɢʜ ᴄᴏɪɴs. (ʏᴏᴜʀ ʙᴀʟᴀɴᴄᴇ: {bal:,})</b>")
        return
        
    game_state.record_play(user_id, game_type.value)
    
    new_bal = int(updated_user.get(target_field, 0))
    new_tok = int(updated_user.get('tokens', 0))
    
    emoji = GAME_EMOJIS.get(game_type, '<tg-emoji emoji-id="6091632796877463207">🧩</tg-emoji>')
    msg = GameUI.format_result(result, emoji)
    msg += f"\n<b>ʙᴀʟᴀɴᴄᴇ: <code>{new_bal:,}</code> ᴄᴏɪɴs</b> | <b>ᴛᴏᴋᴇɴs: <code>{new_tok:,}</code></b>"
    
    await send_or_edit_response(update, msg, GameUI.play_again(game_type.value, extra))


def extract_args(update: Update, context: CallbackContext, override_args: List[str] = None) -> List[str]:
    if override_args is not None and len(override_args) > 0 and override_args != ['_']:
        return override_args
    return context.args or []


# --- GAME HANDLERS ---

async def sbet(update: Update, context: CallbackContext, override_args: List[str] = None):
    user_id = update.effective_user.id
    if await check_cooldown(update, user_id): return
    
    args = extract_args(update, context, override_args)
    try:
        amount, guess = int(args[0]), args[1].lower()
    except (IndexError, ValueError):
        await send_or_edit_response(update, "<b><tg-emoji emoji-id=\"5258500400918587241\">✍️</tg-emoji> ᴜsᴀɢᴇ</b>\n<code>/sbet &lt;amount&gt; heads|tails</code>\n<i><b>ᴇxᴀᴍᴘʟᴇ: /sbet 100 heads</b></i>")
        return
    
    guess = 'heads' if guess in ('h', 'head', 'heads') else ('tails' if guess in ('t', 'tail', 'tails') else None)
    if not guess:
        await send_or_edit_response(update, "<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ɪɴᴠᴀʟɪᴅ ᴄʜᴏɪᴄᴇ</b>\n<b>ᴍᴜsᴛ ʙᴇ 'heads' ᴏʀ 'tails'</b>")
        return
    
    if err := validate_bet_amount(amount):
        return await send_or_edit_response(update, err)
    
    result = GameLogic.coinflip(guess, amount)
    await execute_game_atomic(update, user_id, GameType.COINFLIP, amount, result, f"{amount}:{guess}")


async def roll_cmd(update: Update, context: CallbackContext, override_args: List[str] = None):
    user_id = update.effective_user.id
    if await check_cooldown(update, user_id): return
    
    args = extract_args(update, context, override_args)
    try:
        amount, choice = int(args[0]), args[1].lower()
    except (IndexError, ValueError):
        await send_or_edit_response(update, "<b><tg-emoji emoji-id=\"5258500400918587241\">✍️</tg-emoji> ᴜsᴀɢᴇ</b>\n<code>/roll &lt;amount&gt; odd|even</code>\n<i><b>ᴇxᴀᴍᴘʟᴇ: /roll 50 odd</b></i>")
        return
    
    choice = 'odd' if choice in ('o', 'odd') else ('even' if choice in ('e', 'even') else None)
    if not choice:
        await send_or_edit_response(update, "<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ɪɴᴠᴀʟɪᴅ ᴄʜᴏɪᴄᴇ</b>\n<b>ᴍᴜsᴛ ʙᴇ 'odd' ᴏʀ 'even'</b>")
        return
    
    if err := validate_bet_amount(amount):
        return await send_or_edit_response(update, err)

    result = GameLogic.dice_roll(choice, amount)
    await execute_game_atomic(update, user_id, GameType.DICE, amount, result, f"{amount}:{choice}")


async def gamble(update: Update, context: CallbackContext, override_args: List[str] = None):
    user_id = update.effective_user.id
    if await check_cooldown(update, user_id): return
    
    args = extract_args(update, context, override_args)
    try:
        amount, pick = int(args[0]), args[1].lower()
    except (IndexError, ValueError):
        await send_or_edit_response(update, "<b><tg-emoji emoji-id=\"5258500400918587241\">✍️</tg-emoji> ᴜsᴀɢᴇ</b>\n<code>/gamble &lt;amount&gt; l|r</code>\n<i><b>ᴇxᴀᴍᴘʟᴇ: /gamble 100 l</b></i>")
        return
    
    if pick not in ('l', 'r', 'left', 'right'):
        await send_or_edit_response(update, "<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ɪɴᴠᴀʟɪᴅ ᴄʜᴏɪᴄᴇ</b>\n<b>ᴍᴜsᴛ ʙᴇ 'l' ᴏʀ 'r'</b>")
        return
    
    pick = 'l' if pick.startswith('l') else 'r'
    
    if err := validate_bet_amount(amount):
        return await send_or_edit_response(update, err)

    result = GameLogic.gamble(pick, amount)
    await execute_game_atomic(update, user_id, GameType.GAMBLE, amount, result, f"{amount}:{pick}")


async def basket(update: Update, context: CallbackContext, override_args: List[str] = None):
    user_id = update.effective_user.id
    if await check_cooldown(update, user_id): return
    
    args = extract_args(update, context, override_args)
    try:
        amount = int(args[0])
    except (IndexError, ValueError):
        await send_or_edit_response(update, "<b><tg-emoji emoji-id=\"5258500400918587241\">✍️</tg-emoji> ᴜsᴀɢᴇ</b>\n<code>/basket &lt;amount&gt;</code>\n<i><b>ᴇxᴀᴍᴘʟᴇ: /basket 75</b></i>")
        return
    
    if err := validate_bet_amount(amount):
        return await send_or_edit_response(update, err)

    result = GameLogic.basketball(amount)
    await execute_game_atomic(update, user_id, GameType.BASKET, amount, result, str(amount))


async def dart(update: Update, context: CallbackContext, override_args: List[str] = None):
    user_id = update.effective_user.id
    if await check_cooldown(update, user_id): return
    
    args = extract_args(update, context, override_args)
    try:
        amount = int(args[0])
    except (IndexError, ValueError):
        await send_or_edit_response(update, "<b><tg-emoji emoji-id=\"5258500400918587241\">✍️</tg-emoji> ᴜsᴀɢᴇ</b>\n<code>/dart &lt;amount&gt;</code>\n<i><b>ᴇxᴀᴍᴘʟᴇ: /dart 50</b></i>")
        return
    
    if err := validate_bet_amount(amount):
        return await send_or_edit_response(update, err)

    result = GameLogic.darts(amount)
    await execute_game_atomic(update, user_id, GameType.DART, amount, result, str(amount))


async def stour(update: Update, context: CallbackContext, override_args: List[str] = None):
    user_id = update.effective_user.id
    if await check_cooldown(update, user_id): return
    
    if err := validate_bet_amount(CONFIG.stour_entry_fee):
        return await send_or_edit_response(update, err)

    result = GameLogic.contract()
    await execute_game_atomic(update, user_id, GameType.CONTRACT, CONFIG.stour_entry_fee, result)


async def riddle(update: Update, context: CallbackContext, override_args: List[str] = None):
    user_id = update.effective_user.id
    
    if update.effective_chat.id != -1003087506512:
        text = "<b><tg-emoji emoji-id=\"5291873529464122510\">🔒</tg-emoji> ᴛʜɪs ɢᴀᴍᴇ ᴄᴀɴ ᴏɴʟʏ ʙᴇ ᴘʟᴀʏᴇᴅ ɪɴ ᴏᴜʀ ᴏғғɪᴄɪᴀʟ ɢʀᴏᴜᴘ.</b>"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("ᴊᴏɪɴ ɢʀᴏᴜᴘ ᴛᴏ ᴘʟᴀʏ", url="https://t.me/Anime_Group_hai")]])
        return await send_or_edit_response(update, text, markup)
        
    if await check_cooldown(update, user_id): return
    
    question, answer = GameLogic.generate_riddle()
    text = (
        f"<b><tg-emoji emoji-id=\"5265120027853481187\">🧩</tg-emoji> ʀɪᴅᴅʟᴇ ᴛɪᴍᴇ</b>\n"
        f"<b>sᴏʟᴠᴇ: {question}</b>\n"
        f"<b>ᴛɪᴍᴇ: <code>{CONFIG.riddle_timeout}s</code> | ʀᴇᴡᴀʀᴅ: <code>50</code> ᴄᴏɪɴs + <code>1</code> ᴛᴏᴋᴇɴ</b>\n"
        f"<i><b>ʀᴇᴘʟʏ ᴡɪᴛʜ ᴛʜᴇ ɴᴜᴍʙᴇʀ</b></i>"
    )
    sent = await send_or_edit_response(update, text)
    msg_id = sent.message_id if sent else (update.callback_query.message.message_id if update.callback_query else 0)
    
    riddle_data = PendingRiddle(answer, time.time() + CONFIG.riddle_timeout, msg_id, update.effective_chat.id, question)
    game_state.riddles[user_id] = riddle_data
    game_state.set_cooldown(user_id)
    game_state.record_play(user_id, GameType.RIDDLE.value)
    
    async def expire():
        await asyncio.sleep(CONFIG.riddle_timeout)
        if pending := game_state.riddles.get(user_id):
            if time.time() >= pending.expires_at:
                game_state.riddles.pop(user_id, None)
                try:
                    await application.bot.send_message(pending.chat_id, f"<b><tg-emoji emoji-id=\"6307488052059053932\">🕐</tg-emoji> ᴛɪᴍᴇ's ᴜᴘ</b>\n<b>ᴀɴsᴡᴇʀ ᴡᴀs {answer}</b>", parse_mode="HTML")
                except Exception:
                    pass
    
    asyncio.create_task(expire())


async def riddle_answer(update: Update, context: CallbackContext):
    if not update.effective_user or not update.message or update.effective_chat.id != -1003087506512:
        return
    
    user_id = update.effective_user.id
    pending = game_state.riddles.get(user_id)
    if not pending: return
    
    text = (update.message.text or "").strip()
    if not text: return
    
    if time.time() > pending.expires_at:
        game_state.riddles.pop(user_id, None)
        return
    
    if text == pending.answer:
        game_state.riddles.pop(user_id, None)
        bonus_c, bonus_t = GameLogic._get_random_rewards()
        total_coins = pending.reward_coins + bonus_c
        total_tokens = pending.reward_tokens + bonus_t
        
        target_field = await UserDB.get_target_field(user_id)
        updated_user = await user_collection.find_one_and_update(
            {'id': user_id},
            {'$inc': {target_field: total_coins, 'tokens': total_tokens}},
            return_document=ReturnDocument.AFTER
        )
        
        bal = int(updated_user.get(target_field, 0)) if updated_user else 0
        tok = int(updated_user.get('tokens', 0)) if updated_user else 0
            
        rewards_str = f"<b>ᴇᴀʀɴᴇᴅ {total_coins} ᴄᴏɪɴs</b>"
        if total_tokens > 0:
            rewards_str += f" <b>& {total_tokens} ᴛᴏᴋᴇɴ!</b>"
            
        await update.message.reply_text(
            f"<b><tg-emoji emoji-id=\"6100179962185129743\">✅</tg-emoji> ᴄᴏʀʀᴇᴄᴛ</b>\n{rewards_str}\n<b>ᴛᴏᴛᴀʟ: <code>{bal:,}</code> ᴄᴏɪɴs | <code>{tok:,}</code> ᴛᴏᴋᴇɴs</b>",
            parse_mode="HTML"
        )
    elif text.isdigit() or (text.startswith('-') and text[1:].isdigit()):
        game_state.riddles.pop(user_id, None)
        await update.message.reply_text(
            f"<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ᴡʀᴏɴɢ</b>\n<b>ᴀɴsᴡᴇʀ ᴡᴀs {pending.answer}</b>",
            parse_mode="HTML"
        )


async def games_menu(update: Update, context: CallbackContext):
    text = (
        f"<b>ᴀᴠᴀɪʟᴀʙʟᴇ ɢᴀᴍᴇs <tg-emoji emoji-id=\"6091632796877463207\">🧩</tg-emoji></b>\n"
        f"<b>ᴄᴏɪɴ ғʟɪᴘ • ᴅɪᴄᴇ ʀᴏʟʟ</b>\n"
        f"<b>ɢᴀᴍʙʟᴇ • ʙᴀsᴋᴇᴛʙᴀʟʟ</b>\n"
        f"<b>ᴅᴀʀᴛs • ᴄᴏɴᴛʀᴀᴄᴛ</b>\n"
        f"<b>ʀɪᴅᴅʟᴇ</b>"
    )
    await send_or_edit_response(update, text, GameUI.menu())


async def game_stats(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user = await user_collection.find_one({'id': user_id})
    stats = game_state.stats.get(user_id, {})
    
    if not stats:
        return await send_or_edit_response(update, "<b><tg-emoji emoji-id=\"6314169895890199228\">📊</tg-emoji> ɴᴏ sᴛᴀᴛɪsᴛɪᴄs</b>\n<b>ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴘʟᴀʏᴇᴅ ᴀɴʏ ɢᴀᴍᴇs ʏᴇᴛ.</b>")

    stat_lines = [f"• {game.upper()}: {count} ᴘʟᴀʏ(s)" for game, count in stats.items()]
    stats_str = "\n".join(stat_lines)
    name = user.get('first_name', 'ᴜɴᴋɴᴏᴡɴ') if user else 'ᴜɴᴋɴᴏᴡɴ'
    
    target_field = await UserDB.get_target_field(user_id)
    bal = int(user.get(target_field, 0)) if user else 0
    tok = int(user.get('tokens', 0)) if user else 0

    text = (
        f"<b><tg-emoji emoji-id=\"6314169895890199228\">📊</tg-emoji> ɢᴀᴍᴇ sᴛᴀᴛɪsᴛɪᴄs</b>\n"
        f"<b>ᴜsᴇʀ: {name}</b>\n\n"
        f"<b>{stats_str}</b>\n\n"
        f"<b>ᴄᴜʀʀᴇɴᴛ ʙᴀʟᴀɴᴄᴇ: <code>{bal:,}</code> ᴄᴏɪɴs</b>\n"
        f"<b>ᴄᴜʀʀᴇɴᴛ ᴛᴏᴋᴇɴs: <code>{tok:,}</code></b>"
    )
    await send_or_edit_response(update, text)


# --- CALLBACK QUERY HANDLER ---

async def games_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    if not data.startswith("games:"):
        return await query.answer()

    parts = data.split(":")
    action = parts[1]

    if action == "info":
        await query.answer()
        game_cmd = parts[2]
        info_texts = {
            "sbet": "<b><tg-emoji emoji-id=\"5379600444098093058\">🪙</tg-emoji> ᴄᴏɪɴ ғʟɪᴘ</b>\nUsage: <code>/sbet &lt;amount&gt; heads|tails</code>",
            "roll": "<b><tg-emoji emoji-id=\"6055198348787324579\">🎲</tg-emoji> ᴅɪᴄᴇ ʀᴏʟʟ</b>\nUsage: <code>/roll &lt;amount&gt; odd|even</code>",
            "gamble": "<b><tg-emoji emoji-id=\"5235989279024373566\">🎰</tg-emoji> ɢᴀᴍʙʟᴇ</b>\nUsage: <code>/gamble &lt;amount&gt; l|r</code>",
            "basket": "<b><tg-emoji emoji-id=\"5384088040677319401\">🏀</tg-emoji> ʙᴀsᴋᴇᴛʙᴀʟʟ</b>\nUsage: <code>/basket &lt;amount&gt;</code>",
            "dart": "<b><tg-emoji emoji-id=\"5350460637182993292\">🎯</tg-emoji> ᴅᴀʀᴛs</b>\nUsage: <code>/dart &lt;amount&gt;</code>",
            "stour": f"<b><tg-emoji emoji-id=\"6332514633219315005\">🤝</tg-emoji> ᴄᴏɴᴛʀᴀᴄᴛ</b>\nUsage: <code>/stour</code>\nFee: {CONFIG.stour_entry_fee} coins",
            "riddle": "<b><tg-emoji emoji-id=\"5265120027853481187\">🧩</tg-emoji> ʀɪᴅᴅʟᴇ</b>\nUsage: <code>/riddle</code>"
        }
        await query.message.reply_text(info_texts.get(game_cmd, "Unknown Game"), parse_mode="HTML")

    elif action == "repeat":
        if remaining := game_state.check_cooldown(user_id):
            return await query.answer(f"⏱️ ᴡᴀɪᴛ {remaining:.1f}s ʙᴇғᴏʀᴇ ᴘʟᴀʏɪɴɢ ᴀɢᴀɪɴ!", show_alert=True)

        await query.answer()
        cmd = parts[2]
        
        parsed_args = parts[3:]
        if parsed_args == ['_']: parsed_args = []

        handlers = {
            "sbet": sbet, "roll": roll_cmd, "gamble": gamble,
            "basket": basket, "dart": dart, "stour": stour, "riddle": riddle
        }

        if handler := handlers.get(cmd):
            await handler(update, context, override_args=parsed_args)


# --- HANDLERS REGISTRATION ---
application.add_handler(CommandHandler("sbet", sbet, block=False))
application.add_handler(CommandHandler("roll", roll_cmd, block=False))
application.add_handler(CommandHandler("gamble", gamble, block=False))
application.add_handler(CommandHandler("basket", basket, block=False))
application.add_handler(CommandHandler("dart", dart, block=False))
application.add_handler(CommandHandler("stour", stour, block=False))
application.add_handler(CommandHandler("riddle", riddle, block=False))
application.add_handler(CommandHandler("games", games_menu, block=False))
application.add_handler(CommandHandler("gamestats", game_stats, block=False))

# group=1 ensures riddle answer handler gets precedence
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, riddle_answer), group=1)
application.add_handler(CallbackQueryHandler(games_callback, pattern="^games:", block=False))

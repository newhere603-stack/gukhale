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

def to_small_caps(text: str) -> str:
    small_caps_map = {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ', 
        'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 
        'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ', 
        'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
        'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ғ', 'G': 'ɢ', 
        'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ', 
        'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'ǫ', 'R': 'ʀ', 'S': 's', 'T': 'ᴛ', 'U': 'ᴜ', 
        'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x', 'Y': 'ʏ', 'Z': 'ᴢ'
    }
    return "".join(small_caps_map.get(c, c) for c in text)

@dataclass(frozen=True)
class GameConfig:
    cooldown: int = 5
    riddle_timeout: int = 15
    stour_entry_fee: int = 300
    
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

    def check_cooldown(self, user_id: int) -> Optional[float]:
        if last := self.cooldowns.get(user_id):
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            if elapsed < CONFIG.cooldown:
                return CONFIG.cooldown - elapsed
        return None

    def set_cooldown(self, user_id: int):
        self.cooldowns[user_id] = datetime.now(timezone.utc)


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


class UserDB:
    BALANCE_FIELDS = ['balance', 'coins', 'wallet', 'money', 'gold']

    @staticmethod
    async def get(user_id: int) -> Optional[dict]:
        try:
            return await user_collection.find_one({
                '$or': [
                    {'id': user_id},
                    {'id': str(user_id)},
                    {'user_id': user_id},
                    {'user_id': str(user_id)}
                ]
            })
        except Exception as e:
            print(f"Error fetching user {user_id}: {e}")
            return None

    @staticmethod
    async def get_balance_and_field(user: dict) -> tuple[int, str]:
        if not user:
            return 0, 'balance'
            
        for field in UserDB.BALANCE_FIELDS:
            if field in user and user[field] is not None:
                try:
                    return int(user[field]), field
                except (ValueError, TypeError):
                    pass
        return 0, 'balance'


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
    def is_win(amount: int) -> bool:
        roll = random.randint(1, 100)
        if amount > 10000:
            return roll <= 10
        return roll <= 50

    @staticmethod
    def _get_random_rewards() -> tuple[int, int]:
        chance = random.randint(1, 100)
        if chance <= 80:
            return random.randint(50, 150), 0
        else:
            return 0, 1

    @staticmethod
    def coinflip(guess: str, amount: int) -> GameResult:
        won = GameLogic.is_win(amount)
        outcome = guess if won else ('tails' if guess == 'heads' else 'heads')
        
        if won:
            bonus_c, bonus_t = GameLogic._get_random_rewards()
            win = amount * CONFIG.coinflip_multiplier
            return GameResult(True, win, bonus_coins=bonus_c, tokens_gained=bonus_t, message=f"ʏᴏᴜ ᴡᴏɴ {win:,} ᴄᴏɪɴs", display_outcome=outcome.upper())
        return GameResult(False, 0, message=f"ʏᴏᴜ ʟᴏsᴛ {amount:,} ᴄᴏɪɴs", display_outcome=outcome.upper())

    @staticmethod
    def dice_roll(choice: str, amount: int) -> GameResult:
        won = GameLogic.is_win(amount)
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
        won = GameLogic.is_win(amount)
        if won:
            bonus_c, bonus_t = GameLogic._get_random_rewards()
            win = amount * CONFIG.gamble_multiplier
            display = random.choice(['L', 'R'])
            return GameResult(True, win, bonus_coins=bonus_c, tokens_gained=bonus_t, message=f"ʏᴏᴜ ᴡᴏɴ {win:,} ᴄᴏɪɴs", display_outcome="ʟᴇғᴛ" if display == 'L' else "ʀɪɢʜᴛ")
        display = 'R' if pick == 'l' else 'L'
        return GameResult(False, 0, message=f"ʏᴏᴜ ʟᴏsᴛ {amount:,} ᴄᴏɪɴs", display_outcome="ʟᴇғᴛ" if display == 'L' else "ʀɪɢʜᴛ")

    @staticmethod
    def basketball(amount: int) -> GameResult:
        won = GameLogic.is_win(amount)
        if won:
            bonus_c, bonus_t = GameLogic._get_random_rewards()
            win = amount * CONFIG.basket_multiplier
            return GameResult(True, win, bonus_coins=bonus_c, tokens_gained=bonus_t, message=f"ᴘᴇʀғᴇᴄᴛ sʜᴏᴛ! ʏᴏᴜ sᴄᴏʀᴇᴅ {win:,} ᴄᴏɪɴs")
        return GameResult(False, 0, message=f"ᴍɪssᴇᴅ! ʏᴏᴜ ʟᴏsᴛ {amount:,} ᴄᴏɪɴs")

    @staticmethod
    def darts(amount: int) -> GameResult:
        roll = random.randint(1, 100)
        
        if amount > 10000:
            bullseye_chance = 3
            hit_chance = 10
        else:
            bullseye_chance = 15
            hit_chance = 50
            
        if roll <= bullseye_chance:
            bonus_c, bonus_t = GameLogic._get_random_rewards()
            win = amount * CONFIG.dart_bullseye_multiplier
            return GameResult(True, win, bonus_coins=bonus_c, tokens_gained=bonus_t, message=f"ʙᴜʟʟsᴇʏᴇ! ʏᴏᴜ ᴡᴏɴ {win:,} ᴄᴏɪɴs", display_outcome='<tg-emoji emoji-id="5350460637182993292">🎯</tg-emoji> ʙᴜʟʟsᴇʏᴇ')
        elif roll <= hit_chance:
            bonus_c, bonus_t = GameLogic._get_random_rewards()
            win = amount * CONFIG.dart_hit_multiplier
            return GameResult(True, win, bonus_coins=bonus_c, tokens_gained=bonus_t, message=f"ɢᴏᴏᴅ ʜɪᴛ! ʏᴏᴜ ᴡᴏɴ {win:,} ᴄᴏɪɴs", display_outcome="ᴛᴀʀɢᴇᴛ ʜɪᴛ")
            
        return GameResult(False, 0, message=f"ᴍɪssᴇᴅ! ʏᴏᴜ ʟᴏsᴛ {amount:,} ᴄᴏɪɴs", display_outcome="ᴍɪss")

    @staticmethod
    def contract() -> GameResult:
        won = GameLogic.is_win(CONFIG.stour_entry_fee)
        if won:
            bonus_c, bonus_t = GameLogic._get_random_rewards()
            reward = random.randint(100, 600)
            return GameResult(True, reward, bonus_coins=bonus_c, tokens_gained=bonus_t, message=f"ᴄᴏɴᴛʀᴀᴄᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ! ʏᴏᴜ ᴇᴀʀɴᴇᴅ {reward:,} ᴄᴏɪɴs")
        return GameResult(False, 0, message=f"ᴄᴏɴᴛʀᴀᴄᴛ ғᴀɪʟᴇᴅ! ʏᴏᴜ ʟᴏsᴛ {CONFIG.stour_entry_fee:,} ᴄᴏɪɴs")

    @staticmethod
    def generate_riddle() -> tuple[str, str]:
        a, b = random.randint(2, 50), random.randint(1, 50)
        op = random.choice(['+', '-', '×'])
        ans = a + b if op == '+' else (a - b if op == '-' else a * b)
        return f"{a} {op} {b}", str(ans)


async def send_or_edit_response(update: Update, context: CallbackContext, text: str, markup=None):
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
            return
        except Exception:
            pass
    
    msg = update.callback_query.message if update.callback_query else update.message
    if msg:
        return await msg.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def check_cooldown(update: Update, context: CallbackContext, user_id: int) -> bool:
    if remaining := game_state.check_cooldown(user_id):
        if update.callback_query:
            try:
                await update.callback_query.answer(
                    f"⏱️ ᴡᴀɪᴛ {remaining:.1f}s ʙᴇғᴏʀᴇ ᴘʟᴀʏɪɴɢ ᴀɢᴀɪɴ!", 
                    show_alert=True
                )
            except Exception:
                pass
        else:
            await send_or_edit_response(
                update, context,
                f"<b><tg-emoji emoji-id=\"6307488052059053932\">🕐</tg-emoji> ᴄᴏᴏʟᴅᴏᴡɴ ᴀᴄᴛɪᴠᴇ</b>\n<b>ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ {remaining:.1f}s ʙᴇғᴏʀᴇ ᴘʟᴀʏɪɴɢ ᴀɢᴀɪɴ.</b>"
            )
        return True
    return False


async def validate_amount(update: Update, context: CallbackContext, amount: int, user_id: int) -> Optional[dict]:
    if amount <= 0:
        await send_or_edit_response(update, context, "<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ɪɴᴠᴀʟɪᴅ ᴀᴍᴏᴜɴᴛ</b>\n<b>ᴀᴍᴏᴜɴᴛ ᴍᴜsᴛ ʙᴇ ᴘᴏsɪᴛɪᴠᴇ.</b>")
        return None
        
    if amount > MAX_BET_LIMIT:
        await send_or_edit_response(update, context, f"<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ᴍᴀx ʙᴇᴛ ʟɪᴍɪᴛ ᴇxᴄᴇᴇᴅᴇᴅ</b>\n<b>ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʙᴇᴛ ᴍᴏʀᴇ ᴛʜᴀɴ {MAX_BET_LIMIT:,} ᴄᴏɪɴs.</b>")
        return None
    
    user = await UserDB.get(user_id)
    if not user:
        await send_or_edit_response(update, context, "<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ᴀᴄᴄᴏᴜɴᴛ ɴᴏᴛ ғᴏᴜɴᴅ</b>\n<b>ᴘʟᴇᴀsᴇ ʀᴇɢɪsᴛᴇʀ/ɢᴜᴇss ғɪʀsᴛ!</b>")
        return None

    balance, _ = await UserDB.get_balance_and_field(user)
    if balance < amount:
        await send_or_edit_response(update, context, f"<b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> ɪɴsᴜғғɪᴄɪᴇɴᴛ ʙᴀʟᴀɴᴄᴇ</b>\n<b>ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴇɴᴏᴜɢʜ ᴄᴏɪɴs. (ʏᴏᴜʀ ʙᴀʟᴀɴᴄᴇ: {balance:,})</b>")
        return None
    return user


async def process_game(update: Update, context: CallbackContext, user: dict, game_type: GameType, amount: int, result: GameResult, extra: str = ""):
    user_id = update.effective_user.id
    
    net_coins = -amount
    if result.won:
        net_coins += (result.amount_changed + result.bonus_coins)
    net_tokens = result.tokens_gained if result.won else 0
    
    _, target_field = await UserDB.get_balance_and_field(user)
    
    query = {'_id': user['_id']}
    if net_coins < 0:
        query[target_field] = {'$gte': abs(net_coins)}

    inc_data = {target_field: net_coins}
    if net_tokens > 0:
        inc_data['tokens'] = net_tokens
    
    # Save stats to DB
    inc_data[f'game_stats.{game_type.value}'] = 1

    updated_user = await user_collection.find_one_and_update(
        query,
        {'$inc': inc_data},
        return_document=ReturnDocument.AFTER
    )

    if not updated_user:
        await send_or_edit_response(update, context, "<b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> ɪɴsᴜғғɪᴄɪᴇɴᴛ ʙᴀʟᴀɴᴄᴇ ᴏʀ ᴇʀʀᴏʀ</b>\n<b>ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.</b>")
        return
        
    game_state.set_cooldown(user_id)
    
    new_bal = int(updated_user.get(target_field, 0))
    new_tok = int(updated_user.get('tokens', 0))
    
    emoji = GAME_EMOJIS.get(game_type, '<tg-emoji emoji-id="6091632796877463207">🧩</tg-emoji>')
    msg = GameUI.format_result(result, emoji)
    msg += f"\n<b>ʙᴀʟᴀɴᴄᴇ: <code>{new_bal:,}</code> ᴄᴏɪɴs</b> | <b>ᴛᴏᴋᴇɴs: <code>{new_tok:,}</code></b>"
    
    await send_or_edit_response(update, context, msg, GameUI.play_again(game_type.value, extra))


def extract_args(update: Update, context: CallbackContext, override_args: List[str] = None) -> List[str]:
    if override_args is not None and len(override_args) > 0 and override_args != ['_']:
        return override_args
    return context.args or []


# --- GAME HANDLERS ---

async def sbet(update: Update, context: CallbackContext, override_args: List[str] = None):
    user_id = update.effective_user.id
    if await check_cooldown(update, context, user_id): return
    
    args = extract_args(update, context, override_args)
    try:
        amount, guess = int(args[0]), args[1].lower()
    except (IndexError, ValueError):
        return await send_or_edit_response(update, context, "<b><tg-emoji emoji-id=\"5258500400918587241\">✍️</tg-emoji> ᴜsᴀɢᴇ</b>\n<code>/sbet &lt;amount&gt; heads|tails</code>\n<i><b>ᴇxᴀᴍᴘʟᴇ: /sbet 100 heads</b></i>")
    
    guess = 'heads' if guess in ('h', 'head', 'heads') else ('tails' if guess in ('t', 'tail', 'tails') else None)
    if not guess:
        return await send_or_edit_response(update, context, "<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ɪɴᴠᴀʟɪᴅ ᴄʜᴏɪᴄᴇ</b>\n<b>ᴍᴜsᴛ ʙᴇ 'heads' ᴏʀ 'tails'</b>")
    
    user = await validate_amount(update, context, amount, user_id)
    if not user: return
    
    result = GameLogic.coinflip(guess, amount)
    await process_game(update, context, user, GameType.COINFLIP, amount, result, f"{amount}:{guess}")


async def roll_cmd(update: Update, context: CallbackContext, override_args: List[str] = None):
    user_id = update.effective_user.id
    if await check_cooldown(update, context, user_id): return
    
    args = extract_args(update, context, override_args)
    try:
        amount, choice = int(args[0]), args[1].lower()
    except (IndexError, ValueError):
        return await send_or_edit_response(update, context, "<b><tg-emoji emoji-id=\"5258500400918587241\">✍️</tg-emoji> ᴜsᴀɢᴇ</b>\n<code>/roll &lt;amount&gt; odd|even</code>\n<i><b>ᴇxᴀᴍᴘʟᴇ: /roll 50 odd</b></i>")
    
    choice = 'odd' if choice in ('o', 'odd') else ('even' if choice in ('e', 'even') else None)
    if not choice:
        return await send_or_edit_response(update, context, "<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ɪɴᴠᴀʟɪᴅ ᴄʜᴏɪᴄᴇ</b>\n<b>ᴍᴜsᴛ ʙᴇ 'odd' ᴏʀ 'even'</b>")
    
    user = await validate_amount(update, context, amount, user_id)
    if not user: return

    result = GameLogic.dice_roll(choice, amount)
    await process_game(update, context, user, GameType.DICE, amount, result, f"{amount}:{choice}")


async def gamble(update: Update, context: CallbackContext, override_args: List[str] = None):
    user_id = update.effective_user.id
    if await check_cooldown(update, context, user_id): return
    
    args = extract_args(update, context, override_args)
    try:
        amount, pick = int(args[0]), args[1].lower()
    except (IndexError, ValueError):
        return await send_or_edit_response(update, context, "<b><tg-emoji emoji-id=\"5258500400918587241\">✍️</tg-emoji> ᴜsᴀɢᴇ</b>\n<code>/gamble &lt;amount&gt; l|r</code>\n<i><b>ᴇxᴀᴍᴘʟᴇ: /gamble 100 l</b></i>")
    
    if pick not in ('l', 'r', 'left', 'right'):
        return await send_or_edit_response(update, context, "<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ɪɴᴠᴀʟɪᴅ ᴄʜᴏɪᴄᴇ</b>\n<b>ᴍᴜsᴛ ʙᴇ 'l' ᴏʀ 'r'</b>")
    
    pick = 'l' if pick.startswith('l') else 'r'
    
    user = await validate_amount(update, context, amount, user_id)
    if not user: return

    result = GameLogic.gamble(pick, amount)
    await process_game(update, context, user, GameType.GAMBLE, amount, result, f"{amount}:{pick}")


async def basket(update: Update, context: CallbackContext, override_args: List[str] = None):
    user_id = update.effective_user.id
    if await check_cooldown(update, context, user_id): return
    
    args = extract_args(update, context, override_args)
    try:
        amount = int(args[0])
    except (IndexError, ValueError):
        return await send_or_edit_response(update, context, "<b><tg-emoji emoji-id=\"5258500400918587241\">✍️</tg-emoji> ᴜsᴀɢᴇ</b>\n<code>/basket &lt;amount&gt;</code>\n<i><b>ᴇxᴀᴍᴘʟᴇ: /basket 75</b></i>")
    
    user = await validate_amount(update, context, amount, user_id)
    if not user: return

    result = GameLogic.basketball(amount)
    await process_game(update, context, user, GameType.BASKET, amount, result, str(amount))


async def dart(update: Update, context: CallbackContext, override_args: List[str] = None):
    user_id = update.effective_user.id
    if await check_cooldown(update, context, user_id): return
    
    args = extract_args(update, context, override_args)
    try:
        amount = int(args[0])
    except (IndexError, ValueError):
        return await send_or_edit_response(update, context, "<b><tg-emoji emoji-id=\"5258500400918587241\">✍️</tg-emoji> ᴜsᴀɢᴇ</b>\n<code>/dart &lt;amount&gt;</code>\n<i><b>ᴇxᴀᴍᴘʟᴇ: /dart 50</b></i>")
    
    user = await validate_amount(update, context, amount, user_id)
    if not user: return

    result = GameLogic.darts(amount)
    await process_game(update, context, user, GameType.DART, amount, result, str(amount))


async def stour(update: Update, context: CallbackContext, override_args: List[str] = None):
    user_id = update.effective_user.id
    if await check_cooldown(update, context, user_id): return
    
    user = await validate_amount(update, context, CONFIG.stour_entry_fee, user_id)
    if not user: return

    result = GameLogic.contract()
    await process_game(update, context, user, GameType.CONTRACT, CONFIG.stour_entry_fee, result)


async def riddle(update: Update, context: CallbackContext, override_args: List[str] = None):
    user_id = update.effective_user.id
    
    if update.effective_chat.id != -1003087506512:
        text = "<b><tg-emoji emoji-id=\"5291873529464122510\">🔒</tg-emoji> ᴛʜɪs ɢᴀᴍᴇ ᴄᴀɴ ᴏɴʟʏ ʙᴇ ᴘʟᴀʏᴇᴅ ɪɴ ᴏᴜʀ ᴏғғɪᴄɪᴀʟ ɢʀᴏᴜᴘ.</b>"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("ᴊᴏɪɴ ɢʀᴏᴜᴘ ᴛᴏ ᴘʟᴀʏ", url="https://t.me/Anime_Group_hai")]])
        return await send_or_edit_response(update, context, text, markup)
        
    if await check_cooldown(update, context, user_id): return
    
    user = await UserDB.get(user_id)
    if user:
        await user_collection.update_one({'_id': user['_id']}, {'$inc': {f'game_stats.{GameType.RIDDLE.value}': 1}})

    question, answer = GameLogic.generate_riddle()
    text = (
        f"<b><tg-emoji emoji-id=\"5265120027853481187\">🧩</tg-emoji> ʀɪᴅᴅʟᴇ ᴛɪᴍᴇ</b>\n"
        f"<b>sᴏʟᴠᴇ: {question}</b>\n"
        f"<b>ᴛɪᴍᴇ: <code>{CONFIG.riddle_timeout}s</code> | ʀᴇᴡᴀʀᴅ: <code>50</code> ᴄᴏɪɴs + <code>1</code> ᴛᴏᴋᴇɴ</b>\n"
        f"<i><b>ʀᴇᴘʟʏ ᴡɪᴛʜ ᴛʜᴇ ɴᴜᴍʙᴇʀ</b></i>"
    )
    sent = await send_or_edit_response(update, context, text)
    msg_id = sent.message_id if sent else (update.callback_query.message.message_id if update.callback_query else 0)
    
    riddle_data = PendingRiddle(answer, time.time() + CONFIG.riddle_timeout, msg_id, update.effective_chat.id, question)
    game_state.riddles[user_id] = riddle_data
    game_state.set_cooldown(user_id)
    
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
        
        user = await UserDB.get(user_id)
        if user:
            _, target_field = await UserDB.get_balance_and_field(user)
            updated_user = await user_collection.find_one_and_update(
                {'_id': user['_id']},
                {'$inc': {target_field: total_coins, 'tokens': total_tokens}},
                return_document=ReturnDocument.AFTER
            )
            bal = int(updated_user.get(target_field, 0)) if updated_user else 0
            tok = int(updated_user.get('tokens', 0)) if updated_user else 0
        else:
            bal, tok = 0, 0
            
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
    await send_or_edit_response(update, context, text, GameUI.menu())


async def game_stats(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user = await UserDB.get(user_id)
    
    if not user or 'game_stats' not in user or not user['game_stats']:
        return await send_or_edit_response(update, context, "<b><tg-emoji emoji-id=\"6314169895890199228\">📊</tg-emoji> ɴᴏ sᴛᴀᴛɪsᴛɪᴄs</b>\n<b>ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴘʟᴀʏᴇᴅ ᴀɴʏ ɢᴀᴍᴇs ʏᴇᴛ.</b>")

    stats = user['game_stats']
    stat_lines = [f"<b>{to_small_caps(f'• {game.upper()}: {count} PLAY(s)')}</b>" for game, count in stats.items()]
    stats_str = "\n".join(stat_lines)
    name = user.get('first_name', 'ᴜɴᴋɴᴏᴡɴ')
    
    bal, _ = await UserDB.get_balance_and_field(user)
    tok = user.get('tokens', 0)

    text = (
        f"<b><tg-emoji emoji-id=\"6314169895890199228\">📊</tg-emoji> ɢᴀᴍᴇ sᴛᴀᴛɪsᴛɪᴄs</b>\n"
        f"<b>ᴜsᴇʀ: {name}</b>\n\n"
        f"{stats_str}\n\n"
        f"<b>ᴄᴜʀʀᴇɴᴛ ʙᴀʟᴀɴᴄᴇ: <code>{bal:,}</code> ᴄᴏɪɴs</b>\n"
        f"<b>ᴄᴜʀʀᴇɴᴛ ᴛᴏᴋᴇɴs: <code>{tok:,}</code></b>"
    )
    await send_or_edit_response(update, context, text)


# --- CALLBACK QUERY HANDLER ---

async def games_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    if not data.startswith("games:"):
        try: await query.answer()
        except Exception: pass
        return

    parts = data.split(":")
    action = parts[1]

    if action == "info":
        try: await query.answer()
        except Exception: pass
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
        await context.bot.send_message(chat_id=update.effective_chat.id, text=info_texts.get(game_cmd, "Unknown Game"), parse_mode="HTML")

    elif action == "repeat":
        if remaining := game_state.check_cooldown(user_id):
            try: await query.answer(f"⏱️ ᴡᴀɪᴛ {remaining:.1f}s ʙᴇғᴏʀᴇ ᴘʟᴀʏɪɴɢ ᴀɢᴀɪɴ!", show_alert=True)
            except Exception: pass
            return

        try: await query.answer()
        except Exception: pass
        
        cmd = parts[2]
        
        parsed_args = parts[3:] if len(parts) > 3 and parts[3] != '_' else []

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

application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, riddle_answer, block=False), group=119)
application.add_handler(CallbackQueryHandler(games_callback, pattern="^games:", block=False))

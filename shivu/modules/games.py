import math
import asyncio
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, CallbackContext

from shivu import application, user_collection


@dataclass(frozen=True)
class GameConfig:
    cooldown: int = 5
    riddle_timeout: int = 15
    stour_entry_fee: int = 300
    stour_success_rate: float = 0.1
    basket_base_win_rate: float = 0.20
    dart_bullseye_rate: float = 0.1
    dart_hit_rate: float = 0.20
    gamble_win_rate: float = 0.20
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
    GameType.COINFLIP: "🪙", GameType.DICE: "🎲", GameType.GAMBLE: "🎰",
    GameType.BASKET: "🏀", GameType.DART: "🎯", GameType.CONTRACT: "🤝",
    GameType.RIDDLE: "🧩"
}


class UserDB:
    @staticmethod
    async def get(user_id: int) -> Optional[dict]:
        try:
            return await user_collection.find_one({'id': user_id})
        except Exception:
            return None

    @staticmethod
    async def ensure(user_id: int, first_name: str = None, username: str = None) -> dict:
        doc = await UserDB.get(user_id)
        if doc:
            updates = {}
            if username and username != doc.get('username'):
                updates['username'] = username
            if first_name and first_name != doc.get('first_name'):
                updates['first_name'] = first_name
            if updates:
                try:
                    await user_collection.update_one({'id': user_id}, {'$set': updates})
                except Exception:
                    pass
            return doc

        # Agar user existing nahi hai, tabhi $setOnInsert ke sath safe insert karein
        new_user = {
            'id': user_id,
            'first_name': first_name or 'ᴜɴᴋɴᴏᴡɴ',
            'username': username,
            'balance': 0,
            'characters': [],
            'created_at': datetime.now(timezone.utc)
        }
        try:
            await user_collection.update_one(
                {'id': user_id},
                {'$setOnInsert': new_user},
                upsert=True
            )
        except Exception:
            pass
        return await UserDB.get(user_id)

    @staticmethod
    async def change_balance(user_id: int, delta: int) -> Optional[dict]:
        try:
            # Upsert ko False rakha hai taaki existing document overwrite na ho
            await user_collection.update_one({'id': user_id}, {'$inc': {'balance': delta}})
        except Exception:
            pass
        return await UserDB.get(user_id)


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
             InlineKeyboardButton("ʙᴀsʙᴀʟʟ", callback_data="games:info:basket")],
            [InlineKeyboardButton("ᴅᴀʀᴛs", callback_data="games:info:dart"),
             InlineKeyboardButton("ᴄᴏɴᴛʀᴄᴛ", callback_data="games:info:stour")],
            [InlineKeyboardButton("ʀɪᴅᴅʟᴇ", callback_data="games:info:riddle")]
        ])

    @staticmethod
    def format_result(result: GameResult, emoji: str) -> str:
        status = "<b>✅ ᴡɪɴ</b>" if result.won else "<b>❌ ʟᴏsᴇ</b>"
        msg = f"<b>{emoji} ɢᴀᴍᴇ ʀᴇsᴜʟᴛ</b>\n{status}\n"
        if result.display_outcome:
            msg += f"<b>ᴏᴜᴛᴄᴏᴍᴇ: {result.display_outcome}</b>\n"
        msg += f"<b>{result.message}</b>"
        return msg


class GameLogic:
    @staticmethod
    def coinflip(guess: str, amount: int) -> GameResult:
        outcome = random.choice(['heads', 'tails'])
        won = outcome == guess
        if won:
            win = amount * CONFIG.coinflip_multiplier
            return GameResult(True, win, f"ʏᴏᴜ ᴡᴏɴ {win:,} ᴄᴏɪɴs", outcome.upper())
        return GameResult(False, 0, f"ʏᴏᴜ ʟᴏsᴛ {amount:,} ᴄᴏɪɴs", outcome.upper())

    @staticmethod
    def dice_roll(choice: str, amount: int) -> GameResult:
        dice = random.randint(1, 6)
        result = 'odd' if dice % 2 else 'even'
        won = result == choice
        res_str = 'ᴏᴅᴅ' if result == 'odd' else 'ᴇᴠᴇɴ'
        if won:
            win = amount * CONFIG.dice_multiplier
            return GameResult(True, win, f"ʀᴏʟʟᴇᴅ {dice} ({res_str})\nʏᴏᴜ ᴡᴏɴ {win:,} ᴄᴏɪɴs", f"🎲 {dice}")
        return GameResult(False, 0, f"ʀᴏʟʟᴇᴅ {dice} ({res_str})\nʏᴏᴜ ʟᴏsᴛ {amount:,} ᴄᴏɪɴs", f"🎲 {dice}")

    @staticmethod
    def gamble(pick: str, amount: int) -> GameResult:
        won = random.random() < CONFIG.gamble_win_rate
        if won:
            win = amount * CONFIG.gamble_multiplier
            display = random.choice(['L', 'R'])
            return GameResult(True, win, f"ʏᴏᴜ ᴡᴏɴ {win:,} ᴄᴏɪɴs", "ʟᴇғᴛ" if display == 'L' else "ʀɪɢʜᴛ")
        display = 'R' if pick == 'l' else 'L'
        return GameResult(False, 0, f"ʏᴏᴜ ʟᴏsᴛ {amount:,} ᴄᴏɪɴs", "ʟᴇғᴛ" if display == 'L' else "ʀɪɢʜᴛ")

    @staticmethod
    def basketball(amount: int) -> GameResult:
        win_chance = min(0.6, CONFIG.basket_base_win_rate + math.log1p(amount) / 50)
        won = random.random() < win_chance
        if won:
            win = amount * CONFIG.basket_multiplier
            return GameResult(True, win, f"ᴘᴇʀғᴇᴄᴛ sʜᴏᴛ! ʏᴏᴜ sᴄᴏʀᴇᴅ {win:,} ᴄᴏɪɴs")
        return GameResult(False, 0, f"ᴍɪssᴇᴅ! ʏᴏᴜ ʟᴏsᴛ {amount:,} ᴄᴏɪɴs")

    @staticmethod
    def darts(amount: int) -> GameResult:
        roll = random.random()
        if roll < CONFIG.dart_bullseye_rate:
            win = amount * CONFIG.dart_bullseye_multiplier
            return GameResult(True, win, f"ʙᴜʟʟsᴇʏᴇ! ʏᴏᴜ ᴡᴏɴ {win:,} ᴄᴏɪɴs", "🎯 ʙᴜʟʟsᴇʏᴇ")
        elif roll < (CONFIG.dart_bullseye_rate + CONFIG.dart_hit_rate):
            win = amount * CONFIG.dart_hit_multiplier
            return GameResult(True, win, f"ɢᴏᴏᴅ ʜɪᴛ! ʏᴏᴜ ᴡᴏɴ {win:,} ᴄᴏɪɴs", "ᴛᴀʀɢᴇᴛ ʜɪᴛ")
        return GameResult(False, 0, f"ᴍɪssᴇᴅ! ʏᴏᴜ ʟᴏsᴛ {amount:,} ᴄᴏɪɴs", "ᴍɪss")

    @staticmethod
    def contract() -> GameResult:
        if random.random() < CONFIG.stour_success_rate:
            reward = random.randint(100, 600)
            return GameResult(True, reward, f"ᴄᴏɴᴛʀᴀᴄᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ! ʏᴏᴜ ᴇᴀʀɴᴇᴅ {reward:,} ᴄᴏɪɴs")
        return GameResult(False, 0, f"ᴄᴏɴᴛʀᴀᴄᴛ ғᴀɪʟᴇᴅ! ʏᴏᴜ ʟᴏsᴛ {CONFIG.stour_entry_fee:,} ᴄᴏɪɴs")

    @staticmethod
    def generate_riddle() -> tuple[str, str]:
        a, b = random.randint(2, 50), random.randint(1, 50)
        op = random.choice(['+', '-', '*'])
        ans = a + b if op == '+' else (a - b if op == '-' else a * b)
        return f"{a} {op} {b}", str(ans)


async def get_msg(update: Update):
    return update.callback_query.message if update.callback_query else update.message


async def reply(update: Update, text: str, markup=None):
    msg = await get_msg(update)
    return await msg.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def check_cooldown(update: Update, user_id: int) -> bool:
    if remaining := game_state.check_cooldown(user_id):
        await reply(update, f"<b>⏱ ᴄᴏᴏʟᴅᴏᴡɴ ᴀᴄᴛɪᴠᴇ</b>\n<b>ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ {remaining:.1f}s ʙᴇғᴏʀᴇ ᴘʟᴀʏɪɴɢ ᴀɢᴀɪɴ.</b>")
        return True
    return False


async def validate_amount(update: Update, amount: int, user_id: int) -> bool:
    if amount <= 0:
        await reply(update, "<b>❌ ɪɴᴠᴀʟɪᴅ ᴀᴍᴏᴜɴᴛ</b>\n<b>ᴀᴍᴏᴜɴᴛ ᴍᴜsᴛ ʙᴇ ᴘᴏsɪᴛɪᴠᴇ.</b>")
        return False
    user = await UserDB.get(user_id)
    balance = user.get('balance', 0) if user else 0
    if balance < amount:
        await reply(update, "<b>💸 ɪɴsᴜғғɪᴄɪᴇɴᴛ ʙᴀʟᴀɴᴄᴇ</b>\n<b>ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴇɴᴏᴜɢʜ ᴄᴏɪɴs.</b>")
        return False
    return True


async def process_game(update: Update, context: CallbackContext, game_type: GameType, 
                      amount: int, result: GameResult, extra: str = ""):
    user_id = update.effective_user.id
    
    if result.won and result.amount_changed > 0:
        await UserDB.change_balance(user_id, result.amount_changed)
    
    game_state.record_play(user_id, game_type.value)
    game_state.set_cooldown(user_id)
    
    emoji = GAME_EMOJIS.get(game_type, "🎮")
    msg = GameUI.format_result(result, emoji)
    
    updated = await UserDB.get(user_id)
    curr_bal = updated.get('balance', 0) if updated else 0
    msg += f"\n<b>ʙᴀʟᴀɴᴄᴇ: <code>{curr_bal:,}</code> ᴄᴏɪɴs</b>"
    
    await reply(update, msg, GameUI.play_again(game_type.value, extra))


# --- GAME HANDLERS ---

async def sbet(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if await check_cooldown(update, user_id):
        return
    
    try:
        amount, guess = int(context.args[0]), context.args[1].lower()
    except (IndexError, ValueError):
        await reply(update, "<b>📖 ᴜsᴀɢᴇ</b>\n<code>/sbet &lt;amount&gt; heads|tails</code>\n<i><b>ᴇxᴀᴍᴘʟᴇ: /sbet 100 heads</b></i>")
        return
    
    guess = 'heads' if guess in ('h', 'head', 'heads') else ('tails' if guess in ('t', 'tail', 'tails') else None)
    if not guess:
        await reply(update, "<b>❌ ɪɴᴠᴀʟɪᴅ ᴄʜᴏɪᴄᴇ</b>\n<b>ᴍᴜsᴛ ʙᴇ 'heads' ᴏʀ 'tails'</b>")
        return
    
    await UserDB.ensure(user_id, update.effective_user.first_name, update.effective_user.username)
    if not await validate_amount(update, amount, user_id):
        return
    
    await UserDB.change_balance(user_id, -amount)
    result = GameLogic.coinflip(guess, amount)
    await process_game(update, context, GameType.COINFLIP, amount, result, f"{amount}:{guess}")


async def roll_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if await check_cooldown(update, user_id):
        return
    
    try:
        amount, choice = int(context.args[0]), context.args[1].lower()
    except (IndexError, ValueError):
        await reply(update, "<b>📖 ᴜsᴀɢᴇ</b>\n<code>/roll &lt;amount&gt; odd|even</code>\n<i><b>ᴇxᴀᴍᴘʟᴇ: /roll 50 odd</b></i>")
        return
    
    choice = 'odd' if choice in ('o', 'odd') else ('even' if choice in ('e', 'even') else None)
    if not choice:
        await reply(update, "<b>❌ ɪɴᴠᴀʟɪᴅ ᴄʜᴏɪᴄᴇ</b>\n<b>ᴍᴜsᴛ ʙᴇ 'odd' ᴏʀ 'even'</b>")
        return
    
    await UserDB.ensure(user_id, update.effective_user.first_name, update.effective_user.username)
    if not await validate_amount(update, amount, user_id):
        return
    
    await UserDB.change_balance(user_id, -amount)
    result = GameLogic.dice_roll(choice, amount)
    await process_game(update, context, GameType.DICE, amount, result, f"{amount}:{choice}")


async def gamble(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if await check_cooldown(update, user_id):
        return
    
    try:
        amount, pick = int(context.args[0]), context.args[1].lower()
    except (IndexError, ValueError):
        await reply(update, "<b>📖 ᴜsᴀɢᴇ</b>\n<code>/gamble &lt;amount&gt; l|r</code>\n<i><b>ᴇxᴀᴍᴘʟᴇ: /gamble 100 l</b></i>")
        return
    
    if pick not in ('l', 'r', 'left', 'right'):
        await reply(update, "<b>❌ ɪɴᴠᴀʟɪᴅ ᴄʜᴏɪᴄᴇ</b>\n<b>ᴍᴜsᴛ ʙᴇ 'l' ᴏʀ 'r'</b>")
        return
    
    pick = 'l' if pick.startswith('l') else 'r'
    await UserDB.ensure(user_id, update.effective_user.first_name, update.effective_user.username)
    if not await validate_amount(update, amount, user_id):
        return
    
    await UserDB.change_balance(user_id, -amount)
    result = GameLogic.gamble(pick, amount)
    await process_game(update, context, GameType.GAMBLE, amount, result, f"{amount}:{pick}")


async def basket(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if await check_cooldown(update, user_id):
        return
    
    try:
        amount = int(context.args[0])
    except (IndexError, ValueError):
        await reply(update, "<b>📖 ᴜsᴀɢᴇ</b>\n<code>/basket &lt;amount&gt;</code>\n<i><b>ᴇxᴀᴍᴘʟᴇ: /basket 75</b></i>")
        return
    
    await UserDB.ensure(user_id, update.effective_user.first_name, update.effective_user.username)
    if not await validate_amount(update, amount, user_id):
        return
    
    await UserDB.change_balance(user_id, -amount)
    result = GameLogic.basketball(amount)
    await process_game(update, context, GameType.BASKET, amount, result, str(amount))


async def dart(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if await check_cooldown(update, user_id):
        return
    
    try:
        amount = int(context.args[0])
    except (IndexError, ValueError):
        await reply(update, "<b>📖 ᴜsᴀɢᴇ</b>\n<code>/dart &lt;amount&gt;</code>\n<i><b>ᴇxᴀᴍᴘʟᴇ: /dart 50</b></i>")
        return
    
    await UserDB.ensure(user_id, update.effective_user.first_name, update.effective_user.username)
    if not await validate_amount(update, amount, user_id):
        return
    
    await UserDB.change_balance(user_id, -amount)
    result = GameLogic.darts(amount)
    await process_game(update, context, GameType.DART, amount, result, str(amount))


async def stour(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if await check_cooldown(update, user_id):
        return
    
    await UserDB.ensure(user_id, update.effective_user.first_name, update.effective_user.username)
    if not await validate_amount(update, CONFIG.stour_entry_fee, user_id):
        return
    
    await UserDB.change_balance(user_id, -CONFIG.stour_entry_fee)
    result = GameLogic.contract()
    await process_game(update, context, GameType.CONTRACT, CONFIG.stour_entry_fee, result)


async def riddle(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if await check_cooldown(update, user_id):
        return
    
    question, answer = GameLogic.generate_riddle()
    msg = await get_msg(update)
    text = (
        f"<b>🧩 ʀɪᴅᴅʟᴇ ᴛɪᴍᴇ</b>\n"
        f"<b>sᴏʟᴠᴇ: {question}</b>\n"
        f"<b>ᴛɪᴍᴇ: <code>{CONFIG.riddle_timeout}s</code> | ʀᴇᴡᴀʀᴅ: <code>50</code> ᴄᴏɪɴs</b>\n"
        f"<i><b>ʀᴇᴘʟʏ ᴡɪᴛʜ ᴛʜᴇ ɴᴜ姆ʙᴇʀ</b></i>"
    )
    sent = await msg.reply_text(text, parse_mode="HTML")
    
    riddle_data = PendingRiddle(answer, time.time() + CONFIG.riddle_timeout, sent.message_id, update.effective_chat.id, question)
    game_state.riddles[user_id] = riddle_data
    game_state.set_cooldown(user_id)
    game_state.record_play(user_id, GameType.RIDDLE.value)
    
    async def expire():
        await asyncio.sleep(CONFIG.riddle_timeout)
        if pending := game_state.riddles.get(user_id):
            if time.time() >= pending.expires_at:
                game_state.riddles.pop(user_id, None)
                try:
                    await application.bot.send_message(
                        pending.chat_id, 
                        f"<b>⏳ ᴛɪᴍᴇ's ᴜᴘ</b>\n<b>ᴀɴsᴡᴇʀ ᴡᴀs {answer}</b>", 
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
    
    asyncio.create_task(expire())


async def riddle_answer(update: Update, context: CallbackContext):
    if not update.effective_user or not update.message:
        return
    
    user_id = update.effective_user.id
    if not (pending := game_state.riddles.get(user_id)):
        return
    
    if not update.effective_chat or update.effective_chat.id != pending.chat_id:
        return
    
    text = (update.message.text or "").strip()
    if not text:
        return
    
    if time.time() > pending.expires_at:
        game_state.riddles.pop(user_id, None)
        return
    
    if text == pending.answer:
        await UserDB.change_balance(user_id, pending.reward_coins)
        user = await UserDB.get(user_id)
        bal = user.get('balance', 0) if user else 0
        await update.message.reply_text(
            f"<b>✅ ᴄᴏʀʀᴇᴄᴛ</b>\n<b>ᴇᴀʀɴᴇᴅ {pending.reward_coins} ᴄᴏɪɴs!</b>\n<b>ᴛᴏᴛᴀʟ: <code>{bal:,}</code></b>",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            f"<b>❌ ᴡʀᴏɴɢ</b>\n<b>ᴀɴsᴡᴇʀ ᴡᴀs {pending.answer}</b>",
            parse_mode="HTML"
        )
    
    game_state.riddles.pop(user_id, None)


async def games_menu(update: Update, context: CallbackContext):
    text = (
        f"<b>ᴀᴠᴀɪʟᴀʙʟᴇ ɢᴀᴍᴇs 🎮</b>\n"
        f"<b>ᴄᴏɪɴ ғʟɪᴘ • ᴅɪᴄᴇ ʀᴏʟʟ</b>\n"
        f"<b>ɢᴀᴍʙʟᴇ • ʙᴀsᴋᴇᴛʙᴀʟʟ</b>\n"
        f"<b>ᴅᴀʀᴛs • ᴄᴏɴᴛʀᴀᴄᴛ</b>\n"
        f"<b>ʀɪᴅᴅʟᴇ</b>"
    )
    await reply(update, text, GameUI.menu())


async def game_stats(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    await UserDB.ensure(user_id, update.effective_user.first_name, update.effective_user.username)
    user = await UserDB.get(user_id)
    stats = game_state.stats.get(user_id, {})
    
    if not stats:
        await reply(update, "<b>📊 ɴᴏ sᴛᴀᴛɪsᴛɪᴄs</b>\n<b>ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴘʟᴀʏᴇᴅ ᴀɴʏ ɢᴀᴍᴇs ʏᴇᴛ.</b>")
        return

    stat_lines = [f"• {game.upper()}: {count} ᴘʟᴀʏ(s)" for game, count in stats.items()]
    stats_str = "\n".join(stat_lines)
    name = user.get('first_name', 'ᴜɴᴋɴᴏᴡɴ') if user else 'ᴜɴᴋɴᴏᴡɴ'
    bal = user.get('balance', 0) if user else 0

    text = (
        f"<b>📊 ɢᴀᴍᴇ sᴛᴀᴛɪsᴛɪᴄs</b>\n"
        f"<b>ᴜsᴇʀ: {name}</b>\n\n"
        f"<b>{stats_str}</b>\n\n"
        f"<b>ᴄᴜʀʀᴇɴᴛ ʙᴀʟᴀɴᴄᴇ: <code>{bal:,}</code> ᴄᴏɪɴs</b>"
    )
    await reply(update, text)


# --- CALLBACK QUERY HANDLER FOR GAMES HUB & REPEAT ---

async def games_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data

    if not data.startswith("games:"):
        return

    parts = data.split(":")
    action = parts[1]

    if action == "info":
        game_cmd = parts[2]
        info_texts = {
            "sbet": "<b>🪙 ᴄᴏɪɴ ғʟɪᴘ</b>\nUsage: <code>/sbet &lt;amount&gt; heads|tails</code>",
            "roll": "<b>🎲 ᴅɪᴄᴇ ʀᴏʟʟ</b>\nUsage: <code>/roll &lt;amount&gt; odd|even</code>",
            "gamble": "<b>🎰 ɢᴀᴍʙʟᴇ</b>\nUsage: <code>/gamble &lt;amount&gt; l|r</code>",
            "basket": "<b>🏀 ʙᴀsᴋᴇᴛʙᴀʟʟ</b>\nUsage: <code>/basket &lt;amount&gt;</code>",
            "dart": "<b>🎯 ᴅᴀʀᴛs</b>\nUsage: <code>/dart &lt;amount&gt;</code>",
            "stour": f"<b>🤝 ᴄᴏɴᴛʀᴀᴄᴛ</b>\nUsage: <code>/stour</code>\nFee: {CONFIG.stour_entry_fee} coins",
            "riddle": "<b>🧩 ʀɪᴅᴅʟᴇ</b>\nUsage: <code>/riddle</code>"
        }
        await query.message.reply_text(info_texts.get(game_cmd, "Unknown Game"), parse_mode="HTML")

    elif action == "repeat":
        cmd = parts[2]
        args_str = parts[3]
        context.args = args_str.split(":") if args_str != "_" else []

        handlers = {
            "sbet": sbet,
            "roll": roll_cmd,
            "gamble": gamble,
            "basket": basket,
            "dart": dart,
            "stour": stour,
            "riddle": riddle
        }

        if handler := handlers.get(cmd):
            await handler(update, context)


# --- REGISTER HANDLERS INTO APPLICATION ---

application.add_handler(CommandHandler("sbet", sbet))
application.add_handler(CommandHandler("roll", roll_cmd))
application.add_handler(CommandHandler("gamble", gamble))
application.add_handler(CommandHandler("basket", basket))
application.add_handler(CommandHandler("dart", dart))
application.add_handler(CommandHandler("stour", stour))
application.add_handler(CommandHandler("riddle", riddle))
application.add_handler(CommandHandler("games", games_menu))
application.add_handler(CommandHandler("gamestats", game_stats))

# Callback Query Handler for Game Buttons
application.add_handler(CallbackQueryHandler(games_callback, pattern="^games:"))

# Message Handler for Riddle Answers
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, riddle_answer))

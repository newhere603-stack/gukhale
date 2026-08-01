import asyncio
import random
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler
from shivu import application, user_collection, collection, LOGGER

# RARITIES Import Check
try:
    from shivu.modules.harem import RARITIES, rarity_display
except ImportError:
    RARITIES = {}
    def rarity_display(k): return k.title()

# ---------------- CONFIG ----------------
OWNER_ID = 7657218453
SUDO_USERS = {7657218453}

PROPOSAL_COST = 2000
DICE_COOLDOWN = 1800
PROPOSE_COOLDOWN = 300
PROPOSE_SUCCESS_RATE = 0.5  # 50% Win Rate

UPDATE_GROUP_URL = "https://t.me/Anime_Group_hai"
UPDATE_GROUP_ID = -1003087506512

LOG_GROUP_ID = -1003893927065

PROPOSE_IMAGES = [
    "https://files.catbox.moe/nvx2um.jpg",
    "https://files.catbox.moe/vaz41p.jpg",
    "https://files.catbox.moe/a0ybe8.jpg",
    "https://files.catbox.moe/5z3vgb.jpg"
]
REJECT_IMAGES = [
    "https://files.catbox.moe/b9l3ot.jpg",
    "https://files.catbox.moe/yjygaj.jpg",
    "https://files.catbox.moe/8ezqu8.jpg"
]

# --- TEXT VARIATIONS ---
PROPOSE_START_TEXTS = [
    "<b>💫 ᴛʜᴇ ᴍᴏᴍᴇɴᴛ ʏᴏᴜ'ᴠᴇ ʙᴇᴇɴ ᴡᴀɪᴛɪɴɢ ғᴏʀ... 💍</b>",
    "<b>✨ ғɪɴᴀʟʟʏ ᴛʜᴇ ᴛɪᴍᴇ ʜᴀs ᴄᴏᴍᴇ ✨</b>",
    "<b>🌹 ʜᴏʟᴅɪɴɢ ʏᴏᴜʀ ʙʀᴇᴀᴛʜ, ʏᴏᴜ ᴋɴᴇᴇʟ ᴅᴏᴡɴ... 🛐</b>",
    "<b>🌙 ᴜɴᴅᴇʀ ᴛʜᴇ sᴛᴀʀʀʏ sᴋʏ, ᴀ sᴘᴇᴄɪᴀʟ ᴄᴏɴғᴇssɪᴏɴ... ✨</b>",
    "<b>💖 ᴀ ʜᴇᴀʀᴛ-ᴘᴏᴜɴᴅɪɴɢ ᴄᴏɴғᴇssɪᴏɴ ɪs ᴀʙᴏᴜᴛ ᴛᴏ ʜᴀᴘᴘᴇɴ! 💌</b>",
    "<b>🕊️ ᴛᴀᴋɪɴɢ ᴀ ᴅᴇᴇᴘ ʙʀᴇᴀᴛʜ... ɪs ɪᴛ ᴛʀᴜᴇ ʟᴏᴠᴇ? 🌸</b>"
]

PROPOSING_LOADING_TEXTS = [
    "<b>ᴘʀᴏᴘᴏsɪɴɢ ʜᴇʀ....💍</b>",
    "<b>🌸 ᴡᴀɪᴛɪɴɢ ғᴏʀ ʜᴇʀ ʀᴇsᴘᴏɴsᴇ....💌</b>",
    "<b>💓 ʜᴇʀ ʜᴇᴀʀᴛ ɪs ʙᴇᴀᴛɪɴɢ ғᴀsᴛ....💫</b>",
    "<b>✨ ᴏᴘᴇɴɪɴɢ ᴛʜᴇ ʀɪɴɢ ʙᴏx....🎁</b>",
    "<b>👀 ʟᴏᴏᴋɪɴɢ ɪɴᴛᴏ ʜᴇʀ ᴇʏᴇs....🕊️</b>"
]

DICE_REJECT_TEXTS = [
    "<b>ʏᴏᴜʀ ᴍᴀʀʀɪᴀɢᴇ ᴘʀᴏᴘᴏsᴀʟ ᴡᴀs ʀᴇᴊᴇᴄᴛᴇᴅ ᴀɴᴅ sʜᴇ ʀᴀɴ ᴀᴡᴀʏ!</b>",
    "<b>sʜᴇ sᴀɪᴅ 'ᴇᴡᴡ, ɴᴏ!' ᴀɴᴅ ʙʟᴏᴄᴋᴇᴅ ʏᴏᴜ ᴇᴠᴇʀʏᴡʜᴇʀᴇ!</b>",
    "<b>sʜᴇ ᴊᴜsᴛ ʟᴀᴜɢʜᴇᴅ ᴀᴛ ʏᴏᴜ ᴀɴᴅ ᴡᴀʟᴋᴇᴅ ᴀᴡᴀʏ!</b>",
    "<b>sʜᴇ sᴀɪᴅ sʜᴇ ᴏɴʟʏ sᴇᴇs ʏᴏᴜ ᴀs ᴀ ʙʀᴏᴛʜᴇʀ!</b>",
    "<b>ʏᴏᴜ ɢᴏᴛ ʀᴇᴊᴇᴄᴛᴇᴅ! sʜᴇ ɪs ᴀʟʀᴇᴀᴅʏ ᴅᴀᴛɪɴɢ sᴏᴍᴇᴏɴᴇ ᴇʟsᴇ.</b>"
]

PROPOSE_REJECT_TEXTS = [
    "<b>sʜᴇ sᴀɪᴅ sʜᴇ'ʟʟ ᴅᴀᴛᴇ ʏᴏᴜ... ɪɴ ʜᴇʀ ɴᴇxᴛ ʟɪғᴇ. ʙᴇᴛᴛᴇʀ ʟᴜᴄᴋ ɴᴇxᴛ ʀᴇɪɴᴄᴀʀɴᴀᴛɪᴏɴ! 🔄</b>",
    "<b>ʏᴏᴜ'ᴠᴇ ʙᴇᴇɴ ғʀɪᴇɴᴅ-ᴢᴏɴᴇᴅ sᴏ ʜᴀʀᴅ, ʏᴏᴜ'ʀᴇ ɴᴏᴡ ᴛʜᴇ ᴍᴀʏᴏʀ ᴏғ ғʀɪᴇɴᴅ ᴢᴏɴᴇ ᴄɪᴛʏ! 🏙️</b>",
    "<b>sʜᴇ ᴛᴏᴏᴋ ʏᴏᴜʀ ᴄᴏɪɴs, ᴀᴛᴇ ʏᴏᴜʀ ғᴏᴏᴅ, ᴀɴᴅ sᴀɪᴅ 'ʟᴇᴛ's ᴊᴜsᴛ ʙᴇ ʙᴇsᴛɪᴇs!' 🍟</b>",
    "<b>sʜᴇ sᴀɪᴅ ʏᴏᴜ ᴀʀᴇ ᴛᴏᴏ ɢᴏᴏᴅ ғᴏʀ ʜᴇʀ ᴀɴᴅ ʟᴇғᴛ ʏᴏᴜ ᴏɴ ʀᴇᴀᴅ! 💔</b>",
    "<b>ᴘʀᴏᴘᴏsᴀʟ ʀᴇᴊᴇᴄᴛᴇᴅ! sʜᴇ sᴀɪᴅ sʜᴇ ɪs ғᴏᴄᴜsɪɴɢ ᴏɴ ʜᴇʀ ᴀɴɪᴍᴇ ᴄᴀʀᴇᴇʀ ʀɪɢʜᴛ ɴᴏᴡ. 🎬</b>",
    "<b>sʜᴇ ᴊᴜsᴛ ʟᴀᴜɢʜᴇᴅ ᴀᴛ ʏᴏᴜ, sʟᴀᴘᴘᴇᴅ ʏᴏᴜ ᴀɴᴅ ᴄᴀʟʟᴇᴅ ᴛʜᴇ ᴄᴏᴘs! 🚓💨</b>",
    "<b>'ᴇᴡᴡ, ɴᴏ!' sʜᴇ sᴀɪᴅ ᴀɴᴅ ʙʟᴏᴄᴋᴇᴅ ʏᴏᴜ ᴏɴ ᴇᴠᴇʀʏ sᴏᴄɪᴀʟ ᴍᴇᴅɪᴀ! 🚫</b>"
]

DICE_RARITIES = ["🟢 Common", "🟣 Rare", "🟡 Legendary"]
PROPOSE_RARITIES = ["🔮 Celestial", "💫 Exclusive"]

cooldowns = {"dice": {}, "propose": {}}


# ---------------- HELPERS ----------------
def is_authorized(user_id: int) -> bool:
    return user_id == OWNER_ID or user_id in SUDO_USERS


def check_cooldown(user_id: int, cmd: str, seconds: int) -> tuple[bool, int]:
    last = cooldowns[cmd].get(user_id, 0)
    left = int(seconds - (time.time() - last))
    if left > 0:
        return False, left
    return True, 0


def set_cooldown(user_id: int, cmd: str):
    cooldowns[cmd][user_id] = time.time()


async def is_user_joined(update: Update, context: CallbackContext) -> bool:
    user = update.effective_user
    if not user:
        return True
    
    try:
        member = await context.bot.get_chat_member(UPDATE_GROUP_ID, user.id)
        return member.status in ("member", "administrator", "creator")
    except BadRequest:
        return True  
    except Exception as e:
        LOGGER.error(f"is_user_joined failed for {user.id}: {e}")
        return True


async def get_unique_char(user_id: int, rarities: list[str]):
    try:
        user = await user_collection.find_one({"id": user_id}) or {}
        owned = [c.get("id") for c in user.get("characters", []) if isinstance(c, dict)]
        pipeline = [
            {"$match": {"rarity": {"$in": rarities}, "id": {"$nin": owned}}},
            {"$sample": {"size": 1}},
        ]
        result = await collection.aggregate(pipeline).to_list(length=1)
        return result[0] if result else None
    except Exception as e:
        LOGGER.error(f"get_unique_char failed for {user_id}: {e}")
        return None


async def add_char_to_user(user_id: int, username: str, first_name: str, char: dict) -> bool:
    try:
        await user_collection.update_one(
            {"id": user_id},
            {
                "$push": {"characters": char},
                "$set": {"username": username, "first_name": first_name}
            },
            upsert=True,
        )
        return True
    except Exception as e:
        LOGGER.error(f"add_char_to_user failed for {user_id}: {e}")
        return False


async def send_win_log(context: CallbackContext, user, char: dict, method: str):
    text = (
        "<b>🏆 ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ ᴄʟᴀɪᴍᴇᴅ!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>👤 ᴜsᴇʀ: <a href='tg://user?id={user.id}'>{user.first_name}</a></b>\n"
        f"<b>🕹️ ᴍᴇᴛʜᴏᴅ: <code>/{method}</code></b>\n"
        f"<b>🌸 ɴᴀᴍᴇ: {char.get('name', 'Unknown')}</b>\n"
        f"<b>💎 ʀᴀʀɪᴛʏ: <code>{char.get('rarity', 'N/A')}</code></b>\n━━━━━━━━━━━━━━━━━━━━"
    )
    try:
        await context.bot.send_photo(LOG_GROUP_ID, char["img_url"], caption=text, parse_mode="HTML")
    except Exception as e:
        LOGGER.error(f"send_win_log failed: {e}")


# ---------------- /dice, /marry ----------------
async def dice_marry(update: Update, context: CallbackContext):
    if not update.effective_user or not update.effective_chat:
        return
    
    chat_id = update.effective_chat.id
    user = update.effective_user

    ok, rem = check_cooldown(user.id, "dice", DICE_COOLDOWN)
    if not ok:
        return await context.bot.send_message(
            chat_id=chat_id,
            text=f"<b>⏳ ᴡᴀɪᴛ {rem // 60}ᴍ {rem % 60}s ʙᴇғᴏʀᴇ ᴜsɪɴɢ /dice ᴀɢᴀɪɴ!</b>",
            parse_mode="HTML"
        )

    set_cooldown(user.id, "dice")
    val = (await context.bot.send_dice(chat_id, emoji="🎲")).dice.value
    await asyncio.sleep(3.5)

    if val not in (1, 6):
        return await context.bot.send_message(
            chat_id=chat_id,
            text=random.choice(DICE_REJECT_TEXTS),
            parse_mode="HTML"
        )

    char = await get_unique_char(user.id, DICE_RARITIES)
    if not char:
        return await context.bot.send_message(
            chat_id=chat_id,
            text="<b>ʏᴏᴜ ᴡᴏɴ, ʙᴜᴛ ɴᴏ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀs ʟᴇғᴛ ᴛᴏ ᴄʟᴀɪᴍ!</b>",
            parse_mode="HTML"
        )

    await add_char_to_user(user.id, user.username or "", user.first_name or "User", char)
    
    user_mention = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
    caption = (
        f"<b>🎉 ᴄᴏɴɢʀᴀᴛᴜʟᴀᴛɪᴏɴs {user_mention}!</b>\n"
        f"<b>🌸 ɴᴀᴍᴇ: {char.get('name', 'Unknown')}</b>\n"
        f"<b>💎 ʀᴀʀɪᴛʏ: {char.get('rarity', 'N/A')}</b>"
    )
    
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=char["img_url"],
        caption=caption,
        parse_mode="HTML"
    )
    await send_win_log(context, user, char, "dice")


# ---------------- /propose ----------------
async def propose(update: Update, context: CallbackContext):
    if not update.effective_user or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user

    # FSub Check
    if not await is_user_joined(update, context):
        btn = [
            [InlineKeyboardButton("ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇ", url=UPDATE_GROUP_URL)],
            [InlineKeyboardButton("ᴛʀʏ ᴀɢᴀɪɴ", callback_data="propose_checksub")]
        ]
        return await context.bot.send_message(
            chat_id=chat_id,
            text="<b>⚠️ ᴀᴄᴄᴇss ʟᴏᴄᴋᴇᴅ!</b>\n\n<b>ᴊᴏɪɴ ᴏᴜʀ ᴜᴘᴅᴀᴛᴇ ɢʀᴏᴜᴘ ᴛᴏ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.</b>",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode="HTML",
        )

    user_data = await user_collection.find_one({"id": user.id})
    if not user_data or user_data.get("balance", 0) < PROPOSAL_COST:
        return await context.bot.send_message(
            chat_id=chat_id,
            text="<b>ʏᴏᴜ ɴᴇᴇᴅ ᴀᴛ ʟᴇᴀꜱᴛ 2000 ᴄᴏɪɴs ᴛᴏ ᴘʀᴏᴘᴏꜱᴇ.</b>",
            parse_mode="HTML"
        )

    ok, rem = check_cooldown(user.id, "propose", PROPOSE_COOLDOWN)
    if not ok:
        return await context.bot.send_message(
            chat_id=chat_id,
            text=f"<b>⏳ ᴄᴏᴏʟᴅᴏᴡɴ: <code>{rem // 60}ᴍ {rem % 60}s</code></b>",
            parse_mode="HTML"
        )

    # Deduct coins & set cooldown
    await user_collection.update_one({"id": user.id}, {"$inc": {"balance": -PROPOSAL_COST}})
    set_cooldown(user.id, "propose")

    # Phase 1: Start Message
    msg = await context.bot.send_photo(
        chat_id=chat_id,
        photo=random.choice(PROPOSE_IMAGES),
        caption=random.choice(PROPOSE_START_TEXTS),
        parse_mode="HTML"
    )
    await asyncio.sleep(2)

    # Phase 2: Status Update
    try:
        await msg.edit_caption(
            caption=random.choice(PROPOSING_LOADING_TEXTS),
            parse_mode="HTML"
        )
    except Exception:
        pass

    await asyncio.sleep(2.5)

    # Phase 3: Result (Rejection or Win)
    if random.random() > PROPOSE_SUCCESS_RATE:
        try:
            await msg.delete()
        except Exception:
            pass
        return await context.bot.send_photo(
            chat_id=chat_id,
            photo=random.choice(REJECT_IMAGES),
            caption=random.choice(PROPOSE_REJECT_TEXTS),
            parse_mode="HTML",
        )

    char = await get_unique_char(user.id, PROPOSE_RARITIES)
    if not char:
        await user_collection.update_one({"id": user.id}, {"$inc": {"balance": PROPOSAL_COST}})
        try:
            await msg.delete()
        except Exception:
            pass
        return await context.bot.send_message(
            chat_id=chat_id,
            text="<b>ʀᴇғᴜɴᴅᴇᴅ! ɴᴏ ᴇxᴄʟᴜsɪᴠᴇ/ᴄᴇʟᴇsᴛɪᴀʟ ᴄʜᴀʀs ʟᴇғᴛ ғᴏʀ ʏᴏᴜ.</b>",
            parse_mode="HTML"
        )

    await add_char_to_user(user.id, user.username or "", user.first_name or "User", char)
    try:
        await msg.delete()
    except Exception:
        pass

    user_mention = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
    caption = (
        f"<b>🎉 {char.get('name', 'Waifu')} ʜᴀs ᴀᴄᴄᴇᴘᴛᴇᴅ {user_mention}'s ᴘʀᴏᴘᴏsᴀʟ! 💖</b>\n\n"
        f"<b>☘️ ɴᴀᴍᴇ: {char.get('name', 'Unknown')}</b>\n"
        f"<b>🏵️ ʀᴀʀɪᴛʏ: {char.get('rarity', 'N/A')}</b>\n"
        f"<b>🎞 ᴀɴɪᴍᴇ: {char.get('anime', 'Unknown')}</b>\n"
        f"<b>🔖 ɪᴅ: {char.get('id', 'N/A')}</b>"
    )
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=char["img_url"],
        caption=caption,
        parse_mode="HTML"
    )
    await send_win_log(context, user, char, "propose")


# ---------------- CALLBACK HANDLER FOR TRY AGAIN ----------------
async def propose_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    if not query:
        return

    try:
        await query.answer()
    except Exception:
        pass

    if query.data == "propose_checksub":
        user = query.from_user
        if not await is_user_joined(update, context):
            await query.answer("ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴊᴏɪɴᴇᴅ ᴛʜᴇ ᴜᴘᴅᴀᴛᴇ ɢʀᴏᴜᴘ ʏᴇᴛ!", show_alert=True)
            return
        
        try:
            await query.message.delete()
        except Exception:
            pass
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"<b>✨ ᴛʜᴀɴᴋs ғᴏʀ ᴊᴏɪɴɪɴɢ, <a href='tg://user?id={user.id}'>{user.first_name}</a>! ɴᴏᴡ ʏᴏᴜ ᴄᴀɴ ᴜsᴇ /propose ᴀɢᴀɪɴ.</b>",
            parse_mode="HTML"
        )


# ---------------- /cdm (owner/sudo) ----------------
async def cdm_cmd(update: Update, context: CallbackContext):
    if not update.effective_user or not update.effective_chat:
        return
        
    chat_id = update.effective_chat.id
    if not is_authorized(update.effective_user.id):
        return await context.bot.send_message(
            chat_id=chat_id,
            text="<b>🚫 ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴛᴏ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.</b>",
            parse_mode="HTML"
        )

    reply = update.message.reply_to_message if update.message else None
    target_id = reply.from_user.id if reply and reply.from_user else None
    
    if target_id is None and context.args:
        target_id = int(context.args[0]) if context.args[0].isdigit() else None

    if target_id is None:
        return await context.bot.send_message(
            chat_id=chat_id,
            text="<b>⚠️ ᴜsᴀɢᴇ: /cdm <user_id> (ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴛʜᴇ ᴜsᴇʀ's ᴍᴇssᴀɢᴇ)</b>",
            parse_mode="HTML"
        )

    cooldowns["dice"].pop(target_id, None)
    cooldowns["propose"].pop(target_id, None)
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"<b>ᴄᴏᴏʟᴅᴏᴡɴ ʀᴇsᴇᴛ ғᴏʀ ᴜsᴇʀ <code>{target_id}</code> (ᴍᴀʀʀʏ ɴ ᴘʀᴏᴘᴏsᴇ).</b>",
        parse_mode="HTML"
    )


# ---------------- HANDLERS ----------------
application.add_handler(CommandHandler(["dice", "marry"], dice_marry, block=False))
application.add_handler(CommandHandler(["propose"], propose, block=False))
application.add_handler(CommandHandler(["cdm"], cdm_cmd, block=False))
application.add_handler(CallbackQueryHandler(propose_callback, pattern=r"^propose_checksub$", block=False))

import asyncio
import random
import time
import re
from html import escape

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler

# 🔥 FIX: db aur sahi collections import ki hain
from shivu import application, user_collection, db, LOGGER
from shivu.Database.db import eco_collection

# Asli characters wali collection yahan set ki hai
collection = db['anime_characters_lol']

# ---------------- CUSTOM RARITIES ----------------
RARITIES = {
    "common": ("🟢", "Common"), "rare": ("🟠", "Rare"), "legendary": ("🟡", "Legendary"),
    "special": ("🔵", "Medium"), "celestial": ("🪽", "Celestial"), "erotic": ("🥵", "Spicy"),
    "exclusive": ("💮", "Exclusive"), "premium": ("🔮", "Premium Edition"), "mythic": ("💎", "Mythic"),
    "sweet": ("🍭", "Sweet"), "valentine": ("💞", "Valentine"), "winter": ("❄️", "Winter"),
    "neon": ("⚡", "Neon"), "pearl": ("🐚", "Summer"), "cosmic": ("🌌", "Cosmic"),
}

def get_rarity_display(rarity_str):
    if not isinstance(rarity_str, str):
        return "🟢 Common"
    rarity_str = rarity_str.strip()
    emoji, name = (rarity_str.split(' ', 1) + [''])[:2] if ' ' in rarity_str else (rarity_str, '')
    name = name.strip().lower()
    
    for key, (r_emoji, r_name) in RARITIES.items():
        if rarity_str.lower() == key or emoji == r_emoji or name == r_name.lower():
            return f"{r_emoji} {r_name}"
    
    return rarity_str

# ---------------- CONFIG ----------------
OWNER_ID = 7657218453
SUDO_USERS = {7657218453}

PROPOSAL_COST = 2000
DICE_COOLDOWN = 1800
PROPOSE_COOLDOWN = 300
PROPOSE_SUCCESS_RATE = 0.6  # 60% Win Rate

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
    "<b>ᴛʜᴇ ᴍᴀʀʀɪᴀɢᴇ ᴘʀᴏᴘᴏsᴀʟ ᴡᴀs ʀᴇᴊᴇᴄᴛᴇᴅ ᴀɴᴅ sʜᴇ ʀᴀɴ ᴀᴡᴀʏ!</b>",
    "<b>sʜᴇ sᴀɪᴅ 'ᴇᴡᴡ, ɴᴏ!' ᴀɴᴅ ʙʟᴏᴄᴋᴇᴅ ʏᴏᴜ ᴇᴠᴇʀʏᴡʜᴇʀᴇ!</b>",
    "<b>sʜᴇ ᴊᴜsᴛ ʟᴀᴜɢʜᴇᴅ ᴀɴᴅ wᴀʟᴋᴇᴅ ᴀᴡᴀʏ! 😂</b>",
    "<b>sʜᴇ sᴀɪᴅ sʜᴇ ᴏɴʟʏ sᴇᴇs ʏᴏᴜ ᴀs ᴀ ʙʀᴏᴛʜᴇʀ! 🫂</b>",
    "<b>ᴘʀᴏᴘᴏsᴀʟ ʀᴇᴊᴇᴄᴛᴇᴅ! sʜᴇ ɪs ᴀʟʀᴇᴀᴅʏ ᴅᴀᴛɪɴɢ sᴏᴍᴇᴏɴᴇ ᴇʟsᴇ.</b>"
]

PROPOSE_REJECT_TEXTS = [
    "<b>sʜᴇ sᴀɪᴅ sʜᴇ'ʟʟ ᴅᴀᴛᴇ ʏᴏᴜ... ɪɴ ʜᴇʀ ɴᴇxᴛ ʟɪғᴇ! 🔄</b>",
    "<b>ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ғʀɪᴇɴᴅ-ᴢᴏɴᴇᴅ sᴏ ʜᴀʀᴅ, ʏᴏᴜ ᴀʀᴇ ɴᴏᴡ ᴛʜᴇ ᴍᴀʏᴏʀ ᴏғ ғʀɪᴇɴᴅ ᴢᴏɴᴇ! 🏙️</b>",
    "<b>sʜᴇ ᴛᴏᴏᴋ ʏᴏᴜʀ ᴄᴏɪɴs, ᴀᴛᴇ ʏᴏᴜʀ ғᴏᴏᴅ, ᴀɴᴅ sᴀɪᴅ 'ʟᴇᴛ's ᴊᴜsᴛ ʙᴇ ʙᴇsᴛɪᴇs!' 🍟</b>",
    "<b>sʜᴇ sᴀɪᴅ ʏᴏᴜ ᴀʀᴇ ᴛᴏᴏ ɢᴏᴏᴅ ғᴏʀ ʜᴇʀ ᴀɴᴅ ʟᴇғᴛ ʏᴏᴜ ᴏɴ ʀᴇᴀᴅ!</b>",
    "<b>ᴘʀᴏᴘᴏsᴀʟ ʀᴇᴊᴇᴄᴛᴇᴅ! sʜᴇ sᴀɪᴅ sʜᴇ ɪs ғᴏᴄᴜsɪɴɢ ᴏɴ ʜᴇʀ ᴀɴɪᴍᴇ ᴄᴀʀᴇᴇʀ ʀɪɢʜᴛ ɴᴏᴡ. 🎬</b>",
    "<b>sʜᴇ ᴊᴜsᴛ ʟᴀᴜɢʜᴇᴅ, sʟᴀᴘᴘᴇᴅ ʏᴏᴜ ᴀɴᴅ ᴄᴀʟʟᴇᴅ ᴛʜᴇ ᴄᴏps! 🚓💨</b>",
    "<b>'ᴇᴡᴡ, ɴᴏ!' sʜᴇ sᴀɪᴅ ᴀɴْد ʙʟᴏᴄᴋᴇᴅ ʏᴏᴜ!</b>"
]

cooldowns = {"dice": {}, "propose": {}}
DISABLED_RARITIES = {"premium", "cosmic", "mythic"}

def fix_motor_loop():
    try:
        client = user_collection.database.client
        client.get_io_loop = asyncio.get_running_loop
    except Exception:
        pass

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

async def is_user_joined(context: CallbackContext, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=UPDATE_GROUP_ID, user_id=user_id)
        if member.status in ("member", "administrator", "creator", "restricted"):
            return True
        return False
    except Exception:
        return False

async def get_unique_char(user_id: int, rarity_pattern: str = None):
    try:
        user = await user_collection.find_one({"id": user_id})
        if not user:
            await user_collection.update_one(
                {"id": user_id},
                {"$setOnInsert": {"characters": [], "balance": 0}},
                upsert=True
            )
            user = {}

        raw_owned = [c.get("id") for c in user.get("characters", []) if isinstance(c, dict)]
        owned_set = set()
        for oid in raw_owned:
            if oid is not None:
                owned_set.add(str(oid))
                try:
                    owned_set.add(int(oid))
                except ValueError:
                    pass

        # Ab ye sahi 'anime_characters_lol' collection se data uthayega
        all_chars = await collection.find({"auction_exclusive": {"$ne": True}}).to_list(length=None)
        
        available_chars = []
        for char in all_chars:
            c_id = char.get("id")
            
            rarity_str = char.get("rarity", "").lower()
            skip_rarity = False
            for disabled in DISABLED_RARITIES:
                if disabled in rarity_str:
                    skip_rarity = True
                    break
            if skip_rarity:
                continue

            if c_id not in owned_set and str(c_id) not in owned_set:
                try:
                    if int(c_id) not in owned_set:
                        available_chars.append(char)
                        continue
                except (ValueError, TypeError):
                    pass
                if c_id not in owned_set:
                    available_chars.append(char)

        if not available_chars and all_chars:
            available_chars = [c for c in all_chars if not any(d in c.get("rarity", "").lower() for d in DISABLED_RARITIES)]

        if not available_chars:
            return None

        return random.choice(available_chars)
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
    except Exception:
        return False

async def send_win_log(context: CallbackContext, user, char: dict, method: str):
    user_link = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
    display_rarity = get_rarity_display(char.get('rarity', '🟢 Common'))
    text = (
        "<b>🏆 ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ ᴄʟᴀɪᴍᴇᴅ!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>👤 ᴜsᴇʀ: {user_link}</b>\n"
        f"<b>🕹️ ᴍᴇᴛʜᴏᴅ: <code>/{method}</code></b>\n"
        f"<b>🌸 ɴᴀᴍᴇ: {char.get('name', 'Unknown')}</b>\n"
        f"<b>💎 ʀᴀʀɪᴛʏ: <code>{display_rarity}</code></b>\n━━━━━━━━━━━━━━━━━━━━"
    )
    try:
        await context.bot.send_photo(LOG_GROUP_ID, char["img_url"], caption=text, parse_mode="HTML")
    except Exception:
        pass

async def prarity_on(update: Update, context: CallbackContext):
    if not is_authorized(update.effective_user.id):
        return  
    if not context.args:
        return await update.message.reply_text(
            "<b>ᴜsᴀɢᴇ: /prarity_on &lt;ʀᴀʀɪᴛʏ_ɴᴀᴍᴇ&gt;</b>\n<b>ᴇxᴀᴍᴘʟᴇ:</b> <code>/prarity_on ᴘʀᴇᴍɪᴜᴍ</code>", 
            parse_mode="HTML"
        )
    rarity_name = " ".join(context.args).lower()
    if rarity_name in DISABLED_RARITIES:
        DISABLED_RARITIES.remove(rarity_name)
        await update.message.reply_text(f"✅ <b>ʀᴀʀɪᴛʏ '{rarity_name.title()}' ʜᴀs ʙᴇᴇɴ ᴇɴᴀʙʟᴇᴅ.</b>", parse_mode="HTML")
    else:
        await update.message.reply_text(f"⚠️ <b>ʀᴀʀɪᴛʏ '{rarity_name.title()}' ɪs ᴀʟʀᴇᴀᴅʏ ᴇɴᴀʙʟᴇᴅ.</b>", parse_mode="HTML")

async def prarity_off(update: Update, context: CallbackContext):
    if not is_authorized(update.effective_user.id):
        return  
    if not context.args:
        return await update.message.reply_text(
            "<b>ᴜsᴀɢᴇ: /prarity_off &lt;ʀᴀʀɪᴛʏ_ɴᴀᴍᴇ&gt;</b>\n<b>ᴇxᴀᴍᴘʟᴇ:</b> <code>/prarity_off ᴘʀᴇᴍɪᴜᴍ</code>", 
            parse_mode="HTML"
        )
    rarity_name = " ".join(context.args).lower()
    if rarity_name not in DISABLED_RARITIES:
        DISABLED_RARITIES.add(rarity_name)
        await update.message.reply_text(f"❌ <b>ʀᴀʀɪᴛʏ '{rarity_name.title()}' ʜᴀs ʙᴇᴇɴ ᴅɪsᴀʙʟᴇᴅ.</b>", parse_mode="HTML")
    else:
        await update.message.reply_text(f"⚠️ <b>ʀᴀʀɪᴛʏ '{rarity_name.title()}' ɪs ᴀʟʀᴇᴀᴅʏ ᴅɪsᴀʙʟᴇᴅ.</b>", parse_mode="HTML")

async def dice_marry(update: Update, context: CallbackContext):
    fix_motor_loop() 
    if not update.message or not update.effective_user:
        return
    
    chat_id = update.effective_chat.id
    user = update.effective_user
    msg_id = update.message.message_id
    plain_name = user.first_name

    ok, rem = check_cooldown(user.id, "dice", DICE_COOLDOWN)
    if not ok:
        return await context.bot.send_message(
            chat_id=chat_id,
            text=f"<b>⏳ ᴡᴀɪᴛ {rem // 60}ᴍ {rem % 60}s ʙᴇғᴏʀᴇ ᴜsɪɴɢ ᴀɢᴀɪɴ!</b>",
            parse_mode="HTML",
            reply_to_message_id=msg_id
        )

    set_cooldown(user.id, "dice")
    
    dice_msg = await context.bot.send_dice(chat_id=chat_id, emoji="🎲", reply_to_message_id=msg_id)
    val = dice_msg.dice.value
    await asyncio.sleep(3.5)

    if val not in (1, 2, 5, 6):
        text = random.choice(DICE_REJECT_TEXTS)
        return await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_to_message_id=msg_id)

    char = await get_unique_char(user.id, None)
    if not char:
        cooldowns["dice"].pop(user.id, None) 
        return await context.bot.send_message(chat_id=chat_id, text=f"<b>ʏᴏᴜ ᴡᴏɴ, ʙᴜᴛ ɴᴏ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀs ʟᴇғᴛ ᴛᴏ ᴄʟᴀɪᴍ!</b>", parse_mode="HTML", reply_to_message_id=msg_id)

    await add_char_to_user(user.id, user.username or "", plain_name or "User", char)
    display_rarity = get_rarity_display(char.get('rarity', '🟢 Common'))
    caption = f"<b>🎉 ᴄᴏɴɢʀᴀᴛᴜʟᴀᴛɪᴏns!</b>\n<b>🌸 ɴᴀᴍᴇ: {char.get('name', 'Unknown')}</b>\n<b>💎 ʀᴀʀɪᴛʏ: {display_rarity}</b>"
    
    await context.bot.send_photo(chat_id=chat_id, photo=char["img_url"], caption=caption, parse_mode="HTML", reply_to_message_id=msg_id)
    await send_win_log(context, user, char, "dice")

async def propose(update: Update, context: CallbackContext):
    fix_motor_loop() 
    if not update.message or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    msg_id = update.message.message_id
    plain_name = user.first_name

    if not await is_user_joined(context, user.id):
        btn = [
            [InlineKeyboardButton("ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇ", url=UPDATE_GROUP_URL)],
            [InlineKeyboardButton("ᴛʀʏ ᴀɢᴀɪɴ", callback_data="propose_checksub")]
        ]
        return await context.bot.send_message(
            chat_id=chat_id,
            text=f"<b>⚠️ ᴀᴄᴄᴇss ʟᴏᴄᴋᴇᴅ!</b>\n\n<b>ᴊᴏɪɴ ᴏᴜʀ ᴜᴘᴅᴀᴛᴇ ᴛᴏ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.</b>",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode="HTML",
            reply_to_message_id=msg_id
        )

    user_data = await eco_collection.find_one({"id": user.id})
    if not user_data or user_data.get("balance", 0) < PROPOSAL_COST:
        return await context.bot.send_message(
            chat_id=chat_id,
            text=f"<b>ʏᴏᴜ ɴᴇᴇᴅ ᴀᴛ ʟᴇᴀꜱᴛ {PROPOSAL_COST} ᴄᴏɪɴs ᴛᴏ ᴘʀᴏᴘᴏꜱᴇ.</b>",
            parse_mode="HTML",
            reply_to_message_id=msg_id
        )

    ok, rem = check_cooldown(user.id, "propose", PROPOSE_COOLDOWN)
    if not ok:
        return await context.bot.send_message(
            chat_id=chat_id,
            text=f"<b>⏳ ᴄᴏᴏʟᴅᴏᴡɴ: <code>{rem // 60}ᴍ {rem % 60}s</code></b>",
            parse_mode="HTML",
            reply_to_message_id=msg_id
        )

    await eco_collection.update_one({"id": user.id}, {"$inc": {"balance": -PROPOSAL_COST}})
    set_cooldown(user.id, "propose")

    msg = await context.bot.send_photo(
        chat_id=chat_id,
        photo=random.choice(PROPOSE_IMAGES),
        caption=random.choice(PROPOSE_START_TEXTS),
        parse_mode="HTML",
        reply_to_message_id=msg_id
    )
    await asyncio.sleep(2)

    try:
        await msg.edit_caption(caption=random.choice(PROPOSING_LOADING_TEXTS), parse_mode="HTML")
    except Exception:
        pass

    await asyncio.sleep(2.5)

    try:
        await msg.delete()
    except Exception:
        pass

    if random.random() > PROPOSE_SUCCESS_RATE:
        reject_text = random.choice(PROPOSE_REJECT_TEXTS)
        return await context.bot.send_photo(
            chat_id=chat_id,
            photo=random.choice(REJECT_IMAGES),
            caption=reject_text,
            parse_mode="HTML",
            reply_to_message_id=msg_id
        )

    char = await get_unique_char(user.id, None)
    
    if not char:
        await eco_collection.update_one({"id": user.id}, {"$inc": {"balance": PROPOSAL_COST}})
        return await context.bot.send_message(
            chat_id=chat_id,
            text=f"<b>ʀᴇғᴜɴᴅᴇᴅ! ɴᴏ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀs ʟᴇғᴛ ꜰᴏʀ ʏᴏᴜ.</b>",
            parse_mode="HTML",
            reply_to_message_id=msg_id
        )

    await add_char_to_user(user.id, user.username or "", plain_name or "User", char)
    display_rarity = get_rarity_display(char.get('rarity', '🟢 Common'))
    caption = (
        f"<b>🎉 ʏᴏᴜʀ ᴘʀᴏᴘᴏsᴀʟ ʜᴀs ʙᴇᴇɴ ᴀᴄᴄᴇᴘᴛᴇᴅ! 💖</b>\n\n"
        f"<b>☘️ ɴᴀᴍᴇ: {char.get('name', 'Unknown')}</b>\n"
        f"<b>🏵️ ʀᴀʀɪᴛʏ: {display_rarity}</b>\n"
        f"<b>🎞 ᴀɴɪᴍᴇ: {char.get('anime', 'Unknown')}</b>\n"
        f"<b>🔖 ɪᴅ: {char.get('id', 'N/A')}</b>"
    )
    await context.bot.send_photo(chat_id=chat_id, photo=char["img_url"], caption=caption, parse_mode="HTML", reply_to_message_id=msg_id)
    await send_win_log(context, user, char, "propose")

async def propose_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    if not query:
        return

    if query.data == "propose_checksub":
        user = query.from_user
        if not await is_user_joined(context, user.id):
            return await query.answer("ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴊᴏɪɴᴇᴅ ᴛʜᴇ ᴜᴘᴅᴀᴛᴇ ɢʀᴏᴜᴘ ʏᴇᴛ!", show_alert=True)
        
        await query.answer("✅ ᴠᴇʀɪғɪᴇᴅ! ʏᴏᴜ ᴄᴀɴ ɴᴏᴡ ᴘʀᴏᴘᴏsᴇ.", show_alert=False)
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"<b>✨ ᴛʜᴀɴᴋs ғᴏʀ ᴊᴏɪɴɪɴɢ! ɴᴏᴡ ʏᴏᴜ ᴄᴀɴ ᴜsᴇ /propose ᴀɢᴀɪɴ.</b>", parse_mode="HTML")

async def cdm_cmd(update: Update, context: CallbackContext):
    if not update.message or not update.effective_user:
        return
    chat_id = update.effective_chat.id
    msg_id = update.message.message_id

    if not is_authorized(update.effective_user.id):
        return  

    reply = update.message.reply_to_message if update.message else None
    target_id = None
    target_name = "User"
    
    if reply and reply.from_user:
        target_id = reply.from_user.id
        target_name = reply.from_user.first_name
    elif context.args and context.args[0].isdigit():
        target_id = int(context.args[0])
        try:
            user_info = await context.bot.get_chat(target_id)
            target_name = user_info.first_name or f"User {target_id}"
        except Exception:
            target_name = f"User {target_id}"

    if target_id is None:
        return await context.bot.send_message(
            chat_id=chat_id,
            text=f"<b>ᴜsᴀɢᴇ: /cdm &lt;ᴜsᴇʀ_ɪᴅ&gt; (ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴛʜᴇ ᴜsᴇʀ's ᴍᴇssᴀɢᴇ)</b>",
            parse_mode="HTML",
            reply_to_message_id=msg_id
        )

    cooldowns["dice"].pop(target_id, None)
    cooldowns["propose"].pop(target_id, None)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"<b>✅ ᴄᴏᴏʟᴅᴏᴡɴ ʀᴇsᴇᴛ ғᴏʀ <a href='tg://user?id={target_id}'>{target_name}</a>.</b>",
        parse_mode="HTML",
        reply_to_message_id=msg_id
    )

application.add_handler(CommandHandler(["dice", "marry"], dice_marry, block=False))
application.add_handler(CommandHandler(["propose"], propose, block=False))
application.add_handler(CommandHandler(["cdm"], cdm_cmd, block=False))
application.add_handler(CommandHandler(["prarity_on"], prarity_on, block=False))
application.add_handler(CommandHandler(["prarity_off"], prarity_off, block=False))
application.add_handler(CallbackQueryHandler(propose_callback, pattern=r"^propose_checksub$", block=False))

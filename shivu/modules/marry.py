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

# Asli collections yahan set ki hain
collection = db['anime_characters_lol']
bot_settings_collection = db['bot_settings'] # 🔥 Persistent Settings ke liye

# ---------------- CUSTOM RARITIES ----------------
RARITIES = {
    "mythic": ("💎", '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>', "Mythic"),
    "cosmic": ("🌌", '<tg-emoji emoji-id="5431783411981228752">🎆</tg-emoji>', "Cosmic"),
    "celestial": ("🪽", '<tg-emoji emoji-id="5434121252874756456">🕊</tg-emoji>', "Celestial"),
    "exclusive": ("💮", '<tg-emoji emoji-id="5262772355779809182">💮</tg-emoji>', "Exclusive"),
    "legendary": ("🟡", '<tg-emoji emoji-id="6084550327086883643">🔥</tg-emoji>', "Legendary"),
    "premium": ("🔮", '<tg-emoji emoji-id="6093919703753831564">🔮</tg-emoji>', "Premium Edition"),
    "neon": ("⚡", '<tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>', "Neon"),
    "summer": ("🏖️", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"),
    "sweet": ("🍭", '<tg-emoji emoji-id="6222115531122546353">🍭</tg-emoji>', "Sweet"),
    "special": ("🔵", '<tg-emoji emoji-id="5393592081748877575">🔵</tg-emoji>', "Medium"),
    "valentine": ("💞", '<tg-emoji emoji-id="5255861796350224063">❤️</tg-emoji>', "Valentine"),
    "winter": ("❄️", '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>', "Winter"),
    "erotic": ("🥵", '<tg-emoji emoji-id="6093490292923574796">❤️‍🔥</tg-emoji>', "Spicy"),
    "rare": ("🟠", '<tg-emoji emoji-id="5339390195768774311">🟠</tg-emoji>', "Rare"),
    "common": ("🟢", '<tg-emoji emoji-id="6093722470265658964">🟢</tg-emoji>', "Common")
}

def get_rarity_display(rarity_str):
    if not isinstance(rarity_str, str):
        return '<tg-emoji emoji-id="6093722470265658964">🟢</tg-emoji> Common'
    rarity_str = rarity_str.strip()
    emoji, name = (rarity_str.split(' ', 1) + [''])[:2] if ' ' in rarity_str else (rarity_str, '')
    name = name.strip().lower()
    
    for key, (r_emoji, prem_emoji, r_name) in RARITIES.items():
        if rarity_str.lower() == key or emoji == r_emoji or name == r_name.lower():
            return f"{prem_emoji} {r_name}"
    
    return rarity_str

def get_base_rarity(rarity_str):
    if not rarity_str:
        return "common"
    rarity_str = str(rarity_str).lower().strip()
    for key, (r_emoji, prem_emoji, r_name) in RARITIES.items():
        if key in rarity_str or r_name.lower() in rarity_str or r_emoji in rarity_str:
            return key
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

# 🔥 EXTRA MESSAGES ADDED HERE
PROPOSE_START_TEXTS = [
    "<b><tg-emoji emoji-id=\"5469741319330996757\">💫</tg-emoji> ᴛʜᴇ ᴍᴏᴍᴇɴᴛ ʏᴏᴜ'ᴠᴇ ʙᴇᴇɴ ᴡᴀɪᴛɪɴɢ ғᴏʀ... <tg-emoji emoji-id=\"5262922516426420894\">💍</tg-emoji></b>",
    "<b><tg-emoji emoji-id=\"5472164874886846699\">✨</tg-emoji> ғɪɴᴀʟʟʏ ᴛʜᴇ ᴛɪᴍᴇ ʜᴀs ᴄᴏᴍᴇ <tg-emoji emoji-id=\"5472164874886846699\">✨</tg-emoji></b>",
    "<b><tg-emoji emoji-id=\"5440911110838425969\">🌹</tg-emoji> ʜᴏʟᴅɪɴɢ ʏᴏᴜʀ ʙʀᴇᴀᴛʜ, ʏᴏᴜ ᴋɴᴇᴇʟ ᴅᴏᴡɴ... <tg-emoji emoji-id=\"5370900820336319679\">🥰</tg-emoji></b>",
    "<b><tg-emoji emoji-id=\"6093881568739205721\">🌙</tg-emoji> ᴜɴᴅᴇʀ ᴛʜᴇ sᴛᴀʀʀʏ sᴋʏ, ᴀ sᴘᴇᴄɪᴀʟ ᴄᴏɴғᴇssɪᴏɴ... <tg-emoji emoji-id=\"5472164874886846699\">✨</tg-emoji></b>",
    "<b><tg-emoji emoji-id=\"5276239041052828276\">🎭</tg-emoji> ᴀ ʜᴇᴀʀᴛ-ᴘᴏᴜɴᴅɪɴɢ ᴄᴏɴғᴇssɪᴏɴ ɪs ᴀʙᴏᴜᴛ ᴛᴏ ʜᴀᴘᴘᴇɴ! <tg-emoji emoji-id=\"6093681968724059707\">💌</tg-emoji></b>",
    "<b><tg-emoji emoji-id=\"5339145893734001606\">🕊️</tg-emoji> ᴛᴀᴋɪɴɢ ᴀ ᴅᴇᴇᴘ ʙʀᴇᴀᴛʜ... ɪs ɪᴛ ᴛʀᴜᴇ ʟᴏᴠᴇ? <tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji></b>",
    "<b><tg-emoji emoji-id=\"5472164874886846699\">✨</tg-emoji> ɢᴀᴛʜᴇʀɪɴɢ ᴄᴏᴜʀᴀɢᴇ ᴛᴏ sᴀʏ ɪᴛ... <tg-emoji emoji-id=\"5449455694870748968\">💓</tg-emoji></b>",
    "<b><tg-emoji emoji-id=\"5339145893734001606\">🕊️</tg-emoji> sᴛᴇᴘᴘɪɴɢ ᴄʟᴏsᴇʀ ᴡɪᴛʜ ᴀ ʙᴇᴀᴛɪɴɢ ʜᴇᴀʀᴛ... <tg-emoji emoji-id=\"5276239041052828276\">🎭</tg-emoji></b>",
    "<b><tg-emoji emoji-id=\"5469741319330996757\">💫</tg-emoji> ᴀ ᴍᴀɢɪᴄᴀʟ ᴍᴏᴍᴇɴᴛ ɪs ᴜɴғᴏʟᴅɪɴɢ... <tg-emoji emoji-id=\"5472164874886846699\">✨</tg-emoji></b>"
]

# 🔥 EXTRA LOADING MESSAGES ADDED HERE
PROPOSING_LOADING_TEXTS = [
    "<b>ᴘʀᴏᴘᴏsɪɴɢ ʜᴇʀ....<tg-emoji emoji-id=\"5262922516426420894\">💍</tg-emoji></b>",
    "<b><tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji> ᴡᴀɪᴛɪɴɢ ғᴏʀ ʜᴇʀ ʀᴇsᴘᴏɴsᴇ....<tg-emoji emoji-id=\"6093681968724059707\">💌</tg-emoji></b>",
    "<b><tg-emoji emoji-id=\"5449455694870748968\">💓</tg-emoji> ʜᴇʀ ʜᴇᴀʀᴛ ɪs ʙᴇᴀᴛɪɴɢ ғᴀsᴛ....<tg-emoji emoji-id=\"5469741319330996757\">💫</tg-emoji></b>",
    "<b><tg-emoji emoji-id=\"5472164874886846699\">✨</tg-emoji> ᴏᴘᴇɴɪɴɢ ᴛʜᴇ ʀɪɴɢ ʙᴏx....<tg-emoji emoji-id=\"5199749070830197566\">🎁</tg-emoji></b>",
    "<b><tg-emoji emoji-id=\"5424885441100782420\">👀</tg-emoji> ʟᴏᴏᴋɪɴɢ ɪɴᴛᴏ ʜᴇʀ ᴇʏᴇs....<tg-emoji emoji-id=\"5339145893734001606\">🕊️</tg-emoji></b>",
    "<b><tg-emoji emoji-id=\"5276239041052828276\">🎭</tg-emoji> ᴇxᴘʀᴇssɪɴɢ ᴛʀᴜᴇ ғᴇᴇʟɪɴɢs....<tg-emoji emoji-id=\"6093681968724059707\">💌</tg-emoji></b>",
    "<b><tg-emoji emoji-id=\"5472164874886846699\">✨</tg-emoji> sʜᴏᴡɪɴɢ ᴛʜᴇ ʙᴇᴀᴜᴛɪғᴜʟ ʀɪɴɢ....<tg-emoji emoji-id=\"5262922516426420894\">💍</tg-emoji></b>",
    "<b><tg-emoji emoji-id=\"5339145893734001606\">🕊️</tg-emoji> ʜᴏᴘɪɴɢ ғᴏʀ ᴀ ʏᴇs....<tg-emoji emoji-id=\"5469741319330996757\">💫</tg-emoji></b>"
]

DICE_REJECT_TEXTS = [
    "<b>ᴛʜᴇ ᴍᴀʀʀɪᴀɢᴇ ᴘʀᴏᴘᴏsᴀʟ ᴡᴀs ʀᴇᴊᴇᴄᴛᴇᴅ ᴀɴᴅ sʜᴇ ʀᴀɴ ᴀᴡᴀʏ!</b>",
    "<b>sʜᴇ sᴀɪᴅ 'ᴇᴡᴡ, ɴᴏ!' ᴀɴᴅ ʙʟᴏᴄᴋᴇᴅ ʏᴏᴜ ᴇᴠᴇʀʏᴡʜᴇʀᴇ!</b>",
    "<b>sʜᴇ ᴊᴜsᴛ ʟᴀᴜɢʜᴇᴅ ᴀɴᴅ ᴡᴀʟᴋᴇᴅ ᴀᴡᴀʏ! <tg-emoji emoji-id=\"6332083912424036002\">😂</tg-emoji></b>",
    "<b>sʜᴇ sᴀɪᴅ sʜᴇ ᴏɴʟʏ sᴇᴇs ʏᴏᴜ ᴀs ᴀ ʙʀᴏᴛʜᴇʀ! <tg-emoji emoji-id=\"6159082552431746788\">🫂</tg-emoji></b>",
    "<b>ᴘʀᴏᴘᴏsᴀʟ ʀᴇᴊᴇᴄᴛᴇᴅ! sʜᴇ ɪs ᴀʟʀᴇᴀᴅʏ ᴅᴀᴛɪɴɢ sᴏᴍᴇᴏɴᴇ ᴇʟsᴇ.</b>"
]

# 🔥 EXTRA REJECT MESSAGES ADDED HERE
PROPOSE_REJECT_TEXTS = [
    "<b>sʜᴇ sᴀɪᴅ sʜᴇ'ʟʟ ᴅᴀᴛᴇ ʏᴏᴜ... ɪɴ ʜᴇʀ ɴᴇxᴛ ʟɪғᴇ! <tg-emoji emoji-id=\"6332088903176038586\">🤣</tg-emoji></b>",
    "<b>ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ғʀɪᴇɴᴅ-ᴢᴏɴᴇᴅ sᴏ ʜᴀʀᴅ, ʏᴏᴜ ᴀʀᴇ ɴᴏᴡ ᴛʜᴇ ᴍᴀʏᴏʀ ᴏғ ғʀɪᴇɴᴅ ᴢᴏɴᴇ! <tg-emoji emoji-id=\"6332245643712533982\">🏙</tg-emoji></b>",
    "<b>sʜᴇ ᴛᴏᴏᴋ ʏᴏᴜʀ ᴄᴏɪɴs, ᴀᴛᴇ ʏᴏᴜʀ ғᴏᴏᴅ, ᴀɴᴅ sᴀɪᴅ 'ʟᴇᴛ's ᴊᴜsᴛ ʙᴇ ʙᴇsᴛɪᴇs!' <tg-emoji emoji-id=\"5370962534721395008\">🍟</tg-emoji></b>",
    "<b>sʜᴇ sᴀɪᴅ ʏᴏᴜ ᴀʀᴇ ᴛᴏᴏ ɢᴏᴏᴅ ғᴏʀ ʜᴇʀ ᴀɴᴅ ʟᴇғᴛ ʏᴏᴜ ᴏɴ ʀᴇᴀᴅ!</b>",
    "<b>ᴘʀᴏᴘᴏsᴀʟ ʀᴇᴊᴇᴄᴛᴇᴅ! sʜᴇ sᴀɪᴅ sʜᴇ ɪs ғᴏᴄᴜsɪɴɢ ᴏɴ ʜᴇʀ ᴀɴɪᴍᴇ ᴄᴀʀᴇᴇʀ ʀɪɢʜᴛ ɴᴏᴡ. <tg-emoji emoji-id=\"5375464961822695044\">🎬</tg-emoji></b>",
    "<b>sʜᴇ ᴊᴜsᴛ ʟᴀᴜɢʜᴇᴅ, sʟᴀᴘᴘᴇᴅ ʏᴏᴜ ᴀɴᴅ ᴄᴀʟʟᴇᴅ ᴛʜᴇ ᴄᴏᴘs! <tg-emoji emoji-id=\"5444893443169983691\">🚓</tg-emoji><tg-emoji emoji-id=\"6078051040840653263\">💨</tg-emoji></b>",
    "<b>'ᴇᴡᴡ, ɴᴏ!' sʜᴇ sᴀɪᴅ ᴀɴᴅ ʙʟᴏᴄᴋᴇᴅ ʏᴏᴜ!</b>",
    "<b>sʜᴇ ʀᴏʟʟᴇᴅ ʜᴇʀ ᴇʏᴇs ᴀɴᴅ ʟᴇғᴛ! <tg-emoji emoji-id=\"5424885441100782420\">👀</tg-emoji></b>",
    "<b>ᴘʀᴏᴘᴏsᴀʟ ғᴀɪʟᴇᴅ! sʜᴇ ᴘʀᴇғᴇʀs 𝟸ᴅ ʜᴜsʙᴀɴᴅᴏs. <tg-emoji emoji-id=\"5375464961822695044\">🎬</tg-emoji></b>",
    "<b>sʜᴇ ᴄᴀʟʟᴇᴅ ʏᴏᴜ ᴀ ᴄʀᴇᴇᴘ ᴀɴᴅ ʀᴀɴ ᴀᴡᴀʏ! <tg-emoji emoji-id=\"5444893443169983691\">🚓</tg-emoji><tg-emoji emoji-id=\"6078051040840653263\">💨</tg-emoji></b>",
    "<b>ʏᴏᴜ ɢᴏᴛ ʀᴇᴊᴇᴄᴛᴇᴅ ɪɴ 𝟺ᴋ! <tg-emoji emoji-id=\"6332083912424036002\">😂</tg-emoji></b>"
]

cooldowns = {"dice": {}, "propose": {}}

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

# 🔥 YAHAN PE ROBUST DATABASE LOGIC LAGAYI HAI
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

        # Fetch disabled rarities purely from DB & Normalize them
        settings = await bot_settings_collection.find_one({'_id': 'game_settings'})
        if settings and 'disabled_rarities' in settings:
            raw_disabled = set(settings['disabled_rarities'])
        else:
            raw_disabled = {"premium", "cosmic", "mythic"}
            
        normalized_disabled = {get_base_rarity(d) for d in raw_disabled}

        all_chars = await collection.find({"auction_exclusive": {"$ne": True}}).to_list(length=None)
        
        available_chars = []
        for char in all_chars:
            c_id = char.get("id")
            
            # PERFECT RARITY MATCH
            char_rarity_key = get_base_rarity(char.get("rarity", ""))
            
            if char_rarity_key in normalized_disabled:
                continue

            # CLEAN OWNERSHIP CHECK
            is_owned = False
            if c_id in owned_set or str(c_id) in owned_set:
                is_owned = True
            else:
                try:
                    if int(c_id) in owned_set:
                        is_owned = True
                except (ValueError, TypeError):
                    pass
            
            if not is_owned:
                available_chars.append(char)

        if not available_chars and all_chars:
            available_chars = [c for c in all_chars if get_base_rarity(c.get("rarity", "")) not in normalized_disabled]

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
        f"<b><tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji> ɴᴀᴍᴇ: {char.get('name', 'Unknown')}</b>\n"
        f"<b><tg-emoji emoji-id=\"6093611479720795757\">💫</tg-emoji> ʀᴀʀɪᴛʏ: {display_rarity}</b>\n━━━━━━━━━━━━━━━━━━━━"
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
    
    raw_input = " ".join(context.args)
    base_key = get_base_rarity(raw_input)
    
    settings = await bot_settings_collection.find_one({'_id': 'game_settings'})
    raw_disabled = set(settings.get('disabled_rarities', ["premium", "cosmic", "mythic"])) if settings else {"premium", "cosmic", "mythic"}
    normalized_disabled = {get_base_rarity(d) for d in raw_disabled}

    if base_key in normalized_disabled:
        normalized_disabled.remove(base_key)
        await bot_settings_collection.update_one({'_id': 'game_settings'}, {'$set': {'disabled_rarities': list(normalized_disabled)}}, upsert=True)
        await update.message.reply_text(f"<tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji> <b>ʀᴀʀɪᴛʏ '{base_key.title()}' ʜᴀs ʙᴇᴇɴ ᴇɴᴀʙʟᴇᴅ.</b>", parse_mode="HTML")
    else:
        await update.message.reply_text(f"<tg-emoji emoji-id=\"6309717264639726942\">⚠️</tg-emoji> <b>ʀᴀʀɪᴛʏ '{base_key.title()}' ɪs ᴀʟʀᴇᴀᴅʏ ᴇɴᴀʙʟᴇᴅ.</b>", parse_mode="HTML")

async def prarity_off(update: Update, context: CallbackContext):
    if not is_authorized(update.effective_user.id):
        return  
    if not context.args:
        return await update.message.reply_text(
            "<b>ᴜsᴀɢᴇ: /prarity_off &lt;ʀᴀʀɪᴛʏ_ɴᴀᴍᴇ&gt;</b>\n<b>ᴇxᴀᴍᴘʟᴇ:</b> <code>/prarity_off ᴘʀᴇᴍɪᴜᴍ</code>", 
            parse_mode="HTML"
        )
        
    raw_input = " ".join(context.args)
    base_key = get_base_rarity(raw_input)
    
    settings = await bot_settings_collection.find_one({'_id': 'game_settings'})
    raw_disabled = set(settings.get('disabled_rarities', ["premium", "cosmic", "mythic"])) if settings else {"premium", "cosmic", "mythic"}
    normalized_disabled = {get_base_rarity(d) for d in raw_disabled}

    if base_key not in normalized_disabled:
        normalized_disabled.add(base_key)
        await bot_settings_collection.update_one({'_id': 'game_settings'}, {'$set': {'disabled_rarities': list(normalized_disabled)}}, upsert=True)
        await update.message.reply_text(f"<tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> <b>ʀᴀʀɪᴛʏ '{base_key.title()}' ʜᴀs ʙᴇᴇɴ ᴅɪsᴀʙʟᴇᴅ.</b>", parse_mode="HTML")
    else:
        await update.message.reply_text(f"<tg-emoji emoji-id=\"6309717264639726942\">⚠️</tg-emoji> <b>ʀᴀʀɪᴛʏ '{base_key.title()}' ɪs ᴀʟʀᴇᴀᴅʏ ᴅɪsᴀʙʟᴇᴅ.</b>", parse_mode="HTML")

async def dice_marry(update: Update, context: CallbackContext):
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
            text=f"<b><tg-emoji emoji-id=\"5451732530048802485\">⏳</tg-emoji> ᴡᴀɪᴛ {rem // 60}ᴍ {rem % 60}s ʙᴇғᴏʀᴇ ᴜsɪɴɢ ᴀɢᴀɪɴ!</b>",
            parse_mode="HTML",
            reply_to_message_id=msg_id
        )

    set_cooldown(user.id, "dice")
    
    try:
        dice_msg = await context.bot.send_dice(chat_id=chat_id, emoji="🎲", reply_to_message_id=msg_id)
        await asyncio.sleep(3.2)

        val = dice_msg.dice.value
        if val not in (1, 2, 5, 6):
            text = random.choice(DICE_REJECT_TEXTS)
            return await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_to_message_id=msg_id)

        char = await get_unique_char(user.id, None)
        if not char:
            return await context.bot.send_message(chat_id=chat_id, text=f"<b><tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji> ʏᴏᴜ ᴡᴏɴ, ʙᴜᴛ ɴᴏ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀs ʟᴇғᴛ ᴛᴏ ᴄʟᴀɪᴍ!</b>", parse_mode="HTML", reply_to_message_id=msg_id)

        await add_char_to_user(user.id, user.username or "", plain_name or "User", char)
        display_rarity = get_rarity_display(char.get('rarity', '🟢 Common'))
        caption = f"<b><tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji> ᴄᴏɴɢʀᴀᴛᴜʟᴀᴛɪᴏɴs!</b>\n<b><tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji> ɴᴀᴍᴇ: {char.get('name', 'Unknown')}</b>\n<b><tg-emoji emoji-id=\"6093611479720795757\">💫</tg-emoji> ʀᴀʀɪᴛʏ: {display_rarity}</b>"
        
        await context.bot.send_photo(chat_id=chat_id, photo=char["img_url"], caption=caption, parse_mode="HTML", reply_to_message_id=msg_id)
        await send_win_log(context, user, char, "dice")
    except Exception as e:
        LOGGER.error(f"Error in dice command: {e}")
        cooldowns["dice"].pop(user.id, None)

async def propose(update: Update, context: CallbackContext):
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
            text=f"<b><tg-emoji emoji-id=\"5291873529464122510\">🔓</tg-emoji> ᴀᴄᴄᴇss ʟᴏᴄᴋᴇᴅ!</b>\n\n<b>ᴊᴏɪɴ ᴏᴜʀ ᴜᴘᴅᴀᴛᴇ ᴛᴏ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.</b>",
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
            text=f"<b><tg-emoji emoji-id=\"5451732530048802485\">⏳</tg-emoji> ᴄᴏᴏʟᴅᴏᴡɴ: <code>{rem // 60}ᴍ {rem % 60}s</code></b>",
            parse_mode="HTML",
            reply_to_message_id=msg_id
        )

    # Coins seedha cut kar rahe hain
    await eco_collection.update_one({"id": user.id}, {"$inc": {"balance": -PROPOSAL_COST}})
    set_cooldown(user.id, "propose")

    try:
        msg = await context.bot.send_photo(
            chat_id=chat_id,
            photo=random.choice(PROPOSE_IMAGES),
            caption=random.choice(PROPOSE_START_TEXTS),
            parse_mode="HTML",
            reply_to_message_id=msg_id
        )
        
        # Fast animation (Flood Control safe logic)
        await asyncio.sleep(1.2)
        try:
            await msg.edit_caption(caption=random.choice(PROPOSING_LOADING_TEXTS), parse_mode="HTML")
            await asyncio.sleep(1.2)
        except TelegramError:
            # Agar edit par flood control hit hua to ignore karke seedha result dega
            pass
        
        try:
            await msg.delete()
        except TelegramError:
            pass

    except TelegramError as e:
        LOGGER.error(f"Error sending propose image: {e}")
        # Agar pehla message hi send nahi hua, tabhi fail return hoga
        return

    # Check Success or Failure
    if random.random() > PROPOSE_SUCCESS_RATE:
        reject_text = random.choice(PROPOSE_REJECT_TEXTS)
        try:
            return await context.bot.send_photo(
                chat_id=chat_id,
                photo=random.choice(REJECT_IMAGES),
                caption=reject_text,
                parse_mode="HTML",
                reply_to_message_id=msg_id
            )
        except Exception:
            return

    char = await get_unique_char(user.id, None)
    
    if not char:
        # Koi naya char nahi hai. No refund, seedha reply
        try:
            return await context.bot.send_message(
                chat_id=chat_id,
                text=f"<b><tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji> ʏᴏᴜ ᴡᴏɴ, ʙᴜᴛ ɴᴏ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀs ʟᴇғᴛ ᴛᴏ ᴄʟᴀɪᴍ!</b>",
                parse_mode="HTML",
                reply_to_message_id=msg_id
            )
        except Exception:
            return

    await add_char_to_user(user.id, user.username or "", plain_name or "User", char)
    display_rarity = get_rarity_display(char.get('rarity', '🟢 Common'))
    caption = (
        f"<b><tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji> ʏᴏᴜʀ ᴘʀᴏᴘᴏsᴀʟ ʜᴀs ʙᴇᴇɴ ᴀᴄᴄᴇᴘᴛᴇᴅ! <tg-emoji emoji-id=\"5276239041052828276\">🎭</tg-emoji></b>\n\n"
        f"<b><tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji> ɴᴀᴍᴇ: {char.get('name', 'Unknown')}</b>\n"
        f"<b><tg-emoji emoji-id=\"6093611479720795757\">💫</tg-emoji> ʀᴀʀɪᴛʏ: {display_rarity}</b>\n"
        f"<b><tg-emoji emoji-id=\"6314494724266796319\">🟠</tg-emoji> ᴀɴɪᴍᴇ: {char.get('anime', 'Unknown')}</b>\n"
        f"<b><tg-emoji emoji-id=\"6332443074769196273\">🆔</tg-emoji> ɪᴅ: {char.get('id', 'N/A')}</b>"
    )
    
    try:
        await context.bot.send_photo(chat_id=chat_id, photo=char["img_url"], caption=caption, parse_mode="HTML", reply_to_message_id=msg_id)
        await send_win_log(context, user, char, "propose")
    except Exception as e:
        LOGGER.error(f"Error sending propose win: {e}")

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
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"<b><tg-emoji emoji-id=\"5472164874886846699\">✨</tg-emoji> ᴛʜᴀɴᴋs ғᴏʀ ᴊᴏɪɴɪɴɢ! ɴᴏᴡ ʏᴏᴜ ᴄᴀɴ ᴜsᴇ /propose ᴀɢᴀɪɴ.</b>", parse_mode="HTML")

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
        text=f"<b><tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji> ᴄᴏᴏʟᴅᴏᴡɴ ʀᴇsᴇᴛ ғᴏʀ <a href='tg://user?id={target_id}'>{target_name}</a>.</b>",
        parse_mode="HTML",
        reply_to_message_id=msg_id
    )

application.add_handler(CommandHandler(["dice", "marry"], dice_marry, block=False))
application.add_handler(CommandHandler(["propose"], propose, block=False))
application.add_handler(CommandHandler(["cool"], cdm_cmd, block=False))
application.add_handler(CommandHandler(["prarity_on"], prarity_on, block=False))
application.add_handler(CommandHandler(["prarity_off"], prarity_off, block=False))
application.add_handler(CallbackQueryHandler(propose_callback, pattern=r"^propose_checksub$", block=False))

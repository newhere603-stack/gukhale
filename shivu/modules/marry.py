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
    "exclusive": ("💮", '<tg-emoji emoji-id="5764869176736880220">👀</tg-emoji>', "Exclusive"),
    "legendary": ("🟡", '<tg-emoji emoji-id="6084550327086883643">🔥</tg-emoji>', "Legendary"),
    "premium": ("🔮", '<tg-emoji emoji-id="6093919703753831564">🔮</tg-emoji>', "Premium Edition"),
    "neon": ("⚡", '<tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>', "Neon"),
    "summer": ("🏖️", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"),
    "sweet": ("🍭", '<tg-emoji emoji-id="6222115531122546353">🍭</tg-emoji>', "Sweet"),
    "special": ("🔴", '<tg-emoji emoji-id="6093741664474504699">🔴</tg-emoji>', "Medium"),
    "valentine": ("💞", '<tg-emoji emoji-id="5255861796350224063">❤️</tg-emoji>', "Valentine"),
    "winter": ("❄️", '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>', "Winter"),
    "erotic": ("🥵", '<tg-emoji emoji-id="6093490292923574796">❤️‍🔥</tg-emoji>', "Spicy"),
    "rare": ("🟠", '<tg-emoji emoji-id="5339390195768774311">🟠</tg-emoji>', "Rare"),
    "common": ("🟢", '<tg-emoji emoji-id="6093865707424980866">🟢</tg-emoji>', "Common")
}

def get_rarity_details(rarity_str):
    if not rarity_str:
        return ('<tg-emoji emoji-id="6093865707424980866">🟢</tg-emoji>', 'Common')
    rarity_str = str(rarity_str).lower().strip()
    for key, (r_emoji, prem_emoji, r_name) in RARITIES.items():
        if key in rarity_str or r_name.lower() in rarity_str or r_emoji in rarity_str:
            return (prem_emoji, r_name)
    return ('<tg-emoji emoji-id="6093865707424980866">🟢</tg-emoji>', rarity_str.title())

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
PROPOSE_SUCCESS_RATE = 0.23  # 🔥 EXACT 23% WIN CHANCE!

UPDATE_GROUP_URL = "https://t.me/Anime_Group_hai"
UPDATE_GROUP_ID = -1003087506512
LOG_GROUP_ID = -1003893927065

PROPOSE_IMAGES = [
    "https://files.catbox.moe/nvx2um.jpg",
    "https://files.catbox.moe/vaz41p.jpg",
    "https://files.catbox.moe/a0ybe8.jpg",
    "https://files.catbox.moe/5z3vgb.jpg"
]

# 🔥 UNIQUE REJECT IMAGES (No Duplicates)
REJECT_IMAGES = [
    "https://files.catbox.moe/2ala3u.png",
    "https://files.catbox.moe/k01s4a.png",
    "https://files.catbox.moe/hno2jd.png",
    "https://files.catbox.moe/mia10p.png",
    "https://files.catbox.moe/l5i2sr.png",
    "https://files.catbox.moe/mn22b9.png",
    "https://files.catbox.moe/8b7ibd.png",
    "https://files.catbox.moe/z96p27.png",
    "https://files.catbox.moe/b4x4yb.png",
    "https://files.catbox.moe/z7i3e8.png",
    "https://files.catbox.moe/m18gqd.png"
]

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

# 🔥 FUNNY DICE REJECTS IN HINGLISH
DICE_REJECT_TEXTS = [
    "<b>ᴘʀᴏᴘᴏsᴀʟ ʀᴇᴊᴇᴄᴛ ʜᴏ ɢᴀʏᴀ ᴀᴜʀ ᴡᴏ ʙʜᴀɢ ɢᴀʏɪ! <tg-emoji emoji-id=\"6078051040840653263\">💨</tg-emoji></b>",
    "<b>ᴜsɴᴇ ʙᴏʟᴀ 'ᴇᴡᴡ, ɴᴏ!' ᴀᴜʀ sᴀʙ ᴊᴀɢᴀʜ sᴇ ʙʟᴏᴄᴋ ᴋᴀʀ ᴅɪʏᴀ! <tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji></b>",
    "<b>ᴡᴏ ʙᴀs ʜᴀsɪ ᴀᴜʀ ᴡᴀʜᴀɴ sᴇ ᴄʜᴀʟɪ ɢᴀʏɪ! <tg-emoji emoji-id=\"6332083912424036002\">😂</tg-emoji></b>",
    "<b>ᴜsɴᴇ ʙᴏʟᴀ ᴋɪ ᴡᴏ ᴛᴜᴍʜᴇ sɪʀғ ᴇᴋ ʙʜᴀɪ ᴋɪ ᴛᴀʀᴀʜ ᴅᴇᴋʜᴛɪ ʜᴀɪ! <tg-emoji emoji-id=\"6159082552431746788\">🫂</tg-emoji></b>",
    "<b>ᴘʀᴏᴘᴏsᴀʟ ʀᴇᴊᴇᴄᴛᴇᴅ! ᴡᴏ ᴘᴇʜʟᴇ sᴇ ᴋɪsɪ ᴀᴜʀ ᴋᴏ ᴅᴀᴛᴇ ᴋᴀʀ ʀᴀʜɪ ʜᴀɪ. <tg-emoji emoji-id=\"6332245643712533982\">🏙</tg-emoji></b>",
    "<b>ᴛᴜᴍɴᴇ ᴅɪᴄᴇ ʀᴏʟʟ ᴋɪʏᴀ, ᴘᴀʀ ᴜsɴᴇ ᴀᴘɴɪ ᴀᴀɴᴋʜᴇɪɴ ʀᴏʟʟ ᴋᴀʀ ᴅɪ! <tg-emoji emoji-id=\"5424885441100782420\">👀</tg-emoji></b>",
    "<b>ᴡᴏ ᴛᴜᴍʜᴇ ᴅᴇᴋʜ ᴋᴀʀ ᴛᴀʀᴀs ᴋʜᴀᴛᴇ ʜᴜᴇ ʀᴏɴᴇ ʟᴀɢɪ! <tg-emoji emoji-id=\"6332088903176038586\">🤣</tg-emoji></b>",
    "<b>ᴜsɴᴇ ᴅɪᴄᴇ ᴡᴀᴘᴀs ᴛᴜᴍʜᴀʀᴇ ᴍᴜʜ ᴘᴀʀ ᴍᴀᴀʀ ᴅɪʏᴀ! <tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji></b>",
    "<b>ᴜsɴᴇ ᴛᴜᴍʜᴇ ᴄʀᴇᴇᴘ ʙᴏʟᴋᴀʀ ᴘᴏʟɪᴄᴇ ʙᴜʟᴀ ʟɪ! <tg-emoji emoji-id=\"5444893443169983691\">🚓</tg-emoji></b>"
]

# 🔥 FUNNY PROPOSE REJECT MESSAGES IN HINGLISH
PROPOSE_REJECT_TEXTS = [
    "<b>ᴜsɴᴇ ʙᴏʟᴀ ᴡᴏ ᴛᴜᴍsᴇ ᴀɢʟᴇ ᴊᴀɴᴀᴍ ᴍᴇɪɴ ᴘᴀᴛᴇɢɪ! <tg-emoji emoji-id=\"6332088903176038586\">🤣</tg-emoji></b>",
    "<b>ᴛᴜᴍ ɪᴛɴɪ ʙᴜʀɪ ᴛᴀʀᴀʜ ғʀɪᴇɴᴅ-ᴢᴏɴᴇ ʜᴜᴇ ʜᴏ ᴋɪ ᴀʙ ᴛᴜᴍ ᴡᴀʜᴀɴ ᴋᴇ ᴍᴀʏᴏʀ ʜᴏ! <tg-emoji emoji-id=\"6332245643712533982\">🏙</tg-emoji></b>",
    "<b>ᴜsɴᴇ ᴛᴜᴍʜᴀʀᴇ ᴄᴏɪɴs ʟɪʏᴇ, ᴋʜᴀɴᴀ ᴋʜᴀʏᴀ ᴀᴜʀ ʙᴏʟɪ 'ʜᴜᴍ ʙᴀs ʙᴇsᴛɪᴇs ʜᴀɪɴ!' <tg-emoji emoji-id=\"5370962534721395008\">🍟</tg-emoji></b>",
    "<b>ᴜsɴᴇ ʙᴏʟᴀ ᴛᴜᴍ ᴜsᴋᴇ ʟɪʏᴇ ʙᴏʜᴏᴛ ᴀᴄᴄʜᴇ ʜᴏ ᴀᴜʀ sᴇᴇɴ ᴋᴀʀᴋᴇ ᴄʜʜᴏᴅ ᴅɪʏᴀ! <tg-emoji emoji-id=\"6078051040840653263\">💨</tg-emoji></b>",
    "<b>ᴘʀᴏᴘᴏsᴀʟ ʀᴇᴊᴇᴄᴛᴇᴅ! ᴜsɴᴇ ʙᴏʟᴀ ᴡᴏ ᴀʙʜɪ ᴀᴘɴᴇ ᴀɴɪᴍᴇ ᴄᴀʀᴇᴇʀ ᴘᴀʀ ғᴏᴄᴜs ᴋᴀʀ ʀᴀʜɪ ʜᴀɪ. <tg-emoji emoji-id=\"5375464961822695044\">🎬</tg-emoji></b>",
    "<b>ᴡᴏ ᴢᴏʀsᴇ ʜᴀsɪ, ᴛᴜᴍʜᴇ ᴛʜᴀᴘᴘᴀᴅ ᴍᴀᴀʀᴀ ᴀᴜʀ ᴘᴏʟɪᴄᴇ ʙᴜʟᴀ ʟɪ! <tg-emoji emoji-id=\"5444893443169983691\">🚓</tg-emoji><tg-emoji emoji-id=\"6078051040840653263\">💨</tg-emoji></b>",
    "<b>'ᴇᴡᴡ, ɴᴏ!' ʙᴏʟᴋᴀʀ ᴜsɴᴇ ʙʟᴏᴄᴋ ᴋᴀʀ ᴅɪʏᴀ! <tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji></b>",
    "<b>ᴜsɴᴇ ɪɢɴᴏʀᴇ ᴋɪʏᴀ ᴀᴜʀ ᴋɪsɪ ᴀᴜʀ ʟᴀᴅᴋᴇ ᴋᴇ sᴀᴛʜ ɴɪᴋᴀʟ ɢᴀʏɪ! <tg-emoji emoji-id=\"5424885441100782420\">👀</tg-emoji></b>",
    "<b>ᴘʀᴏᴘᴏsᴀʟ ғᴀɪʟᴇᴅ! ᴜsʜᴇ ᴛᴜᴍʜᴀʀᴇ ʙᴀᴊᴀʏᴇ 𝟸ᴅ ʜᴜsʙᴀɴᴅᴏs ᴢʏᴀᴅᴀ ᴘᴀsᴀɴᴅ ʜᴀɪɴ. <tg-emoji emoji-id=\"5375464961822695044\">🎬</tg-emoji></b>",
    "<b>ᴜsɴᴇ ᴛᴜᴍʜᴇ ᴄʀᴇᴇᴘ ʙᴏʟᴀ ᴀᴜʀ ᴅᴀʀʀ ᴋᴇ ʙʜᴀɢ ɢᴀʏɪ! <tg-emoji emoji-id=\"5444893443169983691\">🚓</tg-emoji><tg-emoji emoji-id=\"6078051040840653263\">💨</tg-emoji></b>",
    "<b>ʙʜᴀɪ ᴛᴇʀᴀ ᴛᴏ 𝟺ᴋ ᴍᴇɪɴ ᴋᴀᴛ ɢᴀʏᴀ! <tg-emoji emoji-id=\"6332083912424036002\">😂</tg-emoji></b>",
    "<b>ᴜsɴᴇ ʙᴏʟᴀ 'ᴍᴀɪɴ ᴛᴜᴍsᴇ ᴘʏᴀʀ ᴋᴀʀᴛɪ ʜᴜ... ᴘᴀʀ ᴇᴋ ʙʜᴀɪ ᴋɪ ᴛᴀʀᴀʜ!' <tg-emoji emoji-id=\"6159082552431746788\">🫂</tg-emoji></b>",
    "<b>ᴜsɴᴇ ᴛᴜᴍʜᴀʀᴀ ʙᴀɴᴋ ʙᴀʟᴀɴᴄᴇ ᴅᴇᴋʜᴀ ᴀᴜʀ ᴄʜᴀʟɪ ɢᴀʏɪ! <tg-emoji emoji-id=\"6332088903176038586\">🤣</tg-emoji></b>"
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
    prem_emoji, r_name = get_rarity_details(char.get('rarity', 'common'))
    text = (
        "<b>🏆 ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ ᴄʟᴀɪᴍᴇᴅ!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>👤 ᴜsᴇʀ: {user_link}</b>\n"
        f"<b>🕹️ ᴍᴇᴛʜᴏᴅ: <code>/{method}</code></b>\n"
        f"<b><tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji> ɴᴀᴍᴇ: {char.get('name', 'Unknown')}</b>\n"
        f"<b>{prem_emoji} ʀᴀʀɪᴛʏ: {r_name}</b>\n━━━━━━━━━━━━━━━━━━━━"
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
    
    if base_key not in RARITIES:
        return await update.message.reply_text(f"<b><tg-emoji emoji-id=\"6309717264639726942\">⚠️</tg-emoji> ɪɴᴠᴀʟɪᴅ ʀᴀʀɪᴛʏ ɴᴀᴍᴇ! ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ʀᴀʀɪᴛʏ.</b>", parse_mode="HTML")
    
    settings = await bot_settings_collection.find_one({'_id': 'game_settings'})
    raw_disabled = set(settings.get('disabled_rarities', ["premium", "cosmic", "mythic"])) if settings else {"premium", "cosmic", "mythic"}
    normalized_disabled = {get_base_rarity(d) for d in raw_disabled if get_base_rarity(d) in RARITIES}

    if base_key in normalized_disabled:
        normalized_disabled.remove(base_key)
        await bot_settings_collection.update_one({'_id': 'game_settings'}, {'$set': {'disabled_rarities': list(normalized_disabled)}}, upsert=True)
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji> ʀᴀʀɪᴛʏ '{base_key.upper()}' ʜᴀs ʙᴇᴇɴ ᴇɴᴀʙʟᴇᴅ.</b>", parse_mode="HTML")
    else:
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"6309717264639726942\">⚠️</tg-emoji> ʀᴀʀɪᴛʏ '{base_key.upper()}' ɪs ᴀʟʀᴇᴀᴅʏ ᴇɴᴀʙʟᴇᴅ.</b>", parse_mode="HTML")

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
    
    if base_key not in RARITIES:
        return await update.message.reply_text(f"<b><tg-emoji emoji-id=\"6309717264639726942\">⚠️</tg-emoji> ɪɴᴠᴀʟɪᴅ ʀᴀʀɪᴛʏ ɴᴀᴍᴇ! ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ʀᴀʀɪᴛʏ.</b>", parse_mode="HTML")
    
    settings = await bot_settings_collection.find_one({'_id': 'game_settings'})
    raw_disabled = set(settings.get('disabled_rarities', ["premium", "cosmic", "mythic"])) if settings else {"premium", "cosmic", "mythic"}
    normalized_disabled = {get_base_rarity(d) for d in raw_disabled if get_base_rarity(d) in RARITIES}

    if base_key not in normalized_disabled:
        normalized_disabled.add(base_key)
        await bot_settings_collection.update_one({'_id': 'game_settings'}, {'$set': {'disabled_rarities': list(normalized_disabled)}}, upsert=True)
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> ʀᴀʀɪᴛʏ '{base_key.upper()}' ʜᴀs ʙᴇᴇɴ ᴅɪsᴀʙʟᴇᴅ.</b>", parse_mode="HTML")
    else:
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"6309717264639726942\">⚠️</tg-emoji> ʀᴀʀɪᴛʏ '{base_key.upper()}' ɪs ᴀʟʀᴇᴀᴅʏ ᴅɪsᴀʙʟᴇᴅ.</b>", parse_mode="HTML")

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
        
        # 🔥 Suspenseful wait for dice roll to complete (takes approx ~4 seconds)
        await asyncio.sleep(4.0)

        val = dice_msg.dice.value
        # 🔥 EXACT 23% OVERALL WIN RATE LOGIC
        # Probability of rolling 5 or 6 = 33.3%
        # So we apply a random check of 69% if you roll 5 or 6 (0.3333 * 0.69 ≈ 0.23)
        if val not in (5, 6) or random.random() > 0.69:
            text = random.choice(DICE_REJECT_TEXTS)
            return await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_to_message_id=msg_id)

        char = await get_unique_char(user.id, None)
        if not char:
            return await context.bot.send_message(chat_id=chat_id, text=f"<b><tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji> ʏᴏᴜ ᴡᴏɴ, ʙᴜᴛ ɴᴏ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀs ʟᴇғᴛ ᴛᴏ ᴄʟᴀɪᴍ!</b>", parse_mode="HTML", reply_to_message_id=msg_id)

        await add_char_to_user(user.id, user.username or "", plain_name or "User", char)
        
        # 🔥 Perfect format: Emoji in front of RARITY, Text value behind (Like Screenshot)
        prem_emoji, r_name = get_rarity_details(char.get('rarity', 'common'))
        
        caption = (
            f"<b><tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji> {char.get('name', 'Unknown')} ᴀᴄᴄᴇᴘᴛᴇᴅ ʏᴏᴜʀ ᴍᴀʀʀɪᴀɢᴇ ᴘʀᴏᴘᴏsᴀʟ! <tg-emoji emoji-id=\"5276239041052828276\">🎭</tg-emoji></b>\n\n"
            f"<b><tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji> ɴᴀᴍᴇ: {char.get('name', 'Unknown')}</b>\n"
            f"<b>{prem_emoji} ʀᴀʀɪᴛʏ: {r_name}</b>\n"
            f"<b><tg-emoji emoji-id=\"6314494724266796319\">🟠</tg-emoji> ᴀɴɪᴍᴇ: {char.get('anime', 'Unknown')}</b>\n"
            f"<b><tg-emoji emoji-id=\"6332443074769196273\">🆔</tg-emoji> ɪᴅ: {char.get('id', 'N/A')}</b>"
        )
        
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
        
        # 🔥 Suspenseful pacing (Wait to build excitement)
        await asyncio.sleep(2.0)
        try:
            await msg.edit_caption(caption=random.choice(PROPOSING_LOADING_TEXTS), parse_mode="HTML")
            await asyncio.sleep(2.5) # Extra wait for rejection/acceptance!
        except TelegramError:
            pass
        
        try:
            await msg.delete()
        except TelegramError:
            pass

    except TelegramError as e:
        LOGGER.error(f"Error sending propose image: {e}")
        return

    # 🔥 EXACT 23% WIN CHANCE!
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
    
    # 🔥 Perfect format: Emoji in front of RARITY, Text value behind (Like Screenshot)
    prem_emoji, r_name = get_rarity_details(char.get('rarity', 'common'))
    
    caption = (
        f"<b><tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji> {char.get('name', 'Unknown')} ᴀᴄᴄᴇᴘᴛᴇᴅ ʏᴏᴜʀ ᴘʀᴏᴘᴏsᴀʟ! <tg-emoji emoji-id=\"5276239041052828276\">🎭</tg-emoji></b>\n\n"
        f"<b><tg-emoji emoji-id=\"6336972134962697188\">🌸</tg-emoji> ɴᴀᴍᴇ: {char.get('name', 'Unknown')}</b>\n"
        f"<b>{prem_emoji} ʀᴀʀɪᴛʏ: {r_name}</b>\n"
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

import random
import html
import logging
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tweak imports according to your main file
from shivu import application, user_collection, collection

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
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

COOLDOWN_HOURS = 24

async def swaifu(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        raw_first_name = update.effective_user.first_name or "User"
        safe_first_name = html.escape(to_small_caps(raw_first_name))
        
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        user_data = await user_collection.find_one({'id': user_id})
        
        if user_data and 'last_swaifu_claim' in user_data:
            last_claim = get_safe_time(user_data['last_swaifu_claim'])
            if last_claim and (now - last_claim) < timedelta(hours=COOLDOWN_HOURS):
                msg = f"<b>{to_small_caps('You have already claimed your waifu today! Come back tomorrow.')}</b>"
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
                return

        # Sirf yeh allowed rarities hi aayengi (case-insensitive check ke liye lowercase me)
        allowed_rarities = [
            "celestial", "exclusive", "legendary", 
            "sweet", "special edition", "rare", "common"
        ]

        cursor = collection.find({})
        all_chars = await cursor.to_list(length=None)

        # Filter characters matching only the allowed rarities
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

    except Exception as e:
        logger.error(f"Swaifu Error: {e}", exc_info=True)
        await update.message.reply_text("<b>⚠️ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ! ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.</b>", parse_mode=ParseMode.HTML)


async def daily_claim_coins(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        raw_first_name = update.effective_user.first_name or "User"
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        user_data = await user_collection.find_one({'id': user_id})
        
        if user_data and 'last_coin_claim' in user_data:
            last_claim = get_safe_time(user_data['last_coin_claim'])
            if last_claim and (now - last_claim) < timedelta(hours=COOLDOWN_HOURS):
                msg = f"<b>{to_small_caps('You have already claimed your daily coins! Try again later.')}</b>"
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
        
    except Exception as e:
        logger.error(f"Claim Error: {e}", exc_info=True)
        await update.message.reply_text("<b>⚠️ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ! ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.</b>", parse_mode=ParseMode.HTML)


# Handlers
application.add_handler(CommandHandler("swaifu", swaifu))
application.add_handler(CommandHandler("claim", daily_claim_coins))

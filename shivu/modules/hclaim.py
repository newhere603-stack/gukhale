import random
import html
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
from telegram.constants import ParseMode
import asyncio

# Tweak imports according to your main file
from shivu import application, user_collection, collection

# Small caps converter function
def to_small_caps(text: str) -> str:
    if not text:
        return ""
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    tr = str.maketrans(normal, small)
    return str(text).translate(tr)

COOLDOWN_HOURS = 24

async def swaifu(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    raw_first_name = update.effective_user.first_name or "User"
    # Convert name to small caps first, THEN escape HTML to avoid breaking tags
    safe_first_name = html.escape(to_small_caps(raw_first_name))
    
    # Using timezone-aware UTC time and converting to naive for safe math
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        # Get user data
        user_data = await user_collection.find_one({'id': user_id})
        
        # Cooldown check safely handling timezone info
        if user_data and 'last_swaifu_claim' in user_data:
            last_claim = user_data['last_swaifu_claim']
            if hasattr(last_claim, 'tzinfo') and last_claim.tzinfo:
                last_claim = last_claim.replace(tzinfo=None)
                
            if (now - last_claim) < timedelta(hours=COOLDOWN_HOURS):
                msg = f"<b>{to_small_caps('You have already claimed your waifu today! Come back tomorrow.')}</b>"
                await update.effective_message.reply_text(msg, parse_mode=ParseMode.HTML)
                return

        # Fetch a random character
        pipeline = [{'$sample': {'size': 1}}]
        cursor = collection.aggregate(pipeline)
        result = await cursor.to_list(length=1)

        if not result:
            await update.effective_message.reply_text(f"<b>{to_small_caps('No characters found in database!')}</b>", parse_mode=ParseMode.HTML)
            return

        character = result[0]
        # Format strings into small caps, then html escape them
        char_name = html.escape(to_small_caps(character.get('name', 'Unknown')))
        anime = html.escape(to_small_caps(character.get('anime', 'Unknown')))
        rarity = html.escape(to_small_caps(character.get('rarity', '🟢 MEDIUM')))
        img_url = character.get('img_url', '')

        # Update database
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

        # Format message correctly without breaking HTML syntax
        caption = (
            f"<b>{to_small_caps('Congratulations')} {safe_first_name}! {to_small_caps('You won')}🔥</b>\n"
            f"<b>◈ {to_small_caps('Name')}: {char_name}</b>\n"
            f"<b>◈ {to_small_caps('Rarity')}: {rarity}</b>\n"
            f"<b>◈ {to_small_caps('Anime')}: {anime}</b>"
        )

        # Send image or fallback to text
        if img_url:
            try:
                await update.effective_message.reply_photo(
                    photo=img_url,
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
                return
            except Exception:
                pass # If image send fails, default to text below
        
        await update.effective_message.reply_text(caption, parse_mode=ParseMode.HTML)

    except Exception as e:
        print(f"Swaifu Command Error: {e}")
        await update.effective_message.reply_text(f"<b>{to_small_caps('An error occurred. Please try again later.')}</b>", parse_mode=ParseMode.HTML)


async def daily_claim_coins(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    raw_first_name = update.effective_user.first_name or "User"
    safe_first_name = html.escape(to_small_caps(raw_first_name))
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        # Get user data
        user_data = await user_collection.find_one({'id': user_id})
        
        # Cooldown check safely
        if user_data and 'last_coin_claim' in user_data:
            last_claim = user_data['last_coin_claim']
            if hasattr(last_claim, 'tzinfo') and last_claim.tzinfo:
                last_claim = last_claim.replace(tzinfo=None)
                
            if (now - last_claim) < timedelta(hours=COOLDOWN_HOURS):
                msg = f"<b>{to_small_caps('You have already claimed your daily coins! Try again later.')}</b>"
                await update.effective_message.reply_text(msg, parse_mode=ParseMode.HTML)
                return

        # Generate random coins between 1000 and 10000
        coins_won = random.randint(1000, 10000)

        # Update database
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

        # Premium casual response message in safe HTML & small caps
        msg_text = (
            f"<b>🎉 {to_small_caps('Daily Reward Claimed!')} 🎉</b>\n\n"
            f"<b>✨ {to_small_caps('Hey')} {safe_first_name}, {to_small_caps('your dedication pays off!')} </b>\n"
            f"<b>💸 {to_small_caps('You just received')} {coins_won} {to_small_caps('coins!')} </b>\n\n"
            f"<b>🏦 {to_small_caps('These have been securely added to your vault.')} </b>\n"
            f"<b>🌟 {to_small_caps('Keep coming back daily to grow your empire!')}</b>"
        )

        await update.effective_message.reply_text(msg_text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        print(f"Claim Command Error: {e}")
        await update.effective_message.reply_text(f"<b>{to_small_caps('An error occurred. Please try again later.')}</b>", parse_mode=ParseMode.HTML)


# Adding Handlers (ensure application is correctly configured in shivu)
application.add_handler(CommandHandler("swaifu", swaifu, block=False))
application.add_handler(CommandHandler("claim", daily_claim_coins, block=False))

import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
from telegram.constants import ParseMode
import asyncio

# Tweak imports according to your main file
from shivu import application, user_collection, collection

# Small caps converter function
def to_small_caps(text: str) -> str:
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    tr = str.maketrans(normal, small)
    return text.translate(tr)

COOLDOWN_HOURS = 24

async def swaifu(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    now = datetime.utcnow()

    # Get user data
    user_data = await user_collection.find_one({'id': user_id})
    
    # Cooldown check
    if user_data and 'last_swaifu_claim' in user_data:
        last_claim = user_data['last_swaifu_claim']
        if (now - last_claim) < timedelta(hours=COOLDOWN_HOURS):
            msg = "<b>ʏᴏᴜ ʜᴀᴠᴇ ᴀʟʀᴇᴀᴅʏ ᴄʟᴀɪᴍᴇᴅ ʏᴏᴜʀ ᴡᴀɪғᴜ ᴛᴏᴅᴀʏ! ᴄᴏᴍᴇ ʙᴀᴄᴋ ᴛᴏᴍᴏʀʀᴏᴡ.</b>"
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            return

    # Fetch a random character
    pipeline = [{'$sample': {'size': 1}}]
    cursor = collection.aggregate(pipeline)
    result = await cursor.to_list(length=1)

    if not result:
        await update.message.reply_text("<b>ɴᴏ ᴄʜᴀʀᴀᴄᴛᴇʀs ғᴏᴜɴᴅ ɪɴ ᴅᴀᴛᴀʙᴀsᴇ!</b>", parse_mode=ParseMode.HTML)
        return

    character = result[0]
    char_name = character.get('name', 'Unknown').upper()
    anime = character.get('anime', 'Unknown').upper()
    rarity = character.get('rarity', '🟢 MEDIUM').upper()
    img_url = character.get('img_url', '')

    # Update database
    await user_collection.update_one(
        {'id': user_id},
        {
            '$push': {'characters': character},
            '$set': {
                'last_swaifu_claim': now,
                'first_name': first_name
            }
        },
        upsert=True
    )

    # Format message exactly like the screenshot
    caption = (
        f"<b>{to_small_caps(f'Congratulations {first_name}! You won')}🔥</b>\n"
        f"<b>◈ {to_small_caps('Name')}:</b> <b>{char_name}</b>\n"
        f"<b>◈ {to_small_caps('Rarity')}:</b> {rarity}\n"
        f"<b>◈ {to_small_caps('Anime')}:</b> <b>{anime}</b>"
    )

    try:
        await update.message.reply_photo(
            photo=img_url,
            caption=caption,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        # Fallback if image fails
        await update.message.reply_text(caption, parse_mode=ParseMode.HTML)


async def daily_claim_coins(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    now = datetime.utcnow()

    # Get user data
    user_data = await user_collection.find_one({'id': user_id})
    
    # Cooldown check
    if user_data and 'last_coin_claim' in user_data:
        last_claim = user_data['last_coin_claim']
        if (now - last_claim) < timedelta(hours=COOLDOWN_HOURS):
            msg = "<b>ʏᴏᴜ ʜᴀᴠᴇ ᴀʟʀᴇᴀᴅʏ ᴄʟᴀɪᴍᴇᴅ ʏᴏᴜʀ ᴅᴀɪʟʏ ᴄᴏɪɴs! ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.</b>"
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
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
                'first_name': first_name
            }
        },
        upsert=True
    )

    # Premium casual response message in small caps
    msg_text = (
        f"<b>🎉 {to_small_caps('Daily Reward Claimed!')} 🎉</b>\n\n"
        f"<b>✨ {to_small_caps(f'Hey {first_name}, your dedication pays off!')} </b>\n"
        f"<b>💸 {to_small_caps(f'You just received {coins_won} coins!')} </b>\n\n"
        f"<b>🏦 {to_small_caps('These have been securely added to your vault.')} </b>\n"
        f"<b>🌟 {to_small_caps('Keep coming back daily to grow your empire!')}</b>"
    )

    await update.message.reply_text(msg_text, parse_mode=ParseMode.HTML)


# Adding Handlers
application.add_handler(CommandHandler("swaifu", swaifu, block=False))
application.add_handler(CommandHandler("claim", daily_claim_coins, block=False))

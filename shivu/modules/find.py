import random
import traceback
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

# Yahan main directly tumhare bot ke in-built collections import kar raha hu
from shivu import application, db
# Agar import fail ho to batana
try:
    from shivu import user_collection, collection
except ImportError:
    collection = db['anime_characters_lol']
    user_collection = db['users'] 

OWNER_ID = 7657218453

def to_small_caps(text: str) -> str:
    mapping = {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 
        'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 
        'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 
        's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 
        'y': 'ʏ', 'z': 'ᴢ', 'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 
        'E': 'ᴇ', 'F': 'ꜰ', 'G': 'ɢ', 'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 
        'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ', 
        'Q': 'ǫ', 'R': 'ʀ', 'S': 'ꜱ', 'T': 'ᴛ', 'U': 'ᴜ', 'V': 'ᴠ', 
        'W': 'ᴡ', 'X': 'x', 'Y': 'ʏ', 'Z': 'ᴢ'
    }
    return "".join(mapping.get(c, c) for c in str(text))

def bold_sc(text: str) -> str:
    return f"<b>{to_small_caps(text)}</b>"

async def marketplace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user_id = update.effective_user.id
        print(f"\n--- [MARKETPLACE TEST] ---")
        print(f"1. Command triggered by User ID: {user_id}")
        
        # Checking DB
        user = await user_collection.find_one({'id': user_id})
        if not user:
            print("2. User not found by 'id'. Trying 'user_id'...")
            user = await user_collection.find_one({'user_id': user_id})
            
        if not user:
            print("3. FAILED: User account completely missing in DB.")
            await update.message.reply_text(bold_sc("❌ Please /start the bot first to create an account."), parse_mode='HTML')
            return
            
        print(f"4. SUCCESS: User found. Name: {user.get('first_name', 'Unknown')}")
        
        # Test character fetch
        pipeline = [{"$sample": {"size": 1}}]
        chars = await collection.aggregate(pipeline).to_list(length=1)
        if not chars:
            print("5. FAILED: No characters in anime_characters_lol.")
            await update.message.reply_text("No characters in DB.")
            return
            
        char = chars[0]
        print(f"6. SUCCESS: Character fetched: {char.get('name')}")
        
        caption = f"🏪 {bold_sc('TEST MARKETPLACE')}\n{bold_sc('NAME:')} {bold_sc(str(char.get('name')))}\n{bold_sc('STATUS:')} {bold_sc('WORKING!')}"
        buttons = [[InlineKeyboardButton(to_small_caps("Buy Test"), callback_data="mp_test")]]
        
        if char.get('img_url'):
            await update.message.reply_photo(photo=char['img_url'], caption=caption, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')
        else:
            await update.message.reply_text(text=caption, reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')
            
        print("7. Message sent successfully.\n")

    except Exception as e:
        print(f"CRITICAL ERROR in marketplace command:\n{traceback.format_exc()}")
        await update.message.reply_text(f"Error: {e}")

async def mp_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    print(f"Button Clicked! Data: {query.data}")
    await query.answer("Button Click is Working!", show_alert=True)

application.add_handler(CommandHandler(['mp', 'marketplace'], marketplace))
application.add_handler(CallbackQueryHandler(mp_callback, pattern="^mp_"))

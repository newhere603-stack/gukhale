from dataclasses import dataclass
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.error import TelegramError
import html

# 🔥 NAYA IMPORT: Database transfer karne ke liye AsyncIOMotorClient
from motor.motor_asyncio import AsyncIOMotorClient

from shivu import db, user_collection, application
from shivu.modules.database.sudo import is_user_sudo

# 🔥 FIX: check module se clear_char_cache import kiya taaki /give ke baad cache turant clear ho jaye
try:
    from shivu.modules.check import clear_char_cache
except ImportError:
    def clear_char_cache(cid): pass

# Asli characters wali collection yahan explicitly set kar di hai
collection = db['anime_characters_lol']

# --- CONFIGURATION ---
LOG_GROUP_ID = -1003893927065 
OWNER_ID = 7657218453  
# ---------------------

RARITY_MAP = {
    "common": ("🟢", '<tg-emoji emoji-id="6093722470265658964">🟢</tg-emoji>', "Common"), 
    "rare": ("🟠", '<tg-emoji emoji-id="5339390195768774311">🟠</tg-emoji>', "Rare"), 
    "legendary": ("🟡", '<tg-emoji emoji-id="6084550327086883643">🔥</tg-emoji>', "Legendary"),
    "special": ("🔵", '<tg-emoji emoji-id="5393592081748877575">🔵</tg-emoji>', "Medium"), 
    "erotic": ("🥵", '<tg-emoji emoji-id="6093490292923574796">❤️‍🔥</tg-emoji>', "Spicy"),
    "celestial": ("🪽", '<tg-emoji emoji-id="5434121252874756456">🕊</tg-emoji>', "Celestial"), 
    "exclusive": ("💮", '<tg-emoji emoji-id="5262772355779809182">💮</tg-emoji>', "Exclusive"), 
    "premium": ("🔮", '<tg-emoji emoji-id="6093919703753831564">🔮</tg-emoji>', "Premium Edition"), 
    "mythic": ("💎", '<tg-emoji emoji-id="5471952986970267163">💎</tg-emoji>', "Mythic"),
    "sweet": ("🍭", '<tg-emoji emoji-id="6222115531122546353">🍭</tg-emoji>', "Sweet"), 
    "valentine": ("💞", '<tg-emoji emoji-id="5255861796350224063">❤️</tg-emoji>', "Valentine"), 
    "winter": ("❄️", '<tg-emoji emoji-id="5431895003821513760">❄️</tg-emoji>', "Winter"),
    "neon": ("⚡", '<tg-emoji emoji-id="6093708348413189642">⚡️</tg-emoji>', "Neon"), 
    "pearl": ("🏖️", '<tg-emoji emoji-id="5433645645376264953">🏖</tg-emoji>', "Summer"), 
    "cosmic": ("🌌", '<tg-emoji emoji-id="5431783411981228752">🎆</tg-emoji>', "Cosmic"),
}

def to_small_caps(text: str) -> str:
    if not text:
        return "ᴜɴᴋɴᴏᴡɴ"
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    tr = str.maketrans(normal, small)
    return str(text).translate(tr)

def get_rarity_display(rarity_raw: str) -> str:
    if not rarity_raw:
        return f"<b>{to_small_caps('Unknown')}</b>"
    raw_str = str(rarity_raw).lower().strip()
    for key, (_, premium_emoji, display_name) in RARITY_MAP.items():
        if key in raw_str or display_name.lower() in raw_str:
            return f"{premium_emoji} <b>{to_small_caps(display_name)}</b>"
    return f"<b>{to_small_caps(str(rarity_raw))}</b>"

@dataclass
class CharacterGiftResult:
    img_url: str
    caption: str
    char_name: str
    char_id: str

async def send_character_media(msg, media_url: str, caption: str):
    url_lower = media_url.lower()
    if url_lower.endswith(('.mp4', '.webm', '.mov', '.mkv')):
        await msg.reply_video(video=media_url, caption=caption, parse_mode=ParseMode.HTML)
    elif url_lower.endswith('.gif'):
        await msg.reply_animation(animation=media_url, caption=caption, parse_mode=ParseMode.HTML)
    else:
        try:
            await msg.reply_photo(photo=media_url, caption=caption, parse_mode=ParseMode.HTML)
        except TelegramError:
            await msg.reply_video(video=media_url, caption=caption, parse_mode=ParseMode.HTML)

async def give_character(receiver_id: int, character_id: str) -> CharacterGiftResult:
    search_ids = [str(character_id)]
    if str(character_id).isdigit():
        search_ids.append(int(character_id))

    character = await collection.find_one({'id': {'$in': search_ids}})
    if not character:
        raise ValueError("Character ID database mein nahi mila.")
    
    await user_collection.update_one(
        {'id': receiver_id},
        {'$push': {'characters': character}}
    )
    
    # 🔥 Instant Cache Invalidation: Jaise hi character mile, cache clear karo
    clear_char_cache(str(character['id']))
    
    char_name = html.escape(character['name'])
    small_name = to_small_caps(char_name)
    rarity_formatted = get_rarity_display(character.get('rarity', 'common'))
    
    caption = (
        f"<b><tg-emoji emoji-id=\"5199749070830197566\">🎁</tg-emoji> {to_small_caps('Character Successfully Given!')}</b>\n\n"
        f"<b><tg-emoji emoji-id=\"6104892988712820269\">👤</tg-emoji> {to_small_caps('Receiver ID')}:</b> <code>{receiver_id}</code>\n"
        f"<b><tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> {to_small_caps('Name')}:</b> <b>{small_name}</b>\n"
        f"<b><tg-emoji emoji-id=\"5256131095094652290\">🎯</tg-emoji> {to_small_caps('Rarity')}:</b> {rarity_formatted}\n"
        f"<b><tg-emoji emoji-id=\"6332443074769196273\">🆔</tg-emoji> {to_small_caps('ID')}:</b> <code>{character['id']}</code>"
    )
    
    return CharacterGiftResult(character['img_url'], caption, character['name'], str(character['id']))

async def give_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id
    
    if user_id != OWNER_ID and not await is_user_sudo(user_id):
        return
    
    if not msg.reply_to_message:
        await msg.reply_text(
            f"<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> {to_small_caps('Reply to a user to give a character.')}</b>", 
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        if not context.args:
            await msg.reply_text(
                f"<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> {to_small_caps('ID Missing! Usage:')} <code>/give [id]</code></b>", 
                parse_mode=ParseMode.HTML
            )
            return

        character_id = context.args[0]
        receiver_id = msg.reply_to_message.from_user.id
        
        result = await give_character(receiver_id, character_id)
        await send_character_media(msg, result.img_url, result.caption)
        
        executor_name = html.escape(to_small_caps(msg.from_user.first_name))
        receiver_name = html.escape(to_small_caps(msg.reply_to_message.from_user.first_name))
        
        log_text = (
            f"<b><tg-emoji emoji-id=\"5422439311196834318\">💡</tg-emoji> #{to_small_caps('GIVE_LOG')}</b>\n\n"
            f"<b>{to_small_caps('Authorized By')}:</b> <b>{executor_name}</b> (<code>{user_id}</code>)\n"
            f"<b>{to_small_caps('Gave To')}:</b> <b>{receiver_name}</b> (<code>{receiver_id}</code>)\n"
            f"<b>{to_small_caps('Character')}:</b> <b>{html.escape(to_small_caps(result.char_name))}</b> (<code>{result.char_id}</code>)\n"
            f"<b>{to_small_caps('Status')}:</b> <b>{to_small_caps('Success')}</b> <tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji>"
        )
        
        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_text, parse_mode=ParseMode.HTML)

    except ValueError as e:
        await msg.reply_text(
            f"<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> <b>{to_small_caps(str(e))}</b></b>", 
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await msg.reply_text(
            f"<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> {to_small_caps('Error')}: <code>{html.escape(str(e))}</code></b>", 
            parse_mode=ParseMode.HTML
        )

# 🔥 YAHAN TERA NAYA TRANSFER DB COMMAND HAI
async def transfer_db_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sirf OWNER_ID use kar sakta hai
    if update.effective_user.id != OWNER_ID:
        return

    if not context.args:
        await update.message.reply_text("<b>⚠️ Naya URL nahi diya!</b>\nUsage: <code>/transferdb [NAYA_MONGO_URL]</code>", parse_mode=ParseMode.HTML)
        return

    new_mongo_url = context.args[0]
    msg = await update.message.reply_text("⏳ <b>Database transfer started in background...</b>\n<i>Fetching characters from old DB...</i>", parse_mode=ParseMode.HTML)

    try:
        # Purane characters fetch karo
        all_chars = await collection.find({}).to_list(length=None)
        total_chars = len(all_chars)

        if total_chars == 0:
            await msg.edit_text("❌ <b>Purane database mein koi characters nahi hain!</b>", parse_mode=ParseMode.HTML)
            return

        await msg.edit_text(f"📦 <b>{total_chars} characters found!</b>\n<i>Connecting to new Database & transferring...</i>", parse_mode=ParseMode.HTML)

        # Naya database connect karo
        new_client = AsyncIOMotorClient(new_mongo_url)
        new_db = new_client["GRABBING_YOUR_WAIFU"] # Tumhare database ka naam
        new_col = new_db["anime_characters_lol"]

        # Pehle naya collection clear karo taaki duplicate ID error na aaye
        await new_col.delete_many({})
        
        # Ek sath sara data naye DB mein daal do!
        await new_col.insert_many(all_chars)

        await msg.edit_text(f"✅ <b>BINGO! {total_chars} characters successfully naye MongoDB mein transfer ho gaye!</b> 🎉", parse_mode=ParseMode.HTML)

    except Exception as e:
        await msg.edit_text(f"❌ <b>Transfer Failed:</b> <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)

application.add_handler(CommandHandler("give", give_cmd, block=False))
application.add_handler(CommandHandler("transferdb", transfer_db_cmd, block=False))

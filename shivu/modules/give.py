from dataclasses import dataclass
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.constants import ParseMode
import html

from shivu import collection, user_collection, application
from shivu.modules.database.sudo import is_user_sudo

# --- CONFIGURATION ---
LOG_GROUP_ID = -1003893927065 
OWNER_ID = 7657218453  # <--- Sirf ye ID aur Sudo users command use kar payenge
# ---------------------

def to_small_caps(text: str) -> str:
    if not text:
        return "ᴜɴᴋɴᴏᴡɴ"
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    tr = str.maketrans(normal, small)
    return str(text).translate(tr)

@dataclass
class CharacterGiftResult:
    img_url: str
    caption: str
    char_name: str
    char_id: str

async def give_character(receiver_id: int, character_id: str) -> CharacterGiftResult:
    character = await collection.find_one({'id': character_id})
    if not character:
        raise ValueError(to_small_caps("Character ID database mein nahi mila."))
    
    await user_collection.update_one(
        {'id': receiver_id},
        {'$push': {'characters': character}}
    )
    
    char_name = html.escape(character['name'])
    small_name = to_small_caps(char_name)
    rarity = character['rarity']
    
    caption = (
        f"<b><tg-emoji emoji-id=\"5199749070830197566\">🎁</tg-emoji> {to_small_caps('Character Successfully Given!')}</b>\n\n"
        f"<b><tg-emoji emoji-id=\"6104892988712820269\">👤</tg-emoji> {to_small_caps('Receiver ID')}:</b> <code>{receiver_id}</code>\n"
        f"<b><tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> {to_small_caps('Name')}:</b> {small_name}\n"
        f"<b><tg-emoji emoji-id=\"5256131095094652290\">🎯</tg-emoji> {to_small_caps('Rarity')}:</b> {rarity}\n"
        f"<b><tg-emoji emoji-id=\"6332443074769196273\">🆔</tg-emoji> {to_small_caps('ID')}:</b> <code>{character['id']}</code>"
    )
    
    return CharacterGiftResult(character['img_url'], caption, character['name'], character['id'])

async def give_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id
    
    # --- OWNER & SUDO CHECK (SILENT FAIL) ---
    # Agar user Owner nahi hai aur Sudo bhi nahi hai, toh bina kuch bole return ho jayega
    if user_id != OWNER_ID and not await is_user_sudo(user_id):
        return
    
    if not msg.reply_to_message:
        await msg.reply_text(f"<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> {to_small_caps('Reply to a user to give a character.')}</b>", parse_mode=ParseMode.HTML)
        return
    
    try:
        if not context.args:
            await msg.reply_text(f"<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> {to_small_caps('ID missing! Usage:')} <code>/give [id]</code></b>", parse_mode=ParseMode.HTML)
            return

        character_id = context.args[0]
        receiver_id = msg.reply_to_message.from_user.id
        
        result = await give_character(receiver_id, character_id)
        
        await msg.reply_photo(
            photo=result.img_url, 
            caption=result.caption, 
            parse_mode=ParseMode.HTML
        )
        
        # --- LOG TO GROUP ---
        executor_name = html.escape(to_small_caps(msg.from_user.first_name))
        receiver_name = html.escape(to_small_caps(msg.reply_to_message.from_user.first_name))
        
        log_text = (
            f"<b><tg-emoji emoji-id=\"5422439311196834318\">💡</tg-emoji> #GIVE_LOG</b>\n\n"
            f"<b>{to_small_caps('Authorized By')}:</b> {executor_name} (<code>{user_id}</code>)\n"
            f"<b>{to_small_caps('Gave To')}:</b> {receiver_name} (<code>{receiver_id}</code>)\n"
            f"<b>{to_small_caps('Character')}:</b> {html.escape(to_small_caps(result.char_name))} (<code>{result.char_id}</code>)\n"
            f"<b>{to_small_caps('Status')}:</b> {to_small_caps('Success')} <tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji>"
        )
        
        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_text, parse_mode=ParseMode.HTML)

    except ValueError as e:
        await msg.reply_text(f"<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> {str(e)}</b>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.reply_text(f"<b><tg-emoji emoji-id=\"6093383288108360854\">❌</tg-emoji> {to_small_caps('Error')}:</b> <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)

# Registration
application.add_handler(CommandHandler("give", give_cmd, block=False))

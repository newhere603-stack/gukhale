import logging
import asyncio
import re
import random
from telegram import Update
from telegram.ext import MessageHandler, CommandHandler, filters, ContextTypes
from shivu import application, user_collection

LOGGER = logging.getLogger(__name__)

WAIFU_CHAT_ENABLED = {}

# ==========================================
# UNLIMITED DYNAMIC SENTENCE BUILDER (Zero API Needed)
# ==========================================
TSUNDERE_PREFIXES = [
    "Hmph!", "B-Baka,", "Arey suno,", "Pagal ho kya?", 
    "Achaaa,", "Waise,", "Oye aalu,", "Itne sawal kyu puchte ho,"
]

CORE_RESPONSES = [
    "mujhe ye sab mat batao", "tumse zyada vella koi nahi hai", 
    "apne nakhre apne paas rakho", "dimag mat khao mera", 
    "soch rahi hu tumhe ignore kar du", "thoda sudhar jao",
    "yeh koi poochne wali baat hai kya", "mujhe kyu pareshan kar rahe ho"
]

CARING_TWISTS = [
    "par suno, apna dhyan rakhna", "waise ho toh tum acche", 
    "chalo maaf kiya tumhe", "khana khaya ya nahi?", 
    "mazak kar rahi thi waise", "aur batao kya chal raha hai"
]

EMOTIONS = ["HAPPY", "SAD", "ANGRY", "BLUSH", "LAUGH", "FLIRT"]

def generate_unlimited_response(text):
    prefix = random.choice(TSUNDERE_PREFIXES)
    core = random.choice(CORE_RESPONSES)
    twist = random.choice(CARING_TWISTS)
    emotion = random.choice(EMOTIONS)
    
    reply = f"{prefix} {core}, par {twist}"
    return reply, emotion

# ==========================================
# STICKER MEDIA POOL
# ==========================================
EMOTION_MEDIA = {
    "HAPPY": [
        "CAACAgUAAxkBAAFR3fNqgBF4PRADJszY3nNrQQoR2sD6qwACAiEAAhwwsVdASn_j-vrqtz0E",
        "CAACAgUAAxkBAAFR3e9qgBFSjkEp_DqBKKAeRJ66piFGjwACmw8AAkn9QFVLHCg1uJAT_j0E",
        "CAACAgUAAxkBAAFR3flqgBHHYP3V2Em2e79sRPyzbuDQIgACjRgAAhahKFWo1Eb60j7KED0E",
        "CAACAgUAAxkBAAFR3ftqgBHTDPhMyLY4vyipafLLeanpFAACqx4AAs8zmFZStDnqOKdFuj0E",
        "CAACAgUAAxkBAAFR3f1qgBHWDRNzfecf0eWs7qwPIIgo1gAC9x4AAo5b4FaPCtbinZpqZD0E",
        "CAACAgUAAxkBAAFR3gFqgBHyYv_a24w1uHuDtKPX8jrNNQAC1yAAAu3i4FaZetf0GSUcfD0E",
        "CAACAgUAAxkBAAFR3gNqgBH3KJb2EY7PhetTiTQSdZs5nwACIiEAAni3YFV75Q2ZCEYyhj0E",
        "CAACAgUAAxkBAAFR3gdqgBID_SkTRU5mf-B4wVXenmjt1QACoCYAAgKlmVT1T9TdkHR3VD0E",
        "CAACAgUAAxkBAAFR3glqgBIFkAtfpoy36MRI6776yrUEPwACOB4AAkR7YVajFSy53E86qz0E",
        "CAACAgUAAxkBAAFR3gtqgBILhNezmyWSfm6NjySXl-NZ9AACjRYAAhJJkVWM1rFooL_RMT0E",
        "CAACAgUAAxkBAAFR3g1qgBIPXhUiQSFaE2xFbTu7AiQdlAACAh4AApw-wVX2mePmM7UE3D0E",
        "CAACAgUAAxkBAAFR3g9qgBIS1T1g9d85idyUs90T2hpI1QACxR8AAqUxGVVwUaNkqQ-9mz0E",
        "CAACAgUAAxkBAAFR3hFqgBIZl8O67TSiCQe4OIJz3t3keAACERoAAr1QeVbFlbbjEywZKj0E",
        "CAACAgUAAxkBAAFR3hVqgBIvSkd0Pe5dpd_SacVvAZMjOwACmRgAAo0RgVa6xF1Ctm59gT0E",
        "CAACAgUAAxkBAAFR3hlqgBI8mSvH9K4eOU4Qj7y-pEQRigACyhgAAmO6EFUgbWsg-1F2Tj0E"
    ],
    "SAD": [
        "CAACAgUAAxkBAAFR3hNqgBIn4b9iZNiFHx4cB10tqRI7NgACOxcAAjV2qFThhaZ9Pm0Myj0E",
        "CAACAgUAAxkBAAFR3iFqgBNuVf4c8hAUW8kKeVXTcGHqAwAC9xsAAvn1SFXgplE-lZdNcj0E",
        "CAACAgUAAxkBAAFR3i1qgBPayyTEc6cFhtqc94SVMMbx1AACiCcAAsyO2VTWyfLCKjr7nD0E"
    ],
    "ANGRY": [
        "CAACAgUAAxkBAAFR3iVqgBO3JC6-oOEUWVM-AmMfloIIjgACAhoAAjqT2VXEvUSG1hjGHj0E",
        "CAACAgUAAxkBAAFR3i9qgBPsx-5fBwufuVgBUlDK_ec4QAACtRAAArI-QFazW1M8z7SWSj0E"
    ],
    "BLUSH": [
        "CAACAgUAAxkBAAFR3jRqgBQf6SJcoFrMUtEB9OM5HCaUpAACoRYAAuqt0VRbqNEszdX3Ej0E",
        "CAACAgUAAxkBAAFR3jZqgBQ007MeN_OWyzW13Mn9rOtKwgACNxgAAisSSVXDmdjUzngLRT0E"
    ],
    "FLIRT": [
        "CAACAgUAAxkBAAFR3hdqgBI2k4bZE6tzwY7zVfiF-tw6fwACXhYAAqgp6FZJs89vgZurvj0E"
    ],
    "LAUGH": [
        "CAACAgUAAxkBAAFR3jtqgBSSa_HpuYq-P7Aiys7efYCmowACIhUAAg10eFcdJmcN6Z9L_z0E"
    ]
}

# ==========================================
# 3. ADMIN & TOGGLE
# ==========================================
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat, user = update.effective_chat, update.effective_user
    if not chat or not user: return False
    if chat.type == "private": return True
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ["creator", "administrator"]
    except Exception: return False

async def toggle_waifu_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message: return
    if not await is_admin(update, context):
        await update.message.reply_text("Only group admins can enable or disable the Waifu ChatBot.")
        return
    chat_id = update.effective_chat.id
    WAIFU_CHAT_ENABLED[chat_id] = not WAIFU_CHAT_ENABLED.get(chat_id, True)
    status_text = "ENABLED" if WAIFU_CHAT_ENABLED[chat_id] else "DISABLED"
    await update.message.reply_text(f"Waifu ChatBot is now: {status_text}")

# ==========================================
# 4. MAIN CHAT HANDLER (Strict Reply-Only Filter)
# ==========================================
async def waifu_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    chat, user = update.effective_chat, update.effective_user
    if not chat or not user: return
    chat_id = chat.id

    if not WAIFU_CHAT_ENABLED.get(chat_id, True): return

    # STEN / STRICT CONDITION CHECK:
    # In groups/supergroups, bot will ONLY respond if the message is an explicit direct reply to the bot's message.
    if chat.type in ["group", "supergroup"]:
        is_reply_to_bot = False
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            is_reply_to_bot = update.message.reply_to_message.from_user.id == context.bot.id
        
        # If it's not a direct reply to the bot, completely ignore it.
        if not is_reply_to_bot:
            return

    # Extract text content if available
    text = "Sticker"
    if update.message.text:
        text = update.message.text.strip()
    elif update.message.animation:
        text = "GIF"

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(0.4)
    except Exception: pass

    try:
        _, emotion = generate_unlimited_response(text)

        # Send ONLY sticker/media response as a reply, with no text output
        if emotion in EMOTION_MEDIA and EMOTION_MEDIA[emotion]:
            sticker_id = random.choice(EMOTION_MEDIA[emotion])
            await update.message.reply_sticker(sticker=sticker_id)

    except Exception as e:
        LOGGER.exception(f"Waifu Chat Error: {e}")

# ==========================================
# 5. REGISTER HANDLERS
# ==========================================
application.add_handler(CommandHandler("togglechat", toggle_waifu_chat_handler, block=False))
application.add_handler(MessageHandler((filters.TEXT | filters.Sticker.ALL | filters.ANIMATION) & ~filters.COMMAND, waifu_chat_handler, block=False), group=2)

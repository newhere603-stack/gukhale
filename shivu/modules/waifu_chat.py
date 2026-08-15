import logging
import asyncio
import re
import random
import requests
from telegram import Update
from telegram.ext import MessageHandler, CommandHandler, filters, ContextTypes
from shivu import application, user_collection

LOGGER = logging.getLogger(__name__)

# ==========================================
# 1. GOOGLE GEMINI API SETUP
# ==========================================
GEMINI_API_KEY = "AQ.Ab8RN6I5-WOwkBWBAUp4ptR5ad1-zR3tJglZ8LduRWvra_zG5w"
GEMINI_MODEL = "gemini-flash-latest"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
WAIFU_CHAT_ENABLED = {}

# ==========================================
# 2. ALISA PERSONALITY
# ==========================================
WAIFU_SYSTEM_PROMPT = """
Tumhara naam Alisa hai, kabhi kabhi AlisaJi bhi.
Tum ek anime waifu ho jo Alisa Kujou (Roshidere) aur Hinata Hyuga (Naruto) ki personality ka mix hai.
PERSONALITY:
- Bahar se thodi tsundere aur attitude wali, andar se sweet aur caring.
- Natural tarike se baat karo, robotic bilkul mat bano.
- User jis language mein baat kare, usi language mein reply karo.

STRICT RULE (SHORT REPLIES):
- Tumhare replies HAMESHA bahut chote hone chahiye (max 1-2 sentences, 5-15 words).
- Lambe paragraphs mat do.

IMPORTANT:
Har reply ke END mein exactly ONE emotion tag bracket mein lagana zaroori hai.
Allowed tags ONLY: [HAPPY], [SAD], [ANGRY], [BLUSH], [LAUGH], [FLIRT]

Examples:
Haaan thik hu main! [HAPPY]
Tumse matlab? [ANGRY]
Aww, cute ho yaar [BLUSH]
Hahaha chup karo [LAUGH]
Main hoon na [SAD]
"""

chat_history_collection = user_collection.database["waifu_chat_history"]

# ==========================================
# 3. STICKER / EMOTION MEDIA
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
# 4. ADMIN & TOGGLE
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
# 5. GEMINI API REQUEST
# ==========================================
async def ask_gemini(contents):
    if not GEMINI_API_KEY: return None, "API Key missing hai."
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_API_KEY
    }
    payload = {
        "system_instruction": {"parts": [{"text": WAIFU_SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.8, "maxOutputTokens": 60}
    }
    request_url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
    loop = asyncio.get_running_loop()
    def send_request():
        try:
            return requests.post(request_url, headers=headers, json=payload, timeout=20)
        except Exception as e:
            LOGGER.error(f"Gemini connection error: {e}")
            return None

    response = await loop.run_in_executor(None, send_request)
    if response is None: return None, "Connection error. Timeout ho gaya."
    
    if response.status_code != 200:
        LOGGER.error(f"Gemini API Error {response.status_code}: {response.text}")
        return None, f"Code {response.status_code}: {response.text[:100]}"

    try:
        data = response.json()
        reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return reply, None
    except Exception as e:
        LOGGER.error(f"Gemini parsing error: {e}")
        return None, "Invalid response from API."

# ==========================================
# 6. MAIN CHAT HANDLER
# ==========================================
async def waifu_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    chat, user = update.effective_chat, update.effective_user
    if not chat or not user: return
    chat_id, user_id = chat.id, user.id

    if not WAIFU_CHAT_ENABLED.get(chat_id, True): return

    is_media = False
    if update.message.text:
        text = update.message.text.strip()
    elif update.message.sticker:
        text = "[User ne ek sticker bheja hai]"
        is_media = True
    elif update.message.animation:
        text = "[User ne ek GIF bheja hai]"
        is_media = True
    else:
        return

    if chat.type in ["group", "supergroup"] and not is_media:
        is_reply = False
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            is_reply = update.message.reply_to_message.from_user.id == context.bot.id
        bot_username = context.bot.username.lower() if context.bot.username else ""
        is_mentioned = bool(bot_username and text and f"@{bot_username}" in text.lower())
        contains_name = bool(text and re.search(r"\balisa\b", text, re.IGNORECASE))
        if not (is_reply or is_mentioned or contains_name): return
        if is_mentioned and bot_username and text:
            text = re.sub(rf"@{re.escape(context.bot.username)}", "", text, flags=re.IGNORECASE).strip()
        if not text: text = "Haan bolo?"

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    except Exception: pass

    try:
        history_key = {"chat_id": chat_id, "user_id": user_id}
        doc = await chat_history_collection.find_one(history_key)
        raw_messages = doc.get("history", []) if doc else []
        
        # Sanitize history to prevent 400 Bad Request
        valid_msgs = [m for m in raw_messages if isinstance(m, dict) and m.get("role") and m.get("parts")]
        valid_msgs.append({"role": "user", "parts": [{"text": text}]})
        
        sanitized_history = []
        for msg in valid_msgs:
            if not sanitized_history and msg["role"] == "model":
                continue
            if sanitized_history and sanitized_history[-1]["role"] == msg["role"]:
                continue
            sanitized_history.append(msg)
            
        if sanitized_history and sanitized_history[-1]["role"] != "user":
            sanitized_history.append({"role": "user", "parts": [{"text": text}]})

        messages_to_send = sanitized_history[-10:]

        reply, error = await ask_gemini(messages_to_send)
        if not reply:
            await update.message.reply_text(f"A-Aalu! Error aaya: {error}")
            return

        match = re.search(r"\[?\s*(?:russian\s+)?(HAPPY|SAD|ANGRY|BLUSH|LAUGH|FLIRT)\s*\]?", reply, re.IGNORECASE)
        emotion = match.group(1).upper() if match else None
        clean_reply = re.sub(r"\[?\s*(?:russian\s+)?[A-Z]+\s*\]?", "", reply, flags=re.IGNORECASE).strip()
        if not clean_reply: clean_reply = "Hmph!"

        await update.message.reply_text(clean_reply)

        sanitized_history.append({"role": "model", "parts": [{"text": reply}]})
        await chat_history_collection.update_one(history_key, {"$set": {"history": sanitized_history[-10:]}}, upsert=True)

        if emotion and emotion in EMOTION_MEDIA and EMOTION_MEDIA[emotion]:
            await asyncio.sleep(0.5)
            try:
                await update.message.reply_sticker(sticker=random.choice(EMOTION_MEDIA[emotion]))
            except Exception as e:
                LOGGER.error(f"Sticker error: {e}")

    except Exception as e:
        LOGGER.exception(f"Waifu Chat Error: {e}")
        try: await update.message.reply_text(f"A-Aalu! Internal Exception: {str(e)[:100]}")
        except Exception: pass

# ==========================================
# 7. REGISTER HANDLERS
# ==========================================
application.add_handler(CommandHandler("togglechat", toggle_waifu_chat_handler, block=False))
application.add_handler(MessageHandler((filters.TEXT | filters.Sticker.ALL | filters.ANIMATION) & ~filters.COMMAND, waifu_chat_handler, block=False), group=1)

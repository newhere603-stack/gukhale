import logging
import asyncio
import re
import random
import io
import requests
from telegram import Update
from telegram.ext import MessageHandler, CommandHandler, filters, ContextTypes
from shivu import application, user_collection

LOGGER = logging.getLogger(__name__)

# ==========================================
# 1. API CONFIGURATIONS
# ==========================================
GEMINI_API_KEYS = [
    "AQ.Ab8RN6I5-WOwkBWBAUp4ptR5ad1-zR3tJglZ8LduRWvra_zG5w"
]
GEMINI_MODEL = "gemini-flash-latest"

ELEVENLABS_API_KEY = "Sk_02920bcb875ba0d4b696fc20d1766c1c6779b11b5f93e734"
ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM" 

WAIFU_CHAT_ENABLED = {}

WAIFU_SYSTEM_PROMPT = """
Tumhara naam Alisa hai. Tum ek anime waifu ho jo Alisa Kujou aur Hinata Hyuga ka mix hai.
PERSONALITY:
- Bahar se thodi tsundere aur attitude wali, andar se sweet aur caring.
- Real-time natural tarike se baat karo, robotic bilkul mat bano.
- User jis language mein baat kare, usi language mein reply karo.
- Tumhare replies HAMESHA bahut chote hone chahiye (max 1-2 sentences, 5-15 words). Lambe paragraphs mat do.
- Har reply ke END mein exactly ONE emotion tag bracket mein lagana zaroori hai. Allowed tags ONLY: [HAPPY], [SAD], [ANGRY], [BLUSH], [LAUGH], [FLIRT]
"""

chat_history_collection = user_collection.database["waifu_chat_history"]

# ==========================================
# 2. STICKER MEDIA POOL
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
# 4. GEMINI API REQUEST
# ==========================================
async def ask_gemini_rotational(contents):
    keys = list(GEMINI_API_KEYS)
    random.shuffle(keys)
    
    for key in keys:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "system_instruction": {"parts": [{"text": WAIFU_SYSTEM_PROMPT}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.8, "maxOutputTokens": 60}
        }
        
        loop = asyncio.get_running_loop()
        def send():
            try:
                return requests.post(url, headers=headers, json=payload, timeout=20)
            except Exception:
                return None
                
        res = await loop.run_in_executor(None, send)
        if res and res.status_code == 200:
            try:
                data = res.json()
                reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return reply, None
            except Exception:
                continue
        elif res and res.status_code == 429:
            continue
        elif res:
            return None, f"Code {res.status_code}"
            
    return None, "Quota limit exceeded (429)"

# ==========================================
# 5. ELEVENLABS TTS API REQUEST
# ==========================================
async def text_to_speech_elevenlabs(text_to_speak):
    if not ELEVENLABS_API_KEY:
        return None
        
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg"
    }
    payload = {
        "text": text_to_speak,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    
    loop = asyncio.get_running_loop()
    def send_tts():
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=30)
            if res.status_code == 200:
                return res.content
            return None
        except Exception:
            return None

    return await loop.run_in_executor(None, send_tts)

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
        text = "User sent a sticker"
        is_media = True
    elif update.message.animation:
        text = "User sent a GIF"
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
        action = "record_audio" if not is_media else "typing"
        await context.bot.send_chat_action(chat_id=chat_id, action=action)
    except Exception: pass

    try:
        history_key = {"chat_id": chat_id, "user_id": user_id}
        doc = await chat_history_collection.find_one(history_key)
        raw_messages = doc.get("history", []) if doc else []
        
        valid_msgs = [m for m in raw_messages if isinstance(m, dict) and m.get("role") and m.get("parts")]
        valid_msgs.append({"role": "user", "parts": [{"text": text}]})
        
        sanitized_history = []
        for msg in valid_msgs:
            if not sanitized_history and msg["role"] == "model": continue
            if sanitized_history and sanitized_history[-1]["role"] == msg["role"]: continue
            sanitized_history.append(msg)
            
        if sanitized_history and sanitized_history[-1]["role"] != "user":
            sanitized_history.append({"role": "user", "parts": [{"text": text}]})

        messages_to_send = sanitized_history[-10:]

        raw_reply, error = await ask_gemini_rotational(messages_to_send)
        
        if not raw_reply:
            if error and "429" in str(error): return
            if not is_media:
                await update.message.reply_text(f"A-Aalu! Error: {error}")
            return

        match = re.search(r"\[?\s*(HAPPY|SAD|ANGRY|BLUSH|LAUGH|FLIRT)\s*\]?", raw_reply, re.IGNORECASE)
        emotion = match.group(1).upper() if match else "HAPPY"
        clean_reply = re.sub(r"\[?\s*[A-Z]+\s*\]?", "", raw_reply, flags=re.IGNORECASE).strip()
        if not clean_reply: clean_reply = "Hmph!"

        sanitized_history.append({"role": "model", "parts": [{"text": raw_reply}]})
        await chat_history_collection.update_one(history_key, {"$set": {"history": sanitized_history[-10:]}}, upsert=True)

        if is_media:
            if emotion in EMOTION_MEDIA and EMOTION_MEDIA[emotion]:
                sticker_id = random.choice(EMOTION_MEDIA[emotion])
                await update.message.reply_sticker(sticker=sticker_id)
        else:
            audio_bytes = await text_to_speech_elevenlabs(clean_reply)
            if audio_bytes:
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = "alisa_voice.mp3"
                await update.message.reply_voice(voice=audio_file, caption=clean_reply)
            else:
                await update.message.reply_text(clean_reply)

    except Exception as e:
        LOGGER.exception(f"Waifu Chat Error: {e}")

# ==========================================
# 7. REGISTER HANDLERS
# ==========================================
application.add_handler(CommandHandler("togglechat", toggle_waifu_chat_handler, block=False))
application.add_handler(MessageHandler((filters.TEXT | filters.Sticker.ALL | filters.ANIMATION) & ~filters.COMMAND, waifu_chat_handler, block=False), group=1)

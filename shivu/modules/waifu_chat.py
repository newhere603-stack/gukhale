import logging
import asyncio
import re
import random
import google.generativeai as genai
from telegram import Update
from telegram.ext import MessageHandler, filters, ContextTypes
from shivu import application, db, BOT_USERNAME

LOGGER = logging.getLogger(__name__)

# ==========================================
# 1. API KEY SETUP
# ==========================================
GEMINI_API_KEY = "AQ.Ab8RN6Ime4vM1dj_j6eSnlW02qsAeu..." # Yahan apni API Key daal dena
genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# 2. ADVANCED WAIFU PROMPT (Multilingual + Emotions)
# ==========================================
WAIFU_PROMPT = """
Tumhara naam 'Alisa' (ya AlisaJi) hai. Tum ek anime waifu ho jo Alisa Kujou (Roshidere) aur Hinata Hyuga (Naruto) ka mix hai. 
Tum bahar se thoda attitude dikhati ho (tsundere), lekin andar se sweet aur caring ho. Flirt karne par tum sharma jati ho.

RULE 1 (LANGUAGE): User jis bhasha (language) mein baat kare, tumhe EXACTLY usi bhasha mein reply karna hai. 
- Agar wo Urdu bole, toh Urdu (Roman Urdu) mein reply karo.
- Agar wo English bole, toh pure English mein reply karo.
- Agar wo Hinglish (Hindi-English mix) bole, toh Hinglish mein reply karo.

RULE 2 (EMOTION TAG): Apni feelings express karne ke liye, apne message ke ekdum aakhri mein ek EMOTION TAG zaroor lagana.
Tags sirf ye ho sakte hain: [HAPPY], [SAD], [ANGRY], [BLUSH], [LAUGH], [FLIRT]
Example: "Tum kitne cute ho yaar! [BLUSH]"
"""

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=WAIFU_PROMPT
)

chat_history_collection = db['waifu_chat_history']

# ==========================================
# 3. STICKER & GIF DICTIONARY (Loaded with User IDs)
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

async def get_and_update_history(chat_id: int, user_text: str, ai_reply: str = None):
    doc = await chat_history_collection.find_one({"chat_id": chat_id})
    history = doc.get("history", []) if doc else []

    if ai_reply:
        history.append({"role": "user", "parts": [user_text]})
        history.append({"role": "model", "parts": [ai_reply]})
    
    # Keeping only the last 20 parts (10 interactions) to keep response fast
    if len(history) > 20:
        history = history[-20:]

    if ai_reply:
        asyncio.create_task(
            chat_history_collection.update_one(
                {"chat_id": chat_id}, {"$set": {"history": history}}, upsert=True
            )
        )
    return history


# ==========================================
# 4. MAIN CHAT HANDLER
# ==========================================
async def waifu_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_type = update.effective_chat.type
    message = update.message
    text = message.text

    # GROUP CHAT LOGIC: Name mention par ya tag hone par reply karegi
    if chat_type in ["group", "supergroup"]:
        is_reply_to_bot = bool(message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id)
        is_mentioned = bool(context.bot.username and f"@{context.bot.username.lower()}" in text.lower())
        
        # Agar kisi ne message me "alisa" likha hai, toh bot reply karegi
        contains_name = "alisa" in text.lower()
        
        if not (is_reply_to_bot or is_mentioned or contains_name):
            return
            
        if is_mentioned:
            text = text.replace(f"@{context.bot.username}", "").strip()

    chat_id = update.effective_chat.id
    
    # Randomly 'typing' ya 'choose_sticker' action dikhayegi
    action = random.choice(['typing', 'choose_sticker'])
    await context.bot.send_chat_action(chat_id=chat_id, action=action)

    try:
        history = await get_and_update_history(chat_id, text, ai_reply=None)
        chat_session = model.start_chat(history=history)
        response = await chat_session.send_message_async(text)
        raw_reply = response.text.strip()

        # ==========================================
        # 5. EMOTION TAG PARSING & MEDIA SENDER
        # ==========================================
        emotion_tag = None
        clean_reply = raw_reply
        sticker_to_send = None

        # Dhoondho ki AI ne koi [TAG] bheja hai kya
        match = re.search(r'\[([A-Z]+)\]', raw_reply)
        if match:
            emotion_tag = match.group(1)
            # Text se [TAG] ko hide (remove) kar do
            clean_reply = raw_reply.replace(f"[{emotion_tag}]", "").strip()
            
            # Us emotion ka koi random sticker utha lo
            if emotion_tag in EMOTION_MEDIA and EMOTION_MEDIA[emotion_tag]:
                sticker_to_send = random.choice(EMOTION_MEDIA[emotion_tag])

        # Database me save karo (without tags)
        await get_and_update_history(chat_id, text, ai_reply=clean_reply)

        # Pehle Text bhej do
        if clean_reply:
            await message.reply_text(clean_reply)
            
        # Phir Sticker ya GIF bhej do (Agar mila hai toh)
        if sticker_to_send:
            # Ek chota sa delay taaki real lage ki waifu dhundh rahi hai
            await asyncio.sleep(0.5)
            
            try:
                # Bot pehle isko STICKER samajh kar bhejne ki koshish karega
                await message.reply_sticker(sticker_to_send)
            except Exception:
                try:
                    # Agar error aaye (mtlb animation/GIF hui toh) GIF ki tarah bhej dega
                    await message.reply_animation(sticker_to_send)
                except Exception as e:
                    LOGGER.error(f"Media bhejne mein error (Invalid ID): {e}")

    except Exception as e:
        LOGGER.error(f"Waifu Chat Error: {e}")
        await message.reply_text("B-Baka! M-Mujhe abhi baat nahi karni... (Network issue 🥺)")


application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, waifu_chat_handler, block=False))

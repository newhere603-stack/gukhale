import logging
import asyncio
import re
import random
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import MessageHandler, CommandHandler, filters, ContextTypes
from shivu import application, user_collection, BOT_USERNAME

LOGGER = logging.getLogger(__name__)

# ==========================================
# 1. OPENROUTER API SETUP
# ==========================================
# OpenRouter ki key daalo
OPENROUTER_API_KEY = "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"
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)

# Chat status tracking
WAIFU_CHAT_ENABLED = {}

# ==========================================
# 2. PROMPT & MODEL
# ==========================================
WAIFU_SYSTEM_PROMPT = """
Tumhara naam 'Alisa' (ya AlisaJi) hai. Tum ek anime waifu ho jo Alisa Kujou (Roshidere) aur Hinata Hyuga (Naruto) ka mix hai. 
Tum bahar se thoda attitude dikhati ho (tsundere), lekin andar se sweet aur caring ho. 
User jis bhasha mein baat kare, usi bhasha mein reply karo.
Message ke aakhri mein emotion tag zaroor lagana: [HAPPY], [SAD], [ANGRY], [BLUSH], [LAUGH], [FLIRT]
"""

# OpenRouter Model (Tum Llama 3 ya Gemini 1.5 Flash use kar sakte ho)
MODEL_NAME = "google/gemini-flash-1.5-exp" 

chat_history_collection = user_collection.database['waifu_chat_history']

# (Sticker dictionary wahi purani wali use hogi - maine yahan skip ki hai taaki code short rahe)
from waifu_chat import EMOTION_MEDIA 

# ==========================================
# 3. CHAT LOGIC (OpenRouter Compatible)
# ==========================================
async def waifu_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    chat_id = update.effective_chat.id
    if not WAIFU_CHAT_ENABLED.get(chat_id, True): return

    text = update.message.text
    # (Group filters wahi purane wale rakho...)
    
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')

    try:
        # History fetch (MongoDB logic)
        doc = await chat_history_collection.find_one({"chat_id": chat_id})
        messages = doc.get("history", []) if doc else []
        messages.append({"role": "user", "content": text})

        # OpenAI format mein OpenRouter call
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": WAIFU_SYSTEM_PROMPT}] + messages[-10:]
        )
        
        reply = response.choices[0].message.content.strip()
        
        # Sticker handling (Wahi purana logic)
        match = re.search(r'\[([A-Z]+)\]', reply)
        clean_reply = re.sub(r'\[[A-Z]+\]', '', reply).strip()
        
        await update.message.reply_text(clean_reply)
        
        # Save history
        messages.append({"role": "assistant", "content": reply})
        asyncio.create_task(chat_history_collection.update_one({"chat_id": chat_id}, {"$set": {"history": messages[-10:]}}, upsert=True))

    except Exception as e:
        LOGGER.error(f"OpenRouter Error: {e}")
        await update.message.reply_text("B-Baka! AI thoda busy hai... 🥺")

# Register handler
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, waifu_chat_handler, block=False), group=1)

import logging
import asyncio
import re
import random
from openrouter import OpenRouter
from telegram import Update
from telegram.ext import MessageHandler, CommandHandler, filters, ContextTypes
from shivu import application, user_collection

LOGGER = logging.getLogger(__name__)

# ==========================================
# 1. OPENROUTER OFFICIAL SDK SETUP
# ==========================================
API_KEY = "Sk-or-v1-e99181b2748d135be852c7573ca3c32330b0991042dec21b727d6a37337e7fdd"
WAIFU_CHAT_ENABLED = {}

WAIFU_SYSTEM_PROMPT = """
Tumhara naam 'Alisa' (ya AlisaJi) hai. Tum ek anime waifu ho jo Alisa Kujou (Roshidere) aur Hinata Hyuga (Naruto) ka mix hai. 
Tum bahar se thoda attitude dikhati ho (tsundere), lekin andar se sweet aur caring ho. 
User jis bhasha mein baat kare, usi bhasha mein reply karo.
Message ke aakhri mein emotion tag zaroor lagana: [HAPPY], [SAD], [ANGRY], [BLUSH], [LAUGH], [FLIRT]
Example: "Tum kitne cute ho yaar! [BLUSH]"
"""

chat_history_collection = user_collection.database['waifu_chat_history']

# ==========================================
# 2. STICKER & GIF DICTIONARY
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
# 3. ADMIN & TOGGLE HANDLERS
# ==========================================
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return False
    if chat.type == "private":
        return True
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ["creator", "administrator"]
    except Exception:
        return False

async def toggle_waifu_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return
    if not await is_admin(update, context):
        await update.message.reply_text("<b>❌ Only group admins can enable or disable the Waifu ChatBot.</b>", parse_mode="HTML")
        return
    chat_id = update.effective_chat.id
    current_status = WAIFU_CHAT_ENABLED.get(chat_id, True)
    new_status = not current_status
    WAIFU_CHAT_ENABLED[chat_id] = new_status
    status_text = "ENABLED ✅" if new_status else "DISABLED ❌"
    await update.message.reply_text(f"<b>Waifu ChatBot is now: {status_text}</b>", parse_mode="HTML")

# ==========================================
# 4. MAIN CHAT HANDLER (OpenRouter Official SDK)
# ==========================================
async def waifu_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    if not WAIFU_CHAT_ENABLED.get(chat_id, True):
        return

    text = update.message.text
    chat_type = update.effective_chat.type

    if chat_type in ["group", "supergroup"]:
        is_reply = bool(update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id)
        bot_uname = context.bot.username.lower() if context.bot.username else ""
        is_mentioned = bool(bot_uname and f"@{bot_uname}" in text.lower())
        contains_name = bool(re.search(r'\balisa\b', text, re.IGNORECASE))
        if not (is_reply or is_mentioned or contains_name):
            return
        if is_mentioned and bot_uname:
            text = text.replace(f"@{context.bot.username}", "").strip()
    
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    except Exception:
        pass

    try:
        doc = await chat_history_collection.find_one({"chat_id": chat_id})
        messages = doc.get("history", []) if doc else []
        messages.append({"role": "user", "content": text})

        # Official OpenRouter SDK call wrapped safely for async
        def call_openrouter():
            with OpenRouter(
                api_key=API_KEY,
                http_referer="https://t.me/AlisaWaifusBot",
                appTitle="Alisa Waifu Bot"
            ) as client:
                return client.chat.send(
                    model="google/gemini-flash-1.5",
                    messages=[{"role": "system", "content": WAIFU_SYSTEM_PROMPT}] + messages[-10:]
                )

        response = await asyncio.to_thread(call_openrouter)
        reply = response.choices[0].message.content.strip()
        
        match = re.search(r'\[([A-Z]+)\]', reply)
        clean_reply = re.sub(r'\[[A-Z]+\]', '', reply).strip()
        
        if clean_reply:
            await update.message.reply_text(clean_reply)
        
        messages.append({"role": "assistant", "content": reply})
        asyncio.create_task(
            chat_history_collection.update_one(
                {"chat_id": chat_id}, {"$set": {"history": messages[-10:]}}, upsert=True
            )
        )

        if match and match.group(1) in EMOTION_MEDIA and EMOTION_MEDIA[match.group(1)]:
            await asyncio.sleep(0.5)
            sticker_to_send = random.choice(EMOTION_MEDIA[match.group(1)])
            try:
                await update.message.reply_sticker(sticker_to_send)
            except Exception:
                try:
                    await update.message.reply_animation(sticker_to_send)
                except Exception as e:
                    LOGGER.error(f"Media error: {e}")

    except Exception as e:
        LOGGER.error(f"Waifu Error: {e}")
        await update.message.reply_text(f"❌ OpenRouter SDK Error:\n{str(e)[:300]}")

# ==========================================
# 5. HANDLERS REGISTRATION
# ==========================================
application.add_handler(CommandHandler("togglechat", toggle_waifu_chat_handler, block=False))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, waifu_chat_handler, block=False), group=1)

import logging
import asyncio
import re
import random
import os
import requests

from telegram import Update
from telegram.ext import (
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)

from shivu import application, user_collection


LOGGER = logging.getLogger(__name__)


# ==========================================
# 1. OPENROUTER API SETUP
# ==========================================

API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Current free OpenRouter model
MODEL = "google/gemma-4-31b-it:free"

WAIFU_CHAT_ENABLED = {}


# ==========================================
# 2. SYSTEM PROMPT
# ==========================================

WAIFU_SYSTEM_PROMPT = """
Tumhara naam Alisa hai.

Tum ek anime waifu ho jo Alisa Kujou (Roshidere)
aur Hinata Hyuga (Naruto) ka mix hai.

Personality:
- Bahar se thoda attitude / tsundere.
- Andar se sweet, caring aur friendly.
- User se natural tarike se baat karo.
- Har reply robotic nahi hona chahiye.
- Kabhi kabhi cute reactions use karo.
- User jis language mein baat kare, usi language mein reply karo.
- Hindi/Hinglish user ho to Hinglish mein reply karo.
- English user ho to English mein reply karo.
- User ke message ka direct answer do.
- Bahut lamba reply mat do jab tak user detail na maange.

Important:
Reply ke END mein exactly ek emotion tag zaroor lagao.

Allowed tags:
[HAPPY]
[SAD]
[ANGRY]
[BLUSH]
[LAUGH]
[FLIRT]

Example:
Tum kitne cute ho yaar! [BLUSH]

Another example:
Hahaha tumse ye expect nahi kiya tha 😂 [LAUGH]
"""


# ==========================================
# 3. CHAT HISTORY COLLECTION
# ==========================================

chat_history_collection = user_collection.database["waifu_chat_history"]


# ==========================================
# 4. STICKER / GIF DICTIONARY
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
        "CAACAgUAAxkBAAFR3hlqgBI8mSvH9K4eOU4Qj7y-pEQRigACyhgAAmO6EFUgbWsg-1F2Tj0E",
    ],

    "SAD": [
        "CAACAgUAAxkBAAFR3hNqgBIn4b9iZNiFHx4cB10tqRI7NgACOxcAAjV2qFThhaZ9Pm0Myj0E",
        "CAACAgUAAxkBAAFR3iFqgBNuVf4c8hAUW8kKeVXTcGHqAwAC9xsAAvn1SFXgplE-lZdNcj0E",
        "CAACAgUAAxkBAAFR3i1qgBPayyTEc6cFhtqc94SVMMbx1AACiCcAAsyO2VTWyfLCKjr7nD0E",
    ],

    "ANGRY": [
        "CAACAgUAAxkBAAFR3iVqgBO3JC6-oOEUWVM-AmMfloIIjgACAhoAAjqT2VXEvUSG1hjGHj0E",
        "CAACAgUAAxkBAAFR3i9qgBPsx-5fBwufuVgBUlDK_ec4QAACtRAAArI-QFazW1M8z7SWSj0E",
    ],

    "BLUSH": [
        "CAACAgUAAxkBAAFR3jRqgBQf6SJcoFrMUtEB9OM5HCaUpAACoRYAAuqt0VRbqNEszdX3Ej0E",
        "CAACAgUAAxkBAAFR3jZqgBQ007MeN_OWyzW13Mn9rOtKwgACNxgAAisSSVXDmdjUzngLRT0E",
    ],

    "FLIRT": [
        "CAACAgUAAxkBAAFR3hdqgBI2k4bZE6tzwY7zVfiF-tw6fwACXhYAAqgp6FZJs89vgZurvj0E",
    ],

    "LAUGH": [
        "CAACAgUAAxkBAAFR3jtqgBSSa_HpuYq-P7Aiys7efYCmowACIhUAAg10eFcdJmcN6Z9L_z0E",
    ],
}


# ==========================================
# 5. ADMIN CHECK
# ==========================================

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return False

    # Private chat
    if chat.type == "private":
        return True

    try:
        member = await context.bot.get_chat_member(
            chat.id,
            user.id
        )

        return member.status in ["creator", "administrator"]

    except Exception as e:
        LOGGER.error(f"Admin check error: {e}")
        return False


# ==========================================
# 6. TOGGLE CHAT
# ==========================================

async def toggle_waifu_chat_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.effective_chat or not update.message:
        return

    if not await is_admin(update, context):

        await update.message.reply_text(
            "<b>❌ Only group admins can enable or disable the Waifu ChatBot.</b>",
            parse_mode="HTML"
        )

        return

    chat_id = update.effective_chat.id

    current_status = WAIFU_CHAT_ENABLED.get(
        chat_id,
        True
    )

    new_status = not current_status

    WAIFU_CHAT_ENABLED[chat_id] = new_status

    status_text = (
        "ENABLED ✅"
        if new_status
        else "DISABLED ❌"
    )

    await update.message.reply_text(
        f"<b>Waifu ChatBot is now: {status_text}</b>",
        parse_mode="HTML"
    )


# ==========================================
# 7. OPENROUTER REQUEST
# ==========================================

async def get_ai_reply(messages):

    if not API_KEY:
        LOGGER.error(
            "OPENROUTER_API_KEY is missing."
        )
        return None, "API_KEY_MISSING"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/AlisaWaifusBot",
        "X-Title": "Alisa Waifu Bot",
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.9,
        "max_tokens": 300,
    }

    loop = asyncio.get_running_loop()

    def make_request():

        try:

            return requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=30
            )

        except Exception as e:

            LOGGER.error(
                f"Request exception: {e}"
            )

            return None

    response = await loop.run_in_executor(
        None,
        make_request
    )

    if response is None:
        return None, "REQUEST_ERROR"

    LOGGER.info(
        f"OpenRouter status: {response.status_code}"
    )

    if response.status_code != 200:

        LOGGER.error(
            f"OpenRouter Error "
            f"{response.status_code}: "
            f"{response.text}"
        )

        return None, response.status_code

    try:

        data = response.json()

    except Exception as e:

        LOGGER.error(
            f"Invalid JSON response: {e}"
        )

        return None, "INVALID_JSON"

    try:

        reply = (
            data["choices"][0]
            ["message"]["content"]
            .strip()
        )

        return reply, None

    except Exception as e:

        LOGGER.error(
            f"Invalid OpenRouter response: "
            f"{data}"
        )

        return None, "INVALID_RESPONSE"


# ==========================================
# 8. MAIN CHAT HANDLER
# ==========================================

async def waifu_chat_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return

    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    chat_id = chat.id
    user_id = user.id

    # --------------------------------------
    # Check group toggle
    # --------------------------------------

    if not WAIFU_CHAT_ENABLED.get(
        chat_id,
        True
    ):
        return

    text = update.message.text.strip()

    if not text:
        return

    # --------------------------------------
    # Group trigger
    # --------------------------------------

    if chat.type in ["group", "supergroup"]:

        is_reply = False

        if update.message.reply_to_message:

            replied_user = (
                update.message.reply_to_message.from_user
            )

            if replied_user:
                is_reply = (
                    replied_user.id
                    == context.bot.id
                )

        bot_username = (
            context.bot.username.lower()
            if context.bot.username
            else ""
        )

        is_mentioned = False

        if bot_username:

            is_mentioned = (
                f"@{bot_username}"
                in text.lower()
            )

        contains_name = bool(
            re.search(
                r"\balisa\b",
                text,
                re.IGNORECASE
            )
        )

        if not (
            is_reply
            or is_mentioned
            or contains_name
        ):
            return

        # Remove mention
        if is_mentioned and bot_username:

            text = re.sub(
                rf"@{re.escape(context.bot.username)}",
                "",
                text,
                flags=re.IGNORECASE
            ).strip()

        if not text:
            text = "Haan? Mujhe bulaya? 👀"

    # --------------------------------------
    # Typing action
    # --------------------------------------

    try:

        await context.bot.send_chat_action(
            chat_id=chat_id,
            action="typing"
        )

    except Exception:
        pass

    # --------------------------------------
    # Database history
    # --------------------------------------

    history_id = {
        "chat_id": chat_id,
        "user_id": user_id
    }

    try:

        doc = await chat_history_collection.find_one(
            history_id
        )

        messages = (
            doc.get("history", [])
            if doc
            else []
        )

        # Keep only valid messages
        messages = [
            msg for msg in messages
            if (
                isinstance(msg, dict)
                and msg.get("role")
                and msg.get("content")
            )
        ]

        messages.append({
            "role": "user",
            "content": text
        })

        # ----------------------------------
        # Prepare AI messages
        # ----------------------------------

        ai_messages = [
            {
                "role": "system",
                "content": WAIFU_SYSTEM_PROMPT
            }
        ] + messages[-10:]

        # ----------------------------------
        # AI request
        # ----------------------------------

        reply, error = await get_ai_reply(
            ai_messages
        )

        # ----------------------------------
        # Error handling
        # ----------------------------------

        if not reply:

            if error == "API_KEY_MISSING":

                error_text = (
                    "❌ OpenRouter API key missing hai."
                )

            elif error == 401:

                error_text = (
                    "❌ OpenRouter API key invalid "
                    "ya revoked hai."
                )

            elif error == 402:

                error_text = (
                    "❌ OpenRouter credits/payment "
                    "problem hai."
                )

            elif error == 429:

                error_text = (
                    "🥺 AI server ki rate limit "
                    "hit ho gayi. Thodi der baad try karo."
                )

            elif error == 404:

                error_text = (
                    "❌ AI model available nahi hai."
                )

            elif error == "REQUEST_ERROR":

                error_text = (
                    "❌ AI server se connection nahi ho paya."
                )

            else:

                error_text = (
                    "B-Baka! AI server busy hai... 🥺"
                )

            await update.message.reply_text(
                error_text
            )

            return

        # ----------------------------------
        # Emotion detection
        # ----------------------------------

        match = re.search(
            r"\[(HAPPY|SAD|ANGRY|BLUSH|LAUGH|FLIRT)\]",
            reply,
            re.IGNORECASE
        )

        if match:

            emotion = match.group(1).upper()

        else:

            emotion = None

        # Remove emotion tag
        clean_reply = re.sub(
            r"\[(HAPPY|SAD|ANGRY|BLUSH|LAUGH|FLIRT)\]",
            "",
            reply,
            flags=re.IGNORECASE
        ).strip()

        # ----------------------------------
        # Send AI reply
        # ----------------------------------

        if clean_reply:

            await update.message.reply_text(
                clean_reply
            )

        # ----------------------------------
        # Save conversation
        # ----------------------------------

        messages.append({
            "role": "assistant",
            "content": reply
        })

        await chat_history_collection.update_one(
            history_id,
            {
                "$set": {
                    "history": messages[-10:]
                }
            },
            upsert=True
        )

        # ----------------------------------
        # Send emotion sticker
        # ----------------------------------

        if (
            emotion
            and emotion in EMOTION_MEDIA
            and EMOTION_MEDIA[emotion]
        ):

            await asyncio.sleep(0.5)

            sticker_id = random.choice(
                EMOTION_MEDIA[emotion]
            )

            try:

                await update.message.reply_sticker(
                    sticker=sticker_id
                )

            except Exception as e:

                LOGGER.error(
                    f"Sticker send error: {e}"
                )

    except Exception as e:

        LOGGER.exception(
            f"Waifu Chat Error: {e}"
        )

        try:

            await update.message.reply_text(
                "B-Baka! M-Mujhe error aa gaya... 🥺"
            )

        except Exception:
            pass


# ==========================================
# 9. REGISTER HANDLERS
# ==========================================

application.add_handler(
    CommandHandler(
        "togglechat",
        toggle_waifu_chat_handler,
        block=False
    )
)

application.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        waifu_chat_handler,
        block=False
    ),
    group=1
)

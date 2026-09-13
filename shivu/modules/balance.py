import logging
import asyncio
import random

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes
# pymongo ReturnDocument ki ab zaroorat nahi padegi, par aapke baaki code ke liye chhod diya hai
from pymongo import ReturnDocument  

from shivu import application, LOGGER, BOT_USERNAME
from shivu.Database.db import eco_collection 


# ==========================================================
# 👤 USER DATA (Superfast Read)
# ==========================================================

async def get_or_init_user(uid: int):
    """User ko fetch karega (Superfast Read). Agar nahi hai tabhi Create karega."""
    try:
        # 🔥 STEP 1: Pehle sirf READ karo (Yeh Find_one_and_update se 10x fast hai)
        user = await eco_collection.find_one({"id": uid})
        
        # 🔥 STEP 2: Agar user database mein NAHI hai, tabhi INSERT karo
        if not user:
            new_user = {
                "id": uid,
                "balance": 0,
                "tokens": 0,
                "bot_started": False
            }
            await eco_collection.insert_one(new_user)
            return new_user
            
        return user
    except Exception as e:
        LOGGER.error(f"Error in get_or_init_user for uid {uid}: {e}")
        return {"id": uid, "balance": 0, "tokens": 0, "bot_started": False}


# ==========================================================
# ✨ TELEGRAM LIVE TEXT ANIMATION (FAST + FORMATTED)
# ==========================================================

# Premium emoji IDs (Balance & Tokens)
BALANCE_EMOJI_ID = "5472030678633684592"
BALANCE_EMOJI_CHAR = "💸"
TOKENS_EMOJI_ID = "6332379101231323246"
TOKENS_EMOJI_CHAR = "💠"


def _build_animated_frame(
    up_to: int,
    emoji_char: str,
    emoji_id: str,
    header_plain: str,   # e.g. " ʙᴀʟᴀɴᴄᴇ: "  (space + label + ": ")
    value_plain: str,
) -> str:
    """
    Build a VALID HTML frame that shows the first `up_to` characters of:
        emoji_char + header_plain + value_plain

    Always renders as:
        <tg-emoji emoji-id="...">emoji</tg-emoji> <b>label: <code>value</code></b>

    So during the whole animation the user sees:
        • Premium emoji
        • Bold label
        • Amount inside <code>
    """
    emoji_len = len(emoji_char)

    if up_to <= 0:
        return ""

    # Can't render a partial premium emoji, just return raw partial (edge case)
    if up_to <= emoji_len:
        return emoji_char[:up_to]

    html = f'<tg-emoji emoji-id="{emoji_id}">{emoji_char}</tg-emoji>'

    header_end = emoji_len + len(header_plain)

    if up_to <= header_end:
        # Still typing the label part
        html += f"<b>{header_plain[: up_to - emoji_len]}</b>"
    else:
        # Typing the value part -> wrap in <code> inside <b>
        value_shown = value_plain[: up_to - header_end]
        html += f"<b>{header_plain}<code>{value_shown}</code></b>"

    return html


async def animated_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    emoji_id: str,
    emoji_char: str,
    label: str,          # e.g. "ʙᴀʟᴀɴᴄᴇ"  (without colon & space)
    value_str: str,      # e.g. "1,000"
    final_text: str,     # final HTML reply (with premium emoji + bold + code)
    speed: float = 0.04,
    chunk_size: int = 4,
):
    """
    Telegram Live Text Animation.

    ✔ Every frame is fully formatted (premium emoji + bold label + code amount)
    ✔ Speed same as before (0.04)
    ✔ Response fast (chunk_size = 4, non-blocking)
    """
    message = update.effective_message
    user = update.effective_user

    if not message or not user:
        return

    # sendMessageDraft ONLY works for private chats. Group mein direct reply dega.
    if update.effective_chat.type != "private":
        return await message.reply_text(
            final_text,
            parse_mode="HTML"
        )

    # Must be non-zero and SAME throughout the animation.
    draft_id = random.randint(1, 2_000_000_000)

    # Header = space + label + ": "   (kyunki emoji ke baad space aata hai)
    header_plain = f" {label}: "
    full_plain = emoji_char + header_plain + value_str
    emoji_len = len(emoji_char)
    total = len(full_plain)

    try:
        # -----------------------------------------
        # FIRST VISIBLE FRAME
        # -----------------------------------------
        up_to = min(chunk_size, total)
        if up_to < emoji_len:
            up_to = emoji_len

        try:
            await context.bot._post(
                "sendMessageDraft",
                {
                    "chat_id": user.id,
                    "draft_id": draft_id,
                    "text": _build_animated_frame(
                        up_to, emoji_char, emoji_id, header_plain, value_str
                    ),
                    "parse_mode": "HTML",
                },
            )
        except AttributeError:
            pass  # Ignore if method not supported in older PTB versions

        await asyncio.sleep(speed)

        # -----------------------------------------
        # CONTINUE STREAMING (same draft_id)
        # -----------------------------------------
        while up_to < total:
            up_to = min(up_to + chunk_size, total)

            try:
                await context.bot._post(
                    "sendMessageDraft",
                    {
                        "chat_id": user.id,
                        "draft_id": draft_id,
                        "text": _build_animated_frame(
                            up_to, emoji_char, emoji_id, header_plain, value_str
                        ),
                        "parse_mode": "HTML",
                    },
                )
            except AttributeError:
                pass

            await asyncio.sleep(speed)

        # -----------------------------------------
        # FINAL PERMANENT REPLY (same look as animation)
        # -----------------------------------------
        return await message.reply_text(
            final_text,
            parse_mode="HTML"
        )

    except Exception as e:
        LOGGER.warning(f"Live text animation failed for {user.id}: {e}")

        # -----------------------------------------
        # SAFE FALLBACK
        # -----------------------------------------
        try:
            return await message.reply_text(
                final_text,
                parse_mode="HTML"
            )
        except Exception as final_error:
            LOGGER.error(f"Animated reply fallback failed: {final_error}")
            return None


# ==========================================================
# 💰 BALANCE COMMAND
# ==========================================================

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return

    uid = update.effective_user.id

    try:
        user = await get_or_init_user(uid)
        
        # Check if user has explicitly started the bot
        if user and not user.get("bot_started", True):
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("sᴛᴀʀᴛ ʙᴏᴛ", url=f"https://t.me/{BOT_USERNAME}?start=True")]
            ])
            await update.message.reply_html(
                "<b>ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ʏᴇᴛ!</b>\n\n"
                "<b>ᴘʟᴇᴀsᴇ sᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ ɪɴ ᴅᴍ ᴛᴏ ᴠɪᴇᴡ ʏᴏᴜʀ ʙᴀʟᴀɴᴄᴇ.</b>",
                reply_markup=kb
            )
            return

        balance = user.get("balance", 0) if user else 0
        balance_str = f"{balance:,}"

        # Animated reply call — same look as final (premium emoji + bold + code)
        await animated_reply(
            update=update,
            context=context,
            emoji_id=BALANCE_EMOJI_ID,
            emoji_char=BALANCE_EMOJI_CHAR,
            label="ʙᴀʟᴀɴᴄᴇ",
            value_str=balance_str,
            final_text=(
                f'<tg-emoji emoji-id="{BALANCE_EMOJI_ID}">💸</tg-emoji> '
                f'<b>ʙᴀʟᴀɴᴄᴇ: <code>{balance_str}</code></b>'
            ),
            speed=0.04,
            chunk_size=4,
        )
        
    except Exception as e:
        LOGGER.error(f"Critical error in balance_cmd: {e}")
        try:
            await update.message.reply_text(
                "<b>ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass


# ==========================================================
# 💠 TOKENS COMMAND
# ==========================================================

async def tokens_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return

    uid = update.effective_user.id

    try:
        user = await get_or_init_user(uid)
        
        # Check if user has explicitly started the bot
        if user and not user.get("bot_started", True):
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("sᴛᴀʀᴛ ʙᴏᴛ", url=f"https://t.me/{BOT_USERNAME}?start=True")]
            ])
            await update.message.reply_html(
                "<b>ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ʏᴇᴛ!</b>\n\n"
                "<b>ᴘʟᴇᴀsᴇ sᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ ɪɴ ᴅᴍ ᴛᴏ ᴠɪᴇᴡ ʏᴏᴜʀ ᴛᴏᴋᴇɴs.</b>",
                reply_markup=kb
            )
            return

        tokens = user.get("tokens", 0) if user else 0
        tokens_str = f"{tokens:,}"

        # Animated reply call — same look as final (premium emoji + bold + code)
        await animated_reply(
            update=update,
            context=context,
            emoji_id=TOKENS_EMOJI_ID,
            emoji_char=TOKENS_EMOJI_CHAR,
            label="ᴛᴏᴋᴇɴs",
            value_str=tokens_str,
            final_text=(
                f'<tg-emoji emoji-id="{TOKENS_EMOJI_ID}">💠</tg-emoji> '
                f'<b>ᴛᴏᴋᴇɴs: <code>{tokens_str}</code></b>'
            ),
            speed=0.04,
            chunk_size=4,
        )
        
    except Exception as e:
        LOGGER.error(f"Critical error in tokens_cmd: {e}")
        try:
            await update.message.reply_text(
                "<b>ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass


# ==========================================================
# 📌 HANDLERS
# ==========================================================

# block=False ki wajah se multiple users ek sath commands denge toh bot hang nahi hoga
application.add_handler(CommandHandler(["bal", "balance", "coins", "coin"], balance_cmd, block=False))
application.add_handler(CommandHandler(["tokens", "tbal", "token"], tokens_cmd, block=False))

LOGGER.info("✓ Balance & Tokens module loaded successfully (Superfast Formatted Animation)")

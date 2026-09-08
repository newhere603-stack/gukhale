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
# ✨ TELEGRAM LIVE TEXT ANIMATION (FIXED)
# ==========================================================

async def animated_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    draft_text: str,
    final_text: str,
    speed: float = 0.12
):
    """
    Telegram Live Text Animation.

    Draft:
        Plain text only, so HTML parsing never breaks.

    Final:
        Proper HTML formatted reply to the user's command.
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

    try:
        # -----------------------------------------
        # STREAMING TEXT
        # -----------------------------------------
        # Small chunks = smoother animation.
        chunk_size = 2

        # First visible part
        current = draft_text[:chunk_size]

        try:
            await context.bot._post(
                "sendMessageDraft",
                {
                    "chat_id": user.id,
                    "draft_id": draft_id,
                    "text": current
                }
            )
        except AttributeError:
            pass # Ignore if method not supported in older PTB versions

        await asyncio.sleep(speed)

        # Continue with SAME draft_id
        for i in range(chunk_size, len(draft_text), chunk_size):
            current = draft_text[:i + chunk_size]

            try:
                await context.bot._post(
                    "sendMessageDraft",
                    {
                        "chat_id": user.id,
                        "draft_id": draft_id,
                        "text": current
                    }
                )
            except AttributeError:
                pass

            await asyncio.sleep(speed)

        # -----------------------------------------
        # FINAL PERMANENT REPLY
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
        
        # Animated reply call
        await animated_reply(
            update=update,
            context=context,
            draft_text=f"💸 ʙᴀʟᴀɴᴄᴇ: {balance:,}",
            final_text=(
                f'<tg-emoji emoji-id="5472030678633684592">💸</tg-emoji> '
                f'<b>ʙᴀʟᴀɴᴄᴇ: <code>{balance:,}</code></b>'
            ),
            speed=0.12
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

        # Animated reply call
        await animated_reply(
            update=update,
            context=context,
            draft_text=f"💠 ᴛᴏᴋᴇɴs: {tokens:,}",
            final_text=(
                f'<tg-emoji emoji-id="6332379101231323246">💠</tg-emoji> '
                f'<b>ᴛᴏᴋᴇɴs: <code>{tokens:,}</code></b>'
            ),
            speed=0.12
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

LOGGER.info("✓ Balance & Tokens module loaded successfully (Live Text Animation Fix Applied)")

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
# ✨ TELEGRAM LIVE TEXT ANIMATION
# ==========================================================

async def animated_text(
    bot,
    chat_id: int,
    final_text: str,
    parse_mode: str = "HTML",
    speed: float = 0.08
):
    """
    Telegram Live Text Animation.

    Private chat mein text gradually appear hoga.
    End mein normal permanent message send hoga.
    Groups/channels mein fail hone par automatically normal message bhejega.
    """
    draft_id = random.randint(1, 2_000_000_000)

    try:
        # Text ko reasonable chunks mein divide karo. (Flood limit bachane ke liye)
        chunk_size = 4

        # ------------------------------------------
        # FIRST DRAFT
        # ------------------------------------------
        current_text = final_text[:chunk_size]

        try:
            # New PTB versions
            await bot.send_message_draft(
                chat_id=chat_id,
                draft_id=draft_id,
                text=current_text,
                parse_mode=parse_mode
            )
        except AttributeError:
            # Older/custom PTB fallback
            await bot._post(
                "sendMessageDraft",
                {
                    "chat_id": chat_id,
                    "draft_id": draft_id,
                    "text": current_text,
                    "parse_mode": parse_mode
                }
            )

        # ------------------------------------------
        # STREAM THE TEXT
        # ------------------------------------------
        for i in range(chunk_size, len(final_text), chunk_size):
            current_text = final_text[:i + chunk_size]

            try:
                await bot.send_message_draft(
                    chat_id=chat_id,
                    draft_id=draft_id,
                    text=current_text,
                    parse_mode=parse_mode
                )
            except AttributeError:
                await bot._post(
                    "sendMessageDraft",
                    {
                        "chat_id": chat_id,
                        "draft_id": draft_id,
                        "text": current_text,
                        "parse_mode": parse_mode
                    }
                )

            # Animation speed
            await asyncio.sleep(speed)

        # ------------------------------------------
        # FINAL PERMANENT MESSAGE
        # ------------------------------------------
        return await bot.send_message(
            chat_id=chat_id,
            text=final_text,
            parse_mode=parse_mode
        )

    except Exception as e:
        LOGGER.warning(f"Animated text failed for {chat_id}: {e}")

        # ------------------------------------------
        # SAFE FALLBACK
        # ------------------------------------------
        # Animation fail ho jaye to bot ka command kabhi break nahi hoga.
        try:
            return await bot.send_message(
                chat_id=chat_id,
                text=final_text,
                parse_mode=parse_mode
            )
        except Exception as final_error:
            LOGGER.error(f"Final message also failed for {chat_id}: {final_error}")
            return None


# ==========================================================
# 💰 BALANCE COMMAND
# ==========================================================

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message or not update.effective_chat:
        return

    uid = update.effective_user.id
    chat_id = update.effective_chat.id

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
        
        balance_text = (
            f'<tg-emoji emoji-id="5472030678633684592">💸</tg-emoji> '
            f'<b>ʙᴀʟᴀɴᴄᴇ: <code>{balance:,}</code></b>'
        )

        # Private chat mein animated live text, fail hone par automatically normal message.
        await animated_text(
            bot=context.bot,
            chat_id=chat_id,
            final_text=balance_text,
            parse_mode="HTML",
            speed=0.08
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
    if not update.effective_user or not update.message or not update.effective_chat:
        return

    uid = update.effective_user.id
    chat_id = update.effective_chat.id

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

        tokens_text = (
            f'<tg-emoji emoji-id="6332379101231323246">💠</tg-emoji> '
            f'<b>ᴛᴏᴋᴇɴs: <code>{tokens:,}</code></b>'
        )

        # Private chat mein animated live text, fail hone par automatically normal message.
        await animated_text(
            bot=context.bot,
            chat_id=chat_id,
            final_text=tokens_text,
            parse_mode="HTML",
            speed=0.08
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

LOGGER.info("✓ Balance & Tokens module loaded successfully (Live Text Animation Enabled)")

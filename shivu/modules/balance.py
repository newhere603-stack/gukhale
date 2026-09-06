import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes
# pymongo ReturnDocument ki ab zaroorat nahi padegi, par aapke baaki code ke liye chhod diya hai
from pymongo import ReturnDocument  

from shivu import application, LOGGER, BOT_USERNAME
from shivu.Database.db import eco_collection 


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


# --- COINS BALANCE COMMAND ---
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

        await update.message.reply_text(
            f'<tg-emoji emoji-id="5472030678633684592">💸</tg-emoji> <b>ʙᴀʟᴀɴᴄᴇ: <code>{balance:,}</code></b>',
            parse_mode="HTML",
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


# --- TOKENS BALANCE COMMAND ---
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

        await update.message.reply_text(
            f'<tg-emoji emoji-id="6332379101231323246">💠</tg-emoji> <b>ᴛᴏᴋᴇɴs: <code>{tokens:,}</code></b>',
            parse_mode="HTML",
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


# block=False ki wajah se multiple users ek sath commands denge toh bot hang nahi hoga
application.add_handler(CommandHandler(["bal", "balance", "coins", "coin"], balance_cmd, block=False))
application.add_handler(CommandHandler(["tokens", "tbal", "token"], tokens_cmd, block=False))

LOGGER.info("✓ Balance & Tokens module loaded successfully (Optimized & Fast)")

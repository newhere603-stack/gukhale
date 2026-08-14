import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes
from shivu import application, user_collection, LOGGER, BOT_USERNAME


async def get_or_init_user(uid: int):
    """User ko database se ek hi query mein fetch ya initialize karega (Super Fast & Atomic)."""
    try:
        # find_one_and_update ek hi round-trip mein document fetch ya upsert kar deta hai
        user = await user_collection.find_one_and_update(
            {"id": uid},
            {
                "$setOnInsert": {
                    "id": uid,
                    "balance": 0,
                    "tokens": 0,
                    "bot_started": False
                }
            },
            upsert=True,
            return_document=True  # Updated/Inserted document turant return karega
        )
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
        
        if not user.get("bot_started", True):
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("sᴛᴀʀᴛ ʙᴏᴛ", url=f"https://t.me/{BOT_USERNAME}?start=True")]
            ])
            await update.message.reply_html(
                "<b>ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ʏᴇᴛ!</b>\n\n"
                "<b>ᴘʟᴇᴀsᴇ sᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ ɪɴ ᴅᴍ ᴛᴏ ᴠɪᴇᴡ ʏᴏᴜʀ ʙᴀʟᴀɴᴄᴇ.</b>",
                reply_markup=kb
            )
            return

        balance = user.get("balance", 0)

        await update.message.reply_text(
            f'<tg-emoji emoji-id="5472030678633684592">💸</tg-emoji> <b>ʙᴀʟᴀɴᴄᴇ: <code>{balance:,}</code></b>',
            parse_mode="HTML",
        )
    except Exception as e:
        LOGGER.error(f"Critical error in balance_cmd: {e}")
        try:
            await update.message.reply_text(
                "<b>⚠️ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.</b>",
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
        
        if not user.get("bot_started", True):
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("sᴛᴀʀᴛ ʙᴏᴛ", url=f"https://t.me/{BOT_USERNAME}?start=True")]
            ])
            await update.message.reply_html(
                "<b>ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ sᴛᴀʀᴛᴇᴅ ᴛ🇭ᴇ ʙᴏᴛ ʏᴇᴛ!</b>\n\n"
                "<b>ᴘʟᴇᴀsᴇ sᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ ɪɴ ᴅᴍ ᴛᴏ ᴠɪᴇᴡ ʏᴏᴜʀ ᴛᴏᴋᴇɴs.</b>",
                reply_markup=kb
            )
            return

        tokens = user.get("tokens", 0)

        await update.message.reply_text(
            f'<tg-emoji emoji-id="6332379101231323246">💠</tg-emoji> <b>ᴛᴏᴋᴇɴs: <code>{tokens:,}</code></b>',
            parse_mode="HTML",
        )
    except Exception as e:
        LOGGER.error(f"Critical error in tokens_cmd: {e}")
        try:
            await update.message.reply_text(
                "<b>⚠️ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass


# block=False ki wajah se multiple users ek sath commands denge toh bot hang nahi hoga
application.add_handler(CommandHandler(["bal", "balance", "coins", "coin"], balance_cmd, block=False))
application.add_handler(CommandHandler(["tokens", "tbal", "token"], tokens_cmd, block=False))

LOGGER.info("✓ Balance & Tokens module loaded successfully (Optimized & Fast)")

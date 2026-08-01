from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from shivu import application, user_collection, LOGGER


async def get_or_init_user(uid: int):
    """User ko database se fetch karega, agar nahi mila toh default values ke sath create karke return karega."""
    try:
        user = await user_collection.find_one({"id": uid})
        if user is None:
            new_user = {"id": uid, "balance": 0, "tokens": 0}
            await user_collection.update_one(
                {"id": uid},
                {"$setOnInsert": new_user},
                upsert=True
            )
            return new_user
        return user
    except Exception as e:
        LOGGER.error(f"Error in get_or_init_user for uid {uid}: {e}")
        return {"id": uid, "balance": 0, "tokens": 0}


# --- COINS BALANCE COMMAND ---
async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return

    uid = update.effective_user.id

    try:
        user = await get_or_init_user(uid)
        balance = user.get("balance", 0)

        # Text: Small Caps + Bold | Number formatted with commas inside code block
        await update.message.reply_text(
            f"💸 <b>ʙᴀʟᴀɴᴄᴇ: <code>{balance:,}</code></b>",
            parse_mode="HTML",
        )
    except Exception as e:
        LOGGER.error(f"Critical error in balance_cmd: {e}")
        try:
            await update.message.reply_text(
                "⚠️ <b>ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.</b>",
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
        tokens = user.get("tokens", 0)

        # Text: Small Caps + Bold | Number formatted with commas inside code block
        await update.message.reply_text(
            f"💠 <b>ᴛᴏᴋᴇɴs: <code>{tokens:,}</code></b>",
            parse_mode="HTML",
        )
    except Exception as e:
        LOGGER.error(f"Critical error in tokens_cmd: {e}")
        try:
            await update.message.reply_text(
                "⚠️ <b>ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass


# Command Handlers Register
application.add_handler(CommandHandler(["bal", "balance"], balance_cmd, block=False))
application.add_handler(CommandHandler(["tokens", "tbal", "token"], tokens_cmd, block=False))

LOGGER.info("✓ Balance & Tokens module loaded successfully")

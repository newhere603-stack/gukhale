from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from shivu import application, user_collection, LOGGER


async def get_user(uid: int):
    try:
        return await user_collection.find_one({"id": uid})
    except Exception as e:
        LOGGER.error(f"Error fetching user in balance: {e}")
        return None


async def init_user(uid: int):
    try:
        # Default balance aur tokens 0 set kar diye hain
        user = {"id": uid, "balance": 0, "tokens": 0}
        await user_collection.update_one(
            {"id": uid},
            {"$setOnInsert": user},
            upsert=True
        )
        return user
    except Exception as e:
        LOGGER.error(f"Error initializing user in balance: {e}")
        return {"id": uid, "balance": 0, "tokens": 0}


# --- COINS BALANCE COMMAND ---
async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return

    uid = update.effective_user.id

    try:
        user = await get_user(uid)
        if user is None:
            user = await init_user(uid)

        balance = user.get("balance", 0)

        # Text: Small Caps + Bold | Number: Monospace / Code Block (Single-tap copy)
        await update.message.reply_text(
            f"💸 <b>ʙᴀʟᴀɴᴄᴇ: <code>{balance}</code></b>",
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
        user = await get_user(uid)
        if user is None:
            user = await init_user(uid)

        # Tokens balance fetch karega
        tokens = user.get("tokens", 0)

        # Text: Small Caps + Bold | Number: Monospace / Code Block (Single-tap copy)
        await update.message.reply_text(
            f"💠 <b>ᴛᴏᴋᴇɴs ʙᴀʟᴀɴᴄᴇ: <code>{tokens}</code></b>",
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

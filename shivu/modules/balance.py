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
        user = {"id": uid, "balance": 0}
        await user_collection.insert_one(user)
        return user
    except Exception as e:
        LOGGER.error(f"Error initializing user in balance: {e}")
        return {"id": uid, "balance": 0}


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
            f"💸 <b>ʙᴀʟᴀɴᴄᴇ: <code>{balance_amount}</code></b>",
            parse_mode="HTML",
        )
    except Exception as e:
        LOGGER.error(f"Critical error in balance_cmd: {e}")
        try:
            await update.message.reply_text(
                "⚠️ **ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.**",
                parse_mode="Markdown",
            )
        except Exception:
            pass


# Command Handler Register
application.add_handler(CommandHandler("bal", balance_cmd, block=False))

LOGGER.info("✓ Balance module loaded successfully")

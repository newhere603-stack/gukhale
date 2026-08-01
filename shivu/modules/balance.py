from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from shivu import application, user_collection, LOGGER


async def get_user(uid: int):
    return await user_collection.find_one({"id": uid})


async def init_user(uid: int):
    user = {"id": uid, "balance": 0}
    await user_collection.insert_one(user)
    return user


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return

    uid = update.effective_user.id

    try:
        user = await get_user(uid)
        if user is None:
            user = await init_user(uid)

        balance = user.get("balance", 0)

        # Output text: Small caps + Bold | Balance number: Monospace (Single-tap Copy)
        await update.message.reply_text(
            f"💸 **ʙᴀʟᴀɴᴄᴇ:** `{balance}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        LOGGER.error(f"Error in balance_cmd: {e}")


# Command Handler registration
application.add_handler(CommandHandler("bal", balance_cmd, block=False))

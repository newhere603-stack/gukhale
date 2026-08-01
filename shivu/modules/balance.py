import logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from shivu import application, user_collection

LOGGER = logging.getLogger(__name__)


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return

    uid = update.effective_user.id

    try:
        user = await user_collection.find_one({"id": uid})
        if not user:
            user = {"id": uid, "balance": 0}
            await user_collection.insert_one(user)

        balance = user.get("balance", 0)

        await update.message.reply_text(
            f"💸 **ʙᴀʟᴀɴᴄᴇ:** `{balance}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        LOGGER.error(f"Error in balance_cmd: {e}")


# Register Command Handler
application.add_handler(CommandHandler("bal", balance_cmd, block=False))

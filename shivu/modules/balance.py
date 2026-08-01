from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
# Apne module se updated functions import karein
from shivu import application, get_user, init_user


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return

    uid = update.effective_user.id

    user = await get_user(uid)
    if user is None:
        user = await init_user(uid)

    balance = user.get("balance", 0)

    # Small caps font (bold) + balance copyable monospace format
    await update.message.reply_text(
        f"💸 **ʙᴀʟᴀɴᴄᴇ:** `{balance}`",
        parse_mode="Markdown",
    )


application.add_handler(CommandHandler("bal", balance_cmd, block=False))

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from shivu import application, get_user, init_user


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return

    uid = update.effective_user.id

    try:
        user = await get_user(uid)
        if user is None:
            user = await init_user(uid)

        balance = user.get("balance", 0)

        await update.message.reply_text(
            f"💸 **ʙᴀʟᴀɴᴄᴇ:** `{balance}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        print(f"Error in balance_cmd: {e}")


# YEH LINE ZARURI HAI:
application.add_handler(CommandHandler("bal", balance_cmd, block=False))

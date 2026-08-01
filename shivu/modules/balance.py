# ==================== BALANCE COMMAND ====================

async def get_user_bal(uid):
    return await user_collection.find_one({"id": uid})

async def init_user_bal(uid):
    user = {"id": uid, "balance": 0}
    await user_collection.insert_one(user)
    return user

async def balance_cmd(update: Update, context: CallbackContext):
    if not update.effective_user or not update.message:
        return

    uid = update.effective_user.id

    try:
        user = await get_user_bal(uid)
        if user is None:
            user = await init_user_bal(uid)

        balance = user.get("balance", 0)

        # Output: Text Small Caps & Bold, Number Monospace (Single-tap copy)
        await update.message.reply_text(
            f"💸 **ʙᴀʟᴀɴᴄᴇ:** `{balance}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        LOGGER.error(f"Error in balance_cmd: {e}")

# Handler Registration
application.add_handler(CommandHandler("bal", balance_cmd, block=False))

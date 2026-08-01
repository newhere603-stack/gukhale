from datetime import datetime
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler
from shivu import application, sudo_users_collection

# Aapki Master Owner ID
OWNER_ID = 7657218453


# Helper Function to convert Normal Text to Small Caps
def to_small_caps(text: str) -> str:
    if not text:
        return ""
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small = "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ"
    trans = str.maketrans(normal, small)
    return str(text).translate(trans)


# Owner Validation Function
def is_owner(user_id: int) -> bool:
    try:
        return int(user_id) == int(OWNER_ID)
    except Exception:
        return False


# 1. ADD SUDO COMMAND (Silent for non-owners)
async def addsudo_cmd(update: Update, context: CallbackContext):
    msg, user = update.effective_message, update.effective_user

    # Owner ke alawa koi aur chalaye toh Silent Ignore
    if not user or not is_owner(user.id):
        return

    target_id = None
    target_name = "Sudo User"
    target_username = "unknown"

    # Reply Check
    if msg.reply_to_message:
        target = msg.reply_to_message.from_user
        target_id = target.id
        target_name = target.first_name or "Sudo User"
        target_username = target.username or "unknown"
    # ID Check (e.g. /addsudo 12345678)
    elif context.args and context.args[0].isdigit():
        target_id = int(context.args[0])
        try:
            chat = await context.bot.get_chat(target_id)
            target_name = chat.first_name or "Sudo User"
            target_username = chat.username or "unknown"
        except Exception:
            pass
    else:
        err_text = f"<b>{to_small_caps('REPLY TO A USER MESSAGE OR GIVE USER ID TO ADD THEM AS SUDO.')}\n{to_small_caps('EXAMPLE: /ADDSUDO 12345678')}</b>"
        return await msg.reply_text(err_text, parse_mode="HTML")

    await sudo_users_collection.update_one(
        {"id": target_id},
        {
            "$set": {
                "id": target_id,
                "username": target_username,
                "first_name": target_name,
                "added_on": datetime.utcnow(),
            }
        },
        upsert=True,
    )

    success_text = f"<b>{to_small_caps('ADDED')} <a href='tg://user?id={target_id}'>{to_small_caps(target_name)}</a> {to_small_caps('AS SUDO USER.')}</b>"
    await msg.reply_html(success_text)


# 2. REMOVE SUDO COMMAND (Silent for non-owners)
async def removesudo_cmd(update: Update, context: CallbackContext):
    msg, user = update.effective_message, update.effective_user

    if not user or not is_owner(user.id):
        return

    target_id = None

    if msg.reply_to_message:
        target_id = msg.reply_to_message.from_user.id
    elif context.args and context.args[0].isdigit():
        target_id = int(context.args[0])
    else:
        err_text = f"<b>{to_small_caps('REPLY TO A SUDO USER MESSAGE OR PROVIDE ID TO REMOVE THEM.')}\n{to_small_caps('EXAMPLE: /REMOVESUDO 12345678')}</b>"
        return await msg.reply_text(err_text, parse_mode="HTML")

    if is_owner(target_id):
        err_text = (
            f"<b>{to_small_caps('YOU CANNOT REMOVE THE MAIN OWNER!')}</b>"
        )
        return await msg.reply_text(err_text, parse_mode="HTML")

    deleted_res = await sudo_users_collection.delete_one({"id": target_id})

    if deleted_res.deleted_count > 0:
        res_text = f"<b>{to_small_caps('REMOVED USER')} <code>{target_id}</code> {to_small_caps('FROM SUDO LIST.')}</b>"
        await msg.reply_html(res_text)
    else:
        res_text = f"<b>{to_small_caps('USER NOT FOUND IN SUDO DATABASE.')}</b>"
        await msg.reply_text(res_text, parse_mode="HTML")


# 3. SUDO LIST COMMAND (Silent for non-owners)
async def sudolist_cmd(update: Update, context: CallbackContext):
    msg, user = update.effective_message, update.effective_user

    if not user or not is_owner(user.id):
        return

    users = await sudo_users_collection.find().to_list(length=None)

    owner_title = to_small_caps("ＩＭ 𖣘 ＵＣＨＩＨＡ (OWNER)")
    text = f"1. <a href='tg://user?id={OWNER_ID}'>{owner_title}</a>\n"
    count = 2

    if users:
        for u in users:
            u_id = u.get("id")
            if not is_owner(u_id):
                u_name = to_small_caps(u.get("first_name", "SUDO USER"))
                text += f"{count}. <a href='tg://user?id={u_id}'>{u_name}</a>\n"
                count += 1

    header = to_small_caps("SUDO OWNERS LIST:")
    await msg.reply_html(f"<b>{header}</b>\n\n<b>{text}</b>")


application.add_handler(CommandHandler("addsudo", addsudo_cmd))
application.add_handler(CommandHandler("removesudo", removesudo_cmd))
application.add_handler(CommandHandler("sudoremove", removesudo_cmd))
application.add_handler(CommandHandler("sudolist", sudolist_cmd))

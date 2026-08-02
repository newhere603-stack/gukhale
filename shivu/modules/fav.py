import asyncio
from html import escape
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler
from shivu import LOGGER, application, user_collection


# Small Caps Font Converter Helper
def to_small_caps(text: str) -> str:
    if not text:
        return ""
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small = "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ"
    trans = str.maketrans(normal, small)
    return str(text).translate(trans)


# Safe Async MongoDB Helper Functions
async def get_user_data(user_id: int):
    return await user_collection.find_one({"id": user_id})


async def update_user_fav(user_id: int, character: dict):
    return await user_collection.update_one(
        {"id": user_id}, {"$set": {"favorites": character}}, upsert=True
    )


# 1. /fav Command Handler
async def fav(update: Update, context: CallbackContext) -> None:
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id

    if not context.args:
        msg = f"<b>{to_small_caps('PLEASE PROVIDE A CHARACTER ID. EXAMPLE: /FAV 1')}</b>"
        await update.message.reply_text(msg, parse_mode="HTML")
        return

    character_id = str(context.args[0]).strip()

    try:
        user = await get_user_data(user_id)

        if (
            not user
            or "characters" not in user
            or not isinstance(user["characters"], list)
        ):
            msg = f"<b>{to_small_caps('YOU HAVE NO CHARACTERS IN YOUR COLLECTION!')}</b>"
            await update.message.reply_text(msg, parse_mode="HTML")
            return

        character = None
        for c in user.get("characters", []):
            if isinstance(c, dict) and str(c.get("id")) == character_id:
                character = c
                break

        if not character:
            msg = f"<b>{to_small_caps('CHARACTER NOT FOUND IN YOUR COLLECTION!')}</b>"
            await update.message.reply_text(msg, parse_mode="HTML")
            return

        buttons = [
            [
                InlineKeyboardButton(
                    "🟢 ʏᴇs", callback_data=f"fvc_{user_id}_{character_id}"
                ),
                InlineKeyboardButton("🔴 ɴᴏ", callback_data=f"fvx_{user_id}"),
            ]
        ]

        char_name = str(character.get("name", "Unknown"))
        anime_name = str(character.get("anime", "Unknown"))

        # Heading & Text in Bold Small Caps
        heading = to_small_caps(
            "ARE YOU SURE YOU WANT TO MAKE THIS WAIFU YOU FAVOURITE?"
        )
        small_char_name = to_small_caps(char_name)
        small_anime_name = to_small_caps(anime_name)

        caption = (
            f"<b>{heading}</b>\n"
            f"⤿ <b>{escape(small_char_name)}</b> ↷\n(<b>{escape(small_anime_name)}</b>)"
        )

        media_url = character.get("img_url")

        if character.get("is_video", False):
            await update.message.reply_video(
                video=media_url,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="HTML",
                supports_streaming=True,
            )
        else:
            await update.message.reply_photo(
                photo=media_url,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="HTML",
            )

    except Exception as e:
        LOGGER.error(f"Fav Command Error: {e}")
        err_msg = f"<b>{to_small_caps('AN INTERNAL ERROR OCCURRED WHILE PROCESSING /FAV.')}</b>"
        await update.message.reply_text(err_msg, parse_mode="HTML")


# 2. Callback Query Handler (YES / NO Pop-up)
async def handle_fav_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if not query:
        return

    try:
        data = query.data
        if not data or not (data.startswith("fvc_") or data.startswith("fvx_")):
            return

        parts = data.split("_")
        action = parts[0]

        if action == "fvc":
            if len(parts) < 3:
                pop_err = to_small_caps("INVALID REQUEST DATA!")
                await query.answer(pop_err, show_alert=True)
                return

            req_user_id = int(parts[1])
            character_id = str(parts[2])

            if query.from_user.id != req_user_id:
                pop_err = to_small_caps("THIS IS NOT YOUR REQUEST!")
                await query.answer(pop_err, show_alert=True)
                return

            user = await get_user_data(req_user_id)
            if not user or "characters" not in user:
                pop_err = to_small_caps("USER COLLECTION NOT FOUND!")
                await query.answer(pop_err, show_alert=True)
                return

            character = None
            for c in user.get("characters", []):
                if isinstance(c, dict) and str(c.get("id")) == character_id:
                    character = c
                    break

            if not character:
                pop_err = to_small_caps("CHARACTER NOT FOUND!")
                await query.answer(pop_err, show_alert=True)
                return

            await update_user_fav(req_user_id, character)

            pop_up_text = to_small_caps("DONE! MADE IT YOUR FAVOURITE")
            await query.answer(pop_up_text, show_alert=True)

            # Message Delete on YES
            if query.message:
                await query.message.delete()

        elif action == "fvx":
            req_user_id = int(parts[1])

            if query.from_user.id != req_user_id:
                pop_err = to_small_caps("THIS IS NOT YOUR REQUEST!")
                await query.answer(pop_err, show_alert=True)
                return

            cancel_text = to_small_caps("CANCELLED!")
            await query.answer(cancel_text, show_alert=True)

            # Message Delete on NO
            if query.message:
                await query.message.delete()

    except Exception as e:
        LOGGER.error(f"Fav Callback Error: {e}")
        pop_err = to_small_caps("ERROR OCCURRED!")
        await query.answer(pop_err, show_alert=True)


# Application Handlers
application.add_handler(CommandHandler("fav", fav))
application.add_handler(
    CallbackQueryHandler(handle_fav_callback, pattern="^fv[cx]_")
)

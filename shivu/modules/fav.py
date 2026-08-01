from html import escape
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler
from shivu import LOGGER, application, user_collection


# Small Caps Font Converter Helper Function
def to_small_caps(text: str) -> str:
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small = "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ"
    trans = str.maketrans(normal, small)
    return str(text).translate(trans)


async def fav(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Provide character ID")
        return

    character_id = str(context.args[0])

    try:
        user = await user_collection.find_one({"id": user_id})
        if not user:
            await update.message.reply_text("You have no characters")
            return

        character = next(
            (
                c
                for c in user.get("characters", [])
                if str(c.get("id")) == character_id
            ),
            None,
        )

        if not character:
            await update.message.reply_text("Character not in your collection")
            return

        # Small Caps Emojis & Buttons
        buttons = [
            [
                InlineKeyboardButton(
                    "🟢 YES", callback_data=f"fvc_{user_id}_{character_id}"
                ),
                InlineKeyboardButton("🔴 NO", callback_data=f"fvx_{user_id}"),
            ]
        ]

        # Fetch Name & Anime
        char_name = character.get("name", "Unknown")
        anime_name = character.get("anime", "Unknown")

        # Convert everything to Small Caps
        heading = to_small_caps("ARE YOU SURE YOU WANT TO MAKE THIS WAIFU YOU FAVOURITE?")
        small_char_name = to_small_caps(char_name)
        small_anime_name = to_small_caps(anime_name)

        # Photo 1 ki tarah exact text + Name + Anime in Small Caps
        caption = (
            f"<b>{heading}</b>\n"
            f"↳ <b>{escape(small_char_name)}</b> [ 🚪 ] (<b>{escape(small_anime_name)}</b>)"
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
        LOGGER.error(f"Fav error: {e}")
        await update.message.reply_text("Error occurred")


async def handle_fav_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query

    try:
        data = query.data

        if not (data.startswith("fvc_") or data.startswith("fvx_")):
            return

        parts = data.split("_", 2)
        if len(parts) < 2:
            await query.answer("Invalid data", show_alert=True)
            return

        action = parts[0]

        if action == "fvc":
            if len(parts) != 3:
                await query.answer("Invalid data", show_alert=True)
                return

            user_id = int(parts[1])
            character_id = str(parts[2])

            if query.from_user.id != user_id:
                await query.answer("Not your request", show_alert=True)
                return

            user = await user_collection.find_one({"id": user_id})
            if not user:
                await query.answer("User not found", show_alert=True)
                return

            character = next(
                (
                    c
                    for c in user.get("characters", [])
                    if str(c.get("id")) == character_id
                ),
                None,
            )

            if not character:
                await query.answer("Character not found", show_alert=True)
                return

            await user_collection.update_one(
                {"id": user_id}, {"$set": {"favorites": character}}
            )

            # Photo 2 ke exact pop-up formatting (Small Caps Text)
            pop_up_text = to_small_caps("DONE! MADE IT YOUR FAVOURITE")
            await query.answer(pop_up_text, show_alert=True)

        elif action == "fvx":
            user_id = int(parts[1])

            if query.from_user.id != user_id:
                await query.answer("Not your request", show_alert=True)
                return

            cancel_text = to_small_caps("CANCELLED!")
            await query.answer(cancel_text, show_alert=True)
            await query.message.delete()

    except Exception as e:
        LOGGER.error(f"Callback error: {e}")
        await query.answer(f"Error: {str(e)[:100]}", show_alert=True)


application.add_handler(CommandHandler("fav", fav, block=False))
application.add_handler(
    CallbackQueryHandler(handle_fav_callback, pattern="^fv[cx]_", block=False)
)

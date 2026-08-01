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


# 1. /fav Command Handler
async def fav(update: Update, context: CallbackContext) -> None:
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id

    # Arguments Check
    if not context.args:
        await update.message.reply_text("Please provide a Character ID. Example: /fav 1")
        return

    character_id = str(context.args[0]).strip()

    try:
        # Safe Database Retrieval
        user = await user_collection.find_one({"id": user_id})
        
        if not user or "characters" not in user or not isinstance(user["characters"], list):
            await update.message.reply_text("You have no characters in your collection!")
            return

        # Find character safely without throwing KeyError
        character = None
        for c in user.get("characters", []):
            if isinstance(c, dict) and str(c.get("id")) == character_id:
                character = c
                break

        if not character:
            await update.message.reply_text("Character not found in your collection!")
            return

        # Prepare Inline Keyboard Buttons
        buttons = [
            [
                InlineKeyboardButton(
                    "🟢 YES", callback_data=f"fvc_{user_id}_{character_id}"
                ),
                InlineKeyboardButton("🔴 NO", callback_data=f"fvx_{user_id}"),
            ]
        ]

        char_name = str(character.get("name", "Unknown"))
        anime_name = str(character.get("anime", "Unknown"))

        # Small Caps Conversion
        heading = to_small_caps("ARE YOU SURE YOU WANT TO MAKE THIS WAIFU YOU FAVOURITE?")
        small_char_name = to_small_caps(char_name)
        small_anime_name = to_small_caps(anime_name)

        caption = (
            f"<b>{heading}</b>\n"
            f"↳ <b>{escape(small_char_name)}</b> [ 🚪 ] (<b>{escape(small_anime_name)}</b>)"
        )

        media_url = character.get("img_url")

        # Media Reply Logic
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
        await update.message.reply_text("An internal error occurred while processing /fav.")


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
                await query.answer("Invalid request data!", show_alert=True)
                return

            req_user_id = int(parts[1])
            character_id = str(parts[2])

            # Validation: Restrict button click to original requester
            if query.from_user.id != req_user_id:
                await query.answer("This is not your request!", show_alert=True)
                return

            user = await user_collection.find_one({"id": req_user_id})
            if not user or "characters" not in user:
                await query.answer("User collection not found!", show_alert=True)
                return

            character = None
            for c in user.get("characters", []):
                if isinstance(c, dict) and str(c.get("id")) == character_id:
                    character = c
                    break

            if not character:
                await query.answer("Character not found!", show_alert=True)
                return

            # Safe Database Update for Favorites
            await user_collection.update_one(
                {"id": req_user_id},
                {"$set": {"favorites": character}},
                upsert=True
            )

            # Exact Pop-Up Confirmation Box in Small Caps
            pop_up_text = to_small_caps("DONE! MADE IT YOUR FAVOURITE")
            await query.answer(pop_up_text, show_alert=True)

        elif action == "fvx":
            req_user_id = int(parts[1])

            if query.from_user.id != req_user_id:
                await query.answer("This is not your request!", show_alert=True)
                return

            cancel_text = to_small_caps("CANCELLED!")
            await query.answer(cancel_text, show_alert=True)
            
            if query.message:
                await query.message.delete()

    except Exception as e:
        LOGGER.error(f"Fav Callback Error: {e}")
        await query.answer(f"Error: {str(e)[:50]}", show_alert=True)


# Application Handlers
application.add_handler(CommandHandler("fav", fav, block=False))
application.add_handler(
    CallbackQueryHandler(handle_fav_callback, pattern="^fv[cx]_", block=False)
)

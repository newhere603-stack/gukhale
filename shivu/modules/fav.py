import asyncio
from html import escape
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler
from shivu import LOGGER, application, user_collection, db

# Global collection image fetch ke liye
collection = db['anime_characters_lol']

def to_small_caps(text: str) -> str:
    if not text: return ""
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small = "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ"
    return str(text).translate(str.maketrans(normal, small))

async def get_user_data(user_id: int):
    return await user_collection.find_one({"id": user_id})

async def update_user_fav(user_id: int, character: dict):
    return await user_collection.update_one({"id": user_id}, {"$set": {"favorites": character}}, upsert=True)

# 1. /fav Command Handler
async def fav(update: Update, context: CallbackContext) -> None:
    if not update.effective_user or not update.message: return
    user_id = update.effective_user.id

    if not context.args:
        return await update.message.reply_text(f"<b>{to_small_caps('PLEASE PROVIDE A CHARACTER ID. EXAMPLE: /FAV 1')}</b>", parse_mode="HTML")

    character_id = str(context.args[0]).strip()
    req_id_clean = character_id.lstrip('0') or '0'

    try:
        user = await get_user_data(user_id)
        if not user or "characters" not in user or not isinstance(user["characters"], list):
            return await update.message.reply_text(f"<b>{to_small_caps('YOU HAVE NO CHARACTERS IN YOUR COLLECTION!')}</b>", parse_mode="HTML")

        character = None
        for c in user.get("characters", []):
            if isinstance(c, dict):
                if (str(c.get("id", "")).strip().lstrip('0') or '0') == req_id_clean:
                    character = c.copy()
                    break

        if not character:
            return await update.message.reply_text(f"<b>{to_small_caps('CHARACTER NOT FOUND IN YOUR COLLECTION!')}</b>", parse_mode="HTML")

        # Original image ke liye DB fetch
        q_ids = [character_id, req_id_clean]
        if req_id_clean.isdigit():
            val = int(req_id_clean)
            q_ids.extend([val, f"{val:02d}", f"{val:03d}", f"{val:04d}"])

        global_char = await collection.find_one({"id": {"$in": q_ids}, "img_url": {"$nin": [None, ""]}})
        if global_char:
            character['img_url'] = global_char.get('img_url')
            character['is_video'] = global_char.get('is_video', False)
            character['name'] = global_char.get('name', character.get('name'))
            character['anime'] = global_char.get('anime', character.get('anime'))

        buttons = [[InlineKeyboardButton("🟢 ʏᴇs", callback_data=f"fvc_{user_id}_{character_id}"), InlineKeyboardButton("🔴 ɴᴏ", callback_data=f"fvx_{user_id}")]]
        char_name = str(character.get("name", "Unknown"))
        anime_name = str(character.get("anime", "Unknown"))
        
        caption = f"<b>{to_small_caps('ARE YOU SURE YOU WANT TO MAKE THIS WAIFU YOUR FAVOURITE?')}</b>\n\n⤿ <b>{escape(to_small_caps(char_name))}</b> ↷\n(<b>{escape(to_small_caps(anime_name))}</b>)"
        media_url = character.get("img_url")

        if not media_url:
            return await update.message.reply_text(text=caption + f"\n\n<b>⚠️ {to_small_caps('IMAGE NOT FOUND IN DATABASE')}</b>", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

        if character.get("is_video", False):
            await update.message.reply_video(video=media_url, caption=caption, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML", supports_streaming=True)
        else:
            await update.message.reply_photo(photo=media_url, caption=caption, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

    except Exception as e:
        LOGGER.error(f"Fav Command Error: {e}")
        await update.message.reply_text(f"<b>{to_small_caps('AN INTERNAL ERROR OCCURRED.')}</b>", parse_mode="HTML")

# 2. Callback Query Handler
async def handle_fav_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if not query: return

    try:
        data = query.data
        if not data or not (data.startswith("fvc_") or data.startswith("fvx_")): return
        parts = data.split("_")
        action = parts[0]

        if action == "fvc":
            req_user_id = int(parts[1])
            character_id = str(parts[2])
            req_id_clean = character_id.lstrip('0') or '0'

            if query.from_user.id != req_user_id:
                return await query.answer(to_small_caps("THIS IS NOT YOUR REQUEST!"), show_alert=True)

            user = await get_user_data(req_user_id)
            if not user or "characters" not in user:
                return await query.answer(to_small_caps("USER COLLECTION NOT FOUND!"), show_alert=True)

            character = None
            for c in user.get("characters", []):
                if isinstance(c, dict):
                    if (str(c.get("id", "")).strip().lstrip('0') or '0') == req_id_clean:
                        character = c.copy()
                        break

            if not character:
                return await query.answer(to_small_caps("CHARACTER NOT FOUND!"), show_alert=True)

            q_ids = [character_id, req_id_clean]
            if req_id_clean.isdigit():
                val = int(req_id_clean)
                q_ids.extend([val, f"{val:02d}", f"{val:03d}", f"{val:04d}"])

            global_char = await collection.find_one({"id": {"$in": q_ids}})
            if global_char:
                character['img_url'] = global_char.get('img_url')
                character['is_video'] = global_char.get('is_video', False)
                character['name'] = global_char.get('name', character.get('name'))
                character['anime'] = global_char.get('anime', character.get('anime'))

            await update_user_fav(req_user_id, character)
            await query.answer(to_small_caps("DONE! MADE IT YOUR FAVOURITE"), show_alert=True)
            if query.message: await query.message.delete()

        elif action == "fvx":
            req_user_id = int(parts[1])
            if query.from_user.id != req_user_id:
                return await query.answer(to_small_caps("THIS IS NOT YOUR REQUEST!"), show_alert=True)
            await query.answer(to_small_caps("CANCELLED!"), show_alert=True)
            if query.message: await query.message.delete()

    except Exception as e:
        LOGGER.error(f"Fav Callback Error: {e}")
        await query.answer(to_small_caps("ERROR OCCURRED!"), show_alert=True)

application.add_handler(CommandHandler("fav", fav))
application.add_handler(CallbackQueryHandler(handle_fav_callback, pattern="^fv[cx]_"))

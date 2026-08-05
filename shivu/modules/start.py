import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from shivu import (
    BOT_USERNAME,
    LOGGER,
    SUPPORT_CHAT,
    UPDATE_CHAT,
    application,
    sudo_users_collection,
    user_collection,
)

START_VIDEO = "https://graph.org/file/e668451eba24048fe880c-8cefbbe834e0f673d8.mp4"
FORCE_SUB_CHAT = "anime_group_hai"
OWNER_ID = 7657218453  # Aapki Master Owner ID

MAIN_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton(
            "sᴜᴘᴘᴏʀᴛ", url=f"https://t.me/{SUPPORT_CHAT}"
        ),
        InlineKeyboardButton(
            "ᴜᴘᴅᴀᴛᴇs", url=f"https://t.me/{UPDATE_CHAT}"
        ),
    ],
    [
        InlineKeyboardButton(
            "sᴛᴀʀᴛ ɢᴜᴇssɪɴɢ💫",
            url=f"https://t.me/{BOT_USERNAME}?startgroup=new",
        )
    ],
    [
        InlineKeyboardButton("ʜᴇʟᴘ", callback_data="sxc_help"),
        InlineKeyboardButton("ᴄʀᴇᴅɪᴛs", callback_data="sxc_credits"),
    ],
])

FORCE_SUB_TEXT = "🔒 <b>ʟᴇᴛ's ɢᴏ ʙᴀʙʏ ᴊᴏɪɴ ᴏᴜʀ ᴜᴘᴅᴀᴛᴇs ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴍᴇ!</b>"
FORCE_SUB_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton(
            "ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ", url=f"https://t.me/{FORCE_SUB_CHAT}"
        )
    ],
    [InlineKeyboardButton("ᴛʀʏ ᴀɢᴀɪɴ", callback_data="sxc_checksub")],
])

PAGE_SIZE = 6

CATEGORIES = {
    "basic": (
        "ʙᴀsɪᴄ ᴄᴏᴍᴍᴀɴᴅs",
        [
            ("/start", "sᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ"),
            ("/grab", "ɢʀᴀʙ ᴛʜᴇ ᴄʜᴀʀᴀᴄᴛᴇʀ"),
            ("/fav", "ᴀᴅᴅ ᴀ ᴄʜᴀʀᴀᴄᴛᴇʀ ᴛᴏ ʏᴏᴜʀ ғᴀᴠᴏᴜʀɪᴛᴇ"),
            ("/claim", "ᴄʟᴀɪᴍ ʏᴏᴜʀ ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ"),
            ("/pay", "ɢɪᴠᴇ ᴄᴏɪɴs ᴛᴏ ᴏᴛʜᴇʀ ᴜsᴇʀs"),
            ("/bal", "sᴇᴇ ʏᴏᴜʀ ʙᴀʟᴀɴᴄᴇ"),
            ("/harem", "sᴇᴇ ʏᴏᴜʀ ᴄʜᴀʀᴀᴄᴛᴇʀ's ᴄᴏʟʟᴇᴄᴛɪᴏɴ"),
            ("/gift", "ɢɪғᴛ ʏᴏᴜʀ ᴡᴀɪғᴜ ᴛᴏ sᴏᴍᴇᴏɴᴇ"),
            ("/trade", "ᴛʀᴀᴅᴇ ᴄʜᴀʀᴀᴄᴛᴇʀs ʙᴇᴛᴡᴇᴇɴ ᴜsᴇʀs"),
            ("/top", "ᴠɪᴇᴡ ᴛʜᴇ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ"),
            ("/sprofile", "ᴠɪᴇᴡ ʏᴏᴜʀ ᴘʀᴏғɪʟᴇ"),
            (
                "/changetime",
                "ᴄʜᴀɴɢᴇ ᴛʜᴇ sᴘᴀᴡɴ ᴛɪᴍᴇ ᴏғ ᴄʜᴀʀᴀᴄᴛᴇʀs [ᴏᴡɴᴇʀ/ᴀᴅᴍɪɴs]",
            ),
        ],
    ),
    "interactive": (
        "ɪɴᴛᴇʀᴀᴄᴛɪᴠᴇ ᴄᴏᴍᴍᴀɴᴅs",
        [
            ("/claim", "ᴄʟᴀɪᴍ ʏᴏᴜʀ ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ"),
            ("/roll", "ɢᴀᴍʙʟᴇ ʏᴏᴜʀ ɢᴏʟᴅ"),
            ("/games", "ᴘʟᴀʏ ɢᴀᴍᴇs"),
        ],
    ),
    "sudo": (
        "sᴜᴅᴏ ᴄᴏᴍᴍᴀɴᴅs",
        [
            ("/broadcast", "ʙʀᴏᴀᴅᴄᴀsᴛ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴀʟʟ ᴜsᴇʀs"),
            ("/addsudo", "ᴀᴅᴅ ᴀ sᴜᴅᴏ ᴜsᴇʀ"),
            ("/removesudo", "ʀᴇᴍᴏᴠᴇ ᴀ sᴜᴅᴏ ᴜsᴇʀ"),
            ("/sudolist", "ᴠɪᴇᴡ sᴜᴅᴏ ᴜsᴇʀs ʟɪsᴛ"),
            ("/ban", "ʙᴀɴ ᴀ ᴜsᴇʀ ғʀᴏᴍ ᴛʜᴇ ʙᴏᴛ"),
            ("/unban", "ᴜɴʙᴀɴ ᴀ ᴜsᴇʀ"),
            ("/stats", "ᴠɪᴇᴡ ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs"),
        ],
    ),
}


# Dynamic Caption Generator with User Mention
def get_main_caption(user_id: int, first_name: str) -> str:
    user_mention = f'<a href="tg://user?id={user_id}">{first_name}</a>'
    return (
        f"<b>✨ Hᴇʏ {user_mention},🎀\nɪ'ᴍ ᴀʟɪꜱᴀ ᴡᴀɪꜰᴜ ʙᴏᴛ, ʏᴏᴜʀ ᴜʟᴛɪᴍᴀᴛᴇ ᴀɴɪᴍᴇ ᴀᴅᴠᴇɴᴛᴜʀᴇ ᴄᴏᴍᴘᴀɴɪᴏɴ.😈</b>\n\n"
        f"<b>ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ ᴀɴᴅ ʟᴇᴛ ᴛʜᴇ ғᴜɴ ʙᴇɢɪɴ!⚡</b>"
    )


# Robust Force Sub Checker (Supports Groups Bypass & API Error Handling)
async def is_force_sub_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        # Group chats me force sub check mat karo
        if update.effective_chat and update.effective_chat.type != ChatType.PRIVATE:
            return True

        user_id = update.effective_user.id
        chat_identifier = (
            f"@{FORCE_SUB_CHAT}"
            if not str(FORCE_SUB_CHAT).startswith("@")
            and not str(FORCE_SUB_CHAT).startswith("-100")
            else FORCE_SUB_CHAT
        )

        member = await context.bot.get_chat_member(
            chat_id=chat_identifier, user_id=user_id
        )
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

    except BadRequest as e:
        LOGGER.warning(f"Force-sub BadRequest for user: {e}")
        return True  # Error hone par allow kar do
    except Exception as e:
        LOGGER.error(f"Force-sub error: {e}")
        return True


def menu_view():
    kb = [
        [
            InlineKeyboardButton(
                "ʙᴀsɪᴄ", callback_data="sxc_cat_basic"
            ),
            InlineKeyboardButton(
                "ɪɴᴛᴇʀᴀᴄᴛɪᴠᴇ", callback_data="sxc_cat_interactive"
            ),
        ],
        [InlineKeyboardButton("🌿 sᴜᴅᴏ", callback_data="sxc_cat_sudo")],
        [InlineKeyboardButton("ᴍᴀɪɴ ᴍᴇɴᴜ", callback_data="sxc_back")],
    ]
    return (
        "<b>ʜᴇʟᴘ ᴍᴇɴᴜ</b>\n\n<b>sᴇʟᴇᴄᴛ ᴀ ᴄᴀᴛᴇɢᴏʀʏ ᴛᴏ ᴠɪᴇᴡ ᴄᴏᴍᴍᴀɴᴅs:</b>",
        InlineKeyboardMarkup(kb),
    )


def category_view(cat_key: str, page: int = 1):
    title, commands = CATEGORIES[cat_key]
    total_pages = max(1, -(-len(commands) // PAGE_SIZE))
    page = max(1, min(page, total_pages))
    chunk = commands[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]

    text = f"<b>{title}</b> `[{page}/{total_pages}]`\n\n" + "\n".join(
        f"• <code>{cmd}</code> - <b>{desc}</b>" for cmd, desc in chunk
    )

    nav = []
    if page > 1:
        nav.append(
            InlineKeyboardButton(
                "ᴘʀᴇᴠɪᴏᴜs", callback_data=f"sxc_pg_{cat_key}_{page - 1}"
            )
        )
    if page < total_pages:
        nav.append(
            InlineKeyboardButton(
                "ɴᴇxᴛ", callback_data=f"sxc_pg_{cat_key}_{page + 1}"
            )
        )

    kb = ([nav] if nav else []) + [
        [InlineKeyboardButton("⟲ ʙᴀᴄᴋ ᴛᴏ ᴍᴇɴᴜ", callback_data="sxc_menu")]
    ]
    return text, InlineKeyboardMarkup(kb)


# Dynamic Credits View Fetching Owner & Sudo Users Directly from Database
async def credits_view(context: ContextTypes.DEFAULT_TYPE):
    kb = []
    added_ids = set()

    # 1. First add Main Owner Always
    try:
        owner_chat = await context.bot.get_chat(OWNER_ID)
        owner_name = owner_chat.first_name or "ＩＭ 𖣘 ＵＣＨＩＨＡ"
    except Exception:
        owner_name = "ＩＭ 𖣘 ＵＣＨＩＨＡ"

    kb.append([InlineKeyboardButton(f"{owner_name}", url=f"tg://user?id={OWNER_ID}")])
    added_ids.add(OWNER_ID)

    # 2. Database se baki sabhi Sudo Users fetch honge
    sudo_users = await sudo_users_collection.find().to_list(length=None)

    if sudo_users:
        for u in sudo_users:
            u_id = u.get("id")
            if u_id not in added_ids:
                name = u.get("first_name", "Sudo User")
                url = f"tg://user?id={u_id}"
                kb.append([InlineKeyboardButton(f"{name}", url=url)])
                added_ids.add(u_id)

    kb.append([InlineKeyboardButton("⟲ ʙᴀᴄᴋ", callback_data="sxc_back")])
    return "<b>sᴜᴅᴏ:✅</b>", InlineKeyboardMarkup(kb)


def _new_user_doc(user_id, first_name, username):
    return {
        "id": user_id,
        "first_name": first_name,
        "username": username,
        "balance": 5000,
        "bot_started": True,  # Yaha flag add kiya gaya hai
        "characters": [],
        "pass_data": {
            "tier": "free",
            "weekly_claims": 0,
            "last_weekly_claim": None,
            "streak_count": 0,
            "last_streak_claim": None,
            "tasks": {"weekly_claims": 0, "grabs": 0},
            "mythic_unlocked": False,
            "premium_expires": None,
            "elite_expires": None,
            "pending_elite_payment": None,
        },
    }


async def _ensure_user(user_id, first_name, username):
    try:
        user_data = await user_collection.find_one({"id": user_id})
        if user_data:
            # Profile pehle se hai to update set me bot_started True kar do
            await user_collection.update_one(
                {"id": user_id},
                {"$set": {"first_name": first_name, "username": username, "bot_started": True}},
            )
            return False
        await user_collection.insert_one(
            _new_user_doc(user_id, first_name, username)
        )
        return True
    except Exception as e:
        LOGGER.error(f"Error in _ensure_user DB query: {e}")
        return False


async def safe_track_bot_start(user_id, first_name, username, is_new_user):
    try:
        from shivu.modules.chatlog import track_bot_start

        await asyncio.wait_for(
            track_bot_start(user_id, first_name, username, is_new_user),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        LOGGER.warning(f"track_bot_start timed out for user {user_id}")
    except ImportError:
        LOGGER.warning(
            "chatlog module not available, skipping bot start tracking"
        )
    except Exception as e:
        LOGGER.error(f"Error in safe_track_bot_start: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update or not update.effective_user or not update.effective_chat:
            return

        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        first_name = update.effective_user.first_name or "User"
        username = update.effective_user.username or ""

        # Safe FSub Check
        if not await is_force_sub_member(update, context):
            await context.bot.send_message(
                chat_id=chat_id,
                text=FORCE_SUB_TEXT,
                parse_mode=ParseMode.HTML,
                reply_markup=FORCE_SUB_KEYBOARD,
            )
            return

        is_new = await _ensure_user(user_id, first_name, username)

        if hasattr(context.application, "create_task"):
            context.application.create_task(
                safe_track_bot_start(user_id, first_name, username, is_new)
            )
        else:
            asyncio.create_task(
                safe_track_bot_start(user_id, first_name, username, is_new)
            )

        caption_text = get_main_caption(user_id, first_name)

        # Direct message send (Bina user message ko reply tag kiye)
        await context.bot.send_video(
            chat_id=chat_id,
            video=START_VIDEO,
            caption=caption_text,
            reply_markup=MAIN_KEYBOARD,
            parse_mode=ParseMode.HTML,
            supports_streaming=True,
        )

    except Exception as e:
        LOGGER.error(f"Critical error in start command: {e}", exc_info=True)
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ <b>ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.</b>",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception as e:
        LOGGER.error(f"Error answering callback query: {e}")
        return

    try:
        data = query.data
        user_id = query.from_user.id
        first_name = query.from_user.first_name or "User"
        username = query.from_user.username or ""

        if data == "sxc_checksub":
            if not await is_force_sub_member(update, context):
                await query.answer(
                    "ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴊᴏɪɴᴇᴅ ʏᴇᴛ!", show_alert=True
                )
                return
            await _ensure_user(user_id, first_name, username)
            try:
                await query.message.delete()
            except Exception:
                pass
            
            caption_text = get_main_caption(user_id, first_name)
            await context.bot.send_video(
                chat_id=user_id,
                video=START_VIDEO,
                caption=caption_text,
                reply_markup=MAIN_KEYBOARD,
                parse_mode=ParseMode.HTML,
                supports_streaming=True,
            )
            return

        if not await is_force_sub_member(update, context):
            await query.answer("ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ ғɪʀsᴛ!", show_alert=True)
            return

        await _ensure_user(user_id, first_name, username)

        if data == "sxc_credits":
            text, markup = await credits_view(context)
        elif data in ("sxc_help", "sxc_menu"):
            text, markup = menu_view()
        elif data.startswith("sxc_cat_"):
            cat_key = data[len("sxc_cat_") :]
            if cat_key not in CATEGORIES:
                await query.answer("⚠️ Unknown category", show_alert=True)
                return
            text, markup = category_view(cat_key)
        elif data.startswith("sxc_pg_"):
            cat_key, _, page_str = data[len("sxc_pg_") :].rpartition("_")
            if cat_key not in CATEGORIES or not page_str.isdigit():
                await query.answer("⚠️ Unknown page", show_alert=True)
                return
            text, markup = category_view(cat_key, int(page_str))
        elif data == "sxc_back":
            text, markup = get_main_caption(user_id, first_name), MAIN_KEYBOARD
        elif data == "sxc_none":
            await query.answer("No sudo users added yet!", show_alert=True)
            return
        else:
            return

        await query.edit_message_caption(
            caption=text, parse_mode=ParseMode.HTML, reply_markup=markup
        )

    except Exception as e:
        LOGGER.error(f"Error in button callback: {e}", exc_info=True)
        try:
            await query.answer(
                "⚠️ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.", show_alert=True
            )
        except Exception:
            pass


application.add_handler(CommandHandler("start", start, block=False))
application.add_handler(
    CallbackQueryHandler(button_callback, pattern=r"^sxc_", block=False)
)

LOGGER.info("✓ Start module loaded successfully")

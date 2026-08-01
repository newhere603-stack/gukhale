import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler
from shivu import application, SUPPORT_CHAT, UPDATE_CHAT, BOT_USERNAME, LOGGER, user_collection

START_VIDEO = "https://graph.org/file/e668451eba24048fe880c-8cefbbe834e0f673d8.mp4"
FORCE_SUB_CHAT = "anime_group_hai"

# Small Caps + Bold Text for Main Caption
MAIN_CAPTION = (
    f"<b>✨ ʜᴇʏ ᴛʜᴇʀᴇ! ɪ'ᴍ ᴀʟɪꜱᴀ ᴡᴀɪꜰᴜ ʙᴏᴛ, ʏᴏᴜʀ ᴜʟᴛɪᴍᴀᴛᴇ ᴀɴɪᴍᴇ ᴀᴅᴠᴇɴᴛᴜʀᴇ ᴄᴏᴍᴘᴀɴɪᴏɴ.</b>\n\n"
    f"<b>ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ ᴀɴᴅ ʟᴇᴛ ᴛʜᴇ ғᴜɴ ʙᴇɢɪɴ!</b>"
)

MAIN_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("sᴜᴘᴘᴏʀᴛ", url=f'https://t.me/{SUPPORT_CHAT}'),
     InlineKeyboardButton("ᴜᴘᴅᴀᴛᴇs", url=f'https://t.me/{UPDATE_CHAT}')],
    [InlineKeyboardButton("sᴛᴀʀᴛ ɢᴜᴇssɪɴɢ💫", url=f'https://t.me/{BOT_USERNAME}?startgroup=new')],
    [InlineKeyboardButton("ʜᴇʟᴘ", callback_data='sxc_help'),
     InlineKeyboardButton("ᴄʀᴇᴅɪᴛs", callback_data='sxc_credits')]
])

FORCE_SUB_TEXT = "🔒 <b>ʟᴇᴛ's ɢᴏ ʙᴀʙʏ ᴊᴏɪɴ ᴏᴜʀ ᴜᴘᴅᴀᴛᴇs ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴍᴇ!</b>"
FORCE_SUB_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ", url=f'https://t.me/{FORCE_SUB_CHAT}')],
    [InlineKeyboardButton("ᴛʀʏ ᴀɢᴀɪɴ", callback_data='sxc_checksub')]
])

PAGE_SIZE = 6

# Small Caps + Bold Categories & Commands List
CATEGORIES = {
    "basic": ("ʙᴀsɪᴄ ᴄᴏᴍᴍᴀɴᴅs", [
        ("/start", "sᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ"),
        ("/grab", "ɢʀᴀʙ ᴛʜᴇ ᴄʜᴀʀᴀᴄᴛᴇʀ"),
        ("/fav", "ᴀᴅᴅ ᴀ ᴄʜᴀʀᴀᴄᴛᴇʀ ᴛᴏ ʏᴏᴜʀ ғᴀᴠᴏᴜʀɪᴛᴇ"),
        ("/claim", "ᴄʟᴀɪᴍ ʏᴏᴜʀ ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ"),
        ("/pay", "ɢɪᴠᴇ ᴄᴏɪɴs💸 ᴛᴏ ᴏᴛʜᴇʀ ᴜsᴇʀs"),
        ("/bal", "sᴇᴇ ʏᴏᴜʀ ʙᴀʟᴀɴᴄᴇ"),
        ("/harem", "sᴇᴇ ʏᴏᴜʀ ᴄʜᴀʀᴀᴄᴛᴇʀ's ᴄᴏʟʟᴇᴄᴛɪᴏɴ"),
        ("/gift", "ɢɪғᴛ ʏᴏᴜʀ ᴡᴀɪғᴜ ᴛᴏ sᴏᴍᴇᴏɴᴇ 🎀"),
        ("/trade", "ᴛʀᴀᴅᴇ ᴄʜᴀʀᴀᴄᴛᴇʀs ʙᴇᴛᴡᴇᴇɴ ᴜsᴇʀs"),
        ("/top", "ᴠɪᴇᴡ ᴛʜᴇ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ"),
        ("/sprofile", "ᴠɪᴇᴡ ʏᴏᴜʀ ᴘʀᴏғɪʟᴇ"),
        ("/changetime", "ᴄʜᴀɴɢᴇ ᴛʜᴇ sᴘᴀᴡɴ ᴛɪᴍᴇ ᴏғ ᴄʜᴀʀᴀᴄᴛᴇʀs [ᴏᴡɴᴇʀ/ᴀᴅᴍɪɴs]"),
    ]),
    "interactive": ("ɪɴᴛᴇʀᴀᴄᴛɪᴠᴇ ᴄᴏᴍᴍᴀɴᴅs", [
        ("/claim", "ᴄʟᴀɪᴍ ʏᴏᴜʀ ᴅᴀɪʟʏ ʀᴇᴡᴀʀᴅ"),
        ("/roll", "ɢᴀᴍʙʟᴇ ʏᴏᴜʀ ɢᴏʟᴅ"),
        ("/games", "ᴘʟᴀʏ ɢᴀᴍᴇs"),
    ]),
    "sudo": ("sᴜᴅᴏ ᴄᴏᴍᴍᴀɴᴅs", [
        ("/broadcast", "ʙʀᴏᴀᴅᴄᴀsᴛ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴀʟʟ ᴜsᴇʀs"),
        ("/addsudo", "ᴀᴅᴅ ᴀ sᴜᴅᴏ ᴜsᴇʀ"),
        ("/removesudo", "ʀᴇᴍᴏᴠᴇ ᴀ sᴜᴅᴏ ᴜsᴇʀ"),
        ("/ban", "ʙᴀɴ ᴀ ᴜsᴇʀ ғʀᴏᴍ ᴛʜᴇ ʙᴏᴛ"),
        ("/unban", "ᴜɴʙᴀɴ ᴀ ᴜsᴇʀ"),
        ("/stats", "ᴠɪᴇᴡ ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs"),
    ]),
}


async def is_force_sub_member(user_id, context: CallbackContext):
    try:
        member = await context.bot.get_chat_member(f"@{FORCE_SUB_CHAT}", user_id)
        return member.status not in ('left', 'kicked')
    except Exception as e:
        LOGGER.warning(f"Force-sub check failed for {user_id}: {e}")
        return True


def menu_view():
    kb = [
        [InlineKeyboardButton("ʙᴀsɪᴄ", callback_data='sxc_cat_basic'),
         InlineKeyboardButton("ɪɴᴛᴇʀᴀᴄᴛɪᴠᴇ", callback_data='sxc_cat_interactive')],
        [InlineKeyboardButton("🌿 sᴜᴅᴏ", callback_data='sxc_cat_sudo')],
        [InlineKeyboardButton("ᴍᴀɪɴ ᴍᴇɴᴜ", callback_data='sxc_back')]
    ]
    return "<b>ʜᴇʟᴘ ᴍᴇɴᴜ</b>\n\n<b>sᴇʟᴇᴄᴛ ᴀ ᴄᴀᴛᴇɢᴏʀʏ ᴛᴏ ᴠɪᴇᴡ ᴄᴏᴍᴍᴀɴᴅs:</b>", InlineKeyboardMarkup(kb)


def category_view(cat_key: str, page: int = 1):
    title, commands = CATEGORIES[cat_key]
    total_pages = max(1, -(-len(commands) // PAGE_SIZE))
    page = max(1, min(page, total_pages))
    chunk = commands[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]

    text = f"<b>{title}</b> `[{page}/{total_pages}]`\n\n" + "\n".join(
        f"• <code>{cmd}</code> - <b>{desc}</b>" for cmd, desc in chunk
    )

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⟴ ᴘʀᴇᴠɪᴏᴜs", callback_data=f'sxc_pg_{cat_key}_{page - 1}'))
    if page < total_pages:
        nav.append(InlineKeyboardButton("ɴᴇxᴛ ⟴", callback_data=f'sxc_pg_{cat_key}_{page + 1}'))

    kb = ([nav] if nav else []) + [[InlineKeyboardButton("⟲ ʙᴀᴄᴋ ᴛᴏ ᴍᴇɴᴜ", callback_data='sxc_menu')]]
    return text, InlineKeyboardMarkup(kb)


CREDITS_USERS = [
    ("ＩＭ 𖣘 ＵＣＨＩＨＡ", "iMSASUKESi", 7657218453),
]


async def credits_view(context: CallbackContext):
    kb = []
    for name, username, user_id in CREDITS_USERS:
        url = f'tg://user?id={user_id}'
        kb.append([InlineKeyboardButton(f"{name}", url=url)])
    kb.append([InlineKeyboardButton("⟲ ʙᴀᴄᴋ", callback_data='sxc_back')])
    return "<b>sᴜᴅᴏ ᴏᴡɴᴇʀs:</b>", InlineKeyboardMarkup(kb)


def _new_user_doc(user_id, first_name, username):
    return {
        "id": user_id, "first_name": first_name, "username": username,
        "balance": 500, "characters": [],
        "pass_data": {
            "tier": "free", "weekly_claims": 0, "last_weekly_claim": None,
            "streak_count": 0, "last_streak_claim": None,
            "tasks": {"weekly_claims": 0, "grabs": 0},
            "mythic_unlocked": False, "premium_expires": None,
            "elite_expires": None, "pending_elite_payment": None
        }
    }


async def _ensure_user(user_id, first_name, username):
    """Safe DB check to avoid runtime loop mismatch crashes."""
    try:
        user_data = await user_collection.find_one({"id": user_id})
        if user_data:
            await user_collection.update_one(
                {"id": user_id}, {"$set": {"first_name": first_name, "username": username}}
            )
            return False
        await user_collection.insert_one(_new_user_doc(user_id, first_name, username))
        return True
    except Exception as e:
        LOGGER.error(f"Error in _ensure_user DB query: {e}")
        return False


async def safe_track_bot_start(user_id, first_name, username, is_new_user):
    try:
        from shivu.modules.chatlog import track_bot_start
        await asyncio.wait_for(track_bot_start(user_id, first_name, username, is_new_user), timeout=5.0)
    except asyncio.TimeoutError:
        LOGGER.warning(f"track_bot_start timed out for user {user_id}")
    except ImportError:
        LOGGER.warning("chatlog module not available, skipping bot start tracking")
    except Exception as e:
        LOGGER.error(f"Error in safe_track_bot_start: {e}")


async def start(update: Update, context: CallbackContext):
    try:
        if not update or not update.effective_user:
            return

        user_id = update.effective_user.id
        first_name = update.effective_user.first_name or "User"
        username = update.effective_user.username or ""

        if not await is_force_sub_member(user_id, context):
            await update.message.reply_text(FORCE_SUB_TEXT, parse_mode='HTML', reply_markup=FORCE_SUB_KEYBOARD)
            return

        is_new = await _ensure_user(user_id, first_name, username)
        
        if hasattr(context.application, "create_task"):
            context.application.create_task(safe_track_bot_start(user_id, first_name, username, is_new))
        else:
            asyncio.create_task(safe_track_bot_start(user_id, first_name, username, is_new))

        await update.message.reply_video(
            video=START_VIDEO, caption=MAIN_CAPTION, reply_markup=MAIN_KEYBOARD,
            parse_mode='HTML', supports_streaming=True
        )

    except Exception as e:
        LOGGER.error(f"Critical error in start command: {e}", exc_info=True)
        try:
            await update.message.reply_text("⚠️ <b>ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.</b>", parse_mode='HTML')
        except Exception:
            pass


async def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    try:
        await query.answer()
    except Exception as e:
        LOGGER.error(f"Error answering callback query: {e}")
        return

    try:
        data = query.data
        user_id = query.from_user.id

        if data == 'sxc_checksub':
            if not await is_force_sub_member(user_id, context):
                await query.answer("⚠️ ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴊᴏɪɴᴇᴅ ʏᴇᴛ!", show_alert=True)
                return
            first_name = query.from_user.first_name or "User"
            username = query.from_user.username or ""
            await _ensure_user(user_id, first_name, username)
            try:
                await query.message.delete()
            except Exception:
                pass
            await context.bot.send_video(
                chat_id=user_id, video=START_VIDEO, caption=MAIN_CAPTION,
                reply_markup=MAIN_KEYBOARD, parse_mode='HTML', supports_streaming=True
            )
            return

        if not await is_force_sub_member(user_id, context):
            await query.answer("⚠️ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ ғɪʀsᴛ!", show_alert=True)
            return

        await _ensure_user(user_id, query.from_user.first_name, query.from_user.username)

        if data == 'sxc_credits':
            text, markup = await credits_view(context)
        elif data in ('sxc_help', 'sxc_menu'):
            text, markup = menu_view()
        elif data.startswith('sxc_cat_'):
            cat_key = data[len('sxc_cat_'):]
            if cat_key not in CATEGORIES:
                await query.answer("⚠️ Unknown category", show_alert=True)
                return
            text, markup = category_view(cat_key)
        elif data.startswith('sxc_pg_'):
            cat_key, _, page_str = data[len('sxc_pg_'):].rpartition('_')
            if cat_key not in CATEGORIES or not page_str.isdigit():
                await query.answer("⚠️ Unknown page", show_alert=True)
                return
            text, markup = category_view(cat_key, int(page_str))
        elif data == 'sxc_back':
            text, markup = MAIN_CAPTION, MAIN_KEYBOARD
        else:
            return

        await query.edit_message_caption(caption=text, parse_mode='HTML', reply_markup=markup)

    except Exception as e:
        LOGGER.error(f"Error in button callback: {e}", exc_info=True)
        try:
            await query.answer("⚠️ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.", show_alert=True)
        except Exception:
            pass


application.add_handler(CommandHandler('start', start, block=False))
application.add_handler(CallbackQueryHandler(button_callback, pattern=r'^sxc_', block=False))

LOGGER.info("✓ Start module loaded successfully")

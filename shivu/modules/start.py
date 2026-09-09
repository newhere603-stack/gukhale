import asyncio
import html
import random  # 🔥 NAYA IMPORT: Animation ke draft_id ke liye
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.error import BadRequest, TelegramError
# 🔥 NAYA IMPORT: ChatMemberHandler add kiya gaya hai auto-detect karne ke liye
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler, ChatMemberHandler
from shivu import (
    BOT_USERNAME,
    LOGGER,
    SUPPORT_CHAT,
    UPDATE_CHAT,
    application,
    sudo_users_collection,
    user_collection,
)

# 🔥 NAYA IMPORT: Economy DB mein 5000 coins add karne ke liye
from shivu.Database.db import eco_collection

# File ID ki jagah temporary direct video URL daal kar check karo
START_VIDEO = "https://gxtusqitetsemwjdtvvq.supabase.co/storage/v1/object/public/photos/1785999431478-sm4ln0.mp4"

FORCE_SUB_CHAT = "anime_group_hai"
OWNER_ID = 7657218453  # Aapki Master Owner ID

# 🔥 DEEP LINK UPDATE: Jab bot add hoga to auto full-rights maangega
ADMIN_RIGHTS_LINK = f"https://t.me/{BOT_USERNAME}?startgroup=new&admin=change_info+delete_messages+restrict_members+invite_users+pin_messages+manage_video_chats+promote_members"

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
        # Is button se automatic full rights prompt hoga
        InlineKeyboardButton(
            "ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ 💫",
            url=ADMIN_RIGHTS_LINK,
        )
    ],
    [
        InlineKeyboardButton("ʜᴇʟᴘ", callback_data="sxc_help"),
        InlineKeyboardButton("ᴄʀᴇᴅɪᴛs", callback_data="sxc_credits"),
    ],
])

FORCE_SUB_TEXT = "<tg-emoji emoji-id=\"5291873529464122510\">🔓</tg-emoji> <b>ʟᴇᴛ's ɢᴏ ʙᴀʙʏ ᴊᴏɪɴ ᴏᴜʀ ᴜᴘᴅᴀᴛᴇs ᴛᴏ ᴜsᴇ ᴍᴇ! <tg-emoji emoji-id=\"6336870266928371445\">💘</tg-emoji></b>"
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
            ("/fav", "ᴀᴅᴅ ᴀ ᴄʜᴀʀᴀᴄᴛᴇʀ yᴛᴏ ʏᴏᴜʀ ғᴀᴠᴏᴜʀɪᴛᴇ"),
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

# Top par check kar lena ki 'import html' likha ho (waise purane code mein tha)

# Dynamic Caption Generator with User Mention (HTML Error Fixed)
def get_main_caption(user_id: int, first_name: str) -> str:
    # 🔥 FIX: html.escape use kiya taaki name ke < > ya ajeeb fonts error na dein
    safe_name = html.escape(first_name)
    user_mention = f'<a href="tg://user?id={user_id}">{safe_name}</a>'
    
    return (
        f"<b><tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> Hᴇʏ {user_mention},<tg-emoji emoji-id=\"6093854622114390223\">🎀</tg-emoji>\n"
        f"ɪ'ᴍ ᴀʟɪꜱᴀ ᴡᴀɪꜰᴜ ʙᴏᴛ, ʏᴏᴜʀ ᴜʟᴛɪᴍᴀᴛᴇ ᴀɴɪᴍᴇ ᴀᴅᴠᴇɴᴛᴜʀᴇ ᴄᴏᴍᴘᴀɴɪᴏɴ. <tg-emoji emoji-id=\"6066873332618238192\">⛈</tg-emoji></b>\n\n"
        f"<b>ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ ᴀɴᴅ ʟᴇᴛ ᴛʜᴇ ғᴜɴ ʙᴇɢɪɴ! <tg-emoji emoji-id=\"6336870266928371445\">💘</tg-emoji></b>"
    )

# 🔥 FULLY FIXED Robust Force Sub Checker
async def is_force_sub_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        # Group mein Force Sub check karne ki jarurat nahi hoti private me karni hai
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
        
        # Agar user ban ho chuka hai ya left kar chuka hai toh False
        if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
            return False
            
        # Baaki sab valid hain (MEMBER, RESTRICTED, ADMINISTRATOR, OWNER)
        return True

    except BadRequest as e:
        # User not found ka error matlab user ne join nahi kiya hai
        if "User not found" in str(e) or "Participant_id_invalid" in str(e):
            return False
        LOGGER.warning(f"Force-sub BadRequest for user: {e}")
        return False # Agar error aaya toh safe side ke liye subscribe bolo
    except Exception as e:
        LOGGER.error(f"Force-sub error: {e}")
        return False


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


# Dynamic Credits View
async def credits_view(context: ContextTypes.DEFAULT_TYPE):
    kb = []
    added_ids = set()

    try:
        owner_chat = await context.bot.get_chat(OWNER_ID)
        owner_name = owner_chat.first_name or "ＩＭ 𖣘 ＵＣＨＩＨＡ"
    except Exception:
        owner_name = "ＩＭ 𖣘 ＵＣＨＩＨＡ"

    kb.append([InlineKeyboardButton(f"{owner_name}", url=f"tg://user?id={OWNER_ID}")])
    added_ids.add(OWNER_ID)

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
    return "<b>sᴜᴅᴏ:<tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji></b>", InlineKeyboardMarkup(kb)


# 🔥 SUPERFAST DUAL DATABASE UPSERT
async def _ensure_user(user_id, first_name, username):
    try:
        char_task = user_collection.find_one({"id": user_id}, {"bot_started": 1})
        eco_task = eco_collection.find_one({"id": user_id}, {"bot_started": 1})
        char_doc, eco_doc = await asyncio.gather(char_task, eco_task)

        is_new_char = not char_doc or not char_doc.get("bot_started")
        is_new_eco = not eco_doc or not eco_doc.get("bot_started")
        is_new_user = is_new_char or is_new_eco

        update_tasks = []

        # 1. Update Character DB (Harem)
        update_tasks.append(
            user_collection.update_one(
                {"id": user_id},
                {
                    "$set": {
                        "first_name": first_name, 
                        "username": username, 
                        "bot_started": True
                    },
                    "$setOnInsert": {
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
                        }
                    }
                },
                upsert=True
            )
        )

        # 2. Update Economy DB
        if is_new_user:
            update_tasks.append(
                eco_collection.update_one(
                    {"id": user_id},
                    {
                        "$set": {
                            "first_name": first_name,
                            "username": username,
                            "bot_started": True
                        },
                        "$inc": {"balance": 5000},  # 🔥 Naye user ko silently 5000 coins denge
                        "$setOnInsert": {"tokens": 0}
                    },
                    upsert=True
                )
            )
        else:
            update_tasks.append(
                eco_collection.update_one(
                    {"id": user_id},
                    {
                        "$set": {
                            "first_name": first_name,
                            "username": username,
                            "bot_started": True
                        }
                    },
                    upsert=True
                )
            )

        await asyncio.gather(*update_tasks)
        return is_new_user
    except Exception as e:
        LOGGER.error(f"Error in _ensure_user DB query: {e}")
        return False


# 🔥 LOG SENDING ERROR FIXED HERE
async def safe_track_bot_start(user_id, first_name, username, is_new_user):
    try:
        from shivu.modules.chatlog import track_bot_start
        
        # Chatlog module bhejte time bhi HTML escape lagana padega taaki track_bot_start fail na ho
        safe_fname = html.escape(first_name)
        safe_uname = html.escape(username)
        
        await asyncio.wait_for(
            track_bot_start(user_id, safe_fname, safe_uname, is_new_user),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        LOGGER.warning(f"track_bot_start timed out for user {user_id}")
    except ImportError:
        LOGGER.warning("chatlog module not available, skipping bot start tracking")
    except Exception as e:
        LOGGER.error(f"Error in safe_track_bot_start: {e}")


# ==========================================
# ✨ TELEGRAM LIVE TEXT ANIMATION (START MENU)
# ==========================================
async def animated_start_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int,
    caption_text: str,
):
    """
    Start menu ke liye FLASH OPEN Animation Helper.
    Small caps text 'sᴛᴀʀᴛɪɴɢ...' flash karke video open karega.
    """
    async def send_final():
        try:
            await context.bot.send_video(
                chat_id=chat_id,
                video=START_VIDEO,
                caption=caption_text,
                reply_markup=MAIN_KEYBOARD,
                parse_mode=ParseMode.HTML,
                supports_streaming=True,
            )
        except Exception as e:
            LOGGER.error(f"Error sending final start video: {e}")

    # Group me bina animation direct reply aayega
    if update.effective_chat and update.effective_chat.type != ChatType.PRIVATE:
        return await send_final()
    
    draft_id = random.randint(1, 2_000_000_000)
    
    # 🔥 FLASH LOADING TEXT (Small Caps 'sᴛᴀʀᴛɪɴɢ...')
    loading_frames = [
        "🚀",
        "🚀 sᴛᴀʀᴛ...",
        "🚀 sᴛᴀʀᴛɪɴɢ...",
        "🚀 sᴛᴀʀᴛɪɴɢ ʙᴏᴛ..."
    ]

    try:
        for frame in loading_frames:
            try:
                await context.bot._post("sendMessageDraft", {"chat_id": user_id, "draft_id": draft_id, "text": frame})
            except AttributeError:
                pass
            await asyncio.sleep(0.025) # Superfast flash (0.1 seconds total)

        # Final Permanent video message
        return await send_final()

    except Exception as e:
        LOGGER.warning(f"Live text animation failed for {user_id}: {e}")
        return await send_final()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update or not update.effective_user or not update.effective_chat:
            return

        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        first_name = update.effective_user.first_name or "User"
        username = update.effective_user.username or ""

        # 🔥 FAST ADMIN CHECK FIX: OWNER status bhi add kiya
        if update.effective_chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            try:
                bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
                if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="<b><tg-emoji emoji-id=\"6093637923834438402\">✨</tg-emoji> ᴍᴀᴋᴇ ᴍᴇ ᴀᴅᴍɪɴ ғɪʀsᴛ!</b>",
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("ᴍᴀᴋᴇ ᴍᴇ ᴀᴅᴍɪɴ", url=ADMIN_RIGHTS_LINK)]
                        ])
                    )
                    return 
            except Exception as e:
                LOGGER.error(f"Error checking admin status inside group: {e}")
                return

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

        # 🔥 FIX: Deep link bypass for 'buy_tokens'
        if context.args and context.args[0] == 'buy_tokens':
            return

        caption_text = get_main_caption(user_id, first_name)

        # Animated helper ko bulaya gaya hai (Send video ki jagah)
        await animated_start_reply(update, context, chat_id, user_id, caption_text)

    except Exception as e:
        LOGGER.error(f"Critical error in start command: {e}", exc_info=True)
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="<tg-emoji emoji-id=\"5420323339723881652\">⚠️</tg-emoji> <b>ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.</b>",
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
                
            is_new = await _ensure_user(user_id, first_name, username)
            
            try:
                await query.message.delete()
            except Exception:
                pass
            
            caption_text = get_main_caption(user_id, first_name)
            # Animated helper yahan bhi laga diya force sub bypass ke baad
            await animated_start_reply(update, context, user_id, user_id, caption_text)
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
                "ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.", show_alert=True
            )
        except Exception:
            pass

async def bot_added_to_group_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if not result or result.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    if result.new_chat_member.status == ChatMemberStatus.MEMBER: 
        try:
            await context.bot.send_message(
                chat_id=result.chat.id,
                text="<b><tg-emoji emoji-id=\"6093637923834438402\">✨</tg-emoji> ᴍᴀᴋᴇ ᴍᴇ ᴀᴅᴍɪɴ ғɪʀsᴛ!</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("ᴍᴀᴋᴇ ᴍᴇ ᴀᴅᴍɪɴ", url=ADMIN_RIGHTS_LINK)]
                ])
            )
        except Exception as e:
            LOGGER.error(f"Admin prompt bhejne mein error: {e}")

application.add_handler(CommandHandler("start", start, block=False), group=1)
application.add_handler(
    CallbackQueryHandler(button_callback, pattern=r"^sxc_", block=False)
)
application.add_handler(ChatMemberHandler(bot_added_to_group_handler, ChatMemberHandler.MY_CHAT_MEMBER, block=False))

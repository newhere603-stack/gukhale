import asyncio
import html
import random
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.error import BadRequest, TelegramError
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
from shivu.Database.db import eco_collection

START_VIDEO = "https://gxtusqitetsemwjdtvvq.supabase.co/storage/v1/object/public/photos/1785999431478-sm4ln0.mp4"

# ⚠️ Yahan apne "Leaf Village" ya actual force sub group/channel ka NUMERIC ID daalna
FORCE_SUB_CHAT = -1001234567890 
# ⚠️ Yahan link ke liye bina '@' ke username daalna
FORCE_SUB_CHAT_USERNAME = "anime_group_hai" 

OWNER_ID = 7657218453  

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
        InlineKeyboardButton(
            **{
                "text": "ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ",
                "url": ADMIN_RIGHTS_LINK,
                "icon_custom_emoji_id": "5469741319330996757"
            }
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
            "ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ", url=f"https://t.me/{FORCE_SUB_CHAT_USERNAME}"
        )
    ],
    [InlineKeyboardButton("ᴛʀʏ ᴀɢᴀɪɴ", callback_data="sxc_checksub")],
])

PAGE_SIZE = 10

CATEGORIES = {
    "basic": (
        "ʙᴀsɪᴄ ᴄᴏᴍᴍᴀɴᴅs",
        [
            ("/start", "ᴛᴏ sᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ"),
            ("/grab", "ᴛᴏ ɢᴜᴇss ᴛʜᴇ ᴡᴀɪғᴜ"),
            ("/fav", "ᴛᴏ ᴍᴀᴋᴇ ʏᴏᴜʀ ᴏᴡɴᴇᴅ ᴡᴀɪғᴜ ғᴀᴠᴏᴜʀɪᴛᴇ"),
            ("/claim", "ᴛᴏ ᴄʟᴀɪᴍ ʏᴏᴜʀ ᴅᴀɪʟʏ ᴄᴏɪɴs"),
            ("/tasks", "ᴛᴏ ᴇᴀʀɴ ᴍᴏʀᴇ ᴄᴏɪɴꜱ"),
            ("/bonus", "ᴛᴏ ᴄʟᴀɪᴍ ʏᴏᴜʀ ᴅᴀɪʟʏ/ᴡᴇᴇᴋʟʏ ʙᴏɴᴜs"),
            ("/top", "ᴛᴏ sᴇᴇ ᴛᴏᴘ ᴘʟᴀʏᴇʀs"),
            ("/bal", "ᴛᴏ sᴇᴇ ʏᴏᴜʀ ʙᴀʟᴀɴᴄᴇ"),
            ("/tokens", "ᴛᴏ sᴇᴇ ʏᴏᴜʀ ᴛᴏᴋᴇɴs"),
            ("/pay", "ᴛᴏ ɢɪᴠᴇ ᴄᴏɪɴs"),
            ("/tpay", "ᴛᴏ ɢɪᴠᴇ ᴛᴏᴋᴇɴs"),
            ("/buy", "ᴛᴏ ʙᴜʏ ᴅɪʀᴇᴄᴛʟʏ ᴀʟʟ"),
            ("/pmarket", "ᴛᴏ ᴏᴘᴇɴ ᴘᴇʀsᴏɴ ᴛᴏ ᴘᴇʀsᴏɴ sʜᴏᴘ"),
            ("/marketplace", "ᴛᴏ ᴏᴘᴇɴ ᴛʜᴇ ᴍᴀʀᴋᴇᴛ"),
            ("/gift", "ᴛᴏ ɢɪғᴛ ʏᴏᴜʀ ᴡᴀɪғᴜ"),
            ("/harem", "ᴛᴏ sᴇᴇ ʏᴏᴜʀ ᴡᴀɪғᴜ"),
            ("/hmode", "ᴛᴏ ᴄʜᴀɴɢᴇ ʜᴀʀᴇᴍ ᴍᴏᴅᴇ"),
            ("/check", "ᴛᴏ sᴇᴇ ᴡᴀɪғᴜ ғʀᴏᴍ ʜᴇʀ ɪᴅ"),
            ("/sprofile", "ᴛᴏ sᴇᴇ ʏᴏᴜʀ's ᴘʀᴏғɪʟᴇ"),
            ("/swaifu", "ᴛᴏ ᴄʟᴀɪᴍ ʏᴏᴜʀ sᴘᴇᴄɪᴀʟ ᴡᴀɪғᴜs"),
            ("/redeem", "ᴛᴏ ʀᴇᴅᴇᴇᴍ ᴄᴏɪɴs/ᴛᴏᴋᴇɴs"),
            ("/sredeem", "ᴛᴏ ʀᴇᴅᴇᴇᴍ ᴡᴀɪғᴜ"),
            ("/leaderboard", "ᴛᴏ ᴠɪᴇᴡ ᴛʜᴇ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ"),
        ],
    ),
    "interactive": (
        "ɪɴᴛᴇʀᴀᴄᴛɪᴠᴇ ᴄᴏᴍᴍᴀɴᴅs",
        [
            ("/mines", "ᴛᴏ ᴘʟᴀʏ ᴍɪɴᴇs"),
            ("/tic", "ᴛᴏ ᴘʟᴀʏ ᴛɪᴄ-ᴛᴀᴄ-ᴛᴏᴇ"),
            ("/sbet", "ᴛᴏ ʙᴇᴛ ʏᴏᴜʀ ᴄᴏɪɴs"),
            ("/games", "ᴘʟᴀʏ ɢᴀᴍᴇs"),
            ("/roll", "ᴛᴏ ʀᴏʟʟ ᴀ ᴅɪᴄᴇ"),
            ("/explore", "ᴛᴏ ᴇxᴘʟᴏʀᴇ ᴀɴᴅ ɢᴇᴛ ᴄᴏɪɴs"),
            ("/marry", "ᴛᴏ ᴍᴀʀʀʏ ᴀ ɴᴇᴡ ᴡᴀɪғᴜ"),
            ("/propose", "ᴛᴏ ᴘʀᴏᴘᴏsᴇ ᴀ ᴡᴀɪғᴜ"),
            ("/new", "ᴛᴏ sᴛᴀʀᴛ ᴀ ɴᴇᴡ ɢᴀᴍᴇ"),
            ("/end", "ᴛᴏ ᴇɴᴅ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ɢᴀᴍᴇ"),
            ("/helpword", "ʜᴏᴡ ᴛᴏ ᴘʟᴀʏ ᴡᴏʀᴅsᴇᴇᴋ"),
            ("/grid", "ᴛᴏ ᴘʟᴀʏ ᴡᴏʀᴅ ɢʀɪᴅ"),
            ("/grid_easy", "ᴛᴏ ᴘʟᴀʏ ᴇᴀsʏ ᴡᴏʀᴅ ɢʀɪᴅ"),
            ("/grid_hard", "ᴛᴏ ᴘʟᴀʏ ʜᴀʀᴅ ᴡᴏʀᴅ ɢʀɪᴅ"),
            ("/endgrid", "ᴇɴᴅ ɢʀɪᴅ ɢᴀᴍᴇ"),
            ("/topgrid", "ᴛᴏ sᴇᴇ ɢʀɪᴅ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ"),
            ("/helpgrid", "ʜᴏᴡ ᴛᴏ ᴘʟᴀʏ ᴡᴏʀᴅɢʀɪᴅ"),
        ],
    ),
    "admins": (
        "ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅs",
        [
            ("/changetime", "ᴛᴏ ᴄʜᴀɴɢᴇ ᴛʜᴇ ᴀᴘᴘᴇᴀʀ ᴛɪᴍᴇ ᴏғ ᴡᴀɪғᴜ [ᴀᴅᴍɪɴ ᴏɴʟʏ]"),
            ("/toggledelete", "ᴛᴏ ᴅᴇʟᴇᴛᴇ ᴡᴏʀᴅsᴇᴇᴋ sᴘᴀᴍ [ᴀᴅᴍɪɴ ᴏɴʟʏ]"),
            ("/togglewordseek", "ᴛᴏ ᴅɪsᴀʙʟᴇ ᴡᴏʀᴅsᴇᴇᴋ ɢᴀᴍᴇ [ᴀᴅᴍɪɴ ᴏɴʟʏ]"),
            ("/gridsettings", "ᴛᴏ ᴏᴘᴇɴ ɢʀɪᴅ sᴇᴛᴛɪɴɢs [ᴀᴅᴍɪɴ ᴏɴʟʏ]"),
        ],
    ),
}

def get_main_caption(user_id: int, first_name: str) -> str:
    safe_name = html.escape(first_name)
    user_mention = f'<a href="tg://user?id={user_id}">{safe_name}</a>'
    
    return (
        f"<b><tg-emoji emoji-id=\"6093431129749070651\">✨</tg-emoji> Hᴇʏ {user_mention},<tg-emoji emoji-id=\"6093854622114390223\">🎀</tg-emoji>\n"
        f"ɪ'ᴍ ᴀʟɪꜱᴀ ᴡᴀɪꜰᴜ ʙᴏᴛ, ʏᴏᴜʀ ᴜʟᴛɪᴍᴀᴛᴇ ᴀɴɪᴍᴇ ᴀᴅᴠᴇɴᴛᴜʀᴇ ᴄᴏᴍᴘᴀɴɪᴏɴ. <tg-emoji emoji-id=\"6066873332618238192\">⛈</tg-emoji></b>\n\n"
        f"<b>ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ ᴀɴᴅ ʟᴇᴛ ᴛʜᴇ ғᴜɴ ʙᴇɢɪɴ! <tg-emoji emoji-id=\"6336870266928371445\">💘</tg-emoji></b>"
    )

async def is_force_sub_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        if not update or not update.effective_user:
            return False

        user_id = update.effective_user.id

        if update.effective_chat and update.effective_chat.type != ChatType.PRIVATE:
            return True

        member = await context.bot.get_chat_member(
            chat_id=FORCE_SUB_CHAT, user_id=user_id
        )
        
        if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
            return False
            
        return True

    except BadRequest as e:
        error_text = str(e).lower()
        if "user not found" in error_text or "participant_id_invalid" in error_text:
            return False
        LOGGER.warning(f"Force-sub BadRequest for user: {e}")
        return True 
    except TelegramError as e:
        LOGGER.error(f"Force-sub TelegramError: {e}")
        return True
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
        [InlineKeyboardButton("👑 ᴀᴅᴍɪɴs", callback_data="sxc_cat_admins")],
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

    text = f"<b>{title}</b>  <b>• ᴘᴀɢᴇ {page}/{total_pages} •</b>\n\n" + "\n".join(
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

async def credits_view(context: ContextTypes.DEFAULT_TYPE):
    kb = []
    added_ids = set()

    try:
        owner_chat = await context.bot.get_chat(OWNER_ID)
        owner_name = owner_chat.first_name or "ＩＭ 𖣘 ＵＣＨＩＨＡ"
    except Exception:
        owner_name = "ＩＭ 𖣘 ＵＣＨＩＨＡ"

    # 🔥 Owner line with Premium Emoji
    kb.append([
        InlineKeyboardButton(
            **{
                "text": f"{owner_name}",
                "url": f"tg://user?id={OWNER_ID}",
                "icon_custom_emoji_id": "6084374074513957348"
            }
        )
    ])
    added_ids.add(OWNER_ID)

    sudo_users = await sudo_users_collection.find().to_list(length=None)

    sudo_row = []
    if sudo_users:
        for u in sudo_users:
            u_id = u.get("id")
            if u_id not in added_ids:
                name = u.get("first_name", "Sudo User")
                url = f"tg://user?id={u_id}"
                
                # 🔥 Sudo users with Premium Emoji
                sudo_row.append(
                    InlineKeyboardButton(
                        **{
                            "text": f"{name}",
                            "url": url,
                            "icon_custom_emoji_id": "6084374074513957348"
                        }
                    )
                )
                added_ids.add(u_id)

                if len(sudo_row) == 2:
                    kb.append(sudo_row)
                    sudo_row = []

        if sudo_row: 
            kb.append(sudo_row)

    kb.append([InlineKeyboardButton("⟲ ʙᴀᴄᴋ", callback_data="sxc_back")])
    return "<b>sᴜᴅᴏ ʟɪsᴛ:<tg-emoji emoji-id=\"6118405866359103466\">✅</tg-emoji></b>", InlineKeyboardMarkup(kb)

async def _ensure_user(user_id, first_name, username):
    try:
        char_task = user_collection.find_one({"id": user_id}, {"bot_started": 1})
        eco_task = eco_collection.find_one({"id": user_id}, {"bot_started": 1})
        char_doc, eco_doc = await asyncio.gather(char_task, eco_task)

        is_new_char = not char_doc or not char_doc.get("bot_started")
        is_new_eco = not eco_doc or not eco_doc.get("bot_started")
        is_new_user = is_new_char or is_new_eco

        update_tasks = []

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
                        "$inc": {"balance": 5000},
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

async def safe_track_bot_start(user_id, first_name, username, is_new_user):
    try:
        from shivu.modules.chatlog import track_bot_start
        safe_fname = html.escape(first_name)
        safe_uname = html.escape(username)
        await asyncio.wait_for(
            track_bot_start(user_id, safe_fname, safe_uname, is_new_user),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        LOGGER.warning(f"track_bot_start timed out for user {user_id}")
    except ImportError:
        pass
    except Exception as e:
        LOGGER.error(f"Error in safe_track_bot_start: {e}")

async def send_start_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    caption_text: str,
    animate: bool = False
):
    message = update.effective_message
    reply_to = message.message_id if message else None

    async def send_final():
        rich_caption_text = caption_text.replace('\n', '<br>')
        rich_caption = f'<video src="{html.escape(START_VIDEO)}"/><br>{rich_caption_text}'
        
        data = {
            "chat_id": chat_id,
            "rich_message": {"html": rich_caption},
            "reply_markup": MAIN_KEYBOARD.to_dict()
        }
        if reply_to:
            data["reply_to_message_id"] = reply_to

        try:
            await context.bot._post("sendRichMessage", data)
            return  
        except Exception as e:
            err_msg = str(e).lower()
            if "parse" in err_msg or "dictionary" in err_msg or "object" in err_msg:
                return 
                
            LOGGER.warning(f"Rich Message failed for start: {e}")
            try:
                clean_caption = re.sub(r'<(video|img)\b[^>]*>', '', caption_text, flags=re.IGNORECASE)
                clean_caption = clean_caption.replace('<h2>', '\n<b>').replace('</h2>', '</b>\n')
                clean_caption = clean_caption.replace('<h3>', '\n<b>').replace('</h3>', '</b>\n')
                clean_caption = clean_caption.replace('<br>', '\n').replace('<br/>', '\n').replace('​', '')
                clean_caption = re.sub(r'\n{3,}', '\n\n', clean_caption).strip()

                await context.bot.send_video(
                    chat_id=chat_id,
                    video=START_VIDEO,
                    caption=clean_caption,
                    reply_markup=MAIN_KEYBOARD,
                    parse_mode=ParseMode.HTML,
                    supports_streaming=True,
                    reply_to_message_id=reply_to
                )
            except Exception as e2:
                LOGGER.error(f"Error sending fallback start video: {e2}")

    if not animate or update.effective_chat.type != ChatType.PRIVATE:
        return await send_final()

    draft_id = random.randint(1, 2_000_000_000)
    
    loading_frames = [
        "<tg-emoji emoji-id=\"6093637923834438402\">✨</tg-emoji>",
        "<b><tg-emoji emoji-id=\"6093637923834438402\">✨</tg-emoji> sᴛᴀʀᴛɪɴɢ...</b>",
        "<b><tg-emoji emoji-id=\"6093637923834438402\">✨</tg-emoji> sᴛᴀʀᴛɪɴɢ ʙᴏᴛ...</b>",
        "<b><tg-emoji emoji-id=\"6093637923834438402\">✨</tg-emoji> sᴛᴀʀᴛɪɴɢ ᴍᴇɴᴜ...</b>"
    ]

    try:
        for frame in loading_frames:
            try:
                await context.bot._post("sendMessageDraft", {
                    "chat_id": chat_id, 
                    "draft_id": draft_id, 
                    "text": frame,
                    "parse_mode": ParseMode.HTML
                })
            except AttributeError:
                pass
            await asyncio.sleep(0.025)

        return await send_final()
    except Exception as e:
        LOGGER.warning(f"Live text animation failed: {e}")
        return await send_final()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update or not update.effective_user or not update.effective_chat:
            return

        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        first_name = update.effective_user.first_name or "User"
        username = update.effective_user.username or ""

        should_animate = False
        if update.effective_chat.type == ChatType.PRIVATE:
            if not context.args or str(context.args[0]).startswith("ref_"):
                should_animate = True

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
            context.application.create_task(safe_track_bot_start(user_id, first_name, username, is_new))
        else:
            asyncio.create_task(safe_track_bot_start(user_id, first_name, username, is_new))

        if context.args and context.args[0] == 'buy_tokens':
            return

        caption_text = get_main_caption(user_id, first_name)
        await send_start_menu(update, context, chat_id, caption_text, animate=should_animate)

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
            should_animate = False
            if update.effective_chat and update.effective_chat.type == ChatType.PRIVATE:
                should_animate = True
                
            if not await is_force_sub_member(update, context):
                try:
                    await query.answer("ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴊᴏɪɴᴇᴅ ʏᴇᴛ!", show_alert=True)
                except Exception:
                    pass
                return
                
            is_new = await _ensure_user(user_id, first_name, username)
            
            try:
                await query.message.delete()
            except Exception:
                pass
            
            caption_text = get_main_caption(user_id, first_name)
            # Yahan direct chat id send kar rahe query ka taki glitch na aye
            await send_start_menu(update, context, query.message.chat_id, caption_text, animate=should_animate)
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

        rich_text = text.replace('\n', '<br>')
        rich_caption = f'<video src="{html.escape(START_VIDEO)}"/><br>{rich_text}'

        try:
            await context.bot._post("editMessageText", {
                "chat_id": query.message.chat_id,
                "message_id": query.message.message_id,
                "rich_message": {"html": rich_caption},
                "reply_markup": markup.to_dict()
            })
        except Exception as e:
            err_msg = str(e).lower()
            if "parse" not in err_msg and "dictionary" not in err_msg and "object" not in err_msg:
                LOGGER.warning(f"Rich Message edit failed: {e}")
            
            try:
                clean_text = re.sub(r'<(video|img)\b[^>]*>', '', text, flags=re.IGNORECASE)
                clean_text = clean_text.replace('<h2>', '\n<b>').replace('</h2>', '</b>\n')
                clean_text = clean_text.replace('<h3>', '\n<b>').replace('</h3>', '</b>\n')
                clean_text = clean_text.replace('<br>', '\n').replace('<br/>', '\n').replace('​', '')
                clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()

                if query.message.caption is not None or query.message.video or query.message.photo:
                    await query.edit_message_caption(
                        caption=clean_text, parse_mode=ParseMode.HTML, reply_markup=markup
                    )
                else:
                    await query.edit_message_text(
                        text=clean_text, parse_mode=ParseMode.HTML, reply_markup=markup, disable_web_page_preview=True
                    )
            except Exception as e2:
                LOGGER.error(f"Fallback edit also failed: {e2}")

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

application.add_handler(CommandHandler("start", start, block=False), group=11)
application.add_handler(
    CallbackQueryHandler(button_callback, pattern=r"^sxc_", block=False)
)
application.add_handler(ChatMemberHandler(bot_added_to_group_handler, ChatMemberHandler.MY_CHAT_MEMBER, block=False))

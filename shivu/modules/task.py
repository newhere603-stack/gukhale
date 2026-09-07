import time
import re
import html
import asyncio
import urllib.parse
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, filters
from telegram.constants import ParseMode
import logging

from shivu import application, db
from shivu.Database.db import eco_collection

LOGGER = logging.getLogger(__name__)

# ==========================================
# ⚙️ CONFIG
# ==========================================
IST = timezone(timedelta(hours=5, minutes=30))
OWNER_ID = 7657218453
LOG_GROUP_ID = -1003893927065
TASKS_PER_PAGE = 5

tasks_collection = db['bot_tasks']
user_tasks_collection = db['user_tasks']

# ==========================================
# ✍️ SMALL CAPS
# ==========================================
def to_small_caps(text: str) -> str:
    if not text:
        return "ᴜɴᴋɴᴏᴡɴ"
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    small = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ0123456789"
    return str(text).translate(str.maketrans(normal, small))

sc = to_small_caps

# ==========================================
# 📡 LOGGING
# ==========================================
def create_log_message(title: str, data: dict) -> str:
    timestamp = datetime.now(IST).strftime("%I:%M %p • %d/%m/%y")
    base = f"<b>{title}</b>\n\n"
    items = list(data.items())
    for i, (key, value) in enumerate(items):
        prefix = "<b>╰</b>" if i == len(items) - 1 else "<b>├</b>"
        base += f"{prefix} <b>{key} :</b> {value}\n"
    base += f"\n<b>⌚ {sc('ᴛɪᴍᴇ')} :</b> <b>{timestamp}</b>"
    return base

async def send_log(context: CallbackContext, text: str):
    try:
        await context.bot.send_message(
            chat_id=LOG_GROUP_ID,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception as e:
        LOGGER.error(f"Task Log error: {e}")

# ==========================================
# 🔄 DAILY RESET + ENSURE USER DATA
# ==========================================
async def ensure_user_data(user_id: int):
    user_data = await user_tasks_collection.find_one({'user_id': user_id})
    today_str = datetime.now(IST).strftime("%Y-%m-%d")

    if not user_data:
        new_data = {
            'user_id': user_id,
            'completed_daily': [],
            'completed_onetime': [],
            'coins_spent_today': 0,
            'messages_sent_today': 0, # Added for Chat Tracking
            'pending_invites': 0,
            'total_invites': 0,
            'last_reset_date': today_str
        }
        await user_tasks_collection.insert_one(new_data)
        return new_data

    if user_data.get('last_reset_date') != today_str:
        await user_tasks_collection.update_one(
            {'user_id': user_id},
            {'$set': {
                'completed_daily': [],
                'coins_spent_today': 0,
                'messages_sent_today': 0, # Reset daily messages
                'last_reset_date': today_str
            }}
        )
        return await user_tasks_collection.find_one({'user_id': user_id})

    return user_data

# ==========================================
# ✉️ MESSAGE TRACKER (To prevent fake claims)
# ==========================================
async def track_user_messages(update: Update, context: CallbackContext):
    if update.effective_user and not update.effective_user.is_bot:
        user_id = update.effective_user.id
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        # Increment message count silently in background
        await user_tasks_collection.update_one(
            {'user_id': user_id, 'last_reset_date': today_str},
            {'$inc': {'messages_sent_today': 1}}
        )

# ==========================================
# 🎁 WELCOME + REFERRAL
# ==========================================
async def handle_referral(update: Update, context: CallbackContext):
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    raw_first_name = update.effective_user.first_name or "User"
    safe_name = html.escape(raw_first_name)

    user_task_data = await user_tasks_collection.find_one({'user_id': user_id})

    if not user_task_data:
        await eco_collection.update_one(
            {'id': user_id},
            {'$inc': {'balance': 1000}, '$set': {'first_name': raw_first_name}},
            upsert=True
        )

        if context.args and context.args[0].startswith("ref_"):
            try:
                referrer_id = int(context.args[0].split("_")[1])
                if referrer_id != user_id:
                    await user_tasks_collection.update_one(
                        {'user_id': referrer_id},
                        {'$inc': {'pending_invites': 1, 'total_invites': 1}},
                        upsert=True
                    )
                    try:
                        ref_msg = (
                            f"<b>{sc('SUCCESSFUL REFERRAL A NEW USER JOINED VIA YOUR LINK')}\n\n"
                            f"{sc('USE')} /tasks {sc('TO CLAIM YOUR REWARD OF 25,000 COINS')}</b>"
                        )
                        await context.bot.send_message(chat_id=referrer_id, text=ref_msg, parse_mode=ParseMode.HTML)
                    except Exception:
                        pass

                    log_data = {
                        sc("ɴᴇᴡ ᴜsᴇʀ"): f"<b><a href='tg://user?id={user_id}'>{safe_name}</a></b>",
                        sc("ɪᴅ"): f"<code>{user_id}</code>",
                        sc("ʀᴇғᴇʀʀᴇᴅ ʙʏ"): f"<code>{referrer_id}</code>",
                        sc("sᴛᴀᴛᴜs"): f"<b>{sc('Pending Claim')}</b>"
                    }
                    asyncio.create_task(send_log(context, create_log_message(f"˹ {sc('ɴᴇᴡ ʀᴇғᴇʀʀᴀʟ')} ˼", log_data)))
            except ValueError:
                pass

        await user_tasks_collection.insert_one({
            'user_id': user_id,
            'completed_daily': [],
            'completed_onetime': [],
            'coins_spent_today': 0,
            'messages_sent_today': 0,
            'pending_invites': 0,
            'total_invites': 0,
            'last_reset_date': datetime.now(IST).strftime("%Y-%m-%d")
        })

        welcome_text = (
            f"<b>{sc('WELCOME YOU RECEIVED 1,000 COINS FOR STARTING THE BOT')}</b>\n"
            f"<b>{sc('USE')} /tasks {sc('TO COMPLETE MISSIONS AND EARN MORE')}</b>"
        )
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)

# ==========================================
# 🛠️ ADMIN COMMANDS
# ==========================================
async def addtask(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return

    try:
        raw_text = update.message.text.split(" ", 1)[1]
        parts = [p.strip() for p in raw_text.split("|")]

        if len(parts) < 5:
            raise ValueError("Not enough parts")

        t_type = parts[0].lower()
        difficulty = parts[1].lower()
        reward = int(parts[2])
        button_name = parts[3]
        mission = parts[4]
        url = None

        if len(parts) > 5 and parts[5].lower() not in ("none", "null", ""):
            url = parts[5]

        if t_type not in ("daily", "onetime"):
            raise ValueError("type must be daily or onetime")
        if difficulty not in ("easy", "normal", "hard"):
            difficulty = "normal"

        task_id = f"task_{int(time.time())}"

        await tasks_collection.insert_one({
            'task_id': task_id,
            'type': t_type,
            'difficulty': difficulty,
            'reward': reward,
            'name': button_name,
            'mission': mission,
            'url': url
        })

        msg = (
            f"<b>✅ {sc('NEW TASK ADDED SUCCESSFULLY')}</b>\n"
            f"<blockquote>"
            f"<b>{sc('ID')}:</b> <code>{task_id}</code>\n"
            f"<b>{sc('BUTTON')}:</b> <b>{html.escape(button_name)}</b>\n"
            f"<b>{sc('MISSION')}:</b> <b>{html.escape(mission)}</b>\n"
            f"<b>{sc('REWARD')}:</b> <b>{reward:,} 💸</b>\n"
            f"<b>{sc('TYPE')}:</b> <b>{sc(t_type.upper())}</b>\n"
            f"<b>{sc('DIFFICULTY')}:</b> <b>{sc(difficulty.upper())}</b>"
            f"</blockquote>"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    except Exception as e:
        error_msg = (
            f"<b>⚠️ {sc('INVALID FORMAT')}</b>\n\n"
            f"<b>{sc('USAGE')}:</b>\n"
            f"<code>/addtask type | difficulty | reward | Button Name | Mission Description | URL(or None)</code>\n\n"
            f"<b>{sc('EXAMPLES')}:</b>\n"
            f"<code>/addtask daily | easy | 5000 | Join Channel | Join our official channel | https://t.me/yourchannel</code>\n"
            f"<code>/addtask daily | normal | 3000 | Message Task | Send 50 messages in the group | None</code>\n"
            f"<code>/addtask daily | normal | 10000 | Spend Coins | Spend 10000 coins | None</code>"
        )
        await update.message.reply_text(error_msg, parse_mode=ParseMode.HTML)

async def tasklist(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return

    try:
        tasks = await tasks_collection.find({}).to_list(length=1000)
        if not tasks:
            await update.message.reply_text(f"<b>{sc('NO TASKS FOUND')}</b>", parse_mode=ParseMode.HTML)
            return

        msg = f"<b>📋 {sc('ALL ACTIVE TASKS')}</b>\n\n"
        keyboard = []
        for t in tasks:
            t_name = html.escape(t.get('name', 'UNKNOWN'))
            t_mission = html.escape(t.get('mission', ''))
            t_id = t['task_id']
            msg += (
                f"<b>{sc('BUTTON')}:</b> {t_name}\n"
                f"<b>{sc('MISSION')}:</b> {t_mission}\n"
                f"<b>{sc('ID')}:</b> <code>{t_id}</code>\n\n"
            )
            keyboard.append([InlineKeyboardButton(f"🗑️ Delete {t_name[:18]}", callback_data=f"dt_{t_id}")])

        msg += f"<b><i>{sc('CLICK THE BUTTON BELOW TO DELETE A TASK')}</i></b>"
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    except Exception as e:
        LOGGER.error(f"Tasklist Error: {e}")
        await update.message.reply_text(f"<b>⚠️ ERROR:</b> {e}", parse_mode=ParseMode.HTML)

async def removetask(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return

    if not context.args:
        await update.message.reply_text(
            f"<b>{sc('USAGE:')} /removetask task_id</b>\n{sc('USE')} /tasklist {sc('TO FIND OR DELETE EASILY')}",
            parse_mode=ParseMode.HTML
        )
        return

    task_id = context.args[0]
    result = await tasks_collection.delete_one({'task_id': task_id})
    if result.deleted_count > 0:
        await update.message.reply_text(f"<b>✅ {sc('TASK REMOVED SUCCESSFULLY')}</b>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"<b>❌ {sc('TASK NOT FOUND')}</b>", parse_mode=ParseMode.HTML)

# ==========================================
# 🔧 KEYBOARD + CAPTION BUILDER
# ==========================================
async def build_task_keyboard(user_id: int, bot_username: str, page: int = 0):
    user_data = await ensure_user_data(user_id)

    completed_daily = set(user_data.get('completed_daily', []))
    completed_onetime = set(user_data.get('completed_onetime', []))
    pending_invites = user_data.get('pending_invites', 0)
    total_invites = user_data.get('total_invites', 0)

    all_tasks = await tasks_collection.find({}).to_list(length=1000)
    total_pages = max(1, (len(all_tasks) + TASKS_PER_PAGE - 1) // TASKS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))

    start = page * TASKS_PER_PAGE
    end = start + TASKS_PER_PAGE
    page_tasks = all_tasks[start:end]

    keyboard = []

    # ========== FIRST ROW: Back | Refresh | Next ==========
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⋞", callback_data=f"bk_{user_id}_{page}", style="primary"))
    else:
        nav_row.append(InlineKeyboardButton("⋞", callback_data=f"ign_{user_id}"))

    nav_row.append(InlineKeyboardButton("⟳", callback_data=f"rf_{user_id}_{page}", style="primary"))

    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("⋟", callback_data=f"nx_{user_id}_{page}", style="primary"))
    else:
        nav_row.append(InlineKeyboardButton("⋟", callback_data=f"ign_{user_id}"))

    keyboard.append(nav_row)

    # ========== TASK ROWS ==========
    for task in page_tasks:
        t_id = task['task_id']
        is_completed = (t_id in completed_daily) or (t_id in completed_onetime)
        difficulty = task.get('difficulty', 'normal').lower()
        name_text = sc(task.get('name', 'Task'))
        reward_text = f"{int(task.get('reward', 0)):,} 💸"

        if is_completed:
            btn_style = "success"
        elif difficulty == "hard":
            btn_style = "danger"
        elif difficulty == "easy":
            btn_style = "primary"
        else:
            btn_style = None

        row = []

        if task.get('url') and not is_completed:
            row.append(InlineKeyboardButton(name_text, url=task['url'], style=btn_style))
        else:
            row.append(InlineKeyboardButton(name_text, callback_data=f"ign_{user_id}", style=btn_style))

        row.append(InlineKeyboardButton(reward_text, callback_data=f"ign_{user_id}"))

        if is_completed:
            row.append(InlineKeyboardButton("✅", callback_data=f"ign_{user_id}", style="success"))
        else:
            row.append(InlineKeyboardButton(sc("check"), callback_data=f"vt_{user_id}_{t_id}_{page}", style=btn_style))

        keyboard.append(row)

    # ========== INVITE ROW ==========
    invite_claim_text = sc('claim') if pending_invites > 0 else sc('check')
    invite_style = "success" if pending_invites > 0 else "primary"

    keyboard.append([
        InlineKeyboardButton(sc('invites'), callback_data=f"ign_{user_id}"),
        InlineKeyboardButton(f"{total_invites} {sc('friends')}", callback_data=f"ign_{user_id}"),
        InlineKeyboardButton(invite_claim_text, callback_data=f"ci_{user_id}_{page}", style=invite_style)
    ])

    # ========== SHARE LINK ==========
    invite_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    raw_share_text = (
        f"{sc('STEP INTO THE ULTIMATE WAIFU BOT')}\n\n"
        f"{sc('COLLECT BEAUTIFUL WAIFUS PLAY GAMES AND EARN HUGE REWARDS')}\n"
        f"{sc('JOIN USING MY LINK AND GET 1000 COINS FREE STARTING BONUS')}\n\n"
        f"{sc('TAP TO START')}: {invite_link}"
    )
    encoded_text = urllib.parse.quote(raw_share_text)
    share_url = f"https://t.me/share/url?text={encoded_text}"
    keyboard.append([InlineKeyboardButton(sc('share invite link'), url=share_url, style="primary")])

    # ========== CAPTION ==========
    caption = (
        f"<b>📋 <a href='tg://user?id={user_id}'>{sc('TASK DASHBOARD')}</a></b>\n\n"
        f"<b>Page {page + 1}/{total_pages}</b>\n\n"
    )

    if not page_tasks:
        caption += f"<b>{sc('NO TASKS ON THIS PAGE')}</b>"
    else:
        for idx, task in enumerate(page_tasks, 1):
            t_id = task['task_id']
            is_completed = (t_id in completed_daily) or (t_id in completed_onetime)
            status = "✅" if is_completed else "▫️"
            
            mission = html.escape(task.get('mission', task.get('name', '')))
            name = html.escape(task.get('name', 'Task'))
            reward = f"{int(task.get('reward', 0)):,}"

            # 🛠️ Updated Single Line Format Logic with small caps
            caption += f"{status} <b>{sc(name)} • {sc(mission)} • {reward} 💸</b>\n\n"

    return InlineKeyboardMarkup(keyboard), caption, page, total_pages

# ==========================================
# 📋 /tasks COMMAND
# ==========================================
async def tasks_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    keyboard, caption, page, total_pages = await build_task_keyboard(user_id, context.bot.username, page=0)

    photo_url = "https://files.catbox.moe/lge487.png"

    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=photo_url,
            caption=caption,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
            reply_to_message_id=update.message.message_id if update.message else None
        )
    except Exception as e:
        LOGGER.error(f"Task photo send error: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=caption,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
            reply_to_message_id=update.message.message_id if update.message else None
        )

# ==========================================
# 🔘 CALLBACK HANDLER
# ==========================================
async def task_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    clicker_id = query.from_user.id
    data = query.data

    try:
        # ========== ADMIN DELETE ==========
        if data.startswith("dt_"):
            if clicker_id != OWNER_ID:
                await query.answer(sc("YOU ARE NOT AUTHORIZED"), show_alert=True)
                return

            task_id = data[3:]
            res = await tasks_collection.delete_one({'task_id': task_id})

            if res.deleted_count > 0:
                await query.answer(sc("TASK DELETED SUCCESSFULLY"), show_alert=True)
                try:
                    await query.message.delete()
                except Exception:
                    pass

                tasks = await tasks_collection.find({}).to_list(length=1000)
                if not tasks:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"<b>{sc('NO TASKS FOUND')}</b>",
                        parse_mode=ParseMode.HTML
                    )
                    return

                msg = f"<b>📋 {sc('ALL ACTIVE TASKS')}</b>\n\n"
                keyboard = []
                for t in tasks:
                    t_name = html.escape(t.get('name', 'UNKNOWN'))
                    t_mission = html.escape(t.get('mission', ''))
                    msg += (
                        f"<b>{sc('BUTTON')}:</b> {t_name}\n"
                        f"<b>{sc('MISSION')}:</b> {t_mission}\n"
                        f"<b>{sc('ID')}:</b> <code>{t['task_id']}</code>\n\n"
                    )
                    keyboard.append([InlineKeyboardButton(f"🗑️ Delete {t_name[:18]}", callback_data=f"dt_{t['task_id']}")])

                msg += f"<b><i>{sc('CLICK THE BUTTON BELOW TO DELETE A TASK')}</i></b>"
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=msg,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )
            else:
                await query.answer(sc("TASK NOT FOUND"), show_alert=True)
            return

        # ========== SAFE PARSING ==========
        parts = data.split("_")
        action = parts[0]

        if action not in ("ign", "ci", "vt", "rf", "nx", "bk"):
            await query.answer()
            return

        try:
            owner_id = int(parts[1])
        except (IndexError, ValueError):
            await query.answer("Invalid data", show_alert=True)
            return

        if clicker_id != owner_id:
            await query.answer(
                f"{sc('PLEASE USE')} /tasks {sc('COMMAND TO OPEN YOUR OWN DASHBOARD')}",
                show_alert=True
            )
            return

        if action == "ign":
            await query.answer()
            return

        # ========== REFRESH / NEXT / BACK ==========
        if action in ("rf", "nx", "bk"):
            try:
                current_page = int(parts[2])
            except (IndexError, ValueError):
                current_page = 0

            if action == "nx":
                new_page = current_page + 1
            elif action == "bk":
                new_page = max(0, current_page - 1)
            else:
                new_page = current_page

            new_kb, new_caption, _, _ = await build_task_keyboard(owner_id, context.bot.username, page=new_page)

            try:
                await query.edit_message_caption(
                    caption=new_caption,
                    reply_markup=new_kb,
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                try:
                    await query.edit_message_reply_markup(reply_markup=new_kb)
                except Exception:
                    pass
            await query.answer()
            return

        # ========== INVITE CLAIM ==========
        if action == "ci":
            try:
                page = int(parts[2]) if len(parts) > 2 else 0
            except ValueError:
                page = 0

            user_data = await ensure_user_data(owner_id)
            pending = user_data.get('pending_invites', 0)

            if pending <= 0:
                await query.answer(sc("NO PENDING INVITES TO CLAIM SHARE YOUR LINK WITH FRIENDS"), show_alert=True)
                return

            res = await user_tasks_collection.update_one(
                {'user_id': owner_id, 'pending_invites': {'$gte': 1}},
                {'$set': {'pending_invites': 0}}
            )

            if res.modified_count == 0:
                await query.answer(sc("YOU HAVE ALREADY CLAIMED THIS"), show_alert=True)
                return

            reward = pending * 25000
            await eco_collection.update_one({'id': owner_id}, {'$inc': {'balance': reward}}, upsert=True)

            await query.answer(
                f"{sc('claim successful')}\n{sc('you received')} {reward:,} {sc('coins for')} {pending} {sc('invites')}",
                show_alert=True
            )

            new_kb, new_caption, _, _ = await build_task_keyboard(owner_id, context.bot.username, page=page)
            try:
                await query.edit_message_caption(
                    caption=new_caption,
                    reply_markup=new_kb,
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                try:
                    await query.edit_message_reply_markup(reply_markup=new_kb)
                except Exception:
                    pass
            return

        # ========== NORMAL TASK CLAIM ==========
        if action == "vt":
            try:
                page = int(parts[-1])
                task_id = "_".join(parts[2:-1])
            except (IndexError, ValueError):
                await query.answer("Invalid task data", show_alert=True)
                return

            user_data = await ensure_user_data(owner_id)

            if task_id in user_data.get('completed_daily', []) or task_id in user_data.get('completed_onetime', []):
                await query.answer(sc("YOU HAVE ALREADY COMPLETED THIS TASK"), show_alert=True)
                return

            task = await tasks_collection.find_one({'task_id': task_id})
            if not task:
                await query.answer(sc("THIS TASK IS NO LONGER AVAILABLE"), show_alert=True)
                return

            check_text = (str(task.get('name', '')) + " " + str(task.get('mission', ''))).lower()
            
            # 1. CHANNEL JOIN CHECK
            need_join_check = ("join" in check_text or "subscribe" in check_text) and task.get('url')
            if need_join_check and "t.me/" in str(task.get('url', '')) and "+" not in task['url'] and "joinchat" not in task['url']:
                try:
                    channel_username = "@" + task['url'].split("t.me/")[1].split("/")[0].split("?")[0].strip()
                    member = await context.bot.get_chat_member(chat_id=channel_username, user_id=owner_id)

                    status = getattr(member, 'status', '')
                    status_str = str(getattr(status, 'value', status)).lower()

                    valid_statuses = ['member', 'creator', 'administrator', 'restricted']
                    if not any(v in status_str for v in valid_statuses):
                        await query.answer(sc("PLEASE JOIN THE CHANNEL FIRST THEN CLICK CHECK"), show_alert=True)
                        return
                except Exception as e:
                    error_msg = str(e).lower()
                    LOGGER.error(f"Channel Verify Error: {e}")
                    if "user not found" in error_msg or "chat not found" in error_msg:
                        await query.answer(sc("PLEASE JOIN THE CHANNEL FIRST THEN CLICK CHECK"), show_alert=True)
                        return

            # 2. MESSAGE SEND CHECK 
            msg_match = re.search(r'(?:send|chat|message|msg)\s+(\d+)', check_text)
            if msg_match:
                req_msgs = int(msg_match.group(1))
                if user_data.get('messages_sent_today', 0) < req_msgs:
                    await query.answer(sc(f"MISSION INCOMPLETE YOU HAVE SENT {user_data.get('messages_sent_today', 0)}/{req_msgs} MESSAGES TODAY"), show_alert=True)
                    return

            # 3. SPEND COINS CHECK (Ab check karega properly bina bug ke)
            if "spend" in check_text or "use" in check_text:
                spend_match = re.search(r'(?:spend|use)\s+(\d+)', check_text)
                if spend_match:
                    req_spend = int(spend_match.group(1))
                else:
                    # Agar task ke text me number nahi likha hai, toh reward amount ko hi required spend maan lega
                    req_spend = int(task.get('reward', 0))
                    
                if user_data.get('coins_spent_today', 0) < req_spend:
                    await query.answer(sc(f"MISSION INCOMPLETE YOU HAVE SPENT {user_data.get('coins_spent_today', 0)}/{req_spend} COINS TODAY"), show_alert=True)
                    return

            # Agar sab rules cross ho gaye to yaha reward de do
            t_type = task.get('type', 'daily').lower()
            field = 'completed_onetime' if t_type == 'onetime' else 'completed_daily'

            res = await user_tasks_collection.update_one(
                {
                    'user_id': owner_id,
                    field: {'$ne': task_id}
                },
                {
                    '$addToSet': {field: task_id}
                }
            )

            if res.modified_count == 0:
                await query.answer(sc("YOU HAVE ALREADY COMPLETED THIS TASK"), show_alert=True)
                return

            reward = int(task.get('reward', 0))
            await eco_collection.update_one(
                {'id': owner_id},
                {'$inc': {'balance': reward}},
                upsert=True
            )

            await query.answer(
                f"✅ {sc('TASK COMPLETED')}!\n{sc('YOU RECEIVED')} {reward:,} 💸",
                show_alert=True
            )

            new_kb, new_caption, _, _ = await build_task_keyboard(owner_id, context.bot.username, page=page)
            try:
                await query.edit_message_caption(
                    caption=new_caption,
                    reply_markup=new_kb,
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                try:
                    await query.edit_message_reply_markup(reply_markup=new_kb)
                except Exception:
                    pass

            try:
                log_data = {
                    sc("ᴜsᴇʀ"): f"<a href='tg://user?id={owner_id}'>{html.escape(query.from_user.first_name or 'User')}</a>",
                    sc("ʙᴜᴛᴛᴏɴ"): html.escape(task.get('name', '')),
                    sc("ᴍɪssɪᴏɴ"): html.escape(task.get('mission', '')),
                    sc("ʀᴇᴡᴀʀᴅ"): f"{reward:,} 💸",
                    sc("ᴛʏᴘᴇ"): sc(t_type.upper())
                }
                asyncio.create_task(send_log(context, create_log_message(f"˹ {sc('ᴛᴀsᴋ ᴄᴏᴍᴘʟᴇᴛᴇᴅ')} ˼", log_data)))
            except Exception:
                pass

            return

        await query.answer()

    except Exception as e:
        LOGGER.error(f"task_callback error: {e}", exc_info=True)
        try:
            await query.answer("Something went wrong, try again", show_alert=True)
        except Exception:
            pass

# ==========================================
# 📌 HANDLERS REGISTER (IMPORTANT)
# ==========================================
application.add_handler(CommandHandler(["tasks", "task"], tasks_cmd))
application.add_handler(CommandHandler("addtask", addtask))
application.add_handler(CommandHandler("tasklist", tasklist))
application.add_handler(CommandHandler("removetask", removetask))
application.add_handler(CallbackQueryHandler(task_callback, pattern=r"^(dt_|ign_|ci_|vt_|rf_|nx_|bk_)"))

# YE HANDLER BHI ADD KIYA HAI MESSAGE COUNT KARNE KE LIYE
application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, track_user_messages), group=32)

import time
import re
import html
import asyncio
import urllib.parse
import random
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
# 🔘 SMART BUTTON HELPER
# ==========================================
def ibtn(text, cb=None, url=None, style=None, icon=None):
    if text == "":
        text = "\u200b"
        
    kw = {"text": text}
    if cb: kw["callback_data"] = cb
    if url: kw["url"] = url
    if style: kw["style"] = style
    if icon: kw["icon_custom_emoji_id"] = icon
    return InlineKeyboardButton(**kw)

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
            'group_messages_today': {},
            'explore_count_today': 0,
            'propose_count_today': 0,  # 🔥 NEW
            'marry_count_today': 0,    # 🔥 NEW
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
                'group_messages_today': {}, 
                'explore_count_today': 0,
                'propose_count_today': 0,  # 🔥 NEW
                'marry_count_today': 0,    # 🔥 NEW
                'last_reset_date': today_str
            }}
        )
        return await user_tasks_collection.find_one({'user_id': user_id})

    return user_data

# ==========================================
# ✉️ MESSAGE TRACKER 
# ==========================================
async def track_user_messages(update: Update, context: CallbackContext):
    if update.effective_user and not update.effective_user.is_bot:
        if update.effective_chat.type in ['group', 'supergroup']:
            user_id = update.effective_user.id
            chat_id = str(update.effective_chat.id)
            today_str = datetime.now(IST).strftime("%Y-%m-%d")
            
            result = await user_tasks_collection.update_one(
                {'user_id': user_id, 'last_reset_date': today_str},
                {'$inc': {f'group_messages_today.{chat_id}': 1}}
            )
            
            if result.modified_count == 0:
                await ensure_user_data(user_id)
                await user_tasks_collection.update_one(
                    {'user_id': user_id, 'last_reset_date': today_str},
                    {'$inc': {f'group_messages_today.{chat_id}': 1}}
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
        is_referral = context.args and context.args[0].startswith("ref_")
        bonus_coins = 10000 if is_referral else 1000  # 🔥 Invite link se 10k warna normal 1k
        
        await eco_collection.update_one(
            {'id': user_id},
            {'$inc': {'balance': bonus_coins}, '$set': {'first_name': raw_first_name}},
            upsert=True
        )

        if is_referral:
            try:
                referrer_id = int(context.args[0].split("_")[1])
                if referrer_id != user_id:
                    await user_tasks_collection.update_one(
                        {'user_id': referrer_id},
                        {'$inc': {'pending_invites': 1, 'total_invites': 1}},
                        upsert=True
                    )
                    try:
                        # 🔥 Referrer Msg With Premium Emojis
                        ref_msg = (
                            f"<b><tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji> {sc('SUCCESSFUL REFERRAL A NEW USER JOINED VIA YOUR LINK')}\n\n"
                            f"{sc('USE')} /tasks {sc('TO CLAIM YOUR REWARD OF')} <b>25,000</b> <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {sc('COINS')}</b>"
                        )
                        await context.bot.send_message(chat_id=referrer_id, text=ref_msg, parse_mode=ParseMode.HTML)
                    except Exception:
                        pass

                    log_data = {
                        sc("ɴᴇᴡ ᴜsᴇʀ"): f"<b><a href='tg://user?id={user_id}'>{safe_name}</a></b>",
                        sc("ɪᴅ"): f"<b>{user_id}</b>",
                        sc("ʀᴇғᴇʀʀᴇᴅ ʙʏ"): f"<b>{referrer_id}</b>",
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
            'group_messages_today': {},
            'explore_count_today': 0,
            'propose_count_today': 0,
            'marry_count_today': 0,
            'pending_invites': 0,
            'total_invites': 0,
            'last_reset_date': datetime.now(IST).strftime("%Y-%m-%d")
        })

        # 🔥 Conditional Welcome Message
        if is_referral:
            welcome_text = (
                f"<b><tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji> {sc('WELCOME YOU RECEIVED')} <b>10,000</b> <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {sc('COINS FOR STARTING THE BOT VIA INVITE LINK')}</b>\n"
                f"<b>{sc('USE')} /tasks {sc('TO COMPLETE MISSIONS AND EARN MORE')}</b>"
            )
        else:
            welcome_text = (
                f"<b>{sc('WELCOME YOU RECEIVED')} <b>1,000</b> {sc('COINS FOR STARTING THE BOT')}</b>\n"
                f"<b>{sc('USE')} /tasks {sc('TO COMPLETE MISSIONS AND EARN MORE')}</b>"
            )
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)

# ==========================================
# 🛠️ ADMIN COMMANDS
# ==========================================
async def addtask(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return

    message = update.effective_message
    if not message or not message.text:
        return

    try:
        parts_initial = message.text.split(" ", 1)
        if len(parts_initial) < 2:
            raise ValueError("Missing arguments")

        raw_text = parts_initial[1]
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

        channel = None
        if len(parts) > 6 and parts[6].lower() not in ("none", "null", ""):
            channel = parts[6]

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
            'url': url,
            'channel': channel
        })

        msg = (
            f"<b><tg-emoji emoji-id=\"6100397639717625616\">✔️</tg-emoji> {sc('NEW TASK ADDED SUCCESSFULLY')}</b>\n"
            f"<blockquote>"
            f"<b>{sc('ID')}:</b> <b>{task_id}</b>\n"
            f"<b>{sc('BUTTON')}:</b> <b>{html.escape(button_name)}</b>\n"
            f"<b>{sc('MISSION')}:</b> <b>{html.escape(mission)}</b>\n"
            f"<b>{sc('REWARD')}:</b> <b>{reward:,}</b> <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>\n"
            f"<b>{sc('TYPE')}:</b> <b>{sc(t_type.upper())}</b>\n"
            f"<b>{sc('DIFFICULTY')}:</b> <b>{sc(difficulty.upper())}</b>\n"
            f"<b>{sc('CHANNEL')}:</b> <b>{html.escape(str(channel))}</b>"
            f"</blockquote>"
        )
        await message.reply_text(msg, parse_mode=ParseMode.HTML)

    except Exception as e:
        error_msg = (
            f"<b><tg-emoji emoji-id=\"6105189427355589893\">⚠️</tg-emoji> {sc('INVALID FORMAT')}</b>\n\n"
            f"<b>{sc('USAGE')}:</b>\n"
            f"<code>/addtask type | difficulty | reward | Button Name | Mission Description | URL(or None) | Channel_ID(or None)</code>\n\n"
            f"<b>{sc('EXAMPLES')}:</b>\n"
            f"<code>/addtask daily | easy | 5000 | Join Channel | Join our official channel | https://t.me/yourchannel | @yourchannel</code>\n"
            f"<code>/addtask daily | normal | 10000 | Spend Coins | Spend 10000 coins | None | None</code>\n"
            f"<code>/addtask daily | hard | 5000 | True Love | Propose 10 times | None | None</code>"
        )
        await message.reply_text(error_msg, parse_mode=ParseMode.HTML)

async def tasklist(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return

    try:
        tasks = await tasks_collection.find({}).to_list(length=1000)
        if not tasks:
            await update.message.reply_text(f"<b>{sc('NO TASKS FOUND')}</b>", parse_mode=ParseMode.HTML)
            return

        msg = f"<b><tg-emoji emoji-id=\"5197269100878907942\">✍️</tg-emoji> {sc('ALL ACTIVE TASKS')}</b>\n\n"
        keyboard = []
        for t in tasks:
            t_name = html.escape(t.get('name', 'UNKNOWN'))
            t_mission = html.escape(t.get('mission', ''))
            t_id = t['task_id']
            t_channel = html.escape(str(t.get('channel', 'None')))
            msg += (
                f"<b>{sc('BUTTON')}:</b> {t_name}\n"
                f"<b>{sc('MISSION')}:</b> {t_mission}\n"
                f"<b>{sc('ID')}:</b> <b>{t_id}</b>\n"
                f"<b>{sc('CH')}:</b> {t_channel}\n\n"
            )
            keyboard.append([InlineKeyboardButton(f"🗑️ Delete {t_name[:18]}", callback_data=f"dt_{t_id}")])

        msg += f"<b><i>{sc('CLICK THE BUTTON BELOW TO DELETE A TASK')}</i></b>"
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    except Exception as e:
        LOGGER.error(f"Tasklist Error: {e}")
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"6105189427355589893\">⚠️</tg-emoji> ERROR:</b> {e}", parse_mode=ParseMode.HTML)

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
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"6100397639717625616\">✔️</tg-emoji> {sc('TASK REMOVED SUCCESSFULLY')}</b>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"<b><tg-emoji emoji-id=\"6105189427355589893\">⚠️</tg-emoji> {sc('TASK NOT FOUND')}</b>", parse_mode=ParseMode.HTML)

# ==========================================
# 🔧 KEYBOARD + CAPTION BUILDER 
# ==========================================
async def build_task_keyboard(user_id: int, bot_username: str, page: int = 0, chat_id: str = None, chat_type: str = 'private'):
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
    nav_row = []
    if page > 0:
        nav_row.append(ibtn("", cb=f"bk_{user_id}_{page}", style="primary", icon="5258236805890710909"))
    else:
        nav_row.append(ibtn("", cb=f"ign_{user_id}", style="primary", icon="5258236805890710909"))

    nav_row.append(ibtn("", cb=f"rf_{user_id}_{page}", style="primary", icon="5258420634785947640"))

    if page < total_pages - 1:
        nav_row.append(ibtn("", cb=f"nx_{user_id}_{page}", style="primary", icon="5260450573768990626"))
    else:
        nav_row.append(ibtn("", cb=f"ign_{user_id}", style="primary", icon="5260450573768990626"))

    keyboard.append(nav_row)

    for task in page_tasks:
        t_id = task['task_id']
        is_completed = (t_id in completed_daily) or (t_id in completed_onetime)
        difficulty = task.get('difficulty', 'normal').lower()
        
        name_text = sc(task.get('name', 'Task'))
        reward_text = f"{int(task.get('reward', 0)):,}"

        if is_completed:
            btn_style = "success"
        elif difficulty == "hard":
            btn_style = "danger"
        elif difficulty == "easy":
            btn_style = "primary"
        else:
            btn_style = None

        row = []

        raw_url = str(task.get('url', '')).strip()
        if raw_url and not is_completed and raw_url.lower() not in ("none", "null"):
            if raw_url.startswith('@'):
                raw_url = f"https://t.me/{raw_url[1:]}"
            elif raw_url.startswith('t.me/'):
                raw_url = f"https://{raw_url}"
                
            if raw_url.startswith(('http://', 'https://', 'tg://')):
                row.append(ibtn(name_text, url=raw_url, style=btn_style))
            else:
                row.append(ibtn(name_text, cb=f"ign_{user_id}", style=btn_style))
        else:
            row.append(ibtn(name_text, cb=f"ign_{user_id}", style=btn_style))

        row.append(ibtn(reward_text, cb=f"ign_{user_id}", style=btn_style, icon="5472030678633684592"))

        if is_completed:
            row.append(ibtn("", cb=f"ign_{user_id}", style="success", icon="6100397639717625616"))
        else:
            row.append(ibtn(sc("check"), cb=f"vt_{user_id}_{t_id}_{page}", style=btn_style))

        keyboard.append(row)

    invite_claim_text = sc('claim') if pending_invites > 0 else sc('check')
    invite_style = "primary"

    keyboard.append([
        ibtn(sc('invites'), cb=f"ign_{user_id}"),
        ibtn("25,000", cb=f"ign_{user_id}", icon="5472030678633684592"),
        ibtn(invite_claim_text, cb=f"ci_{user_id}_{page}", style=invite_style)
    ])

    invite_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    raw_share_text = (
        f"✨ {sc('STEP INTO THE ULTIMATE WAIFU BOT')} ✨\n\n"
        f"🎴 {sc('COLLECT BEAUTIFUL WAIFUS PLAY GAMES AND EARN HUGE REWARDS')} 🎮\n"
        f"🎁 {sc('JOIN USING MY LINK AND GET 10000 COINS FREE STARTING BONUS')} 💰\n\n"
        f"🚀 {sc('TAP TO START')}: {invite_link}"
    )
    encoded_text = urllib.parse.quote(raw_share_text)
    share_url = f"https://t.me/share/url?text={encoded_text}"
    
    keyboard.append([ibtn(f"{sc('SHARE INVITE LINK')}", url=share_url, style="primary", icon="5769289093221454192")])

    photo_urls = [
        "https://files.catbox.moe/lge487.png",
        "https://files.catbox.moe/flth7m.png"
    ]
    img_url = random.choice(photo_urls)
    caption = f'<img src="{html.escape(img_url)}"/>'

    caption += (
        f'<b><tg-emoji emoji-id="5197269100878907942">✍️</tg-emoji> '
        f'<a href="tg://user?id={user_id}">{sc("TASK DASHBOARD")}</a> • '
        f'{sc("page")} <b>{page + 1}</b>/<b>{total_pages}</b></b>\n'
    )

    if not page_tasks:
        caption += f'\n<b>{sc("NO TASKS ON THIS PAGE")}</b>'
    else:
        for task in page_tasks:
            t_id = task['task_id']
            is_completed = (t_id in completed_daily or t_id in completed_onetime)

            status = '<tg-emoji emoji-id="6100397639717625616">✔️</tg-emoji>' if is_completed else '<tg-emoji emoji-id="6309702258023994825">🌟</tg-emoji>'
            name = html.escape(str(task.get('name', 'Task')))
            mission = html.escape(str(task.get('mission', task.get('name', 'Task'))))
            reward = f"{int(task.get('reward', 0)):,}"
            
            progress_text = ""
            msg_match = re.search(r'(?:send|chat|message|msg)\s+(\d+)', mission.lower())
            if msg_match and not is_completed:
                req_msgs = int(msg_match.group(1))
                if chat_type in ['group', 'supergroup'] and chat_id:
                    current_msgs = user_data.get('group_messages_today', {}).get(str(chat_id), 0)
                    progress_text = f" ({current_msgs}/{req_msgs})"
                else:
                    max_msgs = max(user_data.get('group_messages_today', {}).values()) if user_data.get('group_messages_today') else 0
                    progress_text = f" ({max_msgs}/{req_msgs})"

            spend_match = re.search(r'(?:spend|use)\s+(\d+)', mission.lower())
            if spend_match and not is_completed:
                req_spend = int(spend_match.group(1))
                current_spend = user_data.get('coins_spent_today', 0)
                progress_text = f" ({current_spend}/{req_spend})"

            explore_match = re.search(r'explore\s+(\d+)', mission.lower())
            if explore_match and not is_completed:
                req_explores = int(explore_match.group(1))
                current_explores = user_data.get('explore_count_today', 0)
                progress_text = f" ({current_explores}/{req_explores})"

            # 🔥 NEW: Propose Tasks
            propose_match = re.search(r'propose\s+(\d+)', mission.lower())
            if propose_match and not is_completed:
                req_proposes = int(propose_match.group(1))
                current_proposes = user_data.get('propose_count_today', 0)
                progress_text = f" ({current_proposes}/{req_proposes})"

            # 🔥 NEW: Marry Tasks
            marry_match = re.search(r'marry\s+(\d+)', mission.lower())
            if marry_match and not is_completed:
                req_marries = int(marry_match.group(1))
                current_marries = user_data.get('marry_count_today', 0)
                progress_text = f" ({current_marries}/{req_marries})"

            caption += (
                f'<h2>{status} {name} • {mission}{progress_text} • {reward} '
                f'<tg-emoji emoji-id="5472030678633684592">💸</tg-emoji></h2>'
            )

    return InlineKeyboardMarkup(keyboard), caption, page, total_pages, img_url

# ==========================================
# 📋 /tasks COMMAND
# ==========================================
async def tasks_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    
    keyboard, caption, page, total_pages, img_url = await build_task_keyboard(
        user_id, context.bot.username, page=0, chat_id=str(chat_id), chat_type=chat_type
    )

    reply_to = update.message.message_id if update.message else None
    data = {
        "chat_id": chat_id,
        "rich_message": {"html": caption},
        "reply_markup": keyboard.to_dict()
    }
    
    if reply_to:
        data["reply_to_message_id"] = reply_to

    try:
        await context.bot._post("sendRichMessage", data)
        return  # 🔥 FIX: Agar ye success hua to wahi ruk jayega, double message nahi dega
    except Exception as e:
        err_msg = str(e).lower()
        # Agar PTB parsing fail hua par message send ho chuka hai, toh doosra msg mat bhejo
        if "parse" in err_msg or "dictionary" in err_msg or "object" in err_msg:
            return 
            
        LOGGER.warning(f"Rich Message failed: {e}")
        try:
            clean_caption = re.sub(r'<img\b[^>]*>', '', caption, flags=re.IGNORECASE)
            clean_caption = (
                clean_caption
                .replace('<h2>', '\n<b>').replace('</h2>', '</b>\n')
                .replace('<h3>', '\n<b>').replace('</h3>', '</b>\n')
                .replace('<br>', '\n').replace('<br/>', '\n')
                .replace('​', '')
            )
            clean_caption = re.sub(r'\n{3,}', '\n\n', clean_caption).strip()
            
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=img_url,
                caption=clean_caption,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=reply_to
            )
        except Exception as e2:
            LOGGER.error(f"Fallback photo also failed: {e2}")

# ==========================================
# 🔘 CALLBACK HANDLER
# ==========================================
async def task_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    clicker_id = query.from_user.id
    data = query.data

    chat_id_str = str(query.message.chat.id) if query.message else None
    chat_type = query.message.chat.type if query.message else 'private'

    try:
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
                # Rest of delete logic as before...
            return

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

        if action in ("rf", "nx", "bk"):
            try:
                current_page = int(parts[2])
            except (IndexError, ValueError):
                current_page = 0
            new_page = current_page + 1 if action == "nx" else max(0, current_page - 1) if action == "bk" else current_page
            new_kb, new_caption, _, _, _ = await build_task_keyboard(
                owner_id, context.bot.username, page=new_page, chat_id=chat_id_str, chat_type=chat_type
            )
            try:
                await context.bot._post("editMessageText", {
                    "chat_id": query.message.chat_id,
                    "message_id": query.message.message_id,
                    "rich_message": {"html": new_caption},
                    "reply_markup": new_kb.to_dict()
                })
            except Exception:
                pass
            await query.answer()
            return

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

            new_kb, new_caption, _, _, _ = await build_task_keyboard(
                owner_id, context.bot.username, page=page, chat_id=chat_id_str, chat_type=chat_type
            )
            try:
                await context.bot._post("editMessageText", {
                    "chat_id": query.message.chat_id,
                    "message_id": query.message.message_id,
                    "rich_message": {"html": new_caption},
                    "reply_markup": new_kb.to_dict()
                })
            except Exception:
                pass
            return

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
            
            # Sub Checks...
            need_join_check = ("join" in check_text or "subscribe" in check_text)
            target_channel = str(task.get("channel", "")).strip()
            task_url = str(task.get("url", "")).strip()

            if target_channel.lower() in ("none", "null", ""):
                target_channel = None
            if task_url.lower() in ("none", "null", ""):
                task_url = None

            if need_join_check and (target_channel or task_url):
                if not target_channel and task_url:
                    match = re.search(r"(?:https?://)?t\.me/([A-Za-z0-9_]+)", task_url, re.IGNORECASE)
                    if match and "+" not in task_url and "joinchat" not in task_url:
                        target_channel = "@" + match.group(1)

                if target_channel:
                    try:
                        if target_channel.lstrip('-').isdigit():
                            chat_id_to_check = int(target_channel)
                        else:
                            chat_id_to_check = target_channel if target_channel.startswith('@') else f"@{target_channel}"

                        member = await context.bot.get_chat_member(chat_id=chat_id_to_check, user_id=owner_id)
                        status_value = getattr(member.status, "value", str(member.status)).lower().strip()
                        valid_statuses = {"member", "administrator", "creator", "restricted"}

                        if status_value not in valid_statuses:
                            await query.answer(sc("PLEASE JOIN THE CHANNEL FIRST THEN CLICK CHECK"), show_alert=True)
                            return
                    except Exception as e:
                        await query.answer(sc("COULD NOT VERIFY CHANNEL MEMBERSHIP PLEASE TRY AGAIN"), show_alert=True)
                        return
                elif task_url and ("+" in task_url or "joinchat" in task_url):
                    await query.answer(sc("CANNOT VERIFY PRIVATE LINK WITHOUT CHANNEL ID IN ADDTASK"), show_alert=True)
                    return

            msg_match = re.search(r'(?:send|chat|message|msg)\s+(\d+)', check_text)
            if msg_match:
                req_msgs = int(msg_match.group(1))
                group_messages = user_data.get('group_messages_today', {})
                if chat_type in ['group', 'supergroup']:
                    current_msgs = group_messages.get(chat_id_str, 0)
                    if current_msgs < req_msgs:
                        await query.answer(sc(f"MISSION INCOMPLETE YOU HAVE SENT {current_msgs}/{req_msgs} MESSAGES IN THIS GROUP TODAY"), show_alert=True)
                        return
                else:
                    max_msgs_in_any_group = max(group_messages.values()) if group_messages else 0
                    if max_msgs_in_any_group < req_msgs:
                        await query.answer(sc(f"MISSION INCOMPLETE PLEASE DO THIS TASK IN A GROUP ({max_msgs_in_any_group}/{req_msgs})"), show_alert=True)
                        return

            if "spend" in check_text or "use" in check_text:
                spend_match = re.search(r'(?:spend|use)\s+(\d+)', check_text)
                req_spend = int(spend_match.group(1)) if spend_match else int(task.get('reward', 0))
                if user_data.get('coins_spent_today', 0) < req_spend:
                    await query.answer(sc(f"MISSION INCOMPLETE YOU HAVE SPENT {user_data.get('coins_spent_today', 0)}/{req_spend} COINS TODAY"), show_alert=True)
                    return

            if "explore" in check_text:
                explore_match = re.search(r'explore\s+(\d+)', check_text)
                if explore_match:
                    req_explores = int(explore_match.group(1))
                    current_explores = user_data.get('explore_count_today', 0)
                    if current_explores < req_explores:
                        await query.answer(sc(f"MISSION INCOMPLETE YOU HAVE EXPLORED {current_explores}/{req_explores} TIMES TODAY"), show_alert=True)
                        return

            # 🔥 NEW: Propose Check
            if "propose" in check_text:
                propose_match = re.search(r'propose\s+(\d+)', check_text)
                if propose_match:
                    req_proposes = int(propose_match.group(1))
                    current_proposes = user_data.get('propose_count_today', 0)
                    if current_proposes < req_proposes:
                        await query.answer(sc(f"MISSION INCOMPLETE YOU HAVE PROPOSED {current_proposes}/{req_proposes} TIMES TODAY"), show_alert=True)
                        return

            # 🔥 NEW: Marry Check
            if "marry" in check_text:
                marry_match = re.search(r'marry\s+(\d+)', check_text)
                if marry_match:
                    req_marries = int(marry_match.group(1))
                    current_marries = user_data.get('marry_count_today', 0)
                    if current_marries < req_marries:
                        await query.answer(sc(f"MISSION INCOMPLETE YOU HAVE MARRIED {current_marries}/{req_marries} TIMES TODAY"), show_alert=True)
                        return

            t_type = task.get('type', 'daily').lower()
            field = 'completed_onetime' if t_type == 'onetime' else 'completed_daily'

            res = await user_tasks_collection.update_one(
                {'user_id': owner_id, field: {'$ne': task_id}},
                {'$addToSet': {field: task_id}}
            )

            if res.modified_count == 0:
                await query.answer(sc("YOU HAVE ALREADY COMPLETED THIS TASK"), show_alert=True)
                return

            reward = int(task.get('reward', 0))
            await eco_collection.update_one({'id': owner_id}, {'$inc': {'balance': reward}}, upsert=True)

            await query.answer(f"✅ {sc('TASK COMPLETED')}!\n{sc('YOU RECEIVED')} {reward:,} 💸", show_alert=True)

            new_kb, new_caption, _, _, _ = await build_task_keyboard(
                owner_id, context.bot.username, page=page, chat_id=chat_id_str, chat_type=chat_type
            )
            try:
                await context.bot._post("editMessageText", {
                    "chat_id": query.message.chat_id,
                    "message_id": query.message.message_id,
                    "rich_message": {"html": new_caption},
                    "reply_markup": new_kb.to_dict()
                })
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
# 📌 HANDLERS REGISTER 
# ==========================================
application.add_handler(CommandHandler("start", handle_referral), group=35)
application.add_handler(CommandHandler(["tasks", "task"], tasks_cmd))
application.add_handler(CommandHandler("addtask", addtask))
application.add_handler(CommandHandler("tasklist", tasklist))
application.add_handler(CommandHandler("removetask", removetask))
application.add_handler(CallbackQueryHandler(task_callback, pattern=r"^(dt_|ign_|ci_|vt_|rf_|nx_|bk_)"))
application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, track_user_messages), group=32)

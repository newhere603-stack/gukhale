import time
import re
import html
import asyncio
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from telegram.constants import ParseMode
import logging

# Apne bot ka main application aur db import kar lena
from shivu import application, db
from shivu.Database.db import eco_collection

LOGGER = logging.getLogger(__name__)

# Timezone setup (IST)
IST = timezone(timedelta(hours=5, minutes=30))
OWNER_ID = 7657218453
LOG_GROUP_ID = -1003893927065

# ==========================================
# 📋 TASKS DATABASE COLLECTIONS
# ==========================================
tasks_collection = db['bot_tasks']           
user_tasks_collection = db['user_tasks']     

# ==========================================
# ✍️ FONT FORMATTING (Small Caps)
# ==========================================
def to_small_caps(text: str) -> str:
    if not text:
        return "ᴜɴᴋɴᴏᴡɴ"
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    tr = str.maketrans(normal, small)
    return str(text).translate(tr)

sc = to_small_caps

# ==========================================
# 📡 LOGGING SYSTEM
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
# 🎁 WELCOME & REFERRAL LOGIC
# ==========================================
async def handle_referral(update: Update, context: CallbackContext):
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
                        ref_msg = f"<b>{sc('🎉 SOMEONE JOINED USING YOUR INVITE LINK! CHECK /tasks TO CLAIM YOUR REWARD!')}</b>"
                        await context.bot.send_message(chat_id=referrer_id, text=ref_msg, parse_mode=ParseMode.HTML)
                    except Exception:
                        pass
                        
                    log_data = {
                        sc("ɴᴇᴡ ᴜsᴇʀ"): f"<b><a href='tg://user?id={user_id}'>{safe_name}</a></b>",
                        sc("ɪᴅ"): f"<code>{user_id}</code>",
                        sc("ʀᴇғᴇʀʀᴇᴅ ʙʏ"): f"<code>{referrer_id}</code>",
                        sc("sᴛᴀᴛᴜs"): f"<b>{sc('Pending Claim')}</b>"
                    }
                    asyncio.create_task(send_log(context, create_log_message(f"˹ {sc('ɴᴇᴡ ʀᴇғᴇʀʀᴀʟ')} ˼ 👥", log_data)))
            except ValueError:
                pass
                
        await user_tasks_collection.insert_one({
            'user_id': user_id,
            'completed_daily': [],
            'completed_onetime': [],
            'coins_spent_today': 0,
            'pending_invites': 0,
            'total_invites': 0,
            'last_reset_date': datetime.now(IST).strftime("%Y-%m-%d")
        })
        
        welcome_text = (
            f"<b>{sc('🎉 WELCOME! YOU RECEIVED 1,000 💸 FOR STARTING THE BOT!')}</b>\n"
            f"<b>{sc('USE /tasks TO COMPLETE MISSIONS AND EARN MORE.')}</b>"
        )
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)


# ==========================================
# 🛠️ ADMIN TASKS MANAGEMENT
# ==========================================
async def addtask(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return
        
    try:
        raw_text = update.message.text.split(" ", 1)[1]
        parts = [p.strip() for p in raw_text.split("|")]
        
        t_type = parts[0].lower()
        difficulty = parts[1].lower()
        reward = int(parts[2])
        name = parts[3]
        url = parts[4] if len(parts) > 4 and parts[4].lower() != "none" else None
        
        task_id = f"task_{int(time.time())}"
        
        await tasks_collection.insert_one({
            'task_id': task_id,
            'type': t_type,
            'difficulty': difficulty,
            'reward': reward,
            'name': name,
            'url': url
        })
        
        msg = (
            f"<b>✅ {sc('NEW TASK ADDED SUCCESSFULLY!')}</b>\n"
            f"<blockquote><b>{sc('ID')}:</b> <code>{task_id}</code>\n"
            f"<b>{sc('NAME')}:</b> <b>{sc(name)}</b>\n"
            f"<b>{sc('REWARD')}:</b> <b>{reward:,} 💸</b>\n"
            f"<b>{sc('TYPE')}:</b> <b>{sc(t_type.upper())}</b></blockquote>"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        error_msg = (
            f"<b>⚠️ {sc('INVALID FORMAT!')}</b>\n"
            f"<b>{sc('USAGE')}:</b> <code>/addtask type | difficulty | reward | Name | URL(or None)</code>\n\n"
            f"<b>{sc('EXAMPLE')}:</b>\n<code>/addtask daily | normal | 5000 | Join Our Channel | https://t.me/shivu</code>"
        )
        await update.message.reply_text(error_msg, parse_mode=ParseMode.HTML)


async def tasklist(update: Update, context: CallbackContext):
    """Admin command to list and directly delete tasks using inline buttons."""
    if update.effective_user.id != OWNER_ID:
        return
        
    try:
        # Fetching with explicit limit to avoid motor PyMongo errors
        tasks = await tasks_collection.find({}).to_list(length=1000)
        
        if not tasks:
            await update.message.reply_text(f"<b>{sc('NO TASKS FOUND!')}</b>", parse_mode=ParseMode.HTML)
            return
            
        msg = f"<b>📋 {sc('ALL ACTIVE TASKS')}</b>\n\n"
        keyboard = []
        
        for t in tasks:
            t_name = sc(t.get('name', 'UNKNOWN'))
            t_id = t['task_id']
            msg += f"<b>{sc('NAME')}:</b> {t_name}\n<b>{sc('ID')}:</b> <code>{t_id}</code>\n\n"
            
            # Delete button logic
            keyboard.append([InlineKeyboardButton(f"🗑️ {sc('DELETE')} {t_name}", callback_data=f"deltask_{t_id}")])
            
        msg += f"<b><i>{sc('CLICK THE BUTTON BELOW TO DELETE A TASK.')}</i></b>"
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        
    except Exception as e:
        LOGGER.error(f"Tasklist Error: {e}")
        await update.message.reply_text(f"<b>⚠️ ERROR:</b> {e}", parse_mode=ParseMode.HTML)


async def removetask(update: Update, context: CallbackContext):
    """Manual remove command just in case."""
    if update.effective_user.id != OWNER_ID:
        return
        
    if not context.args:
        await update.message.reply_text(f"<b>{sc('USAGE: /removetask <task_id>')}</b>\n{sc('USE /tasklist TO FIND OR DELETE EASILY.')}", parse_mode=ParseMode.HTML)
        return
        
    task_id = context.args[0]
    result = await tasks_collection.delete_one({'task_id': task_id})
    
    if result.deleted_count > 0:
        await update.message.reply_text(f"<b>✅ {sc('TASK REMOVED SUCCESSFULLY!')}</b>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"<b>❌ {sc('TASK NOT FOUND!')}</b>", parse_mode=ParseMode.HTML)


# ==========================================
# 🔄 DAILY RESET CHECKER
# ==========================================
async def check_daily_reset(user_id):
    user_data = await user_tasks_collection.find_one({'user_id': user_id})
    if not user_data:
        return {'completed_daily': [], 'completed_onetime': [], 'coins_spent_today': 0, 'pending_invites': 0, 'total_invites': 0}
        
    today_str = datetime.now(IST).strftime("%Y-%m-%d")
    
    if user_data.get('last_reset_date') != today_str:
        await user_tasks_collection.update_one(
            {'user_id': user_id},
            {'$set': {
                'completed_daily': [], 
                'coins_spent_today': 0, 
                'last_reset_date': today_str
            }}
        )
        return await user_tasks_collection.find_one({'user_id': user_id})
        
    return user_data


# ==========================================
# 📋 USER TASKS DASHBOARD (/tasks)
# ==========================================
async def tasks_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_data = await check_daily_reset(user_id)
    
    completed_daily = user_data.get('completed_daily', [])
    completed_onetime = user_data.get('completed_onetime', [])
    pending_invites = user_data.get('pending_invites', 0)
    total_invites = user_data.get('total_invites', 0)
    
    # Safely fetch tasks
    all_tasks = await tasks_collection.find({}).to_list(length=1000)
    
    keyboard = []
    
    if all_tasks:
        for task in all_tasks:
            t_id = task['task_id']
            is_completed = (t_id in completed_daily) or (t_id in completed_onetime)
            cb_data = f"verify_task_{t_id}"
            
            name_text = f"{sc(task['name'])}"
            reward_text = f"{task['reward']:,} 💸"
            
            row = []
            
            # COLUMN 1: Name (No emojis to save space)
            if task.get('url') and not is_completed:
                btn_name = InlineKeyboardButton(name_text, url=task['url'])
            else:
                btn_name = InlineKeyboardButton(name_text, callback_data="task_ignore")
                
            # COLUMN 2: Reward
            btn_reward = InlineKeyboardButton(reward_text, callback_data="task_ignore")
            
            # COLUMN 3: Status
            if is_completed:
                btn_status = InlineKeyboardButton(f"✅ {sc('DONE')}", callback_data="task_ignore")
            else:
                btn_status = InlineKeyboardButton(f"{sc('VERIFY')}", callback_data=cb_data)
                
            keyboard.append([btn_name, btn_reward, btn_status])
            
    # 2. INVITE SYSTEM ROW (3 Columns)
    invite_claim_text = f"{sc('CLAIM')}" if pending_invites > 0 else f"{sc('CHECK')}"
    keyboard.append([
        InlineKeyboardButton(f"{sc('INVITES')}", callback_data="task_ignore"),
        InlineKeyboardButton(f"{total_invites} {sc('FRIENDS')}", callback_data="task_ignore"),
        InlineKeyboardButton(invite_claim_text, callback_data="claim_invites")
    ])
    
    bot_username = context.bot.username
    invite_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    keyboard.append([InlineKeyboardButton(f"🔗 {sc('SHARE INVITE LINK')}", url=f"https://t.me/share/url?url={invite_link}&text=Join%20this%20awesome%20bot!")])
    
    text = (
        f"<b>📋 <a href='tg://user?id={user_id}'>{sc('TASK DASHBOARD')}</a></b>\n\n"
        f"<b><i>{sc('COMPLETE TASKS TO EARN HUGE REWARDS! DAILY TASKS RESET EVERY MIDNIGHT.')}</i></b>"
    )
    
    photo_url = "https://files.catbox.moe/lge487.png"
    
    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=photo_url,
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        LOGGER.error(f"Task photo send error: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )


# ==========================================
# 🔘 TASK VERIFICATION & ADMIN CALLBACK
# ==========================================
async def task_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    safe_name = html.escape(query.from_user.first_name or "User")
    data = query.data
    
    if data == "task_ignore":
        await query.answer(sc("NO ACTION NEEDED HERE!"), show_alert=False)
        return
        
    # --- ADMIN DELETE TASK LOGIC ---
    if data.startswith("deltask_"):
        if user_id != OWNER_ID:
            await query.answer(sc("YOU ARE NOT AUTHORIZED!"), show_alert=True)
            return
            
        task_id = data.replace("deltask_", "")
        res = await tasks_collection.delete_one({'task_id': task_id})
        
        if res.deleted_count > 0:
            await query.answer(sc("✅ TASK DELETED SUCCESSFULLY!"), show_alert=True)
            try:
                await query.message.delete()
            except:
                pass
            
            # Send updated list immediately
            tasks = await tasks_collection.find({}).to_list(length=1000)
            if not tasks:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"<b>{sc('NO TASKS FOUND!')}</b>", parse_mode=ParseMode.HTML)
                return
                
            msg = f"<b>📋 {sc('ALL ACTIVE TASKS')}</b>\n\n"
            keyboard = []
            for t in tasks:
                t_name = sc(t.get('name', 'UNKNOWN'))
                msg += f"<b>{sc('NAME')}:</b> {t_name}\n<b>{sc('ID')}:</b> <code>{t['task_id']}</code>\n\n"
                keyboard.append([InlineKeyboardButton(f"🗑️ {sc('DELETE')} {t_name}", callback_data=f"deltask_{t['task_id']}")])
                
            msg += f"<b><i>{sc('CLICK THE BUTTON BELOW TO DELETE A TASK.')}</i></b>"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        else:
            await query.answer(sc("❌ TASK NOT FOUND!"), show_alert=True)
        return

    # --- INVITE CLAIM LOGIC ---
    if data == "claim_invites":
        user_data = await check_daily_reset(user_id)
        pending = user_data.get('pending_invites', 0)
        
        if pending > 0:
            reward = pending * 25000
            await eco_collection.update_one({'id': user_id}, {'$inc': {'balance': reward}})
            await user_tasks_collection.update_one({'user_id': user_id}, {'$set': {'pending_invites': 0}})
            
            popup_msg = f"✅ {sc('CLAIM SUCCESSFUL!')}\n{sc('YOU RECEIVED')} {reward:,} 💸 {sc('FOR')} {pending} {sc('INVITES')}"
            await query.answer(popup_msg, show_alert=True)
            
            try:
                await query.message.delete()
            except:
                pass
            await tasks_cmd(update, context)
        else:
            await query.answer(sc("NO PENDING INVITES TO CLAIM! SHARE YOUR LINK WITH FRIENDS."), show_alert=True)
        return

    # --- NORMAL TASK VERIFICATION ---
    if data.startswith("verify_task_"):
        task_id = data.replace("verify_task_", "")
        
        user_data = await check_daily_reset(user_id)
        if task_id in user_data.get('completed_daily', []) or task_id in user_data.get('completed_onetime', []):
            await query.answer(sc("YOU HAVE ALREADY COMPLETED THIS TASK!"), show_alert=True)
            return
            
        task = await tasks_collection.find_one({'task_id': task_id})
        if not task:
            await query.answer(sc("THIS TASK IS NO LONGER AVAILABLE!"), show_alert=True)
            return
            
        task_name_lower = task['name'].lower()
        
        # 1. CHANNEL VERIFICATION LOGIC (Strict Check)
        if "join" in task_name_lower or "subscribe" in task_name_lower:
            if task.get('url') and "t.me/" in task.get('url') and "+" not in task.get('url') and "joinchat" not in task.get('url'):
                try:
                    channel_username = "@" + task['url'].split("t.me/")[1].split("/")[0].split("?")[0]
                    member = await context.bot.get_chat_member(chat_id=channel_username, user_id=user_id)
                    
                    if member.status not in ['member', 'administrator', 'creator']:
                        await query.answer(sc(f"PLEASE JOIN {channel_username} FIRST, THEN CLICK VERIFY!"), show_alert=True)
                        return
                except Exception as e:
                    LOGGER.error(f"Channel Verify Error: {e}")
                    await query.answer(sc("VERIFICATION FAILED! PLEASE MAKE SURE YOU JOINED THE CHANNEL."), show_alert=True)
                    return

        # 2. SPEND TRACKER LOGIC
        if "spend" in task_name_lower:
            required_spend = 0
            nums = re.findall(r'\d+', task['name'])
            if nums: 
                required_spend = int(nums[0])
            
            current_spent = user_data.get('coins_spent_today', 0)
            if current_spent < required_spend:
                await query.answer(sc(f"YOU HAVEN'T SPENT ENOUGH COINS TODAY! (SPENT: {current_spent:,}/{required_spend:,} 💸)"), show_alert=True)
                return

        # COMPLETE TASK
        push_field = 'completed_daily' if task['type'] == 'daily' else 'completed_onetime'
        await user_tasks_collection.update_one(
            {'user_id': user_id},
            {'$push': {push_field: task_id}}
        )
        
        await eco_collection.update_one(
            {'id': user_id},
            {'$inc': {'balance': task['reward']}},
            upsert=True
        )
        
        popup_msg = f"✅ {sc('TASK COMPLETED!')}\n{sc('YOU RECEIVED')} {task['reward']:,} 💸"
        await query.answer(popup_msg, show_alert=True)
        
        log_data = {
            sc("ᴜsᴇʀ"): f"<b><a href='tg://user?id={user_id}'>{safe_name}</a></b>",
            sc("ɪᴅ"): f"<code>{user_id}</code>",
            sc("ᴛᴀsᴋ ɴᴀᴍᴇ"): f"<b>{sc(task['name'])}</b>",
            sc("ʀᴇᴡᴀʀᴅ"): f"<b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {task['reward']:,}</b>",
            sc("ᴛʏᴘᴇ"): f"<b>{sc(task['type'].upper())}</b>"
        }
        asyncio.create_task(send_log(context, create_log_message(f"˹ {sc('ᴛᴀsᴋ ᴄᴏᴍᴘʟᴇᴛᴇᴅ')} ˼ ✅", log_data)))
        
        try:
            await query.message.delete()
        except:
            pass
        await tasks_cmd(update, context)


# ==========================================
# 🛑 HANDLER REGISTRATIONS
# ==========================================
application.add_handler(CommandHandler("addtask", addtask, block=False))
application.add_handler(CommandHandler("removetask", removetask, block=False))
application.add_handler(CommandHandler("tasklist", tasklist, block=False))
application.add_handler(CommandHandler("tasks", tasks_cmd, block=False))
# Maine deltask_ callback handle ko idhar fix add kiya hai:
application.add_handler(CallbackQueryHandler(task_callback, pattern="^verify_task_|^task_ignore|^claim_invites|^deltask_", block=False))

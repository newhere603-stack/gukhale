import time
import re
import html
import asyncio
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
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
                    await eco_collection.update_one(
                        {'id': referrer_id}, 
                        {'$inc': {'balance': 25000}}
                    )
                    try:
                        ref_msg = f"<b>{sc('🎉 Congratulations! Someone joined using your invite link. You received 25,000 💸!')}</b>"
                        await context.bot.send_message(chat_id=referrer_id, text=ref_msg, parse_mode=ParseMode.HTML)
                    except Exception:
                        pass
                        
                    log_data = {
                        sc("ɴᴇᴡ ᴜsᴇʀ"): f"<b><a href='tg://user?id={user_id}'>{safe_name}</a></b>",
                        sc("ɪᴅ"): f"<code>{user_id}</code>",
                        sc("ʀᴇғᴇʀʀᴇᴅ ʙʏ"): f"<code>{referrer_id}</code>",
                        sc("ʀᴇᴡᴀʀᴅ"): f"<b>25,000 💸</b>"
                    }
                    asyncio.create_task(send_log(context, create_log_message(f"˹ {sc('ɴᴇᴡ ʀᴇғᴇʀʀᴀʟ')} ˼ 👥", log_data)))
            except ValueError:
                pass
                
        await user_tasks_collection.insert_one({
            'user_id': user_id,
            'completed_daily': [],
            'completed_onetime': [],
            'coins_spent_today': 0,
            'last_reset_date': datetime.now(IST).strftime("%Y-%m-%d")
        })
        
        welcome_text = (
            f"<b>{sc('🎉 Welcome! You received 1,000 💸 for starting the bot!')}</b>\n"
            f"<b>{sc('Use /tasks to complete missions and earn more.')}</b>"
        )
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)


# ==========================================
# 🛠️ ADMIN TASK ADDER
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
            f"<b>✅ {sc('New Task Added Successfully!')}</b>\n"
            f"<blockquote><b>{sc('Name')}:</b> <b>{sc(name)}</b>\n"
            f"<b>{sc('Reward')}:</b> <b>{reward:,} 💸</b>\n"
            f"<b>{sc('Type')}:</b> <b>{sc(t_type.capitalize())}</b>\n"
            f"<b>{sc('Difficulty')}:</b> <b>{sc(difficulty.capitalize())}</b></blockquote>"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        
        log_data = {
            sc("ᴀᴅᴍɪɴ"): f"<b><a href='tg://user?id={OWNER_ID}'>{html.escape(update.effective_user.first_name)}</a></b>",
            sc("ᴛᴀsᴋ ɴᴀᴍᴇ"): f"<b>{sc(name)}</b>",
            sc("ʀᴇᴡᴀʀᴅ"): f"<b>{reward:,} 💸</b>",
            sc("ᴛʏᴘᴇ"): f"<b>{sc(t_type)}</b>"
        }
        asyncio.create_task(send_log(context, create_log_message(f"˹ {sc('ɴᴇᴡ ᴛᴀsᴋ ᴀᴅᴅᴇᴅ')} ˼ 📝", log_data)))
        
    except Exception as e:
        error_msg = (
            f"<b>⚠️ {sc('Invalid Format!')}</b>\n"
            f"<b>{sc('Usage')}:</b> <code>/addtask type | difficulty | reward | Name | URL(or None)</code>\n\n"
            f"<b>{sc('Example')}:</b>\n<code>/addtask daily | normal | 5000 | Join Our Channel | https://t.me/shivu</code>\n"
            f"<code>/addtask daily | normal | 10000 | Spend 5000 Coins | None</code>"
        )
        await update.message.reply_text(error_msg, parse_mode=ParseMode.HTML)


# ==========================================
# 🔄 DAILY RESET CHECKER
# ==========================================
async def check_daily_reset(user_id):
    user_data = await user_tasks_collection.find_one({'user_id': user_id})
    if not user_data:
        return {'completed_daily': [], 'completed_onetime': [], 'coins_spent_today': 0}
        
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
    
    all_tasks = await tasks_collection.find({}).to_list(length=None)
    
    if not all_tasks:
        await update.message.reply_text(f"<b>{sc('There are no tasks available right now! Check back later.')}</b>", parse_mode=ParseMode.HTML)
        return
        
    keyboard = []
    
    for task in all_tasks:
        t_id = task['task_id']
        is_completed = (t_id in completed_daily) or (t_id in completed_onetime)
        cb_data = f"verify_task_{t_id}"
        
        # Left side button: Task Name | Reward
        icon = "🔴" if task.get('difficulty') == 'hard' else "📝"
        task_btn_text = f"{icon} {sc(task['name'])} | {task['reward']:,} 💸"
        
        row = []
        if is_completed:
            # Agar task completed hai to Verify ki jagah ✅ Completed aayega
            row.append(InlineKeyboardButton(task_btn_text, callback_data="task_ignore"))
            row.append(InlineKeyboardButton(f"✅ {sc('Completed')}", callback_data="task_ignore"))
        else:
            # Agar pending hai to URL open karne ka option dega if URL exists
            if task.get('url'):
                row.append(InlineKeyboardButton(task_btn_text, url=task['url']))
                row.append(InlineKeyboardButton(f"Verify 🔄", callback_data=cb_data))
            else:
                row.append(InlineKeyboardButton(task_btn_text, callback_data="task_ignore"))
                row.append(InlineKeyboardButton(f"Verify 🔄", callback_data=cb_data))
                
        keyboard.append(row)
            
    bot_username = context.bot.username
    invite_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    # Bottom pe Invite button
    keyboard.append([InlineKeyboardButton(f"👥 {sc('Invite Friends')} (25,000 💸)", url=f"https://t.me/share/url?url={invite_link}&text=Join%20this%20awesome%20bot!")])
    
    text = (
        f"<b>📋 <a href='tg://user?id={user_id}'>{sc('TASK DASHBOARD')}</a></b>\n\n"
        f"<b><i>{sc('Complete tasks to earn huge rewards! Daily tasks reset every midnight.')}</i></b>\n"
        f"<blockquote><b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {sc('COINS SPENT TODAY')}:</b> <b>{user_data.get('coins_spent_today', 0):,}</b></blockquote>"
    )
    
    await update.message.reply_text(
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode=ParseMode.HTML, 
        disable_web_page_preview=True
    )


# ==========================================
# 🔘 TASK VERIFICATION CALLBACK
# ==========================================
async def task_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    safe_name = html.escape(query.from_user.first_name or "User")
    data = query.data
    
    if data == "task_ignore":
        await query.answer(sc("You have already completed this task or no action is needed here!"), show_alert=True)
        return
        
    if data.startswith("verify_task_"):
        task_id = data.replace("verify_task_", "")
        task = await tasks_collection.find_one({'task_id': task_id})
        
        if not task:
            await query.answer(sc("This task is no longer available!"), show_alert=True)
            return
            
        user_data = await check_daily_reset(user_id)
        
        # Spend tracker verification logic
        if "spend" in task['name'].lower():
            required_spend = 0
            nums = re.findall(r'\d+', task['name'])
            if nums: 
                required_spend = int(nums[0])
            
            current_spent = user_data.get('coins_spent_today', 0)
            if current_spent < required_spend:
                await query.answer(sc(f"You haven't spent enough coins today! (Spent: {current_spent:,}/{required_spend:,} 💸)"), show_alert=True)
                return

        # Complete the task
        push_field = 'completed_daily' if task['type'] == 'daily' else 'completed_onetime'
        await user_tasks_collection.update_one(
            {'user_id': user_id},
            {'$push': {push_field: task_id}}
        )
        
        # Give rewards
        await eco_collection.update_one(
            {'id': user_id},
            {'$inc': {'balance': task['reward']}},
            upsert=True
        )
        
        await query.answer(sc(f"✅ Task Completed! You received {task['reward']:,} 💸."), show_alert=True)
        
        # Log the completion
        log_data = {
            sc("ᴜsᴇʀ"): f"<b><a href='tg://user?id={user_id}'>{safe_name}</a></b>",
            sc("ɪᴅ"): f"<code>{user_id}</code>",
            sc("ᴛᴀsᴋ ɴᴀᴍᴇ"): f"<b>{sc(task['name'])}</b>",
            sc("ʀᴇᴡᴀʀᴅ"): f"<b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {task['reward']:,}</b>",
            sc("ᴛʏᴘᴇ"): f"<b>{sc(task['type'].capitalize())}</b>"
        }
        asyncio.create_task(send_log(context, create_log_message(f"˹ {sc('ᴛᴀsᴋ ᴄᴏᴍᴘʟᴇᴛᴇᴅ')} ˼ ✅", log_data)))
        
        # Dashboard message update karo
        await tasks_cmd(update, context) 
        try:
            await query.message.delete()
        except:
            pass


# ==========================================
# 🛑 HANDLER REGISTRATIONS
# ==========================================
application.add_handler(CommandHandler("addtask", addtask, block=False))
application.add_handler(CommandHandler("tasks", tasks_cmd, block=False))
application.add_handler(CallbackQueryHandler(task_callback, pattern="^verify_task_|^task_ignore", block=False))

import logging
import time
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, filters
from telegram.constants import ParseMode
from shivu import (
    sudo_users, 
    OWNER_ID,
    user_collection,
    top_global_groups_collection,
    BANNED_USERS,
    banned_groups_collection,
    pm_users,
    application
)

LOGGER = logging.getLogger(__name__)

# --- SMALL CAPS CONVERTER HELPERS ---
SMALL_CAPS_TRANS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
)

def sc(text: str) -> str:
    """Converts regular text to Small Caps font."""
    if not text:
        return ""
    return str(text).translate(SMALL_CAPS_TRANS)

# --- AUTHENTICATION HELPER ---
def is_authorized(user_id: int) -> bool:
    # Yaha par aapka Owner ID (7657218453) add kar diya gaya hai
    if user_id in [OWNER_ID, 7657218453]:
        return True
    if hasattr(sudo_users, '__contains__') and user_id in sudo_users:
        return True
    return False

# --- COMMANDS ---

async def gstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global statistics command - OPTIMIZED FOR EXTREME SPEED"""
    user_id = update.effective_user.id
    
    # Agar user owner/sudo nahi hai, toh bina kuch reply kiye return (Silent Ignore)
    if not is_authorized(user_id):
        return
    
    # Send a quick processing message for instant feedback
    processing_msg = await update.message.reply_text(f"<b><tg-emoji emoji-id=\"6307488052059053932\">🕐</tg-emoji> {sc('fetching statistics...')}</b>", parse_mode=ParseMode.HTML)
    
    try:
        # ⚡ OPTIMIZATION: Fetch all document counts concurrently (in parallel)
        tasks = [
            user_collection.count_documents({}),
            top_global_groups_collection.count_documents({}),
            BANNED_USERS.count_documents({}),
            banned_groups_collection.count_documents({}),
            pm_users.count_documents({})
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle potential errors from gather safely
        total_users = results[0] if isinstance(results[0], int) else 0
        total_chats = results[1] if isinstance(results[1], int) else 0
        banned_users_count = results[2] if isinstance(results[2], int) else 0
        banned_groups_count = results[3] if isinstance(results[3], int) else 0
        pm_users_count = results[4] if isinstance(results[4], int) else 0
        
        stats_text = (
            f"<b><tg-emoji emoji-id=\"6314169895890199228\">📊</tg-emoji> {sc('global statistics')}</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━</b>\n\n"
            f"<b>👥 {sc('total users')} :</b> <code>{total_users:,}</code>\n"
            f"<b>🌐 {sc('total chats')} :</b> <code>{total_chats:,}</code>\n"
            f"<b>📩 {sc('pm users')} :</b> <code>{pm_users_count:,}</code>\n"
            f"<b>🛑 {sc('banned users')} :</b> <code>{banned_users_count:,}</code>\n"
            f"<b>⛔ {sc('banned groups')} :</b> <code>{banned_groups_count:,}</code>\n\n"
            f"<b>⏱️ {sc('updated')} :</b> <i>{datetime.now().strftime('%d %b %Y, %I:%M %p')}</i>"
        )
        
        await processing_msg.edit_text(stats_text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        LOGGER.error(f"Error in gstats: {e}")
        await processing_msg.edit_text(
            f"<b>❌ {sc('error fetching statistics.')}\n{sc('error')}:</b> <code>{str(e)[:100]}</code>",
            parse_mode=ParseMode.HTML
        )


async def check_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check database connectivity and collections - OPTIMIZED"""
    user_id = update.effective_user.id
    
    # Agar user owner/sudo nahi hai, toh bina kuch reply kiye return (Silent Ignore)
    if not is_authorized(user_id):
        return
    
    processing_msg = await update.message.reply_text(f"<b><tg-emoji emoji-id=\"6307488052059053932\">🕐</tg-emoji> {sc('running diagnostics...')}</b>", parse_mode=ParseMode.HTML)
    
    try:
        collections = [
            ("Users", user_collection),
            ("Groups", top_global_groups_collection),
            ("Ban User", BANNED_USERS),
            ("Ban Chat", banned_groups_collection),
            ("PM Users", pm_users)
        ]
        
        # ⚡ OPTIMIZATION: Check all collections concurrently
        async def fetch_col_data(name, col):
            try:
                count = await col.count_documents({})
                sample = await col.find_one({})
                return name, count, sample, None
            except Exception as e:
                return name, 0, None, str(e)
                
        tasks = [fetch_col_data(name, col) for name, col in collections]
        results = await asyncio.gather(*tasks)

        message_parts = [
            f"<b><tg-emoji emoji-id=\"5422439311196834318\">💡</tg-emoji> {sc('database diagnostics')}</b>",
            f"<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
        ]
        
        user_sample = None
        for name, count, sample, error in results:
            formatted_name = sc(name)
            if error:
                message_parts.append(f"<b>❌ {formatted_name} :</b>\n<b>➥ {sc('error')}:</b> <code>{error[:60]}</code>\n")
            else:
                sample_id = str(sample.get('_id', 'N/A'))[:15] + ".." if sample else "Empty"
                message_parts.append(f"<b>✅ {formatted_name} :</b>\n<b>➥ {sc('count')} :</b> <code>{count:,}</code> | <b>ID:</b> <code>{sample_id}</code>\n")
            
            if name == "Users" and sample:
                user_sample = sample
        
        message_parts.append(f"<b><tg-emoji emoji-id=\"5260426225599405269\">🪄</tg-emoji> {sc('user fields check')} :</b>")
        if user_sample:
            fields = list(user_sample.keys())
            message_parts.append(f"<b>➥ {sc('keys')} :</b> <code>{', '.join(fields[:6])}... (+{max(0, len(fields)-6)})</code>\n")
        else:
            message_parts.append(f"<b>➥ </b> <i>{sc('no users found')}</i>\n")
        
        bot_uname = context.bot.username or "unknown"
        message_parts.append(f"<b>🤖 {sc('bot information')} :</b>")
        message_parts.append(f"<b>➥ {sc('bot')} :</b> @{bot_uname}")
        message_parts.append(f"<b>➥ {sc('req user')} :</b> <code>{user_id}</code>")
        
        full_message = "\n".join(message_parts)
        
        await processing_msg.edit_text(full_message, parse_mode=ParseMode.HTML)
            
    except Exception as e:
        LOGGER.error(f"Error in check_db: {str(e)}", exc_info=True)
        await processing_msg.edit_text(
            f"<b>❌ {sc('critical error in checkdb:')}\n</b><code>{str(e)[:150]}</code>", 
            parse_mode=ParseMode.HTML
        )


async def test_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test command for everyone - Premium Style"""
    try:
        count = await user_collection.count_documents({})
        
        response = (
            f"<b>✅ {sc('database connection active!')}</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>📊 {sc('total users registered')} :</b> <code>{count:,}</code>\n"
            f"<b>👤 {sc('your user id')} :</b> <code>{update.effective_user.id}</code>\n"
            f"<b>⏱️ {sc('ping time')} :</b> <i>{datetime.now().strftime('%H:%M:%S')}</i>"
        )
        
        await update.message.reply_text(response, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        error_msg = (
            f"<b>❌ {sc('database test failed!')}</b>\n"
            f"<b>⚠️ {sc('error')} :</b> <code>{str(e)[:100]}</code>"
        )
        await update.message.reply_text(error_msg, parse_mode=ParseMode.HTML)


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if bot is responsive - Premium Style"""
    start_time = time.time()
    message = await update.message.reply_text(f"<b>🏓 {sc('pong...')}</b>", parse_mode=ParseMode.HTML)
    end_time = time.time()
    
    latency = (end_time - start_time) * 1000 
    
    await message.edit_text(
        f"<b>🏓 {sc('pong !')}</b>\n"
        f"<b>━━━━━━━━━━━━━</b>\n"
        f"<b>⚡ {sc('latency')} :</b> <code>{latency:.0f}ms</code>\n"
        f"<b>⏱️ {sc('time')} :</b> <i>{datetime.now().strftime('%I:%M %p')}</i>",
        parse_mode=ParseMode.HTML
    )

# --- HANDLERS REGISTRATION ---
application.add_handler(CommandHandler("gstats", gstats, filters=filters.ALL))
application.add_handler(CommandHandler("checkdb", check_db, filters=filters.ALL))
application.add_handler(CommandHandler("testdb", test_db, filters=filters.ALL))
application.add_handler(CommandHandler("dbinfo", check_db, filters=filters.ALL))
application.add_handler(CommandHandler("ping", ping, filters=filters.ALL))

import html
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

# Apne correct imports yahan lagayein. Example:
from shivu import application, user_collection 
from shivu.Database.db import eco_collection 

# --- CONFIGURATION ---
OWNER_ID = 7657218453
LOG_GROUP_ID = -1003893927065 

# --- PREMIUM UI STYLE ---
class Style:
    CHAR_HEADER = "⚡ 𝗖𝗛𝗔𝗥𝗔𝗖𝗧𝗘𝗥 𝗧𝗥𝗔𝗡𝗦𝗙𝗘𝗥 ⚡"
    ECO_HEADER  = "⚡ 𝗘𝗖𝗢𝗡𝗢𝗠𝗬 𝗧𝗥𝗔𝗡𝗦𝗙𝗘𝗥 ⚡"
    FROM = "📤 𝗦𝗲𝗻𝗱𝗲𝗿 :"
    TO = "📥 𝗥𝗲𝗰𝗲𝗶𝘃𝗲𝗿 :"
    CHARS = "👥 𝗖𝗵𝗮𝗿𝗮𝗰𝘁𝗲𝗿𝘀 :"
    COINS = "💸 𝗖𝗼𝗶𝗻𝘀 :"
    TOKENS = "💠 𝗧𝗼𝗸𝗲𝗻𝘀 :"
    STATUS = "✨ 𝗦𝘁𝗮𝘁𝘂𝘀 :"
    LINE = "━━━━━━━━━━━━━━━━━━━━━━━━"

# ==========================================
# 1. CHARACTER TRANSFER COMMAND (/tchar)
# ==========================================
async def tchar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner command to transfer only Characters."""
    if update.effective_user.id != OWNER_ID:
        return 

    if len(context.args) != 2:
        return await update.message.reply_text(
            f'<b>❌ ᴜꜱᴀɢᴇ:</b> <code>/tchar [sender_id] [receiver_id]</code>', 
            parse_mode='HTML'
        )

    try:
        s_id, r_id = int(context.args[0]), int(context.args[1])
        if s_id == r_id:
            return await update.message.reply_text("<b>❌ ꜱᴇɴᴅᴇʀ ᴀɴᴅ ʀᴇᴄᴇɪᴠᴇʀ ᴄᴀɴɴᴏᴛ ʙᴇ ᴛʜᴇ ꜱᴀᴍᴇ.</b>", parse_mode='HTML')

        s_chara = await user_collection.find_one({'id': s_id})
        s_waifus = s_chara.get('characters', []) if s_chara else []

        if not s_waifus:
            return await update.message.reply_text('<b>⚠️ ꜱᴇɴᴅᴇʀ ʜᴀꜱ 𝟶 ᴄʜᴀʀᴀᴄᴛᴇʀꜱ.</b>', parse_mode='HTML')

        keyboard = [
            [InlineKeyboardButton("✅ 𝗖𝗢𝗡𝗙𝗜𝗥𝗠 𝗖𝗛𝗔𝗥𝗦", callback_data=f"TC|{s_id}|{r_id}")],
            [InlineKeyboardButton("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", callback_data="TC|CANCEL")]
        ]

        msg = (
            f"<b>{Style.CHAR_HEADER}</b>\n"
            f"{Style.LINE}\n"
            f"<b>{Style.FROM}</b> <code>{s_id}</code>\n"
            f"<b>{Style.TO}</b> <code>{r_id}</code>\n"
            f"{Style.LINE}\n"
            f"{Style.CHARS} <code>{len(s_waifus)}</code> ᴛᴏ ᴍᴏᴠᴇ\n"
            f"{Style.LINE}"
        )
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    except ValueError:
        await update.message.reply_text('<b>❌ ᴇʀʀᴏʀ: ɪᴅꜱ ᴍᴜꜱᴛ ʙᴇ ᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀꜱ.</b>', parse_mode='HTML')

async def tchar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != OWNER_ID:
        return await query.answer("❌ ᴏɴʟʏ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜꜱᴇ ᴛʜɪꜱ.", show_alert=True)

    data = query.data.split('|')
    await query.answer()

    if data[1] == "CANCEL":
        return await query.edit_message_text("<b>❌ ᴄʜᴀʀᴀᴄᴛᴇʀ ᴛʀᴀɴꜱꜰᴇʀ ᴄᴀɴᴄᴇʟʟᴇᴅ.</b>", parse_mode='HTML')

    s_id, r_id = int(data[1]), int(data[2])

    try:
        s_chara = await user_collection.find_one({'id': s_id})
        s_waifus = s_chara.get('characters', []) if s_chara else []

        if not s_waifus:
            return await query.edit_message_text("<b>⚠️ ꜱᴇɴᴅᴇʀ ᴀᴄᴄᴏᴜɴᴛ ɪꜱ ᴇᴍᴘᴛʏ.</b>", parse_mode='HTML')

        # ⚡ Parallel DB updates for ultra-fast performance
        await asyncio.gather(
            user_collection.update_one({'id': r_id}, {'$push': {'characters': {'$each': s_waifus}}}, upsert=True),
            user_collection.update_one({'id': s_id}, {'$set': {'characters': []}})
        )

        await query.edit_message_text(
            f"<b>✅ 𝗖𝗛𝗔𝗥𝗔𝗖𝗧𝗘𝗥𝗦 𝗧𝗥𝗔𝗡𝗦𝗙𝗘𝗥𝗥𝗘𝗗!</b>\n\n"
            f"<b>{Style.TO}</b> <code>{r_id}</code>\n"
            f"<b>{Style.CHARS}</b> <code>{len(s_waifus)}</code>", 
            parse_mode='HTML'
        )

        async def send_char_log():
            user_name = html.escape(update.effective_user.first_name)
            log_text = (
                f"📢 <b>#𝗖𝗛𝗔𝗥_𝗧𝗥𝗔𝗡𝗦𝗙𝗘𝗥</b>\n"
                f"{Style.LINE}\n"
                f"<b>👤 𝗕𝘆 𝗢𝘄𝗻𝗲𝗿 :</b> {user_name} (<code>{OWNER_ID}</code>)\n"
                f"<b>{Style.FROM}</b> <code>{s_id}</code>\n"
                f"<b>{Style.TO}</b> <code>{r_id}</code>\n"
                f"<b>{Style.CHARS}</b> <code>{len(s_waifus)}</code>\n"
                f"<b>{Style.STATUS}</b> 𝗖𝗢𝗠𝗣𝗟𝗘𝗧𝗘𝗗 ✅"
            )
            await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_text, parse_mode='HTML')

        asyncio.create_task(send_char_log())

    except Exception as e:
        await query.edit_message_text(f"<b>❌ ᴅᴀᴛᴀʙᴀꜱᴇ ᴇʀʀᴏʀ:</b> <code>{html.escape(str(e))}</code>", parse_mode='HTML')


# ==========================================
# 2. ECONOMY TRANSFER COMMAND (/tmoney)
# ==========================================
async def tmoney_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner command to transfer only Coins & Tokens."""
    if update.effective_user.id != OWNER_ID:
        return 

    if len(context.args) != 2:
        return await update.message.reply_text(
            f'<b>❌ ᴜꜱᴀɢᴇ:</b> <code>/tmoney [sender_id] [receiver_id]</code>', 
            parse_mode='HTML'
        )

    try:
        s_id, r_id = int(context.args[0]), int(context.args[1])
        if s_id == r_id:
            return await update.message.reply_text("<b>❌ ꜱᴇɴᴅᴇʀ ᴀɴᴅ ʀᴇᴄᴇɪᴠᴇʀ ᴄᴀɴɴᴏᴛ ʙᴇ ᴛʜᴇ ꜱᴀᴍᴇ.</b>", parse_mode='HTML')

        s_eco = await eco_collection.find_one({'id': s_id})
        s_coins = s_eco.get('balance', 0) if s_eco else 0
        s_tokens = s_eco.get('tokens', 0) if s_eco else 0

        if s_coins <= 0 and s_tokens <= 0:
            return await update.message.reply_text('<b>⚠️ ꜱᴇɴᴅᴇʀ ʜᴀꜱ 𝟶 ᴄᴏɪɴꜱ & 𝟶 ᴛᴏᴋᴇɴꜱ.</b>', parse_mode='HTML')

        keyboard = [
            [InlineKeyboardButton("✅ 𝗖𝗢𝗡𝗙𝗜𝗥𝗠 𝗠𝗢𝗡𝗘𝗬", callback_data=f"TM|{s_id}|{r_id}")],
            [InlineKeyboardButton("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", callback_data="TM|CANCEL")]
        ]

        msg = (
            f"<b>{Style.ECO_HEADER}</b>\n"
            f"{Style.LINE}\n"
            f"<b>{Style.FROM}</b> <code>{s_id}</code>\n"
            f"<b>{Style.TO}</b> <code>{r_id}</code>\n"
            f"{Style.LINE}\n"
            f"{Style.COINS} <code>{s_coins}</code>\n"
            f"{Style.TOKENS} <code>{s_tokens}</code>\n"
            f"{Style.LINE}"
        )
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    except ValueError:
        await update.message.reply_text('<b>❌ ᴇʀʀᴏʀ: ɪᴅꜱ ᴍᴜꜱᴛ ʙᴇ ᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀꜱ.</b>', parse_mode='HTML')

async def tmoney_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != OWNER_ID:
        return await query.answer("❌ ᴏɴʟʏ ᴏᴡɴᴇʀ ᴄᴀɴ ᴜꜱᴇ ᴛʜɪꜱ.", show_alert=True)

    data = query.data.split('|')
    await query.answer()

    if data[1] == "CANCEL":
        return await query.edit_message_text("<b>❌ ᴇᴄᴏɴᴏᴍʏ ᴛʀᴀɴꜱꜰᴇʀ ᴄᴀɴᴄᴇʟʟᴇᴅ.</b>", parse_mode='HTML')

    s_id, r_id = int(data[1]), int(data[2])

    try:
        s_eco = await eco_collection.find_one({'id': s_id})
        s_coins = s_eco.get('balance', 0) if s_eco else 0
        s_tokens = s_eco.get('tokens', 0) if s_eco else 0

        if s_coins <= 0 and s_tokens <= 0:
            return await query.edit_message_text("<b>⚠️ ꜱᴇɴᴅᴇʀ ᴀᴄᴄᴏᴜɴᴛ ɪꜱ ᴇᴍᴘᴛʏ.</b>", parse_mode='HTML')

        # ⚡ Parallel DB updates for ultra-fast performance
        await asyncio.gather(
            eco_collection.update_one({'id': r_id}, {'$inc': {'balance': s_coins, 'tokens': s_tokens}}, upsert=True),
            eco_collection.update_one({'id': s_id}, {'$set': {'balance': 0, 'tokens': 0}})
        )

        await query.edit_message_text(
            f"<b>✅ 𝗘𝗖𝗢𝗡𝗢𝗠𝗬 𝗧𝗥𝗔𝗡𝗦𝗙𝗘𝗥𝗥𝗘𝗗!</b>\n\n"
            f"<b>{Style.TO}</b> <code>{r_id}</code>\n"
            f"<b>{Style.COINS}</b> <code>{s_coins}</code>\n"
            f"<b>{Style.TOKENS}</b> <code>{s_tokens}</code>", 
            parse_mode='HTML'
        )

        async def send_eco_log():
            user_name = html.escape(update.effective_user.first_name)
            log_text = (
                f"📢 <b>#𝗘𝗖𝗢_𝗧𝗥𝗔𝗡𝗦𝗙𝗘𝗥</b>\n"
                f"{Style.LINE}\n"
                f"<b>👤 𝗕𝘆 𝗢𝘄𝗻𝗲𝗿 :</b> {user_name} (<code>{OWNER_ID}</code>)\n"
                f"<b>{Style.FROM}</b> <code>{s_id}</code>\n"
                f"<b>{Style.TO}</b> <code>{r_id}</code>\n"
                f"<b>{Style.COINS}</b> <code>{s_coins}</code>\n"
                f"<b>{Style.TOKENS}</b> <code>{s_tokens}</code>\n"
                f"<b>{Style.STATUS}</b> 𝗖𝗢𝗠𝗣𝗟𝗘𝗧𝗘𝗗 ✅"
            )
            await context.bot.send_message(chat_id=LOG_GROUP_ID, text=log_text, parse_mode='HTML')

        asyncio.create_task(send_eco_log())

    except Exception as e:
        await query.edit_message_text(f"<b>❌ ᴅᴀᴛᴀʙᴀꜱᴇ ᴇʀʀᴏʀ:</b> <code>{html.escape(str(e))}</code>", parse_mode='HTML')

# ==========================================
# Handlers Registration
# ==========================================
application.add_handler(CommandHandler("tchar", tchar_cmd, block=False))
application.add_handler(CallbackQueryHandler(tchar_callback, pattern="^TC\|", block=False))

application.add_handler(CommandHandler("tmoney", tmoney_cmd, block=False))
application.add_handler(CallbackQueryHandler(tmoney_callback, pattern="^TM\|", block=False))

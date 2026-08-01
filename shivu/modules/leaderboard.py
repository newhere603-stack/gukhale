import os
from datetime import datetime
from html import escape
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import mention_html
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler

from shivu import application, OWNER_ID, user_collection, top_global_groups_collection, group_user_totals_collection
from shivu import sudo_users as SUDO_USERS


def sc(t):
    return t.translate(str.maketrans(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ))


def is_sudo(user_id):
    return user_id == OWNER_ID or str(user_id) in SUDO_USERS or user_id in SUDO_USERS


# ---------- Smart Database & Field Handlers ----------

async def get_user_document(user_id):
    """Fetches user document matching both integer and string formats"""
    try:
        uid_int = int(user_id)
    except (ValueError, TypeError):
        uid_int = user_id
    uid_str = str(user_id)

    user = await user_collection.find_one({
        '$or': [
            {'id': uid_int},
            {'id': uid_str},
            {'user_id': uid_int},
            {'user_id': uid_str},
            {'_id': uid_int},
            {'_id': uid_str}
        ]
    })
    return user


def extract_balance(user_doc):
    """Safely extracts balance/coins from any user document schema"""
    if not user_doc or not isinstance(user_doc, dict):
        return 0
    
    # Common keys used across shivu / anime character collector bots
    for key in ['balance', 'coins', 'wallet', 'money', 'gold', 'bal']:
        val = user_doc.get(key)
        if val is not None:
            if isinstance(val, (int, float)):
                return int(val)
            elif isinstance(val, str) and val.isdigit():
                return int(val)
            elif isinstance(val, dict):
                for sub_key in ['amount', 'coins', 'balance', 'val']:
                    sub_val = val.get(sub_key)
                    if sub_val is not None and str(sub_val).isdigit():
                        return int(sub_val)
    return 0


def extract_tokens(user_doc):
    """Safely extracts tokens"""
    if not user_doc or not isinstance(user_doc, dict):
        return 0
    for key in ['tokens', 'token', 'gems']:
        val = user_doc.get(key)
        if val is not None:
            if isinstance(val, (int, float)):
                return int(val)
            elif isinstance(val, str) and val.isdigit():
                return int(val)
    return 0


def get_rank_badge(rank: int) -> str:
    if rank == 1:
        return "🥇 ᴄʀᴏᴡɴ ʟᴇɢᴇɴᴅ"
    elif rank == 2:
        return "🥈 ᴍᴀsᴛᴇʀ"
    elif rank == 3:
        return "🥉 ᴇʟɪᴛᴇ"
    elif rank <= 10:
        return "🎖️ ᴛᴏᴘ 10"
    elif rank <= 50:
        return "⭐ ᴛᴏᴘ 50"
    return "🏅 ᴄᴏʟʟᴇᴄᴛᴏʀ"


def generate_progress_bar(current: int, total: int, length: int = 8) -> str:
    if total <= 0:
        return "░" * length
    percentage = min(1.0, current / total)
    filled = int(round(length * percentage))
    return "█" * filled + "░" * (length - filled)


def format_list(title, rows):
    header = f"🏆 <b>{sc('top')} {len(rows)} {sc(title)}</b> 🏆\n\n"
    return header + "\n".join(rows)


async def send_or_edit(update, context, text, kb, edit):
    if edit:
        q = update.callback_query
        await q.answer()
        await q.message.edit_text(text, parse_mode='HTML', reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=kb)


def back_close_buttons(refresh_cb, extra_row=None):
    rows = [[InlineKeyboardButton("⟳", callback_data=refresh_cb), InlineKeyboardButton("≼", callback_data="lb_menu")]]
    if extra_row:
        rows.append(extra_row)
    rows.append([InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="lb_close")])
    return InlineKeyboardMarkup(rows)


# ---------- /tops menu ----------

async def tops_menu(update: Update, context: CallbackContext, edit=False):
    text = f"🏆 <b>{sc('select the top list')}</b> 🏆"
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 ᴘʀᴏꜰɪʟᴇ", callback_data="lb_profile"),
            InlineKeyboardButton("💠 ᴛᴏᴋᴇɴꜱ", callback_data="lb_tokens")
        ],
        [
            InlineKeyboardButton("💸 ʙᴀʟᴀɴᴄᴇ", callback_data="lb_bal")
        ],
        [
            InlineKeyboardButton("🎴 ᴄᴛᴏᴘ", callback_data="lb_chars"),
            InlineKeyboardButton("🌱 ɢᴛᴏᴘ", callback_data="lb_gtop")
        ],
    ])
    await send_or_edit(update, context, text, kb, edit)


# ---------- Top by balance ----------

async def top_balance(update: Update, context: CallbackContext, edit=False):
    # Fetch top 50 to sort accurately in python if DB field name varies
    data = await user_collection.find({}).limit(50).to_list(50)

    if not data:
        return await send_or_edit(update, context, f"<b>{sc('no data.')}</b>", None, edit)

    # Sort users by extracted balance
    sorted_data = sorted(data, key=lambda x: extract_balance(x), reverse=True)[:10]

    rows = []
    for i, u in enumerate(sorted_data, 1):
        uid = u.get('id') or u.get('user_id') or u.get('_id', 0)
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            pass
        name = u.get('first_name', 'Unknown')
        link = mention_html(uid, name)
        bal = extract_balance(u)
        rows.append(f"<b>{i}. {link} - 💸 {bal:,}</b>")
    
    text = format_list("users by coins", rows)
    await send_or_edit(update, context, text, back_close_buttons("lb_bal"), edit)


async def top_tokens(update: Update, context: CallbackContext, edit=False):
    data = await user_collection.find({}).limit(50).to_list(50)

    if not data:
        return await send_or_edit(update, context, f"<b>{sc('no data.')}</b>", None, edit)

    sorted_data = sorted(data, key=lambda x: extract_tokens(x), reverse=True)[:10]

    rows = []
    for i, u in enumerate(sorted_data, 1):
        uid = u.get('id') or u.get('user_id') or u.get('_id', 0)
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            pass
        name = u.get("first_name", "Unknown")
        link = mention_html(uid, name)
        tokens = extract_tokens(u)
        rows.append(f"<b>{i}. {link} - 💠 {tokens:,}</b>")

    text = format_list("users by tokens", rows)
    await send_or_edit(update, context, text, back_close_buttons("lb_tokens"), edit)


# ---------- Top by characters ----------

async def top_characters(update: Update, context: CallbackContext, edit=False):
    data = await user_collection.aggregate([
        {"$match": {"characters": {"$exists": True, "$type": "array"}}},
        {"$project": {"user_id": {"$ifNull": ["$id", "$user_id"]}, "first_name": 1, "count": {"$size": "$characters"}}},
        {"$sort": {"count": -1}}, {"$limit": 10}
    ]).to_list(10)

    if not data:
        return await send_or_edit(update, context, f"<b>{sc('no data.')}</b>", None, edit)

    rows = []
    for i, u in enumerate(data, 1):
        uid = u.get('user_id', 0)
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            pass
        name = u.get('first_name', 'Unknown')
        link = mention_html(uid, name)
        rows.append(f"<b>{i}. {link} - {u['count']:,}</b>")

    text = format_list("users by grabbers", rows)
    await send_or_edit(update, context, text, back_close_buttons("lb_chars"), edit)


# ---------- Top groups ----------

async def top_groups(update: Update, context: CallbackContext, edit=False):
    data = await top_global_groups_collection.find({}).sort('count', -1).limit(10).to_list(10)

    if not data:
        return await send_or_edit(update, context, f"<b>{sc('no data.')}</b>", None, edit)

    rows = [f"<b>{i}. {escape(g.get('group_name', 'Unknown'))} - {g.get('count', 0):,}👥</b>"
            for i, g in enumerate(data, 1)]
    text = format_list("groups", rows)
    await send_or_edit(update, context, text, back_close_buttons("lb_gtop"), edit)


# ---------- My Profile (Fixed & Upgraded) ----------

async def my_profile(update: Update, context: CallbackContext, edit=False):
    user_id = update.effective_user.id
    user = await get_user_document(user_id)

    if not user:
        text = (
            f"🏆 <b>{sc('profile not found')}</b> 🏆\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>❌ {sc('start me first!')}</b>\n"
            f"<b>🌱 {sc('start guessing characters in groups to build your profile.')}</b>"
        )
        return await send_or_edit(update, context, text, back_close_buttons("lb_profile"), edit)

    # Characters & Stats
    characters = user.get('characters', [])
    char_count = len(characters)
    balance = extract_balance(user)
    tokens = extract_tokens(user)

    # Calculate collection progress
    total_collectors = await user_collection.count_documents({
        "characters": {"$exists": True, "$type": "array"}
    })
    
    total_available_chars = max(100, char_count, 1)
    completion_pct = round((char_count / total_available_chars) * 100, 1)
    progress_bar = generate_progress_bar(char_count, total_available_chars)

    # Calculate rank
    better_than = await user_collection.count_documents({
        "characters": {"$exists": True, "$type": "array"},
        "$expr": {"$gt": [{"$size": "$characters"}, char_count]}
    })
    rank = better_than + 1
    badge = get_rank_badge(rank)

    link = update.effective_user.mention_html()

    text = (
        f"✨ <b>{sc('user profile')}</b> ✨\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{sc('grabber')} :</b> {link}\n"
        f"🔖 <b>{sc('id')} :</b> <code>{user_id}</code>\n"
        f"🏷️ <b>{sc('badge')} :</b> <b>{badge}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>{sc('collection stats')}</b>\n"
        f"├ <b>{sc('rank')} :</b> <b>#{rank:,}</b> / <b>{total_collectors:,}</b>\n"
        f"├ <b>{sc('cards')} :</b> <b>{char_count:,}</b> 🎴\n"
        f"└ <b>{sc('progress')} :</b> [<code>{progress_bar}</code>] <b>{completion_pct}%</b>\n\n"
        f"🏛️ <b>{sc('vault & wallet')}</b>\n"
        f"├ <b>{sc('balance')} :</b> <b>💸 {balance:,}</b>\n"
        f"└ <b>{sc('tokens')} :</b> <b>💠 {tokens:,}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i><b>❤️‍🔥 {sc('keep grabbing to reach top 10!')}</b></i>"
    )

    profile_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎴 ᴄᴛᴏᴘ", callback_data="lb_chars"),
            InlineKeyboardButton("💸 ʙᴛᴏᴘ", callback_data="lb_bal")
        ],
        [
            InlineKeyboardButton("⟳", callback_data="lb_profile"),
            InlineKeyboardButton("≼", callback_data="lb_menu")
        ],
        [
            InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="lb_close")
        ]
    ])

    await send_or_edit(update, context, text, profile_kb, edit)


# ---------- Owner/sudo stats ----------

async def stats(update: Update, context: CallbackContext, edit=False):
    user_id = update.effective_user.id
    if not is_sudo(user_id):
        msg = f"<b>{sc('unauthorized.')}</b>"
        if edit:
            return await update.callback_query.answer(sc("unauthorized."), show_alert=True)
        return await update.message.reply_text(msg, parse_mode='HTML')

    users = await user_collection.count_documents({})
    groups = len(await group_user_totals_collection.distinct('group_id'))
    collectors = await user_collection.count_documents({"characters": {"$exists": True, "$type": "array"}})

    total_chars_result = await user_collection.aggregate([
        {"$match": {"characters": {"$exists": True, "$type": "array"}}},
        {"$project": {"count": {"$size": "$characters"}}},
        {"$group": {"_id": None, "total": {"$sum": "$count"}}}
    ]).to_list(1)
    total_chars = total_chars_result[0]['total'] if total_chars_result else 0

    text = (
        f"📊 <b>{sc('system stats')}</b> 📊\n\n"
        f"<b>{sc('users')}</b>: <b>{users:,}</b>\n"
        f"<b>{sc('grabbers')}</b>: <b>{collectors:,}</b>\n"
        f"<b>{sc('groups')}</b>: <b>{groups:,}</b>\n"
        f"<b>{sc('total characters')}</b>: <b>{total_chars:,}</b>\n\n"
        f"<i><b>{datetime.now().strftime('%H:%M:%S')}</b></i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⟳", callback_data="lb_stats")],
        [InlineKeyboardButton("×", callback_data="lb_close")]
    ])
    await send_or_edit(update, context, text, kb, edit)


# ---------- Export commands (sudo only) ----------

async def export_users(update: Update, context: CallbackContext):
    if not is_sudo(update.effective_user.id):
        return await update.message.reply_text(f"<b>{sc('unauthorized.')}</b>", parse_mode='HTML')

    users = await user_collection.find({}).to_list(None)
    lines = [f"[{u.get('id') or u.get('user_id')}] {u.get('first_name')} | @{u.get('username')} | {len(u.get('characters', []))} chars"
              for u in users]
    content = f"USER EXPORT — {datetime.now()}\nTotal: {len(users):,}\n{'='*50}\n\n" + "\n".join(lines)

    with open('users.txt', 'w', encoding='utf-8') as f:
        f.write(content)
    with open('users.txt', 'rb') as f:
        await context.bot.send_document(update.effective_chat.id, f, caption=f"<b>{sc('users')}</b>: <b>{len(users):,}</b>", parse_mode='HTML')
    os.remove('users.txt')


async def export_groups(update: Update, context: CallbackContext):
    if not is_sudo(update.effective_user.id):
        return await update.message.reply_text(f"<b>{sc('unauthorized.')}</b>", parse_mode='HTML')

    groups = await top_global_groups_collection.find({}).sort('count', -1).to_list(None)
    lines = [f"[{i}] {g.get('group_name')} | {g.get('count', 0):,}" for i, g in enumerate(groups, 1)]
    content = f"GROUP EXPORT — {datetime.now()}\nTotal: {len(groups):,}\n{'='*50}\n\n" + "\n".join(lines)

    with open('groups.txt', 'w', encoding='utf-8') as f:
        f.write(content)
    with open('groups.txt', 'rb') as f:
        await context.bot.send_document(update.effective_chat.id, f, caption=f"<b>{sc('groups')}</b>: <b>{len(groups):,}</b>", parse_mode='HTML')
    os.remove('groups.txt')


# ---------- Callback router ----------

CALLBACKS = {
    "lb_menu": tops_menu,
    "lb_profile": my_profile,
    "lb_tokens": top_tokens,
    "lb_bal": top_balance,
    "lb_chars": top_characters,
    "lb_gtop": top_groups,
    "lb_stats": stats,
}


async def cb(update: Update, context: CallbackContext):
    data = update.callback_query.data
    if data == "lb_close":
        return await update.callback_query.message.delete()
    handler = CALLBACKS.get(data)
    if handler:
        await handler(update, context, edit=True)


# ---------- Handlers ----------

application.add_handler(CommandHandler(['tops', 'top'], tops_menu, block=False))
application.add_handler(CommandHandler('balancetop', top_balance, block=False))
application.add_handler(CommandHandler('chartop', top_characters, block=False))
application.add_handler(CommandHandler(['gtop', 'topgroups'], top_groups, block=False))
application.add_handler(CommandHandler(['sprofile', 'rank'], my_profile, block=False))
application.add_handler(CommandHandler('stats', stats, block=False))
application.add_handler(CommandHandler('list', export_users, block=False))
application.add_handler(CommandHandler('groups', export_groups, block=False))
application.add_handler(CallbackQueryHandler(cb, pattern="^lb_"))

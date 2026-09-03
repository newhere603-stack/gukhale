import os
import time
from datetime import datetime
from html import escape
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.helpers import mention_html
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler
from telegram.error import BadRequest

from shivu import application, OWNER_ID, user_collection, top_global_groups_collection, group_user_totals_collection
from shivu import sudo_users as SUDO_USERS

# 🔥 NAYA IMPORT: Economy data nikalne ke liye
from shivu.Database.db import eco_collection

def sc(t):
    return t.translate(str.maketrans(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ))

def is_sudo(user_id):
    return user_id == OWNER_ID or str(user_id) in SUDO_USERS or user_id in SUDO_USERS

# ---------- Superfast Cache System (Optimized for Live Economy) ----------
LB_CACHE = {}
CACHE_TTL = 5  # 🔥 FIX: 5 min se ghata kar 5 seconds kar diya taaki NO DATA stuck na ho

async def get_cached_data(key, fetch_function):
    now = time.time()
    if key in LB_CACHE and now - LB_CACHE[key]['time'] < CACHE_TTL:
        return LB_CACHE[key]['data']
    
    data = await fetch_function()
    LB_CACHE[key] = {'time': now, 'data': data}
    return data

# ---------- Smart Database & Field Handlers ----------
async def get_user_document(user_id):
    """Fetches user document matching both integer and string formats (Character DB)"""
    try:
        uid_int = int(user_id)
    except (ValueError, TypeError):
        uid_int = user_id
    uid_str = str(user_id)

    user = await user_collection.find_one({
        '$or': [
            {'id': uid_int}, {'id': uid_str},
            {'user_id': uid_int}, {'user_id': uid_str},
            {'_id': uid_int}, {'_id': uid_str}
        ]
    })
    return user

def extract_balance(user_doc):
    """Safely extracts balance/coins from any user document schema"""
    if not user_doc or not isinstance(user_doc, dict):
        return 0
    for key in ['balance', 'coins', 'wallet', 'money', 'gold', 'bal']:
        val = user_doc.get(key)
        if val is not None:
            try: return int(float(val))
            except: pass
    return 0

def extract_tokens(user_doc):
    """Safely extracts tokens"""
    if not user_doc or not isinstance(user_doc, dict):
        return 0
    for key in ['tokens', 'token', 'gems']:
        val = user_doc.get(key)
        if val is not None:
            try: return int(float(val))
            except: pass
    return 0

def get_rank_badge(rank: int) -> str:
    if rank == 1: return "<tg-emoji emoji-id=\"5440539497383087970\">🥇</tg-emoji> ᴄʀᴏᴡɴ ʟᴇɢᴇɴᴅ"
    elif rank == 2: return "<tg-emoji emoji-id=\"5447203607294265305\">🥈</tg-emoji> ᴍᴀsᴛᴇʀ"
    elif rank == 3: return "<tg-emoji emoji-id=\"5453902265922376865\">🥉</tg-emoji> ᴇʟɪᴛᴇ"
    elif rank <= 10: return "🎖️ ᴛᴏᴘ 10"
    elif rank <= 50: return "⭐ ᴛᴏᴘ 50"
    return "🏅 ᴄᴏʟʟᴇᴄᴛᴏʀ"

def generate_progress_bar(current: int, total: int, length: int = 5) -> str:
    if total <= 0: return "░" * length
    percentage = min(1.0, current / total)
    filled = int(round(length * percentage))
    return "▰" * filled + "▱" * (length - filled)

def format_custom_header(heading: str, rows):
    header = f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>{heading}</b> <tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji>\n\n"
    return header + "\n".join(rows)

async def send_or_edit(update, context, text, kb, edit):
    photo_url = "https://files.catbox.moe/ewtw4l.png"
    if edit:
        q = update.callback_query
        await q.answer()
        try:
            await q.edit_message_media(
                media=InputMediaPhoto(media=photo_url, caption=text, parse_mode='HTML'),
                reply_markup=kb
            )
        except BadRequest as e:
            if "not modified" in str(e).lower(): return
            try: await q.message.delete()
            except: pass
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_url, caption=text, parse_mode='HTML', reply_markup=kb)
        except Exception:
            try: await q.message.delete()
            except: pass
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_url, caption=text, parse_mode='HTML', reply_markup=kb)
    else:
        await update.message.reply_photo(photo=photo_url, caption=text, parse_mode='HTML', reply_markup=kb)

def back_close_buttons(refresh_cb, extra_row=None):
    refresh_data = refresh_cb.replace("lb_", "lb_refresh_")
    rows = [[InlineKeyboardButton("⟳", callback_data=refresh_data), InlineKeyboardButton("≼", callback_data="lb_menu")]]
    if extra_row: rows.append(extra_row)
    rows.append([InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="lb_close")])
    return InlineKeyboardMarkup(rows)

# ---------- /tops menu ----------
async def tops_menu(update: Update, context: CallbackContext, edit=False):
    text = f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>𝗦𝗘𝗟𝗘𝗖𝗧 𝗧𝗛𝗘 𝗧𝗢𝗣 𝗟𝗜𝗦𝗧</b> <tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji>"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("ᴘʀᴏꜰɪʟᴇ", callback_data="lb_profile", icon_custom_emoji_id="5217822164362739968"), InlineKeyboardButton("ᴛᴏᴋᴇɴꜱ", callback_data="lb_tokens", icon_custom_emoji_id="6109593993627050230")],
        [InlineKeyboardButton("ʙᴀʟᴀɴᴄᴇ", callback_data="lb_bal", icon_custom_emoji_id="5472030678633684592")],
        [InlineKeyboardButton("ᴄᴛᴏᴘ", callback_data="lb_chars", icon_custom_emoji_id="6093434630147415641"), InlineKeyboardButton("ɢᴛᴏᴘ", callback_data="lb_gtop", icon_custom_emoji_id="5449850741667668411")],
    ])
    await send_or_edit(update, context, text, kb, edit)

# ---------- Top by balance (🔥 FIX: Direct Mongo Filter) ----------
async def fetch_top_balance():
    data = await eco_collection.find({
        "$or": [{"balance": {"$gt": 0}}, {"coins": {"$gt": 0}}]
    }).to_list(length=10000)
    filtered = [u for u in data if extract_balance(u) > 0]
    return sorted(filtered, key=lambda x: extract_balance(x), reverse=True)[:10]

async def top_balance(update: Update, context: CallbackContext, edit=False):
    sorted_data = await get_cached_data("top_balance", fetch_top_balance)
    if not sorted_data:
        return await send_or_edit(update, context, f"<b>{sc('no data.')}</b>", back_close_buttons("lb_bal"), edit)

    rows = []
    for i, u in enumerate(sorted_data, 1):
        uid = u.get('id') or u.get('user_id') or u.get('_id', 0)
        try: uid = int(uid)
        except: pass
        name = u.get('first_name', 'Unknown')
        link = mention_html(uid, name)
        bal = extract_balance(u)
        rows.append(f"<b>{i}. {link} - <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {bal:,}</b>")
    
    text = format_custom_header("𝗧𝗢𝗣 𝟭𝟬 𝗖𝗢𝗜𝗡 𝗛𝗢𝗟𝗗𝗘𝗥𝗦", rows)
    await send_or_edit(update, context, text, back_close_buttons("lb_bal"), edit)

# ---------- Top by tokens ----------
async def fetch_top_tokens():
    data = await eco_collection.find({
        "$or": [{"tokens": {"$gt": 0}}, {"token": {"$gt": 0}}, {"gems": {"$gt": 0}}]
    }).to_list(length=10000)
    filtered = [u for u in data if extract_tokens(u) > 0]
    return sorted(filtered, key=lambda x: extract_tokens(x), reverse=True)[:10]

async def top_tokens(update: Update, context: CallbackContext, edit=False):
    sorted_data = await get_cached_data("top_tokens", fetch_top_tokens)
    if not sorted_data:
        return await send_or_edit(update, context, f"<b>{sc('no data.')}</b>", back_close_buttons("lb_tokens"), edit)

    rows = []
    for i, u in enumerate(sorted_data, 1):
        uid = u.get('id') or u.get('user_id') or u.get('_id', 0)
        try: uid = int(uid)
        except: pass
        name = u.get("first_name", "Unknown")
        link = mention_html(uid, name)
        tokens = extract_tokens(u)
        rows.append(f"<b>{i}. {link} - <tg-emoji emoji-id=\"6109593993627050230\">💠</tg-emoji> {tokens:,}</b>")

    text = format_custom_header("𝗧𝗢𝗣 𝟭𝟬 𝗧𝗢𝗞𝗘𝗡 𝗛𝗢𝗟𝗗𝗘𝗥", rows)
    await send_or_edit(update, context, text, back_close_buttons("lb_tokens"), edit)

# ---------- Top by characters (🔥 FIX: Ultra Robust MongoDB Aggregation) ----------
async def fetch_top_characters():
    return await user_collection.aggregate([
        {"$match": {"characters": {"$exists": True, "$type": "array", "$not": {"$size": 0}}}},
        {"$project": {"user_id": {"$ifNull": ["$id", "$user_id"]}, "first_name": 1, "count": {"$size": "$characters"}}},
        {"$sort": {"count": -1}}, 
        {"$limit": 10}
    ]).to_list(10)

async def top_characters(update: Update, context: CallbackContext, edit=False):
    data = await get_cached_data("top_chars", fetch_top_characters)
    if not data:
        return await send_or_edit(update, context, f"<b>{sc('no data.')}</b>", back_close_buttons("lb_chars"), edit)

    rows = []
    for i, u in enumerate(data, 1):
        uid = u.get('user_id', 0)
        try: uid = int(uid)
        except: pass
        name = u.get('first_name', 'Unknown')
        link = mention_html(uid, name)
        rows.append(f"<b>{i}. {link} - {u.get('count', 0):,}</b> <tg-emoji emoji-id=\"6093434630147415641\">🃏</tg-emoji>")

    text = format_custom_header("𝗧𝗢𝗣 𝟭𝟬 𝗚𝗥𝗔𝗕𝗕𝗘𝗥𝗦", rows)
    await send_or_edit(update, context, text, back_close_buttons("lb_chars"), edit)

# ---------- Top groups ----------
async def fetch_top_groups():
    return await top_global_groups_collection.find({}).sort('count', -1).limit(10).to_list(10)

async def top_groups(update: Update, context: CallbackContext, edit=False):
    data = await get_cached_data("top_groups", fetch_top_groups)
    if not data:
        return await send_or_edit(update, context, f"<b>{sc('no data.')}</b>", back_close_buttons("lb_gtop"), edit)

    rows = [f"<b>{i}. {escape(g.get('group_name', 'Unknown'))} - {g.get('count', 0):,} <tg-emoji emoji-id=\"5453957997418004470\">👥</tg-emoji></b>" for i, g in enumerate(data, 1)]
    text = format_custom_header("𝗧𝗢𝗣 𝟭𝟬 𝗚𝗥𝗢𝗨𝗣𝗦", rows)
    await send_or_edit(update, context, text, back_close_buttons("lb_gtop"), edit)

# ---------- My Profile (🔥 FIX: Dual DB Merge & Ranking fix) ----------
async def fetch_total_collectors():
    return await user_collection.count_documents({"characters": {"$exists": True, "$type": "array", "$not": {"$size": 0}}})

async def my_profile(update: Update, context: CallbackContext, edit=False):
    user_id = update.effective_user.id
    
    user = await get_user_document(user_id)
    eco_user = await eco_collection.find_one({'id': user_id})

    if not user and not eco_user:
        text = (
            f"<tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji> <b>{sc('profile not found')}</b> <tg-emoji emoji-id=\"6053140037250323814\">🏆</tg-emoji>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b><tg-emoji emoji-id=\"5210952531676504517\">❌</tg-emoji> {sc('start me first!')}</b>\n"
            f"<b><tg-emoji emoji-id=\"5449885771420934013\">🌱</tg-emoji> {sc('start guessing characters in groups to build your profile.')}</b>"
        )
        return await send_or_edit(update, context, text, back_close_buttons("lb_profile"), edit)

    characters = user.get('characters', []) if user else []
    char_count = len(characters)
    
    balance = extract_balance(eco_user) if eco_user else 0
    tokens = extract_tokens(eco_user) if eco_user else 0

    total_collectors = await get_cached_data("total_collectors", fetch_total_collectors)
    
    total_available_chars = max(100, char_count, 1)
    completion_pct = round((char_count / total_available_chars) * 100, 1)
    progress_bar = generate_progress_bar(char_count, total_available_chars)

    better_than = await user_collection.count_documents({
        f"characters.{char_count}": {"$exists": True} 
    })
    
    rank = better_than + 1 if char_count > 0 else total_collectors
    if rank == 0: rank = 1
    badge = get_rank_badge(rank)

    link = update.effective_user.mention_html()

    text = (
        f"<tg-emoji emoji-id=\"6093601953483334318\">✨</tg-emoji> 𝗦𝗣𝗔𝗖𝗜𝗔𝗟 𝗣𝗥𝗢𝗙𝗜𝗟𝗘 <tg-emoji emoji-id=\"6093601953483334318\">✨</tg-emoji>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"5217822164362739968\">👑</tg-emoji> <b>{sc('name')} :</b> {link}\n"
        f"<tg-emoji emoji-id=\"6093857216274635770\">🔖</tg-emoji> <b>{sc('id')} :</b> <code>{user_id}</code>\n"
        f"<tg-emoji emoji-id=\"6336870266928371445\">💘</tg-emoji> <b>{sc('badge')} :</b> <b>{badge}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<tg-emoji emoji-id=\"6093755816391745206\">📊</tg-emoji> <b>{sc('collection stats')}</b>\n"
        f"├ <b>{sc('rank')} :</b> <b>#{rank:,}</b> / <b>{total_collectors:,}</b>\n"
        f"├ <b>{sc('cards')} :</b> <b>{char_count:,}</b> <tg-emoji emoji-id=\"6093434630147415641\">🃏</tg-emoji>\n"
        f"└ <b>{sc('progress')} :</b> <code>{progress_bar}</code> <b>{completion_pct}%</b>\n\n"
        f"<tg-emoji emoji-id=\"5264895611517300926\">🏦</tg-emoji> <b>{sc('vault & wallet')}</b>\n"
        f"├ <b>{sc('balance')} :</b> <b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {balance:,}</b>\n"
        f"└ <b>{sc('tokens')} :</b> <b><tg-emoji emoji-id=\"6109593993627050230\">💠</tg-emoji> {tokens:,}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i><b>{sc('keep grabbing to reach top 10!')}</b></i>"
    )

    profile_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("ᴄᴛᴏᴘ", callback_data="lb_chars", icon_custom_emoji_id="6093434630147415641"), InlineKeyboardButton("ʙᴛᴏᴘ", callback_data="lb_bal", icon_custom_emoji_id="5472030678633684592")],
        [InlineKeyboardButton("⟳", callback_data="lb_refresh_profile"), InlineKeyboardButton("⋞", callback_data="lb_menu")],
        [InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="lb_close")]
    ])

    await send_or_edit(update, context, text, profile_kb, edit)

# ---------- Owner/sudo stats ----------
async def stats(update: Update, context: CallbackContext, edit=False):
    user_id = update.effective_user.id
    if not is_sudo(user_id):
        msg = f"<b>{sc('unauthorized.')}</b>"
        if edit: return await update.callback_query.answer(sc("unauthorized."), show_alert=True)
        return await update.message.reply_text(msg, parse_mode='HTML')

    users = await user_collection.count_documents({})
    groups = len(await group_user_totals_collection.distinct('group_id'))
    collectors = await get_cached_data("total_collectors", fetch_total_collectors)

    total_chars_result = await user_collection.aggregate([
        {"$match": {"characters": {"$exists": True, "$type": "array", "$not": {"$size": 0}}}},
        {"$project": {"count": {"$size": "$characters"}}},
        {"$group": {"_id": None, "total": {"$sum": "$count"}}}
    ]).to_list(1)
    total_chars = total_chars_result[0]['total'] if total_chars_result else 0

    text = (
        f"<tg-emoji emoji-id=\"6093755816391745206\">📊</tg-emoji> <b>{sc('system stats')}</b> <tg-emoji emoji-id=\"6093755816391745206\">📊</tg-emoji>\n\n"
        f"<b>{sc('users')}</b>: <b>{users:,}</b>\n"
        f"<b>{sc('grabbers')}</b>: <b>{collectors:,}</b>\n"
        f"<b>{sc('groups')}</b>: <b>{groups:,}</b>\n"
        f"<b>{sc('total characters')}</b>: <b>{total_chars:,}</b>\n\n"
        f"<i><b>{datetime.now().strftime('%H:%M:%S')}</b></i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⟳", callback_data="lb_refresh_stats")],
        [InlineKeyboardButton("×", callback_data="lb_close")]
    ])
    await send_or_edit(update, context, text, kb, edit)

# ---------- Export commands (sudo only) ----------
async def export_users(update: Update, context: CallbackContext):
    if not is_sudo(update.effective_user.id):
        return await update.message.reply_text(f"<b>{sc('unauthorized.')}</b>", parse_mode='HTML')

    users = await eco_collection.find({}).to_list(None)
    lines = [f"[{u.get('id') or u.get('user_id')}] {u.get('first_name')} | @{u.get('username')} | Bal: {extract_balance(u)}" for u in users]
    content = f"USER EXPORT — {datetime.now()}\nTotal: {len(users):,}\n{'='*50}\n\n" + "\n".join(lines)

    with open('users.txt', 'w', encoding='utf-8') as f: f.write(content)
    with open('users.txt', 'rb') as f: await context.bot.send_document(update.effective_chat.id, f, caption=f"<b>{sc('users')}</b>: <b>{len(users):,}</b>", parse_mode='HTML')
    os.remove('users.txt')

async def export_groups(update: Update, context: CallbackContext):
    if not is_sudo(update.effective_user.id):
        return await update.message.reply_text(f"<b>{sc('unauthorized.')}</b>", parse_mode='HTML')

    groups = await top_global_groups_collection.find({}).sort('count', -1).to_list(None)
    lines = [f"[{i}] {g.get('group_name')} | {g.get('count', 0):,}" for i, g in enumerate(groups, 1)]
    content = f"GROUP EXPORT — {datetime.now()}\nTotal: {len(groups):,}\n{'='*50}\n\n" + "\n".join(lines)

    with open('groups.txt', 'w', encoding='utf-8') as f: f.write(content)
    with open('groups.txt', 'rb') as f: await context.bot.send_document(update.effective_chat.id, f, caption=f"<b>{sc('groups')}</b>: <b>{len(groups):,}</b>", parse_mode='HTML')
    os.remove('groups.txt')

# ---------- Callback router ----------
CALLBACKS = {
    "lb_menu": tops_menu, "lb_profile": my_profile, "lb_tokens": top_tokens,
    "lb_bal": top_balance, "lb_chars": top_characters, "lb_gtop": top_groups, "lb_stats": stats,
}

# --------- Refresh & Cache clear Logic ----------
async def cb(update: Update, context: CallbackContext):
    data = update.callback_query.data
    
    if data == "lb_close":
        return await update.callback_query.message.delete()
        
    if data.startswith("lb_refresh_"):
        actual_cb = data.replace("lb_refresh_", "lb_")
        cache_map = {
            "lb_bal": "top_balance", "lb_tokens": "top_tokens", "lb_chars": "top_chars",
            "lb_gtop": "top_groups", "lb_profile": "total_collectors", "lb_stats": "total_collectors"
        }
        cache_key = cache_map.get(actual_cb)
        if cache_key in LB_CACHE: del LB_CACHE[cache_key]
        data = actual_cb

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
application.add_handler(CallbackQueryHandler(cb, pattern="^lb_", block=False))

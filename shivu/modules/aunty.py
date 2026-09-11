# ============================================================
# 🏦  BANK OF AUNTY — 4% Daily Interest Savings System
# Prefix: bka_  (no conflict with existing bk_ from tasks)
# Logs: -1003893927065 (full transaction details)
# ============================================================
import time
import asyncio
from datetime import datetime, timedelta, timezone
from html import escape
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.helpers import mention_html
from telegram.ext import (
    CommandHandler, CallbackQueryHandler, CallbackContext,
    MessageHandler, filters
)
from telegram.error import BadRequest

from shivu import application, OWNER_ID
from shivu import sudo_users as SUDO_USERS
from shivu.Database.db import eco_collection


# ============================================================
# ⚙️  Config
# ============================================================
BANK_NAME    = "Bank Of Aunty"
DAILY_RATE   = 0.04
DAY_SECONDS  = 86400
MIN_DEPOSIT  = 100
MIN_WITHDRAW = 100
BANK_BANNER  = "https://files.catbox.moe/ewtw4l.png"
LOG_GROUP_ID = -1003893927065
IST          = timezone(timedelta(hours=5, minutes=30))

WALLET_KEYS = ['balance', 'coins', 'wallet', 'money', 'gold', 'bal']


# ============================================================
# 🧰 Helpers
# ============================================================
def sc(t: str) -> str:
    return str(t).translate(str.maketrans(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
    ))


def fmt(n):
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def is_sudo(user_id):
    return user_id == OWNER_ID or str(user_id) in SUDO_USERS or user_id in SUDO_USERS


def extract_balance(doc):
    if not doc:
        return 0
    for k in WALLET_KEYS:
        v = doc.get(k)
        if v is not None:
            try:
                return int(float(v))
            except Exception:
                pass
    return 0


def wallet_key(doc):
    if doc:
        for k in WALLET_KEYS:
            if doc.get(k) is not None:
                return k
    return 'balance'


def bank_balance(doc):
    try:
        return int(doc.get('bank_balance', 0) or 0)
    except Exception:
        return 0


# ============================================================
# 📡 Logger — Full Transaction Details
# ============================================================
async def send_bank_log(
    context, action_icon, action_title, user,
    amount, wallet_before, wallet_after,
    bank_before, bank_after,
    total_deposited=None, total_withdrawn=None,
    interest_earned=None, mode="command"
):
    ts = datetime.now(IST).strftime("%I:%M %p • %d/%m/%y")

    name = escape(user.first_name or "User")
    uname = f"@{user.username}" if user.username else "—"

    lines = [
        f"<b>{action_icon} {action_title}</b>",
        "",
        f"<b>├ {sc('ᴜsᴇʀ')} :</b> <a href='tg://user?id={user.id}'>{name}</a>",
        f"<b>├ {sc('ᴜsᴇʀɴᴀᴍᴇ')} :</b> {uname}",
        f"<b>├ {sc('ᴜsᴇʀ ɪᴅ')} :</b> <code>{user.id}</code>",
        f"<b>├ {sc('ᴀᴍᴏᴜɴᴛ')} :</b> <b>{fmt(amount)}</b> <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>",
        f"<b>├ {sc('ᴡᴀʟʟᴇᴛ')} :</b> <b>{fmt(wallet_before)}</b> → <b>{fmt(wallet_after)}</b>",
        f"<b>├ {sc('ʙᴀɴᴋ')} :</b> <b>{fmt(bank_before)}</b> → <b>{fmt(bank_after)}</b>",
    ]

    if total_deposited is not None:
        lines.append(f"<b>├ {sc('ʟɪꜰᴇᴛɪᴍᴇ ᴅᴇᴘᴏsɪᴛ')} :</b> <b>{fmt(total_deposited)}</b>")
    if total_withdrawn is not None:
        lines.append(f"<b>├ {sc('ʟɪꜰᴇᴛɪᴍᴇ ᴡɪᴛʜᴅʀᴀᴡ')} :</b> <b>{fmt(total_withdrawn)}</b>")
    if interest_earned is not None and interest_earned > 0:
        lines.append(f"<b>├ {sc('ɪɴᴛᴇʀᴇsᴛ ᴊᴜsᴛ ᴄʀᴇᴅɪᴛᴇᴅ')} :</b> <b>+{fmt(interest_earned)}</b>")

    lines.append(f"<b>├ {sc('ᴍᴏᴅᴇ')} :</b> <b>{sc(mode)}</b>")
    lines.append(f"<b>╰ {sc('ᴛɪᴍᴇ')} :</b> <b>{ts}</b>")

    try:
        await context.bot.send_message(
            chat_id=LOG_GROUP_ID,
            text="\n".join(lines),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"[BANK LOG ERROR] {e}")


# ============================================================
# 💹 Interest Engine
# ============================================================
def calc_interest(bal, last_ts):
    now = time.time()
    if bal <= 0 or not last_ts:
        return bal, now, 0, 0
    elapsed = now - last_ts
    days = int(elapsed // DAY_SECONDS)
    if days <= 0:
        return bal, last_ts, 0, 0
    new_bal = int(bal * ((1 + DAILY_RATE) ** days))
    earned = new_bal - bal
    new_last = last_ts + (days * DAY_SECONDS)
    return new_bal, new_last, earned, days


async def settle_interest(user_id):
    doc = await eco_collection.find_one({'id': user_id})
    if not doc:
        return 0
    bal = bank_balance(doc)
    last = doc.get('bank_last_interest')
    new_bal, new_last, earned, days = calc_interest(bal, last)
    if earned > 0:
        await eco_collection.update_one(
            {'id': user_id},
            {'$set': {
                'bank_balance': new_bal,
                'bank_last_interest': new_last,
                'bank_total_interest': int(doc.get('bank_total_interest', 0) or 0) + earned
            }}
        )
    return earned


# ============================================================
# 💰 Deposit / Withdraw (returns full before/after)
# ============================================================
async def deposit_coins(user_id, amount):
    doc = await eco_collection.find_one({'id': user_id})
    if not doc:
        return {'ok': False, 'reason': 'no_account'}

    interest = await settle_interest(user_id)
    doc = await eco_collection.find_one({'id': user_id})

    wallet_before = extract_balance(doc)
    bank_before = bank_balance(doc)

    if wallet_before < amount:
        return {'ok': False, 'reason': 'insufficient',
                'wallet': wallet_before, 'bank': bank_before}

    last = doc.get('bank_last_interest')

    updates = {
        'bank_balance': bank_before + amount,
        'bank_total_deposited': int(doc.get('bank_total_deposited', 0) or 0) + amount,
    }
    if bank_before == 0 or not last:
        updates['bank_last_interest'] = time.time()

    wkey = wallet_key(doc)
    updates[wkey] = wallet_before - amount

    await eco_collection.update_one({'id': user_id}, {'$set': updates})

    return {
        'ok': True,
        'wallet_before': wallet_before,
        'wallet_after': wallet_before - amount,
        'bank_before': bank_before,
        'bank_after': bank_before + amount,
        'total_deposited': updates['bank_total_deposited'],
        'total_withdrawn': int(doc.get('bank_total_withdrawn', 0) or 0),
        'interest_earned': interest,
    }


async def withdraw_coins(user_id, amount):
    doc = await eco_collection.find_one({'id': user_id})
    if not doc:
        return {'ok': False, 'reason': 'no_account'}

    interest = await settle_interest(user_id)
    doc = await eco_collection.find_one({'id': user_id})

    wallet_before = extract_balance(doc)
    bank_before = bank_balance(doc)

    if bank_before < amount:
        return {'ok': False, 'reason': 'insufficient_bank',
                'wallet': wallet_before, 'bank': bank_before}

    new_bank = bank_before - amount

    updates = {
        'bank_balance': new_bank,
        'bank_total_withdrawn': int(doc.get('bank_total_withdrawn', 0) or 0) + amount,
    }
    if new_bank <= 0:
        updates['bank_last_interest'] = None
    elif not doc.get('bank_last_interest'):
        updates['bank_last_interest'] = time.time()

    wkey = wallet_key(doc)
    updates[wkey] = wallet_before + amount

    await eco_collection.update_one({'id': user_id}, {'$set': updates})

    return {
        'ok': True,
        'wallet_before': wallet_before,
        'wallet_after': wallet_before + amount,
        'bank_before': bank_before,
        'bank_after': new_bank,
        'total_deposited': int(doc.get('bank_total_deposited', 0) or 0),
        'total_withdrawn': updates['bank_total_withdrawn'],
        'interest_earned': interest,
    }


# ============================================================
# 🖼 Renderer
# ============================================================
async def send_or_edit(update, context, text, kb, edit=False):
    if edit and update.callback_query:
        q = update.callback_query
        try:
            await q.edit_message_media(
                media=InputMediaPhoto(media=BANK_BANNER, caption=text, parse_mode='HTML'),
                reply_markup=kb
            )
            return
        except BadRequest as e:
            if "not modified" in str(e).lower():
                return
        except Exception:
            pass

        try:
            await q.message.delete()
        except Exception:
            pass
        try:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=BANK_BANNER, caption=text,
                parse_mode='HTML', reply_markup=kb
            )
        except Exception:
            pass
    else:
        await update.message.reply_photo(
            photo=BANK_BANNER, caption=text,
            parse_mode='HTML', reply_markup=kb
        )


# ============================================================
# 🏦 Bank Home Page
# ============================================================
async def bank_page(update, context, edit=False, notice=None):
    user = update.effective_user
    await settle_interest(user.id)
    doc = await eco_collection.find_one({'id': user.id})

    if not doc:
        text = (
            f"<tg-emoji emoji-id=\"5264895611517300926\">🏦</tg-emoji> "
            f"<b>{sc('bank of aunty')}</b>\n"
            f"<b>{sc('please start the bot first to use the bank.')}</b>"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(
            "ᴄʟᴏsᴇ", callback_data=f"bka_{user.id}_close")]])
        return await send_or_edit(update, context, text, kb, edit)

    wallet  = extract_balance(doc)
    bank    = bank_balance(doc)
    total_d = int(doc.get('bank_total_deposited', 0) or 0)
    total_w = int(doc.get('bank_total_withdrawn', 0) or 0)
    total_i = int(doc.get('bank_total_interest', 0) or 0)

    last = doc.get('bank_last_interest') or time.time()
    remaining = DAY_SECONDS - ((time.time() - last) % DAY_SECONDS) if bank > 0 else DAY_SECONDS
    hh = int(remaining // 3600)
    mm = int((remaining % 3600) // 60)
    ss = int(remaining % 60)
    daily = int(bank * DAILY_RATE) if bank > 0 else 0

    note = f"\n<blockquote>{notice}</blockquote>\n" if notice else ""

    text = (
        f"<tg-emoji emoji-id=\"5264895611517300926\">🏦</tg-emoji> "
        f"<b>{sc('bank of aunty')}</b> "
        f"<tg-emoji emoji-id=\"5264895611517300926\">🏦</tg-emoji>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"5217822164362739968\">👑</tg-emoji> "
        f"<b>{user.mention_html()}</b>  •  <code>{user.id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> "
        f"<b>{sc('wallet')} :</b> <b>{fmt(wallet)}</b>\n"
        f"<tg-emoji emoji-id=\"5264895611517300926\">🏦</tg-emoji> "
        f"<b>{sc('bank')} :</b> <b>{fmt(bank)}</b>\n"
        f"<tg-emoji emoji-id=\"6093755816391745206\">📊</tg-emoji> "
        f"<b>{sc('daily +4%')} :</b> <b>+{fmt(daily)}</b>\n"
        f"<tg-emoji emoji-id=\"6093601953483334318\">✨</tg-emoji> "
        f"<b>{sc('next in')} :</b> <code>{hh:02d}h {mm:02d}m {ss:02d}s</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"6100397639717625616\">✔️</tg-emoji> "
        f"<b>{sc('deposited')} :</b> <b>{fmt(total_d)}</b>\n"
        f"<tg-emoji emoji-id=\"6105189427355589893\">⚠️</tg-emoji> "
        f"<b>{sc('withdrawn')} :</b> <b>{fmt(total_w)}</b>\n"
        f"<tg-emoji emoji-id=\"5436040291507247633\">🎉</tg-emoji> "
        f"<b>{sc('interest earned')} :</b> <b>{fmt(total_i)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{note}"
        f"<i><b>{sc('deposit now and earn 4% daily!')}</b></i>"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("ᴅᴇᴘᴏsɪᴛ", callback_data=f"bka_{user.id}_dep",
                                 icon_custom_emoji_id="5472030678633684592"),
            InlineKeyboardButton("ᴡɪᴛʜᴅʀᴀᴡ", callback_data=f"bka_{user.id}_wd",
                                 icon_custom_emoji_id="5264895611517300926"),
        ],
        [
            InlineKeyboardButton("ʀᴜʟᴇs", callback_data=f"bka_{user.id}_rules",
                                 icon_custom_emoji_id="6093434630147415641"),
            InlineKeyboardButton("ᴛᴏᴘ", callback_data=f"bka_{user.id}_top",
                                 icon_custom_emoji_id="6093755816391745206"),
        ],
        [
            InlineKeyboardButton("⟳", callback_data=f"bka_{user.id}_refresh"),
            InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data=f"bka_{user.id}_close"),
        ],
    ])
    await send_or_edit(update, context, text, kb, edit)


# ============================================================
# 💸 Deposit Menu
# ============================================================
async def deposit_menu(update, context, edit=False):
    user = update.effective_user
    doc = await eco_collection.find_one({'id': user.id})
    wallet = extract_balance(doc) if doc else 0

    text = (
        f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> "
        f"<b>{sc('deposit coins')}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"5264895611517300926\">🏦</tg-emoji> "
        f"<b>{sc('wallet')} :</b> <b>{fmt(wallet)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>{sc('choose amount or use')}</b> <code>/deposit &lt;amt&gt;</code>\n"
        f"<i>{sc('minimum')} : {MIN_DEPOSIT}</i>"
    )
    uid = user.id
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("500", callback_data=f"bka_{uid}_dp_500"),
            InlineKeyboardButton("1ᴋ", callback_data=f"bka_{uid}_dp_1000"),
            InlineKeyboardButton("5ᴋ", callback_data=f"bka_{uid}_dp_5000"),
        ],
        [
            InlineKeyboardButton("10ᴋ", callback_data=f"bka_{uid}_dp_10000"),
            InlineKeyboardButton("50ᴋ", callback_data=f"bka_{uid}_dp_50000"),
            InlineKeyboardButton("ᴀʟʟ", callback_data=f"bka_{uid}_dp_all"),
        ],
        [InlineKeyboardButton("≼ ʙᴀᴄᴋ", callback_data=f"bka_{uid}_refresh")],
    ])
    await send_or_edit(update, context, text, kb, edit)


# ============================================================
# 🏧 Withdraw Menu
# ============================================================
async def withdraw_menu(update, context, edit=False):
    user = update.effective_user
    await settle_interest(user.id)
    doc = await eco_collection.find_one({'id': user.id})
    bank = bank_balance(doc) if doc else 0

    text = (
        f"<tg-emoji emoji-id=\"5264895611517300926\">🏦</tg-emoji> "
        f"<b>{sc('withdraw coins')}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"5264895611517300926\">🏦</tg-emoji> "
        f"<b>{sc('bank')} :</b> <b>{fmt(bank)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>{sc('choose amount or use')}</b> <code>/withdraw &lt;amt&gt;</code>\n"
        f"<i>{sc('minimum')} : {MIN_WITHDRAW}</i>"
    )
    uid = user.id
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("500", callback_data=f"bka_{uid}_wq_500"),
            InlineKeyboardButton("1ᴋ", callback_data=f"bka_{uid}_wq_1000"),
            InlineKeyboardButton("5ᴋ", callback_data=f"bka_{uid}_wq_5000"),
        ],
        [
            InlineKeyboardButton("10ᴋ", callback_data=f"bka_{uid}_wq_10000"),
            InlineKeyboardButton("ᴀʟʟ", callback_data=f"bka_{uid}_wq_all"),
        ],
        [InlineKeyboardButton("≼ ʙᴀᴄᴋ", callback_data=f"bka_{uid}_refresh")],
    ])
    await send_or_edit(update, context, text, kb, edit)


# ============================================================
# 📜 Rules Page (public)
# ============================================================
async def bank_rules(update, context, edit=False):
    uid = update.callback_query.from_user.id if edit else update.effective_user.id
    text = (
        f"<tg-emoji emoji-id=\"6093434630147415641\">🃏</tg-emoji> "
        f"<b>{sc('bank of aunty — rules')}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>1.</b> {sc('min deposit')} : <b>{MIN_DEPOSIT}</b>\n"
        f"<b>2.</b> {sc('min withdraw')} : <b>{MIN_WITHDRAW}</b>\n"
        f"<b>3.</b> {sc('daily interest')} : <b>4%</b>\n"
        f"<b>4.</b> {sc('interest compounds every 24 hours')}\n"
        f"<b>5.</b> {sc('withdraw anytime, no penalty')}\n"
        f"<b>6.</b> {sc('interest credited automatically on next action')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i><b>{sc('deposit today, grow every single day!')}</b></i>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("≼ ʙᴀᴄᴋ", callback_data=f"bka_{uid}_refresh")]])
    await send_or_edit(update, context, text, kb, edit)


# ============================================================
# 🏆 Top Bankers (public)
# ============================================================
async def fetch_top_bankers():
    data = await eco_collection.find({'bank_balance': {'$gt': 0}}).to_list(length=10000)
    return sorted(data, key=lambda x: bank_balance(x), reverse=True)[:10]


async def top_bankers(update, context, edit=False):
    uid = update.callback_query.from_user.id if edit else update.effective_user.id
    data = await fetch_top_bankers()

    if not data:
        text = (
            f"<tg-emoji emoji-id=\"6093755816391745206\">📊</tg-emoji> "
            f"<b>{sc('top bankers')}</b>\n\n"
            f"<b>{sc('no bankers yet — be the first!')}</b>"
        )
    else:
        rows = []
        for i, u in enumerate(data, 1):
            uid_v = u.get('id') or u.get('user_id') or u.get('_id', 0)
            try:
                uid_int = int(uid_v)
            except Exception:
                uid_int = uid_v
            name = u.get('first_name', 'Unknown')
            try:
                link = mention_html(uid_int, name)
            except Exception:
                link = escape(str(name))
            bal = bank_balance(u)
            rows.append(
                f"<b>{i}.</b> {link} — "
                f"<tg-emoji emoji-id=\"5264895611517300926\">🏦</tg-emoji> "
                f"<b>{fmt(bal)}</b>"
            )
        text = (
            f"<tg-emoji emoji-id=\"6093755816391745206\">📊</tg-emoji> "
            f"<b>{sc('top 10 bankers')}</b> "
            f"<tg-emoji emoji-id=\"6093755816391745206\">📊</tg-emoji>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            + "\n".join(rows)
        )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("≼ ʙᴀᴄᴋ", callback_data=f"bka_{uid}_refresh")]])
    await send_or_edit(update, context, text, kb, edit)


# ============================================================
# 📥 Commands
# ============================================================
async def bank_cmd(update, context):
    await bank_page(update, context, edit=False)


async def deposit_cmd(update, context):
    if not context.args:
        return await deposit_menu(update, context, edit=False)
    raw = context.args[0].replace(",", "").replace("_", "").strip()
    try:
        amount = int(raw)
    except Exception:
        return await update.message.reply_text(
            f"<b>ɪɴᴠᴀʟɪᴅ ᴀᴍᴏᴜɴᴛ.</b>\n<b>ᴜꜱᴀɢᴇ :</b> <code>/deposit &lt;amt&gt;</code>",
            parse_mode='HTML')
    if amount < MIN_DEPOSIT:
        return await update.message.reply_text(
            f"<b>{sc('min deposit')} : {MIN_DEPOSIT}</b>", parse_mode='HTML')

    u = update.effective_user
    res = await deposit_coins(u.id, amount)
    if not res['ok']:
        if res['reason'] == 'no_account':
            return await update.message.reply_text(
                f"<b>{sc('please start the bot first!')}</b>", parse_mode='HTML')
        return await update.message.reply_text(
            f"<b>{sc('insufficient wallet')} : {fmt(res.get('wallet',0))}</b>",
            parse_mode='HTML')

    # ---------- LOG ----------
    asyncio.create_task(send_bank_log(
        context,
        "<tg-emoji emoji-id=\"6100397639717625616\">✔️</tg-emoji>",
        sc("ʙᴀɴᴋ ᴅᴇᴘᴏsɪᴛ"),
        u, amount,
        res['wallet_before'], res['wallet_after'],
        res['bank_before'], res['bank_after'],
        res['total_deposited'], res['total_withdrawn'],
        res['interest_earned'],
        mode="ᴄᴏᴍᴍᴀɴᴅ"
    ))

    notice = (f"✅ <b>{sc('deposit successful')}</b>\n"
              f"<b>+{fmt(amount)}</b> <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>")
    await bank_page(update, context, edit=False, notice=notice)


async def withdraw_cmd(update, context):
    if not context.args:
        return await withdraw_menu(update, context, edit=False)
    raw = context.args[0].replace(",", "").replace("_", "").strip()
    try:
        amount = int(raw)
    except Exception:
        return await update.message.reply_text(
            f"<b>ɪɴᴠᴀʟɪᴅ ᴀᴍᴏᴜɴᴛ.</b>\n<b>ᴜꜱᴀɢᴇ :</b> <code>/withdraw &lt;amt&gt;</code>",
            parse_mode='HTML')
    if amount < MIN_WITHDRAW:
        return await update.message.reply_text(
            f"<b>{sc('min withdraw')} : {MIN_WITHDRAW}</b>", parse_mode='HTML')

    u = update.effective_user
    res = await withdraw_coins(u.id, amount)
    if not res['ok']:
        if res['reason'] == 'no_account':
            return await update.message.reply_text(
                f"<b>{sc('please start the bot first!')}</b>", parse_mode='HTML')
        return await update.message.reply_text(
            f"<b>{sc('insufficient bank')} : {fmt(res.get('bank',0))}</b>",
            parse_mode='HTML')

    asyncio.create_task(send_bank_log(
        context,
        "<tg-emoji emoji-id=\"6105189427355589893\">⚠️</tg-emoji>",
        sc("ʙᴀɴᴋ ᴡɪᴛʜᴅʀᴀᴡ"),
        u, amount,
        res['wallet_before'], res['wallet_after'],
        res['bank_before'], res['bank_after'],
        res['total_deposited'], res['total_withdrawn'],
        res['interest_earned'],
        mode="ᴄᴏᴍᴍᴀɴᴅ"
    ))

    notice = (f"✅ <b>{sc('withdraw successful')}</b>\n"
              f"<b>+{fmt(amount)}</b> <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>")
    await bank_page(update, context, edit=False, notice=notice)


async def bank_rules_cmd(update, context):
    await bank_rules(update, context, edit=False)


async def banktop_cmd(update, context):
    await top_bankers(update, context, edit=False)


# ============================================================
# 🔔 Text Trigger — "Bank Of Aunty"
# ============================================================
async def bank_text_trigger(update: Update, context: CallbackContext):
    if not update.message or not update.message.text:
        return
    await bank_page(update, context, edit=False)


# ============================================================
# 🔀 Callback Router (prefix bka_)
# ============================================================
async def bank_callback(update: Update, context: CallbackContext):
    q = update.callback_query
    data = q.data
    clicker = q.from_user

    parts = data.split("_")
    if len(parts) < 3:
        return await q.answer("Invalid data", show_alert=True)

    try:
        owner_uid = int(parts[1])
    except Exception:
        return await q.answer("Invalid data", show_alert=True)

    action = parts[2]
    extra = parts[3] if len(parts) > 3 else None

    # ---------- Close ----------
    if action == "close":
        if clicker.id != owner_uid:
            return await q.answer(sc("not your page"), show_alert=True)
        await q.answer()
        try:
            await q.message.delete()
        except Exception:
            pass
        return

    # ---------- Rules (public) ----------
    if action == "rules":
        await q.answer()
        return await bank_rules(update, context, edit=True)

    # ---------- Top (public) ----------
    if action == "top":
        await q.answer()
        return await top_bankers(update, context, edit=True)

    # ---------- Owner-locked from here ----------
    if clicker.id != owner_uid:
        return await q.answer(
            sc("ᴛʜɪs ɪs ɴᴏᴛ ʏᴏᴜʀ ᴘᴀɢᴇ · ᴜsᴇ /bank ᴛᴏ ᴏᴘᴇɴ ʏᴏᴜʀ ᴏᴡɴ"),
            show_alert=True
        )

    if action == "refresh":
        await q.answer(sc("refreshed"))
        return await bank_page(update, context, edit=True)

    if action == "dep":
        await q.answer()
        return await deposit_menu(update, context, edit=True)

    if action == "wd":
        await q.answer()
        return await withdraw_menu(update, context, edit=True)

    # ---------- Quick Deposit ----------
    if action == "dp":
        if extra == "all":
            doc = await eco_collection.find_one({'id': owner_uid})
            amount = extract_balance(doc) if doc else 0
        else:
            try:
                amount = int(extra)
            except Exception:
                return await q.answer("Invalid amount", show_alert=True)

        if amount < MIN_DEPOSIT:
            return await q.answer(sc(f"min deposit is {MIN_DEPOSIT}"), show_alert=True)

        u = clicker
        res = await deposit_coins(u.id, amount)
        if not res['ok']:
            return await q.answer(sc("insufficient wallet balance"), show_alert=True)

        await q.answer(sc("deposited"))

        asyncio.create_task(send_bank_log(
            context,
            "<tg-emoji emoji-id=\"6100397639717625616\">✔️</tg-emoji>",
            sc("ʙᴀɴᴋ ᴅᴇᴘᴏsɪᴛ"),
            u, amount,
            res['wallet_before'], res['wallet_after'],
            res['bank_before'], res['bank_after'],
            res['total_deposited'], res['total_withdrawn'],
            res['interest_earned'],
            mode="ǫᴜɪᴄᴋ ʙᴜᴛᴛᴏɴ"
        ))

        notice = (f"✅ <b>{sc('deposit successful')}</b>\n"
                  f"<b>+{fmt(amount)}</b> <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>")
        return await bank_page(update, context, edit=True, notice=notice)

    # ---------- Quick Withdraw ----------
    if action == "wq":
        await settle_interest(owner_uid)
        doc = await eco_collection.find_one({'id': owner_uid})
        if extra == "all":
            amount = bank_balance(doc) if doc else 0
        else:
            try:
                amount = int(extra)
            except Exception:
                return await q.answer("Invalid amount", show_alert=True)

        if amount < MIN_WITHDRAW:
            return await q.answer(sc(f"min withdraw is {MIN_WITHDRAW}"), show_alert=True)

        u = clicker
        res = await withdraw_coins(u.id, amount)
        if not res['ok']:
            return await q.answer(sc("insufficient bank balance"), show_alert=True)

        await q.answer(sc("withdrawn"))

        asyncio.create_task(send_bank_log(
            context,
            "<tg-emoji emoji-id=\"6105189427355589893\">⚠️</tg-emoji>",
            sc("ʙᴀɴᴋ ᴡɪᴛʜᴅʀᴀᴡ"),
            u, amount,
            res['wallet_before'], res['wallet_after'],
            res['bank_before'], res['bank_after'],
            res['total_deposited'], res['total_withdrawn'],
            res['interest_earned'],
            mode="ǫᴜɪᴄᴋ ʙᴜᴛᴛᴏɴ"
        ))

        notice = (f"✅ <b>{sc('withdraw successful')}</b>\n"
                  f"<b>+{fmt(amount)}</b> <tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>")
        return await bank_page(update, context, edit=True, notice=notice)

    await q.answer()


# ============================================================
# 📌 Register Handlers
# ============================================================
application.add_handler(CommandHandler(['bank', 'aunty', 'boa'], bank_cmd, block=False))
application.add_handler(CommandHandler('deposit', deposit_cmd, block=False))
application.add_handler(CommandHandler('withdraw', withdraw_cmd, block=False))
application.add_handler(CommandHandler('bankrules', bank_rules_cmd, block=False))
application.add_handler(CommandHandler('banktop', banktop_cmd, block=False))
application.add_handler(CallbackQueryHandler(bank_callback, pattern="^bka_", block=False))
application.add_handler(MessageHandler(
    filters.TEXT & ~filters.COMMAND & filters.Regex(r"(?i)^\s*bank[\s_]+of[\s_]+aunty\s*$"),
    bank_text_trigger, block=False
))

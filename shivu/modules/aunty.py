# ============================================================
# 🏦  BANK OF AUNTY — Savings & 4% Daily Interest System
# ============================================================
import os
import time
from datetime import datetime
from html import escape
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.helpers import mention_html
from telegram.ext import (
    CommandHandler, CallbackContext, CallbackQueryHandler,
    MessageHandler, filters
)
from telegram.error import BadRequest

from shivu import application, OWNER_ID, user_collection
from shivu import sudo_users as SUDO_USERS
from shivu.Database.db import eco_collection


# ---------- 🔧 Bank Configuration ----------
BANK_NAME       = "Bank Of Aunty"
DAILY_RATE      = 0.04          # 4% per day (compounded)
DAY_SECONDS     = 86400         # 24 hours
MIN_DEPOSIT     = 100
MIN_WITHDRAW    = 100
BANK_BANNER     = "https://files.catbox.moe/ewtw4l.png"
BALANCE_KEYS    = ['balance', 'coins', 'wallet', 'money', 'gold', 'bal']


# ============================================================
# 🧰 Helpers
# ============================================================
def sc(t: str) -> str:
    return t.translate(str.maketrans(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ))


def fmt(n) -> str:
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def is_sudo(user_id):
    return user_id == OWNER_ID or str(user_id) in SUDO_USERS or user_id in SUDO_USERS


def extract_balance(doc):
    if not doc or not isinstance(doc, dict):
        return 0
    for k in BALANCE_KEYS:
        v = doc.get(k)
        if v is not None:
            try:
                return int(float(v))
            except Exception:
                pass
    return 0


def balance_key(doc):
    if not doc:
        return 'balance'
    for k in BALANCE_KEYS:
        if doc.get(k) is not None:
            return k
    return 'balance'


def bank_balance(doc):
    try:
        return int(doc.get('bank_balance', 0) or 0)
    except Exception:
        return 0


# ============================================================
# 💹 Interest Engine (Compound, applies full days)
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
    """Credit any pending interest for the user. Returns amount credited."""
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
# 💰 Core: Deposit / Withdraw Logic
# ============================================================
async def deposit_coins(user_id, amount):
    doc = await eco_collection.find_one({'id': user_id})
    if not doc:
        return {'ok': False, 'reason': 'no_account'}

    await settle_interest(user_id)
    doc = await eco_collection.find_one({'id': user_id})

    wallet = extract_balance(doc)
    if wallet < amount:
        return {'ok': False, 'reason': 'insufficient', 'wallet': wallet}

    bank = bank_balance(doc)
    last = doc.get('bank_last_interest')

    updates = {
        'bank_balance': bank + amount,
        'bank_total_deposited': int(doc.get('bank_total_deposited', 0) or 0) + amount,
    }
    # Start interest clock on first deposit
    if bank == 0 or not last:
        updates['bank_last_interest'] = time.time()

    wkey = balance_key(doc)
    updates[wkey] = wallet - amount

    await eco_collection.update_one({'id': user_id}, {'$set': updates})
    return {'ok': True, 'wallet': wallet - amount, 'bank': bank + amount}


async def withdraw_coins(user_id, amount):
    doc = await eco_collection.find_one({'id': user_id})
    if not doc:
        return {'ok': False, 'reason': 'no_account'}

    await settle_interest(user_id)
    doc = await eco_collection.find_one({'id': user_id})

    bank = bank_balance(doc)
    if bank < amount:
        return {'ok': False, 'reason': 'insufficient_bank', 'bank': bank}

    wallet = extract_balance(doc)
    new_bank = bank - amount

    updates = {
        'bank_balance': new_bank,
        'bank_total_withdrawn': int(doc.get('bank_total_withdrawn', 0) or 0) + amount,
    }
    # Reset clock if bank emptied
    if new_bank <= 0:
        updates['bank_last_interest'] = None
    elif not doc.get('bank_last_interest'):
        updates['bank_last_interest'] = time.time()

    wkey = balance_key(doc)
    updates[wkey] = wallet + amount

    await eco_collection.update_one({'id': user_id}, {'$set': updates})
    return {'ok': True, 'wallet': wallet + amount, 'bank': new_bank}


# ============================================================
# 📤 Send / Edit Renderer
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
# 🏦 Main Bank Page
# ============================================================
async def bank_page(update: Update, context: CallbackContext, edit=False, notice=None):
    user = update.effective_user

    earned = await settle_interest(user.id)
    doc = await eco_collection.find_one({'id': user.id})

    if not doc:
        text = (
            f"<tg-emoji emoji-id=\"5264895611517300926\">🏦</tg-emoji> "
            f"<b>{sc('welcome to bank of aunty')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>{sc('please start the bot first and earn some coins before using the bank.')}</b>"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="bk_close")]])
        return await send_or_edit(update, context, text, kb, edit)

    wallet   = extract_balance(doc)
    bank     = bank_balance(doc)
    total_d  = int(doc.get('bank_total_deposited', 0) or 0)
    total_w  = int(doc.get('bank_total_withdrawn', 0) or 0)
    total_i  = int(doc.get('bank_total_interest', 0) or 0)

    # interest countdown
    last = doc.get('bank_last_interest') or time.time()
    elapsed = time.time() - last
    remaining = DAY_SECONDS - (elapsed % DAY_SECONDS) if bank > 0 else DAY_SECONDS
    hh = int(remaining // 3600)
    mm = int((remaining % 3600) // 60)
    ss = int(remaining % 60)

    daily = int(bank * DAILY_RATE) if bank > 0 else 0

    if notice:
        note = f"\n<blockquote>{notice}</blockquote>\n"
    elif earned > 0:
        note = (
            f"\n<blockquote>✨ <b>{sc('interest credited')} :</b> "
            f"<b>+{fmt(earned)}</b> "
            f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji></blockquote>\n"
        )
    else:
        note = ""

    text = (
        f"<tg-emoji emoji-id=\"5264895611517300926\">🏦</tg-emoji> "
        f"<b>{sc('bank of aunty')}</b> "
        f"<tg-emoji emoji-id=\"5264895611517300926\">🏦</tg-emoji>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"5217822164362739968\">👑</tg-emoji> "
        f"<b>{sc('account')} :</b> {user.mention_html()}\n"
        f"<tg-emoji emoji-id=\"6093857216274635770\">🔖</tg-emoji> "
        f"<b>{sc('id')} :</b> <code>{user.id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"6093755816391745206\">📊</tg-emoji> "
        f"<b>{sc('account summary')}</b>\n"
        f"├ <b>{sc('wallet')} :</b> "
        f"<b><tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji> {fmt(wallet)}</b>\n"
        f"├ <b>{sc('bank balance')} :</b> "
        f"<b><tg-emoji emoji-id=\"5264895611517300926\">🏦</tg-emoji> {fmt(bank)}</b>\n"
        f"├ <b>{sc('daily income')} :</b> <b>+{fmt(daily)}</b> <i>(4%)</i>\n"
        f"└ <b>{sc('next interest')} :</b> <code>{hh:02d}h {mm:02d}m {ss:02d}s</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<tg-emoji emoji-id=\"6093601953483334318\">✨</tg-emoji> "
        f"<b>{sc('lifetime stats')}</b>\n"
        f"├ <b>{sc('total deposited')} :</b> <b>{fmt(total_d)}</b>\n"
        f"├ <b>{sc('total withdrawn')} :</b> <b>{fmt(total_w)}</b>\n"
        f"└ <b>{sc('total interest earned')} :</b> <b>{fmt(total_i)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{note}"
        f"<i><b>{sc('deposit now and earn 4% daily interest!')}</b></i>"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("ᴅᴇᴘᴏsɪᴛ", callback_data="bk_dep",
                                 icon_custom_emoji_id="5472030678633684592"),
            InlineKeyboardButton("ᴡɪᴛʜᴅʀᴀᴡ", callback_data="bk_wd",
                                 icon_custom_emoji_id="5264895611517300926"),
        ],
        [
            InlineKeyboardButton("ʀᴜʟᴇs", callback_data="bk_rules",
                                 icon_custom_emoji_id="6093434630147415641"),
            InlineKeyboardButton("ᴛᴏᴘ ʙᴀɴᴋᴇʀs", callback_data="bk_top",
                                 icon_custom_emoji_id="6093755816391745206"),
        ],
        [
            InlineKeyboardButton("⟳", callback_data="bk_refresh"),
            InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="bk_close"),
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
        f"<b>{sc('wallet balance')} :</b> <b>{fmt(wallet)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>{sc('choose quick amount below')}</b>\n"
        f"<b>{sc('or use')}</b> <code>/deposit &lt;amount&gt;</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>{sc('minimum deposit')} : {MIN_DEPOSIT}</i>"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("500", callback_data="bk_dp_500"),
            InlineKeyboardButton("1,000", callback_data="bk_dp_1000"),
            InlineKeyboardButton("5,000", callback_data="bk_dp_5000"),
        ],
        [
            InlineKeyboardButton("10,000", callback_data="bk_dp_10000"),
            InlineKeyboardButton("50,000", callback_data="bk_dp_50000"),
            InlineKeyboardButton("ᴀʟʟ-ɪɴ", callback_data="bk_dp_all"),
        ],
        [InlineKeyboardButton("≼ ʙᴀᴄᴋ", callback_data="bk_refresh")],
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
        f"<b>{sc('bank balance')} :</b> <b>{fmt(bank)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>{sc('choose quick amount below')}</b>\n"
        f"<b>{sc('or use')}</b> <code>/withdraw &lt;amount&gt;</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>{sc('minimum withdraw')} : {MIN_WITHDRAW}</i>"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("500", callback_data="bk_wd_500"),
            InlineKeyboardButton("1,000", callback_data="bk_wd_1000"),
            InlineKeyboardButton("5,000", callback_data="bk_wd_5000"),
        ],
        [
            InlineKeyboardButton("10,000", callback_data="bk_wd_10000"),
            InlineKeyboardButton("ᴀʟʟ", callback_data="bk_wd_all"),
        ],
        [InlineKeyboardButton("≼ ʙᴀᴄᴋ", callback_data="bk_refresh")],
    ])
    await send_or_edit(update, context, text, kb, edit)


# ============================================================
# 📜 Bank Rules Page
# ============================================================
async def bank_rules(update, context, edit=False):
    text = (
        f"<tg-emoji emoji-id=\"6093434630147415641\">🃏</tg-emoji> "
        f"<b>{sc('bank of aunty — rules')}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>1.</b> {sc('minimum deposit')} : <b>{MIN_DEPOSIT}</b>\n"
        f"<b>2.</b> {sc('minimum withdraw')} : <b>{MIN_WITHDRAW}</b>\n"
        f"<b>3.</b> {sc('daily interest')} : <b>4%</b>\n"
        f"<b>4.</b> {sc('interest compounds every 24 hours')}\n"
        f"<b>5.</b> {sc('withdraw anytime without any penalty')}\n"
        f"<b>6.</b> {sc('interest is credited automatically when you open the bank or make a transaction')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>{sc('deposit today, grow your wealth every single day!')}</i>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("≼ ʙᴀᴄᴋ", callback_data="bk_refresh")]])
    await send_or_edit(update, context, text, kb, edit)


# ============================================================
# 🏆 Top Bankers Leaderboard
# ============================================================
async def fetch_top_bankers():
    data = await eco_collection.find({'bank_balance': {'$gt': 0}}).to_list(length=10000)
    return sorted(data, key=lambda x: bank_balance(x), reverse=True)[:10]


async def top_bankers(update, context, edit=False):
    data = await fetch_top_bankers()
    if not data:
        text = (
            f"<tg-emoji emoji-id=\"6093755816391745206\">📊</tg-emoji> "
            f"<b>{sc('top 10 bankers')}</b>\n\n"
            f"<b>{sc('no bankers yet. be the first!')}</b>"
        )
    else:
        rows = []
        for i, u in enumerate(data, 1):
            uid = u.get('id') or u.get('user_id') or u.get('_id', 0)
            try:
                uid_int = int(uid)
            except Exception:
                uid_int = uid
            name = u.get('first_name', 'Unknown')
            try:
                link = mention_html(uid_int, name)
            except Exception:
                link = escape(str(name))
            bal = bank_balance(u)
            rows.append(
                f"<b>{i}. {link} — "
                f"<tg-emoji emoji-id=\"5264895611517300926\">🏦</tg-emoji> "
                f"{fmt(bal)}</b>"
            )
        text = (
            f"<tg-emoji emoji-id=\"6093755816391745206\">📊</tg-emoji> "
            f"<b>{sc('top 10 bankers')}</b> "
            f"<tg-emoji emoji-id=\"6093755816391745206\">📊</tg-emoji>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            + "\n".join(rows)
        )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("≼ ʙᴀᴄᴋ", callback_data="bk_refresh")]])
    await send_or_edit(update, context, text, kb, edit)


# ============================================================
# 📥 Command Handlers
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
            f"<b>ɪɴᴠᴀʟɪᴅ ᴀᴍᴏᴜɴᴛ.</b>\n"
            f"<b>ᴜsᴀɢᴇ :</b> <code>/deposit &lt;amount&gt;</code>",
            parse_mode='HTML'
        )

    if amount < MIN_DEPOSIT:
        return await update.message.reply_text(
            f"<b>{sc('minimum deposit is')} {MIN_DEPOSIT}.</b>",
            parse_mode='HTML'
        )

    res = await deposit_coins(update.effective_user.id, amount)
    if not res['ok']:
        if res['reason'] == 'no_account':
            return await update.message.reply_text(
                f"<b>{sc('please start the bot first!')}</b>",
                parse_mode='HTML'
            )
        if res['reason'] == 'insufficient':
            return await update.message.reply_text(
                f"<b>{sc('insufficient wallet balance')} :</b> "
                f"<b>{fmt(res.get('wallet', 0))}</b>",
                parse_mode='HTML'
            )

    notice = (
        f"✅ <b>{sc('deposit successful')}</b>\n"
        f"<b>{sc('deposited')} :</b> <b>+{fmt(amount)}</b> "
        f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>"
    )
    await bank_page(update, context, edit=False, notice=notice)


async def withdraw_cmd(update, context):
    if not context.args:
        return await withdraw_menu(update, context, edit=False)

    raw = context.args[0].replace(",", "").replace("_", "").strip()
    try:
        amount = int(raw)
    except Exception:
        return await update.message.reply_text(
            f"<b>ɪɴᴠᴀʟɪᴅ ᴀᴍᴏᴜɴᴛ.</b>\n"
            f"<b>ᴜsᴀɢᴇ :</b> <code>/withdraw &lt;amount&gt;</code>",
            parse_mode='HTML'
        )

    if amount < MIN_WITHDRAW:
        return await update.message.reply_text(
            f"<b>{sc('minimum withdraw is')} {MIN_WITHDRAW}.</b>",
            parse_mode='HTML'
        )

    res = await withdraw_coins(update.effective_user.id, amount)
    if not res['ok']:
        if res['reason'] == 'no_account':
            return await update.message.reply_text(
                f"<b>{sc('please start the bot first!')}</b>",
                parse_mode='HTML'
            )
        if res['reason'] == 'insufficient_bank':
            return await update.message.reply_text(
                f"<b>{sc('insufficient bank balance')} :</b> "
                f"<b>{fmt(res.get('bank', 0))}</b>",
                parse_mode='HTML'
            )

    notice = (
        f"✅ <b>{sc('withdraw successful')}</b>\n"
        f"<b>{sc('withdrawn')} :</b> <b>+{fmt(amount)}</b> "
        f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>"
    )
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
# 🔀 Callback Router
# ============================================================
async def bank_callback(update: Update, context: CallbackContext):
    q = update.callback_query
    data = q.data
    user = update.effective_user

    if data == "bk_close":
        await q.answer()
        try:
            await q.message.delete()
        except Exception:
            pass
        return

    if data == "bk_refresh":
        await q.answer(sc("refreshed"))
        await bank_page(update, context, edit=True)
        return

    if data == "bk_dep":
        await q.answer()
        await deposit_menu(update, context, edit=True)
        return

    if data == "bk_wd":
        await q.answer()
        await withdraw_menu(update, context, edit=True)
        return

    if data == "bk_rules":
        await q.answer()
        await bank_rules(update, context, edit=True)
        return

    if data == "bk_top":
        await q.answer()
        await top_bankers(update, context, edit=True)
        return

    # ---------- Quick Deposit ----------
    if data.startswith("bk_dp_"):
        val = data.replace("bk_dp_", "")
        if val == "all":
            doc = await eco_collection.find_one({'id': user.id})
            amount = extract_balance(doc) if doc else 0
        else:
            try:
                amount = int(val)
            except Exception:
                return await q.answer()

        if amount < MIN_DEPOSIT:
            return await q.answer(
                sc(f"minimum deposit is {MIN_DEPOSIT}"),
                show_alert=True
            )

        res = await deposit_coins(user.id, amount)
        if not res['ok']:
            return await q.answer(sc("insufficient wallet balance"), show_alert=True)

        await q.answer(sc("deposited successfully"))
        notice = (
            f"✅ <b>{sc('deposit successful')}</b>\n"
            f"<b>{sc('deposited')} :</b> <b>+{fmt(amount)}</b> "
            f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>"
        )
        await bank_page(update, context, edit=True, notice=notice)
        return

    # ---------- Quick Withdraw ----------
    if data.startswith("bk_wd_"):
        val = data.replace("bk_wd_", "")
        await settle_interest(user.id)
        doc = await eco_collection.find_one({'id': user.id})

        if val == "all":
            amount = bank_balance(doc) if doc else 0
        else:
            try:
                amount = int(val)
            except Exception:
                return await q.answer()

        if amount < MIN_WITHDRAW:
            return await q.answer(
                sc(f"minimum withdraw is {MIN_WITHDRAW}"),
                show_alert=True
            )

        res = await withdraw_coins(user.id, amount)
        if not res['ok']:
            return await q.answer(sc("insufficient bank balance"), show_alert=True)

        await q.answer(sc("withdrawn successfully"))
        notice = (
            f"✅ <b>{sc('withdraw successful')}</b>\n"
            f"<b>{sc('withdrawn')} :</b> <b>+{fmt(amount)}</b> "
            f"<tg-emoji emoji-id=\"5472030678633684592\">💸</tg-emoji>"
        )
        await bank_page(update, context, edit=True, notice=notice)
        return


# ============================================================
# 📌 Register Handlers
# ============================================================
application.add_handler(CommandHandler(['bank', 'aunty', 'boa'], bank_cmd, block=False))
application.add_handler(CommandHandler('deposit', deposit_cmd, block=False))
application.add_handler(CommandHandler('withdraw', withdraw_cmd, block=False))
application.add_handler(CommandHandler('bankrules', bank_rules_cmd, block=False))
application.add_handler(CommandHandler('banktop', banktop_cmd, block=False))
application.add_handler(CallbackQueryHandler(bank_callback, pattern="^bk_", block=False))
application.add_handler(MessageHandler(
    filters.TEXT & ~filters.COMMAND & filters.Regex(r"(?i)^\s*bank[\s_]*of[\s_]*aunty\s*$"),
    bank_text_trigger,
    block=False
))

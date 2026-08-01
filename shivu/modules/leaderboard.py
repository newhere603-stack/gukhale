# ---------- Helper Functions for Upgraded Profile ----------

def get_rank_badge(rank: int) -> str:
    """Returns cool trophy badges based on rank."""
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
    """Generates a stylish progress bar."""
    if total <= 0:
        return "░" * length
    percentage = min(1.0, current / total)
    filled = int(round(length * percentage))
    return "█" * filled + "░" * (length - filled)


# ---------- Upgraded My Profile ----------

async def my_profile(update: Update, context: CallbackContext, edit=False):
    user_id = update.effective_user.id
    user = await user_collection.find_one(get_user_id_query(user_id))

    if not user:
        text = (
            f"🏆 <b>{sc('profile not found')}</b> 🏆\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>❌ {sc('you havent collected any characters yet!')}</b>\n"
            f"<b>🌱 {sc('start guessing characters in groups to build your profile.')}</b>"
        )
        return await send_or_edit(update, context, text, back_close_buttons("lb_profile"), edit)

    # Character Data & Calculation
    characters = user.get('characters', [])
    char_count = len(characters)
    
    # Balance & Tokens Data
    balance = get_balance_from_doc(user)
    tokens = user.get('tokens', 0)

    # Total characters in system for Progress Bar
    # (Assuming total characters count or default estimate if not tracked)
    total_db_chars = await user_collection.aggregate([
        {"$unwind": "$characters"},
        {"$group": {"_id": "$characters.id"}}
    ]).to_list(None)
    
    # Fallback to at least total characters or char_count for safety
    total_available_chars = max(len(total_db_chars) if total_db_chars else 100, char_count, 1)
    completion_pct = round((char_count / total_available_chars) * 100, 1)
    progress_bar = generate_progress_bar(char_count, total_available_chars)

    # Ranking System Calculation
    better_than = await user_collection.count_documents({
        "characters": {"$exists": True, "$type": "array"},
        "$expr": {"$gt": [{"$size": "$characters"}, char_count]}
    })
    total_collectors = await user_collection.count_documents({
        "characters": {"$exists": True, "$type": "array"}
    })
    rank = better_than + 1
    badge = get_rank_badge(rank)

    # User Mention
    link = update.effective_user.mention_html()

    # Dynamic Card UI Formatting
    text = (
        f"✨ <b>{sc('user profile')}</b> ✨\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{sc('collector')} :</b> {link}\n"
        f"🆔 <b>{sc('id')} :</b> <code>{user_id}</code>\n"
        f"🏷️ <b>{sc('badge')} :</b> <b>{badge}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>{sc('collection stats')}</b>\n"
        f"├ <b>{sc('rank')} :</b> <b>#{rank:,}</b> / <b>{total_collectors:,}</b>\n"
        f"├ <b>{sc('cards')} :</b> <b>{char_count:,}</b> 🎴\n"
        f"└ <b>{sc('progress')} :</b> [<code>{progress_bar}</code>] <b>{completion_pct}%</b>\n\n"
        f"💰 <b>{sc('vault & wallet')}</b>\n"
        f"├ <b>{sc('balance')} :</b> <b>💸 {balance:,}</b>\n"
        f"└ <b>{sc('tokens')} :</b> <b>💠 {tokens:,}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i><b>🔥 {sc('keep collecting to reach top 10!')}</b></i>"
    )

    # Custom Upgraded Buttons
    profile_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎴 ᴄ-ᴛᴏᴘ", callback_data="lb_chars"),
            InlineKeyboardButton("💸 ʙ-ᴛᴏᴘ", callback_data="lb_bal")
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

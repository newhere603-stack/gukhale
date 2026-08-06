from pymongo import ReturnDocument
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
from shivu import application, OWNER_ID, user_totals_collection, LOGGER

async def change_time(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    chat = update.effective_chat

    try:
        if chat.type not in ['group', 'supergroup']:
            await update.message.reply_text('<b><tg-emoji emoji-id="5420323339723881652">⚠️</tg-emoji> ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴄᴀɴ ᴏɴʟʏ ʙᴇ ᴜsᴇᴅ ɪɴ ɢʀᴏᴜᴘs.</b>', parse_mode='HTML')
            return

        try:
            member = await chat.get_member(user.id)
            if member.status not in ('administrator', 'creator'):
                await update.message.reply_text('<b><tg-emoji emoji-id="6093383288108360854">❌</tg-emoji> ʏᴏᴜ ᴅᴏ ɴᴏᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ. ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴄʜᴀɴɢᴇ sᴘᴀᴡɴ ғʀᴇǫᴜᴇɴᴄʏ.</b>', parse_mode='HTML')
                return
        except Exception as e:
            LOGGER.error(f"Error checking admin status: {e}")
            await update.message.reply_text('<b><tg-emoji emoji-id="6093383288108360854">❌</tg-emoji> ғᴀɪʟᴇᴅ ᴛᴏ ᴠᴇʀɪғʏ ʏᴏᴜʀ ᴀᴅᴍɪɴ sᴛᴀᴛᴜs. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.</b>', parse_mode='HTML')
            return

        args = context.args
        if len(args) != 1:
            await update.message.reply_text('<b><tg-emoji emoji-id="5422439311196834318">💡</tg-emoji> ɪɴᴄᴏʀʀᴇᴄᴛ ғᴏʀᴍᴀᴛ. ᴘʟᴇᴀsᴇ ᴜsᴇ: /changetime ɴᴜᴍʙᴇʀ\n\nᴇxᴀᴍᴘʟᴇ: /changetime 100</b>', parse_mode='HTML')
            return

        try:
            new_frequency = int(args[0])
        except ValueError:
            await update.message.reply_text('<b><tg-emoji emoji-id="6093383288108360854">❌</tg-emoji> ɪɴᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ. ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɪɴᴛᴇɢᴇʀ.</b>', parse_mode='HTML')
            return

        if new_frequency < 50 or new_frequency > 500:
            await update.message.reply_text('<b><tg-emoji emoji-id="5420323339723881652">⚠️</tg-emoji> ғʀᴇǫᴜᴇɴᴄʏ ᴍᴜsᴛ ʙᴇ ʙᴇᴛᴡᴇᴇ 50 ᴀɴᴅ 500 ғᴏʀ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴs.</b>', parse_mode='HTML')
            return

        await user_totals_collection.find_one_and_update(
            {'chat_id': str(chat.id)},
            {'$set': {'message_frequency': new_frequency}},
            upsert=True,
            return_document=ReturnDocument.AFTER
        )

        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="6118405866359103466">✅</tg-emoji> sᴜᴄᴄᴇssғᴜʟʟʏ ᴄʜᴀɴɢᴇᴅ sᴘᴀᴡɴ ғʀᴇǫᴜᴇɴᴄʏ ᴛᴏ ᴇᴠᴇʀʏ {new_frequency} ᴍᴇssᴀɢᴇs.</b>',
            parse_mode='HTML'
        )
        LOGGER.info(f"Changed spawn frequency for chat {chat.id} to {new_frequency}")

    except Exception as e:
        LOGGER.error(f"Error in change_time: {e}")
        await update.message.reply_text('<b><tg-emoji emoji-id="6093383288108360854">❌</tg-emoji> ғᴀɪʟᴇᴅ ᴛᴏ ᴄʜᴀɴɢᴇ ᴄʜᴀʀᴀᴄᴛᴇʀ sᴘᴀᴡɴ ғʀᴇǫᴜᴇɴᴄʏ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.</b>', parse_mode='HTML')


async def change_time_sudo(update: Update, context: CallbackContext) -> None:
    sudo_user_ids = {7657218453, OWNER_ID}
    user = update.effective_user

    try:
        # --- SILENT FAIL FOR NORMAL USERS ---
        if user.id not in sudo_user_ids:
            return

        if update.effective_chat.type not in ['group', 'supergroup']:
            await update.message.reply_text('<b><tg-emoji emoji-id="5420323339723881652">⚠️</tg-emoji> ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴄᴀɴ ᴏɴʟʏ ʙᴇ ᴜsᴇᴅ ɪɴ ɢʀᴏᴜᴘs.</b>', parse_mode='HTML')
            return

        args = context.args
        if len(args) != 1:
            await update.message.reply_text('<b><tg-emoji emoji-id="5422439311196834318">💡</tg-emoji> ɪɴᴄᴏʀʀᴇᴄᴛ ғᴏʀᴍᴀᴛ. ᴘʟᴇᴀsᴇ ᴜsᴇ: /ctime ɴᴜᴍʙᴇʀ\n\nᴇxᴀᴍᴘʟᴇ: /ctime 50</b>', parse_mode='HTML')
            return

        try:
            new_frequency = int(args[0])
        except ValueError:
            await update.message.reply_text('<b><tg-emoji emoji-id="6093383288108360854">❌</tg-emoji> ɪɴᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ. ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɪɴᴛᴇɢᴇʀ.</b>', parse_mode='HTML')
            return

        if new_frequency < 5 or new_frequency > 500:
            await update.message.reply_text('<b><tg-emoji emoji-id="5420323339723881652">⚠️</tg-emoji> ғʀᴇǫᴜᴇɴᴄʏ ᴍᴜsᴛ ʙᴇ ʙᴇᴛᴡᴇᴇ 5 ᴀɴᴅ 500 ғᴏʀ ʙᴏᴛ ᴏᴡɴᴇʀs.</b>', parse_mode='HTML')
            return

        await user_totals_collection.find_one_and_update(
            {'chat_id': str(update.effective_chat.id)},
            {'$set': {'message_frequency': new_frequency}},
            upsert=True,
            return_document=ReturnDocument.AFTER
        )

        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="6118405866359103466">✅</tg-emoji> sᴜᴄᴄᴇssғᴜʟʟʏ ᴄʜᴀɴɢᴇᴅ sᴘᴀᴡɴ ғʀᴇǫᴜᴇɴᴄʏ ᴛᴏ ᴇᴠᴇʀʏ {new_frequency} ᴍᴇssᴀɢᴇs.</b>',
            parse_mode='HTML'
        )
        LOGGER.info(f"[SUDO] Changed spawn frequency for chat {update.effective_chat.id} to {new_frequency} by user {user.id}")

    except Exception as e:
        LOGGER.error(f"Error in change_time_sudo: {e}")
        await update.message.reply_text('<b><tg-emoji emoji-id="6093383288108360854">❌</tg-emoji> ғᴀɪʟᴇᴅ ᴛᴏ ᴄʜᴀɴɢᴇ ᴄʜᴀʀᴀᴄᴛᴇʀ sᴘᴀᴡɴ ғʀᴇǫᴜᴇɴᴄʏ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.</b>', parse_mode='HTML')


async def check_frequency(update: Update, context: CallbackContext) -> None:
    try:
        chat_id = str(update.effective_chat.id)
        chat_frequency = await user_totals_collection.find_one({'chat_id': chat_id})

        if chat_frequency and 'message_frequency' in chat_frequency:
            freq = chat_frequency['message_frequency']
            await update.message.reply_text(
                f'<b><tg-emoji emoji-id="6314169895890199228">📊</tg-emoji> ᴄᴜʀʀᴇɴᴛ sᴘᴀᴡɴ ғʀᴇǫᴜᴇɴᴄʏ: ᴇᴠᴇʀʏ {freq} ᴍᴇssᴀɢᴇs\n\nᴜsᴇ /changetime ɴᴜᴍʙᴇʀ ᴛᴏ ᴄʜᴀɴɢᴇ ɪᴛ (ᴀᴅᴍɪɴ ᴏɴʟʏ)</b>',
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                '<b><tg-emoji emoji-id="6314169895890199228">📊</tg-emoji> ᴄᴜʀʀᴇɴᴛ sᴘᴀᴡɴ ғʀᴇǫᴜᴇɴᴄʏ: ᴇᴠᴇʀʏ 100 ᴍᴇssᴀɢᴇs (ᴅᴇғᴀᴜʟᴛ)\n\nᴜsᴇ /changetime ɴᴜᴍʙᴇʀ ᴛᴏ sᴇᴛ ᴀ ᴄᴜsᴛᴏᴍ ғʀᴇǫᴜᴇɴᴄʏ (ᴀᴅᴍɪɴ ᴏɴʟʏ)</b>',
                parse_mode='HTML'
            )

    except Exception as e:
        LOGGER.error(f"Error in check_frequency: {e}")
        await update.message.reply_text('<b><tg-emoji emoji-id="6093383288108360854">❌</tg-emoji> ғᴀɪʟᴇᴅ ᴛᴏ ᴄʜᴇᴄᴋ ғʀᴇǫᴜᴇɴᴄʏ.</b>', parse_mode='HTML')


async def force_spawn(update: Update, context: CallbackContext) -> None:
    sudo_user_ids = {7657218453, OWNER_ID}
    user = update.effective_user

    # --- SILENT FAIL FOR NORMAL USERS ---
    if user.id not in sudo_user_ids:
        return

    try:
        from shivu.__main__ import send_image
    except ImportError:
        try:
            from shivu.main import send_image
        except ImportError:
            await update.message.reply_text('<b><tg-emoji emoji-id="6093383288108360854">❌</tg-emoji> ᴄᴏᴜʟᴅ ɴᴏᴛ ᴀᴄᴄᴇss sᴘᴀᴡɴ ғᴜɴᴄᴛɪᴏɴ.</b>', parse_mode='HTML')
            return

    try:
        await update.message.reply_text('<b><tg-emoji emoji-id="6055198348787324579">🎲</tg-emoji> sᴘᴀᴡɴɪɴɢ ᴄʜᴀʀᴀᴄᴛᴇʀ...</b>', parse_mode='HTML')
        await send_image(update, context)
    except Exception as e:
        LOGGER.error(f"Error in force_spawn: {e}")
        await update.message.reply_text('<b><tg-emoji emoji-id="6093383288108360854">❌</tg-emoji> ғᴀɪʟᴇᴅ ᴛᴏ sᴘᴀᴡɴ ᴄʜᴀʀᴀᴄᴛᴇʀ.</b>', parse_mode='HTML')


async def reset_message_count(update: Update, context: CallbackContext) -> None:
    sudo_user_ids = {7657218453, OWNER_ID}
    user = update.effective_user

    # --- SILENT FAIL FOR NORMAL USERS ---
    if user.id not in sudo_user_ids:
        return

    try:
        from shivu.__main__ import message_counts
    except ImportError:
        try:
            from shivu.main import message_counts
        except ImportError:
            await update.message.reply_text('<b><tg-emoji emoji-id="6093383288108360854">❌</tg-emoji> ᴄᴏᴜʟᴅ ɴᴏᴛ ᴀᴄᴄᴇss ᴍᴇssᴀɢᴇ ᴄᴏᴜɴᴛᴇʀ.</b>', parse_mode='HTML')
            return

    try:
        chat_id = str(update.effective_chat.id)
        message_counts[chat_id] = 0
        await update.message.reply_text('<b><tg-emoji emoji-id="6118405866359103466">✅</tg-emoji> ᴍᴇssᴀɢᴇ ᴄᴏᴜɴᴛᴇʀ ʀᴇsᴇᴛ ᴛᴏ 0!</b>', parse_mode='HTML')
    except Exception as e:
        LOGGER.error(f"Error in reset_message_count: {e}")
        await update.message.reply_text('<b><tg-emoji emoji-id="6093383288108360854">❌</tg-emoji> ғᴀɪʟᴇᴅ ᴛᴏ ʀᴇsᴇᴛ ᴄᴏᴜɴᴛᴇʀ.</b>', parse_mode='HTML')


# Register handlers
application.add_handler(CommandHandler("ctime", change_time_sudo, block=False))
application.add_handler(CommandHandler("changetime", change_time, block=False))
application.add_handler(CommandHandler("frequency", check_frequency, block=False))
application.add_handler(CommandHandler("freq", check_frequency, block=False))
application.add_handler(CommandHandler("spawn", force_spawn, block=False))
application.add_handler(CommandHandler("fspawn", force_spawn, block=False))
application.add_handler(CommandHandler("resetcount", reset_message_count, block=False))

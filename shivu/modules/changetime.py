from pymongo import ReturnDocument
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
from shivu import application, OWNER_ID, user_totals_collection, LOGGER

async def change_time(update: Update, context: CallbackContext) -> None:
    """Group Admins ke liye command (/changetime)"""
    user = update.effective_user
    chat = update.effective_chat

    try:
        if chat.type not in ['group', 'supergroup']:
            await update.message.reply_text('This command can only be used in groups.')
            return

        # Check if user is admin or creator
        try:
            member = await chat.get_member(user.id)
            if member.status not in ('administrator', 'creator'):
                await update.message.reply_text('You do not have permission to use this command. Only admins can change spawn frequency.')
                return
        except Exception as e:
            LOGGER.error(f"Error checking admin status: {e}")
            await update.message.reply_text('Failed to verify your admin status. Please try again.')
            return

        args = context.args
        if len(args) != 1:
            await update.message.reply_text('Incorrect format. Please use: /changetime NUMBER\n\nExample: /changetime 100')
            return

        try:
            new_frequency = int(args[0])
        except ValueError:
            await update.message.reply_text('Invalid number. Please provide a valid integer.')
            return

        # Group Admin Limits: 50 se 500 tak
        if new_frequency < 50 or new_frequency > 500:
            await update.message.reply_text('Group Admins ke liye message frequency 50 se 500 ke beech honi chahiye.')
            return

        # Update database
        await user_totals_collection.find_one_and_update(
            {'chat_id': str(chat.id)},
            {'$set': {'message_frequency': new_frequency}},
            upsert=True,
            return_document=ReturnDocument.AFTER
        )

        await update.message.reply_text(
            f'✅ Successfully changed character spawn frequency to every {new_frequency} messages.\n\n'
            f'Characters will now appear after every {new_frequency} messages in this group.'
        )
        LOGGER.info(f"Changed spawn frequency for chat {chat.id} to {new_frequency}")

    except Exception as e:
        LOGGER.error(f"Error in change_time: {e}")
        await update.message.reply_text('Failed to change character spawn frequency. Please try again later.')


async def change_time_sudo(update: Update, context: CallbackContext) -> None:
    """Bot Owner ke liye command (/ctime)"""
    sudo_user_ids = {7657218453, OWNER_ID} # Added OWNER_ID fallback just in case
    user = update.effective_user

    try:
        if user.id not in sudo_user_ids:
            await update.message.reply_text('You do not have permission to use this command.')
            return

        if update.effective_chat.type not in ['group', 'supergroup']:
            await update.message.reply_text('This command can only be used in groups.')
            return

        args = context.args
        if len(args) != 1:
            await update.message.reply_text('Incorrect format. Please use: /ctime NUMBER\n\nExample: /ctime 50')
            return

        try:
            new_frequency = int(args[0])
        except ValueError:
            await update.message.reply_text('Invalid number. Please provide a valid integer.')
            return

        # Bot Owner (Sudo) Limits: 5 se 500 tak
        if new_frequency < 5 or new_frequency > 500:
            await update.message.reply_text('Bot Owner ke liye message frequency 5 se 500 ke beech honi chahiye.')
            return

        # Update database
        await user_totals_collection.find_one_and_update(
            {'chat_id': str(update.effective_chat.id)},
            {'$set': {'message_frequency': new_frequency}},
            upsert=True,
            return_document=ReturnDocument.AFTER
        )

        await update.message.reply_text(
            f'✅ Successfully changed character spawn frequency to every {new_frequency} messages.\n\n'
            f'Characters will now appear after every {new_frequency} messages in this group.'
        )
        LOGGER.info(f"[SUDO] Changed spawn frequency for chat {update.effective_chat.id} to {new_frequency} by user {user.id}")

    except Exception as e:
        LOGGER.error(f"Error in change_time_sudo: {e}")
        await update.message.reply_text('Failed to change character spawn frequency. Please try again later.')


async def check_frequency(update: Update, context: CallbackContext) -> None:
    try:
        chat_id = str(update.effective_chat.id)
        chat_frequency = await user_totals_collection.find_one({'chat_id': chat_id})

        if chat_frequency and 'message_frequency' in chat_frequency:
            freq = chat_frequency['message_frequency']
            await update.message.reply_text(
                f'📊 Current spawn frequency: Every {freq} messages\n\n'
                f'Use /changetime NUMBER to change it (admin only)'
            )
        else:
            await update.message.reply_text(
                f'📊 Current spawn frequency: Every 100 messages (default)\n\n'
                f'Use /changetime NUMBER to set a custom frequency (admin only)'
            )

    except Exception as e:
        LOGGER.error(f"Error in check_frequency: {e}")
        await update.message.reply_text('Failed to check frequency.')


async def force_spawn(update: Update, context: CallbackContext) -> None:
    sudo_user_ids = {7657218453, OWNER_ID}
    user = update.effective_user

    if user.id not in sudo_user_ids:
        await update.message.reply_text('⛔ You do not have permission to use this command.')
        return

    # Dynamically import inside the function to avoid Circular Import Error
    try:
        from shivu.__main__ import send_image
    except ImportError:
        try:
            from shivu.main import send_image
        except ImportError:
            await update.message.reply_text('❌ Could not access spawn function.')
            return

    try:
        await update.message.reply_text('🎲 Spawning character...')
        await send_image(update, context)
    except Exception as e:
        LOGGER.error(f"Error in force_spawn: {e}")
        await update.message.reply_text('❌ Failed to spawn character.')


async def reset_message_count(update: Update, context: CallbackContext) -> None:
    sudo_user_ids = {7657218453, OWNER_ID}
    user = update.effective_user

    if user.id not in sudo_user_ids:
        await update.message.reply_text('⛔ You do not have permission to use this command.')
        return

    # Dynamically import message_counts
    try:
        from shivu.__main__ import message_counts
    except ImportError:
        try:
            from shivu.main import message_counts
        except ImportError:
            await update.message.reply_text('❌ Could not access message counter.')
            return

    try:
        chat_id = str(update.effective_chat.id)
        message_counts[chat_id] = 0
        await update.message.reply_text('✅ Message counter reset to 0!')
    except Exception as e:
        LOGGER.error(f"Error in reset_message_count: {e}")
        await update.message.reply_text('❌ Failed to reset counter.')


# Register handlers
application.add_handler(CommandHandler("ctime", change_time_sudo, block=False))
application.add_handler(CommandHandler("changetime", change_time, block=False))
application.add_handler(CommandHandler("frequency", check_frequency, block=False))
application.add_handler(CommandHandler("freq", check_frequency, block=False))
application.add_handler(CommandHandler("spawn", force_spawn, block=False))
application.add_handler(CommandHandler("fspawn", force_spawn, block=False))
application.add_handler(CommandHandler("resetcount", reset_message_count, block=False))

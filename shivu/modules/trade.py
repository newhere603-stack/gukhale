from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler
from shivu import shivuu as bot
from shivu import user_collection, application
import asyncio

pending_trades = {}

def mention_html(user_id, name):
    return f'<a href="tg://user?id={user_id}">{name}</a>'

async def handle_trade_command(update: Update, context: CallbackContext):
    message = update.message
    sender_id = message.from_user.id

    if not message.reply_to_message:
        await message.reply_html("<b>you need to reply to a user's message to trade a character!</b>")
        return

    receiver_id = message.reply_to_message.from_user.id
    if sender_id == receiver_id:
        await message.reply_html("<b>you can't trade a character with yourself!</b>")
        return

    if len(context.args) != 2:
        await message.reply_html("<b>you need to provide two character ids! (your_id their_id)</b>")
        return

    sender_character_id, receiver_character_id = context.args[0], context.args[1]

    sender = await user_collection.find_one({'id': sender_id})
    receiver = await user_collection.find_one({'id': receiver_id})

    # Ensure users exist and 'characters' is a list
    if not sender or not isinstance(sender.get('characters'), list):
        await message.reply_html("<b>your characters data is corrupted or not found!</b>")
        return
    if not receiver or not isinstance(receiver.get('characters'), list):
        await message.reply_html("<b>the other user's characters data is corrupted or not found!</b>")
        return

    sender_character = next((character for character in sender['characters'] if character['id'] == sender_character_id), None)
    receiver_character = next((character for character in receiver['characters'] if character['id'] == receiver_character_id), None)

    if not sender_character:
        await message.reply_html("<b>you don't have the character you're trying to trade!</b>")
        return
    if not receiver_character:
        await message.reply_html("<b>the other user doesn't have the character they're trying to trade!</b>")
        return

    if (sender_id, receiver_id) in pending_trades:
        await message.reply_html("<b>there is already a pending trade between you and this user.</b>")
        return

    pending_trades[(sender_id, receiver_id)] = {
        'sender_character_id': sender_character_id,
        'receiver_character_id': receiver_character_id
    }

    # Sender ID callback data mein bhej rahe hain taaki on_callback_query me easily identify ho
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Confirm ✅", callback_data=f"confirm_trade_{sender_id}")],
            [InlineKeyboardButton("Cancel ❌", callback_data=f"cancel_trade_{sender_id}")]
        ]
    )

    mention = mention_html(receiver_id, message.reply_to_message.from_user.first_name)
    await message.reply_html(f"<b>{mention}, do you accept this trade?</b>", reply_markup=keyboard)

async def on_callback_query(update: Update, context: CallbackContext):
    callback_query = update.callback_query
    receiver_id = callback_query.from_user.id
    data = callback_query.data

    # Check karna ki button trade ka hi hai na
    if not (data.startswith("confirm_trade_") or data.startswith("cancel_trade_")):
        return

    sender_id = int(data.split("_")[2])

    if (sender_id, receiver_id) not in pending_trades:
        await callback_query.answer("this trade is not for you or has expired!", show_alert=True)
        return

    trade_data = pending_trades[(sender_id, receiver_id)]

    if data.startswith("confirm_trade_"):
        sender = await user_collection.find_one({'id': sender_id})
        receiver = await user_collection.find_one({'id': receiver_id})

        sender_character_id = trade_data['sender_character_id']
        receiver_character_id = trade_data['receiver_character_id']

        # Ensure characters still exist before executing trade
        sender_character = next((char for char in sender.get('characters', []) if char['id'] == sender_character_id), None)
        receiver_character = next((char for char in receiver.get('characters', []) if char['id'] == receiver_character_id), None)

        if not sender_character or not receiver_character:
            await callback_query.message.edit_text("<b>one of the characters in the trade no longer exists!</b>", parse_mode='HTML')
            del pending_trades[(sender_id, receiver_id)]
            return

        # MongoDB ke $pull aur $push methods se fast and safe update
        await user_collection.update_one({'id': sender_id}, {'$pull': {'characters': {'id': sender_character_id}}})
        await user_collection.update_one({'id': receiver_id}, {'$pull': {'characters': {'id': receiver_character_id}}})

        await user_collection.update_one({'id': sender_id}, {'$push': {'characters': receiver_character}})
        await user_collection.update_one({'id': receiver_id}, {'$push': {'characters': sender_character}})

        del pending_trades[(sender_id, receiver_id)]

        await callback_query.message.edit_text("<b>🎁 you have successfully traded your character!</b>", parse_mode='HTML')

    elif data.startswith("cancel_trade_"):
        del pending_trades[(sender_id, receiver_id)]
        await callback_query.message.edit_text("<b>❌️ trade canceled.</b>", parse_mode='HTML')


application.add_handler(CommandHandler("trade", handle_trade_command, block=False))
# Pattern update kiya gaya hai taaki naye callback data (confirm_trade_12345) ko pakad sake
application.add_handler(CallbackQueryHandler(on_callback_query, pattern='^(confirm_trade_|cancel_trade_)', block=False))

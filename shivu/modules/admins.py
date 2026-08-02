from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from shivu import application, user_collection, db

OWNER_ID = 7657218453
SUDO_USERS = [7657218453]

def is_authorized(user_id):
    return user_id == OWNER_ID or user_id in SUDO_USERS

bot_settings_collection = db['bot_settings']

# Economy Fields
TOKEN_FIELD = 'balance'
COIN_FIELD = 'coins'

# --- Helper for adding/removing currency ---
async def modify_currency(update: Update, context: CallbackContext, field: str, currency_name: str, is_add: bool):
    try:
        requester_id = update.effective_user.id
        if not is_authorized(requester_id):
            return  # Normal users completely ignored
            
        target_id = None
        amount = None
        
        # Check if replying to a user
        if update.message.reply_to_message:
            target_id = update.message.reply_to_message.from_user.id
            if context.args:
                amount = context.args[0]
        else:
            # Command with user ID and amount
            if len(context.args) >= 2:
                target_id = context.args[0]
                amount = context.args[1]
                
        if target_id is None or amount is None:
            await update.message.reply_text(
                "<b>usage: /command userid amount or reply to user with /command amount</b>", 
                parse_mode='HTML'
            )
            return
            
        try:
            target_id = int(target_id)
            amount = int(amount)
        except ValueError:
            await update.message.reply_text("<b>invalid user id or amount.</b>", parse_mode='HTML')
            return
            
        # VERY IMPORTANT: Checking if user actually exists before updating.
        # Removed upsert=True to prevent creating broken database entries.
        user = await user_collection.find_one({'id': target_id})
        if not user:
            await update.message.reply_text("<b>user not found in database. they need to start the bot first.</b>", parse_mode='HTML')
            return

        if is_add:
            await user_collection.update_one({'id': target_id}, {'$inc': {field: amount}})
        else:
            current = user.get(field, 0)
            new_balance = max(0, current - amount)
            await user_collection.update_one({'id': target_id}, {'$set': {field: new_balance}})
            
        # Fetch updated balance
        user = await user_collection.find_one({'id': target_id})
        new_balance = user.get(field, 0)
        
        action = "added to" if is_add else "removed from"
        await update.message.reply_text(
            f"<b>success! {amount} {currency_name} {action} {target_id}. updated balance: {new_balance} {currency_name}.</b>",
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Currency command error: {e}")


# --- /destroy <user_id> OR Reply ---
async def destroy_cmd(update: Update, context: CallbackContext):
    try:
        requester_id = update.effective_user.id
        if not is_authorized(requester_id):
            return  # Normal users completely ignored

        target_id = None
        if update.message.reply_to_message:
            target_id = update.message.reply_to_message.from_user.id
        elif context.args:
            target_id = context.args[0]

        if not target_id:
            await update.message.reply_text("<b>usage: /destroy userid or reply to a user</b>", parse_mode='HTML')
            return

        try:
            target_id = int(target_id)
        except ValueError:
            await update.message.reply_text("<b>invalid user id.</b>", parse_mode='HTML')
            return

        user = await user_collection.find_one({'id': target_id})
        if not user:
            await update.message.reply_text("<b>user not found in database.</b>", parse_mode='HTML')
            return
            
        count = len(user.get('characters', []))

        await user_collection.update_one(
            {'id': target_id},
            {'$set': {'characters': []}}
        )

        await update.message.reply_text(
            f"<b>successfully destroyed {count} characters for user {target_id}</b>", 
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Destroy command error: {e}")


# --- /setded <percentage> ---
async def setded_cmd(update: Update, context: CallbackContext):
    try:
        requester_id = update.effective_user.id
        if not is_authorized(requester_id):
            return  # Normal users completely ignored

        if not context.args:
            await update.message.reply_text("<b>usage: /setded percentage</b>", parse_mode='HTML')
            return

        try:
            percentage = float(context.args[0])
        except ValueError:
            await update.message.reply_text("<b>invalid percentage.</b>", parse_mode='HTML')
            return

        await bot_settings_collection.update_one(
            {'_id': 'settings'},
            {'$set': {'deduction_percentage': percentage}},
            upsert=True
        )

        await update.message.reply_text(
            f"<b>deduction percentage set to {percentage:.1f}%</b>", 
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Setded command error: {e}")


# --- Economy Wrappers ---
async def tadd_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, TOKEN_FIELD, 'tokens', True)

async def cadd_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, COIN_FIELD, 'coins', True)

async def trem_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, TOKEN_FIELD, 'tokens', False)

async def crem_cmd(update: Update, context: CallbackContext):
    await modify_currency(update, context, COIN_FIELD, 'coins', False)


# Handlers registration
application.add_handler(CommandHandler(['destroy'], destroy_cmd, block=False))
application.add_handler(CommandHandler(['setded'], setded_cmd, block=False))
application.add_handler(CommandHandler(['tadd'], tadd_cmd, block=False))
application.add_handler(CommandHandler(['cadd'], cadd_cmd, block=False))
application.add_handler(CommandHandler(['trem'], trem_cmd, block=False))
application.add_handler(CommandHandler(['crem'], crem_cmd, block=False))

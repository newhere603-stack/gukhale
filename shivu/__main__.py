import asyncio
import traceback
import importlib

# 🔥 Super-Fast Engine Setup (No text/font changes)
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Yahan aapke main games import ho rahe hain
import shivu.modules.wordgrid
import wordle_game
import shivu.modules.chatlog

from telegram import Update
from telegram.ext import CallbackContext
from shivu import db, shivuu, application, LOGGER
from shivu.modules import ALL_MODULES

# 🔥 Economy DB sync ke liye
from shivu.Database.db import eco_collection

OWNER_ID = 7657218453
SUDO_USERS = [7657218453]

def is_authorized(user_id):
    return user_id == OWNER_ID or user_id in SUDO_USERS

# Sirf zaroori database collections ko rakha gaya hai
user_collection = db['user_collection_lmaoooo']
bot_settings_collection = db['bot_settings']
group_settings_collection = db['group_settings_db']


async def setup_database_indexes():
    """Sirf basic aur zaroori indexes create karega."""
    try:
        await user_collection.create_index("id", unique=True, background=True)
        await eco_collection.create_index("id", unique=True, background=True)
        LOGGER.info("⚡ Database Indexes Verified/Created Successfully!")
    except Exception as e:
        if "IndexKeySpecsConflict" not in str(e):
            LOGGER.error(f"Index creation failed: {e}")
        else:
            LOGGER.info("⚡ Existing database indexes verified successfully.")


# Saare modules yahan se dynamically load honge
for module_name in ALL_MODULES:
    try:
        importlib.import_module("shivu.modules." + module_name)
    except Exception:
        LOGGER.exception(f"Failed loading module {module_name}")


async def main():
    try:
        # Database setup run karna
        await setup_database_indexes()

        # Pyrogram client start karna
        await shivuu.start()

        # Application initialize aur start karna
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

        LOGGER.info("✅ ʙᴏᴛ sᴛᴀʀᴛᴇᴅ")

        # Bot start hone par restart log group mein bhejne ka code
        try:
            from shivu.modules.chatlog import send_log_to_group, create_log_message
            bot_info = await application.bot.get_me()
            data = {
                "Bot": f"<b>@{bot_info.username}</b>",
                "Status": "<b>Online & Ready <tg-emoji emoji-id=\"6093708348413189642\">⚡️</tg-emoji></b>"
            }
            log_msg = create_log_message("˹ Bot Restarted ˼ <tg-emoji emoji-id=\"6093679829830344586\">🔝</tg-emoji>", data)
            asyncio.create_task(send_log_to_group(log_msg))
        except Exception as e:
            LOGGER.error(f"Failed to queue startup log: {e}")

        # Bot ko infinite time tak online rakhna
        await asyncio.Event().wait()

    except Exception:
        LOGGER.exception("Bot crashed!")
        traceback.print_exc()

    finally:
        LOGGER.info("Stopping bot...")
        for coro in (application.updater.stop, application.stop, application.shutdown, shivuu.stop):
            try:
                await coro()
            except Exception:
                pass

if __name__ == "__main__":
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()

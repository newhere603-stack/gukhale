import asyncio
import traceback
import importlib
import logging
import os
import time
import wordle_game
import shivu.modules.wordgrid
# 🔥 Super-Fast Engine Setup
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

from telegram import Update
from telegram.ext import Application, PicklePersistence
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client

from shivu.config import Development as Config

# --- LOGGING SETUP ---
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()],
    level=logging.INFO,
)
logging.getLogger("apscheduler").setLevel(logging.ERROR)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger("pyrate_limiter").setLevel(logging.ERROR)
LOGGER = logging.getLogger(__name__)

# --- BOT CREDENTIALS ---
api_id = Config.api_id
api_hash = Config.api_hash
TOKEN = Config.TOKEN
mongo_url = Config.mongo_url 
OWNER_ID = Config.OWNER_ID 
SUDO_USERS = Config.sudo_users
LOG_GROUP_ID = "-1003893927065"

def is_authorized(user_id):
    return user_id == OWNER_ID or user_id in SUDO_USERS

# --- BOT INITIALIZATION ---
persistence = PicklePersistence(filepath="bot_persistence_data.pickle")
application = Application.builder().token(TOKEN).persistence(persistence).build()
shivuu = Client("Shivu", api_id=api_id, api_hash=api_hash, bot_token=TOKEN)

# ==========================================
# 🔥 DATABASE SETUP (Only Essential for Games)
# ==========================================
eco_client = AsyncIOMotorClient(
    mongo_url,
    maxPoolSize=200,
    minPoolSize=20,
    serverSelectionTimeoutMS=3000,
    connectTimeoutMS=5000,
    socketTimeoutMS=5000,
    waitQueueTimeoutMS=3000
)

# Tumhare games points ko yahan store karte hain
db = eco_client['Character_catcher']
eco_db = db 

user_collection = db["user_collection_lmaoooo"] 
eco_collection = db['economy_users'] 

# ==========================================
# 🎮 GAME MODULES ONLY
# ==========================================
# Yahan sirf tumhare dono games import ho rahe hain
import shivu.modules.wordgrid
import wordle_game 

# ==========================================
# 🚀 MAIN FUNCTION
# ==========================================
async def main():
    try:
        # Pyrogram client start (Agar modules mein pyrogram use hua ho toh)
        await shivuu.start()

        # Bot start
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

        LOGGER.info("✅ ʙᴏᴛ sᴛᴀʀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ ᴡɪᴛʜ ᴡᴏʀᴅɢʀɪᴅ & ᴡᴏʀᴅsᴇᴇᴋ ᴏɴʟʏ!")

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

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pyrogram import Client, filters
from pyrogram.types import Message, Chat, User
from pyrogram.errors import (
    PeerIdInvalid, BadRequest, FloodWait, 
    UserIsBlocked, ChatWriteForbidden
)
from shivu import user_collection, shivuu as app

# AAPKI LOG GROUP ID YAHAN FIX KAR DI GAYI HAI
LOG_GROUP_ID = -1003893927065

class AdvancedBotAnalytics:
    def __init__(self, max_cache_size: int = 500):
        self.stats = defaultdict(int)
        self.chat_cache = {}
        self.recent_events = deque(maxlen=100)
        self.max_cache_size = max_cache_size
        self.lock = asyncio.Lock()
        self.log_queue = asyncio.Queue(maxsize=100)
        self._processor_task = None
        self._started = False
        self._chat_cached = False
    
    async def increment(self, key: str):
        async with self.lock:
            self.stats[key] += 1
    
    async def add_event(self, event_type: str, data: Dict[str, Any]):
        event = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        async with self.lock:
            self.recent_events.append(event)
    
    async def cache_chat(self, chat_id: int, info: Dict[str, str]):
        async with self.lock:
            if len(self.chat_cache) >= self.max_cache_size:
                oldest = next(iter(self.chat_cache))
                del self.chat_cache[oldest]
            self.chat_cache[chat_id] = {
                **info,
                "cached_at": datetime.now().isoformat()
            }
    
    async def force_cache_log_group(self):
        """Ye function bina start kiye group ko forcefully yaad dilayega bot ko"""
        if self._chat_cached:
            return True
        try:
            print(f"🔄 Forcing cache for Log Group: {LOG_GROUP_ID}...")
            chat = await app.get_chat(LOG_GROUP_ID)
            print(f"✅ Log Group Cached Successfully: {chat.title}")
            self._chat_cached = True
            return True
        except PeerIdInvalid:
            print("⚠️ PeerIdInvalid: Group ko cache karne me dikkat ho rahi hai. (Admin rights check karein)")
            return False
        except Exception as e:
            print(f"⚠️ Cache Error: {e}")
            return False

    async def queue_log(self, text: str, priority: int = 5):
        await self.ensure_processor_started()
        try:
            await asyncio.wait_for(
                self.log_queue.put((priority, text)),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            print(f"⚠️ Log queue full, dropping message")
        except Exception as e:
            print(f"❌ Queue error: {e}")
    
    async def ensure_processor_started(self):
        if not self._started:
            print("⚡ Starting log processor...")
            self._started = True
            # Processor start hone par group cache zarur karega
            await self.force_cache_log_group()
            self._processor_task = asyncio.create_task(self._process_logs())
    
    async def _process_logs(self):
        batch = []
        batch_timeout = 2.0
        while True:
            try:
                priority, text = await asyncio.wait_for(
                    self.log_queue.get(),
                    timeout=batch_timeout
                )
                batch.append((priority, text))
                
                if len(batch) >= 5:
                    await self._send_batch(batch)
                    batch = []
                    
            except asyncio.TimeoutError:
                if batch:
                    await self._send_batch(batch)
                    batch = []
            except Exception as e:
                pass
    
    async def _send_batch(self, batch: List[tuple]):
        batch.sort(key=lambda x: x[0])
        # Force cache if not done
        await self.force_cache_log_group()
        
        tasks = [
            attempt_send(LOG_GROUP_ID, text, timeout=5)
            for _, text in batch
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

analytics = AdvancedBotAnalytics()

async def attempt_send(chat_id: int, text: str, timeout: int) -> bool:
    for attempt in range(2):
        try:
            await asyncio.wait_for(
                app.send_message(chat_id, text, disable_web_page_preview=True),
                timeout=timeout
            )
            return True
        except FloodWait as e:
            if attempt == 1: return False
            await asyncio.sleep(min(e.value, 3))
        except PeerIdInvalid:
            # Agar fail ho jaye toh ek baar fir forcefully cache try kare
            await app.get_chat(chat_id)
            if attempt == 1: return False
        except (UserIsBlocked, ChatWriteForbidden):
            return False
        except Exception as e:
            if attempt == 1: return False
            await asyncio.sleep(0.3)
    return False

def format_user_mention(user: Optional[User]) -> str:
    if not user:
        return "<b>ᴜɴᴋɴᴏᴡɴ</b>"
    return f"<b><a href='tg://user?id={user.id}'>{user.first_name}</a></b>"

def create_log_message(title: str, data: Dict[str, Any]) -> str:
    """Beautiful bold + small caps text designer"""
    timestamp = datetime.now().strftime("%I:%M %p • %d/%m/%y")
    base = f"<b>{title}</b>\n\n"
    
    items = list(data.items())
    for i, (key, value) in enumerate(items):
        prefix = "<b>╰</b>" if i == len(items) - 1 else "<b>├</b>"
        base += f"{prefix} <b>{key} :</b> {value}\n"
        
    base += f"\n<b>⌚ ᴛɪᴍᴇ :</b> <b>{timestamp}</b>"
    return base

async def get_user_stats() -> Dict[str, Any]:
    try:
        total = await asyncio.wait_for(user_collection.count_documents({}), timeout=1.5)
        return {"total_users": total}
    except Exception:
        return {"total_users": "N/A"}

async def get_chat_info(chat: Chat) -> Dict[str, str]:
    info = {
        "title": f"<b>{chat.title or 'Private'}</b>",
        "username": f"<b>@{chat.username}</b>" if chat.username else "<b>ᴘʀɪᴠᴀᴛᴇ</b>",
        "type": f"<b>{chat.type.value if hasattr(chat, 'type') else 'unknown'}</b>",
        "member_count": "<b>N/A</b>"
    }
    try:
        if hasattr(chat, 'members_count') and chat.members_count:
            info["member_count"] = f"<b>{chat.members_count}</b>"
        elif chat.type in ["group", "supergroup"]:
            count = await asyncio.wait_for(app.get_chat_members_count(chat.id), timeout=1.5)
            info["member_count"] = f"<b>{count}</b>"
    except Exception:
        pass
    return info

# --- ADMIN / SUDO ACTION LOG (Can be imported & used anywhere) ---
async def log_admin_action(action_name: str, admin_name: str, admin_id: int, details: Dict[str, Any]):
    try:
        data = {
            "ᴀᴅᴍɪɴ": f"<b><a href='tg://user?id={admin_id}'>{admin_name}</a></b>",
            "ɪᴅ": f"<code>{admin_id}</code>"
        }
        data.update({k: f"<b>{v}</b>" if not str(v).startswith("<") else v for k, v in details.items()})
        
        log = create_log_message(f"˹ ᴀᴅᴍɪɴ ᴀᴄᴛɪᴏɴ ˼ ⚡", data)
        await analytics.queue_log(log, priority=1)
    except Exception as e:
        print(f"❌ Error in log_admin_action: {e}")

# --- STARTUP LOG (Bot start by user) ---
async def track_bot_start(user_id: int, first_name: str, username: str, is_new: bool):
    try:
        await analytics.increment("bot_starts")
        if is_new:
            await analytics.increment("new_users")
        
        user_mention = f"<b><a href='tg://user?id={user_id}'>{first_name}</a></b>"
        username_str = f"<b>@{username}</b>" if username else "<b>ɴᴏ ᴜsᴇʀɴᴀᴍᴇ</b>"
        
        stats = await get_user_stats()
        status = f"<b>ɴᴇᴡ ᴜsᴇʀ #{stats['total_users']}</b>" if is_new else "<b>ʀᴇᴛᴜʀɴɪɴɢ ᴜsᴇʀ</b>"
        
        data = {
            "sᴛᴀᴛᴜs": status,
            "ᴜsᴇʀ": user_mention,
            "ɪᴅ": f"<code>{user_id}</code>",
            "ᴜsᴇʀɴᴀᴍᴇ": username_str
        }
        
        log = create_log_message("˹ ʙᴏᴛ sᴛᴀʀᴛᴇᴅ ˼ 🌸", data)
        await analytics.queue_log(log, priority=3 if is_new else 5)
        
    except Exception as e:
        pass

# --- NEW GROUP LOG ---
@app.on_message(filters.new_chat_members, group=1)
async def on_new_chat(client: Client, message: Message):
    try:
        bot = await client.get_me()
        if not any(u.id == bot.id for u in message.new_chat_members):
            return

        chat_info = await get_chat_info(message.chat)
        added_by = format_user_mention(message.from_user)
        
        data = {
            "ᴄʜᴀᴛ": chat_info['title'],
            "ɪᴅ": f"<code>{message.chat.id}</code>",
            "ᴜsᴇʀɴᴀᴍᴇ": chat_info['username'],
            "ᴍᴇᴍʙᴇʀs": chat_info['member_count'],
            "ᴀᴅᴅᴇᴅ ʙʏ": added_by
        }
        
        log = create_log_message("˹ ɢʀᴀʙʙɪɴɢ ʏᴏᴜʀ ᴡᴀɪғᴜ ˼ 🥀", data)
        await analytics.queue_log(log, priority=2)
    except Exception as e:
        print(f"❌ on_new_chat error: {e}")

# --- LEFT GROUP LOG ---
@app.on_message(filters.left_chat_member, group=1)
async def on_left_chat(client: Client, message: Message):
    try:
        bot = await client.get_me()
        if message.left_chat_member.id != bot.id:
            return

        chat_info = await get_chat_info(message.chat)
        removed_by = format_user_mention(message.from_user)
        
        data = {
            "ᴄʜᴀᴛ": chat_info['title'],
            "ɪᴅ": f"<code>{message.chat.id}</code>",
            "ᴜsᴇʀɴᴀᴍᴇ": chat_info['username'],
            "ʀᴇᴍᴏᴠᴇᴅ ʙʏ": removed_by
        }
        
        log = create_log_message("˹ ʟᴇғᴛ ɢʀᴏᴜᴘ ˼ ✫", data)
        await analytics.queue_log(log, priority=4)
        
    except Exception as e:
        print(f"❌ on_left_chat error: {e}")

import random
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, ContextTypes
from shivu import application, db

collection = db['anime_characters_lol']

RARITY_MAP = {
    1: "🟢 Common",
    2: "🟣 Rare",
    3: "🟡 Legendary", 
    4: "💮 Special Edition", 
    5: "💫 Neon",
    6: "✨ Manga", 
    7: "🎭 Cosplay",
    8: "🎐 Celestial",
    9: "🔮 Premium Edition",
    10: "💋 Erotic",
    11: "🌤 Summer",
    12: "☃️ Winter",
    13: "☔️ Monsoon",
    14: "💝 Valentine",
    15: "🎃 Halloween", 
    16: "🎄 Christmas",
    17: "🏵 Mythic",
    18: "🎗 Special Events",
    19: "🎥 AMV",
    20: "👼 Tiny"
}

# --- Universal Small Caps & Bold Converter ---
def to_small_caps(text: str) -> str:
    mapping = {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 
        'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 
        'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 
        's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 
        'y': 'ʏ', 'z': 'ᴢ',
        'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ꜰ', 
        'G': 'ɢ', 'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 
        'M': 'ᴍ', 'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'ǫ', 'R': 'ʀ', 
        'S': 'ꜱ', 'T': 'ᴛ', 'U': 'ᴜ', 'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x', 
        'Y': 'ʏ', 'Z': 'ᴢ'
    }
    # Text ko small caps mein badal kar bold tag lagata hai
    converted = "".join(mapping.get(c, c) for c in str(text))
    return f"<b>{converted}</b>"

async def rarity_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        args = context.args
        
        if not args:
            response = f"{to_small_caps('Rarity List')}\n\n"
            for num, name in RARITY_MAP.items():
                response += f"<code>{num}</code> → {to_small_caps(name)}\n"
            response += f"\n{to_small_caps('Usage: /r number')}\n{to_small_caps('Example: /r 1')}"
            await update.message.reply_text(response, parse_mode='HTML')
            return

        try:
            rarity_num = int(args[0])
        except ValueError:
            await update.message.reply_text(
                f"<blockquote>{to_small_caps('Please provide a valid rarity number (1-20)')}</blockquote>",
                parse_mode='HTML'
            )
            return

        if rarity_num not in RARITY_MAP:
            await update.message.reply_text(
                f"<blockquote>{to_small_caps('Invalid rarity. Use number between 1-20')}</blockquote>",
                parse_mode='HTML'
            )
            return

        rarity_name = RARITY_MAP[rarity_num]
        
        # Count with multiple formats
        count_string = await collection.count_documents({'rarity': rarity_name})
        count_number = await collection.count_documents({'rarity': rarity_num})
        emoji = rarity_name.split()[0]
        count_emoji = await collection.count_documents({'rarity': {'$regex': f'^{emoji}'}})
        
        total = max(count_string, count_number, count_emoji)
        
        response = f"<blockquote>{to_small_caps(rarity_name)}</blockquote>\n\n"
        response += f"{to_small_caps('Total Characters:')} <code>{total}</code>"
        
        await update.message.reply_text(response, parse_mode='HTML')

    except Exception as e:
        await update.message.reply_text(f"<blockquote>{to_small_caps(f'Error: {str(e)}') }</blockquote>", parse_mode='HTML')


# --- Marketplace Feature with Small Caps ---
async def marketplace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        pipeline = [{"$sample": {"size": 1}}]
        chars = await collection.aggregate(pipeline).to_list(length=1)
        
        if not chars:
            await update.message.reply_text(to_small_caps('❌ No characters found in database.'), parse_mode='HTML')
            return
            
        char = chars[0]
        name = char.get('name', 'Unknown')
        anime = char.get('anime', 'Unknown')
        char_id = char.get('id', str(random.randint(1000, 9999)))
        rarity = char.get('rarity', 'Unknown')
        img_url = char.get('img_url', None)

        original_price = random.randint(300000, 600000)
        discount = random.randint(2, 15)
        sale_price = int(original_price - (original_price * (discount / 100)))

        caption = f"""{to_small_caps('🏪 Daily Deals (1/2)')}

{to_small_caps('📛 Name:')} {to_small_caps(name)}
{to_small_caps('📺 Series:')} {to_small_caps(anime)}
{to_small_caps('🆔 ID:')} <b>{char_id}</b>
{to_small_caps('💫 Rarity:')} {to_small_caps(rarity)}
{to_small_caps('💰 Original:')} <b>{original_price:,}</b>
{to_small_caps('🏷️ Sale Price:')} <b>{sale_price:,}</b>
{to_small_caps('📉 Discount:')} <b>{discount}%</b>
{to_small_caps('🛒 Status:')} {to_small_caps('Available')}
{to_small_caps('🔴 Owned:')} <b>0</b>"""

        buttons = [
            [
                InlineKeyboardButton("⬅️", callback_data="mp_prev"),
                InlineKeyboardButton("Buy", callback_data=f"mp_buy_{char_id}"),
                InlineKeyboardButton("➡️", callback_data="mp_next")
            ],
            [InlineKeyboardButton("🌿 Auction", callback_data="mp_auction")],
            [InlineKeyboardButton("Refresh (30,000 💰)", callback_data="mp_refresh")]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)

        if img_url:
            await update.message.reply_photo(
                photo=img_url, 
                caption=caption, 
                reply_markup=reply_markup, 
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                text=caption, 
                reply_markup=reply_markup, 
                parse_mode='HTML'
            )

    except Exception as e:
        await update.message.reply_text(f"<blockquote>{to_small_caps(f'Error in Marketplace: {str(e)}') }</blockquote>", parse_mode='HTML')


# Register command handlers (Removed block=False as it causes errors in modern python-telegram-bot versions)
application.add_handler(CommandHandler('r', rarity_count))
application.add_handler(CommandHandler(['mp', 'marketplace'], marketplace))

import os
import asyncio
import logging
import random
from pyrogram import Client, filters
from pyrogram.types import Message, ChatMember, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMembersFilter, ChatMemberStatus
from google import genai
from google.genai import types
from google.genai.errors import APIError

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Credentials & Links (GitHub/Hosting Platform Environment Variables)
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))  # Owner's Telegram User ID

# NEW: Fetching button links securely via Environment Variables
UPDATES_LINK = os.environ.get("UPDATES_LINK", "https://t.me")  # Default backup if not set
SUPPORT_LINK = os.environ.get("SUPPORT_LINK", "https://t.me")  # Default backup if not set

# Validation
if not all([API_ID, API_HASH, BOT_TOKEN, GEMINI_API_KEY]):
    logger.critical("Missing required environment variables!")
    exit(1)

# Initialization
bot = Client("gemini_advanced_tagger_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Active tagging tasks storage
tagging_tasks = {}

# Stats Storage
stats = {"total_groups": set(), "total_users": set(), "tags_executed": 0}

# Gemini In-Memory Chat Storage for Context/Memory
chat_sessions = {}

# --- Helper Functions ---

async def is_admin(chat_id: int, user_id: int) -> bool:
    """Checks if a user is an admin or owner in the group."""
    if user_id == OWNER_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception:
        return False

async def get_all_members(chat_id: int, online_only: bool = False):
    """Fetches group members."""
    members = []
    try:
        async for member in bot.get_chat_members(chat_id):
            if member.user.is_bot:
                continue
            if online_only:
                if str(member.user.status) in ["UserStatus.ONLINE", "UserStatus.RECENTLY"]:
                    members.append(member)
            else:
                members.append(member)
    except Exception as e:
        logger.error(f"Error fetching members: {e}")
    return members

def get_or_create_session(chat_id: int):
    """Creates or retrieves a unique continuous conversation session for each group."""
    if chat_id not in chat_sessions:
        chat_sessions[chat_id] = ai_client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction="You are a helpful, witty, and concise Telegram group assistant. Respond naturally in Hinglish.",
                temperature=0.7,
            )
        )
    return chat_sessions[chat_id]

async def run_tagging_engine(chat_id: int, message: Message, member_list: list, custom_text: str, tag_type: str):
    """Main background loop that handles chunked tagging, pause, and stop."""
    try:
        stats["tags_executed"] += 1
        chunk_size = 6
        
        for i in range(0, len(member_list), chunk_size):
            if chat_id not in tagging_tasks:
                break
                
            while tagging_tasks.get(chat_id, {}).get("status") == "paused":
                await asyncio.sleep(1)
                if chat_id not in tagging_tasks:
                    break

            chunk = member_list[i:i + chunk_size]
            mentions = " ".join([m.user.mention(m.user.first_name) for m in chunk])
            
            final_msg = f"{custom_text}\n\n{mentions}"
            await bot.send_message(chat_id, final_msg)
            await asyncio.sleep(2)  # Anti-flood wait delay
            
        await bot.send_message(chat_id, "✅ **Tagging complete!**")
    except Exception as e:
        logger.error(f"Tagging loop error: {e}")
    finally:
        tagging_tasks.pop(chat_id, None)

# --- Private Chat Start & Button Handlers ---

@bot.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    chat_id = message.chat.id
    user_name = message.from_user.first_name if message.from_user else "User"
    bot_user = await client.get_me()
    bot_username = bot_user.username

    if message.chat.type.name == "PRIVATE":
        welcome_text = (
            f"👋 **Hello {user_name}!**\n\n"
            f"Main ek advanced **AI Mention & Group Tagger Bot** hoon.\n"
            f"Mujhe apne group mein add karke aap kisi bhi member ko tag ya mention kar sakte hain.\n\n"
            f"💡 **Kaise use karein?**\n"
            f"1️⃣ Niche diye gaye button se mujhe group me add karein.\n"
            f"2️⃣ Mujhe admin banayein.\n"
            f"3️⃣ Group me `/tagall` ya mujhe tag (`@{bot_username}`) karke use karein!"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ Add Me To Your Group ➕", url=f"https://t.me{bot_username}?startgroup=true")
            ],
            [
                InlineKeyboardButton("❓ Help & Cmds", callback_data="help_menu"),
                # MODIFIED: Link is loaded dynamically from variable
                InlineKeyboardButton("📢 Updates", url=UPDATES_LINK)  
            ],
            [
                # MODIFIED: Link is loaded dynamically from variable
                InlineKeyboardButton("🎧 Support Chat", url=SUPPORT_LINK) 
            ]
        ])

        await message.reply_text(text=welcome_text, reply_markup=keyboard)
    else:
        await message.reply_text(f"👋 PM me aao `{user_name}`, group me tagging commands ya AI use karein!")

@bot.on_callback_query(filters.regex("help_menu"))
async def help_callback(client: Client, callback_query):
    help_text = (
        "📜 **Bot Commands List:**\n\n"
        "⚡ **Tagging Commands (Admins Only):**\n"
        "• `/tagall` — General tag all members 🔥\n"
        "• `/hitag` — Tag in Hindi 🇮🇳\n"
        "• `/entag` — Tag in English 🇬🇧\n"
        "• `/gmtag` — Good Morning tag 🌅\n"
        "• `/gntag` — Good Night tag 🌙\n"
        "• `/jtag` — Joke tag 😂\n"
        "• `/vctag` — VC Invite (Online members first) 🎙️\n\n"
        "⚙️ **Control Commands:**\n"
        "• `/stop` — Stop tagging ❌\n"
        "• `/pause` — Pause tagging ⏸️\n"
        "• `/resume` — Resume tagging ▶️\n\n"
        "📢 **Shortcuts (For Everyone):**\n"
        "• `@all` ya `/all` — Tag 6 members\n"
        "• `@admin` ya `/admin` — Tag admins"
    )
    await callback_query.message.edit_text(help_text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")]
    ]))

@bot.on_callback_query(filters.regex("back_to_start"))
async def back_to_start_callback(client: Client, callback_query):
    await callback_query.message.delete()
    await start_command(client, callback_query.message)

# --- Group Tagging Commands Handler ---

@bot.on_message(filters.command(["hitag", "entag", "gmtag", "gntag", "tagall", "jtag", "vctag"]) & filters.group)
async def tagging_handler(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    cmd = message.command

    if not await is_admin(chat_id, user_id):
        return await message.reply_text("❌ Sirf admins hi ye command chalate hain!")

    if chat_id in tagging_tasks:
        return await message.reply_text("⚠️ Ek tagging process pehle se chal rahi hai. Use `/stop` karein pehle.")

    user_args = " ".join(message.command[1:]) if len(message.command) > 1 else ""
    theme_text = ""
    online_only = False

    if cmd == "hitag":
        theme_text = user_args or "🇮🇳 Sabhi log dhyan dein! Aapko yahan yaad kiya ja raha hai."
    elif cmd == "entag":
        theme_text = user_args or "🇬🇧 Hello everyone! Please check this important update."
    elif cmd == "gmtag":
        theme_text = user_args or "🌅 Suprabhat / Good Morning! Uth jao sab log, naya din shuru ho gaya."
    elif cmd == "gntag":
        theme_text = user_args or "🌙 Shubh Ratri / Good Night! Sone se pehle ek baar chat dekh lo."
    elif cmd == "tagall":
        theme_text = user_args or "🔥 ATTENTION SABHI LOG! Jaldi se chat par hazir hon."
    elif cmd == "jtag":
        jokes = [
            "😂 Arre group walo! Kam se kam group me hi thoda has liya karo.",
            "🤡 Ek joke yaad aaya, par pehle sab online toh aao!"
        ]
        theme_text = user_args or random.choice(jokes)
    elif cmd == "vctag":
        theme_text = user_args or "🎙️ **Voice Chat (VC) Shuru Ho Gayi Hai!** Online wale jaldi aao."
        online_only = True

    placeholder = await message.reply_text("🔄 Members scan ho rahe hain... Kripya thoda wait karein.")
    members = await get_all_members(chat_id, online_only=online_only)
    await placeholder.delete()

    if not members:
        return await message.reply_text("❌ Tag karne ke liye koi active members nahi mile!")

    tagging_tasks[chat_id] = {"status": "running", "task": None}
    task = asyncio.create_task(run_tagging_engine(chat_id, message, members, theme_text, cmd))
    tagging_tasks[chat_id]["task"] = task

# --- Control Commands (Admins Only) ---

@bot.on_message(filters.command("stop") & filters.group)
async def stop_tagging(client: Client, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id): return
    if message.chat.id in tagging_tasks:
        tagging_tasks[message.chat.id]["task"].cancel()
        tagging_tasks.pop(message.chat.id, None)
        await message.reply_text("❌ Ongoing tagging ko rok diya gaya hai!")
        else:
        

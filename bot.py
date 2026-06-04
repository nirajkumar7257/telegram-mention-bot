import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

# सर्वर के एनवायरनमेंट वेरिएबल्स (Environment Variables) से डिटेल्स उठाना
API_ID = int(os.environ.get("API_ID", 123456)) # डिफ़ॉल्ट नंबर की जगह सर्वर से लेगा
API_HASH = os.environ.get("API_HASH", "your_hash_here")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_token_here")

app = Client("mention_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command(["all", "everyone"]) & filters.group)
async def mention_all(client: Client, message: Message):
    chat_id = message.chat.id
    mentions = ""
    count = 0
    
    async for member in client.get_chat_members(chat_id):
        if member.user.is_bot:
            continue
            
        if member.user.username:
            mentions += f"@{member.user.username} "
        else:
            mentions += f"[{member.user.first_name}](tg://user?id={member.user.id}) "
        
        count += 1
        
        if count == 20:
            await client.send_message(chat_id, mentions)
            mentions = ""
            count = 0
            await asyncio.sleep(2)
            
    if mentions:
        await client.send_message(chat_id, mentions)

print("बॉट सफलतापूर्वक स्टार्ट हो गया है...")
app.run()

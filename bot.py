import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ChatType
import re, os

TOKEN = os.getenv("BOT_TOKEN") or "PUT_NEW_TOKEN_HERE"
bot = Bot(token=TOKEN)
dp = Dispatcher()
user_photos = {}
user_notes = {}
user_reminders = {}

def main_menu():
    keyboard = [
        [KeyboardButton(text="📸 Save Photo"), KeyboardButton(text="🖼 My Gallery")],
        [KeyboardButton(text="⏰ Set Reminder"), KeyboardButton(text="📋 My Reminders")],
        [KeyboardButton(text="📝 Add Note"), KeyboardButton(text="📄 My Notes")],
        [KeyboardButton(text="ℹ️ Help")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def is_private(message: types.Message) -> bool:
    return message.chat.type == ChatType.PRIVATE

#... keep your parse_time and detect_recurring functions same...

async def check_reminders():
    while True:
        now = datetime.now()
        to_remove = []
        for user_id, reminders in list(user_reminders.items()):
            for r in reminders[:]:
                if r['time'] <= now:
                    try:
                        await bot.send_message(user_id, f"⏰ **রিমাইন্ডার**\n\n{r['text']}", parse_mode="Markdown")
                        r['last_sent'] = now
                        if r['recurring'] == "daily":
                            r['time'] += timedelta(days=1)
                        elif r['recurring'] == "weekly":
                            r['time'] += timedelta(weeks=1)
                        elif r['recurring'] == "monthly":
                            r['time'] += timedelta(days=30)
                        else:
                            to_remove.append((user_id, r))
                    except:
                        pass
        for uid, rem in to_remove:
            if rem in user_reminders.get(uid, []):
                user_reminders[uid].remove(rem)
        await asyncio.sleep(30)

async def main():
    print("Secure Multi-language Reminder Bot is running...")
    asyncio.create_task(check_reminders())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
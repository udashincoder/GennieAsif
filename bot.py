import os, asyncio, re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ChatType

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("ERROR: BOT_TOKEN not found in Secrets!")
    exit()

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

def is_private(m): return m.chat.type == ChatType.PRIVATE

def parse_time(text):
    text=text.lower(); now=datetime.now()
    base=now+timedelta(days=1) if any(x in text for x in ["kalke","কালকে","tomorrow"]) else now
    hour=9; minute=0
    match=re.search(r'(\d{1,2})', text)
    if match: hour=int(match.group(1))
    if "bikal" in text or "evening" in text or "pm" in text:
        if hour<12: hour+=12
    rt=base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if rt<now: rt+=timedelta(days=1)
    return rt

@dp.message(CommandStart())
async def start(message: types.Message):
    if not is_private(message): return
    user_photos.setdefault(message.from_user.id, [])
    user_notes.setdefault(message.from_user.id, [])
    user_reminders.setdefault(message.from_user.id, [])
    await message.answer(f"হ্যালো {message.from_user.first_name}! 👋\nআমি আপনার প্রাইভেট বট।\n\nউদাহরণ: kalke shokal 10 tay meeting", reply_markup=main_menu())

@dp.message(F.text == "ℹ️ Help")
async def help_m(message: types.Message):
    await message.answer("উদাহরণ: kalke shokal 10 tay meeting\nprotodin 8 ta medicine")

@dp.message(F.text == "📋 My Reminders")
async def show_rem(message: types.Message):
    rems=user_reminders.get(message.from_user.id, [])
    if not rems: await message.answer("কোনো রিমাইন্ডার নেই।"); return
    txt="📋 রিমাইন্ডার:\n\n"+"\n".join([f"{r['text']} - {r['time'].strftime('%d %b %I:%M %p')}" for r in rems])
    await message.answer(txt)

@dp.message(F.photo)
async def photo_h(message: types.Message):
    user_photos.setdefault(message.from_user.id, []).append(message.photo[-1].file_id)
    await message.answer("✅ ছবি সেভ হয়েছে!")

@dp.message(F.text)
async def all_text(message: types.Message):
    if not is_private(message): return
    if message.text in ["📸 Save Photo","🖼 My Gallery","⏰ Set Reminder","📋 My Reminders","📝 Add Note","📄 My Notes","ℹ️ Help"]: return
    user_id=message.from_user.id
    user_reminders.setdefault(user_id, [])
    rt=parse_time(message.text)
    user_reminders[user_id].append({"text":message.text,"time":rt,"recurring":None})
    await message.answer(f"✅ রিমাইন্ডার সেট!\n📌 {message.text}\n🕒 {rt.strftime('%d %b %Y, %I:%M %p')}")

async def checker():
    while True:
        now=datetime.now()
        for uid, rems in list(user_reminders.items()):
            for r in rems[:]:
                if r['time']<=now:
                    try:
                        await bot.send_message(uid, f"⏰ রিমাইন্ডার: {r['text']}")
                        rems.remove(r)
                    except: pass
        await asyncio.sleep(30)

async def main():
    print("Secure Multi-language Reminder Bot is running...")
    asyncio.create_task(checker())
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())

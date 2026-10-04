import os, asyncio, re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.enums import ChatType
from gtts import gTTS

# === TOKEN ===
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("ERROR: BOT_TOKEN not found in Secrets!")
    exit()

bot = Bot(token=TOKEN)
dp = Dispatcher()

# === STORAGE ===
user_photos = {} # uid: [{"id":file_id, "name":lower, "orig":caption}]
user_notes = {}
user_reminders = {}
user_todos = {}
waiting_photo_name = {} # uid: file_id
waiting_todo = set() # uid

# === MENU ===
def main_menu():
    kb = [
        [KeyboardButton(text="📸 Save Photo"), KeyboardButton(text="🖼 My Gallery")],
        [KeyboardButton(text="⏰ Set Reminder"), KeyboardButton(text="📋 My Reminders")],
        [KeyboardButton(text="📝 My Notes"), KeyboardButton(text="✅ Todo List")],
        [KeyboardButton(text="🎙️ Voice Note"), KeyboardButton(text="ℹ️ Help")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def is_private(m): return m.chat.type == ChatType.PRIVATE

def parse_time(text):
    text=text.lower(); now=datetime.now()
    base=now+timedelta(days=1) if any(x in text for x in ["kalke","কালকে","tomorrow"]) else now
    h=9; m=0
    mt=re.search(r'(\d{1,2})', text)
    if mt: h=int(mt.group(1))
    if any(x in text for x in ["bikal","বিকাল","evening","pm"]):
        if h<12: h+=12
    rt=base.replace(hour=h, minute=m, second=0, microsecond=0)
    if rt<now: rt+=timedelta(days=1)
    return rt

async def send_voice(chat_id, text):
    try:
        tts=gTTS(text=text[:300], lang='bn', slow=False)
        tts.save("voice.mp3")
        await bot.send_voice(chat_id, FSInputFile("voice.mp3"), caption=f"🔊 {text}")
        if os.path.exists("voice.mp3"): os.remove("voice.mp3")
    except Exception as e:
        print(f"Voice error: {e}")
        await bot.send_message(chat_id, f"⏰ {text}")

# === START ===
@dp.message(CommandStart())
async def start(message: types.Message):
    if not is_private(message): return
    uid=message.from_user.id
    user_photos.setdefault(uid, []); user_notes.setdefault(uid, []); user_reminders.setdefault(uid, []); user_todos.setdefault(uid, [])
    await message.answer(f"হ্যালো {message.from_user.first_name}! 👋\n\n"
                         f"📸 ছবি পাঠিয়ে নাম দিন, পরে নাম লিখলেই দেখাবো\n"
                         f"✅ Todo: `todo bazar kora` বা Todo List বাটন\n"
                         f"⏰ Reminder: `kalke 10 tay meeting`\n"
                         f"🎙️ Voice: `voice e bolo hello`", reply_markup=main_menu())

@dp.message(F.text == "ℹ️ Help")
async def help_m(message: types.Message):
    await message.answer("📸 ছবি + Caption = নামে সেভ\n"
                         "উদা: ছবি পাঠিয়ে caption 'family' লিখুন -> পরে 'family' লিখলেই ছবি আসবে\n\n"
                         "✅ Todo: Todo List -> Add Todo\n"
                         "⏰ Reminder: kalke shokal 10 tay meeting\n"
                         "🎙️ Voice e bolo apnar kotha", reply_markup=main_menu())

# === GALLERY ===
@dp.message(F.text == "🖼 My Gallery")
async def gallery(message: types.Message):
    if not is_private(message): return
    photos=user_photos.get(message.from_user.id, [])
    if not photos:
        await message.answer("গ্যালারি খালি। ছবি পাঠান।"); return
    text=f"🖼 আপনার {len(photos)} টা ছবি:\n\n" + "\n".join([f"{i+1}. 📷 {p['orig']}" for i,p in enumerate(photos[-15:])])
    buttons=[[InlineKeyboardButton(text=f"📷 {p['orig'][:20]}", callback_data=f"show_{p['id']}")] for p in photos[-10:]]
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await message.answer("💡 যেকোনো ছবির নাম লিখুন, সাথে সাথে দেখাবো!")

@dp.callback_query(F.data.startswith("show_"))
async def cb_show(cb: types.CallbackQuery):
    await bot.send_photo(cb.message.chat.id, cb.data.replace("show_",""))
    await cb.answer()

# === TODO ===
@dp.message(F.text == "✅ Todo List")
async def show_todo(message: types.Message):
    if not is_private(message): return
    uid=message.from_user.id; todos=user_todos.get(uid, [])
    if not todos:
        kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Add Todo", callback_data="add_todo")]])
        await message.answer("📝 Todo খালি।", reply_markup=kb); return
    txt="✅ **Todo List:**\n\n"
    btns=[]
    for i,t in enumerate(todos):
        st="✅" if t['done'] else "⬜"
        txt+=f"{i+1}. {st} {t['task']}\n"
        btns.append([InlineKeyboardButton(text=f"{'↩️ Undo' if t['done'] else '✅ Done'}: {t['task'][:15]}", callback_data=f"done_{i}"),
                     InlineKeyboardButton(text="❌", callback_data=f"del_{i}")])
    btns.append([InlineKeyboardButton(text="➕ Add Todo", callback_data="add_todo")])
    btns.append([InlineKeyboardButton(text="🗑️ Clear Done", callback_data="clear_done")])
    await message.answer(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data=="add_todo")
async def cb_add(cb: types.CallbackQuery):
    waiting_todo.add(cb.from_user.id)
    await cb.message.answer("✏️ Todo কি? লিখে পাঠান।\nউদা: Bazar kora")
    await cb.answer()

@dp.callback_query(F.data.startswith("done_"))
async def cb_done(cb: types.CallbackQuery):
    uid=cb.from_user.id; idx=int(cb.data.split("_")[1])
    if idx < len(user_todos.get(uid, [])):
        user_todos[uid][idx]['done']=not user_todos[uid][idx]['done']
    await cb.answer("Updated!"); await show_todo(cb.message)

@dp.callback_query(F.data.startswith("del_"))
async def cb_del(cb: types.CallbackQuery):
    uid=cb.from_user.id; idx=int(cb.data.split("_")[1])
    if idx < len(user_todos.get(uid, [])): user_todos[uid].pop(idx)
    await cb.answer("Deleted!"); await show_todo(cb.message)

@dp.callback_query(F.data=="clear_done")
async def cb_clear(cb: types.CallbackQuery):
    uid=cb.from_user.id
    user_todos[uid]=[t for t in user_todos.get(uid,[]) if not t['done']]
    await cb.answer("Cleared!"); await show_todo(cb.message)

# === REMINDERS & NOTES LIST ===
@dp.message(F.text == "📋 My Reminders")
async def show_rem(message: types.Message):
    rems=user_reminders.get(message.from_user.id, [])
    if not rems: await message.answer("কোনো রিমাইন্ডার নেই।"); return
    await message.answer("⏰ Reminders:\n" + "\n".join([f"- {r['text']} @ {r['time'].strftime('%d %b %I:%M %p')}" for r in rems]))

@dp.message(F.text == "📝 My Notes")
async def show_notes(message: types.Message):
    notes=user_notes.get(message.from_user.id, [])
    await message.answer("\n".join(notes) if notes else "নোট খালি।")

@dp.message(F.text == "🎙️ Voice Note")
async def voice_info(message: types.Message):
    await message.answer("🎙️ ভয়েস পাঠান অথবা লিখুন:\n`voice e bolo kalke meeting ache`")

# === PHOTO HANDLER ===
@dp.message(F.photo)
async def photo_h(message: types.Message):
    if not is_private(message): return
    uid=message.from_user.id; file_id=message.photo[-1].file_id
    caption=message.caption.strip() if message.caption else ""
    if caption:
        user_photos.setdefault(uid, []).append({"id":file_id, "name":caption.lower(), "orig":caption})
        await message.answer(f"✅ সেভ হলো: **{caption}**\nএখন '{caption}' লিখলেই দেখাবো!", reply_markup=main_menu())
    else:
        waiting_photo_name[uid]=file_id
        await message.answer("📝 এই ছবির নাম কি দিবো?\nযেমন: family, nid, ammu\nনাম লিখুন।")

# === VOICE HANDLER ===
@dp.message(F.voice | F.audio)
async def voice_h(message: types.Message):
    if not is_private(message): return
    await message.answer("🎧 ভয়েস পেয়েছি! সেভ হলো।\nসময় বলুন: `kalke 10 tay`")
    await send_voice(message.chat.id, "ভয়েস সেভ হয়েছে")

# === MAIN TEXT LOGIC - PHOTO SEARCH + TODO + REMINDER ===
@dp.message(F.text)
async def all_text(message: types.Message):
    if not is_private(message): return
    uid=message.from_user.id; txt=message.text.strip(); low=txt.lower()
    if txt in ["📸 Save Photo","🖼 My Gallery","⏰ Set Reminder","📋 My Reminders","📝 My Notes","✅ Todo List","🎙️ Voice Note","ℹ️ Help"]: return

    # 1. Waiting for photo name
    if uid in waiting_photo_name:
        fid=waiting_photo_name.pop(uid)
        user_photos.setdefault(uid, []).append({"id":fid, "name":low, "orig":txt})
        await message.answer(f"✅ ছবি সেভ: **{txt}**\nএখন '{txt}' লিখলেই পাবেন!", reply_markup=main_menu())
        return

    # 2. Waiting for todo
    if uid in waiting_todo:
        user_todos.setdefault(uid, []).append({"task":txt, "done":False})
        waiting_todo.remove(uid)
        await message.answer(f"✅ Todo যোগ: {txt}", reply_markup=main_menu())
        await show_todo(message); return

    # 3. INSTANT PHOTO SEARCH - If text matches photo name
    photos=user_photos.get(uid, [])
    matched=[p for p in photos if low in p['name'] or p['name'] in low or low == p['name']]
    if matched:
        await message.answer(f"🔍 '{txt}' এর {len(matched)} টা ছবি:")
        for p in matched[:5]:
            await bot.send_photo(message.chat.id, p['id'], caption=f"📷 {p['orig']}")
        return

    # 4. Quick todo: "todo bazar"
    if low.startswith("todo "):
        task=txt[5:].strip()
        user_todos.setdefault(uid, []).append({"task":task, "done":False})
        await message.answer(f"✅ Todo: {task}"); return

    # 5. Voice command
    if "voice e bolo" in low:
        speak=txt.lower().replace("voice e bolo","").strip() or "হ্যালো"
        await send_voice(message.chat.id, speak); return

    # 6. Reminder detection
    if any(w in low for w in ["kalke","কালকে","ajke","আজকে","tomorrow","today","tay","ta ","remind","meeting","protodin","every"]):
        try:
            rt=parse_time(txt)
            user_reminders.setdefault(uid, []).append({"text":txt,"time":rt})
            await message.answer(f"✅ রিমাইন্ডার সেট!\n📌 {txt}\n🕒 {rt.strftime('%d %b %Y, %I:%M %p')}\n🔊 সময় হলে ভয়েসে বলবো")
            return
        except Exception as e:
            print(e)

    # 7. Default = Note
    user_notes.setdefault(uid, []).append(txt)
    await message.answer("✅ নোট সেভ!")

# === REMINDER CHECKER ===
async def checker():
    while True:
        now=datetime.now()
        for uid, rems in list(user_reminders.items()):
            for r in rems[:]:
                if r['time'] <= now:
                    try:
                        await send_voice(uid, r['text'])
                        await bot.send_message(uid, f"⏰ রিমাইন্ডার: {r['text']}")
                        rems.remove(r)
                    except: pass
        await asyncio.sleep(30)

async def main():
    print("Bot with PhotoName + Todo + Voice + Reminder RUNNING...")
    asyncio.create_task(checker())
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
    

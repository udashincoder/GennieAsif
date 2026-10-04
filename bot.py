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
    print("❌ BOT_TOKEN not found! Add in Secrets")
    exit()

bot = Bot(token=TOKEN)
dp = Dispatcher()

# === ADVANCED WHISPER MODEL - Loads once ===
print("🧠 Loading Whisper AI model (small)... first time will download 200MB")
try:
    from faster_whisper import WhisperModel
    whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
    WHISPER_READY = True
    print("✅ Whisper Ready - Bangla + English")
except Exception as e:
    print(f"⚠️ Whisper not available, using backup: {e}")
    whisper_model = None
    WHISPER_READY = False

# === STORAGE ===
user_photos = {}
user_notes = {}
user_reminders = {}
user_todos = {}
waiting_photo_name = {}
waiting_todo = set()

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
    base=now+timedelta(days=1) if any(x in text for x in ["kalke","কালকে","tomorrow","porshu"]) else now
    h=9; m=0
    mt=re.search(r'(\d{1,2})', text)
    if mt: h=int(mt.group(1))
    if any(x in text for x in ["bikal","বিকাল","evening","pm","rat","রাত"]):
        if h<12: h+=12
    rt=base.replace(hour=h, minute=m, second=0, microsecond=0)
    if rt<now: rt+=timedelta(days=1)
    return rt

async def send_voice(chat_id, text, lang='auto'):
    if lang=='auto':
        lang='bn' if any("\u0980" <= c <= "\u09FF" for c in text) else 'en'
    try:
        tts=gTTS(text=text[:350], lang=lang, slow=False)
        tts.save("voice.mp3")
        await bot.send_voice(chat_id, FSInputFile("voice.mp3"), caption=f"🔊 {text}")
        if os.path.exists("voice.mp3"): os.remove("voice.mp3")
    except:
        await bot.send_message(chat_id, f"🔊 {text}")

# === ADVANCED TRANSCRIBE ===
async def transcribe_advanced(file_id):
    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, "voice.ogg")

    text = ""
    lang = "en"

    # 1. Try Whisper (Best for Bangla+English mix)
    if WHISPER_READY:
        try:
            segments, info = whisper_model.transcribe("voice.ogg", beam_size=5, language=None)
            text = " ".join([s.text for s in segments]).strip()
            lang = info.language
        except Exception as e:
            print(f"Whisper error: {e}")

    # 2. Fallback to Google if whisper fails
    if not text:
        try:
            from pydub import AudioSegment
            import speech_recognition as sr
            sound = AudioSegment.from_ogg("voice.ogg")
            sound.export("voice.wav", format="wav")
            r = sr.Recognizer()
            with sr.AudioFile("voice.wav") as source:
                audio = r.record(source)
                try: text = r.recognize_google(audio, language="bn-BD"); lang='bn'
                except:
                    try: text = r.recognize_google(audio, language="en-US"); lang='en'
                    except: text=""
            if os.path.exists("voice.wav"): os.remove("voice.wav")
        except Exception as e:
            print(f"Backup STT error: {e}")

    if os.path.exists("voice.ogg"): os.remove("voice.ogg")
    return text, lang

def understand_intent(text):
    low=text.lower()
    intent={"type":"note", "task":text, "time":None, "query":""}

    # Photo search intent
    if any(w in low for w in ["show","dekhao","দেখাও","photo","ছবি","chobi","family","pic"]):
        intent["type"]="photo_search"
        q=re.sub(r'show|dekhao|দেখাও|photo|ছবি|chobi|dekhan|please|ekta|amake', '', low).strip()
        intent["query"]=q if q else low

    # Todo intent
    elif any(w in low for w in ["todo","কাজ","bazar","কিনতে","করতে","korte","buy","task"]):
        intent["type"]="todo"

    # Reminder intent
    elif any(w in low for w in ["kalke","porshu","ajke","কালকে","আগামীকাল","tomorrow","today","sokal","bikal","tay","ta ","reminder","meeting","medicine","alarm","sokale"]):
        intent["type"]="reminder"
        try: intent["time"]=parse_time(text)
        except: pass

    return intent

# === HANDLERS ===
@dp.message(CommandStart())
async def start(message: types.Message):
    if not is_private(message): return
    uid=message.from_user.id
    for d in [user_photos, user_notes, user_reminders, user_todos]: d.setdefault(uid, [])
    await message.answer(f"হ্যালো {message.from_user.first_name}! 👋\n\n"
                         f"🧠 **Whisper AI Active**\n"
                         f"🎙️ ভয়েস বলুন: 'kalke 10 tay meeting' বা 'family photo dekhao'\n"
                         f"📸 ছবি caption দিয়ে সেভ করুন\n"
                         f"✅ Todo: 'todo bazar kora'", reply_markup=main_menu())

@dp.message(F.text == "ℹ️ Help")
async def help_m(message: types.Message):
    await message.answer("🎙️ **Voice Commands:**\n"
                         "• 'kalke 10 tay meeting' -> Reminder\n"
                         "• 'bazar kora todo' -> Todo\n"
                         "• 'family photo dekhao' -> Shows photo\n"
                         "• 'voice e bolo hello' -> Bot speaks\n\n"
                         "📸 **Photo:** Send with caption 'family', then type 'family' to see instantly", reply_markup=main_menu())

@dp.message(F.text == "🖼 My Gallery")
async def gallery(message: types.Message):
    if not is_private(message): return
    photos=user_photos.get(message.from_user.id, [])
    if not photos: await message.answer("গ্যালারি খালি।"); return
    txt=f"🖼 {len(photos)} photos:\n\n" + "\n".join([f"{i+1}. {p['orig']}" for i,p in enumerate(photos[-15:])])
    btns=[[InlineKeyboardButton(text=f"📷 {p['orig'][:20]}", callback_data=f"show_{p['id']}")] for p in photos[-10:]]
    await message.answer(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("show_"))
async def cb_show(cb: types.CallbackQuery):
    await bot.send_photo(cb.message.chat.id, cb.data.replace("show_","")); await cb.answer()

@dp.message(F.text == "✅ Todo List")
async def show_todo(message: types.Message):
    if not is_private(message): return
    todos=user_todos.get(message.from_user.id, [])
    if not todos:
        await message.answer("Todo খালি।", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Add Todo", callback_data="add_todo")]])); return
    txt="✅ **Todo List:**\n\n"; btns=[]
    for i,t in enumerate(todos):
        st="✅" if t['done'] else "⬜"; txt+=f"{i+1}. {st} {t['task']}\n"
        btns.append([InlineKeyboardButton(text=f"{'↩️' if t['done'] else '✅'} {t['task'][:15]}", callback_data=f"done_{i}"), InlineKeyboardButton(text="❌", callback_data=f"del_{i}")])
    btns.append([InlineKeyboardButton(text="➕ Add Todo", callback_data="add_todo")])
    await message.answer(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data=="add_todo")
async def cb_add(cb: types.CallbackQuery):
    waiting_todo.add(cb.from_user.id); await cb.message.answer("✏️ Todo লিখুন:"); await cb.answer()
@dp.callback_query(F.data.startswith("done_"))
async def cb_done(cb: types.CallbackQuery):
    idx=int(cb.data.split("_")[1]); uid=cb.from_user.id
    if idx < len(user_todos.get(uid, [])): user_todos[uid][idx]['done']=not user_todos[uid][idx]['done']
    await cb.answer("Done!"); await show_todo(cb.message)
@dp.callback_query(F.data.startswith("del_"))
async def cb_del(cb: types.CallbackQuery):
    idx=int(cb.data.split("_")[1]); uid=cb.from_user.id
    if idx < len(user_todos.get(uid, [])): user_todos[uid].pop(idx)
    await cb.answer("Deleted!"); await show_todo(cb.message)

@dp.message(F.text == "📋 My Reminders")
async def show_rem(message: types.Message):
    rems=user_reminders.get(message.from_user.id, [])
    await message.answer("\n".join([f"⏰ {r['text']} @ {r['time'].strftime('%d %b %I:%M %p')}" for r in rems]) if rems else "No reminders")

@dp.message(F.photo)
async def photo_h(message: types.Message):
    if not is_private(message): return
    uid=message.from_user.id; fid=message.photo[-1].file_id; cap=message.caption.strip() if message.caption else ""
    if cap:
        user_photos.setdefault(uid, []).append({"id":fid, "name":cap.lower(), "orig":cap})
        await message.answer(f"✅ সেভ: **{cap}**\nএখন '{cap}' লিখলেই দেখাবো!", reply_markup=main_menu())
    else:
        waiting_photo_name[uid]=fid; await message.answer("📝 এই ছবির নাম দিন? যেমন: family")

# === ADVANCED VOICE HANDLER ===
@dp.message(F.voice | F.audio)
async def voice_h(message: types.Message):
    if not is_private(message): return
    uid=message.from_user.id
    file_id=message.voice.file_id if message.voice else message.audio.file_id

    await bot.send_chat_action(message.chat.id, "typing")
    status = await message.answer("🧠 Whisper AI শুনছে...")

    text, lang = await transcribe_advanced(file_id)

    if not text:
        await status.edit_text("❌ বুঝতে পারিনি। আবার একটু জোরে বলুন।\nCould not understand, speak again clearly.")
        return

    await status.edit_text(f"✅ শুনলাম [{lang}]: **{text}**\n🤖 বুঝছি...")

    intent = understand_intent(text)

    if intent["type"] == "todo":
        user_todos.setdefault(uid, []).append({"task": text, "done": False})
        reply = f"Todo যোগ হলো: {text}" if lang=='bn' else f"Added to Todo: {text}"
        await message.answer(f"✅ {reply}")
        await send_voice(message.chat.id, reply, lang)

    elif intent["type"] == "reminder":
        rt = intent["time"] or parse_time(text)
        user_reminders.setdefault(uid, []).append({"text": text, "time": rt})
        reply = f"রিমাইন্ডার সেট করলাম {rt.strftime('%d %b %I:%M %p')}" if lang=='bn' else f"Reminder set for {rt.strftime('%d %b %I:%M %p')}"
        await message.answer(f"⏰ {reply}\n📌 {text}")
        await send_voice(message.chat.id, reply, lang)

    elif intent["type"] == "photo_search":
        photos=user_photos.get(uid, [])
        q=intent["query"]
        matched=[p for p in photos if q in p['name'] or p['name'] in q or q in p['orig'].lower()]
        if matched:
            await message.answer(f"🔍 '{q}' এর {len(matched)} টা ছবি পেলাম:")
            for p in matched[:5]:
                await bot.send_photo(message.chat.id, p['id'], caption=f"📷 {p['orig']}")
        else:
            await message.answer(f"❌ '{q}' নামে কোনো ছবি পাইনি। Gallery তে আছে: {', '.join([p['orig'] for p in photos[-5:]])}")

    else:
        user_notes.setdefault(uid, []).append(text)
        reply = f"নোট সেভ করলাম: {text}" if lang=='bn' else f"Saved note: {text}"
        await message.answer(f"📝 {reply}")
        await send_voice(message.chat.id, reply, lang)

@dp.message(F.text)
async def all_text(message: types.Message):
    if not is_private(message): return
    uid=message.from_user.id; txt=message.text.strip(); low=txt.lower()
    if txt in ["📸 Save Photo","🖼 My Gallery","⏰ Set Reminder","📋 My Reminders","📝 My Notes","✅ Todo List","🎙️ Voice Note","ℹ️ Help"]: return
    if uid in waiting_photo_name:
        fid=waiting_photo_name.pop(uid); user_photos.setdefault(uid, []).append({"id":fid, "name":low, "orig":txt})
        await message.answer(f"✅ সেভ: {txt} — এখন '{txt}' লিখলেই দেখাবো!", reply_markup=main_menu()); return
    if uid in waiting_todo:
        user_todos.setdefault(uid, []).append({"task":txt, "done":False}); waiting_todo.remove(uid)
        await message.answer(f"✅ Todo: {txt}"); await show_todo(message); return

    # INSTANT PHOTO SEARCH
    photos=user_photos.get(uid, [])
    matched=[p for p in photos if low in p['name'] or p['name'] in low]
    if matched:
        for p in matched[:5]: await bot.send_photo(message.chat.id, p['id'], caption=f"📷 {p['orig']}")
        return

    if low.startswith("todo "):
        user_todos.setdefault(uid, []).append({"task":txt[5:], "done":False}); await message.answer(f"✅ Todo: {txt[5:]}"); return
    if "voice e bolo" in low:
        await send_voice(message.chat.id, txt.lower().replace("voice e bolo","")); return
    if any(w in low for w in ["kalke","কালকে","tomorrow","today","tay","remind","meeting","protodin"]):
        try:
            rt=parse_time(txt); user_reminders.setdefault(uid, []).append({"text":txt,"time":rt})
            await message.answer(f"✅ Reminder: {txt} @ {rt.strftime('%d %b %I:%M %p')}"); return
        except: pass
    user_notes.setdefault(uid, []).append(txt); await message.answer("✅ Note saved!")

async def checker():
    while True:
        now=datetime.now()
        for uid, rems in list(user_reminders.items()):
            for r in rems[:]:
                if r['time'] <= now:
                    try:
                        await send_voice(uid, r['text']); await bot.send_message(uid, f"⏰ {r['text']}"); rems.remove(r)
                    except: pass
        await asyncio.sleep(30)

async def main():
    print("🚀 ULTIMATE BOT with Whisper AI RUNNING...")
    asyncio.create_task(checker())
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())

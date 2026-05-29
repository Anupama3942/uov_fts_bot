import os
import asyncio
from datetime import datetime
from thefuzz import process

# අලුත් Async Firestore Client එක සහ Filters
from google.cloud.firestore import AsyncClient
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.aggregation import AggregationQuery

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  
FIREBASE_KEY_PATH = os.getenv("FIREBASE_KEY_PATH", "firebase.json")
ADMIN_IDS = [1650090885]

# Connect Bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==========================================
# 🚀 NEW: Async Firestore Initialization
# ==========================================
# මෙතැන් සිට firebase_admin වෙනුවට AsyncClient භාවිතා වේ.
db = AsyncClient.from_service_account_info(FIREBASE_KEY_PATH) if not os.path.exists(FIREBASE_KEY_PATH) else AsyncClient.from_service_account_json(FIREBASE_KEY_PATH)

# Database Collections
files_col = db.collection("academic_resources")
pending_col = db.collection("pending_resources")
users_col = db.collection("bot_users")

# ==========================================
# Verified Course List
# ==========================================
SUBJECTS = {
    # LEVEL 1 - Semester 1
    "TICT1114": ("Essentials of ICT", 1, 1),
    "TICT1123": ("Mathematics for Technology", 1, 1),
    "TICT1134": ("Fundamentals of Computer Programming", 1, 1),
    "TICT1142": ("Fundamentals of Web Technologies", 1, 1),
    "TICT1152": ("Principles of Management", 1, 1),
    "AUX1113":  ("English Language I", 1, 1),
    
    # LEVEL 1 - Semester 2
    "TICT1212": ("Discrete Structures", 1, 2),
    "TICT1224": ("Object Oriented Programming", 1, 2),
    "TICT1233": ("Operating Systems", 1, 2),
    "TICT1243": ("Electronics and Digital Circuit Designs", 1, 2),
    "TICT1252": ("Computational Engineering Drawing", 1, 2),
    "TICT1261": ("IT Law", 1, 2),
    "AUX1212":  ("Social Harmony and Active Citizenship", 1, 2),
    
    # LEVEL 2 - Semester 1
    "TICT2113": ("Data Structures and Algorithms", 2, 1),
    "TICT2122": ("Statistics for Technology", 2, 1),
    "TICT2134": ("Advanced Computer Programming", 2, 1),
    "TICT2142": ("Multimedia Design and Technologies", 2, 1),
    "TICT2153": ("Human Computer Interaction", 2, 1),
    "AUX2113":  ("English Language II", 2, 1),
    
    # LEVEL 2 - Semester 2
    "TICT2212": ("Operational Research", 2, 2),
    "TICT2222": ("Computer Networks", 2, 2),
    "TICT2233": ("Database Management Systems", 2, 2),
    "TICT2244": ("Computer Graphics", 2, 2),
    "TICT2252": ("System Analysis and Design", 2, 2),
    "TICT2263": ("Accounting for Technology", 2, 2),
    "AUX2212":  ("Communication and Soft Skills", 2, 2),
    
    # LEVEL 3 - Semester 1
    "TICT3113": ("Computer Architecture and Organization", 3, 1),
    "TICT3123": ("Advanced Database Management Systems", 3, 1),
    "TICT3132": ("Advanced Web Technologies", 3, 1),
    "TICT3142": ("Social and Professional Issues in IT", 3, 1),
    "TICT3153": ("Software Engineering", 3, 1),
    "TICT3162": ("Information Security", 3, 1),
    "AUX3112":  ("Career Guidance", 3, 1),
    
    # LEVEL 3 - Semester 2
    "TICT3214": ("Advanced Computer Networks and Administration", 3, 2),
    "TICT3222": ("IT Project Management", 3, 2),
    "TICT3232": ("Software Quality Assurance", 3, 2),
    "TICT3243": ("Mobile Computing", 3, 2),
    "TICT3252": ("Green Computing", 3, 2),
    "TICT3262": ("Distributed Systems", 3, 2),
    "AUX3211":  ("Research Methodology and Scientific Writing", 3, 2),
    "AUX3221":  ("Entrepreneurship for Technology", 3, 2),
    
    # LEVEL 4 - Semester 1
    "TICT4116": ("Group Research Project", 4, 1),
    "TICT4126": ("Industrial Training", 4, 1),
    
    # LEVEL 4 - Semester 2
    "TICT4213": ("Data Mining and Data Warehousing", 4, 2),
    "TICT4223": ("Digital Image Processing", 4, 2),
    "TICT4233": ("e-Commerce", 4, 2),
    "TICT4242": ("Mobile Application Development", 4, 2),
    "TICT4253": ("Intelligent Systems", 4, 2),
    "TICT4262": ("Cloud Application Development", 4, 2),
    "TICT4272": ("Applied Bio-informatics", 4, 2)
}

def get_subjects_for(level: int, semester: int):
    return {
        code: info[0]
        for code, info in SUBJECTS.items()
        if info[1] == level and info[2] == semester
    }

class UploadForm(StatesGroup):
    waiting_for_subject = State()
    waiting_for_category = State()
    waiting_for_file = State()

# ==========================================
# 👤 Async User Tracking
# ==========================================
async def track_user(user: types.User):
    doc_ref = users_col.document(str(user.id))
    doc = await doc_ref.get() # ASYNC GET
    if not doc.exists:
        await doc_ref.set({ # ASYNC SET
            "first_name": user.first_name,
            "username": user.username if user.username else "",
            "joined_at": datetime.now()
        })

# ==========================================
# Keyboards & UI
# ==========================================
def get_persistent_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📂 Browse Resources"), KeyboardButton(text="🔍 Search Subject")],
            [KeyboardButton(text="📤 Upload Note"), KeyboardButton(text="🏆 Leaderboard")],
            [KeyboardButton(text="🙋‍♂️ Request Paper"), KeyboardButton(text="📊 Bot Statistics")]
        ],
        resize_keyboard=True,
        is_persistent=True,
        placeholder="Select an option from the menu..."
    )

def get_start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Browse Resources", callback_data="browse")],
        [InlineKeyboardButton(text="🔍 Search by Subject Code", callback_data="search")],
    ])

def get_level_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📗 Level 1", callback_data="level_1"),
         InlineKeyboardButton(text="📘 Level 2", callback_data="level_2")],
        [InlineKeyboardButton(text="📙 Level 3", callback_data="level_3"),
         InlineKeyboardButton(text="📕 Level 4", callback_data="level_4")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_start")]
    ])

def get_semester_keyboard(level: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Semester 1", callback_data=f"sem_1_{level}"),
         InlineKeyboardButton(text="📖 Semester 2", callback_data=f"sem_2_{level}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="browse")]
    ])

def get_subject_action_keyboard(level: str, semester: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Download All Past Papers", callback_data=f"dlall_{level}_{semester}")],
        [InlineKeyboardButton(text="📚 Browse by Subject", callback_data=f"bysubject_{level}_{semester}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data=f"level_{level}")]
    ])

def get_subjects_keyboard(level: str, semester: str):
    subjects = get_subjects_for(int(level), int(semester))
    buttons = []
    row = []
    for code in subjects:
        row.append(InlineKeyboardButton(text=code, callback_data=f"subject_{code}_{level}_{semester}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Back", callback_data=f"sem_{semester}_{level}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_category_menu(code: str, level: str, semester: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Past Papers", callback_data=f"subcat_Past Paper_{code}_{level}_{semester}")],
        [InlineKeyboardButton(text="👨‍🏫 Lecture Notes", callback_data=f"subcat_Lecture Note_{code}_{level}_{semester}")],
        [InlineKeyboardButton(text="📝 Student Short Notes", callback_data=f"subcat_Short Note_{code}_{level}_{semester}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data=f"bysubject_{level}_{semester}")]
    ])

# දැන් Database එකට යන නිසා async function එකක් විය යුතුයි
async def get_year_keyboard(code: str, level: str, semester: str):
    try:
        query = files_col.where(filter=FieldFilter("subject_code", "==", code)).where(filter=FieldFilter("category", "==", "Past Paper"))
        years = set()
        
        # ASYNC STREAM
        async for doc in query.stream():
            data = doc.to_dict()
            if "year" in data:
                years.add(data["year"])
                
        available_years = sorted(list(years), reverse=True)
    except Exception:
        available_years = []

    if not available_years:
        return None

    buttons = []
    row = []
    for year in available_years:
        row.append(InlineKeyboardButton(text=f"📅 {year}", callback_data=f"get_{code}_{year}_{semester}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Back", callback_data=f"subject_{code}_{level}_{semester}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_rating_keyboard(doc_id: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ 1", callback_data=f"rate_{doc_id}_1"),
            InlineKeyboardButton(text="⭐ 2", callback_data=f"rate_{doc_id}_2"),
            InlineKeyboardButton(text="⭐ 3", callback_data=f"rate_{doc_id}_3"),
            InlineKeyboardButton(text="⭐ 4", callback_data=f"rate_{doc_id}_4"),
            InlineKeyboardButton(text="⭐ 5", callback_data=f"rate_{doc_id}_5")
        ]
    ])

# ==========================================
# Core Handlers
# ==========================================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await track_user(message.from_user)
    await message.answer(
        f"👋 Welcome {message.from_user.first_name}!\n\n"
        f"📚 *University Faculty Resource Bot*\n"
        f"Access past papers, lecture notes, and community short notes easily.\n\n"
        f"Choose an option below:",
        reply_markup=get_persistent_main_menu(),
        parse_mode="Markdown"
    )
    await message.answer(
        "⚡ Quick Menu:",
        reply_markup=get_start_keyboard()
    )

@dp.callback_query(F.data == "back_to_start")
async def back_to_start(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"👋 Welcome {callback.from_user.first_name}!\n\n"
        f"📚 *University Faculty Resource Bot*\n"
        f"Access past papers and notes easily.\n\n"
        f"Choose an option below:",
        reply_markup=get_start_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(F.text == "📂 Browse Resources")
async def process_persistent_browse(message: types.Message):
    await track_user(message.from_user)
    await message.answer(
        "📂 *Browse Resources*\n\nSelect your level:",
        reply_markup=get_level_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(F.text == "🔍 Search Subject")
async def process_persistent_search(message: types.Message):
    await track_user(message.from_user)
    await message.answer(
        f"🔍 *Search by Subject Code or Name*\n\n"
        f"Type the subject code or keywords and send:\n\n"
        f"Example: `TICT2113` or `Data Structures`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_start")]
        ])
    )

@dp.message(F.text == "🙋‍♂️ Request Paper")
async def process_persistent_request(message: types.Message):
    await track_user(message.from_user)
    await message.answer(
        "🙋‍♂️ *How to request a paper:*\n\n"
        "1. Use the *📂 Browse Resources* or *🔍 Search Subject* buttons to find your subject.\n"
        "2. If no papers are found, a **[🙋‍♂️ Request this Subject]** button will appear.\n"
        "3. Click it, and the admins will be notified instantly!\n\n"
        "Alternatively, you can manually request by typing:\n"
        "`/request SUBJECT_CODE` (e.g., `/request TICT2113`)",
        parse_mode="Markdown"
    )

# ==========================================
# 📊 Optimized Async Bot Statistics
# ==========================================
@dp.message(F.text == "📊 Bot Statistics")
async def process_persistent_stats(message: types.Message):
    await track_user(message.from_user)
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ This feature is reserved for Administrators only.")
        return

    try:
        # ASYNC AGGREGATION QUERIES (Highly efficient, no bandwidth wasted)
        count_query = await files_col.count().get()
        total = count_query[0][0].value
        
        # Async stream for detailed mapping
        all_docs = []
        async for doc in files_col.stream():
            all_docs.append(doc.to_dict())
            
        level_stats = ""
        for level in [1, 2, 3, 4]:
            codes = [c for c, info in SUBJECTS.items() if info[1] == level]
            count = sum(1 for d in all_docs if d.get("subject_code") in codes)
            level_stats += f"• Level {level}: {count} file(s)\n"
            
    except Exception as e:
        await message.answer(f"❌ Database error: {e}")
        return

    await message.answer(
        f"📊 *Bot Statistics*\n\n"
        f"📁 Total verified files: *{total}*\n\n"
        f"📚 By level:\n{level_stats}",
        parse_mode="Markdown"
    )

@dp.message(Command("countdown"))
async def cmd_countdown(message: types.Message):
    await track_user(message.from_user)
    exam_date = datetime(2026, 7, 15, 9, 0)
    now = datetime.now()
    
    if now > exam_date:
        await message.answer("🎉 Exams are over or currently ongoing! Best of luck!")
    else:
        diff = exam_date - now
        await message.answer(
            f"⏳ *Exam Countdown Tracker*\n\n"
            f"Remaining time until final exams:\n"
            f"👉 *{diff.days} Days and {diff.seconds // 3600} Hours*\n\n"
            f"Stay focused and keep studying! 🚀",
            parse_mode="Markdown"
        )

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    broadcast_msg = message.text.replace("/broadcast", "").strip()
    if not broadcast_msg:
        await message.answer("⚠️ Usage: `/broadcast <your message>`", parse_mode="Markdown")
        return

    try:
        count = 0
        async for u in users_col.stream(): # ASYNC STREAM
            try:
                await bot.send_message(chat_id=int(u.id), text=f"📢 *Important Announcement:*\n\n{broadcast_msg}", parse_mode="Markdown")
                count += 1
                await asyncio.sleep(0.05)
            except Exception:
                pass
        await message.answer(f"✅ Broadcast successfully delivered to {count} students!")
    except Exception as e:
        await message.answer(f"❌ Broadcast failed: {e}")

@dp.message(F.text == "🏆 Leaderboard")
@dp.message(Command("leaderboard"))
async def show_leaderboard(message: types.Message):
    await track_user(message.from_user)
    try:
        contributors = {}
        async for doc in files_col.stream(): # ASYNC STREAM
            data = doc.to_dict()
            name = data.get("uploader_name")
            if name and data.get("category") in ["Lecture Note", "Short Note"]:
                contributors[name] = contributors.get(name, 0) + 1
                
        if not contributors:
            await message.answer("🏆 *Leaderboard*\n\nNo community uploads yet! Be the first to share your notes.", parse_mode="Markdown")
            return
            
        sorted_list = sorted(contributors.items(), key=lambda x: x[1], reverse=True)[:10]
        text = "🏆 *Top Contributors Leaderboard*\n\n"
        medals = ["🥇", "🥈", "🥉"]
        for idx, (name, count) in enumerate(sorted_list):
            medal = medals[idx] if idx < 3 else "🏅"
            text += f"{medal} *{name}* — {count} Approved Notes\n"
            
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Error loading leaderboard: {e}")

# ==========================================
# 📤 User Document Upload (Async Writes)
# ==========================================
@dp.message(F.text == "📤 Upload Note")
async def process_upload_start(message: types.Message):
    await track_user(message.from_user)
    instructions = (
        "📤 *Community Resource Upload Guide*\n\n"
        "Students can upload **Lecture Notes** or **Short Notes** directly into this chat window. "
        "To ensure our validation system parses it properly, you **must rename your PDF** using the structure outlined below before sending:\n\n"
        "• 📂 *For Lecture Notes / Slides:*\n"
        "`SUBJECTCODE_NOTE_TopicName.pdf`\n"
        "↳ _Example: `TICT2142_NOTE_RequirementsEngineering.pdf`_\n\n"
        "• 📝 *For Student Short Notes:*\n"
        "`SUBJECTCODE_SNOTE_TopicName.pdf`\n"
        "↳ _Example: `TICT2142_SNOTE_NormalizationRules.pdf`_\n\n"
        "⚠️ *Note:* All community note submissions are held in a pending queue for Admin verification before going live. "
        "Past Papers can only be submitted via Batch Admins."
    )
    await message.answer(instructions, parse_mode="Markdown")


@dp.message(F.chat.type == "private", F.document)
async def handle_user_document_submission(message: types.Message):
    file_name = message.document.file_name
    telegram_file_id = message.document.file_id
    uploader_name = message.from_user.first_name
    uploader_id = message.from_user.id

    if not file_name.lower().endswith(".pdf"):
        await message.answer("❌ Only documents formatted as a **PDF file** are accepted.")
        return

    try:
        clean_name = file_name[:-4] 
        parts = clean_name.split("_")

        if len(parts) < 3:
            raise ValueError("Structure length mismatch")

        subject_code = parts[0].upper()
        doc_type = parts[1].upper()
        topic_title = " ".join(parts[2:])

        if subject_code not in SUBJECTS:
            await message.answer(f"❌ *Unknown Subject Code:* `{subject_code}`\nPlease verify your course code.")
            return

        if doc_type == "NOTE":
            category = "Lecture Note"
        elif doc_type == "SNOTE":
            category = "Short Note"
        else:
            raise ValueError("Invalid flag parameter")

        sanitized_topic = "".join(e for e in topic_title if e.isalnum())
        custom_id = f"{subject_code}_{doc_type}_{sanitized_topic}_{uploader_id}"

        pending_data = {
            "id": custom_id,
            "subject_code": subject_code,
            "category": category,
            "file_id": telegram_file_id,
            "file_name": file_name,
            "uploader_id": uploader_id,
            "uploader_name": uploader_name,
            "upload_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "topic": topic_title
        }

        # ASYNC SET TO DATABASE
        await pending_col.document(custom_id).set(pending_data)

        success_response = (
            f"📥 *Resource Submission Received!*\n\n"
            f"📚 *Classification:* {category}\n"
            f"🔑 *Module Code:* `{subject_code}`\n"
            f"📝 *Topic Name:* {topic_title}\n\n"
            f"⏳ Your file was forwarded to the verification staging environment. "
            f"You will get an automated alert once reviewed."
        )
        await message.answer(success_response, parse_mode="Markdown")

        admin_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Approve", callback_data=f"admin_approve_{custom_id}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"admin_reject_{custom_id}")
            ]
        ])
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_document(
                    chat_id=admin_id,
                    document=telegram_file_id,
                    caption=f"🛡️ *Staging Review Notification*\n\n"
                            f"👤 *Contributor:* {uploader_name}\n"
                            f"📚 *Subject:* {SUBJECTS[subject_code][0]} (`{subject_code}`)\n"
                            f"🔖 *Category:* {category}\n"
                            f"📝 *Topic:* {topic_title}",
                    parse_mode="Markdown",
                    reply_markup=admin_kb
                )
            except Exception:
                pass

    except ValueError:
        error_explanation = (
            "❌ *Invalid Structural Naming Rule!*\n\n"
            "Please apply the correct filename design architecture pattern before uploading:\n\n"
            "• **Lecture Notes:** `CODE_NOTE_Topic.pdf`\n"
            "• **Short Notes:** `CODE_SNOTE_Topic.pdf`"
        )
        await message.answer(error_explanation, parse_mode="Markdown")
    except Exception as e:
        print(f"❌ Structural parse failure: {e}")
        await message.answer("⚠️ System error encountered structural runtime validation failure mapping resource tokens.")

# ==========================================
# 🛡️ Admin Verification (Async Update)
# ==========================================
@dp.callback_query(F.data.startswith("admin_approve_"))
async def admin_approve_handler(callback: types.CallbackQuery):
    doc_id = callback.data.split("_")[2]
    doc_ref = pending_col.document(doc_id)
    doc = await doc_ref.get() # ASYNC GET

    if not doc.exists:
        await callback.answer("Resource already processed!", show_alert=True)
        return

    data = doc.to_dict()
    data["rating_sum"] = 0
    data["rating_count"] = 0
    data["semester"] = SUBJECTS[data["subject_code"]][2]
    
    # ASYNC SET & DELETE
    await files_col.document(doc_id).set(data)
    await doc_ref.delete()

    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n✅ *APPROVED BY ADMIN*")
    await callback.answer("Approved and added to database!")
    
    try:
        await bot.send_message(
            chat_id=data["uploader_id"],
            text=f"🎉 *Good News!*\nYour upload for `{data['subject_code']}` ({data['category']}) was approved and is now available to all students!",
            parse_mode="Markdown"
        )
    except Exception:
        pass

@dp.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject_handler(callback: types.CallbackQuery):
    doc_id = callback.data.split("_")[2]
    doc_ref = pending_col.document(doc_id)
    doc = await doc_ref.get() # ASYNC GET

    if not doc.exists:
        await callback.answer("Resource already processed!", show_alert=True)
        return

    data = doc.to_dict()
    await doc_ref.delete() # ASYNC DELETE

    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n❌ *REJECTED BY ADMIN*")
    await callback.answer("Upload rejected.")
    
    try:
        await bot.send_message(chat_id=data["uploader_id"], text=f"❌ Your upload for `{data['subject_code']}` was rejected during review.")
    except Exception:
        pass

# ==========================================
# ⭐ Student Rating Handler
# ==========================================
@dp.callback_query(F.data.startswith("rate_"))
async def process_rating(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    doc_id = parts[1]
    stars = int(parts[2])

    doc_ref = files_col.document(doc_id)
    doc = await doc_ref.get() # ASYNC GET

    if not doc.exists:
        await callback.answer("This file no longer exists.", show_alert=True)
        return

    data = doc.to_dict()
    new_sum = data.get("rating_sum", 0) + stars
    new_count = data.get("rating_count", 0) + 1
    
    await doc_ref.update({"rating_sum": new_sum, "rating_count": new_count}) # ASYNC UPDATE
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer(f"✅ You rated this note {stars} Stars! Thank you!", show_alert=True)

# ==========================================
# Paper Request Feature
# ==========================================
@dp.message(Command("request"))
async def manual_paper_request(message: types.Message):
    await track_user(message.from_user)
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Please specify the subject code.\nExample: `/request TICT2113`", parse_mode="Markdown")
        return
    
    code = parts[1].strip().upper()
    if code not in SUBJECTS:
        await message.answer(f"❌ Unknown subject code: `{code}`.\nPlease check the handbook and try again.", parse_mode="Markdown")
        return
        
    subject_name = SUBJECTS[code][0]
    user = message.from_user
    username_display = f"(@{user.username})" if user.username else ""

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"🙋‍♂️ *Manual Paper Request*\n\n"
                     f"👤 *Student:* {user.first_name} {username_display}\n"
                     f"📚 *Subject:* {subject_name}\n"
                     f"🔑 *Code:* `{code}`\n\n"
                     f"Please upload this to the channel when available.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    
    await message.answer(f"✅ Your request for *{subject_name}* (`{code}`) has been sent to the admins!", parse_mode="Markdown")

@dp.callback_query(F.data.startswith("req_"))
async def handle_inline_paper_request(callback: types.CallbackQuery):
    code = callback.data.split("_")[1]
    subject_name = SUBJECTS.get(code, ("Unknown",))[0]
    user = callback.from_user
    username_display = f"(@{user.username})" if user.username else ""

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"🙋‍♂️ *Paper Request (From Browse)*\n\n"
                     f"👤 *Student:* {user.first_name} {username_display}\n"
                     f"📚 *Subject:* {subject_name}\n"
                     f"🔑 *Code:* `{code}`\n\n"
                     f"Please upload this to the channel when available.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    
    await callback.answer("✅ Request sent successfully to the admins!", show_alert=True)
    
    await callback.message.edit_text(
        f"✅ Your request for *{subject_name}* (`{code}`) has been forwarded to the admins.\n\n"
        f"You will be able to download it here once it is uploaded.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back to Main Menu", callback_data="back_to_start")]
        ])
    )

# ==========================================
# Browse & Category Filtering
# ==========================================
@dp.callback_query(F.data == "browse")
async def browse(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📂 *Browse Resources*\n\nSelect your level:",
        reply_markup=get_level_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("level_"))
async def process_level(callback: types.CallbackQuery):
    level = callback.data.split("_")[1]
    await callback.message.edit_text(
        f"📗 *Level {level}*\n\nSelect a semester:",
        reply_markup=get_semester_keyboard(level),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("sem_"))
async def process_semester(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    semester, level = parts[1], parts[2]
    await callback.message.edit_text(
        f"📗 *Level {level} — Semester {semester}*\n\nHow would you like to proceed?",
        reply_markup=get_subject_action_keyboard(level, semester),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("bysubject_"))
async def by_subject(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    level, semester = parts[1], parts[2]
    subjects = get_subjects_for(int(level), int(semester))

    text = f"📚 *Level {level} — Semester {semester}*\n\nSelect a subject:\n\n"
    for code, name in subjects.items():
        text += f"• `{code}` — {name}\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_subjects_keyboard(level, semester),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("subject_"))
async def process_subject(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    code, level, semester = parts[1], parts[2], parts[3]
    subject_name = SUBJECTS.get(code, ("Unknown",))[0]

    await callback.message.edit_text(
        f"📚 *{subject_name}* (`{code}`)\n\nSelect a category to browse:",
        reply_markup=get_category_menu(code, level, semester),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("subcat_"))
async def handle_subcategory_view(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    category = parts[1]
    code = parts[2]
    level = parts[3]
    semester = parts[4]
    subject_name = SUBJECTS.get(code, ("Unknown",))[0]

    if category == "Past Paper":
        # දැන් get_year_keyboard එක async නිසා await කරන්න ඕනේ
        keyboard = await get_year_keyboard(code, level, semester) 
        if not keyboard:
            request_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🙋‍♂️ Request this Subject", callback_data=f"req_{code}")],
                [InlineKeyboardButton(text="⬅️ Back", callback_data=f"subject_{code}_{level}_{semester}")]
            ])
            await callback.message.edit_text(
                f"⚠️ No past papers found for *{subject_name}* (`{code}`) yet.\n\n"
                f"Would you like to request the admins to upload it?",
                parse_mode="Markdown",
                reply_markup=request_kb
            )
            return

        await callback.message.edit_text(
            f"📚 *{subject_name}* - Past Papers\n`{code}`\n\nSelect a year:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        try:
            query = files_col.where(filter=FieldFilter("subject_code", "==", code)).where(filter=FieldFilter("category", "==", category))
            results = []
            
            # ASYNC STREAM
            async for doc in query.stream():
                results.append(doc)
        except Exception as e:
            await callback.message.answer(f"❌ Database error: {e}")
            return

        if not results:
            back_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Back", callback_data=f"subject_{code}_{level}_{semester}")]
            ])
            await callback.message.edit_text(
                f"⚠️ No {category}s found for *{subject_name}* (`{code}`) yet.\n\n"
                f"Be the first to share by tapping *📤 Upload Note*!",
                parse_mode="Markdown",
                reply_markup=back_kb
            )
            return

        await callback.message.answer(f"📥 Sending available {category}s for `{code}`...")
        for doc in results:
            data = doc.to_dict()
            doc_id = doc.id
            
            rating_str = ""
            if data.get("rating_count", 0) > 0:
                avg = round(data["rating_sum"] / data["rating_count"], 1)
                rating_str = f"\n⭐ Rating: {avg}/5.0 ({data['rating_count']} votes)"

            uploader_str = f"\n👤 Uploaded by: {data.get('uploader_name', 'Faculty Admin')}"
            caption = f"📄 *{data.get('file_name', 'Resource Document')}*\n`{code}` | {category}{uploader_str}{rating_str}"
            
            kb = get_rating_keyboard(doc_id) if category == "Short Note" else None
            
            await bot.send_document(
                chat_id=callback.from_user.id,
                document=data["file_id"],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=kb
            )
        await callback.answer()

# ==========================================
# Async Bulk Download
# ==========================================
@dp.callback_query(F.data.startswith("dlall_"))
async def download_all(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    level, semester = parts[1], parts[2]
    subjects = get_subjects_for(int(level), int(semester))
    subject_codes = list(subjects.keys())

    try:
        query = files_col.where(filter=FieldFilter("subject_code", "in", subject_codes)).where(filter=FieldFilter("category", "==", "Past Paper"))
        results = []
        
        # ASYNC STREAM
        async for doc in query.stream():
            results.append(doc.to_dict())
    except Exception as e:
        await callback.message.answer(f"❌ Database error: {e}")
        await callback.answer()
        return

    if not results:
        request_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data=f"level_{level}")]
        ])
        await callback.message.edit_text(
            f"⚠️ No papers found for Level {level} Semester {semester} yet.\n\n"
            f"Please browse by individual subject to request missing papers.",
            parse_mode="Markdown",
            reply_markup=request_kb
        )
        await callback.answer()
        return

    await callback.message.answer(
        f"📥 *Sending all past papers for Level {level} — Semester {semester}*\n"
        f"Found *{len(results)}* paper(s). Please wait...",
        parse_mode="Markdown"
    )

    for r in results:
        subject_name = SUBJECTS.get(r["subject_code"], ("Unknown",))[0]
        p_type = r.get("paper_type", "Standard")
        type_label = ""
        if p_type == "Theory":
            type_label = " 📚 [Theory]"
        elif p_type == "Practical":
            type_label = " 💻 [Practical]"

        await bot.send_document(
            chat_id=callback.from_user.id,
            document=r["file_id"],
            caption=f"📄 *{subject_name}*{type_label}\n"
                    f"`{r['subject_code']}` | Year {r['year']} | Sem {r['semester']}",
            parse_mode="Markdown"
        )
    await callback.answer()

# ==========================================
# Download Single Paper
# ==========================================
@dp.callback_query(F.data.startswith("get_"))
async def download_file(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    code, year, semester = parts[1], parts[2], parts[3]
    subject_name = SUBJECTS.get(code, ("Unknown",))[0]

    try:
        query = files_col.where(filter=FieldFilter("subject_code", "==", code)).where(filter=FieldFilter("year", "==", year)).where(filter=FieldFilter("category", "==", "Past Paper"))
        db_results = []
        
        # ASYNC STREAM
        async for doc in query.stream():
            db_results.append(doc.to_dict())
    except Exception as e:
        await callback.message.answer(f"❌ Database error: {e}")
        await callback.answer()
        return

    if db_results:
        await callback.answer(text="📄 Downloading past paper(s)...", show_alert=False)
        for doc in db_results:
            p_type = doc.get("paper_type", "Standard")
            type_label = ""
            if p_type == "Theory":
                type_label = " 📚 [Theory]"
            elif p_type == "Practical":
                type_label = " 💻 [Practical]"
                
            await bot.send_document(
                chat_id=callback.from_user.id,
                document=doc["file_id"],
                caption=f"📄 *{subject_name}*{type_label}\n"
                        f"`{code}` | Year {year} | Sem {semester}",
                parse_mode="Markdown"
            )
    else:
        await callback.message.answer(f"⚠️ No paper found for *{subject_name}* ({year}).", parse_mode="Markdown")
        await callback.answer()

# ==========================================
# Fuzzy Search
# ==========================================
@dp.callback_query(F.data == "search")
async def search_prompt(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"🔍 *Search by Subject Code or Name*\n\n"
        f"Type the subject code or keywords and send:\n\n"
        f"Example: `TICT2113` or `Data Structures`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_start")]
        ])
    )
    await callback.answer()

@dp.message(F.text)
async def handle_search(message: types.Message):
    query = message.text.strip()

    if query.startswith("/"):
        return

    if query in ["📂 Browse Resources", "🔍 Search Subject", "📊 Bot Statistics", "🙋‍♂️ Request Paper", "📤 Upload Note", "🏆 Leaderboard"]:
        return

    choices = {}
    for code, info in SUBJECTS.items():
        choice_str = f"{code} {info[0]}"
        choices[choice_str] = code

    extracts = process.extract(query, choices.keys(), limit=5)
    valid_matches = [match for match in extracts if match[1] >= 50]

    if not valid_matches:
        await message.answer(
            f"❌ No matching subjects found for *\"{query}\"*.\n\n"
            f"💡 Try keywords like `Programming`, `Database` or code like `TICT2113`.",
            parse_mode="Markdown"
        )
        return

    buttons = []
    for choice_text, score in valid_matches:
        code = choices[choice_text]
        name, level, semester = SUBJECTS[code]
        
        buttons.append([InlineKeyboardButton(
            text=f"📚 {code} - {name}",
            callback_data=f"subject_{code}_{level}_{semester}"
        )])
        
    buttons.append([InlineKeyboardButton(text="⬅️ Back to Main Menu", callback_data="back_to_start")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(
        f"🔍 *Search Results for \"{query}\":*\n"
        f"Select a subject below to browse resources:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ==========================================
# Channel Post Auto-Approval
# ==========================================
@dp.channel_post(F.document)
async def handle_channel_upload(post: types.Message):
    print(f"📢 Admin Channel post received! File: {post.document.file_name}")

    current_chat_id = str(post.chat.id)
    current_username = f"@{post.chat.username}" if post.chat.username else ""

    if str(CHANNEL_ID) not in [current_chat_id, current_username]:
        return

    file_name = post.document.file_name
    telegram_file_id = post.document.file_id

    if not file_name.lower().endswith(".pdf"):
        return

    try:
        clean_name = file_name[:-4] 
        parts = clean_name.split("_")

        if len(parts) < 2:
            raise ValueError("File name format mismatch.")

        subject_code = parts[0].upper()
        year = parts[1]

        if subject_code not in SUBJECTS:
            await bot.send_message(
                chat_id=post.chat.id,
                text=f"❌ *Unknown subject code:* `{subject_code}`",
                parse_mode="Markdown"
            )
            return

        semester = SUBJECTS[subject_code][2]
        subject_name = SUBJECTS[subject_code][0]

        paper_type = "Standard"
        if len(parts) > 2:
            last_part = parts[-1].upper()
            if last_part == 'T':
                paper_type = "Theory"
            elif last_part == 'P':
                paper_type = "Practical"

        custom_id = f"{subject_code}_{year}_{paper_type}"
        
        document_data = {
            "id": custom_id,
            "subject_code": subject_code,
            "year": year,
            "semester": semester,
            "paper_type": paper_type,
            "category": "Past Paper",
            "file_id": telegram_file_id,
            "file_name": file_name,
            "uploader_id": post.chat.id,
            "uploader_name": "Batch Admin",
            "upload_date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

        # ASYNC SET
        await files_col.document(custom_id).set(document_data)
        print(f"✅ Past Paper Auto-Approved and Published: {custom_id}")

        await bot.send_message(
            chat_id=post.chat.id,
            text=f"🚀 *Resource Published Live Successfully!*\n\n"
                 f"📚 *Subject:* {subject_name}\n"
                 f"🔑 *Code:* `{subject_code}`\n"
                 f"📅 *Year:* {year}",
            parse_mode="Markdown"
        )

    except ValueError:
        await bot.send_message(
            chat_id=post.chat.id,
            text=f"❌ *Invalid past paper layout:* `{file_name}`\n\n"
                 f"💡 Rule structures:\n"
                 f"`SUBJECTCODE_YEAR.pdf`\n"
                 f"`SUBJECTCODE_YEAR_T.pdf`",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"❌ Error during channel sync: {e}")

# ==========================================
# Run Bot 
# ==========================================
async def main():
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiogram.exceptions import TelegramNetworkError

    print("Bot is starting up. Connecting to Async Firebase... 🚀")

    session = AiohttpSession(timeout=120.0)
    custom_bot = Bot(token=BOT_TOKEN, session=session)

    retry_count = 0
    max_retries = 5

    while retry_count < max_retries:
        try:
            me = await custom_bot.get_me()
            print(f"✅ Bot successfully connected! Username: @{me.username}")

            try:
                chat = await custom_bot.get_chat(CHANNEL_ID)
                print(f"✅ Channel found: {chat.title}")
            except Exception as e:
                print(f"⚠️ Channel access info: {e}")

            print("Bot is now actively polling for messages... 🔄")
            await dp.start_polling(
                custom_bot,
                allowed_updates=[
                    "message",
                    "channel_post",
                    "callback_query",
                    "edited_channel_post",
                    "edited_message"
                ]
            )
            break

        except TelegramNetworkError as net_err:
            retry_count += 1
            print(f"🔴 Network Error (Attempt {retry_count}/{max_retries}): {net_err}")
            print("⏳ Retrying in 10 seconds...")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")
            break
            
    if retry_count == max_retries:
         print("❌ Failed to connect to Telegram after multiple attempts.")

if __name__ == "__main__":
    asyncio.run(main())
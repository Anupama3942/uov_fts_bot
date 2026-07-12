import os
import asyncio
from datetime import datetime
from thefuzz import process

# Async Firestore client and filters
from google.cloud.firestore import AsyncClient
from google.cloud.firestore_v1.base_query import FieldFilter
# from google.cloud.firestore_v1.aggregation import AggregationQuery
from aiogram.client.session.aiohttp import AiohttpSession

from aiogram import Bot, Dispatcher, types, F
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton,InputMediaDocument
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  
FIREBASE_KEY_PATH = os.getenv("FIREBASE_KEY_PATH", "firebase.json")
ADMIN_GROUP_ID = os.getenv("ADMIN_GROUP_ID")

# Initialize bot and dispatcher
session = AiohttpSession(timeout=120.0)
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher()

# ==========================================
# Async Firestore Initialization
# ==========================================
import json

if os.path.exists(FIREBASE_KEY_PATH):
    db = AsyncClient.from_service_account_json(FIREBASE_KEY_PATH)
else:
    _creds_json = os.getenv("FIREBASE_CREDENTIALS")
    if not _creds_json:
        raise RuntimeError(
            "❌ Firebase credentials not found!\n"
            "   firebase.json file එකක් නෑ.\n"
            "   FIREBASE_CREDENTIALS environment variable ද set නෑ.\n"
            "   .env file එකේ FIREBASE_CREDENTIALS='{...}' add කරන්න."
        )
    db = AsyncClient.from_service_account_info(json.loads(_creds_json))

# Database Collections
files_col = db.collection("academic_resources")
pending_col = db.collection("pending_resources")
users_col = db.collection("bot_users")

# ==========================================
# Verified Course List (SUBJECTS)
# ==========================================
from subjects import SUBJECTS

# ==========================================
# Dynamic Admin Checker
# ==========================================
async def is_admin(user_id: int) -> bool:
    """Check whether the user is an admin based on the 'admins' collection."""
    doc = await db.collection("admins").document(str(user_id)).get()
    return doc.exists

def get_subjects_for(level: int, semester: int):
    return {
        code: info[0]
        for code, info in SUBJECTS.items()
        if info[1] == level and info[2] == semester
    }

# ==========================================
# Async User Tracking
# ==========================================
async def track_user(user: types.User):
    # Ban check
    ban_doc = await db.collection("banned_users").document(str(user.id)).get()
    if ban_doc.exists:
        raise Exception("BANNED") 

    doc_ref = users_col.document(str(user.id))
    doc = await doc_ref.get() 
    if not doc.exists:
        await doc_ref.set({ 
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

async def get_year_keyboard(code: str, level: str, semester: str):
    try:
        query = files_col.where(filter=FieldFilter("subject_code", "==", code)).where(filter=FieldFilter("category", "==", "Past Paper"))
        years = set()
        
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
# Optimized Async Bot Statistics (NO DB LOOP)
# ==========================================
@dp.message(F.text == "📊 Bot Statistics")
async def process_persistent_stats(message: types.Message):
    await track_user(message.from_user)
    if not await is_admin(message.from_user.id):
        return await message.answer("❌ This feature is reserved for Administrators only.")

    try:
        count_query = await files_col.count().get()
        total = count_query[0][0].value
        
        level_stats = ""
        # Chunked Count Queries (Does NOT download the entire database)
        for level in [1, 2, 3, 4]:
            codes = [c for c, info in SUBJECTS.items() if info[1] == level]
            lvl_total = 0
            
            # Firestore 'in' query limit is 10, so we split codes into chunks
            for i in range(0, len(codes), 10):
                chunk = codes[i:i+10]
                if chunk:
                    chunk_query = await files_col.where(filter=FieldFilter("subject_code", "in", chunk)).count().get()
                    lvl_total += chunk_query[0][0].value
            
            level_stats += f"• Level {level}: {lvl_total} file(s)\n"
            
        await message.answer(
            f"📊 *Bot Statistics*\n\n📁 Total verified files: *{total}*\n\n📚 By level:\n{level_stats}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ Database error: {e}")

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
    if not await is_admin(message.from_user.id):
        return
        
    broadcast_msg = message.text.replace("/broadcast", "").strip()
    if not broadcast_msg:
        await message.answer("⚠️ Usage: `/broadcast <your message>`", parse_mode="Markdown")
        return

    try:
        count = 0
        async for u in users_col.stream(): 
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
        async for doc in files_col.stream(): 
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
# NEW FSM Interactive Upload Wizard (Easy Upload)
# ==========================================
class UploadForm(StatesGroup):
    waiting_for_subject = State()
    waiting_for_category = State()
    waiting_for_file = State()

@dp.message(F.text == "📤 Upload Note")
async def process_upload_start(message: types.Message, state: FSMContext):
    await track_user(message.from_user)
    await state.set_state(UploadForm.waiting_for_subject)
    
    instructions = (
        "📤 *Interactive Upload Wizard*\n\n"
        "Let's share your resource easily!\n\n"
        "👉 **Step 1:** Please type the **Subject Code** for your note (e.g., `TICT2113`).\n\n"
        "*(Type /cancel at any time to abort the upload process)*"
    )
    # Temporary keyboard during FSM
    await message.answer(
        instructions, 
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="/cancel")]], resize_keyboard=True)
    )

@dp.message(Command("cancel"))
async def cancel_wizard(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
        await message.answer("⚠️ Upload process cancelled.", reply_markup=get_persistent_main_menu())
    else:
        await message.answer("No active process to cancel.")

@dp.message(UploadForm.waiting_for_subject)
async def process_upload_subject(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        return

# cant send photos, stickers, or files as subject code
    if not message.text:
        await message.answer(
            "❌ Please type the **Subject Code** as text (e.g. `TICT2113`).\n"
            "Photos, stickers, and files are not accepted here.\n"
            "Or type /cancel to stop.",
            parse_mode="Markdown"
        )
        return

    subject_code = message.text.strip().upper()
    
    if subject_code not in SUBJECTS:
        await message.answer("❌ Invalid Subject Code. Please check the handbook and try again, or type /cancel.")
        return
    
    await state.update_data(subject_code=subject_code)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍🏫 Lecture Note", callback_data="upcat_Lecture Note")],
        [InlineKeyboardButton(text="📝 Student Short Note", callback_data="upcat_Short Note")]
    ])
    
    await state.set_state(UploadForm.waiting_for_category)
    await message.answer(
        f"✅ Subject set to: *{SUBJECTS[subject_code][0]}* (`{subject_code}`)\n\n"
        f"👉 **Step 2:** Select the category of this file:", 
        reply_markup=keyboard, 
        parse_mode="Markdown"
    )

@dp.callback_query(UploadForm.waiting_for_category, F.data.startswith("upcat_"))
async def process_upload_category(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    category = "_".join(parts[1:])
    await state.update_data(category=category)
    await state.set_state(UploadForm.waiting_for_file)
    
    await callback.message.edit_text(
        f"✅ Category set to: *{category}*\n\n"
        f"👉 **Step 3:** Finally, please **send/upload the PDF Document** into this chat.", 
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(UploadForm.waiting_for_file, F.text)
async def handle_wrong_input_in_file_state(message: types.Message):
    await message.answer(
        "📎 Please **send a PDF file**, not text.\n"
        "Or type /cancel to abort the upload.",
        parse_mode="Markdown"
    )

@dp.message(UploadForm.waiting_for_file, F.document)
async def handle_wizard_document(message: types.Message, state: FSMContext):
    file_name = message.document.file_name
    
    if not file_name.lower().endswith(".pdf"):
        await message.answer("❌ Only **PDF files** are accepted. Please send a PDF or type /cancel.")
        return

    user_data = await state.get_data()
    subject_code = user_data['subject_code']
    category = user_data['category']
    
    telegram_file_id = message.document.file_id
    topic_title = file_name[:-4] 
    uploader_name = message.from_user.first_name
    uploader_id = message.from_user.id
    
    # Safe doc ID generation
    doc_id = f"up_{message.message_id}_{uploader_id}"
    
    pending_data = {
        "id": doc_id,
        "subject_code": subject_code,
        "category": category,
        "topic_title": topic_title,
        "file_id": telegram_file_id,
        "file_name": file_name,
        "uploader_id": uploader_id,
        "uploader_name": uploader_name,
        "upload_date": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    # Save to Firestore pending queue
    await pending_col.document(doc_id).set(pending_data)
    
    # Clear the wizard state
    await state.clear()
    
    success_text = (
        f"📥 *Resource Submitted Successfully!*\n\n"
        f"📚 *Subject:* {SUBJECTS[subject_code][0]}\n"
        f"🔖 *Category:* {category}\n"
        f"📄 *File:* `{file_name}`\n\n"
        f"⏳ Your file has been sent to the Admin Team for verification. Thank you for contributing! 🚀"
    )
    # Return main keyboard to user
    await message.answer(success_text, parse_mode="Markdown", reply_markup=get_persistent_main_menu())

    # Forward dynamically to Admin Group for Approval
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=f"admin_approve_{doc_id}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"admin_reject_{doc_id}")
        ]
    ])
    
    try:
        await bot.send_document(
            chat_id=ADMIN_GROUP_ID,
            document=telegram_file_id,
            caption=f"🛡️ *Staging Review Notification*\n\n"
                    f"👤 *Contributor:* {uploader_name}\n"
                    f"📚 *Subject:* {SUBJECTS[subject_code][0]} (`{subject_code}`)\n"
                    f"🔖 *Category:* {category}\n"
                    f"📝 *File:* {file_name}",
            parse_mode="Markdown",
            reply_markup=admin_kb
        )
    except Exception as e:
        print(f"Failed to alert admin group. Ensure ADMIN_GROUP_ID is correct and bot is an admin in the group. Error: {e}")

# ==========================================
# Admin Verification (Async Update via Group)
# ==========================================
@dp.callback_query(F.data.startswith("admin_approve_"))
async def admin_approve_handler(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ You are not authorized to approve notes!", show_alert=True)
        return

    # Using join to safely handle underscores in IDs if any
    doc_id = "_".join(callback.data.split("_")[2:])
    doc_ref = pending_col.document(doc_id)
    doc = await doc_ref.get() 

    if not doc.exists:
        await callback.answer("Resource already processed by another admin!", show_alert=True)
        return

    data = doc.to_dict()

    # Past papers must NOT be approved in the bot group due to missing year/type fields; admins must use the web dashboard for that.
    if data.get("category") == "Past Paper":
        await callback.answer(
            "⚠️ Past Papers must be approved via the Admin Panel web dashboard.\n"
            "Reason: Year and Paper Type fields are required and must be filled manually.",
            show_alert=True
        )
        return

    data["rating_sum"] = 0
    data["rating_count"] = 0
    data["semester"] = SUBJECTS[data["subject_code"]][2]

    await files_col.document(doc_id).set(data)
    await doc_ref.delete()

    admin_name = callback.from_user.first_name
    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n✅ *APPROVED BY {admin_name}*")
    await callback.answer("Approved and added to database!")
    
    try:
        await bot.send_message(
            chat_id=data["uploader_id"],
            text=f"🎉 *Good News!*\nYour upload for `{data['subject_code']}` ({data['category']}) was approved and is now live!",
            parse_mode="Markdown"
        )
    except Exception:
        pass

@dp.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject_handler(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ You are not authorized to reject notes!", show_alert=True)
        return

    doc_id = "_".join(callback.data.split("_")[2:])
    doc_ref = pending_col.document(doc_id)
    doc = await doc_ref.get() 

    if not doc.exists:
        await callback.answer("Resource already processed by another admin!", show_alert=True)
        return

    data = doc.to_dict()
    await doc_ref.delete() 

    admin_name = callback.from_user.first_name 
    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n❌ *REJECTED BY {admin_name}*")
    await callback.answer("Upload rejected.")
    
    try:
        await bot.send_message(chat_id=data["uploader_id"], text=f"❌ Your upload for `{data['subject_code']}` was rejected during review.")
    except Exception:
        pass

# ==========================================
# Student Rating Handler
# ==========================================
@dp.callback_query(F.data.startswith("rate_"))
async def process_rating(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    # doc_id is everything in between 'rate' and 'stars'
    doc_id = "_".join(parts[1:-1]) 
    stars = int(parts[-1])

    doc_ref = files_col.document(doc_id)
    doc = await doc_ref.get() 

    if not doc.exists:
        await callback.answer("This file no longer exists.", show_alert=True)
        return

    data = doc.to_dict()

    # Check if the user has already rated this note
    rated_by = data.get("rated_by", [])
    if callback.from_user.id in rated_by:
        await callback.answer("⚠️ You have already rated this note!", show_alert=True)
        return

    new_sum = data.get("rating_sum", 0) + stars
    new_count = data.get("rating_count", 0) + 1

    await doc_ref.update({
        "rating_sum": new_sum,
        "rating_count": new_count,
        "rated_by": rated_by + [callback.from_user.id]
    })

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

    try:
        await bot.send_message(
            chat_id=ADMIN_GROUP_ID,
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

    try:
        await bot.send_message(
            chat_id=ADMIN_GROUP_ID,
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

# ==========================================
# handle_subcategory_view Function
# ==========================================
@dp.callback_query(F.data.startswith("subcat_"))
async def handle_subcategory_view(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    
    # 1. FIXED VARIABLE NAMES & CATEGORY EXTRACTION
    level = parts[-2]
    semester = parts[-1]
    code = parts[-3]  # Changed 'subject_code' to 'code' to match your logic below
    
    # Reconstruct category safely (Fixes "Short_Note" split bug)
    category = "_".join(parts[1:-3]) 
    
    # Get subject name, default to "Unknown" if not found
    subject_name = SUBJECTS.get(code, ("Unknown",))[0]

    # --- PAST PAPERS LOGIC ---
    if category == "Past Paper":
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
        
    # --- OTHER RESOURCES LOGIC ---
    else:
        try:
            # Query Firestore for resources
            query = files_col.where(filter=FieldFilter("subject_code", "==", code)).where(filter=FieldFilter("category", "==", category))
            results = []
            
            async for doc in query.stream():
                results.append(doc.to_dict())
        except Exception as e:
            await callback.message.answer(f"❌ Database error: {e}")
            return

        # If no resources found
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
        
        # Chat Flood Fix via MediaGroup (For Lecture Notes)
        if category == "Short Note":
            # Keep individual messages for short notes to preserve inline rating buttons
            for data in results:
                rating = f"\n⭐ Rating: {round(data['rating_sum']/data['rating_count'], 1)}/5.0" if data.get("rating_count", 0) > 0 else ""
                caption = f"📄 *{data.get('topic_title', data.get('file_name', 'Resource'))}*\n`{code}` | {category}\n👤 By: {data.get('uploader_name', 'Admin')}{rating}"
                
                # Make sure you are using 'bot.send_document' globally
                await bot.send_document(
                    chat_id=callback.from_user.id, 
                    document=data["file_id"], 
                    caption=caption, 
                    parse_mode="Markdown", 
                    reply_markup=get_rating_keyboard(data["id"])
                )
        else:
            # Group into chunks of 10 to avoid spamming (MediaGroup)
            media_group = []
            for data in results:
                caption = f"📄 *{data.get('topic_title', data.get('file_name', 'Resource'))}*\n`{code}` | {category}\n👤 By: {data.get('uploader_name', 'Admin')}"
                media_group.append(InputMediaDocument(media=data["file_id"], caption=caption, parse_mode="Markdown"))
            
            # Send in chunks of 10
            for i in range(0, len(media_group), 10):
                chunk = media_group[i:i+10]
                
                # 2. FIXED: Telegram crashes if a MediaGroup has only 1 item.
                if len(chunk) == 1:
                    await bot.send_document(
                        chat_id=callback.from_user.id,
                        document=chunk[0].media,
                        caption=chunk[0].caption,
                        parse_mode="Markdown"
                    )
                else:
                    await bot.send_media_group(chat_id=callback.from_user.id, media=chunk)
                
        await callback.answer()

# ==========================================
# Async Bulk Download
# ==========================================
@dp.callback_query(F.data.startswith("dlall_"))
async def download_all(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    level, semester = parts[1], parts[2]
    subject_codes = list(get_subjects_for(int(level), int(semester)).keys())

    results = []
    # Process chunks of 10 for Firestore 'in' query limitations
    for i in range(0, len(subject_codes), 10):
        chunk = subject_codes[i:i+10]
        async for doc in files_col.where(filter=FieldFilter("subject_code", "in", chunk)).where(filter=FieldFilter("category", "==", "Past Paper")).stream():
            results.append(doc.to_dict())

    if not results:
        return await callback.message.edit_text(f"⚠️ No papers found for Level {level} Semester {semester}.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data=f"level_{level}")]]))

    await callback.message.answer(f"📥 *Sending {len(results)} past paper(s)...*\nPlease wait.", parse_mode="Markdown")

    # MediaGroup chunks of 10
    media_group = []
    for r in results:
        p_type = r.get("paper_type", "Standard")
        type_label = " 📚 [Theory]" if p_type == "Theory" else " 💻 [Practical]" if p_type == "Practical" else ""
        caption = f"📄 *{SUBJECTS.get(r['subject_code'], ('Unknown',))[0]}*{type_label}\n`{r['subject_code']}` | Year {r['year']} | Sem {r['semester']}"
        media_group.append(InputMediaDocument(media=r["file_id"], caption=caption, parse_mode="Markdown"))

    for i in range(0, len(media_group), 10):
        chunk = media_group[i:i+10]
        if len(chunk) == 1:
            await bot.send_document(
                chat_id=callback.from_user.id,
                document=chunk[0].media,
                caption=chunk[0].caption,
                parse_mode="Markdown"
            )
        else:
            await bot.send_media_group(chat_id=callback.from_user.id, media=chunk)

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
@dp.message(F.text)
async def handle_search(message: types.Message, state: FSMContext):

    current_state = await state.get_state()
    if current_state is not None:
        return

    query = (message.text or "").strip()

    if not query:
        return

    if query.startswith("/"):
        return

    # PERMANENT FIX: Forgiving ignore list
    # Checks if the text contains any of our menu keywords or emojis
    ignore_keywords = ["browse", "search", "statistics", "request", "upload", "leaderboard", "📂", "🔍", "📊", "🙋‍♂️", "📤", "🏆"]
    
    if any(keyword in query.lower() for keyword in ignore_keywords):
        # If an old button is pressed, gently ask them to refresh the menu
        await message.answer(
            "🔄 It looks like you are using an old menu button.\n"
            "Please type /start to refresh your keyboard!", 
            reply_markup=get_persistent_main_menu()
        )
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

        await files_col.document(custom_id).set(document_data)

        await bot.send_message(
            chat_id=post.chat.id,
            text=f"🚀 *Resource Published Live Successfully!*\n\n"
                 f"📚 *Subject:* {subject_name}\n"
                 f"🔑 *Code:* `{subject_code}`\n"
                 f"📅 *Year:* {year}",
            parse_mode="Markdown"
        )

    except ValueError:
        pass
    except Exception as e:
        print(f"❌ Error during channel sync: {e}")

# ==========================================
# Run Bot 
# ==========================================
async def main():
    print("Bot is starting up. Connecting to Async Firebase... 🚀")
    retry_count = 0
    max_retries = 5

    while retry_count < max_retries:
        try:
            me = await bot.get_me() 
            print(f"✅ Bot successfully connected! Username: @{me.username}")

            print("Bot is now actively polling for messages... 🔄")
            await dp.start_polling(
                bot, 
                allowed_updates=["message", "channel_post", "callback_query", "edited_channel_post", "edited_message"]
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
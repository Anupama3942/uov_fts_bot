import os
import ssl
import asyncio
from thefuzz import process
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # @username format

# Admin Telegram User IDs
ADMIN_IDS = [1650090885]

# Connect Bot and Database
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

cluster = MongoClient(MONGO_URI)
db = cluster["faculty_database"]
files_col = db["academic_resources"]

# ==========================================
# Verified Course List (from 2020 Handbook)
# ==========================================

SUBJECTS = {
    # LEVEL 1 - Semester 1
    "TICT1114": ("Essentials of ICT", 1, 1),
    "TICT1123": ("Mathematics for Technology", 1, 1),
    "TICT1134": ("Fundamentals for Computer Programming", 1, 1),
    "TICT1142": ("Fundamentals of Web Technologies", 1, 1),
    "TICT1152": ("Principles of Management", 1, 1),
    "AUX1113":  ("English Language I", 1, 1),
    # LEVEL 1 - Semester 2
    "TICT1233": ("Operating Systems", 1, 2),
    "TICT1243": ("Electronics and Digital Circuit Designs", 1, 2),
    
    # LEVEL 2 - Semester 1
    "TICT2113": ("Data Structures and Algorithms", 2, 1),
    "TICT2134": ("Advanced Computer Programming", 2, 1),
    "TICT2153": ("Human Computer Interaction", 2, 1),
    "AUX2113":  ("English Language II", 2, 1),
    # LEVEL 2 - Semester 2
    "TICT2222": ("Introduction to Computer Network", 2, 2),
    "TICT2233": ("Database Management Systems", 2, 2),
    
    # LEVEL 3 - Semester 1
    "TICT3123": ("Advanced Database Management Systems", 3, 1),
    "TICT3132": ("Advanced Web Technologies", 3, 1),
    "TICT3142": ("Social and Professional Issues in IT", 3, 1),
    "TICT3153": ("Software Engineering", 3, 1),
    # LEVEL 3 - Semester 2
    "TICT3232": ("Software Quality Assurance", 3, 2),
    "AUX3211":  ("Research Methodology and Scientific Writing", 3, 2),
    
    # LEVEL 4 - Semester 2
    "TICT4242": ("Mobile Application Development", 4, 2)
}

def get_subjects_for(level: int, semester: int):
    return {
        code: info[0]
        for code, info in SUBJECTS.items()
        if info[1] == level and info[2] == semester
    }

# ==========================================
# Keyboards
# ==========================================

def get_persistent_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📂 Browse Papers"), KeyboardButton(text="🔍 Search Subject")],
            [KeyboardButton(text="🙋‍♂️ Request Paper"), KeyboardButton(text="📊 Bot Statistics")]
        ],
        resize_keyboard=True,
        is_persistent=True,
        placeholder="Select an option from the menu..."
    )

def get_start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Browse Papers", callback_data="browse")],
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
        [InlineKeyboardButton(
            text="📥 Download All Papers",
            callback_data=f"dlall_{level}_{semester}"
        )],
        [InlineKeyboardButton(
            text="📚 Browse by Subject",
            callback_data=f"bysubject_{level}_{semester}"
        )],
        [InlineKeyboardButton(text="⬅️ Back", callback_data=f"level_{level}")]
    ])

def get_subjects_keyboard(level: str, semester: str):
    subjects = get_subjects_for(int(level), int(semester))
    buttons = []
    row = []
    for code in subjects:
        row.append(InlineKeyboardButton(
            text=code,
            callback_data=f"subject_{code}_{level}_{semester}"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(
        text="⬅️ Back",
        callback_data=f"sem_{semester}_{level}"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_year_keyboard(code: str, level: str, semester: str):
    try:
        available_years = files_col.distinct("year", {"subject_code": code})
        available_years.sort(reverse=True)
    except Exception:
        available_years = []

    if not available_years:
        return None

    buttons = []
    row = []
    for year in available_years:
        row.append(InlineKeyboardButton(
            text=f"📅 {year}",
            callback_data=f"get_{code}_{year}_{semester}"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(
        text="⬅️ Back",
        callback_data=f"bysubject_{level}_{semester}"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ==========================================
# Start and Main Menu Handlers
# ==========================================

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        f"👋 Welcome {message.from_user.first_name}!\n\n"
        f"📚 *University Faculty Resource Bot*\n"
        f"Access past papers and notes easily.\n\n"
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

@dp.message(F.text == "📂 Browse Papers")
async def process_persistent_browse(message: types.Message):
    await message.answer(
        "📂 *Browse Papers*\n\nSelect your level:",
        reply_markup=get_level_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(F.text == "🔍 Search Subject")
async def process_persistent_search(message: types.Message):
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
    await message.answer(
        "🙋‍♂️ *How to request a paper:*\n\n"
        "1. Use the *📂 Browse Papers* or *🔍 Search Subject* buttons to find your subject.\n"
        "2. If no papers are found, a **[🙋‍♂️ Request this Subject]** button will appear.\n"
        "3. Click it, and the admins will be notified instantly!\n\n"
        "Alternatively, you can manually request by typing:\n"
        "`/request SUBJECT_CODE` (e.g., `/request TICT2113`)",
        parse_mode="Markdown"
    )

@dp.message(F.text == "📊 Bot Statistics")
async def process_persistent_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ This feature is reserved for Administrators only.")
        return

    try:
        total = files_col.count_documents({})
        level_stats = ""
        for level in [1, 2, 3, 4]:
            codes = [c for c, info in SUBJECTS.items() if info[1] == level]
            count = files_col.count_documents({"subject_code": {"$in": codes}})
            level_stats += f"• Level {level}: {count} file(s)\n"
    except Exception as e:
        await message.answer(f"❌ Database error: {e}")
        return

    await message.answer(
        f"📊 *Bot Statistics*\n\n"
        f"📁 Total files: *{total}*\n\n"
        f"📚 By level:\n{level_stats}",
        parse_mode="Markdown"
    )

# ==========================================
# Paper Request Feature (Command & Callback)
# ==========================================

@dp.message(Command("request"))
async def manual_paper_request(message: types.Message):
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

    # Notify Admins
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

    # Notify Admins
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
    
    # Update the message so they don't click it multiple times
    await callback.message.edit_text(
        f"✅ Your request for *{subject_name}* (`{code}`) has been forwarded to the admins.\n\n"
        f"You will be able to download it here once it is uploaded.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back to Main Menu", callback_data="back_to_start")]
        ])
    )

# ==========================================
# Browse Flow
# ==========================================

@dp.callback_query(F.data == "browse")
async def browse(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📂 *Browse Papers*\n\nSelect your level:",
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

# ==========================================
# Download ALL Papers
# ==========================================

@dp.callback_query(F.data.startswith("dlall_"))
async def download_all(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    level, semester = parts[1], parts[2]
    subjects = get_subjects_for(int(level), int(semester))

    try:
        results = list(files_col.find({"subject_code": {"$in": list(subjects.keys())}}))
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
        f"📥 *Sending all papers for Level {level} — Semester {semester}*\n"
        f"Found *{len(results)}* paper(s). Please wait...",
        parse_mode="Markdown"
    )

    for r in results:
        subject_name = SUBJECTS.get(r["subject_code"], ("Unknown",))[0]
        
        # Display indicator for Theory or Practical
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
# Browse by Subject
# ==========================================

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

    keyboard = get_year_keyboard(code, level, semester)

    if not keyboard:
        # If no papers found, show the Request button
        request_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🙋‍♂️ Request this Subject", callback_data=f"req_{code}")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data=f"sem_{semester}_{level}")]
        ])
        
        await callback.message.edit_text(
            f"⚠️ No papers found for *{subject_name}* (`{code}`) yet.\n\n"
            f"Would you like to request the admins to upload it?",
            parse_mode="Markdown",
            reply_markup=request_kb
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"📚 *{subject_name}*\n`{code}`\n\nSelect a year:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()

# ==========================================
# Download Single Paper (Supports Theory & Practical)
# ==========================================

@dp.callback_query(F.data.startswith("get_"))
async def download_file(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    code, year, semester = parts[1], parts[2], parts[3]
    subject_name = SUBJECTS.get(code, ("Unknown",))[0]

    try:
        # Search the database for ALL papers matching the code and year
        db_results = list(files_col.find({"subject_code": code, "year": year}))
    except Exception as e:
        await callback.message.answer(f"❌ Database error: {e}")
        await callback.answer()
        return

    if db_results:
        await callback.answer(text="📄 Downloading your past paper(s). Please wait...", show_alert=False)
        
        # Loop through found results (Will send both Theory and Practical if they exist)
        for doc in db_results:
            p_type = doc.get("paper_type", "Standard")
            
            # Format label based on the paper type
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
        await callback.message.answer(
            f"⚠️ No paper found for *{subject_name}* ({year}).\n"
            f"Check back later!",
            parse_mode="Markdown"
        )
        await callback.answer()

# ==========================================
# Search Command Prompt
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

# ==========================================
# Fuzzy Search by Subject Code or Name
# ==========================================

@dp.message(F.text)
async def handle_search(message: types.Message):
    query = message.text.strip()

    if query.startswith("/"):
        return

    if query in ["📂 Browse Papers", "🔍 Search Subject", "📊 Bot Statistics", "🙋‍♂️ Request Paper"]:
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
            f"💡 Try using key words like `Programming`, `Database`, `Maths` or the exact code like `TICT2113`.\n"
            f"If the subject is missing, you can type `/request SUBJECT_CODE`.",
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
        f"Select your subject below to browse available past papers:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ==========================================
# Channel: Auto Save File ID (Updated for T & P)
# ==========================================

@dp.channel_post(F.document)
async def handle_channel_upload(post: types.Message):
    print(f"📢 Channel post received! Chat ID: {post.chat.id} | File: {post.document.file_name}")

    current_chat_id = str(post.chat.id)
    current_username = f"@{post.chat.username}" if post.chat.username else ""

    if str(CHANNEL_ID) not in [current_chat_id, current_username]:
        print(f"⚠️ Channel ID mismatch! Expected: {CHANNEL_ID}, Got: {post.chat.id}")
        return

    file_name = post.document.file_name
    telegram_file_id = post.document.file_id

    if not file_name.lower().endswith(".pdf"):
        print(f"❌ Document ignored (Not a PDF): {file_name}")
        return

    try:
        # Safely remove .pdf extension to process the naming convention
        clean_name = file_name[:-4] 
        parts = clean_name.split("_")

        if len(parts) < 2:
            raise ValueError("File name does not match required structure.")

        subject_code = parts[0].upper()
        year = parts[1]

        # Ensure the subject code exists in our official dictionary
        if subject_code not in SUBJECTS:
            await bot.send_message(
                chat_id=post.chat.id,
                text=f"❌ *Unknown subject code:* `{subject_code}`\nCheck the code and try again.",
                parse_mode="Markdown"
            )
            return

        semester = SUBJECTS[subject_code][2]
        subject_name = SUBJECTS[subject_code][0]

        # Determine if it is a Theory (T), Practical (P), or Standard paper
        paper_type = "Standard"
        if len(parts) > 2:
            last_part = parts[-1].upper()
            if last_part == 'T':
                paper_type = "Theory"
            elif last_part == 'P':
                paper_type = "Practical"

        document_data = {
            "custom_id": f"{subject_code}_{year}_{paper_type}", # Now safely unique
            "subject_code": subject_code,
            "year": year,
            "semester": semester,
            "paper_type": paper_type,
            "file_id": telegram_file_id
        }

        files_col.update_one(
            {"custom_id": document_data["custom_id"]},
            {"$set": document_data},
            upsert=True
        )

        # Send a highly detailed confirmation message to the admin channel
        type_str = f" [{paper_type}]" if paper_type != "Standard" else ""
        print(f"✅ Saved to DB: {subject_code} | Year {year} | Sem {semester} | Type: {paper_type}")

        await bot.send_message(
            chat_id=post.chat.id,
            text=f"✅ *Saved successfully to Database!*\n\n"
                 f"📚 *Subject:* {subject_name}\n"
                 f"🔑 *Code:* `{subject_code}`\n"
                 f"📅 *Year:* {year} | *Semester:* {semester}\n"
                 f"🔖 *Type:* {paper_type}{type_str}",
            parse_mode="Markdown"
        )

    except ValueError:
        await bot.send_message(
            chat_id=post.chat.id,
            text=f"❌ *Invalid file name format:* `{file_name}`\n\n"
                 f"💡 Correct formats:\n"
                 f"`SUBJECTCODE_YEAR.pdf` (Standard)\n"
                 f"`SUBJECTCODE_YEAR_T.pdf` (Theory)\n"
                 f"`SUBJECTCODE_YEAR_P.pdf` (Practical)",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"❌ Error during saving: {e}")
        
# ==========================================
# Admin Stats Command
# ==========================================

@dp.message(Command("stats"))
async def admin_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ You are not authorized.")
        return

    try:
        total = files_col.count_documents({})
        level_stats = ""
        for level in [1, 2, 3, 4]:
            codes = [c for c, info in SUBJECTS.items() if info[1] == level]
            count = files_col.count_documents({"subject_code": {"$in": codes}})
            level_stats += f"• Level {level}: {count} file(s)\n"
    except Exception as e:
        await message.answer(f"❌ Database error: {e}")
        return

    await message.answer(
        f"📊 *Bot Statistics*\n\n"
        f"📁 Total files: *{total}*\n\n"
        f"📚 By level:\n{level_stats}",
        parse_mode="Markdown"
    )

# ==========================================
# Run Bot
# ==========================================

async def main():
    print("Bot is running... 🚀")

    me = await bot.get_me()
    print(f"Bot username: @{me.username}")

    try:
        chat = await bot.get_chat(CHANNEL_ID)
        print(f"Channel found: {chat.title}")
        member = await bot.get_chat_member(CHANNEL_ID, me.id)
        print(f"Bot status in channel: {member.status}")
    except Exception as e:
        print(f"Channel access error: {e}")

    await dp.start_polling(
        bot,
        allowed_updates=[
            "message",
            "channel_post",
            "callback_query",
            "edited_channel_post",
            "edited_message"
        ]
    )

if __name__ == "__main__":
    asyncio.run(main())
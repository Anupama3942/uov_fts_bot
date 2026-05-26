import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# Connect Bot and Database
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

cluster = MongoClient(MONGO_URI)
db = cluster["faculty_database"]
files_col = db["academic_resources"]

# ==========================================
# 1. Keyboard Buttons
# ==========================================

def get_year_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="2024", callback_data="year_2024"),
         InlineKeyboardButton(text="2023", callback_data="year_2023")],
        [InlineKeyboardButton(text="2022", callback_data="year_2022")]
    ])
    return keyboard

def get_semester_keyboard(year: str):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Semester 1", callback_data=f"sem_1_{year}"),
         InlineKeyboardButton(text="Semester 2", callback_data=f"sem_2_{year}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_years")]
    ])
    return keyboard

def get_subjects_keyboard(year: str, semester: str):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Data Structures (DSA)", callback_data=f"get_DSA_{year}_{semester}")],
        [InlineKeyboardButton(text="Mathematics (MATH)", callback_data=f"get_MATH_{year}_{semester}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data=f"year_{year}")]
    ])
    return keyboard

# ==========================================
# 2. Admin: PDF Upload Handler
# ==========================================

@dp.message(F.document)
async def handle_admin_upload(message: types.Message):
    file_name = message.document.file_name
    telegram_file_id = message.document.file_id

    if not file_name.endswith(".pdf"):
        await message.answer("❌ Please upload PDF files only.")
        return

    try:
        clean_name = file_name.replace(".pdf", "")
        subject_code, year, semester = clean_name.split("_")

        document_data = {
            "custom_id": f"{subject_code}_{year}_{semester}",
            "subject_code": subject_code,
            "year": year,
            "semester": semester,
            "file_id": telegram_file_id
        }

        files_col.update_one(
            {"custom_id": document_data["custom_id"]},
            {"$set": document_data},
            upsert=True
        )
        await message.answer(
            f"✅ Saved successfully!\n"
            f"📚 Subject: {subject_code}\n"
            f"📅 Year: {year} | Semester: {semester}"
        )

    except ValueError:
        await message.answer(
            "❌ Invalid file name!\n"
            "Format: SUBJECT_YEAR_SEM.pdf\n"
            "Example: DSA_2023_1.pdf"
        )

# ==========================================
# 3. Student: Browse and Download
# ==========================================

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        f"Welcome {message.from_user.first_name}! 👋\n"
        "Please select a year:",
        reply_markup=get_year_keyboard()
    )

@dp.callback_query(F.data.startswith("year_"))
async def process_year(callback: types.CallbackQuery):
    selected_year = callback.data.split("_")[1]
    await callback.message.edit_text(
        f"📅 Year: {selected_year}\nPlease select a semester:",
        reply_markup=get_semester_keyboard(selected_year)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("sem_"))
async def process_semester(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    semester, year = parts[1], parts[2]
    await callback.message.edit_text(
        f"📚 Year {year} - Semester {semester}\nPlease select a subject:",
        reply_markup=get_subjects_keyboard(year, semester)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("get_"))
async def download_file(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    subject_code, year, semester = parts[1], parts[2], parts[3]
    target_id = f"{subject_code}_{year}_{semester}"

    db_result = files_col.find_one({"custom_id": target_id})

    if db_result:
        await bot.send_document(
            chat_id=callback.from_user.id,
            document=db_result["file_id"],
            caption=f"📄 {subject_code} ({year} Sem {semester})"
        )
    else:
        await callback.message.answer(
            f"⚠️ No file found for {target_id}."
        )
    await callback.answer()

@dp.callback_query(F.data == "back_to_years")
async def process_back(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Please select a year:",
        reply_markup=get_year_keyboard()
    )
    await callback.answer()

# ==========================================
# 4. Run Bot
# ==========================================

async def main():
    print("Bot is running... 🚀")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
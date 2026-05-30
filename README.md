# UOV FTS Telegram Bot

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Aiogram](https://img.shields.io/badge/Aiogram-3.x-green)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-red)
![Firebase](https://img.shields.io/badge/Firebase-Firestore-orange)
![License](https://img.shields.io/badge/License-MIT-blue.svg)

A comprehensive Telegram Bot designed to help university students efficiently access, share, and manage academic resources such as past papers, lecture notes, and short notes.

## 🌟 Key Features

- **Resource Browsing**: Categorized resources by academic level and semester.
- **Smart Fuzzy Search**: Easily find subjects by typing partial names, keywords, or subject codes (powered by `TheFuzz`).
- **Interactive Upload Wizard**: A step-by-step UI to help students upload their own notes and past papers.
- **Admin Approval System**: Every uploaded resource is securely placed in a pending queue and can be approved/rejected either directly inside the Admin Telegram Group or via the Streamlit web dashboard.
- **Community Leaderboard**: Real-time ranking of top contributing students to gamify and encourage peer sharing.
- **Live Statistics**: Real-time database insights (Files, Pending resources, Student counts) directly accessible via the Bot and Admin Panel.
- **Web Dashboard**: An accompanying `admin_panel.py` built on Streamlit for easier moderation.

## 🛠️ Tech Stack

- **[Python](https://www.python.org/)** - Core programming language
- **[Aiogram](https://docs.aiogram.dev/)** - Asynchronous framework for Telegram Bot API
- **[Google Cloud Firestore](https://firebase.google.com/docs/firestore)** - NoSQL cloud database for data storage
- **[Streamlit](https://streamlit.io/)** - Fast and powerful framework for the Admin Web Panel
- **[TheFuzz](https://github.com/seatgeek/thefuzz)** - Fuzzy string matching for robust search functionality

## ⚙️ Installation & Setup

### Prerequisites

- Python 3.8 or higher.
- A Telegram Bot Token (obtained from [@BotFather](https://t.me/BotFather)).
- Firebase Service Account JSON keys.

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/UOV_FTS_BOT.git
cd UOV_FTS_BOT
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file in the root directory and add the following keys:

```env
BOT_TOKEN=your_telegram_bot_token_here
CHANNEL_ID=-100xxxxxxxxxx
ADMIN_GROUP_ID=-100xxxxxxxxxx
FIREBASE_KEY_PATH=firebase.json
DASHBOARD_PASSWORD=your_secure_admin_password
```

### 4. Setup Firebase

Place your Firebase service account credentials JSON file in the root directory and rename it to `firebase.json` (or update your `FIREBASE_KEY_PATH` accordingly in the `.env` file).

### 5. Run the Application

**To start the Telegram Bot:**

```bash
python bot.py
```

**To start the Streamlit Admin Panel:**

```bash
streamlit run admin_panel.py
```

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

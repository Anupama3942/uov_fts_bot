import os
import requests
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Use the subject list (SUBJECTS) from the main bot
from subjects import SUBJECTS 

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "admin2026")

# Initialize Firebase securely
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ==========================================
# Web Page Configuration (Mobile Optimization)
# ==========================================
st.set_page_config(page_title="UOV FTS Bot - Admin", page_icon="⚙️", layout="centered")

st.markdown("""
    <style>
        .stButton button {
            width: 100%;
            margin-bottom: 10px;
            padding: 0.5rem 1rem;
        }
        code {
            white-space: pre-wrap !important;
            word-break: break-all !important;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# Login System (Password Gate)
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.title("🔒 Admin Login")
        st.caption("Please enter the dashboard password to continue.")
        
        password_input = st.text_input("Password", type="password", key="password")
        
        if password_input:
            if password_input == DASHBOARD_PASSWORD:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ Incorrect Password. Please try again.")
        return False
    return True

if not check_password():
    st.stop()

# ==========================================
# Main Dashboard View
# ==========================================
st.title("🛠️ Admin Dashboard")
st.caption("UOV FTS Bot Management Portal")

# ==========================================
# Statistics Section
# ==========================================
st.subheader("📊 Bot Statistics")

try:
    users_count_query = db.collection("bot_users").count().get()
    users_count = users_count_query[0][0].value

    files_count_query = db.collection("academic_resources").count().get()
    files_count = files_count_query[0][0].value
except Exception:
    users_count = 0
    files_count = 0

pending_docs = list(db.collection("pending_resources").stream())
pending_count = len(pending_docs)

col1, col2, col3 = st.columns(3)
col1.metric("Total Students", users_count)
col2.metric("Approved Resources", files_count)
col3.metric("Pending Approvals", pending_count)

st.divider()

# ==========================================
# Pending Approvals Section
# ==========================================
st.subheader("⏳ Pending Review")

if not pending_docs:
    st.info("🎉 No pending notes to review at the moment.")
else:
    for doc in pending_docs:
        doc_id = doc.id
        data = doc.to_dict()
        
        subject_code = data.get("subject_code", "Unknown")
        category = data.get("category", "Unknown")
        topic_title = data.get("topic_title", "No Title")
        uploader_name = data.get("uploader_name", "Anonymous")
        
        with st.expander(f"📄 {topic_title} ({subject_code})"):
            st.markdown(f"**Subject:** `{subject_code}` | **Category:** {category} | **Uploader:** {uploader_name}")
            st.write("---")
            
            paper_year = ""
            paper_type = "Standard"
            if category == "Past Paper":
                y_col, t_col = st.columns(2)
                paper_year = y_col.text_input("Enter Paper Year (e.g., 2023):", key=f"year_{doc_id}")
                paper_type = t_col.selectbox("Paper Type:", ["Standard", "Theory", "Practical"], key=f"ptype_{doc_id}")
            
            # REJECT REASON SELECTBOX
            reject_reason = st.selectbox(
                "Select reason if rejecting:",
                ["Low Quality / Blurry", "Wrong Subject / Category", "Duplicate Content", "Not a valid educational PDF", "Other"],
                key=f"reason_{doc_id}"
            )
            
            btn_col1, btn_col2 = st.columns(2)
            
            if btn_col1.button("✅ Approve Note", key=f"app_{doc_id}", type="primary"):
                # year must be provided if category is Past Paper
                if category == "Past Paper" and not paper_year.strip():
                    st.error("⚠️ Please enter a valid year before approving a Past Paper!")
                else:
                    final_data = data.copy()
                    final_data["rating_sum"] = 0
                    final_data["rating_count"] = 0
                    
                    if category == "Past Paper":
                        final_data["year"] = paper_year.strip()
                        final_data["paper_type"] = paper_type

                    if subject_code in SUBJECTS:
                        final_data["semester"] = SUBJECTS[subject_code][2]
                    
                    db.collection("academic_resources").document(doc_id).set(final_data)
                    db.collection("pending_resources").document(doc_id).delete()
                    
                    telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                    success_text = f"🎉 *Good News!*\nYour upload for `{subject_code}` ({category}) was approved and is now available to all students!"
                    try:
                        requests.post(telegram_url, data={"chat_id": data.get("uploader_id"), "text": success_text, "parse_mode": "Markdown"})
                    except Exception:
                        pass
                    
                    st.success("Resource Approved successfully!")
                    st.rerun()

            if btn_col2.button("❌ Reject Note", key=f"rej_{doc_id}"):
                db.collection("pending_resources").document(doc_id).delete()
                
                telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                rejection_text = f"❌ Your upload for `{subject_code}` was rejected during administrative review.\n\n*Reason:* {reject_reason}\n\nPlease check your document and try again."
                try:
                    requests.post(telegram_url, data={"chat_id": data.get("uploader_id"), "text": rejection_text, "parse_mode": "Markdown"})
                except Exception:
                    pass
                
                st.error("Resource Rejected.")
                st.rerun()
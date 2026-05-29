import os
import requests
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Import SUBJECTS dictionary from the main bot script
from bot import SUBJECTS 

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize Firebase App safely
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ==========================================
# Web Page Configuration (Mobile Optimization)
# ==========================================
st.set_page_config(page_title="UOV FTS Bot - Admin", page_icon="⚙️", layout="centered")

# Inject Custom CSS for better mobile touch-targets and button spacing
st.markdown("""
    <style>
        /* Make buttons wider and easier to tap on mobile devices */
        .stButton button {
            width: 100%;
            margin-bottom: 10px;
            padding: 0.5rem 1rem;
        }
        /* Ensure code snippets and text wrap properly on small screens */
        code {
            white-space: pre-wrap !important;
            word-break: break-all !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🛠️ Admin Dashboard")
st.caption("UOV FTS Bot Management Portal")

# ==========================================
# 📊 Statistics Section
# ==========================================
st.subheader("📊 Bot Statistics")

# Fetch current metrics
users_count = len(list(db.collection("bot_users").stream()))
files_count = len(list(db.collection("academic_resources").stream()))
pending_count = len(list(db.collection("pending_resources").stream()))

# Responsive columns: Automatically stacks vertically on mobile devices
col1, col2, col3 = st.columns(3)
col1.metric("Total Students", users_count)
col2.metric("Approved Resources", files_count)
col3.metric("Pending Approvals", pending_count)

st.divider()

# ==========================================
# ⏳ Pending Approvals Section
# ==========================================
st.subheader("⏳ Pending Review")

pending_docs = list(db.collection("pending_resources").stream())

if not pending_docs:
    st.info("🎉 No pending notes to review.")
else:
    for doc in pending_docs:
        data = doc.to_dict()
        doc_id = doc.id
        
        # Safe data extraction
        subject_code = data.get("subject_code", "Unknown")
        subject_name = SUBJECTS.get(subject_code, ("Unknown",))[0]
        semester = SUBJECTS.get(subject_code, ("", "", 1))[2]
        topic = data.get("topic", None)
        
        # Clean mobile-friendly header for the expander container
        expander_title = f"📄 {subject_code} ({data.get('category')})"
        
        with st.expander(expander_title):
            st.markdown(f"**Subject:** {subject_name}")
            if topic:
                st.markdown(f"**Topic/Title:** {topic}")
            st.markdown(f"**Uploader:** {data.get('uploader_name')} ({data.get('uploader_id')})")
            st.markdown(f"**File Name:** `{data.get('file_name')}`")
            st.markdown(f"**Uploaded:** {data.get('upload_date')}")
            
            st.write("---")
            
            # Action button matrix
            btn_col1, btn_col2 = st.columns(2)
            
            # ---------------------------------
            # Approve Action Logic
            # ---------------------------------
            if btn_col1.button("✅ Approve Note", key=f"app_{doc_id}", type="primary"):
                new_data = data.copy()
                new_data["rating_sum"] = 0
                new_data["rating_count"] = 0
                new_data["semester"] = semester
                
                # Move document to active pool
                db.collection("academic_resources").document(doc_id).set(new_data)
                db.collection("pending_resources").document(doc_id).delete()
                
                # Send Telegram Notification to student
                telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                success_text = (
                    f"🎉 *Good News!*\nYour upload for `{subject_code}` "
                    f"has been verified and approved by an Admin!"
                )
                
                try:
                    requests.post(
                        telegram_url,
                        data={
                            "chat_id": data.get("uploader_id"), 
                            "text": success_text,
                            "parse_mode": "Markdown"
                        }
                    )
                except Exception as e:
                    st.warning(f"Database updated, but Telegram notification failed: {e}")
                
                st.success("Resource Approved!")
                st.rerun() 

            # ---------------------------------
            # Reject Action Logic
            # ---------------------------------
            if btn_col2.button("❌ Reject Note", key=f"rej_{doc_id}"):
                # Remove document from the pending pool
                db.collection("pending_resources").document(doc_id).delete()
                
                # Send Rejection Notification to student
                telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                rejection_text = f"❌ Your upload for `{subject_code}` was rejected during administrative review."
                
                try:
                    requests.post(
                        telegram_url,
                        data={
                            "chat_id": data.get("uploader_id"), 
                            "text": rejection_text
                        }
                    )
                except Exception as e:
                    st.warning(f"Database updated, but Telegram notification failed: {e}")
                
                st.error("Resource Rejected.")
                st.rerun()
import os
import json
import requests
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict

from subjects import SUBJECTS

# ==========================================
# Environment & Firebase Init
# ==========================================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "admin2026")

if not firebase_admin._apps:
    firebase_env = os.getenv("FIREBASE_CREDENTIALS")
    if firebase_env:
        cred = credentials.Certificate(json.loads(firebase_env))
        firebase_admin.initialize_app(cred)
    else:
        st.error("❌ FIREBASE_CREDENTIALS environment variable is missing!")
        st.stop()

db = firestore.client()

# ==========================================
# Page Config
# ==========================================
st.set_page_config(page_title="UOV FTS Bot - Admin", page_icon="⚙️", layout="wide")

st.markdown("""
    <style>
        .stButton button { width: 100%; margin-bottom: 8px; }
        code { white-space: pre-wrap !important; word-break: break-all !important; }
        .log-entry { font-family: monospace; font-size: 0.82rem; padding: 4px 8px;
                     border-left: 3px solid #4CAF50; margin-bottom: 4px; background: #f9f9f9; }
        .log-entry.reject { border-left-color: #f44336; }
        .log-entry.delete { border-left-color: #FF9800; }
        .log-entry.ban    { border-left-color: #9C27B0; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# Login
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.title("🔒 Admin Login")
        st.caption("Enter the dashboard password to continue.")
        pw = st.text_input("Password", type="password", key="password")
        if pw:
            if pw == DASHBOARD_PASSWORD:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ Incorrect password.")
        return False
    return True

if not check_password():
    st.stop()

# ==========================================
# Logging Helper
# ==========================================
def write_log(action: str, detail: str):
    """Write an action to the admin_logs Firestore collection."""
    try:
        db.collection("admin_logs").add({
            "action": action,
            "detail": detail,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception:
        pass

# ==========================================
# Telegram Notify Helper
# ==========================================
def notify_user(chat_id, text: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=5
        )
    except Exception:
        pass

# ==========================================
# Sidebar Navigation
# ==========================================
st.sidebar.title("⚙️ UOV FTS Admin")
st.sidebar.caption("Management Portal")
page = st.sidebar.radio(
    "Navigate",
    ["📊 Dashboard", "⏳ Pending Approvals", "📁 Resource Management", "👥 User Management", "📋 Activity Log"]
)
st.sidebar.divider()
if st.sidebar.button("🔓 Logout"):
    st.session_state["password_correct"] = False
    st.rerun()

# ==========================================
# Load Data (cached per session refresh)
# ==========================================
@st.cache_data(ttl=60)
def load_stats():
    try:
        uc = db.collection("bot_users").count().get()[0][0].value
        fc = db.collection("academic_resources").count().get()[0][0].value
    except Exception:
        uc, fc = 0, 0
    return uc, fc

@st.cache_data(ttl=30)
def load_resources():
    return [d.to_dict() | {"_id": d.id} for d in db.collection("academic_resources").stream()]

@st.cache_data(ttl=30)
def load_users():
    return [{"_id": d.id} | d.to_dict() for d in db.collection("bot_users").stream()]

@st.cache_data(ttl=30)
def load_banned():
    try:
        return {d.id for d in db.collection("banned_users").stream()}
    except Exception:
        return set()

# ==========================================
# PAGE 1 — DASHBOARD
# ==========================================
if page == "📊 Dashboard":
    st.title("📊 Dashboard")
    st.caption("Overview of bot activity and resource distribution.")

    users_count, files_count = load_stats()
    pending_docs = list(db.collection("pending_resources").stream())
    pending_count = len(pending_docs)

    # ── Metrics Row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Total Students", users_count)
    c2.metric("✅ Approved Resources", files_count)
    c3.metric("⏳ Pending Approvals", pending_count)

    # Count banned users
    try:
        banned_count = db.collection("banned_users").count().get()[0][0].value
    except Exception:
        banned_count = 0
    c4.metric("🚫 Banned Users", banned_count)

    st.divider()

    # ── Charts from academic_resources
    resources = load_resources()
    if resources:
        st.subheader("📈 Resource Breakdown")
        ch1, ch2 = st.columns(2)

        # By Category
        cat_counts = defaultdict(int)
        for r in resources:
            cat_counts[r.get("category", "Unknown")] += 1
        with ch1:
            st.markdown("**By Category**")
            for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
                st.progress(count / max(cat_counts.values()), text=f"{cat}: {count}")

        # By Level
        level_counts = defaultdict(int)
        for r in resources:
            code = r.get("subject_code", "")
            if code in SUBJECTS:
                level_counts[f"Level {SUBJECTS[code][1]}"] += 1
            else:
                level_counts["Unknown"] += 1
        with ch2:
            st.markdown("**By Level**")
            for lvl, count in sorted(level_counts.items()):
                st.progress(count / max(level_counts.values()), text=f"{lvl}: {count}")

        st.divider()

        # Top Uploaders
        st.subheader("🏆 Top Contributors")
        uploader_counts = defaultdict(int)
        for r in resources:
            name = r.get("uploader_name", "Unknown")
            if r.get("category") in ["Lecture Note", "Short Note"]:
                uploader_counts[name] += 1
        if uploader_counts:
            sorted_uploaders = sorted(uploader_counts.items(), key=lambda x: -x[1])[:10]
            medals = ["🥇", "🥈", "🥉"]
            for i, (name, count) in enumerate(sorted_uploaders):
                medal = medals[i] if i < 3 else "🏅"
                st.markdown(f"{medal} **{name}** — {count} file(s)")
        else:
            st.info("No community uploads yet.")

        st.divider()

        # Top Rated Resources
        st.subheader("⭐ Top Rated Notes")
        rated = [r for r in resources if r.get("rating_count", 0) > 0]
        rated_sorted = sorted(rated, key=lambda x: x["rating_sum"] / x["rating_count"], reverse=True)[:5]
        if rated_sorted:
            for r in rated_sorted:
                avg = round(r["rating_sum"] / r["rating_count"], 1)
                st.markdown(
                    f"⭐ **{avg}/5.0** ({r['rating_count']} votes) — "
                    f"`{r.get('subject_code','')}` · {r.get('topic_title', r.get('file_name',''))} "
                    f"· *by {r.get('uploader_name','?')}*"
                )
        else:
            st.info("No ratings yet.")
    else:
        st.info("No resources in the database yet.")

# ==========================================
# PAGE 2 — PENDING APPROVALS
# ==========================================
elif page == "⏳ Pending Approvals":
    st.title("⏳ Pending Approvals")

    pending_docs = list(db.collection("pending_resources").stream())

    if not pending_docs:
        st.success("🎉 No pending items — all clear!")
    else:
        # Filter controls
        all_categories = list({d.to_dict().get("category", "Unknown") for d in pending_docs})
        filter_cat = st.selectbox("Filter by Category", ["All"] + sorted(all_categories))
        search_term = st.text_input("🔍 Search by subject code or title", "").strip().lower()

        filtered = []
        for doc in pending_docs:
            data = doc.to_dict()
            if filter_cat != "All" and data.get("category") != filter_cat:
                continue
            if search_term:
                haystack = (data.get("subject_code", "") + data.get("topic_title", "")).lower()
                if search_term not in haystack:
                    continue
            filtered.append((doc.id, data))

        st.caption(f"Showing {len(filtered)} of {len(pending_docs)} pending items.")
        st.divider()

        for doc_id, data in filtered:
            subject_code = data.get("subject_code", "Unknown")
            category     = data.get("category", "Unknown")
            topic_title  = data.get("topic_title", "No Title")
            uploader_name = data.get("uploader_name", "Anonymous")
            uploader_id  = data.get("uploader_id")
            upload_date  = data.get("upload_date", "—")

            with st.expander(f"📄 {topic_title} ({subject_code}) · {category} · {upload_date}"):
                st.markdown(
                    f"**Subject:** `{subject_code}` | **Category:** {category} | "
                    f"**Uploader:** {uploader_name} | **Date:** {upload_date}"
                )
                st.write("---")

                paper_year = ""
                paper_type = "Standard"
                if category == "Past Paper":
                    y_col, t_col = st.columns(2)
                    paper_year = y_col.text_input("Paper Year (e.g. 2023):", key=f"year_{doc_id}")
                    paper_type = t_col.selectbox("Paper Type:", ["Standard", "Theory", "Practical"], key=f"ptype_{doc_id}")

                reject_reason = st.selectbox(
                    "Reject reason (if rejecting):",
                    ["Low Quality / Blurry", "Wrong Subject / Category", "Duplicate Content",
                     "Not a valid educational PDF", "Other"],
                    key=f"reason_{doc_id}"
                )

                btn1, btn2 = st.columns(2)

                if btn1.button("✅ Approve", key=f"app_{doc_id}", type="primary"):
                    if category == "Past Paper" and not paper_year.strip():
                        st.error("⚠️ Enter a valid year before approving a Past Paper!")
                    else:
                        final_data = data.copy()
                        final_data["rating_sum"] = 0
                        final_data["rating_count"] = 0
                        final_data["rated_by"] = []
                        if category == "Past Paper":
                            final_data["year"] = paper_year.strip()
                            final_data["paper_type"] = paper_type
                        if subject_code in SUBJECTS:
                            final_data["semester"] = SUBJECTS[subject_code][2]

                        db.collection("academic_resources").document(doc_id).set(final_data)
                        db.collection("pending_resources").document(doc_id).delete()
                        notify_user(uploader_id,
                            f"🎉 *Good News!*\nYour upload for `{subject_code}` ({category}) was approved!")
                        write_log("APPROVE", f"{category} | {subject_code} | {topic_title} | by {uploader_name}")
                        st.success("✅ Approved!")
                        st.cache_data.clear()
                        st.rerun()

                if btn2.button("❌ Reject", key=f"rej_{doc_id}"):
                    db.collection("pending_resources").document(doc_id).delete()
                    notify_user(uploader_id,
                        f"❌ Your upload for `{subject_code}` was rejected.\n\n*Reason:* {reject_reason}\n\nPlease check and try again.")
                    write_log("REJECT", f"{category} | {subject_code} | {topic_title} | Reason: {reject_reason} | by {uploader_name}")
                    st.error("❌ Rejected.")
                    st.cache_data.clear()
                    st.rerun()

# ==========================================
# PAGE 3 — RESOURCE MANAGEMENT
# ==========================================
elif page == "📁 Resource Management":
    st.title("📁 Resource Management")
    st.caption("Search, view, and delete approved resources.")

    resources = load_resources()

    if not resources:
        st.info("No resources in the database yet.")
    else:
        # Filters
        f1, f2, f3 = st.columns(3)
        filter_level = f1.selectbox("Level", ["All", "1", "2", "3", "4"])
        filter_cat   = f2.selectbox("Category", ["All", "Past Paper", "Lecture Note", "Short Note"])
        search_res   = f3.text_input("🔍 Search subject code / title", "").strip().lower()

        filtered_res = []
        for r in resources:
            code = r.get("subject_code", "")
            lvl = str(SUBJECTS[code][1]) if code in SUBJECTS else "?"
            if filter_level != "All" and lvl != filter_level:
                continue
            if filter_cat != "All" and r.get("category") != filter_cat:
                continue
            if search_res:
                hay = (code + r.get("topic_title", "") + r.get("file_name", "")).lower()
                if search_res not in hay:
                    continue
            filtered_res.append(r)

        st.caption(f"Showing {len(filtered_res)} of {len(resources)} resources.")
        st.divider()

        for r in filtered_res:
            doc_id    = r["_id"]
            code      = r.get("subject_code", "?")
            category  = r.get("category", "?")
            title     = r.get("topic_title", r.get("file_name", "Unknown"))
            uploader  = r.get("uploader_name", "Admin")
            date      = r.get("upload_date", "—")
            rating    = f"⭐ {round(r['rating_sum']/r['rating_count'],1)}/5 ({r['rating_count']} votes)" if r.get("rating_count", 0) > 0 else "No ratings"
            year_info = f" | Year: {r['year']}" if r.get("year") else ""

            with st.expander(f"📄 {title} · `{code}` · {category}{year_info}"):
                st.markdown(
                    f"**Subject:** `{code}` | **Category:** {category} | "
                    f"**Uploader:** {uploader} | **Date:** {date} | **Rating:** {rating}"
                )

                if st.button("🗑️ Delete Resource", key=f"del_{doc_id}"):
                    db.collection("academic_resources").document(doc_id).delete()
                    write_log("DELETE", f"{category} | {code} | {title} | uploaded by {uploader}")
                    st.warning(f"🗑️ Deleted: {title}")
                    st.cache_data.clear()
                    st.rerun()

# ==========================================
# PAGE 4 — USER MANAGEMENT
# ==========================================
elif page == "👥 User Management":
    st.title("👥 User Management")
    st.caption("View registered students and manage bans.")

    users = load_users()
    banned_ids = load_banned()

    if not users:
        st.info("No registered users yet.")
    else:
        search_user = st.text_input("🔍 Search by name or username", "").strip().lower()
        filter_ban  = st.selectbox("Filter", ["All Users", "Active Only", "Banned Only"])

        filtered_users = []
        for u in users:
            uid = u["_id"]
            name = u.get("first_name", "")
            uname = u.get("username", "")
            is_banned = uid in banned_ids

            if filter_ban == "Active Only" and is_banned:
                continue
            if filter_ban == "Banned Only" and not is_banned:
                continue
            if search_user:
                hay = (name + uname).lower()
                if search_user not in hay:
                    continue
            filtered_users.append((uid, u, is_banned))

        st.caption(f"Showing {len(filtered_users)} of {len(users)} users.")
        st.divider()

        for uid, u, is_banned in filtered_users:
            name    = u.get("first_name", "Unknown")
            uname   = f"@{u['username']}" if u.get("username") else "—"
            joined  = u.get("joined_at", "—")
            if hasattr(joined, "strftime"):
                joined = joined.strftime("%Y-%m-%d")

            status = "🚫 Banned" if is_banned else "✅ Active"

            with st.expander(f"{status} · {name} ({uname}) · ID: {uid}"):
                st.markdown(
                    f"**Name:** {name} | **Username:** {uname} | "
                    f"**Telegram ID:** `{uid}` | **Joined:** {joined} | **Status:** {status}"
                )

                if is_banned:
                    if st.button("✅ Unban User", key=f"unban_{uid}"):
                        db.collection("banned_users").document(uid).delete()
                        notify_user(int(uid),
                            "✅ Your access to the UOV FTS Bot has been restored. You can now use the bot again.")
                        write_log("UNBAN", f"User {name} ({uname}) | ID: {uid}")
                        st.success(f"✅ {name} has been unbanned.")
                        st.cache_data.clear()
                        st.rerun()
                else:
                    ban_reason = st.text_input("Ban reason:", key=f"banreason_{uid}", placeholder="e.g. Spamming / Abuse")
                    if st.button("🚫 Ban User", key=f"ban_{uid}"):
                        db.collection("banned_users").document(uid).set({
                            "name": name,
                            "username": u.get("username", ""),
                            "banned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "reason": ban_reason
                        })
                        notify_user(int(uid),
                            "🚫 You have been banned from the UOV FTS Bot due to a policy violation. "
                            "Please contact the faculty admin if you believe this is a mistake.")
                        write_log("BAN", f"User {name} ({uname}) | ID: {uid} | Reason: {ban_reason}")
                        st.error(f"🚫 {name} has been banned.")
                        st.cache_data.clear()
                        st.rerun()

# ==========================================
# PAGE 5 — ACTIVITY LOG
# ==========================================
elif page == "📋 Activity Log":
    st.title("📋 Activity Log")
    st.caption("All admin actions are recorded here automatically.")

    try:
        log_docs = list(
            db.collection("admin_logs")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(200)
            .stream()
        )
    except Exception:
        log_docs = []

    if not log_docs:
        st.info("No activity logs yet. Logs appear after you approve, reject, delete, or ban.")
    else:
        # Filter by action type
        action_filter = st.selectbox(
            "Filter by action",
            ["All", "APPROVE", "REJECT", "DELETE", "BAN", "UNBAN"]
        )

        shown = 0
        for doc in log_docs:
            entry = doc.to_dict()
            action    = entry.get("action", "?")
            detail    = entry.get("detail", "")
            timestamp = entry.get("timestamp", "—")

            if action_filter != "All" and action != action_filter:
                continue

            css_class = {
                "APPROVE": "log-entry",
                "REJECT":  "log-entry reject",
                "DELETE":  "log-entry delete",
                "BAN":     "log-entry ban",
                "UNBAN":   "log-entry",
            }.get(action, "log-entry")

            action_emoji = {
                "APPROVE": "✅",
                "REJECT":  "❌",
                "DELETE":  "🗑️",
                "BAN":     "🚫",
                "UNBAN":   "✅",
            }.get(action, "•")

            st.markdown(
                f'<div class="{css_class}">'
                f'<strong>{action_emoji} {action}</strong> &nbsp;|&nbsp; {timestamp}<br>'
                f'{detail}'
                f'</div>',
                unsafe_allow_html=True
            )
            shown += 1

        st.caption(f"{shown} log entries shown.")

        st.divider()
        if st.button("🗑️ Clear All Logs", type="secondary"):
            for doc in log_docs:
                doc.reference.delete()
            st.success("All logs cleared.")
            st.rerun()
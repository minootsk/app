import streamlit as st
import pandas as pd
import hashlib
import re
from utils import get_gsheets_client, get_worksheet_by_key, make_unique_headers
import io

# --- Page config ---
st.set_page_config(
    page_title="Influencer Checker",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="📑"
)

# --- Current page in session ---
st.session_state.current_page = 'credibility'

# --- Session state initialization ---
def init_session_state():
    defaults = {
        "full_table": None,
        "editor_version": 0,
        "sheet_version": None,
        "sheet_updated": False,
        "data_loaded": False,
        "pending_changes": None,
        "new_influencers_df": None,
        "added_influencers": False
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
init_session_state()

# --- Google Sheet Config ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1pFpU-ClSWJx2bFEdbZzaH47vedgtI8uxhDVXSKX0ZkE/edit"
INF_SHEET = "Influencers List"
SHEET_ID = re.search(r"/d/([a-zA-Z0-9-_]+)", SHEET_URL).group(1)

# --- Connect to Google Sheet ---
@st.cache_resource(show_spinner=False)
def get_worksheet():
    client = get_gsheets_client()
    return get_worksheet_by_key(client, SHEET_ID, INF_SHEET)

try:
    worksheet_influencers = get_worksheet()
except Exception as e:
    st.error(f"❌ Failed to connect to Google Sheets: {e}")
    st.stop()

# --- Load sheet version ---
@st.cache_data(ttl=60, show_spinner=False)
def get_sheet_version(_ws):
    all_values = _ws.get_all_values()
    last_row = "".join(all_values[-1]) if all_values else ""
    version_str = f"{len(all_values)}-{last_row}"
    return hashlib.md5(version_str.encode()).hexdigest()

# --- Load sheet data ---
@st.cache_data(ttl=120, show_spinner="↺ Loading data from Google Sheets...")
def load_data(_worksheet_influencers):
    data = _worksheet_influencers.get_all_values()
    if not data or len(data) < 2:
        return pd.DataFrame(), None, None, None

    headers = make_unique_headers(data[0])
    df = pd.DataFrame(data[1:], columns=headers)

    def safe_find_column(df, keyword, default_name):
        try:
            return next(c for c in df.columns if keyword in c)
        except StopIteration:
            st.error(f"❌ Required column containing '{keyword}' not found in Google Sheet")
            st.stop()
            return default_name

    id_col = safe_find_column(df, "ID", "ID")
    cred_col = safe_find_column(df, "Credibility", "Credibility")
    comment_col = safe_find_column(df, "Comment", "Comment")

    if cred_col in df.columns:
        df[cred_col] = df[cred_col].replace(
            {"TRUE": True, "True": True, "true": True, "FALSE": False, "False": False, "false": False}
        ).fillna(False)

    return df, id_col, cred_col, comment_col

try:
    sheet_version = get_sheet_version(worksheet_influencers)
    influencers_df, id_col, cred_col, comment_col = load_data(worksheet_influencers)
except Exception as e:
    st.error(f"❌ Error loading data: {e}")
    st.stop()

# --- Initialize full table ---
if influencers_df is not None and not influencers_df.empty:
    if st.session_state.full_table is None:
        needed_cols = [c for c in [id_col, comment_col, cred_col] if c in influencers_df.columns]
        st.session_state.full_table = influencers_df[needed_cols].copy()

    if st.session_state.sheet_version is None:
        st.session_state.sheet_version = sheet_version
    elif st.session_state.sheet_version != sheet_version:
        needed_cols = [c for c in [id_col, comment_col, cred_col] if c in influencers_df.columns]
        st.session_state.full_table = influencers_df[needed_cols].copy()
        st.session_state.sheet_version = sheet_version
        st.session_state.editor_version += 1
        st.rerun()

# --- Google Sheet update function ---
@st.cache_data(ttl=300, show_spinner=False)
def update_google_sheet(df, _worksheet_influencers, id_col, cred_col, comment_col):
    df_to_write = df.copy()
    if cred_col in df_to_write.columns:
        df_to_write[cred_col] = df_to_write[cred_col].map({True: "True", False: "False"})
    values = [df_to_write.columns.tolist()] + df_to_write.values.tolist()
    _worksheet_influencers.clear()
    _worksheet_influencers.update(values)
    return True

# --- Sidebar ---
with st.sidebar:
    if st.button("↻ Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.session_state.data_loaded = False
        st.rerun()

    st.markdown("---")
    st.markdown("### ☁️ Google Sheet Actions")

    if st.button("🔄 Update Google Sheet", use_container_width=True, type="primary"):
        try:
            with st.spinner("↺ Updating Google Sheets..."):
                success = update_google_sheet(
                    st.session_state.full_table,
                    worksheet_influencers,
                    id_col,
                    cred_col,
                    comment_col
                )
            if success:
                st.success("✔️ Google Sheet updated successfully!")
                st.session_state.sheet_updated = True
                st.session_state.added_influencers = False
                st.cache_data.clear()
        except Exception as e:
            st.error(f"❌ Failed to update Google Sheet: {e}")

# --- COLUMN NORMALIZATION FUNCTION ---
COLUMN_ALIASES = {
    # ID
    "id": "ID",
    "username": "ID",
    "handle": "ID",
    "profile": "ID",

    # Followers
    "followers": "Followers",
    "follower": "Followers",
    "follower count": "Followers",
    "followers count": "Followers",
    "audience": "Followers",
    "audience size": "Followers",

    # Post Price
    "post price": "Post price",
    "post price (t)": "Post price",
    "postprice": "Post price",
    "price": "Post price",
    "rate": "Post price",
    "price per post": "Post price",
    "post rate": "Post price",
    "post_fee": "Post price",

    # Avg View
    "avg view": "Avg View",
    "avg views": "Avg View",
    "average view": "Avg View",
    "average views": "Avg View",
    "view average": "Avg View",
    "views avg": "Avg View",

    # Avg Like
    "avg like": "Avg like",
    "avg likes": "Avg like",
    "ave like": "Avg like",
    "ave likes": "Avg like",
    "average like": "Avg like",
    "average likes": "Avg like",

    # Avg Comment
    "avg comment": "Avg comments",
    "avg comments": "Avg comments",
    "ave comment": "Avg comments",
    "ave comments": "Avg comments",
    "average comment": "Avg comments",
    "average comments": "Avg comments",

    # IER / ER
    "ier": "IER",
    "ie": "IER",
    "er": "IER",
    "engagement rate": "IER",
    "eng. rate": "IER",

    # CPV
    "cpv": "CPV",
    "cost per view": "CPV",

    # Category
    "category": "Category",
    "niche": "Category",
    "type": "Category",
    "segment": "Category",

    # Link
    "link": "Link",
    "profile link": "Link",
    "url": "Link",
}

def clean_uploaded_file(df):
    # Normalize column names
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(r"[\s\-_]+", " ", regex=True)
    )
    # Apply alias mapping
    df.rename(columns=lambda x: COLUMN_ALIASES.get(x, x), inplace=True)

    # Ensure ID exists
    if "ID" not in df.columns:
        df.rename(columns={df.columns[0]: "ID"}, inplace=True)

    df["ID"] = df["ID"].astype(str).str.lstrip("@").str.strip()

    # Ensure missing columns
    for col in COLUMN_ALIASES.values():
        if col not in df.columns:
            df[col] = None

    # Convert numeric columns
    NUMERIC_COLS = ["Followers", "Post price", "Avg View", "Avg like", "Avg comments", "IER", "CPV"]
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

# --- SECTION 3: Excel-like Bulk Editor ---
with st.expander("➕ Paste Single or Multiple Influencers Here", expanded=True):
    if st.session_state.new_influencers_df is None:
        st.session_state.new_influencers_df = pd.DataFrame({
            "ID": [""] * 5,
            "Comment": [""] * 5,
            "Credibility": [False] * 5
        })

    new_editor_df = st.data_editor(
        st.session_state.new_influencers_df,
        use_container_width=True,
        column_config={
            "ID": st.column_config.TextColumn("ID"),
            "Comment": st.column_config.TextColumn("Comment"),
            "Credibility": st.column_config.CheckboxColumn("Credibility (default=❌ Rejected)")
        },
        hide_index=True,
        num_rows="dynamic",
        key="bulk_add_editor"
    )

    if st.button("💾 Add Influencers to List", type="primary"):
        new_rows = new_editor_df[new_editor_df["ID"].str.strip() != ""].copy()
        if not new_rows.empty:
            new_rows = clean_uploaded_file(new_rows)  # Apply robust column normalization
            st.session_state.full_table = pd.concat([new_rows, st.session_state.full_table], ignore_index=True)
            st.session_state.added_influencers = True
            st.success(f"✔️ {len(new_rows)} influencer(s) added locally!")
            st.warning("⚠️ Don’t forget to click **Update Google Sheet** in the sidebar to save changes permanently!")

            st.session_state.new_influencers_df = pd.DataFrame({
                "ID": [""] * 5,
                "Comment": [""] * 5,
                "Credibility": [False] * 5
            })
            st.session_state.editor_version += 1
        else:
            st.warning("⚠️ Please enter at least one influencer ID to add.")

# --- Scorecards Section ---
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("---")
if st.session_state.full_table is not None and cred_col in st.session_state.full_table.columns:
    approved_count = int(st.session_state.full_table[cred_col].sum())
    rejected_count = int(len(st.session_state.full_table) - approved_count)

    st.markdown(
        f"""
        <div style="display: flex; gap: 2rem; align-items: center; margin-bottom: 20px;">
            <div style="background-color:#eafbea; padding:1rem; border-radius:10px; text-align:center; flex:1;">
                <h4 style="margin:0;">✔️ Approved</h4>
                <p style="font-size:1.5rem; margin:0;"><b>{approved_count}</b></p>
            </div>
            <div style="background-color:#fdecea; padding:1rem; border-radius:10px; text-align:center; flex:1;">
                <h4 style="margin:0;">❌ Rejected</h4>
                <p style="font-size:1.5rem; margin:0;"><b>{rejected_count}</b></p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# --- Filter Influencers ---
st.markdown("### 🔍 Change Credibility")
col1, col2 = st.columns(2)
cred_labels = {"All": "All", True: "✔️ Approved", False: "❌ Rejected"}
with col1:
    cred_filter = st.selectbox(
        "Filter by Credibility",
        options=["All", True, False],
        format_func=lambda x: cred_labels[x]
    )
with col2:
    if st.session_state.full_table is not None and comment_col in st.session_state.full_table.columns:
        comment_options = ["All"] + sorted(st.session_state.full_table[comment_col].dropna().unique().tolist())
    else:
        comment_options = ["All"]
    comment_filter = st.selectbox("Filter by Comment", options=comment_options)

# --- Apply filters ---
def get_filtered_table():
    df = st.session_state.full_table
    mask = pd.Series(True, index=df.index)
    if cred_filter != "All" and cred_col in df.columns:
        mask &= df[cred_col] == cred_filter
    if comment_filter != "All" and comment_col in df.columns:
        mask &= df[comment_col] == comment_filter
    result = df[mask].copy()
    if cred_col in result.columns:
        result["Status"] = result[cred_col].map({True: "✔️ Approved", False: "❌ Rejected"})
    return result

filtered_df = get_filtered_table()
display_df = filtered_df.copy()

# --- Edit Influencer Data ---
editor_key = f"main_editor_v{st.session_state.editor_version}"
if display_df.empty:
    st.info("ℹ️ No influencers match the current filters")
else:
    edited_table = st.data_editor(
        display_df,
        use_container_width=True,
        num_rows="fixed",
        key=editor_key,
        hide_index=True
    )

    if edited_table is not None and not edited_table.empty:
        updated_full = st.session_state.full_table.copy()
        changes = []
        for idx, row in edited_table.iterrows():
            if idx not in updated_full.index:
                continue
            if cred_col in updated_full.columns and row.get(cred_col) is not None and updated_full.at[idx, cred_col] != row[cred_col]:
                updated_full.at[idx, cred_col] = row[cred_col]
                changes.append(idx)
            if comment_col in updated_full.columns and row.get(comment_col) is not None and updated_full.at[idx, comment_col] != row[comment_col]:
                updated_full.at[idx, comment_col] = row[comment_col]
                changes.append(idx)

        if changes:
            st.session_state.pending_changes = updated_full
            if st.button("✅ Apply Changes", type="primary"):
                st.session_state.full_table = st.session_state.pending_changes
                st.session_state.pending_changes = None
                st.session_state.editor_version += 1
                st.success(f"✔️ {len(set(changes))} row(s) updated locally")
                st.warning("⚠️ Don’t forget to click **Update Google Sheet** in the sidebar to save changes permanently!")

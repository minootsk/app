import streamlit as st
import pandas as pd
import hashlib
from utils import get_gsheets_client, get_worksheet_by_url, make_unique_headers

# Set page config must be the FIRST Streamlit command
st.set_page_config(page_title="Influencer Checker", layout="wide", initial_sidebar_state="expanded")

# --- AUTHENTICATION ---
def check_login():
    # Define valid credentials
    valid_credentials = {
        "solico": {"password": "solico123", "name": "Solico Group"},
        "minoo": {"password": "minoo123", "name": "Minoo Tashakori"}
    }
    
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.session_state.name = ""
    
    if not st.session_state.authenticated:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Login")
            
            if submit_button:
                if (username in valid_credentials and 
                    password == valid_credentials[username]["password"]):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.name = valid_credentials[username]["name"]
                    st.rerun()
                else:
                    st.error("Invalid username or password")
        
        st.stop()
    
    return True

check_login()

if st.session_state.authenticated:
    with st.sidebar:
        st.write(f"Welcome, **{st.session_state.name}**")
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.username = ""
            st.session_state.name = ""
            st.rerun()

# --- CONFIGURATION ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1pFpU-ClSWJx2bFEdbZzaH47vedgtI8uxhDVXSKX0ZkE/edit"
INF_SHEET = "Influencers List"

# --- GOOGLE SHEET SETUP ---
@st.cache_resource(show_spinner=False)
def get_worksheet():
    client = get_gsheets_client()   # ✅ no JSON path, uses st.secrets
    ws_inf = get_worksheet_by_url(client, SHEET_URL, INF_SHEET)
    return ws_inf

try:
    worksheet_influencers = get_worksheet()
except Exception as e:
    st.error(f"Failed to connect to Google Sheets: {e}")
    st.stop()

# --- VERSION & LOAD DATA ---
@st.cache_data(ttl=60, show_spinner=False)
def get_sheet_version(_ws):
    all_values = _ws.get_all_values()
    last_row = "".join(all_values[-1]) if all_values else ""
    version_str = f"{len(all_values)}-{last_row}"
    return hashlib.md5(version_str.encode()).hexdigest()

@st.cache_data(ttl=120, show_spinner="Loading data from Google Sheets...")
def load_data(_worksheet_influencers):
    data = _worksheet_influencers.get_all_values()
    headers = make_unique_headers(data[0])
    df = pd.DataFrame(data[1:], columns=headers)
    id_col = next(c for c in df.columns if "ID" in c)
    cred_col = next(c for c in df.columns if "Credibility" in c)
    comment_col = next(c for c in df.columns if "Comment" in c)
    df[cred_col] = df[cred_col].replace(
        {"TRUE": True, "True": True, "true": True,
         "FALSE": False, "False": False, "false": False}
    ).fillna(False)
    return df, id_col, cred_col, comment_col

try:
    sheet_version = get_sheet_version(worksheet_influencers)
    influencers_df, id_col, cred_col, comment_col = load_data(worksheet_influencers)
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# --- SESSION STATE ---
if "full_table" not in st.session_state:
    st.session_state.full_table = influencers_df[[id_col, comment_col, cred_col]].copy()
if "editor_version" not in st.session_state:
    st.session_state.editor_version = 0
if "sheet_version" not in st.session_state:
    st.session_state.sheet_version = sheet_version
elif st.session_state.sheet_version != sheet_version:
    st.session_state.full_table = influencers_df[[id_col, comment_col, cred_col]].copy()
    st.session_state.sheet_version = sheet_version
    st.session_state.editor_version += 1
    st.rerun()

# --- DYNAMIC CARDS ---
def show_dynamic_cards():
    df = st.session_state.full_table
    approved_count = df[df[cred_col] == True].shape[0]
    rejected_count = df[df[cred_col] == False].shape[0]
    st.markdown(
        f"""
        <div style="display:flex; gap:20px; justify-content:left; margin-bottom:20px;">
            <div style="flex:2; padding:15px; border-radius:10px; text-align:center; background-color:#d1fae5; border:2px solid #10b981; max-width:280px;">
                <h4 style="color:#065f46; margin:0;">✅ Approved</h4>
                <h2 style="color:#065f46; margin:0;">{approved_count}</h2>
            </div>
            <div style="flex:2; padding:15px; border-radius:10px; text-align:center; background-color:#fee2e2; border:2px solid #ef4444; max-width:280px;">
                <h4 style="color:#991b1b; margin:0;">❌ Rejected</h4>
                <h2 style="color:#991b1b; margin:0;">{rejected_count}</h2>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

show_dynamic_cards()

# --- FILTERS ---
col1, col2 = st.columns(2)
with col1:
    cred_filter = st.selectbox(
        "Filter by Credibility",
        options=["All", True, False],
        format_func=lambda x: "All" if x == "All" else ("✅ Approved" if x else "❌ Rejected")
    )
with col2:
    comment_filter = st.selectbox(
        "Filter by Comment",
        options=["All"] + sorted(st.session_state.full_table[comment_col].dropna().unique().tolist())
    )

# --- APPLY FILTERS ---
def get_filtered_table():
    df = st.session_state.full_table
    mask = pd.Series(True, index=df.index)
    if cred_filter != "All":
        mask &= df[cred_col] == cred_filter
    if comment_filter != "All":
        mask &= df[comment_col] == comment_filter
    result = df[mask].copy()
    result["Status"] = result[cred_col].map({True: "✅ Approved", False: "❌ Rejected"})
    return result

filtered_df = get_filtered_table()
display_df = filtered_df.reset_index().rename(columns={'index': '__orig_index'})
cols = ['__orig_index'] + [c for c in display_df.columns if c != '__orig_index']
display_df = display_df[cols]

editor_key = f"main_editor_v{st.session_state.editor_version}"

edited_table = st.data_editor(
    display_df,
    use_container_width=True,
    num_rows="fixed",
    key=editor_key,
    column_config={
        "__orig_index": st.column_config.TextColumn("Row", help="Internal index", disabled=True),
        cred_col: st.column_config.CheckboxColumn(
            "Credibility",
            help="Check = Approved / True, Uncheck = Rejected / False"
        ),
        "Status": st.column_config.TextColumn("Status", disabled=True)
    }
)

# --- UPDATE FULL TABLE WITH EDITS ---
if edited_table is not None:
    updated_full = st.session_state.full_table.copy()
    changes = []
    for _, row in edited_table.iterrows():
        orig_idx = row["__orig_index"]
        if pd.isna(orig_idx):
            continue
        if (
            updated_full.at[orig_idx, cred_col] != row[cred_col]
            or updated_full.at[orig_idx, comment_col] != row[comment_col]
        ):
            updated_full.at[orig_idx, cred_col] = row[cred_col]
            updated_full.at[orig_idx, comment_col] = row[comment_col]
            changes.append(orig_idx)
    if changes:
        st.session_state.full_table = updated_full
        st.session_state.editor_version += 1
        st.success(f"✅ {len(changes)} row(s) updated locally")
        st.rerun()

# --- ADD/UPDATE INFLUENCER FORM ---
st.markdown("---")
with st.expander("➕ Add / Update Influencer"):
    with st.form("add_influencer_form"):
        new_id = st.text_input("ID")
        new_comment = st.text_input("Comment")
        new_cred = st.checkbox("Approved / Credibility", value=True)
        submitted = st.form_submit_button("Add / Update")
        if submitted:
            if not new_id:
                st.error("Please enter ID")
            else:
                idx_list = st.session_state.full_table[st.session_state.full_table[id_col] == new_id].index.tolist()
                if idx_list:
                    idx = idx_list[0]
                    st.session_state.full_table.at[idx, comment_col] = new_comment
                    st.session_state.full_table.at[idx, cred_col] = new_cred
                    st.success(f"✅ Influencer '{new_id}' updated successfully")
                else:
                    new_row = pd.DataFrame({
                        id_col: [new_id],
                        comment_col: [new_comment],
                        cred_col: [new_cred]
                    })
                    st.session_state.full_table = pd.concat([new_row, st.session_state.full_table], ignore_index=True)
                    st.success(f"✅ Influencer '{new_id}' added successfully")
                st.session_state.editor_version += 1
                st.rerun()

# --- GOOGLE SHEET UPDATE ---
@st.cache_data(ttl=300, show_spinner=False)
def update_google_sheet(df, _worksheet_influencers, id_col, cred_col, comment_col):
    df_to_write = df.copy()
    df_to_write[cred_col] = df_to_write[cred_col].map({True: "True", False: "False"})
    values = [df_to_write.columns.tolist()] + df_to_write.values.tolist()
    _worksheet_influencers.clear()
    _worksheet_influencers.update(values)
    return True

if st.button("☁️ Update Influencers List in Google Sheet"):
    try:
        success = update_google_sheet(
            st.session_state.full_table, 
            worksheet_influencers, 
            id_col, 
            cred_col, 
            comment_col
        )
        if success:
            st.success("✅ Google Sheet updated successfully!")
            st.cache_data.clear()
            st.rerun()
    except Exception as e:
        st.error(f"Failed to update Google Sheet: {e}")

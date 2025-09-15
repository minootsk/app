import streamlit as st
import pandas as pd
import io
import re
import hashlib
from utils import get_gsheets_client, get_worksheet_by_key, load_worksheet_df

# --- Page config ---
st.set_page_config(page_title="Influencer Checker", layout="wide", initial_sidebar_state="expanded")

# --- Authentication ---
def check_login():
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

# --- Google Sheets setup ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1pFpU-ClSWJx2bFEdbZzaH47vedgtI8uxhDVXSKX0ZkE/edit#gid=92547169"
SHEET_ID = re.search(r"/d/([a-zA-Z0-9-_]+)", SHEET_URL).group(1)
INF_SHEET = "Influencers List"
MASTER_SHEET = "Master"

@st.cache_resource(show_spinner=False)
def get_sheets():
    client = get_gsheets_client()   # ✅ uses st.secrets
    ws_inf = get_worksheet_by_key(client, SHEET_ID, INF_SHEET)
    ws_master = get_worksheet_by_key(client, SHEET_ID, MASTER_SHEET)
    return ws_inf, ws_master

try:
    worksheet_influencers, worksheet_master = get_sheets()
except Exception as e:
    st.error(f"Failed to connect to Google Sheets: {e}")
    st.stop()

# --- Load and prepare data ---
@st.cache_data(ttl=60, show_spinner=False)
def get_sheet_version(_ws):
    all_values = _ws.get_all_values()
    last_row = "".join(all_values[-1]) if all_values else ""
    version_str = f"{len(all_values)}-{last_row}"
    return hashlib.md5(version_str.encode()).hexdigest()

@st.cache_data(ttl=120, show_spinner="🔄 Loading data from Google Sheets...")
def load_and_prepare_data(_ws_inf, _ws_master):
    inf_df = load_worksheet_df(_ws_inf)
    master_df = load_worksheet_df(_ws_master)
    
    # Ensure columns exist
    inf_df["ID"] = inf_df.get("ID", inf_df.columns[0]).astype(str).str.strip()
    inf_df["Comment"] = inf_df.get("Comment", pd.Series([""] * len(inf_df)))
    inf_df["Credibility"] = inf_df.get("Credibility", pd.Series(["False"] * len(inf_df)))
    inf_df["Credibility"] = inf_df["Credibility"].astype(str).str.strip().str.lower().map({"true": "True", "false": "False"}).fillna("False")
    
    master_df["ID"] = master_df.get("ID", master_df.columns[0]).astype(str).str.strip()
    for col in ["Latest Followers", "Post Price", "Story Price", "Publication date(Miladi)"]:
        if col not in master_df.columns:
            master_df[col] = ""
    try:
        master_df["Publication date(Miladi)"] = pd.to_datetime(master_df["Publication date(Miladi)"], errors="coerce").dt.date
    except Exception:
        master_df["Publication date(Miladi)"] = ""
    
    master_latest_df = master_df.sort_values("Publication date(Miladi)", ascending=False).drop_duplicates(subset="ID", keep="first")
    all_data_df = inf_df.merge(master_latest_df, on="ID", how="left")
    
    for col in ["Latest Followers", "Post Price", "Story Price", "Publication date(Miladi)"]:
        all_data_df[col] = all_data_df[col].fillna("-")
    
    approved_ids = set(inf_df[inf_df["Credibility"] == "True"]["ID"])
    rejected_ids = set(inf_df[inf_df["Credibility"] == "False"]["ID"])
    existing_ids = set(inf_df["ID"])
    
    return all_data_df, approved_ids, rejected_ids, existing_ids

try:
    influencers_version = get_sheet_version(worksheet_influencers)
    master_version = get_sheet_version(worksheet_master)
    all_data_df, approved_ids, rejected_ids, existing_ids = load_and_prepare_data(worksheet_influencers, worksheet_master)
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# --- Helper ---
def credibility_status(val):
    return "✅ Approved" if str(val).lower() == "true" else "❌ Rejected"

# --- File Upload & Processing ---
st.markdown("### 📤 Upload File")
uploaded_file = st.file_uploader("Upload a new influencer file", type=["xlsx", "xls", "csv"])

if uploaded_file:
    @st.cache_data(ttl=300, show_spinner="Processing uploaded file...")
    def process_uploaded_file(_uploaded_file):
        if _uploaded_file.name.endswith(".csv"):
            new_df = pd.read_csv(_uploaded_file)
        else:
            new_df = pd.read_excel(_uploaded_file)
        if "ID" not in new_df.columns:
            new_df.rename(columns={new_df.columns[0]: "ID"}, inplace=True)
        new_df["ID"] = new_df["ID"].astype(str).str.lstrip("@").str.strip()
        new_df["Comment"] = new_df.get("Comment", pd.Series([""] * len(new_df)))
        new_df["Credibility"] = new_df.get("Credibility", pd.Series(["False"] * len(new_df)))
        new_df["Credibility"] = new_df["Credibility"].astype(str).str.strip().str.lower().map({"true": "True", "false": "False"}).fillna("False")
        return new_df

    new_df = process_uploaded_file(uploaded_file)
    approved_matches = new_df[new_df["ID"].isin(approved_ids)]
    rejected_matches = new_df[new_df["ID"].isin(rejected_ids)]
    known_ids = approved_ids.union(rejected_ids).union(existing_ids)
    unknown_matches = new_df[~new_df["ID"].isin(known_ids)]

    file_key_suffix = hashlib.md5(uploaded_file.name.encode()).hexdigest()[:8]

    # --- Rejected Table ---
    st.markdown(
        f'<p style="color:red; font-size:20px;">❌ Rejected Influencers ({len(rejected_matches)})</p>',
        unsafe_allow_html=True
    )
    rejected_table_df = all_data_df[all_data_df["ID"].isin(rejected_matches["ID"])].copy()
    rejected_table_df["Credibility_Status"] = rejected_table_df["Credibility"].map(credibility_status)
    rejected_table_df["Select"] = False
    rejected_edited = st.data_editor(
        rejected_table_df[["ID", "Latest Followers", "Post Price", "Story Price", "Publication date(Miladi)", "Comment", "Credibility_Status", "Select"]].drop_duplicates(subset="ID"),
        use_container_width=True,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select for Download"),
            "Credibility_Status": st.column_config.TextColumn("Credibility", disabled=True)
        },
        key=f"rejected_editor_{file_key_suffix}"
    )

    # --- Approved Table ---
    st.markdown(
        f'<p style="color:green; font-size:20px;">✅ Approved Influencers ({len(approved_matches)})</p>',
        unsafe_allow_html=True
    )
    approved_table_df = all_data_df[all_data_df["ID"].isin(approved_matches["ID"])].copy()
    approved_table_df["Credibility_Status"] = approved_table_df["Credibility"].map(credibility_status)
    approved_table_df["Select"] = False
    approved_edited = st.data_editor(
        approved_table_df[["ID", "Latest Followers", "Post Price", "Story Price", "Publication date(Miladi)", "Comment", "Credibility_Status", "Select"]].drop_duplicates(subset="ID"),
        use_container_width=True,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select for Download"),
            "Credibility_Status": st.column_config.TextColumn("Credibility", disabled=True)
        },
        key=f"approved_editor_{file_key_suffix}"
    )

    # --- Unknown Table ---
    st.markdown(
        f'<p style="color:orange; font-size:20px;">❓ Unknown Influencers ({len(unknown_matches)})</p>',
        unsafe_allow_html=True
    )
    unknown_display_df = unknown_matches[["ID"]].copy()
    unknown_display_df["Comment"] = ""
    unknown_display_df["Approved"] = False
    unknown_display_df["Credibility_Status"] = unknown_display_df["Approved"].map(lambda x: "✅ Approved" if x else "❌ Rejected")
    unknown_display_df["Select_Sheet"] = False
    unknown_edited = st.data_editor(
        unknown_display_df,
        use_container_width=True,
        column_config={
            "Approved": st.column_config.CheckboxColumn("Approved"),
            "Credibility_Status": st.column_config.TextColumn("Credibility", disabled=True),
            "Select_Sheet": st.column_config.CheckboxColumn("Add to Google Sheet"),
        },
        key=f"unknown_editor_{file_key_suffix}"
    )

    # --- Add selected unknowns to Google Sheet ---
    if st.button("☁️ Add Selected Unknowns to Google Sheet"):
        to_add = unknown_edited[unknown_edited["Select_Sheet"]].copy()
        if not to_add.empty:
            to_add["Credibility"] = to_add["Approved"].map(lambda x: "True" if x else "False")
            values_to_append = to_add[["ID", "Comment", "Credibility"]].values.tolist()
            if values_to_append:
                try:
                    worksheet_influencers.append_rows(values_to_append, value_input_option="USER_ENTERED")
                    st.success(f"✅ {len(values_to_append)} row(s) added to Google Sheet")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update Google Sheet: {e}")

    # --- Final Download Table ---
    final_download_ids = pd.concat([
        rejected_edited[rejected_edited["Select"]]["ID"],
        approved_edited[approved_edited["Select"]]["ID"]
    ]).unique()

    final_df = new_df[new_df["ID"].isin(final_download_ids)].copy()
    final_df = final_df[["ID", "Last Update Followers", "New Post Price", "New Story Price"]]

    st.markdown(
        f'<p style="font-size:20px;">🎯 Final Download Table ({len(final_df)})</p>',
        unsafe_allow_html=True
    )
    st.dataframe(final_df, use_container_width=True)

    if not final_df.empty:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            final_df.to_excel(writer, index=False, sheet_name="Final Influencers")
        output.seek(0)
        st.download_button(
            label="⬇️ Download Final Selected Influencers",
            data=output,
            file_name="final_selected_influencers.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

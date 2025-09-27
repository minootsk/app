import streamlit as st
import pandas as pd
import io
import re
import hashlib
import plotly.express as px
from utils import get_gsheets_client, get_worksheet_by_key, load_worksheet_df

# ---------------- Page config ----------------
st.set_page_config(
    page_title="Influencer Checker",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="📑"
)

# ---------------- Session State ----------------
def init_session_state():
    defaults = {
        "data_loaded": False,
        "inf_df": None,
        "master_df": None,
        "ws_inf": None,
        "current_file_hash": None,
        "new_df": None,
        "pending_df": None,
        "rejected_df": None,
        "unknown_df": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
init_session_state()

# ---------------- Sidebar ----------------
with st.sidebar:
    st.title("📑 Influencer Checker")
    st.divider()
    st.success("👋 Welcome")
    if st.button("↻ Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.session_state.data_loaded = False
        st.rerun()

# ---------------- Helper ----------------
@st.cache_data
def format_number(x):
    if pd.isna(x) or x == "" or x is None:
        return ""
    try:
        x = float(x)
        return f"{int(x):,}" if x.is_integer() else f"{x:,.2f}"
    except:
        return str(x)

# ---------------- Google Sheets ----------------
SHEET_URL = "https://docs.google.com/spreadsheets/d/1pFpU-ClSWJx2bFEdbZzaH47vedgtI8uxhDVXSKX0ZkE/edit#gid=92547169"
SHEET_ID = re.search(r"/d/([a-zA-Z0-9-_]+)", SHEET_URL).group(1)
INF_SHEET = "Influencers List"
MASTER_SHEET = "Master"

@st.cache_resource(show_spinner=False)
def get_sheets_client():
    return get_gsheets_client()

# ---------------- Load Influencers (Startup) ----------------
@st.cache_data(ttl=60, show_spinner="↺ Loading Influencers List...")
def load_influencers():
    client = get_sheets_client()
    ws_inf = get_worksheet_by_key(client, SHEET_ID, INF_SHEET)
    inf_df = load_worksheet_df(ws_inf)

    inf_df["ID"] = inf_df.get("ID", inf_df.columns[0]).astype(str).str.strip()
    inf_df["Comment"] = inf_df.get("Comment", pd.Series([""] * len(inf_df)))
    inf_df["Credibility"] = inf_df.get("Credibility", pd.Series(["False"] * len(inf_df)))
    inf_df["Credibility"] = inf_df["Credibility"].astype(str).str.lower()

    return inf_df, ws_inf

# ---------------- Lazy Load Master ----------------
@st.cache_data(ttl=60, show_spinner="↺ Loading Master Sheet...")
def load_master_sheet():
    client = get_sheets_client()
    ws_master = get_worksheet_by_key(client, SHEET_ID, MASTER_SHEET)
    master_df = load_worksheet_df(ws_master)
    return master_df

# ---------------- Initial Load ----------------
if not st.session_state.data_loaded:
    st.session_state.inf_df, st.session_state.ws_inf = load_influencers()
    st.session_state.data_loaded = True

# ---------------- File Upload ----------------
uploaded_file = st.file_uploader(
    "Upload Excel/CSV file",
    type=["xlsx", "xls", "csv"],
    help="File must contain influencer IDs"
)

if uploaded_file:
    file_hash = hashlib.md5(uploaded_file.getvalue()).hexdigest()
    if st.session_state.current_file_hash != file_hash:
        st.session_state.current_file_hash = file_hash
        if uploaded_file.name.endswith(".csv"):
            new_df = pd.read_csv(uploaded_file)
        else:
            new_df = pd.read_excel(uploaded_file)
        if "ID" not in new_df.columns:
            new_df.rename(columns={new_df.columns[0]: "ID"}, inplace=True)
        new_df["ID"] = new_df["ID"].astype(str).str.lstrip("@").str.strip()
        numeric_cols = ["Followers", "Post price", "Avg View", "CPV", "IER", "Avg like", "Avg comments"]
        for col in numeric_cols:
            if col in new_df.columns:
                new_df[col] = pd.to_numeric(new_df[col], errors="coerce")
        st.session_state.new_df = new_df

    new_df = st.session_state.new_df
    inf_df = st.session_state.inf_df

    merged_df = new_df.merge(inf_df, on="ID", how="left", suffixes=("", "_sheet"))
    merged_df["Link"] = "https://www.instagram.com/" + merged_df["ID"]

    rejected_df = merged_df[merged_df["Credibility"] == "false"][ ["ID", "Comment", "Link"] ]
    unknown_df = merged_df[merged_df["Credibility"].isna()][ ["ID", "Link"] ]
    pending_ids = set(new_df["ID"]) - set(rejected_df["ID"]) - set(unknown_df["ID"])

    pending_df = new_df[new_df["ID"].isin(pending_ids)].copy()
    pending_df["Link"] = "https://www.instagram.com/" + pending_df["ID"]
    pending_df["Select"] = True
    pending_df["Compare"] = False

    for col in ["Followers", "Category", "Avg View", "CPV", "IER", "Avg like", "Avg comments", "Post price"]:
        if col not in pending_df.columns:
            pending_df[col] = ""

    unknown_df = unknown_df.copy()
    unknown_df["Comment"] = "No comment yet"
    unknown_df["Select_Sheet"] = False
    unknown_df["Status"] = "Rejected"

    st.session_state.rejected_df = rejected_df
    st.session_state.unknown_df = unknown_df
    st.session_state.pending_df = pending_df

    # ---------------- Title ----------------
    st.markdown("## 🔍 Analyzing Influencers Credibility")

    # ---------------- Tabs ----------------
    tabs = st.tabs([
        f"🕒 Pending ({len(pending_df)})",
        f"❌ Rejected ({len(rejected_df)})",
        f"❓ Unknown ({len(unknown_df)})"
    ])

    # ---------------- Pending Tab ----------------
    with tabs[0]:
        pending_display = pending_df.copy()
        for col in ["Followers", "Post price", "Avg View", "CPV", "IER", "Avg like", "Avg comments"]:
            if col in pending_display.columns:
                pending_display[col] = pending_display[col].apply(format_number)

        display_cols = ["ID", "Link", "Followers", "Category", "Post price", "IER", "Avg like", "Avg comments", "Avg View", "CPV", "Select", "Compare"]
        pending_edited = st.data_editor(
            pending_display[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn("Include in Export", default=True),
                "Compare": st.column_config.CheckboxColumn("Compare History", default=False),
                "Link": st.column_config.LinkColumn("Instagram", display_text="View Profile")
            },
            key="pending_editor"
        )

        # -------- Lazy Load Master Sheet Safely --------
        compare_df = pending_edited[pending_edited["Compare"]]
        if not compare_df.empty:
            if "master_df" not in st.session_state or st.session_state.master_df is None:
                st.session_state.master_df = load_master_sheet()
            master_df = st.session_state.master_df

            st.markdown("### 📈 Compare History")
            for influencer_id in compare_df["ID"]:
                if master_df is not None and "ID" in master_df.columns:
                    influencer_history = master_df[master_df["ID"].astype(str) == str(influencer_id)].dropna(subset=["Publication date(Miladi)"])
                else:
                    st.warning(f"Master sheet data not available for {influencer_id}")
                    continue

                if influencer_history.empty:
                    st.warning(f"No historical data found for {influencer_id}")
                    continue

                # --- Sort by Publication date (Miladi) ---
                influencer_history = influencer_history.sort_values(by="Publication date(Miladi)")

                # --- Format Publication date for hover ---
                influencer_history["Publication date(Miladi)"] = pd.to_datetime(influencer_history["Publication date(Miladi)"]).dt.strftime("%Y-%m-%d")

                # --- Select Y-axis ---
                y_axis_choice = st.selectbox(
                    f"Select Y-axis",
                    options=["Post Price", "Follower"],
                    key=f"y_axis_{influencer_id}"
                )

                # --- Plot line chart with Campaign name on X-axis and hover tooltip ---
                fig = px.line(
                    influencer_history,
                    x="Campaign name",
                    y=y_axis_choice,
                    markers=True,
                    title=f"📊 {influencer_id} - {y_axis_choice} Over Time",
                    hover_data={"Publication date(Miladi)": True, y_axis_choice: True, "Campaign name": True}
                )
                fig.update_layout(
                    xaxis_title="Campaign Name",
                    yaxis_title=y_axis_choice
                )
                st.plotly_chart(fig, use_container_width=True)

        # -------- Export 20-column Excel --------
        selected = pending_edited[pending_edited["Select"]]
        if not selected.empty:
            st.markdown("### 📥 Export Selected Influencers")
            export_df = pd.DataFrame(columns=[f"col{i}" for i in range(1, 21)])
            export_df["col6"] = selected["ID"]
            export_df["col12"] = selected["Link"]
            export_df["col13"] = selected.get("Category", "")
            export_df["col15"] = selected.get("Followers", "")
            export_df["col16"] = selected.get("IER", "")
            export_df["col17"] = selected.get("Avg like", "")
            export_df["col18"] = selected.get("Avg comments", "")
            export_df["col20"] = selected.get("Post price", "")

            col_names = [
                "", "", "", "", "", "ID", "", "", "", "",
                "", "Link", "Category", "", "Follower", "IER", "Avg Like", "Avg Comment", "", "Post Price"
            ]
            export_df.columns = col_names

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                export_df.to_excel(writer, index=False, sheet_name="Selected")
            output.seek(0)

            st.download_button(
                "📥 Download Excel",
                output,
                "selected_influencers.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    # ---------------- Rejected Tab ----------------
    with tabs[1]:
        st.dataframe(rejected_df, use_container_width=True, hide_index=True,
            column_config={"Link": st.column_config.LinkColumn("Instagram", display_text="View Profile")})

    # ---------------- Unknown Tab ----------------
    with tabs[2]:
        unknown_edited = st.data_editor(
            unknown_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=["Approved", "Rejected"]),
                "Select_Sheet": st.column_config.CheckboxColumn("Add to Sheet"),
                "Link": st.column_config.LinkColumn("Instagram", display_text="View Profile"),
                "Comment": st.column_config.TextColumn("Comment")
            },
            key="unknown_editor"
        )
        if st.button("☁️ Add Selected to Google Sheet", type="primary", use_container_width=True):
            to_add = unknown_edited[unknown_edited["Select_Sheet"]]
            if not to_add.empty:
                to_add["Credibility"] = to_add["Status"].map({"Approved": "True", "Rejected": "False"})
                try:
                    st.session_state.ws_inf.append_rows(
                        to_add[["ID", "Comment", "Credibility"]].values.tolist(),
                        value_input_option="USER_ENTERED"
                    )
                    st.success(f"✔️ {len(to_add)} influencer(s) added successfully!")
                    st.cache_data.clear()
                    st.session_state.data_loaded = False
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to update Google Sheet: {e}")

else:
    st.markdown("<h3 style='text-align:center'>👋 Upload a file to start</h3>", unsafe_allow_html=True)

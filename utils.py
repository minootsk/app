import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import streamlit as st
import time
from functools import wraps

# ---------------- Google Sheets API Scopes ----------------
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def retry_on_failure(max_retries=3, delay=1):
    """Decorator for retrying functions on failure."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    time.sleep(delay * (attempt + 1))
            return None
        return wrapper
    return decorator

# ---------------- Google Sheets Client ----------------
@st.cache_resource(show_spinner=False)
@retry_on_failure(max_retries=3)
def get_gsheets_client():
    """
    Authorize and return a gspread client with retry logic.
    Requires service account JSON in Streamlit secrets.
    """
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPE
        )
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ Failed to authenticate with Google Sheets: {str(e)}")
        return None

# ---------------- Worksheet Helpers ----------------
@retry_on_failure(max_retries=2)
def get_worksheet_by_key(client, sheet_id, worksheet_name):
    """Get worksheet with error handling and retry logic."""
    try:
        sheet = client.open_by_key(sheet_id)
        return sheet.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        st.error(f"❌ Worksheet '{worksheet_name}' not found in sheet ID {sheet_id}")
        return None
    except Exception as e:
        st.error(f"❌ Failed to access worksheet: {str(e)}")
        return None

def load_worksheet_df(worksheet):
    """Load worksheet data into DataFrame with optimized parsing."""
    try:
        data = worksheet.get_all_values()
        if not data or len(data) <= 1:
            return pd.DataFrame()
        
        headers = make_unique_headers(data[0])
        df = pd.DataFrame(data[1:], columns=headers)
        
        return optimize_dataframe(df)
    except Exception as e:
        st.error(f"❌ Failed to load data from worksheet: {str(e)}")
        return pd.DataFrame()

# ---------------- DataFrame Utils ----------------
def make_unique_headers(headers):
    """Ensure all headers are unique."""
    seen = {}
    result = []
    for h in headers:
        if h not in seen:
            seen[h] = 0
            result.append(h)
        else:
            seen[h] += 1
            result.append(f"{h}_{seen[h]}")
    return result

def optimize_dataframe(df):
    """Optimize DataFrame memory usage."""
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = pd.to_numeric(df[col], errors="ignore")
            if df[col].dtype == "object" and df[col].nunique() / len(df) < 0.5:
                df[col] = df[col].astype("category")
    return df

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st

# Google Sheets API scopes
SCOPE = ["https://spreadsheets.google.com/feeds", 
         "https://www.googleapis.com/auth/drive"]

def get_gsheets_client():
    """
    Authorize and return a gspread client using credentials stored in Streamlit secrets.
    """
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPE
    )
    return gspread.authorize(creds)

def get_worksheet_by_key(client, sheet_id, worksheet_name):
    sheet = client.open_by_key(sheet_id)
    return sheet.worksheet(worksheet_name)

def get_worksheet_by_url(client, sheet_url, worksheet_name):
    sheet = client.open_by_url(sheet_url)
    return sheet.worksheet(worksheet_name)

def load_worksheet_df(worksheet):
    data = worksheet.get_all_values()
    headers = make_unique_headers(data[0])
    df = pd.DataFrame(data[1:], columns=headers)
    return df

def make_unique_headers(headers):
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

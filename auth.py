# auth.py
import streamlit as st

# Simple authentication system
def check_auth():
    # Define valid credentials
    valid_credentials = {
        "solico": "solico123",
        "minoo": "minoo123"
    }
    
    # Initialize session state
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    # If not authenticated, show login form
    if not st.session_state.authenticated:
        # Simple inline form without extra styling
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Login")
            
            if submit_button:
                if (username in valid_credentials and 
                    password == valid_credentials[username]):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Invalid username or password")
        
        st.stop()
    
    return True

def logout():
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.rerun()
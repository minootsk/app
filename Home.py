import streamlit as st

# Set page config
st.set_page_config(
    page_title="Influencer Web App",
    layout="wide",
)

st.markdown("""
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
<style>
.app-title { font-size:28px !important; font-weight:500; color:#333; margin-bottom:20px; }
.section-header { font-size:24px; font-weight:500; margin-top:22px; margin-bottom:10px; }
.counter-badge {
    display:inline-block;
    background:#eee;
    color:#333;
    font-size:14px;
    font-weight:500;
    padding:2px 8px;
    border-radius:12px;
    margin-left:8px;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="app-title">Influencer Management System</p>', unsafe_allow_html=True)
st.write("Welcome to the Influencer Management System. Use the navigation sidebar on the left to access different pages:")
st.markdown("- **credibility**: View and edit influencer credibility and comments.")
st.markdown("- **List**: See the full, unfiltered list of all influencers.")
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import toml

# Mock loading secrets from the file since st.secrets might not work in standalone script easily
# unless we use specific streamlit loading pattern, but direct toml load is safer for a script
try:
    secrets = toml.load(".streamlit/secrets.toml")
    gcp_secrets = secrets["gcp_service_account"]
except Exception as e:
    print(f"Error loading secrets: {e}")
    exit(1)

print("Authenticating...")
scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(gcp_secrets, scopes=scope)
client = gspread.authorize(creds)
print("Authenticated successfully.")

sheet_name = gcp_secrets.get("sheet_name", "MCMP Feedback")
sheet_id = "1N9YOiOQKgjEbA_P0868FQjVjkykhnPrrOnqPxztYSyY"

print(f"Attempting to open by Name: '{sheet_name}'...")
try:
    sh = client.open(sheet_name)
    print(f"✅ Success! Opened by name '{sheet_name}'. ID: {sh.id}")
except Exception as e:
    print(f"❌ Failed to open by name: {e}")

print(f"\nAttempting to open by Key (ID): '{sheet_id}'...")
try:
    sh = client.open_by_key(sheet_id)
    print(f"✅ Success! Opened by key '{sheet_id}'. Title: {sh.title}")
except Exception as e:
    print(f"❌ Failed to open by key: {e}")

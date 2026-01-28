import streamlit as st
import os
import json
from datetime import datetime
from src.core.engine import RAGEngine
from src.utils.logger import log_info, log_error

def save_feedback(name, feedback):
    """Saves user feedback to Google Sheets (if configured) or local JSON."""
    timestamp = datetime.now().isoformat()
    
    # 1. Try Google Sheets
    if "gcp_service_account" in st.secrets:
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
            client = gspread.authorize(creds)
            
            # Open the sheet
            # 1. Try by ID (most robust)
            sheet_id = st.secrets["gcp_service_account"].get("sheet_id")
            if sheet_id:
                try:
                    sheet = client.open_by_key(sheet_id).sheet1
                except Exception as e:
                     log_error(f"Failed to open by ID {sheet_id}: {e}")
                     raise
            else:
                # 2. Fallback to Name
                sheet_name = st.secrets["gcp_service_account"].get("sheet_name", "MCMP Feedback")
                try:
                    sheet = client.open(sheet_name).sheet1
                except gspread.SpreadsheetNotFound:
                    # Optional: create if not found, but requires Drive write scope/logic
                    log_error(f"Google Sheet '{sheet_name}' not found. Fallback to JSON.")
                    raise
                
            sheet.append_row([timestamp, name, feedback])
            log_info(f"Feedback saved to Google Sheet: {sheet_name}")
            return
        except Exception as e:
            log_error(f"Failed to save to Google Sheets: {e}")
            # Fall through to JSON

    # 2. Local JSON Fallback
    feedback_file = "data/feedback.json"
    os.makedirs("data", exist_ok=True)
    
    entry = {
        "timestamp": timestamp,
        "name": name,
        "feedback": feedback
    }
    
    if os.path.exists(feedback_file):
        with open(feedback_file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []
        
    data.append(entry)
    
    with open(feedback_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def main():
    st.set_page_config(
        page_title="MCMP Activity Chatbot",
        page_icon="🎓",
        layout="centered"
    )

    st.title("MCMP Chatbot")
    st.markdown("Ask me anything about the Munich Center for Mathematical Philosophy: our research, people, history, and upcoming events.\n\nThis is basically Retrieval-Augmented Generation (RAG) + Web scraping ([README](https://github.com/IgnacioOQ/mcmp_chatbot/blob/main/README.md)). It is still very much a demo and it will lack knowledge, but it should be able to provide accurate and up to date information. It is also a little slow, but it gets the job done.")

    # Auto-refresh check
    RAW_DATA_PATH = "data/raw_events.json"
    needs_refresh = False
    if not os.path.exists(RAW_DATA_PATH):
        needs_refresh = True
    else:
        # If older than 24 hours
        mtime = os.path.getmtime(RAW_DATA_PATH)
        if (datetime.now().timestamp() - mtime) > 86400:
            needs_refresh = True

    if needs_refresh and "auto_refreshed" not in st.session_state:
        with st.status("Initializing knowledge base..."):
            from src.scrapers.mcmp_scraper import MCMPScraper
            from src.core.vector_store import VectorStore
            scraper = MCMPScraper()
            scraper.scrape_events()
            scraper.save_to_json()
            vs = VectorStore()
            vs.add_events()
            st.session_state.auto_refreshed = True
            st.rerun()

    # Sidebar for configuration
    with st.sidebar:
        st.header("Calendar")
        
        # Load events for calendar
        try:
            with open("data/raw_events.json", "r") as f:
                raw_events = json.load(f)
            
            from src.utils.calendar_utils import prepare_calendar_events
            from streamlit_calendar import calendar
            
            cal_events = prepare_calendar_events(raw_events)
            
            # Simple calendar view
            calendar_options = {
                "initialView": "dayGridMonth",
                "headerToolbar": {
                    "left": "prev,next",
                    "center": "title",
                    "right": ""
                },
                "height": 400,
            }
            
            calendar(events=cal_events, options=calendar_options)
            
        except Exception as e:
            st.error(f"Could not load calendar: {e}")

        st.markdown("---")
        with st.expander("Give Feedback"):
            with st.form("feedback_form"):
                name = st.text_input("Name (optional)")
                feedback = st.text_area("Your Feedback", help="Let us know what you think!")
                submitted = st.form_submit_button("Submit")
                if submitted and feedback:
                    save_feedback(name, feedback)
                    st.success("Thank you for your feedback!")

    # Initialize RAGEngine
    if "engine" not in st.session_state:
        # Try to get key from secrets, otherwise RAGEngine will fallback to os.getenv
        api_key = st.secrets.get("GEMINI_API_KEY") 
        st.session_state.engine = RAGEngine(provider="gemini", api_key=api_key)

    # Chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # User input
    if prompt := st.chat_input("What is the next talk about?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = st.session_state.engine.generate_response(prompt)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()

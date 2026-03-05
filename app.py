import streamlit as st
import os
import json
from datetime import datetime, timedelta
from src.core.engine import RAGEngine
from src.utils.logger import log_info, log_error

@st.cache_data
def load_raw_events():
    """Cached loader for events data to reduce disk I/O."""
    try:
        with open("data/raw_events.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

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
        page_title="Leopold - The MCMP Chatbot",
        page_icon="🎓",
        layout="wide"
    )

    # Custom CSS to widen sidebar and adjust chat container
    st.markdown("""
        <style>
        [data-testid="stSidebar"] {
            min-width: 450px;
            max-width: 500px;
        }
        .stMainBlockContainer {
            max-width: 900px;
            margin: 0 auto;
            padding-left: 3rem;
            padding-right: 3rem;
        }
        [data-testid="stChatInput"] {
            max-width: 900px;
            margin: 0 auto;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("Leopold - The MCMP Chatbot")
    st.markdown("Ask me anything about the Munich Center for Mathematical Philosophy: our research, people, history, and upcoming events.\n\nThis is basically Retrieval-Augmented Generation (RAG) + Web scraping ([README](https://github.com/IgnacioOQ/mcmp_chatbot/blob/main/README.md)). It is still very much a demo and it will lack knowledge, but it should be able to provide accurate and up to date information. It is also a little slow, but it gets the job done.\n\nPlease use the feedback form on the left to leave comments, it will help improve the bot.")

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
        # 1. Monthly Calendar at the top
        import calendar
        
        # Initialize calendar month/year in session state
        if "cal_year" not in st.session_state:
            st.session_state.cal_year = datetime.now().year
        if "cal_month" not in st.session_state:
            st.session_state.cal_month = datetime.now().month
        
        cal_year = st.session_state.cal_year
        cal_month = st.session_state.cal_month
        
        # Navigation
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("◀", key="prev_month", use_container_width=True):
                if cal_month == 1:
                    st.session_state.cal_month = 12
                    st.session_state.cal_year -= 1
                else:
                    st.session_state.cal_month -= 1
                st.rerun()
        with col2:
            month_name = calendar.month_name[cal_month]
            st.markdown(f"<h4 style='text-align: center; margin: 0; padding: 8px 0;'>{month_name} {cal_year}</h4>", unsafe_allow_html=True)
        with col3:
            if st.button("▶", key="next_month", use_container_width=True):
                if cal_month == 12:
                    st.session_state.cal_month = 1
                    st.session_state.cal_year += 1
                else:
                    st.session_state.cal_month += 1
                st.rerun()
        
        # Build calendar HTML
        today = datetime.now().date()
        cal = calendar.Calendar(firstweekday=0)  # Monday start
        month_days = cal.monthdayscalendar(cal_year, cal_month)
        
        # Load events to highlight days with events
        event_days = set()
        raw_events = load_raw_events()
        for event in raw_events:
            date_str = event.get("metadata", {}).get("date")
            if date_str:
                try:
                    ev_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    if ev_date.year == cal_year and ev_date.month == cal_month:
                        event_days.add(ev_date.day)
                except ValueError:
                    pass
        
        # Streamlit 1.53 strictly enforces DOM closure, so we cannot wrap columns with raw 'div' tags.
        # Instead, we identify buttons purely by their standard Streamlit UI type property.
        st.markdown("""
        <style>
        /* 1. Main Calendar Wrapper Base (Target Streamlit's block container) */
        div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(#calendar-wrapper) {
            background: rgba(30, 41, 59, 0.7) !important;
            backdrop-filter: blur(12px) !important;
            -webkit-backdrop-filter: blur(12px) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 16px !important;
            padding: 16px !important;
            margin-bottom: 12px !important;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2) !important;
        }

        /* 2. Calendar Header */
        .calendar-header {
            display: flex;
            justify-content: space-around;
            margin-bottom: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: 8px;
        }
        .day-header-item {
            color: #94a3b8;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            width: 36px;
            text-align: center;
        }
        
        /* 3. Tighten Streamlit Grid */
        div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(#calendar-wrapper) [data-testid="column"] {
            padding: 0 2px !important;
        }

        /* 4. Base Button Styling (All Days) */
        div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(#calendar-wrapper) [data-testid="column"] button {
            background: rgba(255, 255, 255, 0.03) !important;
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
            padding: 0 !important;
            min-height: 44px !important;
            height: 44px !important;
            width: 100% !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            border-radius: 10px !important;
            transition: all 0.15s ease !important;
            box-shadow: none !important;
        }

        /* 5. 'No Event' / Normal day (Secondary Disabled) */
        div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(#calendar-wrapper) [data-testid="column"] button[data-testid="baseButton-secondary"]:disabled {
            color: #94a3b8 !important;         /* slate-400 */
            font-size: 13px !important;
            font-weight: 500 !important;
            opacity: 0.4 !important;
            cursor: default !important;
        }

        /* 6. 'Has Event' (Secondary Clickable) */
        div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(#calendar-wrapper) [data-testid="column"] button[data-testid="baseButton-secondary"]:not(:disabled) {
            background: rgba(6, 182, 212, 0.1) !important; 
            border: 1px solid rgba(6, 182, 212, 0.4) !important;
            color: #22d3ee !important;         /* cyan-400 */
            font-weight: 600 !important;
            font-size: 13px !important;
            cursor: pointer !important;
            opacity: 1 !important;
            position: relative !important;
        }
        div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(#calendar-wrapper) [data-testid="column"] button[data-testid="baseButton-secondary"]:not(:disabled):hover {
            background: rgba(6, 182, 212, 0.2) !important;
            border-color: rgba(6, 182, 212, 0.6) !important;
            color: #67e8f9 !important;         /* cyan-300 */
            box-shadow: 0 2px 10px rgba(6, 182, 212, 0.2) !important;
            transform: translateY(-2px) !important;
        }

        /* 7. 'Today' Styling (Primary Button) */
        div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(#calendar-wrapper) [data-testid="column"] button[data-testid="baseButton-primary"] {
            background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%) !important; /* indigo to purple gradient */
            border: none !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            font-size: 13px !important;
            box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.3) !important;  
            opacity: 1 !important;
            cursor: pointer !important;
        }
        div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(#calendar-wrapper) [data-testid="column"] button[data-testid="baseButton-primary"]:disabled {
            opacity: 1 !important; /* For days that are "Today" but have no event */
            cursor: default !important;
            color: #ffffff !important;
        }
        div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(#calendar-wrapper) [data-testid="column"] button[data-testid="baseButton-primary"]:not(:disabled):hover {
            background: linear-gradient(135deg, #4f46e5 0%, #9333ea 100%) !important; /* deeper indigo-purple */
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 12px rgba(168, 85, 247, 0.5) !important;
        }
        div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(#calendar-wrapper) [data-testid="column"] button[data-testid="baseButton-primary"] p {
            color: #ffffff !important;
        }

        /* 8. Invisible padding cells for day 0 (Tertiary Button) */
        div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(#calendar-wrapper) [data-testid="column"] button[data-testid="baseButton-tertiary"] {
            opacity: 0 !important;
            pointer-events: none !important;
            background: transparent !important;
            border: none !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Build calendar grid natively wrapped in a container to trigger the CSS rules
        with st.container():
            st.markdown('<div id="calendar-wrapper"></div>', unsafe_allow_html=True)
            
            st.markdown("""
                <div class="calendar-header">
                    <div class="day-header-item">Mo</div>
                    <div class="day-header-item">Tu</div>
                    <div class="day-header-item">We</div>
                    <div class="day-header-item">Th</div>
                    <div class="day-header-item">Fr</div>
                    <div class="day-header-item">Sa</div>
                    <div class="day-header-item">Su</div>
                </div>
            """, unsafe_allow_html=True)
            
            for w, week in enumerate(month_days):
                cols = st.columns(7)
                for i, day in enumerate(week):
                    with cols[i]:
                        if day == 0:
                            # Tertiary buttons are our invisible placeholders for grid alignment
                            st.button(" ", key=f"cal_empty_{cal_year}_{cal_month}_{w}_{i}", use_container_width=True, type="tertiary", disabled=True)
                        else:
                            is_today = day == today.day and cal_month == today.month and cal_year == today.year
                            has_event = day in event_days
                            
                            # Primary means it's today (highlighted), Secondary means it's a normal/event day (dimmed or glow)
                            btn_type = "primary" if is_today else "secondary"
                            disabled = not has_event
                            
                            if st.button(f"{day}", key=f"cal_{cal_year}_{cal_month}_{day}", use_container_width=True, type=btn_type, disabled=disabled):
                                st.session_state.calendar_query_date = f"{cal_year}-{cal_month:02d}-{day:02d}"
                                st.session_state.calendar_query_formatted = datetime(cal_year, cal_month, day).strftime("%B %d, %Y")
        
        st.markdown("---")
        
        # 2. Feedback form
        with st.expander("💬 Give Feedback", expanded=False):
            with st.form("feedback_form"):
                name = st.text_input("Name (optional)")
                feedback = st.text_area("Your Feedback", help="Let us know what you think!")
                submitted = st.form_submit_button("Submit")
                if submitted and feedback:
                    save_feedback(name, feedback)
                    st.success("Thank you for your feedback!")

        st.markdown("---")
        
        # 3. Events this week
        st.header("📆 Events this Week")
        
        # Load and filter events
        try:
            raw_events = load_raw_events()

            today = datetime.now().date()
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            
            events_this_week = []
            
            for event in raw_events:
                meta = event.get("metadata", {})
                date_str = meta.get("date")
                if not date_str:
                    continue

                try:
                    event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    if start_of_week <= event_date <= end_of_week:
                        # Enhanced speaker extraction
                        speaker = meta.get("speaker")
                        title = event.get("title", "Untitled")
                        
                        if not speaker or speaker == "Unknown Speaker":
                            # Heuristic: "Talk: [Speaker Name]" or "Talk (Info): [Speaker Name]"
                            if "Talk" in title and ":" in title:
                                try:
                                    # Split by first colon and strip
                                    parts = title.split(":", 1)
                                    if len(parts) > 1:
                                        speaker = parts[1].strip()
                                except:
                                    pass

                        if not speaker:
                             speaker = "Unknown Speaker"

                        # Enhanced title extraction from description
                        description = event.get("description", "")
                        if "Title:\n" in description:
                            try:
                                # Extract text after "Title:\n"
                                part_after = description.split("Title:\n", 1)[1]
                                # Stop at "Abstract"
                                if "Abstract" in part_after:
                                    real_title = part_after.split("Abstract", 1)[0].strip()
                                    # Clean up newlines if it spans multiple lines
                                    if real_title:
                                        title = real_title.replace("\n", " ")
                            except:
                                pass

                        events_this_week.append({
                            "title": title,
                            "speaker": speaker,
                            "date": event_date,
                            "time": meta.get("time_start", "Time TBA"),
                            "url": event.get("url", "#")
                        })
                except ValueError:
                    continue
            
            events_this_week.sort(key=lambda x: x["date"])
            
            if not events_this_week:
                st.info("No events scheduled for this week.")
            else:
                for ev in events_this_week:
                    date_fmt = ev["date"].strftime("%A, %d")
                    st.markdown(f"**{ev['speaker']}**")
                    st.markdown(f"[{ev['title']}]({ev['url']})")
                    st.caption(f"📅 {date_fmt} at {ev['time']}")
                    st.markdown("---")
            
        except Exception as e:
            st.error(f"Could not load events: {e}")



    # Initialize RAGEngine
    if "engine" not in st.session_state:
        # Try to get key from secrets, otherwise RAGEngine will fallback to os.getenv
        api_key = st.secrets.get("GEMINI_API_KEY") 
        st.session_state.engine = RAGEngine(provider="gemini", api_key=api_key, use_mcp=True)

    # Chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Handle calendar day click via session state (from button clicks)
    if "calendar_query_date" in st.session_state:
        query_formatted = st.session_state.calendar_query_formatted
        # Clear the trigger to prevent re-execution
        del st.session_state.calendar_query_date
        del st.session_state.calendar_query_formatted
        
        # Generate the prompt silently
        auto_prompt = f"What talks or events are scheduled for {query_formatted}? Please provide details about each event, including an abstract or description."
        
        # Add to chat history and generate response
        st.session_state.messages.append({"role": "user", "content": auto_prompt})
        with st.chat_message("user"):
            st.markdown(auto_prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Looking up events..."):
                response = st.session_state.engine.generate_response(
                    auto_prompt, 
                    use_mcp_tools=True, 
                    model_name="gemini-2.0-flash"
                )
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

    # User input
    if prompt := st.chat_input("What is the next talk about?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = st.session_state.engine.generate_response(
                    prompt, 
                    use_mcp_tools=True, 
                    model_name="gemini-2.0-flash"
                )
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()

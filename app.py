import streamlit as st
import os
import json
from datetime import datetime
from src.core.engine import RAGEngine
from src.utils.logger import log_info

def save_feedback(name, feedback):
    """Saves user feedback to a JSON file."""
    feedback_file = "data/feedback.json"
    os.makedirs("data", exist_ok=True)
    
    entry = {
        "timestamp": datetime.now().isoformat(),
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

    st.title("MCMP Intelligence")
    st.markdown("Ask me anything about the Munich Center for Mathematical Philosophy: our research, people, history, and upcoming events.")

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
        st.header("Settings")
        if st.button("Refresh Data"):
            with st.spinner("Scraping and indexing latest events..."):
                from src.scrapers.mcmp_scraper import MCMPScraper
                from src.core.vector_store import VectorStore
                scraper = MCMPScraper()
                scraper.scrape_events()
                scraper.scrape_people()
                scraper.scrape_research()
                scraper.scrape_general()
                scraper.scrape_reading_groups()
                scraper.save_to_json()
                vs = VectorStore()
                vs.add_events()
                st.success("Data refreshed!")

        st.markdown("---")
        with st.expander("Give Feedback"):
            with st.form("feedback_form"):
                name = st.text_input("Name (optional)")
                feedback = st.text_area("Your Feedback", help="Let us know what you think!")
                submitted = st.form_submit_button("Submit")
                if submitted and feedback:
                    save_feedback(name, feedback)
                    st.success("Thank you for your feedback!")

        with st.expander("Admin Access"):
            password = st.text_input("Admin Password", type="password")
            if password == "mcmp2026": # Simple password for demo
                feedback_file = "data/feedback.json"
                if os.path.exists(feedback_file):
                    with open(feedback_file, 'r', encoding='utf-8') as f:
                        feedback_data = json.load(f)
                    
                    st.write(f"Total Feedback: {len(feedback_data)}")
                    st.dataframe(feedback_data)
                    
                    st.download_button(
                        label="Download Feedback JSON",
                        data=json.dumps(feedback_data, indent=4),
                        file_name="feedback.json",
                        mime="application/json"
                    )
                else:
                    st.info("No feedback received yet.")

    # Initialize RAG Engine
    if "engine" not in st.session_state:
        st.session_state.engine = RAGEngine(provider="gemini")

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

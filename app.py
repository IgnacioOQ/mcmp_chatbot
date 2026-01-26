import streamlit as st
import os
from datetime import datetime
from src.core.engine import RAGEngine
from src.utils.logger import log_info

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

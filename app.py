import streamlit as st
import os
from src.core.engine import RAGEngine
from src.utils.logger import log_info

def main():
    st.set_page_config(
        page_title="MCMP Activity Chatbot",
        page_icon="🎓",
        layout="centered"
    )

    st.title("MCMP Activity Chatbot")
    st.markdown("Ask me anything about the Munich Center for Mathematical Philosophy's upcoming talks, workshops, and events.")

    # Sidebar for configuration
    with st.sidebar:
        st.header("Settings")
        provider = st.radio("LLM Provider", ["gemini", "openai", "anthropic"])
        if st.button("Refresh Data"):
            with st.spinner("Scraping and indexing latest events..."):
                from src.scrapers.mcmp_scraper import MCMPScraper
                from src.core.vector_store import VectorStore
                scraper = MCMPScraper()
                scraper.scrape_events()
                scraper.save_to_json()
                vs = VectorStore()
                vs.add_events()
                st.success("Data refreshed!")

    # Initialize RAG Engine
    if "engine" not in st.session_state or st.session_state.provider != provider:
        st.session_state.engine = RAGEngine(provider=provider)
        st.session_state.provider = provider

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

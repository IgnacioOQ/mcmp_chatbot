# Python User Interface Agent Skill
- status: active
- type: agent_skill
- owner: dev-1
- context_dependencies: {"app": "app.py", "engine": "src/core/engine.py"}
<!-- content -->
This file defines the skill/persona for manipulating the Streamlit UI (`app.py`) in the MCMP Chatbot project. Agents should refer to this when asked to modify the frontend.

## UI Architecture Overview
- status: active
- type: context
<!-- content -->
The application is a single-page Streamlit app structured as follows:
1.  **Configuration**: `st.set_page_config` sets the title and layout.
2.  **State Management**: Uses `st.session_state` to persist:
    - `messages`: List of chat history dicts `{"role": "user/assistant", "content": "..."}`.
    - `engine`: The `RAGEngine` instance (lazy-loaded).
    - `auto_refreshed`: Flag to prevent infinite refresh loops.
3.  **Sidebar (`with st.sidebar`)**: Ordered by importance:
    - **Events**: Dynamic list of this week's events.
    - **Feedback**: Expander with a submission form.
    - **Configuration**: Settings like MCP toggle and Model Selection.
4.  **Main Chat Interface**:
    - Renders history loop.
    - Captures input with `st.chat_input`.
    - Generates response with `st.spinner`.

## Modification Protocols
- status: active
- type: protocol
<!-- content -->
When modifying `app.py`, adhere to these rules:

### 1. State Persistence
- status: active
<!-- content -->
Variables lost on rerun must be stored in `st.session_state`.
```python
if "my_feature_enabled" not in st.session_state:
    st.session_state.my_feature_enabled = True
```

### 2. Sidebar Organization
- status: active
<!-- content -->
Maintain the visual hierarchy:
- **Top**: Content relevant to the user *now* (e.g., "Events this Week").
- **Middle**: Interactive forms (e.g., Feedback).
- **Bottom**: System settings and configuration (e.g., "Select Model", "Enable MCP"). Use `st.markdown("---")` to separate sections.

### 3. Async/Blocking Operations
- status: active
<!-- content -->
- Use `st.spinner("Message...")` for any LLM call or network request.
- Do not run heavy computations outside of user interactions or cached resource loading.

### 4. Code Style
- status: active
<!-- content -->
- Keep logic in `src/` modules (e.g., `src/ui/` or `src/core/`) where possible.
- Keep `app.py` focused on layout and state wiring.

## Common Patterns
- status: active
- type: guideline
<!-- content -->

### Adding a Configuration Toggle
Place it at the bottom of the sidebar and pass it to the engine generation call.

```python
with st.sidebar:
    # ... after other sections
    st.markdown("---")
    st.header("Configuration")
    enable_feature = st.toggle("Enable Feature", value=True)

# Usage
if prompt:
    # ...
    response = st.session_state.engine.generate(prompt, enable_feature=enable_feature)
```

### Handling Chat History
Always append to `st.session_state.messages` immediately after displaying.

```python
st.session_state.messages.append({"role": "user", "content": prompt})
with st.chat_message("user"):
    st.markdown(prompt)
```

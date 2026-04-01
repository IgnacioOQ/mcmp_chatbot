# Python User Interface Agent Skill
- status: active
- type: reference
- description: Streamlit UI reference for the MCMP Chatbot: single-page app architecture, session state management, and patterns for modifying the frontend.
- injection: informational

<!-- content -->

This file defines the skill/persona for manipulating the Streamlit UI (`app.py`) in the MCMP Chatbot project. Agents should refer to this when asked to modify the frontend.

## UI Architecture Overview
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
When modifying `app.py`, adhere to these rules:

### 1. State Persistence
Variables lost on rerun must be stored in `st.session_state`.
```python
if "my_feature_enabled" not in st.session_state:
    st.session_state.my_feature_enabled = True
```

### 2. Sidebar Organization
Maintain the visual hierarchy:
- **Top**: Content relevant to the user *now* (e.g., "Events this Week").
- **Middle**: Interactive forms (e.g., Feedback).
- **Bottom**: System settings and configuration (e.g., "Select Model", "Enable MCP"). Use `st.markdown("---")` to separate sections.

### 3. Async/Blocking Operations
- Use `st.spinner("Message...")` for any LLM call or network request.
- Do not run heavy computations outside of user interactions or cached resource loading.

### 4. Code Style
- Keep logic in `src/` modules (e.g., `src/ui/` or `src/core/`) where possible.
- Keep `app.py` focused on layout and state wiring.

## Common Patterns
### Adding a Configuration Toggle
if prompt:
    # ...
    response = st.session_state.engine.generate(prompt, enable_feature=enable_feature)
```

### Handling Chat History
if "cal_year" not in st.session_state:
    st.session_state.cal_year = datetime.now().year
if "cal_month" not in st.session_state:
    st.session_state.cal_month = datetime.now().month

# Navigation buttons
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("◀", key="prev_month", use_container_width=True):
        # Decrement month (wrap to previous year if January)
        if st.session_state.cal_month == 1:
            st.session_state.cal_month = 12
            st.session_state.cal_year -= 1
        else:
            st.session_state.cal_month -= 1
        st.rerun()
with col2:
    month_name = calendar.month_name[st.session_state.cal_month]
    st.markdown(f"<h4 style='text-align: center;'>{month_name} {st.session_state.cal_year}</h4>", unsafe_allow_html=True)
with col3:
    if st.button("▶", key="next_month", use_container_width=True):
        # Increment month (wrap to next year if December)
        ...

# Build calendar grid
cal = calendar.Calendar(firstweekday=0)  # Monday start
month_days = cal.monthdayscalendar(st.session_state.cal_year, st.session_state.cal_month)
```

**Styling the calendar**: Use an HTML/CSS grid for elegant display with gradient backgrounds and day highlighting.

### Native Streamlit Calendar Grid
for week in month_days:
    cols = st.columns(7)
    for i, day in enumerate(week):
        with cols[i]:
            if day == 0:
                st.markdown("<div style='height: 36px;'></div>", unsafe_allow_html=True)
            else:
                has_event = day in event_days
                if has_event:
                    if st.button(f"{day}", key=f"cal_{year}_{month}_{day}", use_container_width=True):
                        st.session_state.calendar_query_date = f"{year}-{month:02d}-{day:02d}"
                else:
                    st.button(f"{day}", key=f"cal_{year}_{month}_{day}", use_container_width=True, disabled=True)
```

### Button Alignment & Consistent Styling
To mimic glassmorphic or highly customized CSS grids *without* breaking Streamlit's native grid, apply CSS overrides targeting Streamlit's internal `data-testid` selectors.

```python
st.markdown("""
<style>
/* 1. Tighten the Streamlit Grid */
[data-testid="stSidebar"] [data-testid="column"] {
    padding: 0 2px !important;
}

/* 2. Base style for ALL calendar buttons */
[data-testid="stSidebar"] [data-testid="column"] button {
    height: 40px !important;
    padding: 0px !important;
    border-radius: 8px !important;
    background: rgba(255, 255, 255, 0.03) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
}

/* 3. Style Specific Types (e.g., Primary = Today) */
[data-testid="stSidebar"] [data-testid="column"] button[data-testid="baseButton-primary"] {
    border: 1px solid rgba(74, 222, 128, 0.4) !important;
    color: #4ade80 !important; 
    font-weight: 700 !important;
}
</style>
""", unsafe_allow_html=True)
```

**Key CSS patterns:**
- Target `[data-testid="column"]` to reduce padding for horizontal calendar alignment.
- Use `button[data-testid="baseButton-primary"]` and `button[data-testid="baseButton-secondary"]` to differentiate days natively without needing custom classes.

### HTML Links Do NOT Work for Interactivity
**Critical limitation**: HTML links (`<a href="...">`) in `st.markdown()` cannot trigger Python callbacks. They navigate to a new page or reload the app.

**Attempted approaches that DON'T work:**
1. Query parameters (`href="?event_day=..."`) - Opens in new window or reloads app
2. JavaScript click handlers - Streamlit doesn't support inline JS execution
3. Fragment links (`href="#..."`) - No way to detect in Python

**The ONLY solution**: Use `st.button()` components. They are the sole mechanism for triggering Python code from user clicks in Streamlit.

**Workaround pattern**: If visual design requires link-like appearance, style buttons to look like links:
```css
button {
    background: transparent !important;
    color: #64ffda !important;
    text-decoration: underline !important;
    cursor: pointer !important;
}
```

### Zip Download of Source Files
When the user wants to download a collection of files, generate a ZIP file in-memory using `io.BytesIO` and `zipfile`.

```python
import zipfile
import io

zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
    for file_path in file_list:
        if os.path.exists(file_path):
             zip_file.write(file_path, arcname=os.path.basename(file_path))

st.download_button(
    label="Download Zip",
    data=zip_buffer.getvalue(),
    file_name="bundle.zip",
    mime="application/zip",
    key="download_btn" # Important!
)
```

**Why this works:** It provides a seamless single-file download for complex contexts without requiring server-side storage.

### Avoiding Stale Caching
Avoid using `@st.cache_resource` or `@st.cache_data` on functions that load mutable system state, such as a file registry that might be updated during the session.

**Anti-Pattern:**
```python
@st.cache_resource
def get_manager():
    return DependencyManager() # BAD: Will hold onto old registry data
```

**Correct Pattern:**
```python
def get_manager():
    return DependencyManager() # GOOD: Reloads fresh data on each rerun
```

### Safe Streamlit CSS & Native Widgets
**Critical limitation**: Streamlit React components (like `st.button`) render *outside* of manually injected HTML `<div>` blocks. You cannot use `st.markdown('<div class="wrapper">', unsafe_allow_html=True)` to wrap a native widget and style it via CSS.

**Attempted approaches that DON'T work:**
```python
# BROKEN: The button renders outside the div in the DOM 
st.markdown('<div class="my-wrapper">', unsafe_allow_html=True)
st.button("Click Me")
st.markdown('</div>', unsafe_allow_html=True)
```

**The Solution**: 
Rely on a native-first Streamlit aesthetic. 
1. Use default layout columns (`st.columns`) and tighten their padding via CSS using Streamlit's `data-testid` attributes.
2. Use native widget themes (like `type="primary"`).
3. If you must inject indicators (like events on a calendar), use Unicode emojis inside the button label instead of complex CSS overlays.
4. Target Streamlit elements explicitly through their `data-testid` properties (e.g., `[data-testid="stSidebar"] [data-testid="column"]`).

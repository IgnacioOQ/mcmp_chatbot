# Python User Interface Agent Skill
- status: active
- type: agent_skill
- owner: dev-1
- label: [agent]
<!-- content -->
- context_dependencies: {"app": "app.py", "engine": "src/core/engine.py"}
<!-- content -->
This file defines the skill/persona for manipulating the Streamlit UI (`app.py`) in the MCMP Chatbot project. Agents should refer to this when asked to modify the frontend.

## UI Architecture Overview
- status: active
- type: documentation
- label: [agent]
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
- type: guideline
- label: [agent, protocol]
<!-- content -->
When modifying `app.py`, adhere to these rules:

### 1. State Persistence
- status: active
- type: agent_skill
- label: [agent]
<!-- content -->
Variables lost on rerun must be stored in `st.session_state`.
```python
if "my_feature_enabled" not in st.session_state:
    st.session_state.my_feature_enabled = True
```

### 2. Sidebar Organization
- status: active
- type: agent_skill
- label: [agent]
<!-- content -->
Maintain the visual hierarchy:
- **Top**: Content relevant to the user *now* (e.g., "Events this Week").
- **Middle**: Interactive forms (e.g., Feedback).
- **Bottom**: System settings and configuration (e.g., "Select Model", "Enable MCP"). Use `st.markdown("---")` to separate sections.

### 3. Async/Blocking Operations
- status: active
- type: agent_skill
- label: [agent]
<!-- content -->
- Use `st.spinner("Message...")` for any LLM call or network request.
- Do not run heavy computations outside of user interactions or cached resource loading.

### 4. Code Style
- status: active
- type: agent_skill
- label: [agent]
<!-- content -->
- Keep logic in `src/` modules (e.g., `src/ui/` or `src/core/`) where possible.
- Keep `app.py` focused on layout and state wiring.

## Common Patterns
- status: active
- type: guideline
- label: [agent]
<!-- content -->

### Adding a Configuration Toggle
- id: python_user_interface_agent_skill.common_patterns.adding_a_configuration_toggle
- status: active
- type: documentation
- last_checked: 2026-02-02
- label: [agent]
<!-- content -->
Place it at the bottom of the sidebar and pass it to the engine generation call.

```python
with st.sidebar:
    # ... after other sections
    st.markdown("---")
    st.header("Configuration")
    enable_feature = st.toggle("Enable Feature", value=True)

# Usage
- id: usage
- status: active
- type: documentation
- last_checked: 2026-02-02
- label: [agent]
<!-- content -->
if prompt:
    # ...
    response = st.session_state.engine.generate(prompt, enable_feature=enable_feature)
```

### Handling Chat History
- id: usage.handling_chat_history
- status: active
- type: documentation
- last_checked: 2026-02-02
- label: [agent]
<!-- content -->
Always append to `st.session_state.messages` immediately after displaying.

```python
st.session_state.messages.append({"role": "user", "content": prompt})
with st.chat_message("user"):
    st.markdown(prompt)
```

### Custom CSS for Layout Control
- status: active
- type: agent_skill
- label: [agent]
<!-- content -->
Use `st.markdown` with `unsafe_allow_html=True` to inject custom CSS. Target Streamlit's internal test IDs:

```python
st.markdown("""
    <style>
    /* Widen sidebar */
    [data-testid="stSidebar"] {
        min-width: 450px;
        max-width: 500px;
    }
    /* Constrain main content and center it */
    .stMainBlockContainer {
        max-width: 900px;
        margin: 0 auto;
        padding-left: 3rem;
        padding-right: 3rem;
    }
    /* Align chat input with main content */
    [data-testid="stChatInput"] {
        max-width: 900px;
        margin: 0 auto;
    }
    </style>
""", unsafe_allow_html=True)
```

### Monthly Calendar with Navigation
- status: active
- type: agent_skill
- label: [agent]
<!-- content -->
Create an interactive monthly calendar using Python's `calendar` module and session state for navigation:

```python
import calendar

# Initialize month/year in session state
- id: initialize_monthyear_in_session_state
- status: active
- type: documentation
- last_checked: 2026-02-02
- label: [agent]
<!-- content -->
if "cal_year" not in st.session_state:
    st.session_state.cal_year = datetime.now().year
if "cal_month" not in st.session_state:
    st.session_state.cal_month = datetime.now().month

# Navigation buttons
- id: navigation_buttons
- status: active
- type: documentation
- last_checked: 2026-02-02
- label: [agent]
<!-- content -->
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
- id: build_calendar_grid
- status: active
- type: documentation
- last_checked: 2026-02-02
- label: [agent]
<!-- content -->
cal = calendar.Calendar(firstweekday=0)  # Monday start
month_days = cal.monthdayscalendar(st.session_state.cal_year, st.session_state.cal_month)
```

**Styling the calendar**: Use an HTML/CSS grid for elegant display with gradient backgrounds and day highlighting.

### Interactive Elements Triggering LLM Queries
- status: active
- type: agent_skill
- label: [agent]
<!-- content -->
To make UI elements (like calendar day buttons) silently trigger LLM queries:

1. **Store trigger data in session state** when the element is clicked:
```python
if st.button(f"{day}", key=f"cal_day_{year}_{month}_{day}"):
    st.session_state.calendar_query_date = date_obj.strftime("%Y-%m-%d")
    st.session_state.calendar_query_formatted = date_obj.strftime("%B %d, %Y")
```

2. **Detect and handle the trigger** before the normal chat input logic:
```python
if "calendar_query_date" in st.session_state:
    query_formatted = st.session_state.calendar_query_formatted
    # Clear trigger to prevent re-execution
    del st.session_state.calendar_query_date
    del st.session_state.calendar_query_formatted
    
    # Generate prompt automatically
    auto_prompt = f"What events are scheduled for {query_formatted}?"
    
    # Add to chat and generate response
    st.session_state.messages.append({"role": "user", "content": auto_prompt})
    with st.chat_message("user"):
        st.markdown(auto_prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Looking up events..."):
            response = st.session_state.engine.generate_response(auto_prompt)
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
```

**Key insight**: Since HTML links can't trigger Python callbacks in Streamlit, use `st.button` components and session state as the communication bridge.

### Highlighting Data-Driven Days
- status: active
- type: agent_skill
- label: [agent]
<!-- content -->
Load event data to determine which days to highlight:

```python
event_days = set()
with open("data/raw_events.json", "r") as f:
    raw_events = json.load(f)
for event in raw_events:
    date_str = event.get("metadata", {}).get("date")
    if date_str:
        ev_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if ev_date.year == cal_year and ev_date.month == cal_month:
            event_days.add(ev_date.day)
```

Then conditionally add CSS classes or render buttons only for those days.

### Native Streamlit Calendar Grid
- status: active
- type: agent_skill
- label: [agent]
<!-- content -->
Build calendars using native Streamlit components for proper interactivity:

```python
import calendar

cal = calendar.Calendar(firstweekday=0)  # Monday start
month_days = cal.monthdayscalendar(cal_year, cal_month)

# Build calendar grid using native Streamlit columns
- id: build_calendar_grid_using_native_streamlit_columns
- status: active
- type: documentation
- last_checked: 2026-02-02
- label: [agent]
<!-- content -->
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
- status: active
- type: agent_skill
- label: [agent]
<!-- content -->
Enabled and disabled buttons can have different default heights. Fix alignment with explicit CSS:

```python
st.markdown("""
<style>
/* Base style for ALL calendar buttons */
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button {
    border: none !important;
    background: transparent !important;
    color: #ccd6f6 !important;
    font-size: 13px !important;
    padding: 8px 4px !important;
    min-height: 36px !important;
    height: 36px !important;          /* Fixed height for alignment */
    line-height: 20px !important;     /* Consistent line-height */
}
/* Disabled buttons - visible but non-interactive */
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button:disabled {
    opacity: 0.6 !important;
    cursor: default !important;
}
/* Event day accent */
.event-day-btn button {
    background: rgba(100, 255, 218, 0.1) !important;
    border: 1px solid rgba(100, 255, 218, 0.3) !important;
    color: #64ffda !important;
    opacity: 1 !important;
}
</style>
""", unsafe_allow_html=True)
```

**Key CSS patterns:**
- Use `height` AND `min-height` for consistent sizing
- Scope selectors to container (e.g., `[data-testid="stSidebar"]`) to avoid affecting other buttons
- Override opacity for styled buttons to prevent disabled-like appearance

### HTML Links Do NOT Work for Interactivity
- status: active
- type: agent_skill
- label: [agent]
<!-- content -->
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
- status: active
- type: agent_skill
- label: [agent]
<!-- content -->
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
- status: active
- type: agent_skill
- label: [agent]
<!-- content -->
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
- status: active
- type: agent_skill
- label: [agent]
<!-- content -->
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

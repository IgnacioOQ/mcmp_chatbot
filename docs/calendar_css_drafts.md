# Calendar CSS Drafts
- status: active
- type: documentation
<!-- content -->

This file stores different iterations and drafts for the Calendar UI CSS in `app.py`.

## Draft 1: Premium Glassmorphism (Current)
- status: active
- type: code_snippet
<!-- content -->

```python
        # Custom CSS for calendar styling
        st.markdown("""
        <style>
        /* Modern Glassmorphic Calendar Container */
        .calendar-wrapper {
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 12px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        }
        
        /* Day Headers */
        .day-headers {
            display: flex;
            justify-content: space-around;
            margin-bottom: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: 8px;
        }
        .day-header {
            flex: 1;
            text-align: center;
            font-weight: 700;
            font-size: 11px;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        /* Premium Button Styling for ALL calendar buttons */
        [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button {
            border: 1px solid transparent !important;
            background: rgba(255, 255, 255, 0.02) !important;
            color: #f8fafc !important;
            font-size: 14px !important;
            font-weight: 500 !important;
            padding: 8px 4px !important;
            min-height: 40px !important;
            height: 40px !important;
            line-height: 22px !important;
            border-radius: 10px !important;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }
        
        /* Hover state for interactive buttons */
        [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button:hover {
            background: rgba(255, 255, 255, 0.08) !important;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }

        /* Disabled buttons (empty days) */
        [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button:disabled {
            opacity: 0.3 !important;
            cursor: default !important;
            background: transparent !important;
            transform: none !important;
            box-shadow: none !important;
        }
        
        /* Event day buttons - Elegant Primary Gradient */
        [data-testid="stSidebar"] .event-day-btn button {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(236, 72, 153, 0.15) 100%) !important;
            border: 1px solid rgba(99, 102, 241, 0.3) !important;
            color: #e0e7ff !important;
            font-weight: 600 !important;
            opacity: 1 !important;
        }
        [data-testid="stSidebar"] .event-day-btn button:hover {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.25) 0%, rgba(236, 72, 153, 0.25) 100%) !important;
            border: 1px solid rgba(99, 102, 241, 0.5) !important;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.2) !important;
        }
        
        /* Today highlight - Vibrant Solid Gradient */
        [data-testid="stSidebar"] .today-btn button {
            background: linear-gradient(135deg, #6366f1 0%, #ec4899 100%) !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            box-shadow: 0 4px 15px rgba(236, 72, 153, 0.4) !important;
            border: none !important;
            opacity: 1 !important;
        }
        [data-testid="stSidebar"] .today-btn button:hover {
            transform: translateY(-2px) scale(1.05);
            box-shadow: 0 6px 20px rgba(236, 72, 153, 0.5) !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Calendar header
        st.markdown("""
        <div class="calendar-wrapper">
            <div class="day-headers">
                <span class="day-header">Mo</span>
                <span class="day-header">Tu</span>
                <span class="day-header">We</span>
                <span class="day-header">Th</span>
                <span class="day-header">Fr</span>
                <span class="day-header">Sa</span>
                <span class="day-header">Su</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Build calendar grid using native Streamlit columns
        for week in month_days:
            cols = st.columns(7)
            for i, day in enumerate(week):
                with cols[i]:
                    if day == 0:
                        st.markdown("<div style='height: 36px;'></div>", unsafe_allow_html=True)
                    else:
                        is_today = day == today.day and cal_month == today.month and cal_year == today.year
                        has_event = day in event_days
                        
                        # Apply CSS class wrapper for styling
                        if has_event and is_today:
                            wrapper_class = "event-day-btn today-btn"
                        elif has_event:
                            wrapper_class = "event-day-btn"
                        elif is_today:
                            wrapper_class = "today-btn"
                        else:
                            wrapper_class = ""
                        
                        if wrapper_class:
                            st.markdown(f'<div class="{wrapper_class}">', unsafe_allow_html=True)
                        
                        if has_event:
                            if st.button(f"{day}", key=f"cal_{cal_year}_{cal_month}_{day}", use_container_width=True):
                                st.session_state.calendar_query_date = f"{cal_year}-{cal_month:02d}-{day:02d}"
                                st.session_state.calendar_query_formatted = datetime(cal_year, cal_month, day).strftime("%B %d, %Y")
                        else:
                            # Non-clickable day - just show the number
                            st.button(f"{day}", key=f"cal_{cal_year}_{cal_month}_{day}", use_container_width=True, disabled=True)
                        
                        if wrapper_class:
                            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")
```

## Draft 3: Native Streamlit Logic (Agent Refactor)
- status: draft
- type: code_snippet
<!-- content -->
```python
        # Scoped, safe CSS to tighten the grid and style the container
        st.markdown("""
        <style>
            /* Tighten column spacing for the calendar grid */
            [data-testid="stSidebar"] [data-testid="column"] {
                padding: 0 2px;
            }
            
            /* Make calendar buttons perfectly square and uniform */
            [data-testid="stSidebar"] button {
                height: 40px !important;
                padding: 0px !important;
                border-radius: 8px !important;
            }
            
            /* Subtle text styling for the native headers */
            .day-header-row {
                display: flex;
                justify-content: space-between;
                margin-bottom: 8px;
                padding: 0 10px;
            }
            .day-header-item {
                color: #94a3b8;
                font-weight: 600;
                font-size: 12px;
                width: 14%;
                text-align: center;
            }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="day-header-row">
            <span class="day-header-item">Mo</span>
            <span class="day-header-item">Tu</span>
            <span class="day-header-item">We</span>
            <span class="day-header-item">Th</span>
            <span class="day-header-item">Fr</span>
            <span class="day-header-item">Sa</span>
            <span class="day-header-item">Su</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Build calendar grid natively
        for week in month_days:
            cols = st.columns(7)
            for i, day in enumerate(week):
                with cols[i]:
                    if day == 0:
                        # Empty placeholder to maintain grid structure
                        st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
                    else:
                        is_today = (day == today.day and cal_month == today.month and cal_year == today.year)
                        has_event = day in event_days
                        
                        # Determine button label and type
                        # Using emoji or unicode dots is the safest way to indicate events in native Streamlit
                        button_label = f"{day}\n🔵" if has_event else str(day)
                        
                        # Use primary button type to naturally highlight "today"
                        btn_type = "primary" if is_today else "secondary"
                        
                        if st.button(
                            button_label, 
                            key=f"cal_{cal_year}_{cal_month}_{day}", 
                            use_container_width=True,
                            type=btn_type
                        ):
                            st.session_state.calendar_query_date = f"{cal_year}-{cal_month:02d}-{day:02d}"
                            st.session_state.calendar_query_formatted = datetime(cal_year, cal_month, day).strftime("%B %d, %Y")
        
        st.markdown("---")
```

## Draft 2: Minimalist Bright (Alternative)
- status: draft
- type: code_snippet
<!-- content -->
```python
        st.markdown("""
        <style>
        /* Minimalist Light/Dark Aware Container */
        .calendar-wrapper {
            background: transparent;
            border: 1px solid rgba(150, 150, 150, 0.2);
            border-radius: 8px;
            padding: 8px;
            margin-bottom: 12px;
        }
        
        .day-headers {
            display: flex;
            justify-content: space-around;
            margin-bottom: 8px;
            border-bottom: 1px solid rgba(150, 150, 150, 0.1);
            padding-bottom: 4px;
        }
        .day-header {
            flex: 1;
            text-align: center;
            font-weight: 500;
            font-size: 12px;
            color: #64748b;
        }
        
        [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button {
            border: none !important;
            background: transparent !important;
            color: inherit !important;
            border-radius: 50% !important; /* Circular buttons */
            min-height: 36px !important;
            height: 36px !important;
            width: 36px !important;
            padding: 0 !important;
            margin: 0 auto !important;
        }
        
        [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button:hover {
            background: rgba(150, 150, 150, 0.1) !important;
        }

        [data-testid="stSidebar"] .event-day-btn button {
            background: rgba(99, 102, 241, 0.1) !important;
            color: #6366f1 !important;
            font-weight: bold !important;
        }
        
        [data-testid="stSidebar"] .today-btn button {
            background: #6366f1 !important;
            color: white !important;
            box-shadow: 0 2px 5px rgba(99, 102, 241, 0.4) !important;
        }
        </style>
        """, unsafe_allow_html=True)
```

import time
import json
import streamlit as st
from datetime import datetime, timedelta

@st.cache_data
def load_events():
    try:
        with open("data/raw_events.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def load_events_baseline():
    start = time.time()
    for _ in range(100):
        try:
            with open("data/raw_events.json", "r") as f:
                raw_events = json.load(f)
            # simulate usage
            count = 0
            for event in raw_events:
                meta = event.get("metadata", {})
                date_str = meta.get("date")
                if date_str:
                    count += 1
        except FileNotFoundError:
            pass
    return time.time() - start

def load_events_optimized():
    start = time.time()
    for _ in range(100):
        raw_events = load_events()
        # simulate usage
        count = 0
        for event in raw_events:
            meta = event.get("metadata", {})
            date_str = meta.get("date")
            if date_str:
                count += 1
    return time.time() - start

if __name__ == "__main__":
    t_base = load_events_baseline()
    t_opt = load_events_optimized()
    print(f"Baseline (100 runs): {t_base:.4f} seconds")
    print(f"Optimized (100 runs): {t_opt:.4f} seconds")

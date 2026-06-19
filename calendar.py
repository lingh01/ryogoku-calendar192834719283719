import streamlit as st
from streamlit_calendar import calendar
from datetime import datetime
import requests

SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzhDt08hJDuXwJFYxQ5BXkhlsK9xpl3ClmR22mL-mUFLe9o8Sf_G0Hix1TyNmyNXYvs/exec"

# --- PASSWORD PROTECTION ---
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Please enter your password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Please enter your password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        return True

# --- MAIN APP EXECUTION ---
if check_password():
    st.title("発送件カレンダー 📅")
    

    # ==========================================
    # NEW: CACHED DATA FETCHING
    # ==========================================
    @st.cache_data(ttl=300) # Memorizes the data for 5 minutes (300 seconds)
    def fetch_calendar_data():
        try:
            response = requests.get(SCRIPT_URL)
            if response.status_code == 200:
                return response.json()
            return []
        except:
            return []

    # ==========================================
    # 1. EVENT CREATION FORM
    # ==========================================
    with st.sidebar:
        st.header("➕ 新しい発送件を追加")
        
        with st.form("add_event_form", clear_on_submit=True):
            # Easily add/remove fields here:
            event_title = st.text_input("タイトル")
            start_date = st.date_input("日付")
            shipping_type = st.selectbox("発送方法", ["通常発送", "自社都合追加発送", "他社都合追加発送", "緊急発送", "ハンドキャリー", "その他（e.g. 先方が受け取りに来る場合）"])
            pic_name = st.text_input("担当者")
            item_count = st.number_input("発送件数", min_value=1, step=1)
            
            submit_btn = st.form_submit_button("追加")
            
            if submit_btn:
                if event_title:
                    # Map your fields to a dictionary. 
                    # Keys MUST match your Google Sheet headers exactly!
                    event_data = {
                        "Title": event_title,
                        "Start Date": str(start_date),
                        "Shipping Type": shipping_type,
                        "PIC": pic_name,
                        "Item Count": item_count
                    }
                    
                    with st.spinner("Saving to Google Sheets..."):
                        response = requests.post(SCRIPT_URL, json=event_data)
                        
                    if response.status_code == 200 and response.json().get("status") == "success":
                        st.success("発送件を追加しました！")

                        fetch_calendar_data.clear()
                        st.rerun()
                    else:
                        st.error("エラーが起こりました。もう一度お試しください。")
                else:
                    st.warning("タイトルを入力してください。")


    # ==========================================
    # 2. FETCH DATA & DISPLAY CALENDAR
    # ==========================================
    @st.fragment
    def show_calendar():

        sheet_data = fetch_calendar_data()

        # Format data for the calendar component
        calendar_events = []
        for row in sheet_data:
            if row.get("Title") and row.get("Start Date"):
                color = "#3BB873" if row.get("Shipping Type") == "Local" else "#FF6C6C"
                calendar_events.append({
                    "title": f"{row.get('Title')} ({row.get('PIC', 'N/A')})",
                    "start": str(row.get("Start Date")).split("T")[0], 
                    "backgroundColor": color,
                    "borderColor": color,
                    # --- NEW: Store your custom variables here! ---
                    "extendedProps": {
                        "Title": row.get("Title", "N/A"),
                        "Shipping Type": row.get("Shipping Type", "N/A"),
                        "PIC": row.get("PIC", "N/A"),
                        "Item Count": row.get("Item Count", "N/A")
                    }
                })

        calendar_options = {
            "headerToolbar": {"left": "today prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek"},
            "initialView": "dayGridMonth",
            "locale": "ja",  
        }

        # --- NEW: Catch the state of the calendar ---
        custom_css = """
        /* Saturday: Blue text and light blue background */
        .fc-day-sat .fc-col-header-cell-cushion, 
        .fc-day-sat .fc-daygrid-day-number {
            color: #0066cc !important; 
        }
        .fc-day-sat {
            background-color: #f0f8ff !important; 
        }

        /* Sunday: Red text and light red background */
        .fc-day-sun .fc-col-header-cell-cushion, 
        .fc-day-sun .fc-daygrid-day-number {
            color: #cc0000 !important; 
        }
        .fc-day-sun {
            background-color: #fff0f0 !important; 
        }
        """

        # --- NEW: Add the custom_css parameter here ---
        cal_state = calendar(
            events=calendar_events, 
            options=calendar_options, 
            custom_css=custom_css
        )

        

        # --- NEW: Display event details if an event is clicked ---
        if cal_state.get("eventClick"):
            st.divider()
            st.subheader("🔍 Event Details")
            
            # The clicked event's data is buried inside the state dictionary
            clicked_event = cal_state["eventClick"]["event"]
            props = clicked_event["extendedProps"]
            
            # Display it nicely in columns
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**タイトル:** {props.get('Title')}")
                st.markdown(f"**Date:** {clicked_event['start'].split('T')[0]}")
            with col2:
                st.markdown(f"**発送方法:** {props.get('Shipping Type')}")
                st.markdown(f"**担当者:** {props.get('PIC')}")
                st.markdown(f"**発送件数:** {props.get('Item Count')}")

    show_calendar()
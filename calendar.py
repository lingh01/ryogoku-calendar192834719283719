import streamlit as st
from streamlit_calendar import calendar
from datetime import datetime
import requests
import pandas as pd
import uuid  # NEW: We need this to generate unique IDs for each row

SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzhDt08hJDuXwJFYxQ5BXkhlsK9xpl3ClmR22mL-mUFLe9o8Sf_G0Hix1TyNmyNXYvs/exec"

# --- PASSWORD PROTECTION ---
def check_password():
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
    # CACHED DATA FETCHING
    # ==========================================
    @st.cache_data(ttl=300) 
    def fetch_database_data():
        """Fetches both Events and Titles from Google Sheets"""
        try:
            response = requests.get(SCRIPT_URL)
            if response.status_code == 200:
                return response.json()
            return {"events": [], "titles": []}
        except:
            return {"events": [], "titles": []}

    # Extract our data from the payload
    db_data = fetch_database_data()
    sheet_data = db_data.get("events", [])
    fetched_titles = db_data.get("titles", [])
    
    # Build our title options dynamically from the spreadsheet
    TITLE_OPTIONS = fetched_titles + ["その他（自由入力）"]

    # ==========================================
    # 1. SIDEBAR FORMS
    # ==========================================
    with st.sidebar:
        
        # --- NEW: Form to permanently add a new title ---
        with st.expander("⚙️ 取引先/タイトルを登録"):
            new_title_input = st.text_input("新しいタイトル名")
            if st.button("データベースに保存"):
                if new_title_input and new_title_input not in fetched_titles:
                    payload = {
                        "action": "add_title", 
                        "Title": new_title_input
                    }
                    with st.spinner("保存中..."):
                        requests.post(SCRIPT_URL, json=payload)
                    fetch_database_data.clear() # Clear cache to fetch the new title
                    st.success("追加しました！")
                    st.rerun()
                elif new_title_input in fetched_titles:
                    st.warning("すでに登録されています。")

        st.divider()

        st.header("➕ 新しい発送件を追加")
        
        with st.form("add_event_form", clear_on_submit=True):
            # --- FIXED: Always show both, decide on submit ---
            selected_title = st.selectbox("タイトル", TITLE_OPTIONS)
            custom_title = st.text_input("※「その他」を選んだ場合のみ入力してください")
            
            start_date = st.date_input("日付")
            
            shipping_options = ["通常発送", "自社都合追加発送", "他社都合追加発送", "緊急発送", "ハンドキャリー", "その他（e.g. 先方が受け取りに来る場合）"]
            shipping_type = st.selectbox("発送方法", shipping_options)

            shipping_regions_list = ["国内", "海外"]
            shipping_region = st.selectbox("発送地域", shipping_regions_list)
            
            pic_name = st.text_input("担当者")
            item_count = st.number_input("発送件数", min_value=1, step=1)

            submit_btn = st.form_submit_button("追加")
            
            if submit_btn:
                # Figure out which title to use before saving
                if selected_title == "その他（自由入力）":
                    final_title = custom_title
                else:
                    final_title = selected_title

                if final_title: # Make sure it isn't blank
                    event_data = {
                        "action": "add", 
                        "ID": str(uuid.uuid4()), 
                        "Title": final_title, # Use final_title here!
                        "Start Date": str(start_date),
                        "Shipping Type": shipping_type,
                        "Shipping Region": shipping_region,
                        "PIC": pic_name,
                        "Item Count": item_count
                    }
                    
                    with st.spinner("追加中..."):
                        response = requests.post(SCRIPT_URL, json=event_data)
                        
                    if response.status_code == 200 and response.json().get("status") == "success":
                        st.success("発送件を追加しました！")
                        fetch_database_data.clear()
                        st.rerun()
                    else:
                        st.error("エラーが起こりました。もう一度お試しください。")
                else:
                    st.warning("タイトルを入力してください。")

    # ==========================================
    # 2. CALENDAR DISPLAY & EDITING
    # ==========================================
    @st.fragment
    def show_calendar():
        calendar_events = []
        for row in sheet_data:
            if row.get("Title") and row.get("Start Date"):
                color = "#3BB873" if row.get("Shipping Type") == "Local" else "#FF6C6C"
                calendar_events.append({
                    "title": f"{row.get('Title')} ({row.get('PIC', 'N/A')})",
                    "start": str(row.get("Start Date")).split("T")[0], 
                    "backgroundColor": color,
                    "borderColor": color,
                    "extendedProps": {
                        "ID": row.get("ID", ""), 
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

        custom_css = """
        .fc-day-sat .fc-col-header-cell-cushion, 
        .fc-day-sat .fc-daygrid-day-number { color: #0066cc !important; }
        .fc-day-sat { background-color: #f0f8ff !important; }
        .fc-day-sun .fc-col-header-cell-cushion, 
        .fc-day-sun .fc-daygrid-day-number { color: #cc0000 !important; }
        .fc-day-sun { background-color: #fff0f0 !important; }
        """

        cal_state = calendar(
            events=calendar_events, 
            options=calendar_options, 
            custom_css=custom_css
        )

        if cal_state.get("eventClick"):
            st.divider()
            st.subheader("🔍 詳細 / 編集 (Details & Edit)")
            
            clicked_event = cal_state["eventClick"]["event"]
            props = clicked_event["extendedProps"]
            event_id = props.get("ID")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**タイトル:** {props.get('Title')}")
                st.markdown(f"**Date:** {clicked_event['start'].split('T')[0]}")
            with col2:
                st.markdown(f"**発送方法:** {props.get('Shipping Type')}")
                st.markdown(f"**発送地域:** {props.get('Shipping Region')}")
                st.markdown(f"**担当者:** {props.get('PIC')}")
                st.markdown(f"**発送件数:** {props.get('Item Count')}")

            if event_id:
                with st.expander("✏️ この予定を編集・削除する (Edit / Delete)"):
                    with st.form("edit_event_form"):
                        
                        current_title = props.get("Title")
                        if current_title in TITLE_OPTIONS:
                            default_title_index = TITLE_OPTIONS.index(current_title)
                            default_custom_title = ""
                        else:
                            default_title_index = TITLE_OPTIONS.index("その他（自由入力）")
                            default_custom_title = current_title 

                        # --- FIXED: Always show both in the edit form too ---
                        edit_selected_title = st.selectbox("タイトル", TITLE_OPTIONS, index=default_title_index)
                        edit_custom_title = st.text_input("※「その他」を選んだ場合のみ入力してください", value=default_custom_title)
                        
                        try:
                            parsed_date = datetime.strptime(clicked_event['start'].split('T')[0], "%Y-%m-%d").date()
                        except:
                            parsed_date = datetime.now().date()
                        edit_date = st.date_input("日付", value=parsed_date)
                        
                        shipping_options = ["通常発送", "自社都合追加発送", "他社都合追加発送", "緊急発送", "ハンドキャリー", "その他（e.g. 先方が受け取りに来る場合）"]
                        
                        try:
                            default_shipping_index = shipping_options.index(props.get("Shipping Type"))
                        except ValueError:
                            default_shipping_index = 0
                        
                        shipping_regions_list = ["国内", "海外"]
                        try:
                            default_shipping_region = shipping_regions_list.index(props.get("Shipping Region"))
                        except ValueError:
                            default_shipping_region = 0

                        edit_shipping = st.selectbox("発送方法", shipping_options, index=default_shipping_index)
                        edit_pic = st.text_input("担当者", value=props.get("PIC"))
                        
                        try:
                            default_count = int(props.get("Item Count"))
                        except:
                            default_count = 1
                        edit_count = st.number_input("発送件数", min_value=1, step=1, value=default_count)

                        colA, colB = st.columns(2)
                        with colA:
                            submit_edit = st.form_submit_button("更新 (Update)")
                        with colB:
                            submit_delete = st.form_submit_button("🗑️ 削除 (Delete)")

                        if submit_edit:
                            # Figure out the title to update
                            if edit_selected_title == "その他（自由入力）":
                                final_edit_title = edit_custom_title
                            else:
                                final_edit_title = edit_selected_title

                            update_data = {
                                "action": "edit",
                                "ID": event_id,
                                "Title": final_edit_title, # Use final_edit_title here!
                                "Start Date": str(edit_date),
                                "Shipping Type": edit_shipping,
                                "PIC": edit_pic,
                                "Item Count": edit_count
                            }
                            with st.spinner("更新中..."):
                                requests.post(SCRIPT_URL, json=update_data)
                            fetch_database_data.clear()
                            st.rerun()
                            
                        if submit_delete:
                            delete_data = {
                                "action": "delete",
                                "ID": event_id
                            }
                            with st.spinner("削除中..."):
                                requests.post(SCRIPT_URL, json=delete_data)
                            fetch_database_data.clear()
                            st.rerun()
            else:
                st.warning("⚠️ このイベントはIDがないため編集できません (古いデータです)。")

    # ==========================================
    # 3. TABS: CALENDAR & GRAPH
    # ==========================================
    tab1, tab2 = st.tabs(["📅 発送カレンダー ", "📈 進捗グラフ"])
    with tab1:
        show_calendar()

    with tab2:
        st.subheader("日別梱包数")
    
    # Paste your published CSV link here
    SHEET_CSV_URL = "YOUR_PUBLISHED_CSV_LINK_HERE" 
    
    try:
        # Read the data from the Google Sheet
        df = pd.read_csv(SHEET_CSV_URL)
        
        # Clean up the columns so Streamlit can chart them properly
        # Make sure these names exactly match your Google Sheet headers!
        df["Date"] = pd.to_datetime(df["Date"]).dt.date
        df["Count"] = pd.to_numeric(df["Count"], errors="coerce").fillna(0)
        
        # Group by date (just in case they put multiple entries for one day)
        daily_data = df.groupby("Date")["Count"].sum().reset_index()
        daily_data.set_index("Date", inplace=True)
        
        # Draw the graph
        st.bar_chart(daily_data)
        
    except Exception as e:
        st.info("データがまだありません、または読み込めません。")
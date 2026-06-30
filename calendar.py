import streamlit as st
from streamlit_calendar import calendar
from datetime import datetime
import requests
import pandas as pd
from fpdf import FPDF
import base64
import tempfile
import os
from PIL import Image
from streamlit_pdf_viewer import pdf_viewer
import plotly.express as px  # <-- ADD THIS LINE
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
def show_main_dashboard():
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

    packaging_data = db_data.get("packaging", [])
    
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

        if st.button("🔄 データを更新"):
            fetch_database_data.clear()
            st.rerun()
        
        if packaging_data:
            # 1. Convert the JSON payload directly into a Pandas DataFrame
            df = pd.DataFrame(packaging_data)
            
            # 2. Clean up the columns so Streamlit can chart them properly
            # (Assuming your headers in the sheet are exactly "Date" and "Count")
            if "日付" in df.columns and "件数" in df.columns:
                # Force read as UTC, convert to Japan time (+9 hours), then extract the date
                df["Date"] = pd.to_datetime(df["日付"], utc=True).dt.tz_convert("Asia/Tokyo").dt.date
                df["Count"] = pd.to_numeric(df["件数"], errors="coerce").fillna(0)
                
                # 3. Group by date in case there are multiple entries per day
                daily_data = df.groupby("Date")["Count"].sum().reset_index()
                daily_data.set_index("Date", inplace=True)

                # --- NEW: Format the dates as "〇月〇日" strings ---
                # This pulls the month and day, formats them, and makes them text labels
                # so it still prevents that weird hour-by-hour zooming!
                daily_data.index = daily_data.index.map(lambda d: f"{d.month}月{d.day}日")
                # 4. Draw the graph!
                # 4. Draw the graph using Plotly!
                fig = px.line(
                    daily_data, 
                    x=daily_data.index, 
                    y="Count", 
                    markers=True, # Adds dots to the data points
                )
                
                # Optional: customize axis labels to match your Japanese text
                fig.update_layout(
                    xaxis_title="日付",
                    yaxis_title="件数"
                )
                
                st.plotly_chart(fig, width="stretch")
            else:
                st.error("スプレッドシートの列名が '日付' と '件数' ではありません。")
        else:
            st.info("データがまだありません。")



def show_pdf(file_path):
    # This library handles the rendering safely without using iframes
    pdf_viewer(file_path, height=800)

def add_step():
    # We use uuid to give each block a unique key for Streamlit widgets
    st.session_state.blocks.append({
        'id': str(uuid.uuid4()), 
        'type': 'step'
    })

def add_table():
    st.session_state.blocks.append({
        'id': str(uuid.uuid4()), 
        'type': 'table',
        # Provide a default empty dataframe
        'data': pd.DataFrame([{"Column 1": "", "Column 2": ""}])
    })

def show_blog():

    # 1. Make sure the 'static' folder exists on the server
    if not os.path.exists("static"):
        os.makedirs("static")

    # 1. Initialize the session state to hold our blocks
    if 'blocks' not in st.session_state:
        st.session_state.blocks = []

    

    st.title("マニュアル作成ツール")
    # ADD THIS LINE:
    manual_title = st.text_input("マニュアルのタイトル", value="マニュアル", key="manual_title_input")
    st.markdown("---")

    # 2. Loop through and render the blocks
    step_counter = 1 # Keep track of the step numbers

    for block in st.session_state.blocks:
        block_id = block['id']
        
        # Render a Step
        if block['type'] == 'step':
            st.subheader(f"ステップ {step_counter}")
            
            # Unique keys are required for Streamlit widgets inside loops
            st.text_input("本文（必須）", key=f"main_{block_id}")
            st.text_area("補足説明（任意）", key=f"sub_{block_id}")
            st.file_uploader("画像アップロード（任意）", type=['png', 'jpg', 'jpeg'], key=f"img_{block_id}", accept_multiple_files=True)
            
            step_counter += 1
            st.markdown("---")

        # Render a Table
        elif block['type'] == 'table':
            st.subheader("表 (Table)")
            
            # --- NEW: Add Column UI ---
            # We use columns to put the input box and button side-by-side
            col_input, col_btn = st.columns([3, 1])
            
            with col_input:
                # Input for the new column name
                new_col_name = st.text_input("新しい列名", key=f"col_input_{block_id}")
                
            with col_btn:
                # We add a bit of vertical space so the button aligns with the text box
                st.write("") 
                st.write("")
                if st.button("➕ 列を追加 ", key=f"add_col_btn_{block_id}", width="stretch"):
                    if new_col_name:
                        # Add the new column to the dataframe with empty strings
                        block['data'][new_col_name] = ""
                        # Refresh the app immediately to show the new column
                        st.rerun() 
            # --------------------------

            # The actual data editor
            # We save the output back to block['data'] so user edits are kept!
            # --- NEW: UI to Rename Existing Columns ---
            with st.expander("✏️ 既存の列名を変更"):
                rename_dict = {}
                for col_name in block['data'].columns:
                    # Create a text input for each existing column
                    new_name = st.text_input(f"'{col_name}' の新しい名前:", value=col_name, key=f"rename_{block_id}_{col_name}")
                    rename_dict[col_name] = new_name
                    
                if st.button("列名を更新", key=f"update_cols_btn_{block_id}"):
                    # Apply the new names to the dataframe and refresh
                    block['data'] = block['data'].rename(columns=rename_dict)
                    st.rerun()
            # ------------------------------------------

            block['data'] = st.data_editor(
                block['data'], 
                num_rows="dynamic", 
                key=f"table_{block_id}", 
                width="stretch"
            )
            # The actual data editor
    
    # 3. The Add Buttons at the bottom
    col1, col2 = st.columns(2)
    with col1:
        st.button("➕ ステップ追加", on_click=add_step, width="stretch")
    with col2:
        st.button("➕ 表の追加", on_click=add_table, width="stretch")
    
    st.subheader("出力")

    if st.button("📄 マニュアルをPDF化する", width="stretch"):
        # 1. Initialize A4 PDF
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.add_page()
        
        # 2. Setup Japanese Font (MUST have this file in your repo!)
        # Change 'NotoSansJP-Regular.ttf' to whatever font file you download
        try:
            pdf.add_font("NotoSansJP", style="", fname="NotoSansJP-VariableFont_wght.ttf")
            pdf.set_font("NotoSansJP", size=12)
        except RuntimeError:
            st.error("Font file missing! Please add 'NotoSansJP-Regular.ttf' to your folder.")
            st.stop()

        # Title (Now dynamic!)
        pdf.set_font("NotoSansJP", size=18)
        # We use the variable 'manual_title' from the top of the function
        pdf.cell(0, 10, txt=manual_title, ln=True, align="C")
        pdf.ln(10)

        # 3. Loop through blocks and print to PDF
        step_counter = 1
        
        for block in st.session_state.blocks:
            block_id = block['id']
            
            if block['type'] == 'step':
                # Get text from session state (Streamlit saves widget values in st.session_state using their keys)
                main_text = st.session_state.get(f"main_{block_id}", "")
                sub_text = st.session_state.get(f"sub_{block_id}", "")
                uploaded_img = st.session_state.get(f"img_{block_id}", None)

                # Write Step Header & Main Text
                pdf.set_font("NotoSansJP", size=14)
                pdf.cell(0, 10, txt=f"{step_counter}. {main_text}", ln=True)
                
                # Write Sub-text if it exists
                if sub_text:
                    pdf.set_font("NotoSansJP", size=10)
                    # multi_cell handles text wrapping automatically
                    pdf.multi_cell(0, 6, txt=sub_text)
                
                # Handle Image if it exists
            # uploaded_img is now a list, so we check if it is truthy (not None and not empty)
            if uploaded_img:
                
                # Iterate through each uploaded file in the list
                for img_file in uploaded_img:
                    try:
                        # 1. Open image with Pillow to handle format safely
                        img = Image.open(img_file)
                        
                        # 2. Flatten transparency layers to avoid silent white-out errors
                        if img.mode == "RGBA":
                            background = Image.new("RGB", img.size, (255, 255, 255))
                            background.paste(img, mask=img.split()[3])
                            img = background
                        else:
                            img = img.convert("RGB")
                        
                        # 3. Save to a temporary JPEG file
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                            img.save(tmp_file.name, format="JPEG")
                            tmp_file_path = tmp_file.name
                        
                        # 4. Insert image with an EXPLICIT X coordinate position
                        # OPTION A: Left-aligned with text margins
                        pdf.image(tmp_file_path, x=pdf.l_margin, w=100)
                        
                        # OPTION B: Center it on the A4 page instead (Uncomment below if preferred)
                        # pdf.image(tmp_file_path, x=(210 - 100) / 2, w=100)
                        
                        # OPTIONAL: Add a line break so multiple images don't overlap vertically
                        pdf.ln(5) 
                        
                        os.remove(tmp_file_path) # Clean up temp file
                        
                    except Exception as img_err:
                        st.error(f"画像の埋め込み中にエラーが発生しました ({img_file.name}): {img_err}")
                    
                pdf.ln(5) # Add space after the step
                step_counter += 1

            elif block['type'] == 'table':
                df = block['data']
                pdf.set_font("NotoSansJP", size=10)
                
                # Calculate column width dynamically based on A4 width (approx 190mm usable)
                num_columns = len(df.columns)
                if num_columns > 0:
                    col_width = 190 / num_columns
                    
                    # Print Table Rows
                    for index, row in df.iterrows():
                        # Save the starting Y position for this row
                        start_y = pdf.get_y()
                        max_y = start_y # Keep track of the tallest cell
                        
                        for i, col_name in enumerate(df.columns):
                            cell_value = str(row[col_name]) if pd.notna(row[col_name]) else ""
                            
                            # Calculate the X position based on column index
                            current_x = pdf.l_margin + (i * col_width)
                            
                            # Move cursor to correct X/Y before drawing the cell
                            pdf.set_xy(current_x, start_y)
                            
                            # multi_cell automatically wraps text!
                            pdf.multi_cell(col_width, 8, txt=cell_value, border=1, align="C")
                            
                            # Update max_y if this cell was taller than the others
                            if pdf.get_y() > max_y:
                                max_y = pdf.get_y()
                                
                        # After drawing all columns in the row, reset Y to the tallest point
                        pdf.set_y(max_y)
                
                pdf.ln(10) # Add space after table

        # 3. Create a totally unique filename inside the static folder
        unique_filename = f"manual_{uuid.uuid4()}.pdf"
        pdf_filepath = f"static/{unique_filename}"
        
        # # 4. Output the PDF to that specific path
        # st.success("PDF作成完了！")
        # show_pdf(unique_filename)
        
        # 2. ACTUALLY BUILD AND SAVE THE FILE (Crucial missing step!)
        pdf.output(pdf_filepath)
        
        # READ THE PDF AND CONVERT TO BASE64
        with open(pdf_filepath, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
            
        st.success("PDF作成完了！")
        
        # 3. USE BASE64 INSTEAD OF THE FILE PATH
        pdf_url = f"data:application/pdf;base64,{base64_pdf}"
        
        # We construct a styled HTML link that looks exactly like a Streamlit button
        # We use a tiny JavaScript script to convert the Base64 to a Blob URL,
        # which browsers ALLOW to be opened safely in a new tab!
        html_code = f"""
        <script>
        function openPDF() {{
            const byteCharacters = atob("{base64_pdf}");
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {{
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }}
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], {{type: "application/pdf"}});
            const blobUrl = URL.createObjectURL(blob);
            window.open(blobUrl, "_blank");
        }}
        </script>
        
        <button onclick="openPDF()" style="
            background-color: #FF4B4B;
            color: white;
            padding: 10px 20px;
            text-align: center;
            border-radius: 8px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 10px;
            border: none;
            width: 100%;
            font-family: sans-serif;
            font-size: 16px;
        ">
            新しいタブでマニュアルを開いて印刷する
        </button>
        """
        
        # Display using Streamlit's native HTML component (allows JS to run)
        st.components.v1.html(html_code, height=70)

# --- ROUTER AND SECURITY CONTROL ---
if check_password():
    # Define your pages programmatically
    dashboard_page = st.Page(show_main_dashboard, title="発送カレンダー", icon="📅", default=True)
    blog_page = st.Page(show_blog, title="デジタルマニュアル", icon="🚀", url_path="example1")
    
    # Initialize and execute the navigation sidebar
    pg = st.navigation([dashboard_page, blog_page])
    pg.run()
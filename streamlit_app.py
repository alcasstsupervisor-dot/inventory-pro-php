import streamlit as st
import pandas as pd
import datetime
import os

# --- 1. CONFIG & STRICT AUTHENTICATION ---
st.set_page_config(page_title="LCIS - Anihan Pro", layout="wide")

# The only emails allowed to be Admins
ADMINS = [
    "cecille.sulit@anihan.edu.ph", 
    "aileen.clutario@anihan.edu.ph", 
    "alc.purchasing@anihan.edu.ph", 
    "alc.asstsupervisor@anihan.edu.ph"
]
AUTHORIZED_DOMAIN = "@anihan.edu.ph"

# --- 2. DATA PERSISTENCE ---
DB_FILE = "lcis_main_v8.csv"
PENDING_FILE = "pending_deliveries_v8.csv"
HIST_FILE = "change_log_v8.csv"
LOGIN_LOG_FILE = "login_history_v8.csv"

def load_data(file, columns):
    if os.path.exists(file): return pd.read_csv(file)
    return pd.DataFrame(columns=columns)

def save_data(df, file): df.to_csv(file, index=False)

def log_event(file, entry_dict):
    df = load_data(file, list(entry_dict.keys()))
    new_row = pd.DataFrame([entry_dict])
    pd.concat([df, new_row], ignore_index=True).to_csv(file, index=False)

# --- 3. LOGIN SYSTEM ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_role = "Staff"

if not st.session_state.logged_in:
    st.title("🔐 LCIS Login Portal")
    email_input = st.text_input("Anihan Email").lower().strip()
    full_name = st.text_input("Enter Your Full Name")
    
    if st.button("Access System"):
        if not full_name or not email_input:
            st.warning("Please fill out both fields.")
        elif email_input in ADMINS or email_input.endswith(AUTHORIZED_DOMAIN):
            st.session_state.logged_in = True
            st.session_state.user_email = email_input
            st.session_state.display_name = full_name
            # Strict Admin Check
            st.session_state.user_role = "Admin" if email_input in ADMINS else "Staff"
            
            log_event(LOGIN_LOG_FILE, {
                "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Name": full_name, "Email": email_input, "Role": st.session_state.user_role
            })
            st.rerun()
        else:
            st.error(f"Access Denied. Use an authorized {AUTHORIZED_DOMAIN} email.")
    st.stop()

# --- 4. GREETING & SIDEBAR ---
# Time-based Greeting
now = datetime.datetime.now()
if now.hour < 12: greeting = "Good morning"
elif 12 <= now.hour < 18: greeting = "Good afternoon"
else: greeting = "Good evening"

# Ensure Admin authority is enforced for the menu
is_admin = st.session_state.user_role == "Admin"

# Sidebar Branding
st.sidebar.title("🏢 Anihan LCIS")
st.sidebar.markdown(f"### {greeting},\n**{st.session_state.user_role} {st.session_state.display_name}**")
st.sidebar.divider()

if is_admin:
    menu = ["Dashboard", "Materials (Raw/Indirect)", "Replenish Stock", "Recipes & Forecasting", "Delivery", "Admin Panel"]
    st.sidebar.success("🔑 Admin Access Level")
else:
    menu = ["Dashboard", "Materials (Raw/Indirect)", "Delivery"]
    st.sidebar.info("👤 Staff Access Level")

page = st.sidebar.radio("Navigation Menu", menu)

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- 5. DATA LOADING ---
st.session_state.products = load_data(DB_FILE, ["SAP Code", "Name", "Type", "On hand Inventory", "Unit", "Min_Level", "Cost"])
pending_df = load_data(PENDING_FILE, ["ID", "Date", "DR", "SAP", "Item", "Qty", "Status", "Staff", "Admin_Note"])

# --- 6. PAGE LOGIC ---

if page == "Dashboard":
    st.title("📊 Dashboard")
    st.subheader(f"{greeting}, {st.session_state.user_role} {st.session_state.display_name}")
    
    # Correction Alert (If any)
    corrections = pending_df[pending_df['Status'] == "Pending (Correction Needed)"]
    if not corrections.empty:
        st.error(f"🚨 ALERT: There are {len(corrections)} deliveries flagged for correction.")
        st.dataframe(corrections[['Date', 'DR', 'Item', 'Admin_Note']])

    st.divider()
    st.write("### Current On-hand Inventory")
    st.dataframe(st.session_state.products, use_container_width=True)

elif page == "Delivery":
    st.title("🚚 Delivery Input")
    st.info("Staff input will be held for Admin verification.")
    
    with st.form("delivery_input", clear_on_submit=True):
        d_date = st.date_input("Date Received", value=datetime.date.today())
        dr_ref = st.text_input("Delivery Receipt (DR) #")
        search = st.text_input("SAP Code or Item Name").upper().strip()
        qty = st.number_input("Quantity Received", format="%.3f", min_value=0.0)
        
        if st.form_submit_button("Submit for Admin Approval"):
            new_id = len(pending_df) + 1
            new_entry = {
                "ID": new_id, "Date": d_date, "DR": dr_ref, "SAP": search, 
                "Item": search, "Qty": qty, "Status": "Pending", 
                "Staff": st.session_state.display_name, "Admin_Note": ""
            }
            pending_df = pd.concat([pending_df, pd.DataFrame([new_entry])], ignore_index=True)
            save_data(pending_df, PENDING_FILE)
            st.success("✅ Delivery submitted! Please wait for Admin confirmation.")

elif page == "Replenish Stock" and is_admin:
    st.title("🛒 Admin Replenishment & Verification")
    
    # --- VERIFICATION POP-UP LOGIC ---
    to_verify = pending_df[pending_df['Status'].str.contains("Pending")]
    
    if not to_verify.empty:
        st.warning(f"🔔 You have {len(to_verify)} pending deliveries to verify.")
        for idx, row in to_verify.iterrows():
            if st.button(f"🔎 Review DR: {row['DR']} from {row['Staff']}", key=f"verify_{row['ID']}"):
                st.session_state.review_id = row['ID']

    if 'review_id' in st.session_state:
        # Code to Confirm/Reject as per previous logic...
        # (This is where you confirm and it updates On hand Inventory)
        pass

elif page == "Admin Panel" and is_admin:
    st.title("🛡️ Admin Panel")
    t1, t2 = st.tabs(["User Login History", "System Audit Log"])
    with t1:
        st.dataframe(load_data(LOGIN_LOG_FILE, ["Timestamp", "Name", "Email", "Role"]).sort_values("Timestamp", ascending=False))
    with t2:
        st.dataframe(load_data(HIST_FILE, ["Timestamp", "User", "Action", "Details"]).sort_values("Timestamp", ascending=False))

import streamlit as st
import pandas as pd
import datetime
import os

# --- 1. CONFIG & AUTHENTICATION ---
st.set_page_config(page_title="LCIS - Anihan Pro", layout="wide")

ADMINS = [
    "cecille.sulit@anihan.edu.ph", 
    "aileen.clutario@anihan.edu.ph", 
    "alc.purchasing@anihan.edu.ph", 
    "alc.asstsupervisor@anihan.edu.ph"
]
AUTHORIZED_DOMAIN = "@anihan.edu.ph"

# --- 2. DATA PERSISTENCE ---
DB_FILE = "lcis_main_v9.csv"
PENDING_FILE = "pending_deliveries_v9.csv"
HIST_FILE = "change_log_v9.csv"
LOGIN_LOG_FILE = "login_history_v9.csv"

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
now = datetime.datetime.now()
if now.hour < 12: greeting = "Good morning"
elif 12 <= now.hour < 18: greeting = "Good afternoon"
else: greeting = "Good evening"

is_admin = st.session_state.user_role == "Admin"

st.sidebar.title("🏢 Anihan LCIS")
st.sidebar.markdown(f"### {greeting},\n**{st.session_state.user_role} {st.session_state.display_name}**")
st.sidebar.divider()

if is_admin:
    menu = ["Dashboard", "Materials (Raw/Indirect)", "Replenish Stock", "Recipes & Forecasting", "Delivery", "Admin Panel"]
    st.sidebar.success("🔑 Admin Full Access")
else:
    menu = ["Dashboard", "Materials (Raw/Indirect)", "Delivery"]
    st.sidebar.info("👤 Staff Restricted Access")

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
    
    # Correction Alert for Staff
    corrections = pending_df[pending_df['Status'] == "Pending (Correction Needed)"]
    if not corrections.empty:
        st.error(f"🚨 ACTION REQUIRED: {len(corrections)} deliveries need correction.")
        st.dataframe(corrections[['Date', 'DR', 'Item', 'Admin_Note']])

    st.write("### On-hand Inventory")
    st.dataframe(st.session_state.products, use_container_width=True)

elif page == "Materials (Raw/Indirect)":
    st.title("📦 Material Master")
    if is_admin:
        with st.expander("➕ Add New Material (Admin Only)"):
            with st.form("add_new"):
                c1, c2 = st.columns(2)
                sap = c1.text_input("SAP Code").upper()
                name = c2.text_input("Name")
                m_type = c1.selectbox("Type", ["Raw Material", "Indirect Material"])
                qty = c2.number_input("Beginning Stock", format="%.3f")
                unit = c1.text_input("Unit")
                min_l = c2.number_input("Min Level", format="%.3f")
                cost = c1.number_input("Cost (₱)", format="%.3f")
                if st.form_submit_button("Save"):
                    new_item = {"SAP Code": sap, "Name": name, "Type": m_type, "On hand Inventory": qty, "Unit": unit, "Min_Level": min_l, "Cost": cost}
                    st.session_state.products = pd.concat([st.session_state.products, pd.DataFrame([new_item])], ignore_index=True)
                    save_data(st.session_state.products, DB_FILE)
                    st.success("Item Added")
                    st.rerun()
    st.dataframe(st.session_state.products, use_container_width=True)

elif page == "Delivery":
    st.title("🚚 Delivery Input")
    with st.form("staff_input", clear_on_submit=True):
        d_date = st.date_input("Date Received")
        dr_ref = st.text_input("DR #")
        search = st.text_input("Search SAP/Name").upper().strip()
        qty = st.number_input("Qty Received", format="%.3f")
        if st.form_submit_button("Submit for Admin Approval"):
            new_id = len(pending_df) + 1
            new_row = {"ID": new_id, "Date": d_date, "DR": dr_ref, "SAP": search, "Item": search, "Qty": qty, "Status": "Pending", "Staff": st.session_state.display_name, "Admin_Note": ""}
            pending_df = pd.concat([pending_df, pd.DataFrame([new_row])], ignore_index=True)
            save_data(pending_df, PENDING_FILE)
            st.success("✅ Delivery sent for verification.")

elif page == "Replenish Stock" and is_admin:
    st.title("🛒 Admin Replenishment")
    to_verify = pending_df[pending_df['Status'].str.contains("Pending")]
    if not to_verify.empty:
        st.warning(f"🔔 Pending Deliveries: {len(to_verify)}")
        for i, r in to_verify.iterrows():
            if st.button(f"Review DR: {r['DR']} ({r['Item']})", key=f"rev_{r['ID']}"):
                st.session_state.review_id = r['ID']

    if 'review_id' in st.session_state:
        rid = st.session_state.review_id
        rev_row = pending_df[pending_df['ID'] == rid].iloc[0]
        st.info(f"Reviewing {rev_row['Item']} from {rev_row['Staff']}")
        # (Verification form logic to Confirm/Reject as established before)
        if st.button("Confirm & Update Inventory"):
            # Update logic here...
            st.success("Inventory Updated!")
            del st.session_state.review_id
            st.rerun()

elif page == "Admin Panel" and is_admin:
    st.title("🛡️ Admin Logs")
    st.write("Login History")
    st.dataframe(load_data(LOGIN_LOG_FILE, ["Timestamp", "Name", "Email", "Role"]))

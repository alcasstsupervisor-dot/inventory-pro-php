import streamlit as st
import pandas as pd
import datetime
import os

# --- 1. CONFIG & AUTHENTICATION ---
st.set_page_config(page_title="LCIS - Anihan", layout="wide")

ADMINS = [
    "cecille.sulit@anihan.edu.ph", 
    "aileen.clutario@anihan.edu.ph", 
    "alc.purchasing@anihan.edu.ph", 
    "alc.asstsupervisor@anihan.edu.ph"
]
AUTHORIZED_DOMAIN = "@anihan.edu.ph"

# --- 2. DATA PERSISTENCE FILES ---
DB_FILE = "lcis_main_v4.csv"
HIST_FILE = "change_log_v4.csv"
DELIVERY_FILE = "deliveries_v4.csv"
LOGIN_LOG_FILE = "login_history_v4.csv"

def load_data(file, columns):
    if os.path.exists(file):
        return pd.read_csv(file)
    return pd.DataFrame(columns=columns)

def save_data(df, file):
    df.to_csv(file, index=False)

def log_event(file, entry_dict):
    df = load_data(file, list(entry_dict.keys()))
    new_row = pd.DataFrame([entry_dict])
    pd.concat([df, new_row], ignore_index=True).to_csv(file, index=False)

# --- 3. LOGIN SCREEN ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_role = "Staff"
    st.session_state.display_name = ""

if not st.session_state.logged_in:
    st.title("🔐 LCIS Login Portal")
    email_input = st.text_input("Anihan Email Address").lower().strip()
    full_name = st.text_input("Enter Your Full Name (First Name Last Name)")
    
    if st.button("Access System"):
        if not full_name:
            st.warning("Please enter your name before proceeding.")
        elif email_input in ADMINS or email_input.endswith(AUTHORIZED_DOMAIN):
            st.session_state.logged_in = True
            st.session_state.user_email = email_input
            st.session_state.display_name = full_name
            st.session_state.user_role = "Admin" if email_input in ADMINS else "Staff"
            
            # Record Login in Admin Database
            log_event(LOGIN_LOG_FILE, {
                "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Name": full_name,
                "Email": email_input,
                "Role": st.session_state.user_role
            })
            st.rerun()
        else:
            st.error(f"Access Denied. Only {AUTHORIZED_DOMAIN} emails are authorized.")
    st.stop()

# --- 4. GREETING LOGIC ---
now = datetime.datetime.now()
hour = now.hour
if hour < 12: greeting = "Good morning"
elif 12 <= hour < 18: greeting = "Good afternoon"
else: greeting = "Good evening"

# --- 5. SIDEBAR NAVIGATION ---
is_admin = st.session_state.user_role == "Admin"
st.sidebar.title(f"🏠 LCIS {st.session_state.user_role}")
st.sidebar.write(f"**{greeting}, {st.session_state.user_role} {st.session_state.display_name}**")

if is_admin:
    menu = ["Dashboard", "Inventory & Suppliers", "Replenish Stock", "Recipes & Forecasting", "Delivery", "Admin Panel"]
else:
    menu = ["Dashboard", "Inventory & Suppliers", "Delivery"]

page = st.sidebar.radio("Navigation", menu)

# --- 6. PAGE CONTENT ---

# Initialize Products for all pages
if 'products' not in st.session_state:
    st.session_state.products = load_data(DB_FILE, ["SAP Code", "Name", "Type", "Supplier", "On hand Inventory", "Unit", "Min_Level", "Cost"])

if page == "Dashboard":
    st.title("📊 Dashboard")
    st.subheader(f"{greeting}, Staff {st.session_state.display_name}")
    
    if st.session_state.products.empty:
        st.info("No items in inventory. Admins can add items in 'Inventory & Suppliers'.")
    else:
        # Display table with 3 decimal places
        st.dataframe(st.session_state.products, use_container_width=True)

elif page == "Delivery":
    st.title("🚚 Delivery Receiving")
    st.write("Match items via SAP Code or Name (Case-insensitive)")
    
    with st.form("del_form", clear_on_submit=True):
        d_date = st.date_input("Delivery Date", value=datetime.date.today())
        dr_ref = st.text_input("DR Reference Number")
        search_query = st.text_input("Search SAP Code or Item Name").strip().upper()
        
        # Search logic
        match = st.session_state.products[
            (st.session_state.products['SAP Code'].str.upper() == search_query) | 
            (st.session_state.products['Name'].str.upper() == search_query)
        ]
        
        qty_rec = st.number_input("Quantity Received", format="%.3f")
        
        if st.form_submit_button("Submit Delivery"):
            if not match.empty:
                item_name = match.iloc[0]['Name']
                idx = match.index[0]
                
                # Update Inventory
                st.session_state.products.at[idx, 'On hand Inventory'] += qty_rec
                save_data(st.session_state.products, DB_FILE)
                
                # Log the delivery
                log_event(DELIVERY_FILE, {
                    "Date": d_date, "DR": dr_ref, "SAP": match.iloc[0]['SAP Code'], 
                    "Item": item_name, "Qty": qty_rec, "Receiver": st.session_state.display_name
                })
                
                # Log for Admin Audit
                log_event(HIST_FILE, {
                    "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "User": st.session_state.display_name,
                    "Action": "DELIVERY",
                    "Details": f"Received {qty_rec} of {item_name}"
                })
                st.success(f"Successfully added {qty_rec} to {item_name}!")
            else:
                st.error("Item not found. Please contact an Admin to register this SAP Code.")

elif page == "Admin Panel":
    st.title("🛡️ Admin Panel")
    t1, t2, t3 = st.tabs(["Login History", "Change Log", "Expenses"])
    
    with t1:
        st.subheader("User Access History")
        login_history = load_data(LOGIN_LOG_FILE, ["Timestamp", "Name", "Email", "Role"])
        st.dataframe(login_history.sort_values(by="Timestamp", ascending=False), use_container_width=True)
        
    with t2:
        st.subheader("System Change Audit")
        audit_log = load_data(HIST_FILE, ["Timestamp", "User", "Action", "Details"])
        st.dataframe(audit_log.sort_values(by="Timestamp", ascending=False), use_container_width=True)

# Note: Other tabs (Replenish, Recipes) remain restricted to Admin based on the 'menu' logic.

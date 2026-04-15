import streamlit as st
import pandas as pd
import datetime
import os

# --- 1. CONFIG ---
st.set_page_config(page_title="LCIS Anihan Pro", layout="wide")

ADMIN_LIST = [
    "cecille.sulit@anihan.edu.ph", 
    "aileen.clutario@anihan.edu.ph", 
    "alc.purchasing@anihan.edu.ph", 
    "alc.asstsupervisor@anihan.edu.ph"
]
DOMAIN = "@anihan.edu.ph"

# --- 2. DATABASE REFRESH (v18) ---
DB_FILE = "lcis_main_v18.csv"
PENDING_FILE = "pending_v18.csv"
RECIPE_FILE = "recipes_v18.csv"
SUP_FILE = "suppliers_v18.csv"
AUDIT_FILE = "master_audit_v18.csv"

def load_data(file, cols):
    if os.path.exists(file): return pd.read_csv(file)
    return pd.DataFrame(columns=cols)

def save_data(df, file):
    df.to_csv(file, index=False)

def log_event(user, event_type, details):
    df = load_data(AUDIT_FILE, ["Timestamp", "User", "Type", "Details"])
    new_log = pd.DataFrame([{"Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), 
                             "User": user, "Type": event_type, "Details": details}])
    save_data(pd.concat([df, new_log], ignore_index=True), AUDIT_FILE)

# --- 3. LOGIN SESSION ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 LCIS Anihan: Secure Login")
    u_email = st.text_input("School Email").lower().strip()
    u_name = st.text_input("Full Name")
    if st.button("Login"):
        if u_email in ADMIN_LIST or u_email.endswith(DOMAIN):
            st.session_state.logged_in = True
            st.session_state.user_email = u_email
            st.session_state.user_name = u_name
            st.session_state.role = "Admin" if u_email in ADMIN_LIST else "Staff"
            log_event(u_name, "LOGIN", f"Logged in as {st.session_state.role}")
            st.rerun()
    st.stop()

# --- 4. DATA LOADING ---
products = load_data(DB_FILE, ["SAP Code", "Name", "Type", "Supplier", "On hand Inventory", "Unit", "Min_Level", "Cost", "Prev_Qty", "Prev_Cost", "Prev_Date"])
# Updated Supplier Columns
suppliers = load_data(SUP_FILE, ["Company Name", "Representative", "Position", "Contact Number", "Email", "Address"])
pending = load_data(PENDING_FILE, ["ID", "Date", "DR", "SAP", "Qty", "Cost", "Staff", "Status"])
recipes_db = load_data(RECIPE_FILE, ["Recipe Name", "Ingredient", "Qty Per Unit"])

# --- 5. SIDEBAR ---
is_admin = st.session_state.role == "Admin"
choice = st.sidebar.radio("Navigate", ["Dashboard", "Materials & Suppliers", "Replenish Stock", "Recipes & Forecasting", "Delivery", "Admin Panel"] if is_admin else ["Dashboard", "Materials & Suppliers", "Delivery"])

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- 6. DASHBOARD COLOR LOGIC ---
def highlight_stock(row):
    try:
        inv, mn = float(row['On hand Inventory']), float(row['Min_Level'])
        if inv < mn: return ['background-color: #ff4b4b'] * len(row)
        if inv == mn: return ['background-color: #ffd166'] * len(row)
    except: pass
    return [''] * len(row)

# --- 7. NAVIGATION LOGIC ---

if choice == "Dashboard":
    st.title("📊 Inventory Dashboard")
    st.dataframe(products.style.apply(highlight_stock, axis=1), use_container_width=True)

elif choice == "Materials & Suppliers":
    st.title("📦 Master Data Management")
    t1, t2 = st.tabs(["Materials", "Supplier Management"])
    
    with t1:
        if is_admin:
            with st.expander("➕ Add New Material"):
                with st.form("mat_f"):
                    c1, c2 = st.columns(2)
                    sap = c1.text_input("SAP Code").upper()
                    name = c2.text_input("Name")
                    sup = c1.selectbox("Supplier", suppliers["Company Name"].unique() if not suppliers.empty else ["N/A"])
                    unit = c2.selectbox("Unit", ["kg", "g", "L", "ml", "pc", "pack", "sack"])
                    qty = c1.number_input("Initial Qty", format="%.3f")
                    cost = c2.number_input("Initial Cost", format="%.3f")
                    min_l = c1.number_input("Min Level", format="%.3f")
                    if st.form_submit_button("Save Material"):
                        new_item = pd.DataFrame([{"SAP Code": sap, "Name": name, "Type": "Raw", "Supplier": sup, "On hand Inventory": qty, "Unit": unit, "Min_Level": min_l, "Cost": cost, "Prev_Qty": 0, "Prev_Cost": 0, "Prev_Date": "N/A"}])
                        save_data(pd.concat([products, new_item], ignore_index=True), DB_FILE)
                        st.rerun()
        st.dataframe(products, use_container_width=True)

    with t2:
        if is_admin:
            with st.expander("➕ Register New Supplier"):
                with st.form("sup_f"):
                    s1 = st.text_input("Company Name")
                    s2 = st.text_input("Representative")
                    s3 = st.text_input("Position")
                    s4 = st.text_input("Contact Number")
                    s5 = st.text_input("Email")
                    s6 = st.text_area("Address")
                    if st.form_submit_button("Save Supplier"):
                        new_s = pd.DataFrame([{"Company Name": s1, "Representative": s2, "Position": s3, "Contact Number": s4, "Email": s5, "Address": s6}])
                        save_data(pd.concat([suppliers, new_s], ignore_index=True), SUP_FILE)
                        st.rerun()
        st.dataframe(suppliers, use_container_width=True)

elif choice == "Replenish Stock" and is_admin:
    st.title("🛒 Admin Approvals")
    to_rev = pending[pending["Status"] == "Pending"]
    for i, r in to_rev.iterrows():
        with st.expander(f"Review DR: {r['DR']} | From: {r['Staff']}", expanded=True):
            st.write(f"**Item:** {r['SAP']} | **Qty:** {r['Qty']} | **Cost:** ₱{r['Cost']}")
            if st.button("Confirm Approval", key=f"app_{i}"):
                idx = products[products["SAP Code"] == r["SAP"]].index
                if not idx.empty:
                    # UPDATED HISTORY LOGIC: Current becomes Previous
                    products.at[idx[0], "Prev_Qty"] = products.at[idx[0], "On hand Inventory"]
                    products.at[idx[0], "Prev_Cost"] = products.at[idx[0], "Cost"]
                    products.at[idx[0], "Prev_Date"] = datetime.datetime.now().strftime("%Y-%m-%d")
                    # Update New Values
                    products.at[idx[0], "On hand Inventory"] += r["Qty"]
                    products.at[idx[0], "Cost"] = r["Cost"]
                    save_data(products, DB_FILE)
                    pending.at[i, "Status"] = "Approved"
                    save_data(pending, PENDING_FILE)
                    log_event(st.session_state.user_name, "DELIVERY_APPROVE", f"Approved DR {r['DR']}")
                    st.rerun()

elif choice == "Delivery":
    st.title("🚚 Delivery Form")
    with st.form("del_f", clear_on_submit=True):
        d1, d2 = st.date_input("Date Received"), st.text_input("DR #")
        d3 = st.text_input("SAP Code / Name").upper()
        d4, d5 = st.number_input("Qty", format="%.3f"), st.number_input("Unit Cost", format="%.3f")
        if st.form_submit_button("Submit"):
            new_p = pd.DataFrame([{"ID": len(pending)+1, "Date": d1, "DR": d2, "SAP": d3, "Qty": d4, "Cost": d5, "Staff": st.session_state.user_name, "Status": "Pending"}])
            save_data(pd.concat([pending, new_p], ignore_index=True), PENDING_FILE)
            log_event(st.session_state.user_name, "DELIVERY_REQ", f"Submitted DR {d2}")
            st.success("Sent to Admin.")

elif choice == "Admin Panel" and is_admin:
    st.title("🛡️ Master Audit Trail")
    audit_data = load_data(AUDIT_FILE, ["Timestamp", "User", "Type", "Details"])
    st.dataframe(audit_data.sort_values("Timestamp", ascending=False), use_container_width=True)
    
# ... Recipes & Forecasting logic remains as per v17 ...

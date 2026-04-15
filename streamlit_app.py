import streamlit as st
import pandas as pd
import datetime
import os

# --- 1. CONFIG & SYSTEM AUTH ---
st.set_page_config(page_title="LCIS Anihan Pro", layout="wide")

ADMIN_LIST = [
    "cecille.sulit@anihan.edu.ph", 
    "aileen.clutario@anihan.edu.ph", 
    "alc.purchasing@anihan.edu.ph", 
    "alc.asstsupervisor@anihan.edu.ph"
]
DOMAIN = "@anihan.edu.ph"

# --- 2. DATABASE REFRESH (v16) ---
DB_FILE = "lcis_main_v16.csv"
PENDING_FILE = "pending_v16.csv"
RECIPE_FILE = "recipes_v16.csv"
SUP_FILE = "suppliers_v16.csv"
AUDIT_FILE = "master_audit_v16.csv" # Combined Login & Activity Log

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
            log_event(u_name, "LOGIN", f"User logged in as {st.session_state.role}")
            st.rerun()
    st.stop()

# --- 4. DATA LOADING ---
products = load_data(DB_FILE, ["SAP Code", "Name", "Type", "Supplier", "On hand Inventory", "Unit", "Min_Level", "Current_Cost", "Prev_Qty", "Prev_Cost", "Prev_Date"])
suppliers = load_data(SUP_FILE, ["Supplier Name", "Contact"])
pending = load_data(PENDING_FILE, ["ID", "Date", "DR", "SAP", "Qty", "Cost", "Staff", "Status"])
recipes_db = load_data(RECIPE_FILE, ["Recipe Name", "Ingredient", "Qty Per Unit"])

# --- 5. SIDEBAR ---
is_admin = st.session_state.role == "Admin"
now = datetime.datetime.now()
greet = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"

st.sidebar.title("🏢 LCIS Anihan")
st.sidebar.subheader(f"{greet}, {st.session_state.role} {st.session_state.user_name}")

tabs = ["Dashboard", "Materials & Suppliers", "Replenish Stock", "Recipes & Forecasting", "Delivery", "Admin Panel"] if is_admin else ["Dashboard", "Materials & Suppliers", "Delivery"]
choice = st.sidebar.radio("Navigate", tabs)

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- 6. DASHBOARD COLOR LOGIC ---
def highlight_stock(row):
    try:
        inv = float(row['On hand Inventory'])
        mn = float(row['Min_Level'])
        if inv < mn: return ['background-color: #ff4b4b'] * len(row)
        if inv == mn: return ['background-color: #ffd166'] * len(row)
    except: pass
    return [''] * len(row)

# --- 7. PAGE LOGIC ---

if choice == "Dashboard":
    st.title("📊 Inventory Dashboard")
    st.dataframe(products.style.apply(highlight_stock, axis=1), use_container_width=True)

elif choice == "Replenish Stock" and is_admin:
    st.title("🛒 Admin Approvals")
    to_rev = pending[pending["Status"] == "Pending"]
    if to_rev.empty:
        st.info("No pending deliveries for approval.")
    else:
        for i, r in to_rev.iterrows():
            with st.expander(f"📋 Review DR: {r['DR']} | From: {r['Staff']}", expanded=True):
                st.write(f"**Item (SAP/Name):** {r['SAP']}")
                st.write(f"**Quantity:** {r['Qty']} | **Cost:** ₱{r['Cost']}")
                st.write(f"**Date Submitted:** {r['Date']}")
                
                if st.button("Confirm & Approve Replenishment", key=f"app_{i}"):
                    idx = products[products["SAP Code"] == r["SAP"]].index
                    if not idx.empty:
                        # Update Previous History
                        products.at[idx[0], "Prev_Qty"] = r["Qty"]
                        products.at[idx[0], "Prev_Cost"] = r["Cost"]
                        products.at[idx[0], "Prev_Date"] = r["Date"]
                        # Replenish Inventory
                        products.at[idx[0], "On hand Inventory"] += r["Qty"]
                        save_data(products, DB_FILE)
                        # Mark Pending as Approved
                        pending.at[i, "Status"] = "Approved"
                        save_data(pending, PENDING_FILE)
                        log_event(st.session_state.user_name, "DELIVERY_APPROVE", f"Approved DR {r['DR']} for {r['SAP']}")
                        st.success(f"Inventory for {r['SAP']} updated!")
                        st.rerun()
                    else:
                        st.error("Item SAP not found in Materials list. Please add item first.")

elif choice == "Delivery":
    st.title("🚚 Delivery Form")
    with st.form("del_f", clear_on_submit=True):
        d1 = st.date_input("Date Received")
        d2 = st.text_input("DR #")
        d3 = st.text_input("SAP Code or Name").upper()
        d4 = st.number_input("Qty", format="%.3f")
        d5 = st.number_input("Unit Cost", format="%.3f")
        if st.form_submit_button("Submit for Approval"):
            new_del = pd.DataFrame([{"ID": len(pending)+1, "Date": d1, "DR": d2, "SAP": d3, "Qty": d4, "Cost": d5, "Staff": st.session_state.user_name, "Status": "Pending"}])
            save_data(pd.concat([pending, new_del], ignore_index=True), PENDING_FILE)
            log_event(st.session_state.user_name, "DELIVERY_REQUEST", f"Submitted DR {d2} for {d3}")
            st.success("Request sent to Admin.")

elif choice == "Materials & Suppliers":
    st.title("📦 Master Data")
    t1, t2 = st.tabs(["Materials", "Suppliers"])
    with t1:
        if is_admin:
            with st.expander("➕ Add Material"):
                with st.form("m_f"):
                    c1, c2 = st.columns(2)
                    sap = c1.text_input("SAP Code").upper()
                    name = c2.text_input("Name")
                    sup = c1.selectbox("Supplier", suppliers["Supplier Name"].unique() if not suppliers.empty else ["N/A"])
                    unit = c2.selectbox("Unit", ["kg", "g", "L", "ml", "pc", "pack", "sack"])
                    qty = c1.number_input("Stock", format="%.3f")
                    min_l = c2.number_input("Min Level", format="%.3f")
                    if st.form_submit_button("Save"):
                        new_m = pd.DataFrame([{"SAP Code": sap, "Name": name, "Type": "Raw", "Supplier": sup, "On hand Inventory": qty, "Unit": unit, "Min_Level": min_l, "Current_Cost": 0.0, "Prev_Qty": 0, "Prev_Cost": 0, "Prev_Date": "N/A"}])
                        save_data(pd.concat([products, new_m], ignore_index=True), DB_FILE)
                        st.rerun()
        st.dataframe(products, use_container_width=True)
    with t2:
        if is_admin:
            with st.form("s_f"):
                sn = st.text_input("Supplier Name")
                if st.form_submit_button("Save Supplier"):
                    save_data(pd.concat([suppliers, pd.DataFrame([{"Supplier Name": sn, "Contact": "N/A"}])], ignore_index=True), SUP_FILE)
                    st.rerun()
        st.dataframe(suppliers, use_container_width=True)

elif choice == "Recipes & Forecasting" and is_admin:
    st.title("🧪 Recipe Production")
    # ... Same Production Logic as v15 ...
    if not recipes_db.empty:
        pick = st.selectbox("Select Recipe", recipes_db["Recipe Name"].unique())
        batch = st.number_input("Batch Size", min_value=1)
        if st.button("Deduct Materials"):
            reqs = recipes_db[recipes_db["Recipe Name"] == pick]
            for _, r in reqs.iterrows():
                products.loc[products["Name"] == r["Ingredient"], "On hand Inventory"] -= (r["Qty Per Unit"] * batch)
            save_data(products, DB_FILE)
            log_event(st.session_state.user_name, "PRODUCTION", f"Executed {batch} units of {pick}")
            st.rerun()

elif choice == "Admin Panel" and is_admin:
    st.title("🛡️ Master History & Audit Trail")
    audit_data = load_data(AUDIT_FILE, ["Timestamp", "User", "Type", "Details"])
    st.dataframe(audit_data.sort_values("Timestamp", ascending=False), use_container_width=True)

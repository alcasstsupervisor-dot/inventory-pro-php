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

# --- 2. DATABASE REFRESH (v23) ---
DB_FILE = "lcis_main_v23.csv"
PENDING_FILE = "pending_v23.csv"
RECIPE_FILE = "recipes_v23.csv"
SUP_FILE = "suppliers_v23.csv"
AUDIT_FILE = "master_audit_v23.csv"

def load_data(file, cols):
    if os.path.exists(file): return pd.read_csv(file)
    return pd.DataFrame(columns=cols)

def save_data(df, file):
    df.to_csv(file, index=False)

def log_event(user_name, event_type, details):
    df = load_data(AUDIT_FILE, ["Timestamp", "User", "Type", "Details"])
    new_log = pd.DataFrame([{"Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "User": user_name, "Type": event_type, "Details": details}])
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
            log_event(st.session_state.user_name, "LOGIN", f"Role: {st.session_state.role}")
            st.rerun()
    st.stop()

# --- 4. DATA LOADING ---
products = load_data(DB_FILE, ["SAP Code", "Name", "Type", "Supplier", "On hand Inventory", "Unit", "Min_Level", "Cost", "Prev_Qty", "Prev_Cost", "Prev_Date"])
suppliers = load_data(SUP_FILE, ["Company Name", "Representative", "Position", "Contact Number", "Email", "Address"])
pending = load_data(PENDING_FILE, ["ID", "Date", "DR", "Identifier", "Qty", "Unit", "Cost", "Staff", "Status"])
recipes_db = load_data(RECIPE_FILE, ["Recipe Name", "Ingredient", "Qty Per Unit"])

# --- 5. SIDEBAR & GREETING (FIXED) ---
is_admin = st.session_state.role == "Admin"
now = datetime.datetime.now()
greet = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"

st.sidebar.title("🏢 LCIS Anihan")
# RESTORED GREETING
st.sidebar.subheader(f"{greet}, {st.session_state.user_name}")
if is_admin:
    st.sidebar.markdown("⭐ **Admin Access Active**")

# RE-ENABLED MENU LOGIC
menu = ["Dashboard", "Materials & Suppliers", "Replenish Stock", "Recipes & Forecasting", "Delivery", "Admin Panel"] if is_admin else ["Dashboard", "Materials & Suppliers", "Delivery"]
choice = st.sidebar.radio("Navigate", menu)

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- 6. PAGE LOGIC ---

if choice == "Dashboard":
    st.title("📊 Inventory Dashboard")
    def highlight_stock(row):
        try:
            inv, mn = float(row['On hand Inventory']), float(row['Min_Level'])
            if inv < mn: return ['background-color: #ff4b4b'] * len(row)
            if inv == mn: return ['background-color: #ffd166'] * len(row)
        except: pass
        return [''] * len(row)
    st.dataframe(products.style.apply(highlight_stock, axis=1), use_container_width=True)

elif choice == "Materials & Suppliers":
    st.title("📦 Master Data")
    t1, t2 = st.tabs(["Materials", "Suppliers"])
    with t1:
        if is_admin:
            with st.expander("➕ Add New Material"):
                with st.form("add_mat"):
                    c1, c2 = st.columns(2)
                    s = c1.text_input("SAP Code").upper()
                    n = c2.text_input("Name")
                    ty = c1.selectbox("Type", ["Raw Materials", "Indirect Materials"])
                    su = c2.selectbox("Supplier", suppliers["Company Name"].unique() if not suppliers.empty else ["N/A"])
                    u = c1.selectbox("Unit", ["kg", "g", "L", "ml", "pc", "pack", "sack"])
                    q = c1.number_input("Initial Stock")
                    co = c2.number_input("Initial Cost")
                    mi = c2.number_input("Min Level")
                    if st.form_submit_button("Save Material"):
                        nm = pd.DataFrame([{"SAP Code": s, "Name": n, "Type": ty, "Supplier": su, "On hand Inventory": q, "Unit": u, "Min_Level": mi, "Cost": co, "Prev_Qty": 0, "Prev_Cost": 0, "Prev_Date": "N/A"}])
                        save_data(pd.concat([products, nm], ignore_index=True), DB_FILE)
                        st.rerun()
        st.dataframe(products, use_container_width=True)
    with t2:
        if is_admin:
            with st.expander("➕ Register Supplier"):
                with st.form("add_sup"):
                    sn = st.text_input("Company Name")
                    rep = st.text_input("Representative")
                    if st.form_submit_button("Save Supplier"):
                        ns = pd.DataFrame([{"Company Name": sn, "Representative": rep, "Position": "", "Contact Number": "", "Email": "", "Address": ""}])
                        save_data(pd.concat([suppliers, ns], ignore_index=True), SUP_FILE)
                        st.rerun()
        st.dataframe(suppliers, use_container_width=True)

elif choice == "Replenish Stock" and is_admin:
    st.title("🛒 Admin Approvals")
    to_rev = pending[pending["Status"] == "Pending"]
    if to_rev.empty:
        st.info("No pending deliveries. They will appear here once submitted by staff.")
    else:
        for i, r in to_rev.iterrows():
            # Match by SAP or Name
            match = products[(products["SAP Code"] == r["Identifier"]) | (products["Name"] == r["Identifier"])]
            oh = match["On hand Inventory"].values[0] if not match.empty else "N/A"
            with st.expander(f"DR: {r['DR']} | From: {r['Staff']}"):
                st.write(f"Item: {r['Identifier']} | Qty: {r['Qty']} | On-Hand: {oh}")
                if st.button("Approve", key=f"app_{i}"):
                    if not match.empty:
                        idx = match.index[0]
                        # History Shifting
                        products.at[idx, "Prev_Qty"] = products.at[idx, "On hand Inventory"]
                        products.at[idx, "Prev_Cost"] = products.at[idx, "Cost"]
                        products.at[idx, "Prev_Date"] = r["Date"]
                        # Update
                        products.at[idx, "On hand Inventory"] += r["Qty"]
                        products.at[idx, "Cost"] = r["Cost"]
                        save_data(products, DB_FILE)
                        pending.at[i, "Status"] = "Approved"
                        save_data(pending, PENDING_FILE)
                        st.rerun()

elif choice == "Recipes & Forecasting" and is_admin:
    st.title("🧪 Recipes & Production")
    r_tab1, r_tab2 = st.tabs(["Manage Recipes", "Execute Production"])
    with r_tab1:
        # Simplified recipe creation
        st.write("Recipes defined in the system:")
        st.dataframe(recipes_db, use_container_width=True)
    with r_tab2:
        if not recipes_db.empty:
            target = st.selectbox("Select Product", recipes_db["Recipe Name"].unique())
            batch = st.number_input("Quantity to Produce", min_value=1)
            if st.button("Deduct Raw Materials"):
                needed = recipes_db[recipes_db["Recipe Name"] == target]
                for _, row in needed.iterrows():
                    products.loc[products["Name"] == row["Ingredient"], "On hand Inventory"] -= (row["Qty Per Unit"] * batch)
                save_data(products, DB_FILE)
                log_event(st.session_state.user_name, "PRODUCTION", f"Produced {batch} {target}")
                st.success("Stocks updated!")
                st.rerun()

elif choice == "Delivery":
    st.title("🚚 Delivery Form")
    if 'rows' not in st.session_state: st.session_state.rows = 1
    with st.form("del_form"):
        dr = st.text_input("DR #")
        dt = st.date_input("Date")
        items = []
        for n in range(st.session_state.rows):
            c1, c2, c3, c4 = st.columns([3,1,1,1])
            ident = c1.text_input("SAP / Product Name", key=f"id_{n}").upper()
            qty = c2.number_input("Qty", key=f"q_{n}")
            unit = c3.selectbox("Unit", ["kg", "g", "L", "ml", "pc"], key=f"u_{n}")
            cost = c4.number_input("Cost", key=f"c_{n}")
            items.append({"Identifier": ident, "Qty": qty, "Unit": unit, "Cost": cost})
        
        if st.form_submit_button("Submit"):
            for it in items:
                if it["Identifier"]:
                    new_row = pd.DataFrame([{"ID": len(pending)+1, "Date": dt, "DR": dr, "Identifier": it["Identifier"], "Qty": it["Qty"], "Unit": it["Unit"], "Cost": it["Cost"], "Staff": st.session_state.user_name, "Status": "Pending"}])
                    pending = pd.concat([pending, new_row], ignore_index=True)
            save_data(pending, PENDING_FILE)
            st.success("Submitted for approval!")
            st.rerun()

elif choice == "Admin Panel" and is_admin:
    st.title("🛡️ Admin Panel")
    st.dataframe(load_data(AUDIT_FILE, ["Timestamp", "User", "Type", "Details"]), use_container_width=True)

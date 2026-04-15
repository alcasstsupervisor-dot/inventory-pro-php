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

# --- 2. DATABASE REFRESH (v14) ---
# Added historical columns: Prev_Qty, Prev_Cost, Prev_Date
DB_FILE = "lcis_main_v14.csv"
PENDING_FILE = "pending_v14.csv"
RECIPE_FILE = "recipes_v14.csv"
SUP_FILE = "suppliers_v14.csv"
HIST_FILE = "audit_v14.csv"
LOGIN_FILE = "logins_v14.csv"

def load_data(file, cols):
    if os.path.exists(file): return pd.read_csv(file)
    return pd.DataFrame(columns=cols)

def save_data(df, file):
    df.to_csv(file, index=False)

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
            st.rerun()
    st.stop()

# --- 4. DATA LOADING ---
# Added historical tracking columns
products = load_data(DB_FILE, ["SAP Code", "Name", "Type", "Supplier", "On hand Inventory", "Unit", "Min_Level", "Current_Cost", "Prev_Qty", "Prev_Cost", "Prev_Date"])
suppliers = load_data(SUP_FILE, ["Supplier Name", "Contact"])
pending = load_data(PENDING_FILE, ["ID", "Date", "DR", "SAP", "Qty", "Cost", "Staff", "Status", "Note"])
recipes_db = load_data(RECIPE_FILE, ["Recipe Name", "Ingredient", "Qty Per Unit"])

# --- 5. SIDEBAR & GREETING ---
is_admin = st.session_state.role == "Admin"
now = datetime.datetime.now()
greet = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"

st.sidebar.title("🏢 LCIS Anihan")
st.sidebar.subheader(f"{greet}, {st.session_state.role} {st.session_state.user_name}")

if is_admin:
    tabs = ["Dashboard", "Materials & Suppliers", "Replenish Stock", "Recipes & Forecasting", "Delivery", "Admin Panel"]
else:
    tabs = ["Dashboard", "Materials & Suppliers", "Delivery"]

choice = st.sidebar.radio("Navigate", tabs)

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- 6. DASHBOARD COLOR LOGIC ---
def highlight_stock(row):
    # Red: Below Minimum
    if row['On hand Inventory'] < row['Min_Level']:
        return ['background-color: #ff4b4b'] * len(row)
    # Yellow: At Minimum (Low Stock)
    elif row['On hand Inventory'] == row['Min_Level']:
        return ['background-color: #ffd166'] * len(row)
    return [''] * len(row)

# --- 7. PAGE LOGIC ---

if choice == "Dashboard":
    st.title("📊 Inventory Dashboard")
    st.write("🔴 **Red**: Below Minimum | 🟡 **Yellow**: At Minimum Level")
    
    # Apply styling
    styled_df = products.style.apply(highlight_stock, axis=1)
    st.dataframe(styled_df, use_container_width=True)

elif choice == "Materials & Suppliers":
    st.title("📦 Master Data")
    t1, t2 = st.tabs(["Materials", "Suppliers"])
    with t1:
        if is_admin:
            with st.expander("➕ Add New Material"):
                with st.form("mat_f"):
                    c1, c2 = st.columns(2)
                    sap = c1.text_input("SAP Code").upper()
                    name = c2.text_input("Item Name")
                    m_type = c1.selectbox("Type", ["Raw", "Indirect"])
                    m_sup = c2.selectbox("Supplier", suppliers["Supplier Name"].unique() if not suppliers.empty else ["N/A"])
                    qty = c1.number_input("Current Stock", format="%.3f")
                    unit = c2.selectbox("Unit", ["kg", "g", "L", "ml", "pc", "pack", "sack"])
                    cost = c1.number_input("Current Cost", format="%.3f")
                    min_l = c2.number_input("Min Level (Threshold)", format="%.3f")
                    if st.form_submit_button("Save"):
                        new_m = {"SAP Code": sap, "Name": name, "Type": m_type, "Supplier": m_sup, "On hand Inventory": qty, 
                                 "Unit": unit, "Min_Level": min_l, "Current_Cost": cost, 
                                 "Prev_Qty": 0, "Prev_Cost": 0, "Prev_Date": "N/A"}
                        products = pd.concat([products, pd.DataFrame([new_m])], ignore_index=True)
                        save_data(products, DB_FILE)
                        st.rerun()
        st.dataframe(products, use_container_width=True)
    with t2:
        if is_admin:
            with st.expander("➕ Add Supplier"):
                with st.form("sup_f"):
                    s_name = st.text_input("Supplier Name")
                    s_cont = st.text_input("Contact Info")
                    if st.form_submit_button("Save Supplier"):
                        new_s = pd.concat([suppliers, pd.DataFrame([{"Supplier Name": s_name, "Contact": s_cont}])], ignore_index=True)
                        save_data(new_s, SUP_FILE)
                        st.rerun()
        st.dataframe(suppliers, use_container_width=True)

elif choice == "Replenish Stock" and is_admin:
    st.title("🛒 Admin Approval & Historical Update")
    to_rev = pending[pending["Status"] == "Pending"]
    if to_rev.empty: st.info("No pending deliveries.")
    else:
        for i, r in to_rev.iterrows():
            with st.expander(f"Review DR: {r['DR']} - {r['SAP']}"):
                if st.button("Approve & Update History", key=f"a{i}"):
                    midx = products[products["SAP Code"] == r["SAP"]].index
                    if not midx.empty:
                        # Move Current values to Previous before updating
                        products.at[midx[0], "Prev_Qty"] = r["Qty"]
                        products.at[midx[0], "Prev_Cost"] = r["Cost"]
                        products.at[midx[0], "Prev_Date"] = r["Date"]
                        # Update Inventory and Current Cost
                        products.at[midx[0], "On hand Inventory"] += r["Qty"]
                        products.at[midx[0], "Current_Cost"] = r["Cost"]
                        
                        save_data(products, DB_FILE)
                        pending.at[i, "Status"] = "Approved"
                        save_data(pending, PENDING_FILE)
                        st.rerun()

elif choice == "Recipes & Forecasting" and is_admin:
    st.title("🧪 Recipe Production")
    # ... (Recipe creation logic remains same) ...
    if not recipes_db.empty:
        target = st.selectbox("Execute Recipe", recipes_db["Recipe Name"].unique())
        batch = st.number_input("Batch Size", min_value=1)
        if st.button("Execute & Deduct Inventory"):
            needed = recipes_db[recipes_db["Recipe Name"] == target]
            for _, row in needed.iterrows():
                deduction = row["Qty Per Unit"] * batch
                products.loc[products["Name"] == row["Ingredient"], "On hand Inventory"] -= deduction
            save_data(products, DB_FILE)
            st.success(f"Deducted materials for {batch} {target}(s)")
            st.rerun()

elif choice == "Delivery":
    st.title("🚚 Delivery Form")
    with st.form("del"):
        d1 = st.date_input("Date")
        d2 = st.text_input("DR #")
        d3 = st.text_input("SAP Code / Name").upper()
        d4 = st.number_input("Qty Received", format="%.3f")
        d5 = st.number_input("Unit Cost", format="%.3f")
        if st.form_submit_button("Submit"):
            new_p = pd.DataFrame([{"ID": len(pending)+1, "Date": d1, "DR": d2, "SAP": d3, "Qty": d4, "Cost": d5, "Staff": st.session_state.user_name, "Status": "Pending", "Note": ""}])
            save_data(pd.concat([pending, new_p], ignore_index=True), PENDING_FILE)
            st.success("Delivery sent to Admin for approval.")

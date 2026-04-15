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

# --- 2. DATABASE NAMES (v15) ---
DB_FILE = "lcis_main_v15.csv"
PENDING_FILE = "pending_v15.csv"
RECIPE_FILE = "recipes_v15.csv"
SUP_FILE = "suppliers_v15.csv"
HIST_FILE = "audit_v15.csv"
LOGIN_FILE = "logins_v15.csv"

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
products = load_data(DB_FILE, ["SAP Code", "Name", "Type", "Supplier", "On hand Inventory", "Unit", "Min_Level", "Current_Cost", "Prev_Qty", "Prev_Cost", "Prev_Date"])
suppliers = load_data(SUP_FILE, ["Supplier Name", "Contact"])
pending = load_data(PENDING_FILE, ["ID", "Date", "DR", "SAP", "Qty", "Cost", "Staff", "Status", "Note"])
recipes_db = load_data(RECIPE_FILE, ["Recipe Name", "Ingredient", "Qty Per Unit"])

# --- 5. SIDEBAR ---
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
    try:
        if float(row['On hand Inventory']) < float(row['Min_Level']):
            return ['background-color: #ff4b4b'] * len(row) # Red
        elif float(row['On hand Inventory']) == float(row['Min_Level']):
            return ['background-color: #ffd166'] * len(row) # Yellow
    except:
        pass
    return [''] * len(row)

# --- 7. NAVIGATION LOGIC (THE FIX) ---

if choice == "Dashboard":
    st.title("📊 Inventory Dashboard")
    st.info("🔴 Red: Below Min | 🟡 Yellow: At Min")
    st.dataframe(products.style.apply(highlight_stock, axis=1), use_container_width=True)

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
                    m_sup = c1.selectbox("Supplier", suppliers["Supplier Name"].unique() if not suppliers.empty else ["N/A"])
                    unit = c2.selectbox("Unit", ["kg", "g", "L", "ml", "pc", "pack", "sack"])
                    qty = c1.number_input("Current Stock", format="%.3f")
                    min_l = c2.number_input("Min Level", format="%.3f")
                    cost = c1.number_input("Current Cost", format="%.3f")
                    if st.form_submit_button("Save"):
                        new_m = pd.DataFrame([{"SAP Code": sap, "Name": name, "Type": "Raw", "Supplier": m_sup, "On hand Inventory": qty, "Unit": unit, "Min_Level": min_l, "Current_Cost": cost, "Prev_Qty": 0, "Prev_Cost": 0, "Prev_Date": "N/A"}])
                        save_data(pd.concat([products, new_m], ignore_index=True), DB_FILE)
                        st.rerun()
        st.dataframe(products, use_container_width=True)
    with t2:
        if is_admin:
            with st.form("sup_f"):
                sn = st.text_input("Supplier Name")
                sc = st.text_input("Contact")
                if st.form_submit_button("Save Supplier"):
                    save_data(pd.concat([suppliers, pd.DataFrame([{"Supplier Name": sn, "Contact": sc}])], ignore_index=True), SUP_FILE)
                    st.rerun()
        st.dataframe(suppliers, use_container_width=True)

elif choice == "Recipes & Forecasting":
    st.title("🧪 Recipe Production")
    r1, r2 = st.tabs(["Create Recipe", "Execute Production"])
    with r1:
        with st.form("rec_create"):
            rn = st.text_input("Recipe Name")
            ing = st.multiselect("Ingredients", products["Name"].unique())
            if st.form_submit_button("Start Recipe"):
                st.session_state.active_rec = {"name": rn, "ings": ing}
        if "active_rec" in st.session_state:
            with st.form("qty_define"):
                temp_list = []
                for i in st.session_state.active_rec["ings"]:
                    val = st.number_input(f"Qty of {i} per unit", format="%.3f")
                    temp_list.append({"Recipe Name": st.session_state.active_rec["name"], "Ingredient": i, "Qty Per Unit": val})
                if st.form_submit_button("Save Full Recipe"):
                    save_data(pd.concat([recipes_db, pd.DataFrame(temp_list)], ignore_index=True), RECIPE_FILE)
                    del st.session_state.active_rec
                    st.rerun()
    with r2:
        if not recipes_db.empty:
            pick = st.selectbox("Select Recipe to Produce", recipes_db["Recipe Name"].unique())
            batch = st.number_input("Production Batch Size", min_value=1)
            if st.button("Execute Production"):
                reqs = recipes_db[recipes_db["Recipe Name"] == pick]
                for _, r in reqs.iterrows():
                    products.loc[products["Name"] == r["Ingredient"], "On hand Inventory"] -= (r["Qty Per Unit"] * batch)
                save_data(products, DB_FILE)
                st.success(f"Deducted stock for {batch} {pick}")
                st.rerun()

elif choice == "Replenish Stock":
    st.title("🛒 Admin Approvals")
    to_rev = pending[pending["Status"] == "Pending"]
    for i, r in to_rev.iterrows():
        with st.expander(f"Review: {r['DR']}"):
            if st.button("Approve", key=f"app_{i}"):
                idx = products[products["SAP Code"] == r["SAP"]].index
                if not idx.empty:
                    # Update History before adding new stock
                    products.at[idx[0], "Prev_Qty"] = r["Qty"]
                    products.at[idx[0], "Prev_Cost"] = r["Cost"]
                    products.at[idx[0], "Prev_Date"] = r["Date"]
                    products.at[idx[0], "On hand Inventory"] += r["Qty"]
                    save_data(products, DB_FILE)
                    pending.at[i, "Status"] = "Approved"
                    save_data(pending, PENDING_FILE)
                    st.rerun()

elif choice == "Delivery":
    st.title("🚚 Delivery Form")
    with st.form("del_f"):
        c1, c2 = st.columns(2)
        d1 = c1.date_input("Date")
        d2 = c2.text_input("DR #")
        d3 = c1.text_input("SAP / Name").upper()
        d4 = c2.number_input("Qty", format="%.3f")
        d5 = c1.number_input("Unit Cost", format="%.3f")
        if st.form_submit_button("Submit Delivery"):
            new_del = pd.DataFrame([{"ID": len(pending)+1, "Date": d1, "DR": d2, "SAP": d3, "Qty": d4, "Cost": d5, "Staff": st.session_state.user_name, "Status": "Pending", "Note": ""}])
            save_data(pd.concat([pending, new_del], ignore_index=True), PENDING_FILE)
            st.success("Sent for approval.")

elif choice == "Admin Panel":
    st.title("🛡️ Admin Panel")
    st.write("### Login History")
    st.dataframe(load_data(LOGIN_FILE, ["Time", "Name", "Email", "Role"]))

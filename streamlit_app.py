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

# --- 2. DATABASE NAMES (v12) ---
DB_FILE = "lcis_main_v12.csv"
PENDING_FILE = "pending_v12.csv"
RECIPE_FILE = "recipes_v12.csv"
SUP_FILE = "suppliers_v12.csv"
HIST_FILE = "audit_v12.csv"
LOGIN_FILE = "logins_v12.csv"

# --- 3. HELPER FUNCTIONS ---
def load_data(file, cols):
    if os.path.exists(file): return pd.read_csv(file)
    return pd.DataFrame(columns=cols)

def save_data(df, file):
    df.to_csv(file, index=False)

def log_action(user, action, details):
    df = load_data(HIST_FILE, ["Time", "User", "Action", "Details"])
    new = pd.DataFrame([{"Time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "User": user, "Action": action, "Details": details}])
    pd.concat([df, new], ignore_index=True).to_csv(HIST_FILE, index=False)

# --- 4. LOGIN LOGIC ---
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
            # CRITICAL ROLE ASSIGNMENT
            st.session_state.role = "Admin" if u_email in ADMIN_LIST else "Staff"
            
            # Log Login
            ldf = load_data(LOGIN_FILE, ["Time", "Name", "Email", "Role"])
            new_l = pd.DataFrame([{"Time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "Name": u_name, "Email": u_email, "Role": st.session_state.role}])
            pd.concat([ldf, new_l], ignore_index=True).to_csv(LOGIN_FILE, index=False)
            st.rerun()
    st.stop()

# --- 5. PERMISSION CHECK & SIDEBAR ---
is_admin = st.session_state.role == "Admin"

# Greeting
now = datetime.datetime.now()
greet = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"

st.sidebar.title("🏢 LCIS Anihan")
st.sidebar.subheader(f"{greet}, {st.session_state.role} {st.session_state.user_name}")

if is_admin:
    # Admin sees ALL 6 TABS
    tabs = ["Dashboard", "Materials & Suppliers", "Replenish Stock", "Recipes & Forecasting", "Delivery", "Admin Panel"]
    st.sidebar.success("🛡️ Full Admin Access")
else:
    # Staff sees ONLY 3 TABS
    tabs = ["Dashboard", "Materials & Suppliers", "Delivery"]
    st.sidebar.info("👤 Staff Access")

choice = st.sidebar.radio("Navigate", tabs)

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- 6. DATA LOADING ---
products = load_data(DB_FILE, ["SAP Code", "Name", "Type", "Supplier", "On hand Inventory", "Unit", "Min_Level", "Cost"])
suppliers = load_data(SUP_FILE, ["Supplier Name", "Contact", "Address"])
pending = load_data(PENDING_FILE, ["ID", "Date", "DR", "SAP", "Qty", "Staff", "Status", "Note"])
recipes = load_data(RECIPE_FILE, ["Product", "Ingredient", "QtyPer"])

# --- 7. TAB LOGIC ---

if choice == "Dashboard":
    st.title("📊 Dashboard")
    st.write(f"Logged in as: **{st.session_state.user_email}**")
    st.dataframe(products, use_container_width=True)

elif choice == "Materials & Suppliers":
    st.title("📦 Master Data")
    t1, t2 = st.tabs(["Materials", "Suppliers"])
    
    with t1:
        if is_admin:
            with st.expander("➕ Add New Material (Admin)"):
                with st.form("mat_form"):
                    c1, c2 = st.columns(2)
                    s_code = c1.text_input("SAP Code").upper()
                    m_name = c2.text_input("Item Name")
                    m_type = c1.selectbox("Type", ["Raw", "Indirect"])
                    m_sup = c2.selectbox("Supplier", suppliers["Supplier Name"].unique() if not suppliers.empty else ["None"])
                    m_qty = c1.number_input("Beginning Stock", format="%.3f")
                    m_unit = c2.text_input("Unit")
                    m_cost = c1.number_input("Cost", format="%.3f")
                    m_min = c2.number_input("Min Level", format="%.3f")
                    if st.form_submit_button("Save Item"):
                        new_m = {"SAP Code": s_code, "Name": m_name, "Type": m_type, "Supplier": m_sup, "On hand Inventory": m_qty, "Unit": m_unit, "Min_Level": m_min, "Cost": m_cost}
                        products = pd.concat([products, pd.DataFrame([new_m])], ignore_index=True)
                        save_data(products, DB_FILE)
                        st.success("Item saved.")
                        st.rerun()
        st.dataframe(products, use_container_width=True)

    with t2:
        if is_admin:
            with st.expander("➕ Add New Supplier (Admin)"):
                with st.form("sup_form"):
                    sn = st.text_input("Supplier Name")
                    sc = st.text_input("Contact Info")
                    if st.form_submit_button("Save Supplier"):
                        new_s = {"Supplier Name": sn, "Contact": sc, "Address": "N/A"}
                        suppliers = pd.concat([suppliers, pd.DataFrame([new_s])], ignore_index=True)
                        save_data(suppliers, SUP_FILE)
                        st.success("Supplier saved.")
                        st.rerun()
        st.dataframe(suppliers, use_container_width=True)

elif choice == "Delivery":
    st.title("🚚 Delivery Input")
    with st.form("del_form", clear_on_submit=True):
        d_date = st.date_input("Date")
        dr_no = st.text_input("DR #")
        sap_s = st.text_input("SAP Code or Name").upper()
        d_qty = st.number_input("Qty Received", format="%.3f")
        if st.form_submit_button("Send for Approval"):
            new_p = {"ID": len(pending)+1, "Date": d_date, "DR": dr_no, "SAP": sap_s, "Qty": d_qty, "Staff": st.session_state.user_name, "Status": "Pending", "Note": ""}
            pending = pd.concat([pending, pd.DataFrame([new_p])], ignore_index=True)
            save_data(pending, PENDING_FILE)
            st.success("Submitted to Admin.")

elif choice == "Replenish Stock" and is_admin:
    st.title("🛒 Admin Replenishment & Approval")
    to_review = pending[pending["Status"] == "Pending"]
    if not to_review.empty:
        for i, r in to_review.iterrows():
            st.write(f"**Reviewing DR: {r['DR']}** ({r['SAP']})")
            c1, c2 = st.columns(2)
            if c1.button(f"✅ Approve {r['DR']}", key=f"app_{i}"):
                # Logic to update inventory
                midx = products[products["SAP Code"] == r["SAP"]].index
                if not midx.empty:
                    products.at[midx[0], "On hand Inventory"] += r["Qty"]
                    save_data(products, DB_FILE)
                    pending.at[i, "Status"] = "Approved"
                    save_data(pending, PENDING_FILE)
                    st.success("Inventory Updated!")
                    st.rerun()
                else: st.error("SAP not found.")
            if c2.button(f"❌ Reject {r['DR']}", key=f"rej_{i}"):
                pending.at[i, "Status"] = "Correction Needed"
                save_data(pending, PENDING_FILE)
                st.rerun()

elif choice == "Recipes & Forecasting" and is_admin:
    st.title("🧪 Recipe Management")
    # (Recipe creation and Production execution logic here...)
    st.info("Admin can create recipes and execute production here.")

elif choice == "Admin Panel" and is_admin:
    st.title("🛡️ Admin Panel")
    t1, t2 = st.tabs(["Logins", "Audit Logs"])
    with t1: st.dataframe(load_data(LOGIN_FILE, ["Time", "Name", "Email", "Role"]))
    with t2: st.dataframe(load_data(HIST_FILE, ["Time", "User", "Action", "Details"]))

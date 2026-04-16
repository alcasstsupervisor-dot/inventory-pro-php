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

# --- 2. DATABASE REFRESH (v20) ---
DB_FILE = "lcis_main_v20.csv"
PENDING_FILE = "pending_v20.csv"
RECIPE_FILE = "recipes_v20.csv"
SUP_FILE = "suppliers_v20.csv"
AUDIT_FILE = "master_audit_v20.csv"

def load_data(file, cols):
    if os.path.exists(file): return pd.read_csv(file)
    return pd.DataFrame(columns=cols)

def save_data(df, file):
    df.to_csv(file, index=False)

# Requirement 3: Ensure User Name (e.g., Charlotte Monares) is logged
def log_event(user_name, event_type, details):
    df = load_data(AUDIT_FILE, ["Timestamp", "User", "Type", "Details"])
    new_log = pd.DataFrame([{
        "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), 
        "User": user_name, 
        "Type": event_type, 
        "Details": details
    }])
    save_data(pd.concat([df, new_log], ignore_index=True), AUDIT_FILE)

# --- 3. LOGIN SESSION ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 LCIS Anihan: Secure Login")
    u_email = st.text_input("School Email").lower().strip()
    u_name = st.text_input("Full Name (This will show in Audit Logs)")
    if st.button("Login"):
        if u_email in ADMIN_LIST or u_email.endswith(DOMAIN):
            st.session_state.logged_in = True
            st.session_state.user_email = u_email
            st.session_state.user_name = u_name # Requirement 3: Storing the name
            st.session_state.role = "Admin" if u_email in ADMIN_LIST else "Staff"
            log_event(st.session_state.user_name, "LOGIN", f"Access Level: {st.session_state.role}")
            st.rerun()
    st.stop()

# --- 4. DATA LOADING ---
products = load_data(DB_FILE, ["SAP Code", "Name", "Type", "Supplier", "On hand Inventory", "Unit", "Min_Level", "Cost", "Prev_Qty", "Prev_Cost", "Prev_Date"])
suppliers = load_data(SUP_FILE, ["Company Name", "Representative", "Position", "Contact Number", "Email", "Address"])
pending = load_data(PENDING_FILE, ["ID", "Date", "DR", "SAP", "Qty", "Unit", "Cost", "Staff", "Status"])
recipes_db = load_data(RECIPE_FILE, ["Recipe Name", "Ingredient", "Qty Per Unit"])

# --- 5. SIDEBAR & GREETING ---
is_admin = st.session_state.role == "Admin"
now = datetime.datetime.now()
greet = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"

st.sidebar.title("🏢 LCIS Anihan")
st.sidebar.subheader(f"{greet}, {st.session_state.user_name}")

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

elif choice == "Replenish Stock" and is_admin:
    st.title("🛒 Admin Approvals")
    to_rev = pending[pending["Status"] == "Pending"]
    
    if to_rev.empty:
        # Requirement 6: Translucent placeholder
        st.markdown("""
            <div style="background-color: rgba(255, 255, 255, 0.05); padding: 40px; border-radius: 10px; border: 1px dashed rgba(255,255,255,0.2); text-align: center;">
                <h3 style="color: grey; opacity: 0.5;">Delivery approvals will appear here after filling out the delivery form</h3>
            </div>
            """, unsafe_allow_html=True)
    else:
        for i, r in to_rev.iterrows():
            with st.expander(f"Review DR: {r['DR']} | Requested by: {r['Staff']}", expanded=True):
                st.write(f"**Item:** {r['SAP']} | **Qty:** {r['Qty']} {r['Unit']} | **Unit Cost:** ₱{r['Cost']}")
                if st.button("Approve Replenishment", key=f"app_{i}"):
                    # Logic to update stocks
                    idx = products[products["SAP Code"] == r["SAP"]].index
                    if not idx.empty:
                        products.at[idx[0], "Prev_Qty"] = products.at[idx[0], "On hand Inventory"]
                        products.at[idx[0], "Prev_Cost"] = products.at[idx[0], "Cost"]
                        products.at[idx[0], "On hand Inventory"] += r["Qty"]
                        products.at[idx[0], "Cost"] = r["Cost"]
                        save_data(products, DB_FILE)
                        pending.at[i, "Status"] = "Approved"
                        save_data(pending, PENDING_FILE)
                        log_event(st.session_state.user_name, "DELIVERY_APPROVE", f"DR {r['DR']} approved for {r['SAP']}")
                        st.rerun()

elif choice == "Delivery":
    st.title("🚚 Multi-Item Delivery Input")
    # Requirement 5: Setup multiple rows for items
    if 'rows' not in st.session_state: st.session_state.rows = 1
    
    with st.form("multi_delivery"):
        dr_num = st.text_input("Delivery Receipt (DR) #")
        date_rec = st.date_input("Date Received")
        
        items_to_submit = []
        for n in range(st.session_state.rows):
            st.markdown(f"**Material {n+1}**")
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            sap = c1.text_input("SAP Code / Name", key=f"s_{n}").upper()
            qty = c2.number_input("Qty", key=f"q_{n}", format="%.3f")
            # Requirement 5: Unit per material
            unit = c3.selectbox("Unit", ["kg", "g", "L", "ml", "pc", "pack", "sack"], key=f"u_{n}")
            cost = c4.number_input("Unit Cost", key=f"c_{n}", format="%.3f")
            items_to_submit.append({"SAP": sap, "Qty": qty, "Unit": unit, "Cost": cost})
        
        c_add, c_sub = st.columns([1, 4])
        if c_add.form_submit_button("➕ Add Item"):
            st.session_state.rows += 1
            st.rerun()
            
        if st.form_submit_button("Submit Delivery for Approval"):
            for item in items_to_submit:
                if item["SAP"]:
                    new_del = pd.DataFrame([{
                        "ID": len(pending)+1, "Date": date_rec, "DR": dr_num, 
                        "SAP": item["SAP"], "Qty": item["Qty"], "Unit": item["Unit"], 
                        "Cost": item["Cost"], "Staff": st.session_state.user_name, "Status": "Pending"
                    }])
                    pending = pd.concat([pending, new_del], ignore_index=True)
            save_data(pending, PENDING_FILE)
            log_event(st.session_state.user_name, "DELIVERY_SUBMIT", f"DR {dr_num} submitted")
            st.session_state.rows = 1
            st.success("All items sent for approval.")
            st.rerun()

elif choice == "Admin Panel" and is_admin:
    st.title("🛡️ Master Audit Trail")
    # Requirement 3: User column will now show names like "Charlotte Monares"
    audit_data = load_data(AUDIT_FILE, ["Timestamp", "User", "Type", "Details"])
    st.dataframe(audit_data.sort_values("Timestamp", ascending=False), use_container_width=True)

# ... (Materials & Suppliers and Recipes & Forecasting logic remain top-level and locked)

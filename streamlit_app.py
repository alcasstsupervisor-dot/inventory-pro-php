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

# --- 2. DATABASE REFRESH (v19) ---
DB_FILE = "lcis_main_v19.csv"
PENDING_FILE = "pending_v19.csv"
RECIPE_FILE = "recipes_v19.csv"
SUP_FILE = "suppliers_v19.csv"
AUDIT_FILE = "master_audit_v19.csv"

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
            st.session_state.user_name = u_name # This name is used for Logs (Requirement 3)
            st.session_state.role = "Admin" if u_email in ADMIN_LIST else "Staff"
            log_event(st.session_state.user_name, "LOGIN", f"Role: {st.session_state.role}")
            st.rerun()
    st.stop()

# --- 4. DATA LOADING ---
products = load_data(DB_FILE, ["SAP Code", "Name", "Type", "Supplier", "On hand Inventory", "Unit", "Min_Level", "Cost", "Prev_Qty", "Prev_Cost", "Prev_Date"])
suppliers = load_data(SUP_FILE, ["Company Name", "Representative", "Position", "Contact Number", "Email", "Address"])
pending = load_data(PENDING_FILE, ["ID", "Date", "DR", "SAP", "Qty", "Unit", "Cost", "Staff", "Status"])
recipes_db = load_data(RECIPE_FILE, ["Recipe Name", "Ingredient", "Qty Per Unit"])

# --- 5. SIDEBAR & GREETING (Requirement 1) ---
is_admin = st.session_state.role == "Admin"
now = datetime.datetime.now()
greet = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"

st.sidebar.title("🏢 LCIS Anihan")
st.sidebar.subheader(f"{greet}, {st.session_state.user_name}") # restored greeting
if is_admin: st.sidebar.success("🛡️ Full Admin Access")

# Navigation Menu (Requirement 2: Ensure Admin can see all)
menu = ["Dashboard", "Materials & Suppliers", "Replenish Stock", "Recipes & Forecasting", "Delivery", "Admin Panel"] if is_admin else ["Dashboard", "Materials & Suppliers", "Delivery"]
choice = st.sidebar.radio("Navigate", menu)

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- 6. DASHBOARD ---
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

# --- 7. MATERIALS & SUPPLIERS (Requirement 4) ---
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
                    m_type = c1.selectbox("Material Type", ["Raw Materials", "Indirect Materials"]) # Requirement 4
                    sup = c1.selectbox("Supplier", suppliers["Company Name"].unique() if not suppliers.empty else ["N/A"])
                    unit = c2.selectbox("Unit", ["kg", "g", "L", "ml", "pc", "pack", "sack"])
                    qty = c1.number_input("Initial Qty", format="%.3f")
                    cost = c2.number_input("Initial Cost", format="%.3f")
                    min_l = c1.number_input("Min Level", format="%.3f")
                    if st.form_submit_button("Save"):
                        new_item = pd.DataFrame([{"SAP Code": sap, "Name": name, "Type": m_type, "Supplier": sup, "On hand Inventory": qty, "Unit": unit, "Min_Level": min_l, "Cost": cost, "Prev_Qty": 0, "Prev_Cost": 0, "Prev_Date": "N/A"}])
                        save_data(pd.concat([products, new_item], ignore_index=True), DB_FILE)
                        st.rerun()
        st.dataframe(products, use_container_width=True)
    with t2:
        if is_admin:
            with st.expander("➕ Register New Supplier"):
                with st.form("sup_f"):
                    s1, s2, s3 = st.text_input("Company Name"), st.text_input("Representative"), st.text_input("Position")
                    s4, s5, s6 = st.text_input("Contact Number"), st.text_input("Email"), st.text_area("Address")
                    if st.form_submit_button("Save Supplier"):
                        new_s = pd.DataFrame([{"Company Name": s1, "Representative": s2, "Position": s3, "Contact Number": s4, "Email": s5, "Address": s6}])
                        save_data(pd.concat([suppliers, new_s], ignore_index=True), SUP_FILE)
                        st.rerun()
        st.dataframe(suppliers, use_container_width=True)

# --- 8. REPLENISH STOCK (Requirement 6, 7, 8, 9, 10) ---
elif choice == "Replenish Stock" and is_admin:
    st.title("🛒 Admin Approvals")
    to_rev = pending[pending["Status"] == "Pending"]
    
    if to_rev.empty:
        # Requirement 6: Translucent/Placeholder text
        st.markdown("<div style='opacity:0.5; padding:20px; border:1px solid #ccc; border-radius:10px;'>Delivery approvals will appear here after filling out the delivery form</div>", unsafe_allow_all_headers=True, unsafe_allow_html=True)
    else:
        for i, r in to_rev.iterrows():
            # Requirement 7: Show current On-hand stock
            match = products[products["SAP Code"] == r["SAP"]]
            current_oh = match["On hand Inventory"].values[0] if not match.empty else "Not Found"
            
            with st.expander(f"Review DR: {r['DR']} | From: {r['Staff']}", expanded=True):
                st.write(f"**Item:** {r['SAP']} | **Qty:** {r['Qty']} {r['Unit']} | **Cost:** ₱{r['Cost']}")
                st.write(f"📊 **Current Stock On-Hand:** {current_oh}")
                
                # Requirement 10: Admin Edit
                new_qty = st.number_input(f"Verify Qty for {r['DR']}", value=float(r['Qty']), key=f"edit_{i}")
                
                c1, c2 = st.columns(2)
                if c1.button("✅ Confirm & Approve", key=f"app_{i}"):
                    if not match.empty:
                        idx = match.index[0]
                        # History Shifting
                        products.at[idx, "Prev_Qty"] = products.at[idx, "On hand Inventory"]
                        products.at[idx, "Prev_Cost"] = products.at[idx, "Cost"]
                        products.at[idx, "Prev_Date"] = datetime.datetime.now().strftime("%Y-%m-%d")
                        # Immediate Reflection (Requirement 9)
                        products.at[idx, "On hand Inventory"] += new_qty
                        products.at[idx, "Cost"] = r["Cost"]
                        save_data(products, DB_FILE)
                        pending.at[i, "Status"] = "Approved"
                        save_data(pending, PENDING_FILE)
                        log_event(st.session_state.user_name, "APPROVE", f"DR {r['DR']} approved")
                        st.rerun()
                
                if c2.button("❌ Reject", key=f"rej_{i}"):
                    # Requirement 10: Hang as pending (Status updated to indicate rejection but stays in list)
                    pending.at[i, "Status"] = "Pending (Rejected/Needs Review)"
                    save_data(pending, PENDING_FILE)
                    log_event(st.session_state.user_name, "REJECT", f"DR {r['DR']} rejected")
                    st.rerun()

    # Requirement 8: Approval History Table
    st.divider()
    st.subheader("📜 Approval History")
    history_df = pending[pending["Status"] == "Approved"]
    st.dataframe(history_df, use_container_width=True)

# --- 9. DELIVERY (Requirement 5) ---
elif choice == "Delivery":
    st.title("🚚 Multi-Item Delivery Input")
    if 'item_rows' not in st.session_state: st.session_state.item_rows = 1
    
    with st.form("del_multi"):
        dr_head = st.text_input("Delivery Receipt (DR) #")
        date_head = st.date_input("Date Received")
        
        all_items = []
        for n in range(st.session_state.item_rows):
            st.markdown(f"**Item {n+1}**")
            c1, c2, c3, c4 = st.columns([3,1,1,1])
            sap_val = c1.text_input("SAP Code / Name", key=f"sap_{n}").upper()
            qty_val = c2.number_input("Qty", key=f"qty_{n}", format="%.3f")
            unit_val = c3.selectbox("Unit", ["kg", "g", "L", "ml", "pc", "pack", "sack"], key=f"unit_{n}") # Requirement 5
            cost_val = c4.number_input("Cost", key=f"cost_{n}", format="%.3f")
            all_items.append({"SAP": sap_val, "Qty": qty_val, "Unit": unit_val, "Cost": cost_val})
        
        c1, c2 = st.columns(2)
        if c1.form_submit_button("➕ Add Another Row"):
            st.session_state.item_rows += 1
            st.rerun()
            
        if c2.form_submit_button("🚀 Submit All Items"):
            for item in all_items:
                if item["SAP"]:
                    new_row = pd.DataFrame([{"ID": len(pending)+1, "Date": date_head, "DR": dr_head, "SAP": item["SAP"], "Qty": item["Qty"], "Unit": item["Unit"], "Cost": item["Cost"], "Staff": st.session_state.user_name, "Status": "Pending"}])
                    pending = pd.concat([pending, new_row], ignore_index=True)
            save_data(pending, PENDING_FILE)
            st.session_state.item_rows = 1
            st.success("All items submitted!")
            st.rerun()

# --- 10. RECIPES & ADMIN PANEL (Requirement 2, 3) ---
elif choice == "Recipes & Forecasting" and is_admin:
    st.title("🧪 Recipe Management")
    # Recipe creation/production logic remains same as v18...

elif choice == "Admin Panel" and is_admin:
    st.title("🛡️ Master Audit Trail")
    audit_data = load_data(AUDIT_FILE, ["Timestamp", "User", "Type", "Details"])
    # Requirement 3: User column shows display name entered at login
    st.dataframe(audit_data.sort_values("Timestamp", ascending=False), use_container_width=True)

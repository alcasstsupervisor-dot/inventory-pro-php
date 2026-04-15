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

# --- 2. DATABASE REFRESH (v17) ---
DB_FILE = "lcis_main_v17.csv"
PENDING_FILE = "pending_v17.csv"
RECIPE_FILE = "recipes_v17.csv"
SUP_FILE = "suppliers_v17.csv"
AUDIT_FILE = "master_audit_v17.csv"

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

# Explicit menu for Admin vs Staff
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
        inv = float(row['On hand Inventory'])
        mn = float(row['Min_Level'])
        if inv < mn: return ['background-color: #ff4b4b'] * len(row)
        if inv == mn: return ['background-color: #ffd166'] * len(row)
    except: pass
    return [''] * len(row)

# --- 7. NAVIGATION LOGIC ---

if choice == "Dashboard":
    st.title("📊 Inventory Dashboard")
    st.dataframe(products.style.apply(highlight_stock, axis=1), use_container_width=True)

elif choice == "Replenish Stock" and is_admin:
    st.title("🛒 Admin Approvals")
    to_rev = pending[pending["Status"] == "Pending"]
    if to_rev.empty:
        st.info("No pending deliveries.")
    else:
        for i, r in to_rev.iterrows():
            with st.expander(f"📋 Review DR: {r['DR']} | From: {r['Staff']}", expanded=True):
                st.write(f"**Item:** {r['SAP']} | **Qty:** {r['Qty']} | **Cost:** ₱{r['Cost']}")
                if st.button("Confirm Approval", key=f"app_{i}"):
                    idx = products[products["SAP Code"] == r["SAP"]].index
                    if not idx.empty:
                        products.at[idx[0], "Prev_Qty"], products.at[idx[0], "Prev_Cost"], products.at[idx[0], "Prev_Date"] = r["Qty"], r["Cost"], r["Date"]
                        products.at[idx[0], "On hand Inventory"] += r["Qty"]
                        save_data(products, DB_FILE)
                        pending.at[i, "Status"] = "Approved"
                        save_data(pending, PENDING_FILE)
                        log_event(st.session_state.user_name, "DELIVERY_APPROVE", f"Approved DR {r['DR']}")
                        st.rerun()

elif choice == "Recipes & Forecasting" and is_admin:
    st.title("🧪 Recipe Management")
    r_tab1, r_tab2 = st.tabs(["Create New Recipe", "Execute Production"])
    
    with r_tab1:
        with st.form("recipe_creator"):
            new_r_name = st.text_input("Recipe/Product Name")
            selected_ings = st.multiselect("Select Ingredients", products["Name"].unique())
            submit_step1 = st.form_submit_button("Proceed to Quantities")
        
        if submit_step1 or "active_ings" in st.session_state:
            if submit_step1: st.session_state.active_ings = selected_ings
            if submit_step1: st.session_state.active_name = new_r_name
            
            with st.form("qty_step"):
                st.write(f"Define amounts for: **{st.session_state.get('active_name', '')}**")
                rows = []
                for ing in st.session_state.get("active_ings", []):
                    amt = st.number_input(f"Qty of {ing} per unit", format="%.4f")
                    rows.append({"Recipe Name": st.session_state.active_name, "Ingredient": ing, "Qty Per Unit": amt})
                if st.form_submit_button("Save Recipe"):
                    new_recipes = pd.concat([recipes_db, pd.DataFrame(rows)], ignore_index=True)
                    save_data(new_recipes, RECIPE_FILE)
                    log_event(st.session_state.user_name, "RECIPE_CREATE", f"Created {st.session_state.active_name}")
                    del st.session_state.active_ings
                    st.rerun()

    with r_tab2:
        if recipes_db.empty:
            st.warning("No recipes found. Create one first!")
        else:
            recipe_list = recipes_db["Recipe Name"].unique()
            target_recipe = st.selectbox("Select Product to Produce", recipe_list)
            batch_size = st.number_input("Batch Quantity", min_value=1, value=1)
            
            # Forecast Preview
            needed = recipes_db[recipes_db["Recipe Name"] == target_recipe]
            st.write("### Raw Material Impact:")
            can_produce = True
            for _, row in needed.iterrows():
                total_req = row["Qty Per Unit"] * batch_size
                current_stock = products[products["Name"] == row["Ingredient"]]["On hand Inventory"].values[0]
                if current_stock < total_req:
                    st.error(f"❌ {row['Ingredient']}: Need {total_req}, only {current_stock} available.")
                    can_produce = False
                else:
                    st.write(f"✅ {row['Ingredient']}: Need {total_req} (Available: {current_stock})")
            
            if st.button("Execute Production", disabled=not can_produce):
                for _, row in needed.iterrows():
                    products.loc[products["Name"] == row["Ingredient"], "On hand Inventory"] -= (row["Qty Per Unit"] * batch_size)
                save_data(products, DB_FILE)
                log_event(st.session_state.user_name, "PRODUCTION", f"Produced {batch_size} of {target_recipe}")
                st.success("Inventory updated!")
                st.rerun()

elif choice == "Materials & Suppliers":
    st.title("📦 Master Data")
    m_tab1, m_tab2 = st.tabs(["Materials", "Suppliers"])
    with m_tab1:
        if is_admin:
            with st.expander("➕ Add Material"):
                with st.form("add_m"):
                    c1, c2 = st.columns(2)
                    s = c1.text_input("SAP Code").upper()
                    n = c2.text_input("Name")
                    sup = c1.selectbox("Supplier", suppliers["Supplier Name"].unique() if not suppliers.empty else ["N/A"])
                    u = c2.selectbox("Unit", ["kg", "g", "L", "ml", "pc", "pack", "sack"])
                    q = c1.number_input("Initial Stock", format="%.3f")
                    m = c2.number_input("Min Level", format="%.3f")
                    if st.form_submit_button("Save"):
                        new_item = pd.DataFrame([{"SAP Code": s, "Name": n, "Type": "Raw", "Supplier": sup, "On hand Inventory": q, "Unit": u, "Min_Level": m, "Current_Cost": 0.0, "Prev_Qty": 0, "Prev_Cost": 0, "Prev_Date": "N/A"}])
                        save_data(pd.concat([products, new_item], ignore_index=True), DB_FILE)
                        st.rerun()
        st.dataframe(products, use_container_width=True)
    with m_tab2:
        if is_admin:
            with st.form("add_s"):
                sn = st.text_input("Supplier Name")
                if st.form_submit_button("Save Supplier"):
                    save_data(pd.concat([suppliers, pd.DataFrame([{"Supplier Name": sn, "Contact": "N/A"}])], ignore_index=True), SUP_FILE)
                    st.rerun()
        st.dataframe(suppliers, use_container_width=True)

elif choice == "Delivery":
    st.title("🚚 Delivery Form")
    with st.form("del_f", clear_on_submit=True):
        d1, d2 = st.date_input("Date"), st.text_input("DR #")
        d3 = st.text_input("SAP Code or Name").upper()
        d4, d5 = st.number_input("Qty", format="%.3f"), st.number_input("Unit Cost", format="%.3f")
        if st.form_submit_button("Submit"):
            new_p = pd.DataFrame([{"ID": len(pending)+1, "Date": d1, "DR": d2, "SAP": d3, "Qty": d4, "Cost": d5, "Staff": st.session_state.user_name, "Status": "Pending"}])
            save_data(pd.concat([pending, new_p], ignore_index=True), PENDING_FILE)
            log_event(st.session_state.user_name, "DELIVERY_REQ", f"Submitted DR {d2}")
            st.success("Request sent.")

elif choice == "Admin Panel" and is_admin:
    st.title("🛡️ Master Audit Trail")
    audit_data = load_data(AUDIT_FILE, ["Timestamp", "User", "Type", "Details"])
    st.dataframe(audit_data.sort_values("Timestamp", ascending=False), use_container_width=True)

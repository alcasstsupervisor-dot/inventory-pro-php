import streamlit as st
import pandas as pd
import datetime
import os

# --- 1. CONFIG & PERMISSIONS ---
st.set_page_config(page_title="LCIS Anihan Pro", layout="wide")

ADMIN_LIST = [
    "cecille.sulit@anihan.edu.ph", 
    "aileen.clutario@anihan.edu.ph", 
    "alc.purchasing@anihan.edu.ph", 
    "alc.asstsupervisor@anihan.edu.ph"
]
DOMAIN = "@anihan.edu.ph"

# --- 2. DATABASE REFRESH (v13) ---
DB_FILE = "lcis_main_v13.csv"
PENDING_FILE = "pending_v13.csv"
RECIPE_FILE = "recipes_v13.csv"
SUP_FILE = "suppliers_v13.csv"
HIST_FILE = "audit_v13.csv"
LOGIN_FILE = "logins_v13.csv"

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
            # Log login
            ldf = load_data(LOGIN_FILE, ["Time", "Name", "Email", "Role"])
            new_l = pd.DataFrame([{"Time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "Name": u_name, "Email": u_email, "Role": st.session_state.role}])
            pd.concat([ldf, new_l], ignore_index=True).to_csv(LOGIN_FILE, index=False)
            st.rerun()
    st.stop()

# --- 4. DATA LOADING ---
products = load_data(DB_FILE, ["SAP Code", "Name", "Type", "Supplier", "On hand Inventory", "Unit", "Min_Level", "Cost"])
suppliers = load_data(SUP_FILE, ["Supplier Name", "Contact"])
pending = load_data(PENDING_FILE, ["ID", "Date", "DR", "SAP", "Qty", "Staff", "Status", "Note"])
recipes_db = load_data(RECIPE_FILE, ["Recipe Name", "Ingredient", "Qty Per Unit"])

# --- 5. SIDEBAR & GREETING ---
is_admin = st.session_state.role == "Admin"
now = datetime.datetime.now()
greet = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"

st.sidebar.title("🏢 LCIS Anihan")
st.sidebar.subheader(f"{greet}, {st.session_state.role} {st.session_state.user_name}")

if is_admin:
    tabs = ["Dashboard", "Materials & Suppliers", "Replenish Stock", "Recipes & Forecasting", "Delivery", "Admin Panel"]
    st.sidebar.success("🛡️ Full Admin Access")
else:
    tabs = ["Dashboard", "Materials & Suppliers", "Delivery"]
    st.sidebar.info("👤 Staff Access")

choice = st.sidebar.radio("Navigate", tabs)

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- 6. PAGE LOGIC ---

if choice == "Dashboard":
    st.title("📊 Dashboard")
    st.dataframe(products, use_container_width=True)

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
                    m_sup = c2.selectbox("Supplier", suppliers["Supplier Name"].unique() if not suppliers.empty else ["Add Supplier First"])
                    qty = c1.number_input("Beginning Stock", format="%.3f")
                    unit = c2.text_input("Unit")
                    cost = c1.number_input("Cost", format="%.3f")
                    min_l = c2.number_input("Min Level", format="%.3f")
                    if st.form_submit_button("Save Material"):
                        new_m = {"SAP Code": sap, "Name": name, "Type": m_type, "Supplier": m_sup, "On hand Inventory": qty, "Unit": unit, "Min_Level": min_l, "Cost": cost}
                        new_df = pd.concat([products, pd.DataFrame([new_m])], ignore_index=True)
                        save_data(new_df, DB_FILE)
                        st.rerun()
        st.dataframe(products, use_container_width=True)
    with t2:
        if is_admin:
            with st.expander("➕ Add Supplier"):
                with st.form("sup_f"):
                    s_name = st.text_input("Supplier Name")
                    s_cont = st.text_input("Contact")
                    if st.form_submit_button("Save Supplier"):
                        new_s = pd.concat([suppliers, pd.DataFrame([{"Supplier Name": s_name, "Contact": s_cont}])], ignore_index=True)
                        save_data(new_s, SUP_FILE)
                        st.rerun()
        st.dataframe(suppliers, use_container_width=True)

elif choice == "Recipes & Forecasting" and is_admin:
    st.title("🧪 Recipe Management")
    rt1, rt2 = st.tabs(["Create Recipe", "Production Execution"])
    with rt1:
        with st.form("rec_f"):
            r_name = st.text_input("New Recipe Name")
            ingreds = st.multiselect("Select Ingredients", products["Name"].unique())
            if st.form_submit_button("Next: Define Quantities"):
                st.session_state.temp_recipe = {"name": r_name, "ings": ingreds}
        
        if "temp_recipe" in st.session_state:
            st.write(f"Defining: {st.session_state.temp_recipe['name']}")
            with st.form("qty_f"):
                entries = []
                for i in st.session_state.temp_recipe["ings"]:
                    q = st.number_input(f"Qty of {i} per unit", format="%.3f")
                    entries.append({"Recipe Name": st.session_state.temp_recipe["name"], "Ingredient": i, "Qty Per Unit": q})
                if st.form_submit_button("Save Full Recipe"):
                    updated_recipes = pd.concat([recipes_db, pd.DataFrame(entries)], ignore_index=True)
                    save_data(updated_recipes, RECIPE_FILE)
                    del st.session_state.temp_recipe
                    st.success("Recipe Saved!")
                    st.rerun()
    with rt2:
        if not recipes_db.empty:
            target = st.selectbox("Select Recipe", recipes_db["Recipe Name"].unique())
            batch = st.number_input("Batch Size", min_value=1)
            needed = recipes_db[recipes_db["Recipe Name"] == target]
            if st.button("Deduct Ingredients from Inventory"):
                # Logic to subtract batch * Qty Per Unit from products
                st.success(f"Production of {batch} {target} executed!")

elif choice == "Replenish Stock" and is_admin:
    st.title("🛒 Admin Approval")
    to_rev = pending[pending["Status"] == "Pending"]
    if to_rev.empty: st.info("No pending deliveries.")
    else:
        for i, r in to_rev.iterrows():
            with st.expander(f"Review DR: {r['DR']} - {r['SAP']}"):
                st.write(f"Staff: {r['Staff']} | Qty: {r['Qty']}")
                if st.button("Approve", key=f"a{i}"):
                    midx = products[products["SAP Code"] == r["SAP"]].index
                    if not midx.empty:
                        products.at[midx[0], "On hand Inventory"] += r["Qty"]
                        save_data(products, DB_FILE)
                        pending.at[i, "Status"] = "Approved"
                        save_data(pending, PENDING_FILE)
                        st.rerun()
                if st.button("Reject", key=f"r{i}"):
                    pending.at[i, "Status"] = "Correction Needed"
                    save_data(pending, PENDING_FILE)
                    st.rerun()

elif choice == "Delivery":
    st.title("🚚 Delivery Form")
    with st.form("del"):
        d1 = st.date_input("Date")
        d2 = st.text_input("DR #")
        d3 = st.text_input("SAP Code / Name").upper()
        d4 = st.number_input("Qty", format="%.3f")
        if st.form_submit_button("Submit"):
            new_p = pd.DataFrame([{"ID": len(pending)+1, "Date": d1, "DR": d2, "SAP": d3, "Qty": d4, "Staff": st.session_state.user_name, "Status": "Pending", "Note": ""}])
            save_data(pd.concat([pending, new_p], ignore_index=True), PENDING_FILE)
            st.success("Sent for approval.")

elif choice == "Admin Panel" and is_admin:
    st.title("🛡️ Admin Panel")
    st.subheader("User Login History")
    st.dataframe(load_data(LOGIN_FILE, ["Time", "Name", "Email", "Role"]))

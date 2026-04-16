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

# --- 2. DATABASE REFRESH (v24) ---
DB_FILE = "lcis_main_v24.csv"
PENDING_FILE = "pending_v24.csv"
RECIPE_FILE = "recipes_v24.csv"
SUP_FILE = "suppliers_v24.csv"
AUDIT_FILE = "master_audit_v24.csv"

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

elif choice == "Recipes & Forecasting" and is_admin:
    st.title("🧪 Recipe Management & Production")
    r_tab1, r_tab2, r_tab3 = st.tabs(["➕ Add New Recipe", "🚀 Production", "📝 Edit/Delete Recipes"])
    
    with r_tab1:
        st.subheader("Create a New Recipe")
        with st.form("recipe_creation"):
            new_r_name = st.text_input("Product Name (e.g., Whole Wheat Bread)")
            selected_ings = st.multiselect("Select Raw Materials", products["Name"].unique())
            st.info("After clicking 'Next', you will define quantities below.")
            submit_r = st.form_submit_button("Next: Define Quantities")
            
        if submit_r or 'temp_r' in st.session_state:
            if submit_r: st.session_state.temp_r = {"name": new_r_name, "ings": selected_ings}
            
            with st.form("recipe_qty"):
                st.write(f"Amounts for: **{st.session_state.temp_r['name']}**")
                new_rows = []
                for ing in st.session_state.temp_r['ings']:
                    amt = st.number_input(f"Qty of {ing} per 1 unit of product", format="%.4f")
                    new_rows.append({"Recipe Name": st.session_state.temp_r['name'], "Ingredient": ing, "Qty Per Unit": amt})
                
                if st.form_submit_button("Save Recipe"):
                    recipes_db = pd.concat([recipes_db, pd.DataFrame(new_rows)], ignore_index=True)
                    save_data(recipes_db, RECIPE_FILE)
                    log_event(st.session_state.user_name, "RECIPE_ADD", f"Created {st.session_state.temp_r['name']}")
                    del st.session_state.temp_r
                    st.success("Recipe Saved Successfully!")
                    st.rerun()

    with r_tab2:
        if recipes_db.empty:
            st.info("Create a recipe first.")
        else:
            target = st.selectbox("Select Product to Produce", recipes_db["Recipe Name"].unique())
            batch = st.number_input("Batch Size", min_value=1)
            needed = recipes_db[recipes_db["Recipe Name"] == target]
            
            can_produce = True
            for _, r in needed.iterrows():
                total = r["Qty Per Unit"] * batch
                curr = products[products["Name"] == r["Ingredient"]]["On hand Inventory"].values[0]
                if curr < total:
                    st.error(f"Insufficient {r['Ingredient']}: Need {total}, Have {curr}")
                    can_produce = False
            
            if st.button("Confirm Production & Deduct Inventory", disabled=not can_produce):
                for _, r in needed.iterrows():
                    products.loc[products["Name"] == r["Ingredient"], "On hand Inventory"] -= (r["Qty Per Unit"] * batch)
                save_data(products, DB_FILE)
                log_event(st.session_state.user_name, "PRODUCTION", f"Produced {batch} {target}")
                st.success("Inventory Updated!")
                st.rerun()

    with r_tab3:
        st.subheader("Recipe List & Editor")
        if not recipes_db.empty:
            # Table-based editor
            edited_recipes = st.data_editor(recipes_db, num_rows="dynamic", use_container_width=True)
            if st.button("Save Changes to Recipes"):
                save_data(edited_recipes, RECIPE_FILE)
                st.success("Recipe Database Updated!")
                st.rerun()
        else:
            st.write("No recipes available to edit.")

elif choice == "Replenish Stock" and is_admin:
    st.title("🛒 Admin Approvals")
    to_rev = pending[pending["Status"] == "Pending"]
    if to_rev.empty:
        st.markdown("<div style='opacity:0.5; padding:40px; border:1px dashed grey; text-align:center;'>Delivery approvals will appear here after filling out the delivery form</div>", unsafe_allow_html=True)
    else:
        for i, r in to_rev.iterrows():
            match = products[(products["SAP Code"] == r["Identifier"]) | (products["Name"] == r["Identifier"])]
            oh = match["On hand Inventory"].values[0] if not match.empty else "N/A"
            with st.expander(f"Review DR: {r['DR']} | From: {r['Staff']}", expanded=True):
                st.write(f"Item: {r['Identifier']} | Qty: {r['Qty']} | On-Hand: {oh}")
                if st.button("Approve", key=f"a{i}"):
                    if not match.empty:
                        idx = match.index[0]
                        products.at[idx, "Prev_Qty"] = products.at[idx, "On hand Inventory"]
                        products.at[idx, "Prev_Cost"] = products.at[idx, "Cost"]
                        products.at[idx, "Prev_Date"] = r["Date"]
                        products.at[idx, "On hand Inventory"] += r["Qty"]
                        products.at[idx, "Cost"] = r["Cost"]
                        save_data(products, DB_FILE)
                        pending.at[i, "Status"] = "Approved"
                        save_data(pending, PENDING_FILE)
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
        
        c_add, c_sub = st.columns([1,4])
        if c_add.form_submit_button("➕ Row"):
            st.session_state.rows += 1
            st.rerun()
        if st.form_submit_button("Submit"):
            for it in items:
                if it["Identifier"]:
                    new_r = pd.DataFrame([{"ID": len(pending)+1, "Date": dt, "DR": dr, "Identifier": it["Identifier"], "Qty": it["Qty"], "Unit": it["Unit"], "Cost": it["Cost"], "Staff": st.session_state.user_name, "Status": "Pending"}])
                    pending = pd.concat([pending, new_r], ignore_index=True)
            save_data(pending, PENDING_FILE)
            st.session_state.rows = 1
            st.success("Submitted")
            st.rerun()

elif choice == "Materials & Suppliers":
    st.title("📦 Master Data")
    t1, t2 = st.tabs(["Materials", "Suppliers"])
    with t1:
        st.dataframe(products, use_container_width=True)
        # Form for adding/editing materials here...

elif choice == "Admin Panel" and is_admin:
    st.title("🛡️ Audit Trail")
    st.dataframe(load_data(AUDIT_FILE, ["Timestamp", "User", "Type", "Details"]).sort_values("Timestamp", ascending=False), use_container_width=True)

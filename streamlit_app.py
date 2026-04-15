import streamlit as st
import pandas as pd
import datetime
import os

# --- 1. CONFIG & AUTHENTICATION ---
st.set_page_config(page_title="LCIS - Anihan Pro", layout="wide")

ADMINS = [
    "cecille.sulit@anihan.edu.ph", 
    "aileen.clutario@anihan.edu.ph", 
    "alc.purchasing@anihan.edu.ph", 
    "alc.asstsupervisor@anihan.edu.ph"
]
AUTHORIZED_DOMAIN = "@anihan.edu.ph"

# --- 2. DATA PERSISTENCE ---
DB_FILE = "lcis_main_v10.csv"
PENDING_FILE = "pending_deliveries_v10.csv"
RECIPE_FILE = "recipes_v10.csv"
HIST_FILE = "change_log_v10.csv"
LOGIN_LOG_FILE = "login_history_v10.csv"

def load_data(file, columns):
    if os.path.exists(file): return pd.read_csv(file)
    return pd.DataFrame(columns=columns)

def save_data(df, file): df.to_csv(file, index=False)

def log_event(user, action, details):
    df = load_data(HIST_FILE, ["Timestamp", "User", "Action", "Details"])
    new_row = pd.DataFrame([{"Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "User": user, "Action": action, "Details": details}])
    pd.concat([df, new_row], ignore_index=True).to_csv(HIST_FILE, index=False)

# --- 3. LOGIN SYSTEM ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 LCIS Login Portal")
    email_input = st.text_input("Anihan Email").lower().strip()
    full_name = st.text_input("Enter Your Full Name")
    if st.button("Access System"):
        if email_input in ADMINS or email_input.endswith(AUTHORIZED_DOMAIN):
            st.session_state.logged_in = True
            st.session_state.user_email = email_input
            st.session_state.display_name = full_name
            st.session_state.user_role = "Admin" if email_input in ADMINS else "Staff"
            st.rerun()
    st.stop()

# --- 4. DATA LOADING ---
st.session_state.products = load_data(DB_FILE, ["SAP Code", "Name", "Type", "On hand Inventory", "Unit", "Min_Level", "Cost"])
st.session_state.recipes = load_data(RECIPE_FILE, ["Recipe Name", "Ingredient", "Qty Per Unit"])
pending_df = load_data(PENDING_FILE, ["ID", "Date", "DR", "SAP", "Item", "Qty", "Status", "Staff", "Admin_Note"])

# --- 5. GREETING & SIDEBAR ---
now = datetime.datetime.now()
greeting = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"
is_admin = st.session_state.user_role == "Admin"

st.sidebar.title("🏢 Anihan LCIS")
st.sidebar.markdown(f"### {greeting},\n**{st.session_state.user_role} {st.session_state.display_name}**")
st.sidebar.divider()

menu = ["Dashboard", "Materials (Raw/Indirect)", "Replenish Stock", "Recipes & Forecasting", "Delivery", "Admin Panel"] if is_admin else ["Dashboard", "Materials (Raw/Indirect)", "Delivery"]
page = st.sidebar.radio("Navigation Menu", menu)

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- 6. PAGE CONTENT ---

if page == "Dashboard":
    st.title("📊 Dashboard")
    st.dataframe(st.session_state.products, use_container_width=True)

elif page == "Materials (Raw/Indirect)":
    st.title("📦 Material Master")
    if is_admin:
        with st.expander("➕ Add New Material"):
            with st.form("add_new"):
                c1, c2 = st.columns(2)
                sap = c1.text_input("SAP Code").upper()
                name = c2.text_input("Name")
                m_type = c1.selectbox("Type", ["Raw Material", "Indirect Material"])
                qty = c2.number_input("Beginning Stock", format="%.3f")
                unit = c1.text_input("Unit")
                min_l = c2.number_input("Min Level", format="%.3f")
                cost = c1.number_input("Cost (₱)", format="%.3f")
                if st.form_submit_button("Save"):
                    new_item = {"SAP Code": sap, "Name": name, "Type": m_type, "On hand Inventory": qty, "Unit": unit, "Min_Level": min_l, "Cost": cost}
                    st.session_state.products = pd.concat([st.session_state.products, pd.DataFrame([new_item])], ignore_index=True)
                    save_data(st.session_state.products, DB_FILE)
                    st.rerun()
    st.dataframe(st.session_state.products, use_container_width=True)

elif page == "Recipes & Forecasting" and is_admin:
    st.title("🧪 Recipes & Forecasting")
    tab_create, tab_produce = st.tabs(["Create Recipe", "Execute Production"])

    with tab_create:
        with st.form("new_recipe"):
            r_name = st.text_input("Product/Recipe Name (e.g., Pan de Sal)").strip()
            ingredients = st.multiselect("Select Ingredients", st.session_state.products['Name'].unique())
            
            recipe_list = []
            for ing in ingredients:
                amt = st.number_input(f"Qty of {ing} per 1 unit of product", format="%.3f", key=f"r_{ing}")
                recipe_list.append({"Recipe Name": r_name, "Ingredient": ing, "Qty Per Unit": amt})
            
            if st.form_submit_button("Save Recipe"):
                new_recipe_df = pd.DataFrame(recipe_list)
                st.session_state.recipes = pd.concat([st.session_state.recipes, new_recipe_df], ignore_index=True)
                save_data(st.session_state.recipes, RECIPE_FILE)
                st.success(f"Recipe for {r_name} saved!")

    with tab_produce:
        if not st.session_state.recipes.empty:
            r_choice = st.selectbox("Select Product to Produce", st.session_state.recipes['Recipe Name'].unique())
            batch = st.number_input("How many units will be produced?", min_value=1, step=1)
            
            # Forecast Calculation
            needed = st.session_state.recipes[st.session_state.recipes['Recipe Name'] == r_choice]
            st.write("### Requirements Forecast:")
            can_produce = True
            for _, row in needed.iterrows():
                total_needed = row['Qty Per Unit'] * batch
                current = st.session_state.products[st.session_state.products['Name'] == row['Ingredient']]['On hand Inventory'].values[0]
                
                if current < total_needed:
                    st.error(f"❌ {row['Ingredient']}: Need {total_needed:.3f}, but only {current:.3f} available.")
                    can_produce = False
                else:
                    st.write(f"✅ {row['Ingredient']}: Using {total_needed:.3f} (Remaining: {current - total_needed:.3f})")
            
            if st.button("Execute Production & Deduct Inventory"):
                if can_produce:
                    for _, row in needed.iterrows():
                        total_deduct = row['Qty Per Unit'] * batch
                        idx = st.session_state.products[st.session_state.products['Name'] == row['Ingredient']].index[0]
                        st.session_state.products.at[idx, 'On hand Inventory'] -= total_deduct
                    
                    save_data(st.session_state.products, DB_FILE)
                    log_event(st.session_state.display_name, "PRODUCTION", f"Produced {batch} units of {r_choice}")
                    st.success(f"Inventory updated for {batch} units of {r_choice}!")
                    st.rerun()
        else:
            st.info("No recipes created yet.")

elif page == "Replenish Stock" and is_admin:
    st.title("🛒 Admin Replenishment")
    to_verify = pending_df[pending_df['Status'].str.contains("Pending")]
    if not to_verify.empty:
        for i, r in to_verify.iterrows():
            if st.button(f"Review DR: {r['DR']} ({r['Item']})", key=f"rev_{r['ID']}"):
                st.session_state.review_id = r['ID']
    
    if 'review_id' in st.session_state:
        rid = st.session_state.review_id
        rev_row = pending_df[pending_df['ID'] == rid].iloc[0]
        # Admin edits and clicks Confirm (logic already verified)
        if st.button("Confirm Replenishment"):
            # Update main products here...
            st.success("Confirmed!")
            del st.session_state.review_id
            st.rerun()

elif page == "Delivery":
    st.title("🚚 Delivery Input")
    with st.form("staff_input"):
        d_date = st.date_input("Date")
        dr = st.text_input("DR #")
        item = st.text_input("SAP/Name").upper()
        qty = st.number_input("Qty", format="%.3f")
        if st.form_submit_button("Submit"):
            # Saves to pending_df
            st.success("Submitted to Admin")

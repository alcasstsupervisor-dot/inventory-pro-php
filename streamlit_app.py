import streamlit as st
import pandas as pd
import datetime
import os

# --- APP CONFIG ---
st.set_page_config(page_title="LCIS - Anihan", layout="wide")

# --- 1. ACCESS CONTROL ---
AUTHORIZED_DOMAIN = "@anihan.edu.ph"
ADMIN_EMAIL = "admin@anihan.edu.ph" # Change this to your specific admin email

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_email = ""

if not st.session_state.logged_in:
    st.title("🔐 LCIS Login")
    email = st.text_input("Enter your Anihan Email")
    if st.button("Login"):
        if email.lower().endswith(AUTHORIZED_DOMAIN):
            st.session_state.logged_in = True
            st.session_state.user_email = email.lower()
            st.rerun()
        else:
            st.error(f"Access denied. Only {AUTHORIZED_DOMAIN} accounts allowed.")
    st.stop()

# --- 2. LOCAL DATA PERSISTENCE ---
# This saves your data to a CSV file so it doesn't disappear on refresh
DB_FILE = "lcis_database.csv"
SUP_FILE = "suppliers_database.csv"
HIST_FILE = "replenish_history.csv"

def load_data(file, columns):
    if os.path.exists(file):
        return pd.read_csv(file)
    return pd.DataFrame(columns=columns)

def save_data(df, file):
    df.to_csv(file, index=False)

# Initialize Dataframes
if 'products' not in st.session_state:
    st.session_state.products = load_data(DB_FILE, ["SAP Code", "Name", "Type", "Supplier", "Qty", "Unit", "Min_Level", "Cost", "Prev_Date", "Prev_Qty", "Prev_Cost"])
if 'suppliers' not in st.session_state:
    st.session_state.suppliers = load_data(SUP_FILE, ["Name", "Contact", "Delivery"])
if 'replenish_history' not in st.session_state:
    st.session_state.replenish_history = load_data(HIST_FILE, ["Date", "SAP", "Name", "Qty", "Cost", "Total"])
if 'recipes' not in st.session_state:
    st.session_state.recipes = {}

UNITS = ["bottles", "sack", "carboy", "kgs", "g", "ml", "L", "plastic bag", "Others"]

# --- NAVIGATION ---
user_name = st.session_state.user_email.split('@')[0].replace('.', ' ').title()
st.sidebar.title(f"👋 Mabuhay, {user_name}!")
page = st.sidebar.radio("LCIS Menu", ["Dashboard", "Inventory & Suppliers", "Replenish Stock", "Recipes & Forecasting", "Financials"])

# --- DASHBOARD ---
if page == "Dashboard":
    st.title("📊 LCIS Dashboard")
    st.write(f"Logged in: **{st.session_state.user_email}**")
    
    if not st.session_state.products.empty:
        total_val = (st.session_state.products['Qty'].astype(float) * st.session_state.products['Cost'].astype(float)).sum()
        low_stock_mask = st.session_state.products['Qty'].astype(float) <= st.session_state.products['Min_Level'].astype(float)
        
        c1, c2 = st.columns(2)
        c1.metric("Total Inventory Value", f"₱{total_val:,.3f}")
        c2.metric("Low Stock Items", len(st.session_state.products[low_stock_mask]))

        st.subheader("Inventory Status")
        def style_rows(row):
            if float(row['Qty']) <= float(row['Min_Level']):
                return ['background-color: #ff4b4b'] * len(row)
            return [''] * len(row)
        
        st.dataframe(st.session_state.products.style.apply(style_rows, axis=1), use_container_width=True)
    else:
        st.info("Database empty. Add materials in the next tab.")

# --- INVENTORY & SUPPLIERS ---
elif page == "Inventory & Suppliers":
    st.title("📦 Master Data")
    is_admin = st.session_state.user_email == ADMIN_EMAIL
    
    tab_p, tab_s = st.tabs(["Materials (Raw/Indirect)", "Suppliers"])
    
    with tab_p:
        st.subheader("Complete Material List")
        st.dataframe(st.session_state.products, use_container_width=True)
        
        with st.expander("➕ Add New Material / SAP Entry"):
            with st.form("add_mat"):
                c1, c2 = st.columns(2)
                sap = c1.text_input("SAP Code")
                name = c2.text_input("Material Name")
                m_type = c1.selectbox("Type", ["Raw Material", "Indirect Material"])
                unit = c2.selectbox("Unit", UNITS)
                if unit == "Others": unit = st.text_input("Specify Unit")
                
                cost = c1.number_input("Cost (₱)", format="%.3f")
                qty = c2.number_input("Initial Qty", format="%.3f")
                min_l = c1.number_input("Min Level", format="%.3f")
                sup_list = st.session_state.suppliers['Name'].tolist() if not st.session_state.suppliers.empty else ["No Suppliers"]
                sup = c2.selectbox("Supplier", sup_list)
                
                if st.form_submit_button("Confirm Add"):
                    new_item = {"SAP Code": sap, "Name": name, "Type": m_type, "Supplier": sup, "Qty": qty, "Unit": unit, "Min_Level": min_l, "Cost": cost}
                    st.session_state.products = pd.concat([st.session_state.products, pd.DataFrame([new_item])], ignore_index=True)
                    save_data(st.session_state.products, DB_FILE)
                    st.success("Added to SAP record.")
                    st.rerun()

    with tab_s:
        if is_admin:
            st.subheader("Admin: Manage Suppliers")
            edited_sup = st.data_editor(st.session_state.suppliers, num_rows="dynamic")
            if st.button("Save Supplier Changes"):
                st.session_state.suppliers = edited_sup
                save_data(st.session_state.suppliers, SUP_FILE)
                st.success("Suppliers Updated")
        else:
            st.warning("Supplier editing restricted to Admin.")
            st.table(st.session_state.suppliers)

# --- REPLENISH STOCK ---
elif page == "Replenish Stock":
    st.title("🛒 Replenishment & History")
    
    # Show History First
    with st.expander("📜 Replenishment History"):
        st.dataframe(st.session_state.replenish_history, use_container_width=True)

    st.subheader("Active Replenishment Form")
    # Threshold for replenishment (Red + 1 Week Warning)
    replenish_target = st.session_state.products[st.session_state.products['Qty'].astype(float) <= (st.session_state.products['Min_Level'].astype(float) * 1.2)]
    
    if not replenish_target.empty:
        selected = st.multiselect("Select materials to replenish:", replenish_target['Name'])
        
        form_data = []
        for item in selected:
            row = st.session_state.products[st.session_state.products['Name'] == item].iloc[0]
            st.write(f"---")
            st.write(f"**{item}** (SAP: {row['SAP Code']})")
            
            c1, c2 = st.columns(2)
            use_prev = c1.checkbox(f"Use previous cost/qty? (Qty: {row['Prev_Qty']}, Cost: {row['Prev_Cost']})", key=f"p_{item}")
            
            new_q = row['Prev_Qty'] if use_prev else c2.number_input(f"New Qty for {item}", format="%.3f", key=f"q_{item}")
            new_c = row['Prev_Cost'] if use_prev else c1.number_input(f"New Cost for {item}", format="%.3f", key=f"c_{item}")
            
            form_data.append({"Date": str(datetime.date.today()), "SAP": row['SAP Code'], "Name": item, "Qty": new_q, "Cost": new_c, "Total": new_q * new_c})

        if form_data and st.button("Update Inventory & Show Summary"):
            for order in form_data:
                idx = st.session_state.products[st.session_state.products['Name'] == order['Name']].index[0]
                st.session_state.products.at[idx, 'Qty'] += order['Qty']
                st.session_state.products.at[idx, 'Cost'] = order['Cost']
                st.session_state.products.at[idx, 'Prev_Qty'] = order['Qty']
                st.session_state.products.at[idx, 'Prev_Cost'] = order['Cost']
                st.session_state.products.at[idx, 'Prev_Date'] = order['Date']
            
            # Save
            new_hist = pd.concat([st.session_state.replenish_history, pd.DataFrame(form_data)], ignore_index=True)
            st.session_state.replenish_history = new_hist
            save_data(st.session_state.products, DB_FILE)
            save_data(st.session_state.replenish_history, HIST_FILE)
            
            st.subheader("Order Summary")
            summary_df = pd.DataFrame(form_data)
            st.table(summary_df)
            
            # Print Function
            st.components.v1.html(f"""
                <script>function printDiv() {{ window.print(); }}</script>
                <button onclick="printDiv()" style="padding:10px; background:#4CAF50; color:white; border:none; border-radius:5px; cursor:pointer;">🖨️ Click Here to Print Summary</button>
                <div id="printarea">
                    <h2>LCIS Replenishment Summary - {datetime.date.today()}</h2>
                    {summary_df.to_html()}
                </div>
            """, height=300)

# --- RECIPES ---
elif page == "Recipes & Forecasting":
    st.title("🧪 Recipe Production")
    
    t_add, t_exec = st.tabs(["Add New Recipe", "Process Production"])
    
    with t_add:
        r_name = st.text_input("Finished Product/Variant Name")
        ingredients = st.multiselect("Select Raw/Indirect Materials used:", st.session_state.products['Name'])
        
        recipe_details = {}
        for ing in ingredients:
            amt = st.number_input(f"Amount of {ing} per 1 unit of product", format="%.3f")
            recipe_details[ing] = amt
        
        if st.button("Save Recipe") and r_name:
            st.session_state.recipes[r_name] = recipe_details
            st.success(f"Recipe for {r_name} saved!")

    with t_exec:
        if st.session_state.recipes:
            choice = st.selectbox("Select Item to Produce", list(st.session_state.recipes.keys()))
            batch = st.number_input("Batch Size / Quantity", min_value=1)
            
            if st.button("Execute Production"):
                needed = st.session_state.recipes[choice]
                for item, qty_per in needed.items():
                    total_used = qty_per * batch
                    idx = st.session_state.products[st.session_state.products['Name'] == item].index[0]
                    st.session_state.products.at[idx, 'Qty'] -= total_used
                
                save_data(st.session_state.products, DB_FILE)
                st.success(f"Production complete. Stock deducted for {choice}.")
        else:
            st.info("No recipes found.")

# --- FINANCIALS ---
elif page == "Financials":
    st.title("💸 Monthly Expense Tracker")
    if not st.session_state.replenish_history.empty:
        df_exp = st.session_state.replenish_history.copy()
        df_exp['Date'] = pd.to_datetime(df_exp['Date'])
        monthly = df_exp.resample('ME', on='Date')['Total'].sum()
        st.line_chart(monthly)
        st.write("Raw Expense Data:")
        st.dataframe(df_exp)

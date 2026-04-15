import streamlit as st
import pandas as pd
import datetime

# --- APP CONFIG ---
st.set_page_config(page_title="LCIS Pro", layout="wide")

# --- 1. ACCESS CONTROL ---
AUTHORIZED_DOMAIN = "@yourcompany.com" # Change this to your actual domain
ADMIN_EMAIL = "admin@yourcompany.com"   # Change this to your admin email

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_email = ""

if not st.session_state.logged_in:
    st.title("🔐 LCIS Login")
    email = st.text_input("Enter Company Email")
    if st.button("Login"):
        if email.endswith(AUTHORIZED_DOMAIN):
            st.session_state.logged_in = True
            st.session_state.user_email = email
            st.rerun()
        else:
            st.error("Access denied. Please use a company email.")
    st.stop()

# --- 2. DATA INITIALIZATION ---
# Using 3 decimal places for Qty/Cost throughout
if 'products' not in st.session_state:
    st.session_state.products = pd.DataFrame(columns=[
        "SAP Code", "Name", "Type", "Supplier", "Qty", "Unit", "Min_Level", "Cost", 
        "Prev_Date", "Prev_Qty", "Prev_Cost"
    ])

if 'suppliers' not in st.session_state:
    st.session_state.suppliers = pd.DataFrame([
        {"Name": "Global Grain", "Contact": "0917-123-4567", "Delivery": "Monday"}
    ])

if 'replenish_history' not in st.session_state:
    st.session_state.replenish_history = pd.DataFrame()

if 'recipes' not in st.session_state:
    st.session_state.recipes = {} # Structure: {"Bread": {"Ingredients": {"Flour": 0.5}, "Output_Qty": 1}}

UNITS = ["bottles", "sack", "carboy", "kgs", "g", "ml", "L", "plastic bag", "Others"]

# --- NAVIGATION ---
st.sidebar.title(f"👋 Hello, {st.session_state.user_email.split('@')[0]}!")
page = st.sidebar.radio("LCIS Menu", ["Dashboard", "Inventory & Suppliers", "Replenish Stock", "Recipes & Forecasting", "Financials"])

# --- DASHBOARD ---
if page == "Dashboard":
    st.title(f"📊 LCIS Dashboard")
    st.write(f"Welcome back! Logged in as: **{st.session_state.user_email}**")
    
    # Summary Metrics
    if not st.session_state.products.empty:
        total_val = (st.session_state.products['Qty'] * st.session_state.products['Cost']).sum()
        low_count = len(st.session_state.products[st.session_state.products['Qty'] <= st.session_state.products['Min_Level']])
        
        c1, c2 = st.columns(2)
        c1.metric("Total Stock Value", f"₱{total_val:,.3f}")
        c2.metric("Low Stock Items", low_count)

        # Color Coding Table
        def style_stock(row):
            color = 'background-color: #ff4b4b' if row['Qty'] <= row['Min_Level'] else ''
            return [color] * len(row)
        
        st.subheader("Inventory List")
        st.dataframe(st.session_state.products.style.apply(style_stock, axis=1), use_container_width=True)
    else:
        st.info("No items in inventory yet.")

# --- INVENTORY & SUPPLIERS ---
elif page == "Inventory & Suppliers":
    st.title("📦 Master Data Management")
    is_admin = st.session_state.user_email == ADMIN_EMAIL
    
    t1, t2 = st.tabs(["All Products (Raw & Indirect)", "Supplier Directory"])
    
    with t1:
        with st.expander("➕ Add New Material (Raw/Indirect)"):
            with st.form("add_mat"):
                col_a, col_b = st.columns(2)
                sap = col_a.text_input("SAP Code")
                name = col_b.text_input("Material Name")
                m_type = col_a.selectbox("Material Type", ["Raw Material", "Indirect Material"])
                unit = col_b.selectbox("Unit of Measure", UNITS)
                if unit == "Others":
                    unit = st.text_input("Specify Other Unit")
                
                cost = col_a.number_input("Unit Cost (₱)", format="%.3f")
                qty = col_b.number_input("Initial Qty", format="%.3f")
                min_l = col_a.number_input("Min Level (Replenish trigger)", format="%.3f")
                sup = col_b.selectbox("Supplier", st.session_state.suppliers['Name'])
                
                if st.form_submit_button("Save to System"):
                    new_row = pd.DataFrame([{"SAP Code": sap, "Name": name, "Type": m_type, "Supplier": sup, "Qty": qty, "Unit": unit, "Min_Level": min_l, "Cost": cost}])
                    st.session_state.products = pd.concat([st.session_state.products, new_row], ignore_index=True)
                    st.rerun()

    with t2:
        if is_admin:
            st.subheader("Manage Suppliers (Admin Only)")
            # Edit/Delete logic would go here
            st.data_editor(st.session_state.suppliers, num_rows="dynamic", key="sup_editor")
        else:
            st.warning("Only Admins can edit supplier details.")
            st.table(st.session_state.suppliers)

# --- REPLENISH STOCK ---
elif page == "Replenish Stock":
    st.title("🛒 Replenishment Module")
    
    low_stock = st.session_state.products[st.session_state.products['Qty'] <= (st.session_state.products['Min_Level'] * 1.2)]
    
    if not low_stock.empty:
        selected = st.multiselect("Select Low Stock Items", low_stock['Name'])
        
        orders = []
        for item in selected:
            row = st.session_state.products[st.session_state.products['Name'] == item].iloc[0]
            st.divider()
            st.write(f"**Item:** {item} | **Current Qty:** {row['Qty']:.3f}")
            
            same_as_prev = st.checkbox(f"Same as previous purchase? (Qty: {row['Prev_Qty']}, Cost: {row['Prev_Cost']})", key=f"check_{item}")
            
            new_q = row['Prev_Qty'] if same_as_prev else st.number_input(f"New Qty for {item}", format="%.3f", key=f"q_{item}")
            new_c = row['Prev_Cost'] if same_as_prev else st.number_input(f"New Cost for {item}", format="%.3f", key=f"c_{item}")
            
            orders.append({"SAP": row['SAP Code'], "Name": item, "Qty": new_q, "Cost": new_c, "Total": new_q * new_c})

        if orders and st.button("Generate Summary & Update"):
            summary_df = pd.DataFrame(orders)
            st.session_state.last_summary = summary_df
            
            # Update Inventory Logic
            for o in orders:
                idx = st.session_state.products[st.session_state.products['Name'] == o['Name']].index[0]
                st.session_state.products.at[idx, 'Prev_Qty'] = o['Qty']
                st.session_state.products.at[idx, 'Prev_Cost'] = o['Cost']
                st.session_state.products.at[idx, 'Prev_Date'] = str(datetime.date.today())
                st.session_state.products.at[idx, 'Qty'] += o['Qty']
            
            # Log History
            st.session_state.replenish_history = pd.concat([st.session_state.replenish_history, summary_df], ignore_index=True)
            st.success("System updated!")

    # Print Section
    if 'last_summary' in st.session_state:
        st.subheader("Current Order Summary")
        st.table(st.session_state.last_summary)
        if st.button("🖨️ Print Summary"):
            st.write("Printing... (Your browser print dialog should open)")
            # JavaScript trick for printing
            st.components.v1.html(f"""
                <script>window.print();</script>
                <h3>Order Summary - {datetime.date.today()}</h3>
                {st.session_state.last_summary.to_html()}
            """, height=0)

# --- RECIPES ---
elif page == "Recipes & Forecasting":
    st.title("🧪 Recipes & Forecasting")
    
    with st.expander("➕ Create New Recipe"):
        r_name = st.text_input("Finished Product Name (e.g., Bread Variant A)")
        ingredients = st.multiselect("Select Ingredients", st.session_state.products['Name'])
        
        ing_map = {}
        for ing in ingredients:
            amt = st.number_input(f"Amount of {ing} needed for 1 unit", format="%.3f")
            ing_map[ing] = amt
            
        if st.button("Save Recipe"):
            st.session_state.recipes[r_name] = ing_map
            st.success("Recipe Saved")

    st.subheader("Process Production/Sale")
    if st.session_state.recipes:
        prod = st.selectbox("Select Recipe to Process", list(st.session_state.recipes.keys()))
        amount_to_make = st.number_input("Quantity to produce", min_value=1)
        
        if st.button("Confirm Production"):
            needed = st.session_state.recipes[prod]
            for item, qty_per in needed.items():
                total_deduct = qty_per * amount_to_make
                idx = st.session_state.products[st.session_state.products['Name'] == item].index[0]
                st.session_state.products.at[idx, 'Qty'] -= total_deduct
            st.success("Inventory updated based on recipe forecasting.")

# --- FINANCIALS ---
elif page == "Financials":
    st.title("💸 Monthly Expense Analysis")
    # Fix for the 'ME' issue
    if not st.session_state.replenish_history.empty:
        # Assuming Date column exists in history
        st.write("Monthly Expense Movement")
        # Logic to chart replenishment history over time
        st.dataframe(st.session_state.replenish_history)

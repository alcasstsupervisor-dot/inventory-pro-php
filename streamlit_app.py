import streamlit as st
import pandas as pd
import datetime
from datetime import timedelta

# --- APP CONFIG ---
st.set_page_config(page_title="Inventory Pro PHP", layout="wide")

# --- DATA INITIALIZATION ---
if 'products' not in st.session_state:
    st.session_state.products = pd.DataFrame([
        {"ID": 1, "Name": "Flour", "Supplier": "Global Grain", "Qty": 50, "Min_Level": 20, "Cost": 150.00, "Prev_Date": "2023-10-01", "Prev_Qty": 100, "Prev_Cost": 140.00},
        {"ID": 2, "Name": "Sugar", "Supplier": "SweetCo", "Qty": 15, "Min_Level": 30, "Cost": 80.00, "Prev_Date": "2023-09-15", "Prev_Qty": 50, "Prev_Cost": 75.00}
    ])

if 'suppliers' not in st.session_state:
    st.session_state.suppliers = pd.DataFrame([
        {"Name": "Global Grain", "Contact": "0917-123-4567", "Delivery_Day": "Monday"},
        {"Name": "SweetCo", "Contact": "0918-999-8888", "Delivery_Day": "Thursday"}
    ])

if 'expenses' not in st.session_state:
    st.session_state.expenses = pd.DataFrame([
        {"Date": "2023-09-01", "Amount": 5000.00},
        {"Date": "2023-10-01", "Amount": 3200.00}
    ])

if 'recipes' not in st.session_state:
    st.session_state.recipes = {"Bread": {"Flour": 0.5, "Sugar": 0.1}}

# --- HELPER FUNCTIONS ---
def get_status(row):
    # Logic: Red if below Min_Level, Yellow if within 20% of hitting Min_Level (1-week forecast proxy)
    if row['Qty'] <= row['Min_Level']:
        return "Critical (Red)"
    elif row['Qty'] <= (row['Min_Level'] * 1.2):
        return "Warning (Yellow)"
    return "Healthy"

# --- SIDEBAR NAVIGATION ---
page = st.sidebar.radio("Navigation", ["Dashboard", "Inventory & Suppliers", "Replenish Stock", "Recipes & Forecasting", "Financials"])

# --- DASHBOARD ---
if page == "Dashboard":
    st.title("📊 Business Overview")
    
    total_val = (st.session_state.products['Qty'] * st.session_state.products['Cost']).sum()
    total_exp = st.session_state.expenses['Amount'].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Stock Value", f"₱{total_val:,.2f}")
    col2.metric("Total Expenses", f"₱{total_exp:,.2f}")
    
    low_stock_df = st.session_state.products[st.session_state.products['Qty'] <= st.session_state.products['Min_Level']]
    col3.metric("Items to Replenish", len(low_stock_df))

    st.subheader("Inventory Status")
    # Styling for Red/Yellow
    def style_rows(row):
        status = get_status(row)
        if status == "Critical (Red)": return ['background-color: #ff4b4b'] * len(row)
        if status == "Warning (Yellow)": return ['background-color: #ffeb3b; color: black'] * len(row)
        return [''] * len(row)

    st.dataframe(st.session_state.products.style.apply(style_rows, axis=1), use_container_width=True)

# --- INVENTORY & SUPPLIERS ---
elif page == "Inventory & Suppliers":
    st.title("📦 Management")
    
    tab1, tab2 = st.tabs(["Products", "Suppliers"])
    
    with tab1:
        with st.expander("Add New Product"):
            with st.form("new_prod"):
                n_name = st.text_input("Product Name")
                n_sup = st.selectbox("Supplier", st.session_state.suppliers['Name'])
                n_qty = st.number_input("Current Qty", min_value=0.0)
                n_min = st.number_input("Min Level (Replenish trigger)", min_value=1.0)
                n_cost = st.number_input("Cost (₱)", min_value=0.0)
                if st.form_submit_button("Save Product"):
                    new_entry = {"ID": len(st.session_state.products)+1, "Name": n_name, "Supplier": n_sup, "Qty": n_qty, "Min_Level": n_min, "Cost": n_cost}
                    st.session_state.products = pd.concat([st.session_state.products, pd.DataFrame([new_entry])], ignore_index=True)
                    st.rerun()

    with tab2:
        st.table(st.session_state.suppliers)

# --- REPLENISH STOCK ---
elif page == "Replenish Stock":
    st.title("🛒 Replenish Products")
    
    # Filter for low or warning stock
    to_replenish = st.session_state.products[st.session_state.products['Qty'] <= (st.session_state.products['Min_Level'] * 1.2)]
    
    if to_replenish.empty:
        st.success("All stock levels are healthy!")
    else:
        selected_items = st.multiselect("Select products to order:", to_replenish['Name'])
        
        if selected_items:
            order_list = []
            with st.form("replenish_form"):
                for item_name in selected_items:
                    row = st.session_state.products[st.session_state.products['Name'] == item_name].iloc[0]
                    st.write(f"### {item_name} (Supplier: {row['Supplier']})")
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"Prev Date: {row['Prev_Date']}")
                    c2.write(f"Prev Qty: {row['Prev_Qty']}")
                    c3.write(f"Prev Cost: ₱{row['Prev_Cost']}")
                    
                    new_qty = st.number_input(f"New Order Qty for {item_name}", min_value=1.0, key=f"qty_{item_name}")
                    new_cost = st.number_input(f"New Cost for {item_name} (₱)", value=float(row['Cost']), key=f"cost_{item_name}")
                    order_list.append({"Name": item_name, "Qty": new_qty, "Cost": new_cost})
                
                if st.form_submit_button("Generate Order Summary"):
                    st.session_state.current_order = order_list
            
            if 'current_order' in st.session_state:
                st.subheader("Order Summary (Printable)")
                summary_df = pd.DataFrame(st.session_state.current_order)
                summary_df['Total'] = summary_df['Qty'] * summary_df['Cost']
                st.table(summary_df)
                st.write(f"**Grand Total: ₱{summary_df['Total'].sum():,.2f}**")
                if st.button("Confirm Purchase & Update Inventory"):
                    # Update inventory logic
                    for item in st.session_state.current_order:
                        idx = st.session_state.products[st.session_state.products['Name'] == item['Name']].index
                        st.session_state.products.at[idx[0], 'Qty'] += item['Qty']
                        st.session_state.products.at[idx[0], 'Cost'] = item['Cost']
                    
                    # Log Expense
                    new_exp = {"Date": str(datetime.date.today()), "Amount": summary_df['Total'].sum()}
                    st.session_state.expenses = pd.concat([st.session_state.expenses, pd.DataFrame([new_exp])], ignore_index=True)
                    st.success("Inventory updated!")

# --- RECIPES & FORECASTING ---
elif page == "Recipes & Forecasting":
    st.title("📈 Forecasting & Orders")
    
    st.subheader("Input Customer Order")
    order_item = st.selectbox("Select Recipe Sold", list(st.session_state.recipes.keys()))
    order_qty = st.number_input("Quantity Sold", min_value=1)
    
    if st.button("Process Sale"):
        ingredients = st.session_state.recipes[order_item]
        for ing, amt in ingredients.items():
            total_needed = amt * order_qty
            idx = st.session_state.products[st.session_state.products['Name'] == ing].index
            st.session_state.products.at[idx[0], 'Qty'] -= total_needed
        st.success(f"Processed {order_qty} {order_item}(s). Inventory deducted.")

# --- FINANCIALS ---
elif page == "Financials":
    st.title("💸 Expense Tracking")
    st.session_state.expenses['Date'] = pd.to_datetime(st.session_state.expenses['Date'])
    monthly_exp = st.session_state.expenses.set_index('Date').resample('M').sum()
    st.line_chart(monthly_exp)
    st.table(st.session_state.expenses)

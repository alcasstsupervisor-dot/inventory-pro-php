import streamlit as st
import pandas as pd
import datetime
import os

# --- 1. CONFIG & AUTH ---
st.set_page_config(page_title="LCIS - Verification System", layout="wide")
ADMINS = [
    "cecille.sulit@anihan.edu.ph", 
    "aileen.clutario@anihan.edu.ph", 
    "alc.purchasing@anihan.edu.ph", 
    "alc.asstsupervisor@anihan.edu.ph"
]
AUTHORIZED_DOMAIN = "@anihan.edu.ph"

# --- 2. DATA FILES ---
DB_FILE = "lcis_main_v7.csv"
PENDING_FILE = "pending_deliveries_v7.csv"
HIST_FILE = "change_log_v7.csv"
LOGIN_LOG_FILE = "login_history_v7.csv"

def load_data(file, columns):
    if os.path.exists(file): return pd.read_csv(file)
    return pd.DataFrame(columns=columns)

def save_data(df, file): df.to_csv(file, index=False)

# --- 3. LOGIN & SESSION ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_role = "Staff"

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

# Load Databases into Session
st.session_state.products = load_data(DB_FILE, ["SAP Code", "Name", "Type", "On hand Inventory", "Min_Level", "Cost"])
pending_df = load_data(PENDING_FILE, ["ID", "Date", "DR", "SAP", "Item", "Qty", "Status", "Staff", "Admin_Note"])

# --- 4. NAVIGATION ---
is_admin = st.session_state.user_role == "Admin"
if is_admin:
    menu = ["Dashboard", "Materials (Raw/Indirect)", "Replenish Stock", "Delivery", "Admin Panel"]
else:
    menu = ["Dashboard", "Materials (Raw/Indirect)", "Delivery"]
page = st.sidebar.radio("Navigation", menu)

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- 5. PAGE LOGIC ---

if page == "Dashboard":
    st.title("📊 Dashboard")
    # Show items that are "Pending" but were rejected/returned for correction
    corrections = pending_df[pending_df['Status'] == "Pending (Correction Needed)"]
    if not corrections.empty:
        st.error(f"⚠️ {len(corrections)} Deliveries were rejected by Admin and need correction.")
        st.dataframe(corrections)
    
    st.subheader("Current Inventory Status")
    st.dataframe(st.session_state.products, use_container_width=True)

elif page == "Delivery":
    st.title("🚚 Delivery Input")
    with st.form("staff_del", clear_on_submit=True):
        d_date = st.date_input("Date Received")
        dr_ref = st.text_input("DR #")
        search = st.text_input("Search SAP or Name").upper().strip()
        qty = st.number_input("Qty Received", format="%.3f")
        if st.form_submit_button("Submit for Verification"):
            new_id = len(pending_df) + 1
            new_entry = {
                "ID": new_id, "Date": d_date, "DR": dr_ref, "SAP": search, "Item": search, 
                "Qty": qty, "Status": "Pending", "Staff": st.session_state.display_name, "Admin_Note": ""
            }
            pending_df = pd.concat([pending_df, pd.DataFrame([new_entry])], ignore_index=True)
            save_data(pending_df, PENDING_FILE)
            st.success("Sent to Admin for approval.")

elif page == "Replenish Stock" and is_admin:
    st.title("🛒 Replenishment & Verification")
    
    # --- ADMIN NOTIFICATION ---
    to_verify = pending_df[pending_df['Status'].str.contains("Pending")]
    
    if not to_verify.empty:
        st.write("### 🔔 Delivery Verification Queue")
        for index, row in to_verify.iterrows():
            status_color = "🔴" if "Correction" in row['Status'] else "🔵"
            if st.button(f"{status_color} Review DR: {row['DR']} ({row['Item']})", key=f"btn_{row['ID']}"):
                st.session_state.review_id = row['ID']

    if 'review_id' in st.session_state:
        # Fetch the specific row to edit
        row_idx = pending_df[pending_df['ID'] == st.session_state.review_id].index[0]
        rev_item = pending_df.loc[row_idx]
        
        st.divider()
        st.write(f"### Reviewing Delivery: {rev_item['DR']}")
        
        # Admin can correct the info before confirming
        c1, c2 = st.columns(2)
        edit_sap = c1.text_input("Correct SAP Code", value=rev_item['SAP']).upper()
        edit_qty = c2.number_input("Correct Quantity", value=float(rev_item['Qty']), format="%.3f")
        admin_note = st.text_area("Notes for Staff (if rejecting)", value=rev_item['Admin_Note'])

        b1, b2, b3 = st.columns(3)
        if b1.button("✅ Confirm & Replenish"):
            # 1. Update Inventory
            match_idx = st.session_state.products[st.session_state.products['SAP Code'].str.upper() == edit_sap].index
            if not match_idx.empty:
                st.session_state.products.at[match_idx[0], 'On hand Inventory'] += edit_qty
                save_data(st.session_state.products, DB_FILE)
                # 2. Mark as Replenished
                pending_df.at[row_idx, 'Status'] = "Replenished"
                save_data(pending_df, PENDING_FILE)
                st.success("Inventory updated successfully!")
                del st.session_state.review_id
                st.rerun()
            else:
                st.error("SAP Code not found in master list. Add material first.")

        if b2.button("↩️ Send Back for Correction"):
            pending_df.at[row_idx, 'Status'] = "Pending (Correction Needed)"
            pending_df.at[row_idx, 'Admin_Note'] = admin_note
            save_data(pending_df, PENDING_FILE)
            st.info("Marked for correction. Remains in Pending.")
            del st.session_state.review_id
            st.rerun()
            
        if b3.button("Close Review"):
            del st.session_state.review_id
            st.rerun()

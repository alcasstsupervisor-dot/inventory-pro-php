import streamlit as st
import pandas as pd
import datetime
import os

# --- 1. CONFIG & STRICT AUTHENTICATION ---
st.set_page_config(page_title="LCIS - Anihan Pro", layout="wide")

ADMINS = [
    "cecille.sulit@anihan.edu.ph", 
    "aileen.clutario@anihan.edu.ph", 
    "alc.purchasing@anihan.edu.ph", 
    "alc.asstsupervisor@anihan.edu.ph"
]
AUTHORIZED_DOMAIN = "@anihan.edu.ph"

# --- 2. DATA PERSISTENCE ---
DB_FILE = "lcis_main_v11.csv"
PENDING_FILE = "pending_deliveries_v11.csv"
RECIPE_FILE = "recipes_v11.csv"
SUP_FILE = "suppliers_v11.csv"
HIST_FILE = "change_log_v11.csv"
LOGIN_LOG_FILE = "login_history_v11.csv"

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
            
            log_event(full_name, "LOGIN", f"Logged in as {st.session_state.user_role}")
            # Separate log for logins
            log_df = load_data(LOGIN_LOG_FILE, ["Timestamp", "Name", "Email", "Role"])
            new_log = pd.DataFrame([{"Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Name": full_name, "Email": email_input, "Role": st.session_state.user_role}])
            pd.concat([log_df, new_log], ignore_index=True).to_csv(LOGIN_LOG_FILE, index=False)
            st.rerun()
    st.stop()

# --- 4. DATA LOADING ---
st.session_state.products = load_data(DB_FILE, ["SAP Code", "Name", "Type", "Supplier", "On hand Inventory", "Unit", "Min_Level", "Cost"])
st.session_state.recipes = load_data(RECIPE_FILE, ["Recipe Name", "Ingredient", "Qty Per Unit"])
st.session_state.suppliers = load_data(SUP_FILE, ["Supplier Name", "Contact Person", "Contact Details"])
pending_df = load_data(PENDING_FILE, ["ID", "Date", "DR", "SAP", "Item", "Qty", "Status", "Staff", "Admin_Note"])

# --- 5. GREETING & SIDEBAR ---
now = datetime.datetime.now()
greeting = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"
is_admin = st.session_state.user_role == "Admin"

st.sidebar.title("🏢 Anihan LCIS")
st.sidebar.markdown(f"### {greeting},\n**{st.session_state.user_role} {st.session_state.display_name}**")
st.sidebar.divider()

if is_admin:
    menu = ["Dashboard", "Materials (Raw/Indirect)", "Replenish Stock", "Recipes & Forecasting", "Delivery", "Admin Panel"]
else:
    menu = ["Dashboard", "Materials (Raw/Indirect)", "Delivery"]

page = st.sidebar.radio("Navigation Menu", menu)

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- 6. PAGE LOGIC ---

if page == "Dashboard":
    st.title("📊 Dashboard")
    st.subheader(f"Status for {st.session_state.display_name}")
    
    # Alert for Staff if Admin rejected a delivery
    corrections = pending_df[(pending_df['Status'] == "Pending (Correction Needed)") & (pending_df['Staff'] == st.session_state.display_name)]
    if not corrections.empty:
        st.error(f"🚨 {st.session_state.display_name}, you have {len(corrections)} deliveries to correct!")
        st.dataframe(corrections[['DR', 'Item', 'Admin_Note']])

    st.write("### Current Inventory")
    st.dataframe(st.session_state.products, use_container_width=True)

elif page == "Materials (Raw/Indirect)":
    st.title("📦 Material & Supplier Management")
    t1, t2 = st.tabs(["Materials List", "Supplier Directory"])
    
    with t1:
        if is_admin:
            with st.expander("➕ Add New Material"):
                with st.form("new_mat"):
                    c1, c2 = st.columns(2)
                    sap = c1.text_input("SAP Code").upper()
                    name = c2.text_input("Name")
                    m_type = c1.selectbox("Type", ["Raw Material", "Indirect Material"])
                    sup = c2.selectbox("Supplier", st.session_state.suppliers["Supplier Name"].unique() if not st.session_state.suppliers.empty else ["No Suppliers"])
                    qty = c1.number_input("Beginning Stock", format="%.3f")
                    unit = c2.text_input("Unit")
                    min_l = c1.number_input("Min Level", format="%.3f")
                    cost = c2.number_input("Cost (₱)", format="%.3f")
                    if st.form_submit_button("Save Material"):
                        new_item = {"SAP Code": sap, "Name": name, "Type": m_type, "Supplier": sup, "On hand Inventory": qty, "Unit": unit, "Min_Level": min_l, "Cost": cost}
                        st.session_state.products = pd.concat([st.session_state.products, pd.DataFrame([new_item])], ignore_index=True)
                        save_data(st.session_state.products, DB_FILE)
                        log_event(st.session_state.display_name, "ADD_MAT", f"Added {name}")
                        st.rerun()
        st.dataframe(st.session_state.products, use_container_width=True)

    with t2:
        if is_admin:
            with st.expander("➕ Add New Supplier"):
                with st.form("new_sup"):
                    s_name = st.text_input("Supplier Name")
                    s_cont = st.text_input("Contact Person")
                    s_det = st.text_input("Phone/Email")
                    if st.form_submit_button("Save Supplier"):
                        new_s = {"Supplier Name": s_name, "Contact Person": s_cont, "Contact Details": s_det}
                        st.session_state.suppliers = pd.concat([st.session_state.suppliers, pd.DataFrame([new_s])], ignore_index=True)
                        save_data(st.session_state.suppliers, SUP_FILE)
                        st.rerun()
        st.dataframe(st.session_state.suppliers, use_container_width=True)

elif page == "Delivery":
    st.title("🚚 Delivery Input")
    with st.form("delivery_form", clear_on_submit=True):
        d_date = st.date_input("Date")
        dr = st.text_input("DR #")
        search = st.text_input("Search SAP/Name").upper().strip()
        qty = st.number_input("Qty Received", format="%.3f")
        if st.form_submit_button("Submit"):
            new_id = len(pending_df) + 1
            new_row = {"ID": new_id, "Date": d_date, "DR": dr, "SAP": search, "Item": search, "Qty": qty, "Status": "Pending", "Staff": st.session_state.display_name, "Admin_Note": ""}
            pending_df = pd.concat([pending_df, pd.DataFrame([new_row])], ignore_index=True)
            save_data(pending_df, PENDING_FILE)
            st.success("Sent to Admins for approval.")

elif page == "Replenish Stock" and is_admin:
    st.title("🛒 Verification Queue")
    to_verify = pending_df[pending_df['Status'].str.contains("Pending")]
    if not to_verify.empty:
        for i, r in to_verify.iterrows():
            if st.button(f"Review DR: {r['DR']} from {r['Staff']}", key=f"rev_{r['ID']}"):
                st.session_state.review_id = r['ID']

    if 'review_id' in st.session_state:
        rid = st.session_state.review_id
        row_idx = pending_df[pending_df['ID'] == rid].index[0]
        rev_row = pending_df.loc[row_idx]
        
        st.info(f"Reviewing {rev_row['Item']}")
        correct_sap = st.text_input("Match SAP", value=rev_row['SAP']).upper()
        correct_qty = st.number_input("Final Qty", value=float(rev_row['Qty']), format="%.3f")
        note = st.text_area("Notes for Staff")

        col1, col2 = st.columns(2)
        if col1.button("✅ Confirm"):
            match_idx = st.session_state.products[st.session_state.products['SAP Code'] == correct_sap].index
            if not match_idx.empty:
                st.session_state.products.at[match_idx[0], 'On hand Inventory'] += correct_qty
                save_data(st.session_state.products, DB_FILE)
                pending_df.at[row_idx, 'Status'] = "Replenished"
                save_data(pending_df, PENDING_FILE)
                st.success("Inventory Updated!")
                del st.session_state.review_id
                st.rerun()
        if col2.button("↩️ Reject"):
            pending_df.at[row_idx, 'Status'] = "Pending (Correction Needed)"
            pending_df.at[row_idx, 'Admin_Note'] = note
            save_data(pending_df, PENDING_FILE)
            del st.session_state.review_id
            st.rerun()

elif page == "Admin Panel" and is_admin:
    st.title("🛡️ Admin Panel")
    t1, t2 = st.tabs(["Login History", "System Changes"])
    with t1: st.dataframe(load_data(LOGIN_LOG_FILE, ["Timestamp", "Name", "Email", "Role"]))
    with t2: st.dataframe(load_data(HIST_FILE, ["Timestamp", "User", "Action", "Details"]))

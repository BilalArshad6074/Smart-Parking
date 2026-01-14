import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import pandas as pd
import random
import json

# 1. SECURE DATABASE CONNECTION
if not firebase_admin._apps:
    # This reads the key from Streamlit's internal "Secrets" settings
    if "firebase" in st.secrets:
        key_dict = json.loads(st.secrets["firebase"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    else:
        # Fallback for local testing
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)

db = firestore.client()

# --- THE REST OF YOUR WORKING CODE ---
st.set_page_config(page_title="SPMS Pro Dashboard", layout="wide")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
    .status-card { padding: 20px; border-radius: 10px; color: white; text-align: center; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); margin-bottom: 10px; }
    .receipt-style {
        background-color: #ffffff; color: #333; padding: 20px;
        border-left: 10px solid #2ecc71; border-radius: 5px;
        font-family: 'Courier New', Courier, monospace;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.2); margin-top: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

def get_data():
    slots = db.collection('parking_slots').order_by("spot_number").stream()
    return [{"id": slot.id, **slot.to_dict()} for slot in slots]

def add_new_slot(number, p_type):
    doc_id = f"slot_{number}"
    db.collection('parking_slots').document(doc_id).set({
        "spot_number": number, "type": p_type, "status": "available", "entry_time": None
    })

def log_transaction(slot_no, amount, tx_id):
    db.collection('audit_log').add({
        "slot": slot_no, "amount": amount, "tx_id": tx_id, "timestamp": datetime.now()
    })

data = get_data()
total = len(data)
occ = sum(1 for s in data if s['status'] == 'occupied')
current_rate = 15.0 + (5.0 if (total > 0 and occ/total > 0.7) else 0.0)

st.sidebar.header("🏗️ Facility Admin")
tab_add, tab_edit, tab_del = st.sidebar.tabs(["Add", "Edit", "Delete"])

with tab_add:
    n_no = st.number_input("Slot #", min_value=1, step=1, key="add_n")
    n_type = st.selectbox("Type", ["Car", "EV", "Handicapped"], key="add_t")
    if st.button("Add New Slot"):
        add_new_slot(n_no, n_type); st.rerun()

with tab_edit:
    slot_ids = [s['id'] for s in data]
    if slot_ids:
        target_s = st.selectbox("Select Slot", slot_ids, key="edit_s")
        new_t = st.selectbox("New Category", ["Car", "EV", "Handicapped"], key="edit_t")
        if st.button("Update Slot"):
            db.collection('parking_slots').document(target_s).update({"type": new_t})
            st.rerun()

with tab_del:
    if slot_ids:
        d_slot = st.selectbox("Select to Delete", slot_ids, key="del_s")
        if st.button("🗑️ Permanently Delete"):
            db.collection('parking_slots').document(d_slot).delete(); st.rerun()

st.title("🏙️ SPMS: Smart City Command Center")
st.caption("Developed by Bilal Arshad & Faraz Ahsan | Group 4650")

c1, c2, c3 = st.columns(3)
c1.metric("Total Slots", total)
c2.metric("Occupancy", f"{(occ/total)*100 if total>0 else 0:.1f}%")
c3.metric("Current Rate", f"${current_rate}", delta="SURGE" if current_rate > 15 else "NORMAL")

st.write("### Live Floor Map")
grid = st.columns(4)
for i, slot in enumerate(data):
    with grid[i % 4]:
        is_occ = slot['status'] == 'occupied'
        color = "#e74c3c" if is_occ else "#2ecc71"
        st.markdown(f'<div class="status-card" style="background-color: {color};"><small>{slot["type"]}</small><h3>P-{slot["spot_number"]}</h3><p>{slot["status"].upper()}</p></div>', unsafe_allow_html=True)
        
        if not is_occ:
            if st.button(f"Check-In P-{slot['spot_number']}", key=f"in_{slot['id']}"):
                db.collection('parking_slots').document(slot['id']).update({"status": "occupied", "entry_time": datetime.now().strftime("%H:%M:%S")})
                st.rerun()
        else:
            if st.button(f"Pay & Exit P-{slot['spot_number']}", key=f"out_{slot['id']}"):
                tx_id = f"TXN-{random.randint(10000, 99999)}"
                entry_t = slot.get('entry_time', "N/A")
                log_transaction(slot['spot_number'], current_rate, tx_id)
                db.collection('parking_slots').document(slot['id']).update({"status": "available", "entry_time": None})
                st.balloons()
                st.markdown(f'<div class="receipt-style"><h4>PARKING RECEIPT</h4><p>ID: {tx_id}</p><p>Slot: P-{slot["spot_number"]}</p><p>Entry: {entry_t}</p><hr><h3>PAID: ${current_rate}</h3></div>', unsafe_allow_html=True)

st.markdown("---")
st.write("### 📑 Payment Audit Trail")
logs = db.collection('audit_log').order_by("timestamp", direction=firestore.Query.DESCENDING).limit(5).stream()
log_data = [{"Time": l.to_dict()['timestamp'], "Slot": l.to_dict()['slot'], "TX_ID": l.to_dict()['tx_id'], "Amount": f"${l.to_dict()['amount']}"} for l in logs]
if log_data: st.table(pd.DataFrame(log_data))
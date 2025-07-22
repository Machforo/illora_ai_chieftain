import streamlit as st

st.title("🛎️ Room Booking")

show_payment_form = st.checkbox("💰 Initiate Payment")

if show_payment_form:
    with st.form("booking_form"):
        room_type = st.selectbox("🏨 Select Room Type", ["Deluxe", "Executive", "Family"])
        nights = st.number_input("🕒 Number of nights", min_value=1, step=1)
        payment_method = st.radio("💳 Payment Method", ["Online", "Cash on Arrival"])
        
        submitted = st.form_submit_button("✅ Confirm and Pay")

    if submitted:
        st.success(f"You selected {room_type} for {nights} nights via {payment_method}")

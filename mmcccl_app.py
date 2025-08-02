# -----------------------
# Tab 1: Inventory Update
# -----------------------
with tab1:
    st.header("📊 Inventory Level & Transaction Log")

    search_cat = st.text_input("🔍 Search Catalog Number").strip()
    filtered_cat_nos = sorted(df[df['cat_no.'].str.contains(search_cat, case=False, na=False)]['cat_no.'].unique())
    cat_selected = st.selectbox("Select Catalog Number", filtered_cat_nos)

    item_data = df[df['cat_no.'] == cat_selected].copy()
    item_name = item_data['item'].values[0]
    current_qty = item_data['quantity'].values[0]

    st.metric(label=f"{item_name} (Cat#: {cat_selected})", value=current_qty)

    col1, col2 = st.columns(2)
    with col1:
        action_type = st.selectbox("Action", ["Add", "Remove"])
    with col2:
        qty_change = st.number_input("Quantity", min_value=1, step=1)

    user_initials = st.text_input("Your Initials", max_chars=5).upper()

    if st.button("Submit Update"):
        if not user_initials:
            st.error("Please enter your initials before submitting.")
        else:
            idx = item_data.index[0]
            timestamp = datetime.now()

            if action_type == "Add":
                df.at[idx, 'quantity'] += qty_change
            else:
                if qty_change > df.at[idx, 'quantity']:
                    st.error("❌ Not enough items on hand to remove.")
                    st.stop()
                else:
                    df.at[idx, 'quantity'] -= qty_change

            # Log transaction
            df_log.loc[len(df_log)] = {
                'timestamp': timestamp,
                'cat_no.': cat_selected,
                'item': item_name,
                'action': action_type.lower(),
                'quantity': qty_change,
                'initials': user_initials
            }

            st.success(f"✅ {action_type}ed {qty_change} unit(s) of {item_name}. New total: {df.at[idx, 'quantity']}")

    # Show log history for selected item
    st.subheader(f"📄 Transaction Log for {item_name}")
    history = df_log[df_log['cat_no.'] == cat_selected].sort_values(by='timestamp', ascending=False)
    st.dataframe(history, use_container_width=True)

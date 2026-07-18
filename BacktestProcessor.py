import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import timedelta
from io import BytesIO

st.set_page_config(page_title="SMC Swing Matrix Analyzer", layout="wide")
st.title("SMC Swing Matrix Analyzer v2.2")

uploaded = st.file_uploader("1. Upload Backtest CSV", type="csv")

if uploaded:
    try:
        df = pd.read_csv(uploaded)
        df.columns = df.columns.str.lower()
        df['date'] = pd.to_datetime(df['date'], dayfirst=True)

        def get_sorted_dates(group):
            sorted_dt = sorted(group.unique())
            return [dt.strftime('%Y-%m-%d') for dt in sorted_dt]

        dates_per_symbol = df.groupby('symbol')['date'].apply(get_sorted_dates).reset_index()
        dates_expanded = pd.DataFrame(dates_per_symbol['date'].tolist(), index=dates_per_symbol['symbol'])
        dates_expanded.columns = [f'Date {i+1}' for i in range(dates_expanded.shape[1])]
        dates_expanded = dates_expanded.reset_index()
        meta_df = df.groupby('symbol')[['marketcapname', 'sector']].first().reset_index()
        master_df = pd.merge(meta_df, dates_expanded, on='symbol')

        st.session_state['master_df'] = master_df
        st.success(f"Loaded {len(master_df)} stocks from CSV.")
    except Exception as e:
        st.error(f"Load failed: {e}")

if 'master_df' in st.session_state:
    master_df = st.session_state['master_df']

    col1, col2 = st.columns(2)
    with col1:
        cap_options = ["All"] + sorted(master_df['marketcapname'].dropna().unique().tolist())
        cap_choice = st.selectbox("Market Cap", cap_options)
    with col2:
        sector_options = ["All"] + sorted(master_df['sector'].dropna().unique().tolist())
        sector_choice = st.selectbox("Sector", sector_options)

    filtered_df = master_df.copy()
    if cap_choice != "All":
        filtered_df = filtered_df[filtered_df['marketcapname'] == cap_choice]
    if sector_choice != "All":
        filtered_df = filtered_df[filtered_df['sector'] == sector_choice]

    filtered_df = filtered_df.copy()
    filtered_df.insert(0, 'S.No.', range(1, len(filtered_df) + 1))

    st.dataframe(filtered_df, use_container_width=True, height=400)

    buf = BytesIO()
    filtered_df.to_excel(buf, index=False, engine='openpyxl')
    st.download_button("2. Export to Excel", data=buf.getvalue(), file_name="backtest.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown("---")
    st.subheader("Performance Analysis")

    stock_list = filtered_df['symbol'].tolist()
    symbol = st.selectbox("Select Stock", stock_list)

    if symbol:
        row = master_df[master_df['symbol'] == symbol].iloc[0]
        date_cols = [c for c in master_df.columns if c.startswith('Date ')]
        available_dates = [str(row[c]) for c in date_cols if pd.notnull(row[c]) and str(row[c]) != '']

        if available_dates:
            selected_date = st.selectbox("Select Entry Date", available_dates)

            curr_idx = available_dates.index(selected_date)
            next_date_val = available_dates[curr_idx + 1] if curr_idx + 1 < len(available_dates) else None

            ticker = symbol if "." in symbol else f"{symbol}.NS"
            try:
                start_dt = pd.to_datetime(selected_date)
                end_dt_fetch = start_dt + timedelta(days=250)
                data = yf.download(ticker, start=start_dt, end=end_dt_fetch, progress=False)

                if not data.empty:
                    entry_price = data['Close'].iloc[0].item()
                    entry_dt_actual = pd.to_datetime(data.index[0]).strftime('%Y-%m-%d')

                    results = []
                    results.append({"Period": "ENTRY", "Date": entry_dt_actual, "Price": f"{entry_price:.2f}", "Return %": "0.00%"})

                    if next_date_val:
                        end_window = pd.to_datetime(next_date_val)
                        window_data = data[data.index < end_window]
                        window_label = f"Highest before {next_date_val}"
                    else:
                        window_data = data
                        window_label = "Highest (Till Date)"

                    if not window_data.empty:
                        max_high = window_data['High'].max().item()
                        max_date_ts = window_data['High'].idxmax()
                        if isinstance(max_date_ts, pd.Series):
                            max_date_ts = max_date_ts.iloc[0]
                        max_date = pd.to_datetime(max_date_ts).strftime('%Y-%m-%d')
                        high_ret = ((max_high - entry_price) / entry_price) * 100
                        results.append({"Period": window_label, "Date": max_date, "Price": f"{max_high:.2f}", "Return %": f"{high_ret:.2f}%"})
                    else:
                        results.append({"Period": "Highest Price", "Date": "N/A", "Price": "N/A", "Return %": "No High Found"})

                    for m in [1, 2, 3, 4, 5, 6]:
                        idx = m * 21
                        if idx < len(data):
                            price_then = data['Close'].iloc[idx].item()
                            date_then_ts = data.index[idx]
                            if isinstance(date_then_ts, pd.Series):
                                date_then_ts = date_then_ts.iloc[0]
                            date_then = pd.to_datetime(date_then_ts).strftime('%Y-%m-%d')
                            pct = ((price_then - entry_price) / entry_price) * 100
                            results.append({"Period": f"{m} Month", "Date": date_then, "Price": f"{price_then:.2f}", "Return %": f"{pct:.2f}%"})

                    results_df = pd.DataFrame(results)

                    def color_return(val):
                        if isinstance(val, str) and '%' in val:
                            try:
                                num = float(val.replace('%', ''))
                                if num >= 0:
                                    return 'color: green'
                                else:
                                    return 'color: red'
                            except:
                                pass
                        return ''

                    styled = results_df.style.map(color_return, subset=['Return %'])
                    st.dataframe(styled, use_container_width=True, hide_index=True)
                else:
                    st.warning("No data found on Yahoo Finance for this ticker/date.")
            except Exception as e:
                st.error(f"Error fetching data: {e}")
        else:
            st.info("No dates available for this stock.")

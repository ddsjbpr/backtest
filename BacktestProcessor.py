import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import timedelta
import io

# --- Page Configuration ---
st.set_page_config(page_title="SMC Swing Matrix Analyzer", layout="wide")
st.title("📊 SMC Swing Matrix Analyzer v2.2")

# --- Logic Functions ---

def process_data(df):
    """Processes the uploaded CSV and expands dates into columns."""
    df['date'] = pd.to_datetime(df['date'], dayfirst=True)
    
    def get_sorted_dates(group):
        sorted_dt = sorted(group.unique())
        return [dt.strftime('%Y-%m-%d') for dt in sorted_dt]
    
    dates_per_symbol = df.groupby('symbol')['date'].apply(get_sorted_dates).reset_index()
    dates_expanded = pd.DataFrame(dates_per_symbol['date'].tolist(), index=dates_per_symbol['symbol'])
    dates_expanded.columns = [f'Date {i+1}' for i in range(dates_expanded.shape[1])]
    dates_expanded = dates_expanded.reset_index()
    
    meta_df = df.groupby('symbol')[['marketcapname', 'sector']].first().reset_index()
    return pd.merge(meta_df, dates_expanded, on='symbol')

def get_stock_analysis(symbol, selected_date, all_dates):
    """Fetches yfinance data and calculates performance returns."""
    ticker = symbol if "." in symbol else f"{symbol}.NS"
    try:
        curr_idx = all_dates.index(selected_date)
        next_date_val = all_dates[curr_idx + 1] if curr_idx + 1 < len(all_dates) else None
        
        start_dt = pd.to_datetime(selected_date)
        end_dt_fetch = start_dt + timedelta(days=250) 
        data = yf.download(ticker, start=start_dt, end=end_dt_fetch, progress=False)
        
        if data.empty:
            return None

        # Helper to ensure we get a single scalar value, not a Series/DataFrame
        def get_scalar(val):
            if hasattr(val, "iloc"):
                return val.iloc[0]
            return val

        # Handle potential Multi-Index columns in newer yfinance
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        entry_price = float(get_scalar(data['Close'].iloc[0]))
        entry_dt_actual = pd.to_datetime(get_scalar(data.index[0])).strftime('%Y-%m-%d')
        
        results = []
        results.append({
            "Period": "ENTRY", 
            "Date": entry_dt_actual, 
            "Price": f"{entry_price:.2f}", 
            "Return %": "0.00%"
        })

        # --- Max High Logic ---
        if next_date_val:
            end_window = pd.to_datetime(next_date_val)
            window_data = data[data.index < end_window]
            window_label = f"Highest before {next_date_val}"
        else:
            window_data = data
            window_label = "Highest (Till Date)"

        if not window_data.empty:
            max_high = float(get_scalar(window_data['High'].max()))
            max_date_ts = window_data['High'].idxmax()
            max_date = pd.to_datetime(get_scalar(max_date_ts)).strftime('%Y-%m-%d')
            high_ret = ((max_high - entry_price) / entry_price) * 100
            results.append({
                "Period": window_label, 
                "Date": max_date, 
                "Price": f"{max_high:.2f}", 
                "Return %": f"{high_ret:.2f}%"
            })

        # --- Monthly Checkpoints ---
        for m in [1, 2, 3, 4, 5, 6]:
            idx = m * 21
            if idx < len(data):
                price_then = float(get_scalar(data['Close'].iloc[idx]))
                date_then = pd.to_datetime(get_scalar(data.index[idx])).strftime('%Y-%m-%d')
                pct = ((price_then - entry_price) / entry_price) * 100
                results.append({
                    "Period": f"{m} Month", 
                    "Date": date_then, 
                    "Price": f"{price_then:.2f}", 
                    "Return %": f"{pct:.2f}%"
                })
        
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Error fetching data for {symbol}: {e}")
        return None

# --- Sidebar: File Upload & Filters ---
st.sidebar.header("Settings")
uploaded_file = st.sidebar.file_uploader("1. Load Backtest CSV", type="csv")

if uploaded_file:
    # Use session state to persist data across re-runs
    if 'master_df' not in st.session_state:
        raw_df = pd.read_csv(uploaded_file)
        st.session_state.master_df = process_data(raw_df)

    master_df = st.session_state.master_df

    # Filter Options
    caps = ["All"] + sorted(master_df['marketcapname'].unique().tolist())
    sectors = ["All"] + sorted(master_df['sector'].unique().tolist())
    
    selected_cap = st.sidebar.selectbox("Market Cap Filter", caps)
    selected_sector = st.sidebar.selectbox("Sector Filter", sectors)

    # Apply Filtering
    filtered_df = master_df.copy()
    if selected_cap != "All":
        filtered_df = filtered_df[filtered_df['marketcapname'] == selected_cap]
    if selected_sector != "All":
        filtered_df = filtered_df[filtered_df['sector'] == selected_sector]

    # --- Main UI Layout ---
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Backtest Data Table")
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        
        # Excel Export
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            filtered_df.to_excel(writer, index=False, sheet_name='Backtest')
        
        st.download_button(
            label="📥 Export to Excel",
            data=buffer,
            file_name="backtest_analysis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    with col2:
        st.subheader("Performance Analysis")
        symbol_list = filtered_df['symbol'].unique()
        symbol_to_analyze = st.selectbox("Pick a Stock", symbol_list)
        
        if symbol_to_analyze:
            row_data = filtered_df[filtered_df['symbol'] == symbol_to_analyze].iloc[0]
            # Identify columns containing dates
            date_cols = [c for c in filtered_df.columns if c.startswith("Date ") and pd.notnull(row_data[c])]
            available_dates = [row_data[c] for c in date_cols]
            
            selected_entry_date = st.selectbox("Pick Entry Date", available_dates)
            
            if st.button("Calculate Returns"):
                with st.spinner(f'Fetching {symbol_to_analyze} data...'):
                    analysis_res = get_stock_analysis(symbol_to_analyze, selected_entry_date, available_dates)
                    if analysis_res is not None:
                        # Displaying results as a table
                        st.table(analysis_res)
else:
    st.info("👋 Welcome! Please upload your Backtest CSV file in the sidebar to begin.")
    

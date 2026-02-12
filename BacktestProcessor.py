import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import yfinance as yf
from datetime import timedelta

class BacktestApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SMC Swing Matrix Analyzer v2.2")
        self.root.geometry("1200x650")
        
        self.master_df = None
        self.filtered_df = None

        # --- UI Layout ---
        top_frame = tk.Frame(self.root, pady=10, bg="#f0f0f0")
        top_frame.pack(side=tk.TOP, fill=tk.X)

        tk.Button(top_frame, text="1. Load Backtest CSV", command=self.load_data, bg="#2196F3", fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=10)
        
        tk.Label(top_frame, text="Market Cap:", bg="#f0f0f0").pack(side=tk.LEFT, padx=(20, 5))
        self.cap_filter = ttk.Combobox(top_frame, values=["All"], state="readonly", width=15)
        self.cap_filter.set("All")
        self.cap_filter.pack(side=tk.LEFT)
        self.cap_filter.bind("<<ComboboxSelected>>", self.apply_filter)

        tk.Label(top_frame, text="Sector:", bg="#f0f0f0").pack(side=tk.LEFT, padx=(20, 5))
        self.sector_filter = ttk.Combobox(top_frame, values=["All"], state="readonly", width=25)
        self.sector_filter.set("All")
        self.sector_filter.pack(side=tk.LEFT)
        self.sector_filter.bind("<<ComboboxSelected>>", self.apply_filter)

        tk.Button(top_frame, text="2. Export to Excel", command=self.export_excel, bg="#4CAF50", fg="white", font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=10)

        # --- Table (Treeview) ---
        self.table_frame = tk.Frame(self.root)
        self.table_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        self.tree = ttk.Treeview(self.table_frame, show="headings")
        self.tree.bind("<Double-1>", self.on_item_double_click) 
        
        vsb = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        self.table_frame.grid_columnconfigure(0, weight=1)
        self.table_frame.grid_rowconfigure(0, weight=1)

    def load_data(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not file_path: return
        try:
            df = pd.read_csv(file_path)
            df['date'] = pd.to_datetime(df['date'], dayfirst=True)
            def get_sorted_dates(group):
                sorted_dt = sorted(group.unique())
                return [dt.strftime('%Y-%m-%d') for dt in sorted_dt]
            dates_per_symbol = df.groupby('symbol')['date'].apply(get_sorted_dates).reset_index()
            dates_expanded = pd.DataFrame(dates_per_symbol['date'].tolist(), index=dates_per_symbol['symbol'])
            dates_expanded.columns = [f'Date {i+1}' for i in range(dates_expanded.shape[1])]
            dates_expanded = dates_expanded.reset_index()
            meta_df = df.groupby('symbol')[['marketcapname', 'sector']].first().reset_index()
            self.master_df = pd.merge(meta_df, dates_expanded, on='symbol')
            self.cap_filter['values'] = ["All"] + sorted(self.master_df['marketcapname'].unique().tolist())
            self.sector_filter['values'] = ["All"] + sorted(self.master_df['sector'].unique().tolist())
            self.apply_filter()
            messagebox.showinfo("Success", "Loaded. Double-click to see performance & Max High.")
        except Exception as e:
            messagebox.showerror("Error", f"Load failed: {e}")

    def apply_filter(self, event=None):
        if self.master_df is None: return
        cap_choice = self.cap_filter.get()
        sector_choice = self.sector_filter.get()
        temp_df = self.master_df.copy()
        if cap_choice != "All": temp_df = temp_df[temp_df['marketcapname'] == cap_choice]
        if sector_choice != "All": temp_df = temp_df[temp_df['sector'] == sector_choice]
        self.filtered_df = temp_df.copy()
        self.filtered_df.insert(0, 'S.No.', range(1, len(self.filtered_df) + 1))
        self.update_table(self.filtered_df)

    def update_table(self, display_df):
        self.tree.delete(*self.tree.get_children())
        cols = list(display_df.columns)
        self.tree["columns"] = cols
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=110, anchor='center')
        for _, row in display_df.iterrows():
            vals = [str(v) if pd.notnull(v) else "" for v in row]
            self.tree.insert("", "end", values=vals)

    def on_item_double_click(self, event):
        item_id = self.tree.selection()[0]
        row_values = self.tree.item(item_id, "values")
        symbol = row_values[1]
        available_dates = [d for d in row_values[4:] if d and d != "None" and d != ""]
        if available_dates:
            self.open_analysis_window(symbol, available_dates)

    def open_analysis_window(self, symbol, dates):
        win = tk.Toplevel(self.root)
        win.title(f"SMC Performance: {symbol}")
        win.geometry("600x500")

        header_frame = tk.Frame(win, pady=10)
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text=f"Stock: {symbol}", font=("Arial", 11, "bold")).pack()
        tk.Label(header_frame, text="Select Entry Date:").pack(side=tk.LEFT, padx=10)
        
        date_var = tk.StringVar()
        date_dropdown = ttk.Combobox(header_frame, textvariable=date_var, values=dates, state="readonly")
        date_dropdown.pack(side=tk.LEFT, padx=5)
        date_dropdown.set(dates[0])

        cols = ("Period", "Date", "Price", "Return %")
        res_tree = ttk.Treeview(win, columns=cols, show="headings", height=12)
        for col in cols:
            res_tree.heading(col, text=col)
            res_tree.column(col, width=120, anchor="center")
        res_tree.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        def calculate_returns(*args):
            res_tree.delete(*res_tree.get_children())
            selected_date = date_var.get()
            
            try:
                curr_idx = dates.index(selected_date)
                next_date_val = dates[curr_idx + 1] if curr_idx + 1 < len(dates) else None
            except:
                next_date_val = None

            ticker = symbol if "." in symbol else f"{symbol}.NS"
            try:
                start_dt = pd.to_datetime(selected_date)
                end_dt_fetch = start_dt + timedelta(days=250) 
                data = yf.download(ticker, start=start_dt, end=end_dt_fetch, progress=False)
                
                if data.empty: return

                entry_price = data['Close'].iloc[0].item()
                # FIX 1: Use .index[0] and ensure it's treated as a single value
                entry_dt_actual = pd.to_datetime(data.index[0]).strftime('%Y-%m-%d')
                res_tree.insert("", "end", values=("ENTRY", entry_dt_actual, f"{entry_price:.2f}", "0.00%"), tags=('bold',))

                if next_date_val:
                    end_window = pd.to_datetime(next_date_val)
                    window_data = data[data.index < end_window]
                    window_label = f"Highest before {next_date_val}"
                else:
                    window_data = data
                    window_label = "Highest (Till Date)"

                if not window_data.empty:
                    max_high = window_data['High'].max().item()
                    # FIX 2: Get the timestamp from the IDXMASK correctly
                    max_date_ts = window_data['High'].idxmax()
                    if isinstance(max_date_ts, pd.Series): max_date_ts = max_date_ts.iloc[0]
                    max_date = pd.to_datetime(max_date_ts).strftime('%Y-%m-%d')
                    
                    high_ret = ((max_high - entry_price) / entry_price) * 100
                    res_tree.insert("", "end", values=(window_label, max_date, f"{max_high:.2f}", f"{high_ret:.2f}%"), tags=('high',))
                else:
                    res_tree.insert("", "end", values=("Highest Price", "N/A", "N/A", "No High Found"))

                res_tree.insert("", "end", values=("---", "---", "---", "---"))

                for m in [1, 2, 3, 4, 5, 6]:
                    idx = m * 21
                    if idx < len(data):
                        price_then = data['Close'].iloc[idx].item()
                        # FIX 3: Access index using .index[idx] and wrap in pd.to_datetime
                        date_then_ts = data.index[idx]
                        if isinstance(date_then_ts, pd.Series): date_then_ts = date_then_ts.iloc[0]
                        date_then = pd.to_datetime(date_then_ts).strftime('%Y-%m-%d')
                        
                        pct = ((price_then - entry_price) / entry_price) * 100
                        tag = 'pos' if pct >= 0 else 'neg'
                        res_tree.insert("", "end", values=(f"{m} Month", date_then, f"{price_then:.2f}", f"{pct:.2f}%"), tags=(tag,))
                
                res_tree.tag_configure('pos', foreground="green")
                res_tree.tag_configure('neg', foreground="red")
                res_tree.tag_configure('high', background="#e1f5fe", font=('Arial', 9, 'bold'))
                res_tree.tag_configure('bold', font=('Arial', 9, 'bold'))
            except Exception as e: 
                print(f"Error Details: {e}") # This helps debug in console

        date_dropdown.bind("<<ComboboxSelected>>", calculate_returns)
        calculate_returns()

    def export_excel(self):
        if self.filtered_df is None: return
        save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if save_path:
            try:
                self.filtered_df.to_excel(save_path, index=False)
                messagebox.showinfo("Export Successful", f"Saved to {save_path}")
            except Exception as e: messagebox.showerror("Export Error", f"{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = BacktestApp(root)
    root.mainloop()
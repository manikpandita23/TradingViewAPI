import json
import random
import re
import string
import requests
from websocket import create_connection
import tkinter as tk
from tkinter import ttk

class TradingViewApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TradingView Symbol Search")
        self.pair_label = ttk.Label(root, text="Enter the trading pair:")
        self.pair_entry = ttk.Entry(root)
        self.market_label = ttk.Label(root, text="Enter the market category:")
        self.market_entry = ttk.Entry(root)
        self.search_button = ttk.Button(root, text="Search", command=self.search_symbol)
        self.symbol_label = ttk.Label(root, text="Symbol ID:")
        self.symbol_text = tk.Text(root, height=5, width=40, state="disabled")

        self.pair_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.pair_entry.grid(row=0, column=1, padx=10, pady=5)
        self.market_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.market_entry.grid(row=1, column=1, padx=10, pady=5)
        self.search_button.grid(row=2, column=0, columnspan=2, pady=10)
        self.symbol_label.grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.symbol_text.grid(row=3, column=1, padx=10, pady=5)

    def search_symbol(self):
        pair = self.pair_entry.get().strip()
        market = self.market_entry.get().strip()

        try:
            symbol_id = get_symbol_id(pair, market)
            self.symbol_text.config(state="normal")
            self.symbol_text.delete(1.0, "end")
            self.symbol_text.insert("end", symbol_id)
            self.symbol_text.config(state="disabled")
            self.start_trading_view(pair, market)

        except Exception as e:
            self.symbol_text.config(state="normal")
            self.symbol_text.delete(1.0, "end")
            self.symbol_text.insert("end", f"Error: {e}")
            self.symbol_text.config(state="disabled")

    def start_trading_view(self, pair, market):
        main_logic(pair, market)

def search(query, category):
    url = f"https://symbol-search.tradingview.com/symbol_search/?text={query}&type={category}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if data:
            return data[0]
        else:
            print("Symbol not found.")
            exit(1)
    else:
        print("Network Error!")
        exit(1)

def generate_session():
    string_length = 12
    letters = string.ascii_lowercase
    random_string = "".join(random.choice(letters) for _ in range(string_length))
    return "qs_" + random_string

def prepend_header(content):
    return f"~m~{len(content)}~m~{content}"

def construct_message(func, param_list):
    return json.dumps({"m": func, "p": param_list}, separators=(",", ":"))

def create_message(func, param_list):
    return prepend_header(construct_message(func, param_list))

def send_message(ws, func, args):
    ws.send(create_message(func, args))

def send_ping_packet(ws, result):
    ping_str = re.findall(".......(.*)", result)
    if ping_str:
        ping_str = ping_str[0]
        ws.send(f"~m~{len(ping_str)}~m~{ping_str}")

def socket_loop(ws):
    while True:
        try:
            result = ws.recv()
            if "quote_completed" in result or "session_id" in result:
                continue
            res = re.findall("^.*?({.*)$", result)
            if res:
                json_res = json.loads(res[0])
                if json_res["m"] == "qsd":
                    prefix = json_res["p"][1]
                    symbol = prefix["n"]
                    price = prefix["v"].get("lp", None)
                    volume = prefix["v"].get("volume", None)
                    change = prefix["v"].get("ch", None)
                    change_percentage = prefix["v"].get("chp", None)
                    print(f"{symbol} -> {price=}, {change=}, {change_percentage=}, {volume=}")
            else:
                send_ping_packet(ws, result)
        except KeyboardInterrupt:
            print("\n Thank You!")
            exit(0)
        except Exception as e:
            print(f"ERROR: {e}\nTradingView message: {result}")
            continue

def get_symbol_id(pair, market):
    data = search(pair, market)
    symbol_name = data["symbol"]
    broker = data.get("prefix", data["exchange"])
    symbol_id = f"{broker.upper()}:{symbol_name.upper()}"
    return symbol_id

def main_logic(pair, market):
    symbol_id = get_symbol_id(pair, market)

    trading_view_socket = "wss://data.tradingview.com/socket.io/websocket"
    headers = json.dumps({"Origin": "https://data.tradingview.com"})
    ws = create_connection(trading_view_socket, headers=headers)
    session = generate_session()

    send_message(ws, "quote_create_session", [session])
    send_message(
        ws,
        "quote_set_fields",
        [
            session,
            "lp",
            "volume",
            "ch",
            "chp",
        ],
    )
    send_message(ws, "quote_add_symbols", [session, symbol_id])

    socket_loop(ws)

if __name__ == "__main__":
    root = tk.Tk()
    app = TradingViewApp(root)
    root.mainloop()

from flask import Flask, render_template, request
from flask_socketio import SocketIO
from datetime import datetime
from threading import Thread
import csv
import json
import random
import re
import string
import requests
from websocket import create_connection

app = Flask(__name__)
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('start_stream')
def start_stream(data):
    pair = data['pair'].strip()
    market = data['market'].strip()

    if not pair or not market:
        socketio.emit('stream_error', {'message': 'Please enter both trading pair and market category.'})
        return

    csv_file = open('market_data.csv', 'a', newline='')
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(['Timestamp', 'Symbol', 'Price', 'Change', 'Change Percentage', 'Volume'])

    symbol_id = get_symbol_id(pair, market)
    trading_view_socket = "wss://data.tradingview.com/socket.io/websocket"
    headers = {"Origin": "https://data.tradingview.com"}

    ws = create_connection(trading_view_socket, headers=headers)
    session = generate_session()

    send_message(ws, "quote_create_session", [session])
    send_message(ws, "quote_set_fields", [session, "lp", "volume", "ch", "chp"])
    send_message(ws, "quote_add_symbols", [session, symbol_id])

    stream_thread = Thread(target=socket_loop, args=(ws, csv_writer))
    stream_thread.start()

@socketio.on('disconnect')
def disconnect():
    print('Client disconnected')

def get_symbol_id(pair, market):
    url = f"https://symbol-search.tradingview.com/symbol_search/?text={pair}&type={market}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if data:
            symbol_name = data[0]["symbol"]
            broker = data[0].get("prefix", data[0]["exchange"])
            return f"{broker.upper()}:{symbol_name.upper()}"
        else:
            return "Symbol not found."
    else:
        return "Network Error."

def generate_session():
    string_length = 12
    letters = string.ascii_lowercase
    random_string = "".join(random.choice(letters) for _ in range(string_length))
    return "qs_" + random_string

def send_message(ws, func, param_list):
    message = prepend_header(construct_message(func, param_list))
    ws.send(message)

def prepend_header(content):
    return f"~m~{len(content)}~m~{content}"

def construct_message(func, param_list):
    return json.dumps({"m": func, "p": param_list}, separators=(",", ":"))

def socket_loop(ws, csv_writer):
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
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    data = {
                        'symbol': symbol,
                        'price': price,
                        'volume': volume,
                        'change': change,
                        'change_percentage': change_percentage,
                        'timestamp': timestamp,
                    }
                    socketio.emit('stream_data', data)
                    csv_writer.writerow([timestamp, symbol, price, change, change_percentage, volume])
            else:
                send_ping_packet(ws, result)
        except KeyboardInterrupt:
            print("\nGoodbye!")
            csv_writer.close()
            break
        except Exception as e:
            print(f"ERROR: {e}\nTradingView message: {result}")
            continue

def send_ping_packet(ws, result):
    ping_str = re.findall(".......(.*)", result)
    if ping_str:
        ping_str = ping_str[0]
        ws.send(f"~m~{len(ping_str)}~m~{ping_str}")

if __name__ == "__main__":
    socketio.run(app, debug=True)

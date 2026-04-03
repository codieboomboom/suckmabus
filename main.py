import requests
from dotenv import load_dotenv
from os import environ
from pathlib import Path
import json

load_dotenv()
TELEGRAM_BOT_TOKEN=environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_BASEURL=f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
LTA_TOKEN=environ.get("LTA_DATAMALL_TOKEN")
LTA_BASEURL="https://datamall2.mytransport.sg/ltaodataservice"

DB_FILE = "database.json"

BOT_STATE_IDLE = "idle"
BOT_STATE_REGISTER_PENDING_BUS_STOP_NUM = "pending_bus_stop_num"
BOT_STATE_REGISTER_PENDING_BUS_STOP_ALIAS = "pending_bus_stop_alias"

# Global startup
curr_state = BOT_STATE_IDLE
    
# Data store helper=========
def load_db():
    with open(DB_FILE, "r", encoding='utf-8') as f:
        data = json.load(f)
    return data

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

# Telegram stuffs ===========
def get_updates(offset=None):
    """Get updates from user"""
    params = {
        "timeout": 30, # long polling
        "allowed_updates": ["message"]
    }
    if offset:
        params["offset"] = offset

    resp = requests.get(
        url=f"{TELEGRAM_BOT_BASEURL}/getUpdates", 
        params=params,
        timeout=35 # need to be longer than the timeout from telegram bot, otw will cut it off prematurely
    )
    return resp.json()


def send_message(chat_id, text):
    """Send a reply back to user"""
    json_message_to_send = {
        "chat_id": chat_id,
        "text": text
    }
    requests.post(url=f"{TELEGRAM_BOT_BASEURL}/sendMessage", json=json_message_to_send)

def handle_register_bus_stop(args):
    print(args)

def handle_deregister_bus_stops():
    print("Deregistering")

def handle_check():
    print("Checking")

def handle_update(update):
    """
    This is where you decide what to do with each incoming message.
    We pull out the fields we care about and dispatch to handlers.
    """
    # Safety: not every update contains a message (could be edited_message etc.)
    message = update.get("message")
    if not message:
        return

    chat_id = message["chat"]["id"]
    text = message.get("text", "")   # could be a sticker/photo with no text

    print(f"Received: '{text}' from chat_id={chat_id}")

    # Parse the command (first word) and arguments (rest)
    parts = text.strip().split()
    if not parts:
        return

    command = parts[0].lower()
    args = parts[1:]

    # Dispatch
    if command == "/start":
        send_message(chat_id, "Hello! I'm your bus bot. Try /help")

    elif command == "/help":
        send_message(chat_id,
            "/register <bus_stop_no> - Register a bus stop\n"
            "/deregister              - Remove a bus stop\n"
            "/check <stop_or_alias>   - Check arrival timings"
        )

    elif command == "/register":
        handle_register_bus_stop(args)

    elif command == "/deregister":
        handle_deregister_bus_stops()

    elif command == "/check":
        handle_check()

        else:
            send_message(chat_id, f"I don't understand you. Please try /help")

def fetch_all_bus_stops():
    url = f"{LTA_BASEURL}/BusStops"
    headers = {
        "accountKey": LTA_TOKEN
    }
    resp = requests.get(url, headers=headers)

    json_result = resp.json()

    if "value" not in json_result or not json_result["value"]:
        return {}

    bus_stop_lists = json_result["value"]
    bus_stops_dict = {}

    for bus_stop_entry in bus_stop_lists:
        bus_stops_dict[bus_stop_entry["BusStopCode"]] = bus_stop_entry

    return bus_stops_dict



def run():
    if not Path(DB_FILE).exists():
        save_db(data={})

    db = load_db()
    if "bus_stops" not in db:
        db["bus_stops"] = fetch_all_bus_stops()
    save_db(db)

    offset = None
    print("Bot is running...")

    while True:
        result = get_updates(offset)
        print(result)
        updates = result.get("result", [])

        for update in updates:
            print(update)
            handle_update(update)
            offset = update["update_id"] + 1        

if __name__=="__main__":
    run()
import requests
from dotenv import load_dotenv
from os import environ
from pathlib import Path
from enum import Enum, auto
import json

load_dotenv()
TELEGRAM_BOT_TOKEN=environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_BASEURL=f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
LTA_TOKEN=environ.get("LTA_DATAMALL_TOKEN")
LTA_BASEURL="https://datamall2.mytransport.sg/ltaodataservice"

# ============ States ===========================

class State(Enum):
    IDLE = auto()
    REGISTER_AWAITING_BUS_STOP_NUM = auto()
    REGISTER_AWAITING_CONFIRM = auto()
    DEREGISTER_AWAITING_SELECTION = auto()
    DEREGISTER_AWAITING_CONFIRM = auto()
    CHECK_AWAITING_SELECTION = auto()

# ============== Sessions Management =====================
sessions : dict[int] = {}

def get_session(chat_id: int) -> dict:
    # Get session-specific data for the user identified
    # by chat_id
    if chat_id not in sessions:
        sessions[chat_id] = {
            "state": State.IDLE,
            "data": {}
        }
    return sessions[chat_id]

def reset_session(chat_id: int):
    # Reset the chat_id session state back to IDLE
    sessions[chat_id] = {
        "state": State.IDLE,
        "data": {}
    }

def update_state_and_data(chat_id: int, next_state: State, **updates):
    # Helper to update state and data to chat_id sessions
    sessions[chat_id]["state"] = next_state
    sessions[chat_id]["data"].update(updates)

# ============= DB Management ===========================
DATABASE_URL = "database.json"

def write_to_db(data: dict):
    with open(DATABASE_URL, "w", encoding='utf-8') as db:
        json.dump(data, db, indent=4)

def read_from_db():
    with open(DATABASE_URL, "r", encoding='utf-8') as db:
        data = json.load(db)
    return data

def init_db():
    if not Path(DATABASE_URL).exists():
        bus_stops_data = fetch_all_bus_stops()
        write_to_db(
            data = {"bus_stops": bus_stops_data}
        )

# Telegram stuffs ===========
def get_updates(offset=None):
    """Get updates from Telegram server via long polling"""
    # Long polling
    # only interested in "message" or "callback_query"
    params = {
        "timeout": 30, # long polling
        "allowed_updates": ["message", "callback_query"]
    }
    if offset:
        params["offset"] = offset

    resp = requests.get(
        url=f"{TELEGRAM_BOT_BASEURL}/getUpdates", 
        params=params,
        timeout=35 # need to be longer than the timeout from telegram bot, otw will cut it off prematurely
    )
    return resp.json()


def send_message(chat_id, text, **kwargs):
    """Send a reply back to user"""
    msg = {
        "chat_id": chat_id,
        "text": text
    }
    if kwargs:
        msg.update(kwargs)
    requests.post(url=f"{TELEGRAM_BOT_BASEURL}/sendMessage", json=msg)

def parse_command(text: str):
    # Parse and return the name of command and arguments
    # if text is not command, return None and an empty argument list
    if not text.startswith("/") and len(text) > 1:
        return (None, [])
    
    command_and_args = text[1:].split()

    return command_and_args[0], command_and_args[1:]

def handle_callback_query(callback_query):
    print("[handle_callback_query")

def handle_message(message):
    print("[handle_message]")
    chat_id = message["chat"]["id"]
    text = message.get("text", "")   # could be a sticker/photo with no text

    if not chat_id:
        raise ValueError("chat_id must be present in message type")

    command, args = parse_command(text)

    if command == "help":
        # Display help message
        send_message(chat_id, "Hi, I can help you with: \n"
            "/reg - Register a bus stop\n"
            "/dereg - Remove a bus stop\n"
            "/modify - Edit bus stop information\n"
            "/check - Check arrival timings"
        )
    elif command == "cancel":
        # drop whatever been doing, reset session of the chat
        reset_session(chat_id)
    curr_session = get_session(chat_id)


def handle_update(update):
    """
    This is where you decide what to do with each incoming message.
    We pull out the fields we care about and dispatch to handlers.
    """
    update_id = update.get("update_id")
    print(f"[handle_update] Received and handling update id:{update_id}")

    # Check type of update and handle
    if update.get("callback_query"):
        # Handle callback query
        callback_query = update.get("callback_query")
        handle_callback_query(callback_query)
    elif update.get("message"):
        # Handle message
        msg = update.get("message")
        handle_message(msg)
    else:
        # an unimplemented update
        print("[handle_update] Received an update that is not callback_query nor message")

def fetch_all_bus_stops():
    """
    Fetch all bus stops from the LTA database and return a dictionary
    where key is the bus stop number and the value is a dictionary of key-value
    pairs representing information of the bus stops
    """
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
    init_db()
    offset = None
    print("Bot is running...")

    while True:
        result = get_updates(offset)
        updates = result.get("result", [])

        for update in updates:
            handle_update(update)
            offset = update["update_id"] + 1        

if __name__=="__main__":
    run()

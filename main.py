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


# Telegram stuffs ===========
def get_updates(offset=None):
    """Get updates from user"""
    params = {
        "timeout": 30, # long polling
        "allowed_updates": ["message"] # TODO: Adjust here cuz not always will be purely message
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

    """IDLE state is where the bot start off, signifying waiting for a command from user.
    Some commands may be multi-stage and must return back into BOT_STATE_IDLE once it
    finish it flow"""

    # Parse the command (first word) and arguments (rest)
    parts = text.strip().split()
    if not parts:
        return

    command = parts[0].lower()

    if command == "/start":
        send_message(chat_id, "Hello! I'm your bus bot. Try /help")

    elif command == "/help":
        send_message(chat_id,
            "/reg - Register a bus stop\n"
            "/dereg - Remove a bus stop\n"
            "/modify - Edit bus stop information\n"
            "/check - Check arrival timings"
        )


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
import requests
from dotenv import load_dotenv
from os import environ
from pathlib import Path
from enum import Enum, auto
import json

load_dotenv()
TELEGRAM_BOT_TOKEN = environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_BASEURL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
LTA_TOKEN = environ.get("LTA_DATAMALL_TOKEN")
LTA_BASEURL = "https://datamall2.mytransport.sg/ltaodataservice"

LTA_API_SKIP_OFFSET = 500  # max number of record fetched per call to API
# ============ States ===========================


class State(Enum):
    IDLE = auto()
    REGISTER_AWAITING_BUS_STOP_NUM = auto()
    REGISTER_AWAITING_CONFIRM = auto()
    DEREGISTER_AWAITING_SELECTION = auto()
    DEREGISTER_AWAITING_CONFIRM = auto()
    CHECK_AWAITING_SELECTION = auto()


# ============== Sessions Management =====================
sessions: dict[int] = {}


def get_session(chat_id: int) -> dict:
    # Get session-specific data for the user identified
    # by chat_id
    if chat_id not in sessions:
        sessions[chat_id] = {"state": State.IDLE, "data": {}}
        print(
            f"[get_session] Create a new session entry for chat_id {chat_id} as not existed previously"
        )
    return sessions[chat_id]


def reset_session(chat_id: int):
    # Reset the chat_id session state back to IDLE
    sessions[chat_id] = {"state": State.IDLE, "data": {}}
    print(f"[reset_session] Session for chat_id {chat_id} has been reset!")


def update_state_and_data(chat_id: int, next_state: State, **updates):
    # Helper to update state and data to chat_id sessions
    # TODO: What if no state changes?
    sessions[chat_id]["state"] = next_state
    sessions[chat_id]["data"].update(updates)
    print(f"[update_state_and_data] Updated to State: {next_state} and Data: {updates}")
    print(f"[update_state_and_data] Sessions view {sessions}")


# ============= DB Management ===========================
DATABASE_URL = "database.json"


def write_to_db(data: dict):
    with open(DATABASE_URL, "w", encoding="utf-8") as db:
        json.dump(data, db, indent=4)


def read_from_db():
    with open(DATABASE_URL, "r", encoding="utf-8") as db:
        data = json.load(db)
    return data


def init_db():
    if not Path(DATABASE_URL).exists():
        bus_stops_data = fetch_all_bus_stops()
        write_to_db(data={"bus_stops": bus_stops_data, "registered": {}})


# Telegram stuffs ===========
def get_updates(offset=None):
    """Get updates from Telegram server via long polling"""
    # Long polling
    # only interested in "message" or "callback_query"
    params = {
        "timeout": 30,  # long polling
        "allowed_updates": ["message", "callback_query"],
    }
    if offset:
        params["offset"] = offset

    resp = requests.get(
        url=f"{TELEGRAM_BOT_BASEURL}/getUpdates",
        params=params,
        timeout=35,  # need to be longer than the timeout from telegram bot, otw will cut it off prematurely
    )
    return resp.json()


def send_message(chat_id, text, **kwargs):
    """Send a reply back to user"""
    msg = {"chat_id": chat_id, "text": text}
    if kwargs:
        msg.update(kwargs)
    requests.post(url=f"{TELEGRAM_BOT_BASEURL}/sendMessage", json=msg)


def parse_command(text: str):
    # Parse and return the name of command and arguments
    # if text is not command, return None and an empty argument list
    if not text.startswith("/") and len(text) > 1:
        return (None, [])

    command_and_args = text[1:].split()

    return (command_and_args[0], command_and_args[1:])


def answer_callback_query(callback_query_id, **kwargs):
    payload = {"callback_query_id": callback_query_id}
    if kwargs:
        payload.update(kwargs)
    requests.post(url=f"{TELEGRAM_BOT_BASEURL}/answerCallbackQuery", json=payload)


def handle_callback_query(callback_query):
    print("[handle_callback_query")
    # Answer the callback query first
    callback_query_id = callback_query["id"]
    if not callback_query_id:
        raise ValueError("callback_query_id must be present inside a callback query")

    answer_callback_query(callback_query_id)
    print(
        f"[handle_callback_query] Answered to callback_query with id {callback_query_id}"
    )

    # Process the callback query from button clicks
    callback_data = callback_query["data"]
    if not callback_data:
        return

    command_in_process, tbc_resource_type, chat_id, verdict = callback_data.split(":")
    print(
        f"[handle_callback_query] Callback data parsing: {command_in_process} {tbc_resource_type} {chat_id} {verdict}"
    )

    # TODO: Does Telegram API works with integer chat_id only? Here need to
    # convert back to integer as the way button callback make it a text
    chat_id = int(chat_id)

    # Based on session data and the callback_query information
    # Function the FSM
    curr_session = get_session(chat_id)
    curr_state = curr_session["state"]
    curr_session_data = curr_session["data"]

    if curr_state == State.REGISTER_AWAITING_CONFIRM and command_in_process == "reg":
        if tbc_resource_type == "bus_stop" and verdict == "yes":
            print("[handle_callback_query][confirm bus stop yes]")
            pending_bus_stop_num = curr_session_data["bus_stop_num"]
            db_data = read_from_db()
            # Create bus stop entry for this user: stop number, road name, description
            bus_stop_entry = {
                "bus_stop_num": pending_bus_stop_num,
                "road_name": db_data["bus_stops"][pending_bus_stop_num]["RoadName"],
                "desc": db_data["bus_stops"][pending_bus_stop_num]["Description"],
            }
            if "registered" not in db_data:
                db_data["registered"] = {}
            if chat_id not in db_data["registered"]:
                db_data["registered"][chat_id] = {}
            # TODO: if we ever extend to have alias of bus stop,
            # this part need to be handled as well (store in cache still, move
            # to next stage
            db_data["registered"][chat_id][pending_bus_stop_no] = bus_stop_entry
            write_to_db(db_data)

            text = f"Registered bus stop with {pending_bus_stop_num}"
            send_message(chat_id, text)
            reset_session(chat_id)
        elif tbc_resource_type == "bus_stop" and verdict == "no":
            print("[handle_callback_query][confirm bus stop no]")
            text = "Please provide another bus stop number or /cancel"
            send_message(chat_id, text)
            update_state_and_data(chat_id, State.REGISTER_AWAITING_BUS_STOP_NUM)


def handle_message(message):
    print("[handle_message]")
    chat_id = message["chat"]["id"]
    text = message.get("text", "")  # could be a sticker/photo with no text

    if not chat_id:
        raise ValueError("chat_id must be present in message type")

    command, args = parse_command(text)

    if command == "help":
        # Display help message
        send_message(
            chat_id,
            "Hi, I can help you with: \n"
            "/reg - Register a bus stop\n"
            "/dereg - Remove a bus stop\n"
            "/modify - Edit bus stop information\n"
            "/check - Check arrival timings",
        )
        return
    elif command == "start":
        welcome_msg = """Hello, I am sucky-sucky 🚌. I can help track when is your next bus. Please /reg a bus stop first before /check your bus timing. More information using /help"""
        send_message(chat_id, welcome_msg)
        reset_session(chat_id)
        return
    elif command == "cancel":
        # drop whatever been doing, reset session of the chat
        cancel_msg = "Cancelled current command! Let's try again"
        send_message(chat_id, cancel_msg)
        reset_session(chat_id)
        return

    # Handle depending on which chat_id we are working with
    # To allow multiple user
    curr_session = get_session(chat_id)
    curr_state = curr_session["state"]
    curr_session_data = curr_session["data"] 

    if curr_state == State.IDLE and command == "reg":
        reply_text = "Please provide a valid bus stop number to register"
        send_message(chat_id, reply_text)
        update_state_and_data(chat_id, next_state=State.REGISTER_AWAITING_BUS_STOP_NUM)
        return
        
    elif curr_state == State.IDLE and command == "check":
        pass
    elif curr_state == State.IDLE and command == "modify":
        pass
    elif curr_state == State.IDLE and command == "unreg":
        pass
    elif curr_state == State.REGISTER_AWAITING_BUS_STOP_NUM:
        # FSM handling when receiving an input for bus stop number
        if command:
            send_message(chat_id, "Please enter a bus stop number only 🥺. Try again!")
        else:
            # Validate if the bus stop exist at all
            bus_stop_num = text.strip()
            print(f"[handle_message] Received bus stop number: {bus_stop_num}")
            db_data = read_from_db() 
            if bus_stop_num not in db_data["bus_stops"]:
                send_message(chat_id, "Sorry, seems like your bus stop number not exist 🥺. Try again or /cancel to abort registration")
            else:
                # When bus stop does exists, ready to move to next stage where
                # users may confirm whether the information retrieved by us
                # regarding their bus stop is accurated
                bus_stop_description = db_data["bus_stops"][bus_stop_num]["Description"]
                bus_stop_road_name = db_data["bus_stops"][bus_stop_num]["RoadName"]
                reply_msg = f"""Is this the bus stop you wanted to register?

{bus_stop_description}
on {bus_stop_road_name}
                """
                # Markup keyboard on telegram chat UI showing option to above
                # question.
                confirm_keyboard_markup = {
                    "inline_keyboard": [
                        [
                            {
                                "text": "Yes",
                                "callback_data": f"reg:bus_stop:{chat_id}:yes",
                            },
                            {
                                "text": "No",
                                "callback_data": f"reg:bus_stop:{chat_id}:no",
                            },
                        ]
                    ]
                }
                kwargs = {"reply_markup": confirm_keyboard_markup}
                send_message(chat_id, reply_msg, **kwargs)
                # Store temporarily the bus_stop_num and move to wait for user confirm
                ss_data_to_store = {"bus_stop_num": bus_stop_num}
                update_state_and_data(
                    chat_id,
                    next_state=State.REGISTER_AWAITING_CONFIRM,
                    **ss_data_to_store,
                )

    else:
        reset_session(chat_id)
        send_message(
            chat_id,
            "🥺 Sorry I don't understand you! Please refer to /help and try again!",
        )


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
        print(
            "[handle_update] Received an update that is not callback_query nor message"
        )


def fetch_all_bus_stops():
    """
    Fetch all bus stops from the LTA database and return a dictionary
    where key is the bus stop number and the value is a dictionary of key-value
    pairs representing information of the bus stops
    """
    headers = {"accountKey": LTA_TOKEN}
    bus_stops = []
    skip_by = 0  # Number of entry to skip
    # Based on https://datamall.lta.gov.sg/content/dam/datamall/datasets/LTA_DataMall_API_User_Guide.pdf
    # Currently, each API call only returns max LTA_API_SKIP_OFFSET
    # Here we needs to handle them until all entries are fetched
    while True:
        url = f"{LTA_BASEURL}/BusStops?$skip={skip_by}"
        resp = requests.get(url, headers=headers)
        json_result = resp.json()

        if "value" not in json_result or not json_result["value"]:
            break

        bus_stops.extend(json_result["value"])
        if len(json_result["value"]) < LTA_API_SKIP_OFFSET:
            break

        skip_by += LTA_API_SKIP_OFFSET

    # Need to be key-value format for easier storage into file database
    bus_stops_dict = {}
    for bus_stop_entry in bus_stops:
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


if __name__ == "__main__":
    run()

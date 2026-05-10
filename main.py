import requests
from dotenv import load_dotenv
from os import environ
from pathlib import Path
from enum import Enum, auto
from datetime import datetime, timezone, timedelta
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
    UNREGISTER_AWAITING_SELECTION = auto()
    UNREGISTER_AWAITING_CONFIRM = auto()
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

    callback_data_fields = callback_data.split(":")
    command_in_process = callback_data_fields[0]
    # TODO: Does Telegram API works with integer chat_id only? Here need to
    # convert back to integer as the way button callback make it a text
    chat_id = int(callback_data_fields[1])  # protocol defined command:chat_id:blah:blah
    # Based on session data and the callback_query information
    # Function the FSM
    curr_session = get_session(chat_id)
    curr_state = curr_session["state"]
    curr_session_data = curr_session["data"]

    if curr_state == State.REGISTER_AWAITING_CONFIRM and command_in_process == "reg":
        print(
            f"[handle_callback_query] Processing callback for /{command_in_process} at stage {curr_state}"
        )
        tbc_resource_type = callback_data_fields[2]
        verdict = callback_data_fields[3]

        if tbc_resource_type == "bus_stop" and verdict == "yes":
            print("[handle_callback_query][confirm bus stop yes]")
            pending_bus_stop_num = curr_session_data["bus_stop_num"]
            db_data = read_from_db()
            db_chat_id = str(chat_id)  # for stupid reasons...
            # Create bus stop entry for this user: stop number, road name, description
            bus_stop_entry = {
                "bus_stop_num": pending_bus_stop_num,
                "road_name": db_data["bus_stops"][pending_bus_stop_num]["RoadName"],
                "desc": db_data["bus_stops"][pending_bus_stop_num]["Description"],
            }
            if "registered" not in db_data:
                db_data["registered"] = {}
            if db_chat_id not in db_data["registered"]:
                db_data["registered"][db_chat_id] = {}
            # TODO: if we ever extend to have alias of bus stop,
            # this part need to be handled as well (store in cache still, move
            # to next stage
            db_data["registered"][db_chat_id][pending_bus_stop_num] = bus_stop_entry
            write_to_db(db_data)

            text = f"Registered bus stop with {pending_bus_stop_num}"
            send_message(chat_id, text)
            reset_session(chat_id)
        elif tbc_resource_type == "bus_stop" and verdict == "no":
            print("[handle_callback_query][confirm bus stop no]")
            text = "Please provide another bus stop number or /cancel"
            send_message(chat_id, text)
            update_state_and_data(chat_id, State.REGISTER_AWAITING_BUS_STOP_NUM)
    elif curr_state == State.CHECK_AWAITING_SELECTION and command_in_process == "check":
        print(
            f"[handle_callback_query] Processing callback for /{command_in_process} at stage {curr_state}"
        )
        selected_bus_stop_num = callback_data_fields[3]
        bus_num_to_arrivals_timestamp_mapping = fetch_bus_stop_arrival(
            selected_bus_stop_num
        )
        msg_parts = [
            f"Sure! Here are the arriving buses for bus stop 🚏 {selected_bus_stop_num}:\n"
        ]
        for bus_num, bus_arrival_entry in bus_num_to_arrivals_timestamp_mapping.items():
            # TODO: might need refactor if bus_arrival_entry is no longer list
            timestamps_iso8601 = bus_arrival_entry
            minutes = calc_minutes_to_arrival(timestamps_iso8601)
            # TODO: What if bus time arrival diff is -ve?
            print(
                f"[handle_callback_query][check][stop_numer {selected_bus_stop_num}] bus {bus_num} has following next buses: {minutes}"
            )
            bus_arrival_msg = build_bus_arrival_info_string(bus_num, minutes)
            msg_parts.append(bus_arrival_msg)
        text = "".join(msg_parts)
        send_message(chat_id, text)
        reset_session(chat_id)


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
            "/unreg - Remove a bus stop\n"
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
        # Ensure that there are bus stop registered first
        db_data = read_from_db()
        db_chat_id = str(chat_id)
        if (
            "registered" not in db_data
            or db_chat_id not in db_data["registered"]
            or not db_data["registered"][db_chat_id]
        ):
            reply_text = (
                "You don't seems to have any saved bus stop. Please /reg first!"
            )
            send_message(chat_id, reply_text)
            reset_session(chat_id)
            return
        # Prepare list of bus stops as buttons to be selected
        reply_text = "Please select a bus stop to check timing:"
        rows_on_inline_keyboard = []
        for bus_stop_num, bus_stop_entry in db_data["registered"][db_chat_id].items():
            keyboard_entry_as_row = [
                {
                    "text": f"{bus_stop_entry['desc']} ({bus_stop_entry['road_name']})",
                    "callback_data": f"check:{chat_id}:bus_arrival:{bus_stop_num}",
                }
            ]
            rows_on_inline_keyboard.append(keyboard_entry_as_row)
        selection_keyboard_markup = {"inline_keyboard": rows_on_inline_keyboard}
        # Send inline keyboard with selection of stored bus stop
        send_message(chat_id, reply_text, reply_markup=selection_keyboard_markup)
        update_state_and_data(chat_id, State.CHECK_AWAITING_SELECTION)

    elif curr_state == State.IDLE and command == "modify":
        # TODO: Implement
        pass
    elif curr_state == State.IDLE and command == "unreg":
        # Check if there are anything to remove
        db_data = read_from_db()
        db_chat_id = str(chat_id)
        if (
            "registered" not in db_data
            or db_chat_id not in db_data["registered"]
            or not db_data["registered"][db_chat_id]
        ):
            reply_text = (
                "You don't seems to have any saved bus stop to remove. All good"
            )
            send_message(chat_id, reply_text)
            reset_session(chat_id)
            return

        # Prepare list of bus stops as buttons to be selected
        reply_text = "Please select a bus stop you wish to remove"
        rows_on_inline_keyboard = []
        for bus_stop_num, bus_stop_entry in db_data["registered"][db_chat_id].items():
            keyboard_entry_as_row = [
                {
                    "text": f"{bus_stop_entry['desc']} ({bus_stop_entry['road_name']})",
                    "callback_data": f"unreg:{chat_id}:bus_stop:{bus_stop_num}",
                }
            ]
            rows_on_inline_keyboard.append(keyboard_entry_as_row)
        selection_keyboard_markup = {"inline_keyboard": rows_on_inline_keyboard}
        # Send inline keyboard with selection of stored bus stop
        send_message(chat_id, reply_text, reply_markup=selection_keyboard_markup)
        update_state_and_data(chat_id, State.UNREGISTER_AWAITING_SELECTION)
    elif curr_state == State.REGISTER_AWAITING_BUS_STOP_NUM:
        # Handle arriving bus stop number for registration
        if command:
            send_message(chat_id, "Please enter a bus stop number only 🥺. Try again!")
        else:
            # Validate if the bus stop valid at all
            bus_stop_num = text.strip()
            print(f"[handle_message] Received bus stop number: {bus_stop_num}")
            db_data = read_from_db()
            db_chat_id = str(chat_id)
            if bus_stop_num not in db_data["bus_stops"]:
                send_message(
                    chat_id,
                    "Sorry, seems like your bus stop number not exist 🥺. Try again or /cancel to abort registration",
                )
            elif bus_stop_num in db_data["registered"][db_chat_id]:
                send_message(
                    chat_id,
                    "You have registered this bus stop. Try a different one or /cancel to abort",
                )
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
                                "callback_data": f"reg:{chat_id}:bus_stop:yes",
                            },
                            {
                                "text": "No",
                                "callback_data": f"reg:{chat_id}:bus_stop:no",
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


def build_bus_arrival_info_string(bus_num, minutes_to_arrival):
    result = [f"🚌 {bus_num}: "]
    for next_arrival_est in minutes_to_arrival:
        if next_arrival_est < 0:
            result.append("[✅ ARRIVING] ")
        else:
            result.append(f"[{next_arrival_est} MINs] ")
    result.append("\n")
    return "".join(result)


def calc_minutes_to_arrival(timestamp_in_iso8601):
    """
    Calculate the minutes for bus to arrivals, in minutes from the ISO8601
    timestamps given. Return a list of integer with similar dimesion as the
    input list where each element denotes minutes remaining until bus arriving
    """
    if not timestamp_in_iso8601:
        return []

    # current time in Singapore time zone
    sgtz = timezone(timedelta(hours=8))
    curr_time = datetime.now(sgtz)

    arrivals_minutes = []
    for arrival_timestamp_iso8601 in timestamp_in_iso8601:
        # Convert to datetime
        arrival_dt = datetime.fromisoformat(arrival_timestamp_iso8601)
        arrivals_minutes.append(int((arrival_dt - curr_time).total_seconds() / 60))

    return arrivals_minutes


def fetch_bus_stop_arrival(bus_stop_num):
    """
    Query the LTA database using the bus_stop_num for a list of arriving buses
    """
    headers = {"accountKey": LTA_TOKEN}
    url = f"{LTA_BASEURL}/v3/BusArrival?BusStopCode={bus_stop_num}"
    resp = requests.get(
        url, headers=headers
    )  # TODO: handle the case where nothing is return, as noted by the datamall api
    json_result = resp.json()

    if "Services" not in json_result or not json_result["Services"]:
        return []

    bus_arrivals = {}
    for bus_service_entry in json_result["Services"]:
        bus_num = bus_service_entry["ServiceNo"]
        arrival_timestamp = []
        for next_bus_key in ["NextBus", "NextBus2", "NextBus3"]:
            # TODO: Here we only store the timestamp for simplicity sake
            # What can our application extend in the future?
            if bus_service_entry[next_bus_key]["EstimatedArrival"]:
                arrival_timestamp.append(
                    bus_service_entry[next_bus_key]["EstimatedArrival"]
                )
        bus_arrivals[bus_num] = arrival_timestamp

    return bus_arrivals


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

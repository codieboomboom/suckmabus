import requests
from dotenv import load_dotenv
from os import environ

load_dotenv()
TELEGRAM_BOT_TOKEN=environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_BASEURL=f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

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
import requests
from dotenv import load_dotenv
from os import environ

TELEGRAM_BOT_TOKEN=environ("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_BASEURL=f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def get_update(offset=None):
    """Get updates from user"""
    pass

def send_message(chat_id, text):
    """Send a reply back to user"""
    pass

def handle_update(update):
    """Handle the update received by user"""
    pass

def run():
    pass

if __name__=="__main__":
    run()
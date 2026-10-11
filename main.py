import os
import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

def main():
    if not TOKEN:
        print("Missing Telegram bot token")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    print("Aviator Spy bot is ready")

if __name__ == "__main__":
    main()

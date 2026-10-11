import os
import requests
import time

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    print("Missing Telegram bot token")
    raise SystemExit(1)

URL = f"https://api.telegram.org/bot{TOKEN}/"

def main():
    offset = 0
    print("Bot started")

    while True:
        try:
            response = requests.get(
                URL + "getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35
            )
            response.raise_for_status()

            for update in response.json().get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message", {})
                chat = message.get("chat", {})
                text = message.get("text", "")

                if not chat or not text:
                    continue

                if text == "/start":
                    reply = (
                        "مرحباً بك! البوت يعمل بنجاح.\n"
                        "هذا البوت لا يتنبأ بنتائج Aviator."
                    )
                else:
                    reply = "البوت يعمل. أرسل /start للبدء."

                requests.post(
                    URL + "sendMessage",
                    json={
                        "chat_id": chat["id"],
                        "text": reply
                    },
                    timeout=15
                )

        except Exception as error:
            print("Error:", error)
            time.sleep(5)

if __name__ == "__main__":
    main()

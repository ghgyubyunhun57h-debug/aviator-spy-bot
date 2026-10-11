import os
import time
import statistics
import requests

# إعدادات البوت
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DOMAIN = os.getenv("SPINMAMA_DOMAIN", "").strip().rstrip("/")
SPIN_TOKEN = os.getenv("SPINMAMA_TOKEN", "").strip()

if not TOKEN:
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN environment variable")

TG = f"https://api.telegram.org/bot{TOKEN}/"
http = requests.Session()
history = []


def send(chat_id, text):
    response = http.post(
        TG + "sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=15,
    )
    response.raise_for_status()

    if not response.json().get("ok"):
        raise RuntimeError("Telegram sendMessage failed")


def extract(payload):
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = next(
            (
                payload.get(key)
                for key in (
                    "results",
                    "outcomes",
                    "roundHistory",
                    "history",
                    "data",
                )
                if isinstance(payload.get(key), list)
            ),
            [],
        )
    else:
        items = []

    parsed = []

    for item in items:
        raw = item
        timestamp = None

        if isinstance(item, dict):
            raw = next(
                (
                    item.get(key)
                    for key in (
                        "multiplier",
                        "crashPoint",
                        "result",
                        "value",
                        "outcome",
                    )
                    if item.get(key) is not None
                ),
                None,
            )

            timestamp = (
                item.get("created_at")
                or item.get("time")
                or item.get("timestamp")
            )

        try:
            value = float(
                str(raw).lower().replace("x", "").strip()
            )

            if 0.01 <= value <= 1_000_000:
                parsed.append(
                    {
                        "multiplier": round(value, 4),
                        "timestamp": timestamp,
                    }
                )

        except (TypeError, ValueError):
            continue

    return parsed


def report(results):
    values = [item["multiplier"] for item in results]

    if not values:
        return "لم أجد نتائج مفهومة في استجابة مصدر البيانات."

    lines = ["📊 نتائج Aviator:"]

    for index, item in enumerate(results[-20:], 1):
        stamp = (
            f" — {item['timestamp']}"
            if item.get("timestamp")
            else ""
        )

        lines.append(
            f"{index}. {item['multiplier']:.2f}x{stamp}"
        )

    below_two = sum(value < 2 for value in values)

    lines.extend(
        [
            "",
            f"عدد النتائج: {len(values)}",
            f"المتوسط: {statistics.mean(values):.2f}x",
            f"الوسيط: {statistics.median(values):.2f}x",
            (
                f"أقل من 2x: {below_two} "
                f"({below_two / len(values) * 100:.1f}%)"
            ),
            "",
            "تنبيه: النتائج السابقة لا تضمن نتيجة الجولة القادمة.",
        ]
    )

    return "\n".join(lines)


def fetch_spinmama():
    if not DOMAIN or not SPIN_TOKEN:
        raise RuntimeError(
            "مصدر Spinmama غير مضبوط. نحتاج عنوان API رسمي "
            "ورمز وصول صحيحاً من المنصة."
        )

    # استخدم هذا المسار فقط إذا أكدت Spinmama أنه رسمي.
    response = http.get(
        DOMAIN + "/outcomes",
        headers={
            "Authorization": f"Bearer {SPIN_TOKEN}",
            "Accept": "application/json",
        },
        timeout=20,
    )

    response.raise_for_status()
    return extract(response.json())


def handle_update(update):
    message = (
        update.get("message")
        or update.get("edited_message")
    )

    if not message:
        return

    chat_id = (message.get("chat") or {}).get("id")
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return

    command = text.split()[0].split("@")[0].lower()

    if command in ("/start", "/help"):
        send(
            chat_id,
            "أهلاً! أنا Aviator Spy.\n\n"
            "/fetch — جلب النتائج من مصدر API رسمي\n"
            "/stats — إحصائيات النتائج\n"
            "/last — آخر النتائج\n\n"
            "القراءة التلقائية تحتاج عنوان API رسمي وبيانات وصول صحيحة.",
        )

    elif command == "/fetch":
        try:
            results = fetch_spinmama()

            if not results:
                send(
                    chat_id,
                    "مصدر البيانات لم يُرجع نتائج مفهومة.",
                )
                return

            history.extend(results)
            del history[:-500]

            send(chat_id, report(results))

        except Exception as error:
            send(
                chat_id,
                f"تعذّر جلب النتائج: "
                f"{type(error).__name__}: {error}",
            )

    elif command == "/stats":
        if history:
            send(chat_id, report(history))
        else:
            send(
                chat_id,
                "لا توجد نتائج جلبها البوت بعد.",
            )

    elif command == "/last":
        if not history:
            send(chat_id, "لا توجد نتائج محفوظة بعد.")
        else:
            lines = [
                f"{index}. {item['multiplier']:.2f}x"
                for index, item in enumerate(
                    history[-20:], 1
                )
            ]

            send(
                chat_id,
                "آخر النتائج:\n" + "\n".join(lines),
            )

    else:
        send(
            chat_id,
            "الأوامر المتاحة: /start، /fetch، /stats، /last",
        )


def main():
    offset = 0
    print("Aviator Spy started")

    while True:
        try:
            response = http.get(
                TG + "getUpdates",
                params={
                    "offset": offset,
                    "timeout": 25,
                    "allowed_updates": ["message"],
                },
                timeout=35,
            )

            response.raise_for_status()
            payload = response.json()

            if not payload.get("ok"):
                raise RuntimeError(
                    "Telegram getUpdates failed"
                )

            for update in payload.get("result", []):
                offset = max(
                    offset,
                    int(update.get("update_id", 0)) + 1,
                )

                try:
                    handle_update(update)
                except Exception as error:
                    print(
                        f"Update handler error: "
                        f"{type(error).__name__}: {error}"
                    )

        except KeyboardInterrupt:
            break

        except Exception as error:
            print(
                f"Polling error: "
                f"{type(error).__name__}: {error}"
            )
            time.sleep(15)


if __name__ == "__main__":
    main()

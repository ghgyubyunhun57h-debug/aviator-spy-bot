import os
import time
import statistics
import requests

# إعدادات البوت
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DOMAIN = os.getenv("SPINMAMA_DOMAIN", "").strip().rstrip("/")
SPIN_TOKEN = os.getenv("SPINMAMA_TOKEN", "").strip()

if not TOKEN:
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN")

TG = f"https://api.telegram.org/bot{TOKEN}/"
http = requests.Session()
history = []


def send(chat_id, text):
    r = http.post(
        TG + "sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=15
    )
    r.raise_for_status()

    if not r.json().get("ok"):
        raise RuntimeError("Telegram sendMessage failed")


def extract(payload):
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = next(
            (
                payload.get(k)
                for k in (
                    "results",
                    "outcomes",
                    "roundHistory",
                    "history",
                    "data"
                )
                if isinstance(payload.get(k), list)
            ),
            []
        )
    else:
        items = []

    out = []

    for item in items:
        raw = item
        stamp = None

        if isinstance(item, dict):
            raw = next(
                (
                    item.get(k)
                    for k in (
                        "multiplier",
                        "crashPoint",
                        "result",
                        "value",
                        "outcome"
                    )
                    if item.get(k) is not None
                ),
                None
            )

            stamp = (
                item.get("created_at")
                or item.get("time")
                or item.get("timestamp")
            )

        try:
            val = float(
                str(raw).lower().replace("x", "").strip()
            )

            if 0.01 <= val <= 1000000:
                out.append({
                    "multiplier": round(val, 4),
                    "timestamp": stamp
                })

        except (TypeError, ValueError):
            pass

    return out


def report(results):
    vals = [x["multiplier"] for x in results]

    if not vals:
        return "ما في نتائج مفهومة ضمن رد API."

    lines = ["📊 نتائج Aviator:"]

    for i, x in enumerate(results[-20:], 1):
        stamp = (
            f" — {x['timestamp']}"
            if x.get("timestamp")
            else ""
        )

        lines.append(
            f"{i}. {x['multiplier']:.2f}x{stamp}"
        )

    lines += [
        "",
        f"عدد النتائج: {len(vals)}",
        f"المتوسط: {statistics.mean(vals):.2f}x",
        f"الوسيط: {statistics.median(vals):.2f}x",
        (
            f"أقل من 2x: "
            f"{sum(v < 2 for v in vals)} "
            f"({sum(v < 2 for v in vals) / len(vals) * 100:.1f}%)"
        ),
        "",
        "تنبيه: النتائج السابقة لا تضمن نتيجة الجولة القادمة."
    ]

    return "\n".join(lines)


def fetch():
    if not DOMAIN or not SPIN_TOKEN:
        raise RuntimeError(
            "مصدر Spinmama غير مضبوط. "
            "نحتاج API رسمي ورمز وصول صحيح."
        )

    # استخدم هذا العنوان فقط إذا أكدت Spinmama أنه رسمي.
    r = http.get(
        DOMAIN + "/outcomes",
        headers={
            "Authorization": f"Bearer {SPIN_TOKEN}",
            "Accept": "application/json"
        },
        timeout=20
    )

    r.raise_for_status()
    return extract(r.json())


def handle(update):
    msg = update.get("message") or update.get("edited_message")

    if not msg:
        return

    chat_id = (msg.get("chat") or {}).get("id")
    text = (msg.get("text") or "").strip()

    if not chat_id or not text:
        return

    cmd = text.split()[0].split("@")[0].lower()

    if cmd in ("/start", "/help"):
        send(
            chat_id,
            "أ

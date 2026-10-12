import os
import time
import statistics
import logging
import requests

# =========================
# إعدادات البوت
# =========================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

DOMAIN = os.getenv(
    "SPINMAMA_DOMAIN", ""
).strip().rstrip("/")

SPIN_TOKEN = os.getenv(
    "SPINMAMA_TOKEN", ""
).strip()

API_PATH = os.getenv(
    "SPINMAMA_API_PATH", "/outcomes"
).strip()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

log = logging.getLogger(__name__)

if not TOKEN:
    raise SystemExit(
        "Missing TELEGRAM_BOT_TOKEN environment variable"
    )

TG = f"https://api.telegram.org/bot{TOKEN}/"

http = requests.Session()
history = []


# =========================
# إرسال رسائل Telegram
# =========================

def send(chat_id, text):
    response = http.post(
        TG + "sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
        },
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            "Telegram sendMessage failed"
        )


# =========================
# استخراج النتائج
# =========================

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
                if isinstance(
                    payload.get(key), list
                )
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
                str(raw)
                .lower()
                .replace("x", "")
                .strip()
            )

            if 0.01 <= value <= 1_000_000:
                parsed.append(
                    {
                        "multiplier": round(
                            value, 4
                        ),
                        "timestamp": timestamp,
                    }
                )

        except (TypeError, ValueError):
            continue

    return parsed


# =========================
# عرض النتائج والإحصائيات
# =========================

def report(results):
    if not results:
        return "ما في نتائج محفوظة حالياً."

    values = [
        item["multiplier"]
        for item in results
    ]

    lines = [
        "📊 نتائج Aviator",
        "",
    ]

    for index, item in enumerate(
        results[-20:][::-1], 1
    ):
        stamp = (
            f" — {item['timestamp']}"
            if item.get("timestamp")
            else ""
        )

        lines.append(
            f"{index}. "
            f"{item['multiplier']:.2f}x"
            f"{stamp}"
        )

    below_two = sum(
        value < 2 for value in values
    )

    lines.extend(
        [
            "",
            f"عدد النتائج: {len(values)}",
            (
                f"المتوسط: "
                f"{statistics.mean(values):.2f}x"
            ),
            (
                f"الوسيط: "
                f"{statistics.median(values):.2f}x"
            ),
            (
                f"أقل من 2x: {below_two} "
                f"({below_two / len(values) * 100:.1f}%)"
            ),
            "",
            "تنبيه: النتائج السابقة لا تضمن "
            "نتيجة الجولة القادمة.",
        ]
    )

    return "\n".join(lines)


# =========================
# جلب البيانات من المصدر
# =========================

def fetch_spinmama():
    if not DOMAIN or not SPIN_TOKEN:
        raise RuntimeError(
            "مصدر البيانات غير مضبوط. "
            "يلزم عنوان API رسمي ورمز وصول صحيح."
        )

    if not API_PATH.startswith("/"):
        raise RuntimeError(
            "SPINMAMA_API_PATH يجب أن يبدأ بـ /"
        )

    response = http.get(
        DOMAIN + API_PATH,
        headers={
            "Authorization": (
                f"Bearer {SPIN_TOKEN}"
            ),
            "Accept": "application/json",
        },
        timeout=20,
    )

    response.raise_for_status()

    return extract(response.json())


# =========================
# معالجة أوامر المستخدم
# =========================

def handle_update(update):
    message = (
        update.get("message")
        or update.get("edited_message")
    )

    if not message:
        return

    chat_id = (
        message.get("chat") or {}
    ).get("id")

    text = (
        message.get("text") or ""
    ).strip()

    if not chat_id or not text:
        return

    command = (
        text.split()[0]
        .split("@")[0]
        .lower()
    )

    if command in ("/start", "/help"):
        send(
            chat_id,
            "أهلاً بك في Aviator Spy Bot! ✈️\n\n"
            "الأوامر المتاحة:\n"
            "/fetch - جلب النتائج\n"
            "/stats - الإحصائيات\n"
            "/last - آخر النتائج\n"
            "/help - المساعدة\n\n"
            "ملاحظة: جلب النتائج يحتاج "
            "إلى مصدر API رسمي وصحيح.",
        )
        return

    if command == "/fetch":
        send(
            chat_id,
            "⏳ جارٍ محاولة جلب النتائج..."
        )

        try:
            results = fetch_spinmama()

            if not results:
                send(
                    chat_id,
                    "لم يرجع مصدر البيانات "
                    "نتائج مفهومة."
                )
                return

            history.extend(results)

            # الاحتفاظ بآخر 500 نتيجة
            del history[:-500]

            send(chat_id, report(results))

        except requests.RequestException as exc:
            log.warning(
                "Data request failed: %s",
                type(exc).__name__,
            )

            send(
                chat_id,
                "تعذّر الاتصال بمصدر البيانات. "
                "تحقق من عنوان API وإعداداته."
            )

        except Exception:
            log.exception(
                "Fetch operation failed"
            )

            send(
                chat_id,
                "حدث خطأ أثناء جلب النتائج. "
                "راجع سجلات Railway."
            )

        return

    if command == "/stats":
        send(chat_id, report(history))
        return

    if command == "/last":
        if history:
            send(
                chat_id,
                report(history[-20:])
            )
        else:
            send(
                chat_id,
                "ما في نتائج محفوظة. "
                "جرّب /fetch أولاً."
            )

        return

    send(
        chat_id,
        "الأمر غير معروف. استخدم /help"
    )


# =========================
# تشغيل البوت واستقبال الرسائل
# =========================

def main():
    log.info("Starting Aviator Spy Bot")

    # تفعيل استقبال الرسائل عن طريق polling
    response = http.post(
        TG + "deleteWebhook",
        json={
            "drop_pending_updates": False
        },
        timeout=20,
    )

    response.raise_for_status()

    if not response.json().get("ok"):
        raise RuntimeError(
            "Could not configure Telegram polling"
        )

    offset = None

    while True:
        try:
            params = {
                "timeout": 30,
                "allowed_updates": [
                    "message",
                    "edited_message",
                ],
            }

            if offset is not None:
                params["offset"] = offset

            response = http.get(
                TG + "getUpdates",
                params=params,
                timeout=40,
            )

            response.raise_for_status()

            data = response.json()

            if not data.get("ok"):
                raise RuntimeError(
                    "Telegram getUpdates failed"
                )

            for update in data.get(
                "result", []
            ):
                offset = (
                    update["update_id"] + 1
                )

                try:
                    handle_update(update)

                except Exception:
                    log.exception(
                        "Failed to process update"
                    )

        except KeyboardInterrupt:
            log.info("Bot stopped")
            break

        except Exception:
            log.exception(
                "Polling error; retrying"
            )
            time.sleep(5)


if __name__ == "__main__":
    main()

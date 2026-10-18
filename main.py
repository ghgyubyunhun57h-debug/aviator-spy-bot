
import os
import re
import time
import logging
import sqlite3
import statistics
from io import BytesIO
from datetime import datetime, timezone

import requests
from PIL import Image, ImageOps, ImageFilter
import pytesseract

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DB_PATH = os.getenv("DB_PATH", "aviator_history.db")
TG = f"https://api.telegram.org/bot{TOKEN}/"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aviator_bot")
http = requests.Session()

if not TOKEN:
    raise SystemExit("متغير TELEGRAM_BOT_TOKEN غير موجود")

# قاعدة بيانات للنتائج التي قرأها البوت
def db():
    return sqlite3.connect(DB_PATH)

def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                multiplier REAL NOT NULL,
                created_at TEXT NOT NULL,
                source TEXT NOT NULL
            )
        """)

def save_results(chat_id, values, source="photo"):
    now = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        for value in values:
            conn.execute(
                """INSERT INTO results
                   (chat_id, multiplier, created_at, source)
                   VALUES (?, ?, ?, ?)""",
                (chat_id, value, now, source)
            )

def get_results(chat_id, limit=500):
    with db() as conn:
        rows = conn.execute(
            """SELECT multiplier, created_at
               FROM results
               WHERE chat_id = ?
               ORDER BY id DESC LIMIT ?""",
            (chat_id, limit)
        ).fetchall()
    return [
        {"multiplier": row[0], "timestamp": row[1]}
        for row in reversed(rows)
    ]

def send(chat_id, text):
    response = http.post(
        TG + "sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
        },
        timeout=30,
    )
    response.raise_for_status()
    if not response.json().get("ok"):
        raise RuntimeError("فشل إرسال رسالة تيليجرام")

def get_file(file_id):
    response = http.get(
        TG + "getFile",
        params={"file_id": file_id},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError("تعذّر الحصول على الصورة")

    path = data["result"]["file_path"]
    url = f"https://api.telegram.org/file/bot{TOKEN}/{path}"
    image_response = http.get(url, timeout=60)
    image_response.raise_for_status()
    return Image.open(BytesIO(image_response.content))

def read_multipliers(image):
    # تحسين بسيط للصورة قبل قراءة النص
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")
    image = ImageOps.autocontrast(image)
    image = image.filter(ImageFilter.SHARPEN)

    # أرقام المضاعفات المعتادة: 1.23x، 2.50x، إلخ
    text = pytesseract.image_to_string(
        image,
        config="--psm 6"
    )

    pattern = r"(?<![\d.])(\d{1,6}[.,]\d{1,4})\s*[xX×]?"
    values = []

    for match in re.finditer(pattern, text):
        try:
            value = float(match.group(1).replace(",", "."))
            if 1.0 <= value <= 100000:
                values.append(round(value, 2))
        except ValueError:
            continue

    # إزالة التكرار المتتالي فقط، مع الحفاظ على الترتيب
    cleaned = []
    for value in values:
        if not cleaned or cleaned[-1] != value:
            cleaned.append(value)

    return cleaned, text

def report(chat_id, limit=500):
    results = get_results(chat_id, limit)
    if not results:
        return "ما في نتائج محفوظة بعد.\nابعث صورة واضحة لسجل المضاعفات."

    values = [r["multiplier"] for r in results]
    under_two = sum(v < 2 for v in values)
    two_to_five = sum(2 <= v < 5 for v in values)
    five_plus = sum(v >= 5 for v in values)

    lines = [
        "📊 تحليل نتائج Aviator",
        f"عدد النتائج المسجلة: {len(values)}",
        f"المتوسط الحسابي: {statistics.mean(values):.2f}x",
        f"الوسيط: {statistics.median(values):.2f}x",
        f"أقل من 2x: {under_two} ({under_two / len(values) * 100:.1f}%)",
        f"من 2x إلى أقل من 5x: {two_to_five}",
        f"5x فأكثر: {five_plus}",
        "",
        "آخر النتائج المسجلة:",
    ]

    for item in results[-15:][::-1]:
        lines.append(f"• {item['multiplier']:.2f}x")

    # تقدير وصفي مبني على التكرار التاريخي، وليس توقعاً مضموناً
    if len(values) >= 30:
        rate = under_two / len(values) * 100
        lines.extend([
            "",
            "📈 تقدير إحصائي تجريبي",
            f"نسبة النتائج السابقة الأقل من 2x: {rate:.1f}%",
            "هذه نسبة تاريخية وليست احتمالاً مؤكداً للجولة القادمة.",
        ])
    else:
        lines.extend([
            "",
            "نحتاج إلى 30 نتيجة على الأقل لعرض ملخص إحصائي أولي."
        ])

    lines.extend([
        "",
        "⚠️ النتائج السابقة لا تضمن النتائج القادمة."
    ])
    return "\n".join(lines)

def handle(update):
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return

    text = (message.get("text") or "").strip()
    command = text.split()[0].split("@")[0].lower() if text else ""

    if command in ("/start", "/help"):
        send(
            chat_id,
            "أهلاً بك في بوت تحليل Aviator ✈️\n\n"
            "📷 ابعث صورة واضحة لسجل المضاعفات.\n\n"
            "الأوامر:\n"
            "/start - بدء البوت\n"
            "/stats - الإحصائيات\n"
            "/last - آخر النتائج\n"
            "/help - المساعدة\n\n"
            "البوت يحلل النتائج السابقة ولا يضمن الجولة القادمة."
        )
        return

    if command == "/stats":
        send(chat_id, report(chat_id))
        return

    if command == "/last":
        results = get_results(chat_id, 20)
        if not results:
            send(chat_id, "ما في نتائج محفوظة بعد.")
        else:
            send(
                chat_id,
                "🕘 آخر النتائج:\n" +
                "\n".join(f"• {r['multiplier']:.2f}x" for r in results[::-1])
            )
        return

    photos = message.get("photo") or []
    if photos:
        send(chat_id, "⏳ وصلت الصورة، عم حاول أقرأ المضاعفات...")
        try:
            # أكبر نسخة متاحة من الصورة
            image = get_file(photos[-1]["file_id"])
            values, raw_text = read_multipliers(image)

            if not values:
                send(
                    chat_id,
                    "ما قدرت أقرأ المضاعفات بوضوح.\n"
                    "جرّب صورة أوضح ومقرّبة لسجل النتائج."
                )
                log.info("OCR text: %s", raw_text[:1000])
                return

            save_results(chat_id, values)
            send(
                chat_id,
                f"✅ قرأت {len(values)} نتيجة وحفظتها.\n\n" +
                report(chat_id)
            )
        except Exception:
            log.exception("Image processing failed")
            send(
                chat_id,
                "تعذّرت معالجة الصورة. تأكد من إعدادات قراءة الصور، "
                "ثم راجع سجلات Railway."
            )
        return

    if text:
        send(chat_id, "ابعث صورة لسجل النتائج أو استخدم /help.")

def main():
    init_db()
    log.info("Aviator bot started")

    # إزالة Webhook حتى يعمل الاستقبال بالـ polling
    response = http.post(
        TG + "deleteWebhook",
        json={"drop_pending_updates": False},
        timeout=30,
    )
    response.raise_for_status()
    if not response.json().get("ok"):
        raise RuntimeError("تعذّر إعداد استقبال تيليجرام")

    offset = None
    while True:
        try:
            params = {
                "timeout": 30,
                "allowed_updates": ["message", "edited_message"],
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
                raise RuntimeError("فشل استقبال تحديثات تيليجرام")

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                try:
                    handle(update)
                except Exception:
                    log.exception("Update processing failed")
        except KeyboardInterrupt:
            break
        except Exception:
            log.exception("Polling error")
            time.sleep(5)

if __name__ == "__main__":
    main()

import os
import requests
import time
import json

# ==========================================
# 1. إعدادات المسار (The Path to SpinMama)
# ==========================================
# George، التأكد ان المسار يطابق البيانات التي قمت بإ.getByIdها من SpinMama
SPIN_MAMA_DOMAIN = os.getenv("SPINMAMA_DOMAIN", "https://api.spinmama.com") 
# الملاحظة: تأكد من وجود Token الخاص بـ SpinMama إذا اقتصب المنصة
SPIN_MAMA_TOKEN = os.getenv("SPINMAMA_TOKEN") 

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN or not SPIN_MAMA_TOKEN:
    print("Missing Telegram or SpinMama bot token")
    raise SystemExit(1)

URL = f"https://api.telegram.org/bot{TOKEN}/"

def organize_game_data(data):
    """
    دالة لتنظيف وتنسيق بيانات SpinMama القادمة بشكل احترافي
    """
    if not data or not isinstance(data, list):
        return []

    results = []
    for item in data:
        # هنا نأخذ البيانات بناءً على هيكلية SpinMama的标准
        uuid = item.get("uuid") or item.get("id")
        game_name = item.get("game_name", "Aviator")
        result_letter = item.get("result", item.get("outcome")) # إما win/loss أو winness
        multiplier = float(item.get("multiplier", "2.0"))
        balance = item.get("balance_before") # مفيد للمقارنة
        
        results.append({
            "uuid": uuid,
            "game": game_name,
            "result": result_letter, # مثال: Win, Loss, Draw
            "multiplier": multiplier,
            "timestamp": item.get("created_at", item.get("time"))
        })
    
    return results

def broadcast_results(results, group_name="Results Stream"):
    """
    دالة إرسال النتائج في شكل رسالة منسقة
    """
    if not results:
        return

    # تحويل النتائج لخط واحد إن لم تكن كثيرة جداً
    # في حالة النتائج الكثيرة، بعض المستخدمين يفضلون جدولاً، هنا جمعت لسهولة القراءة
    status_map = {
        "win": "🟢 WIN", 
        "loss": "🔴 LOSS", 
        "draw": "🟡 DRAW", 
        "winnings": "💰 WIN" # بعض الألعاب تستخدم Winnings
    }
    
    formatted_lines = []
    
    for index, res in enumerate(results):
        status = status_map.get(res["result"], "❓")
        formatted_lines.append(f"{index + 1}. {status} x {res['multiplier']}")

    final_text = f"🎲 *Results for {group_name}*\n\n" + "\n".join(formatted_lines)

    # الإرسال للجماعة
    requests.post(
        URL + "sendMessage",
        json={
            "chat_id": group_name, # هنا نستخدم اسم المستخدم إذا كان شخصاً واحداً، أو اسم الجماع
            "text": final_text,
            "parse_mode": "Markdown"
        },
        timeout=15
    )

def main():
    offset = 0
    group_chat_id = os.getenv("GROUP_CHAT_ID", "-1001234567890") # تأكد من وضع ID الجماع هنا
    
    print("🚀 Bot started & Ready to fetch SpinMama Data")

    while True:
        try:
            # 1. جلب الرسائل من تيلغرام
            response = requests.get(
                URL + "getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35
            )
            response.raise_for_status()

            data = response.json().get("result", [])

            for update in data:
                chat = update.get("chat", {})
                message = update.get("message", {})
                text = message.get("text", "")
                
                # تحديث الـ Offset لأنه الوحيد المتغير إذا كان الرسالة تأتي واحدة تلو الأخرى
                # ملاحظة: إذا استخدمت الجماع لإرسال النتائج مرة واحدة، ستحتاج لشروط مختلفة قليلاً
                if "update_id" in update and "message" in update:
                    offset = update["update_id"] + 1
                
                if not chat or not text:
                    continue

                # 2. منطق التحليل بناءً على النص الذي أرسل المستخدم
                if text in ["/start", "/new_round"]: #"/new_round" مفيد إذا أردت تحديث النتائج كل جولة
                    # إرسال ترحيب أو "بدء الجولة الحالية"
                    broadcast_results(
                        # هنا نرسل بيانات حديثة من SpinMama، سنضعها في متغير عالمي مثلاً
                        [], # يمكن استبدالها بطلب API حقيقي إذا أردت التحديث التلقائي
                        group_name=f"Game Round {chat['id']}"
                    )
                    
                    reply = (
                        "🟢 البوت حوصل لنتائج SpinMama!"
                        f"\n📊 جاري تحليل جولة {chat['id']}..."
                    )
                    
                    requests.post(
                        URL + "sendMessage",
                        json={
                            "chat_id": chat["id"],
                            "text": reply,
                            "parse_mode": "Markdown"
                        },
                        timeout=15
                    )

                else:
                    # منطق الرد العادي (إذا كان الرد على نفسه أو شيء مشابه)
                    if text.isdigit(): # في حال أرسل المستخدم رقم دمج
                        reply = f"New Ticket: **{text}** analyzed at SpinMama."
                        requests.post(
                            URL + "sendMessage",
                            json={
                                "chat_id": chat["id"],
                                "text": reply,
                                "parse_mode": "Markdown"
                            }
                        )

                # 3. الاتصال بـ SpinMama Vector (عكس السابق - هنا البوت يستدعي النتائج)
                if text == "/fetch": # زر خاص في التيلغرام لطلب النتائج مباشرة
                
                    # استدعاء API الخاص بـ SpinMama الذي حسبناه
                    outcomes_url = f"{SPIN_MAMA_DOMAIN}/outcomes"
                    
                    resp = requests.get(outcomes_url, headers={
                        "Authorization": f"Bearer {SPIN_MAMA_TOKEN}",
                        "Accept": "application/json"
                    }, timeout=45)
                    
                    if resp.status_code == 200:
                        parsed_data = organize_game_data(resp.json())
                        if parsed_data:
                            broadcast_results(parsed_data, group_name="Live Results")
                            
            except Exception as error:
                print("Error captured:", error)
                time.sleep(5)

        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()

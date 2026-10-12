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
                f"{type(error).name}: {error}",
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
                        f"{type(error).name}: {error}"
                    )

        except KeyboardInterrupt:
            break

        except Exception as error:
            print(
                f"Polling error: "
                f"{type(error).name}: {error}"
            )
            time.sleep(15)


if name == "main":
    main()

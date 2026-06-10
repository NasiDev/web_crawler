# -*- coding: utf-8 -*-
"""
Created on Sat Apr 12 14:48:09 2025

@author: Nastaran
"""

import sqlite3
import json

# اتصال به دیتابیس
conn = sqlite3.connect('crawler_results.db')
cursor = conn.cursor()

# بازیابی تمام رکوردها
cursor.execute("SELECT url, positive, neutral, negative, entities, language FROM pages")
rows = cursor.fetchall()

# اگر چیزی پیدا نشد
if not rows:
    print("❌ دیتابیس خالیه! هنوز صفحه‌ای کراول نشده.")
else:
    print(f"✅ {len(rows)} صفحه پیدا شد:\n")
    for row in rows:
        url, pos, neu, neg, entities, lang = row
        print("🌐 URL:", url)
        print("  👍 مثبت:", pos, "| 😐 خنثی:", neu, "| 👎 منفی:", neg)
        print("  🔠 زبان:", lang)
        print("  🧠 موجودیت‌ها:", json.loads(entities) if entities else [])
        print("-" * 60)

# بستن اتصال
conn.close()

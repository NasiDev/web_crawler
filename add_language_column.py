# -*- coding: utf-8 -*-
"""
Created on Sat Apr 12 14:52:29 2025

@author: Nastaran
"""

import sqlite3

conn = sqlite3.connect('crawler_results.db')
cursor = conn.cursor()

# اضافه کردن ستون language اگر وجود نداشته باشه
try:
    cursor.execute("ALTER TABLE pages ADD COLUMN language TEXT")
    print("ستون 'language' با موفقیت اضافه شد.")
except sqlite3.OperationalError as e:
    print("⚠️ ستون وجود داره یا خطا:", e)

conn.commit()
conn.close()

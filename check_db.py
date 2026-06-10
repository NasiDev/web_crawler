# -*- coding: utf-8 -*-
"""
Created on Sat Apr 12 14:42:07 2025

@author: Nastaran
"""

import sqlite3

conn = sqlite3.connect("crawler_results.db")
cursor = conn.cursor()

cursor.execute("SELECT * FROM pages")
rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()

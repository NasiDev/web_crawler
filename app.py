import logging
import base64
from flask import Flask, jsonify, render_template, request, redirect, url_for
from io import BytesIO
import matplotlib.pyplot as plt
import sqlite3
import json
from web_crawler import WebCrawler  # کلاس WebCrawler را از فایل web_crawler ایمپورت می‌کنیم

# Flask setup
app = Flask(__name__)

# مقداردهی اولیه crawler (بیرون از متد run)
config = {
    'start_url': 'https://www.tutorialspoint.com/',  # آدرس شروع
    'max_pages': 100,  # تعداد صفحات برای جستجو
    'delay': 2,  # تاخیر بین درخواست‌ها
    'num_threads': 5,  # تعداد نخ‌ها
    'keywords': ['python', 'web scraping', 'AI', 'machine learning']  # کلمات کلیدی برای جستجو
}

crawler = WebCrawler(config)  # ایجاد شی WebCrawler
crawler.setup_ner_model()  # مدل NER را راه‌اندازی می‌کنیم

# صفحات مختلف وب‌سایت
@app.route('/')
def hello_world():
    return render_template('index.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    query = None
    pages = []
    if request.method == 'POST':
        query = request.form['query']
        for page in crawler.visited:
            if query.lower() in page.lower():
                pages.append(page)
    return render_template('search.html', pages=pages)

@app.route("/start")
def start_crawling():
    crawler.crawl()  # شروع فرایند خزیدن
    return render_template("status.html", message="Crawling started!")

@app.route('/visited_pages')
def visited_pages():
    visited_urls = list(crawler.visited)
    return render_template('visited_pages.html', pages=visited_urls)

@app.route('/dashboard')
def dashboard():
    cursor = crawler.conn.cursor()
    cursor.execute("SELECT * FROM pages")
    pages = cursor.fetchall()

    sentiment_counts = {'positive': 0, 'neutral': 0, 'negative': 0}
    for page in pages:
        sentiment_counts['positive'] += page[1]
        sentiment_counts['neutral'] += page[2]
        sentiment_counts['negative'] += page[3]

    # ایجاد نمودار دایره‌ای برای تحلیل احساسات
    fig, ax = plt.subplots()
    ax.pie(sentiment_counts.values(), labels=sentiment_counts.keys(), autopct='%1.1f%%', startangle=90)
    ax.axis('equal')

    img = BytesIO()
    fig.savefig(img, format='png')
    img.seek(0)
    img_base64 = base64.b64encode(img.getvalue()).decode('utf8')

    return render_template('dashboard.html', img_data=img_base64)

# اجرای اپلیکیشن Flask
if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)

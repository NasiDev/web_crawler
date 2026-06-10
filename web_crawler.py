import logging
import requests
from bs4 import BeautifulSoup
from textblob import TextBlob
from urllib.parse import urljoin, urlparse
import time
import os
from urllib.robotparser import RobotFileParser
from queue import PriorityQueue
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
import spacy
import json
import sqlite3
from flask import Flask, jsonify, render_template, request
from langdetect import detect
import base64
from io import BytesIO
import matplotlib.pyplot as plt
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
from transformers.utils import logging as hf_logging
import spacy

# بارگذاری مدل
nlp = spacy.load("en_core_web_sm")

# Flask app setup
app = Flask(__name__)

# Logging setup
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler('web_crawler.log', 'a', 'utf-8'),
                              logging.StreamHandler()])

hf_logging.set_verbosity_error()  # Suppress warnings from transformers

# WebCrawler class definition
class WebCrawler:
    def __init__(self, config):
        self.config = config
        self.visited = set()
        self.to_visit = PriorityQueue()
        self.to_visit.put((0, self.config['start_url']))
        self.domain = urlparse(self.config['start_url']).netloc
        self.robot_parser = self.setup_robot_parser()
        self.lock = Lock()
        self.setup_database()
        self.setup_ner_model()

    def setup_ner_model(self):
        try:
            self.ner_tokenizer = AutoTokenizer.from_pretrained("Davlan/bert-base-multilingual-cased-ner-hrl")
            self.ner_model = AutoModelForTokenClassification.from_pretrained("Davlan/bert-base-multilingual-cased-ner-hrl")
        except OSError:
            logging.warning("Falling back to local NER model")
            self.ner_tokenizer = AutoTokenizer.from_pretrained("./models/ner-hrl")
            self.ner_model = AutoModelForTokenClassification.from_pretrained("./models/ner-hrl")
        self.ner_pipeline = pipeline("ner", model=self.ner_model, tokenizer=self.ner_tokenizer, grouped_entities=True)

    def setup_database(self):
        self.conn = sqlite3.connect('crawler_results.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute(''' 
            CREATE TABLE IF NOT EXISTS pages (
                url TEXT PRIMARY KEY,
                positive INTEGER,
                neutral INTEGER,
                negative INTEGER,
                entities TEXT,
                images TEXT,
                keyword_matches TEXT,
                language TEXT
            )
        ''')
        self.conn.commit()

    def setup_robot_parser(self):
        robots_url = urljoin(self.config['start_url'], '/robots.txt')
        robot_parser = RobotFileParser()
        robot_parser.set_url(robots_url)
        try:
            robot_parser.read()
        except:
            logging.warning("robots.txt couldn't be read")
        return robot_parser

    def fetch_page(self, url):
        try:
            if not self.robot_parser.can_fetch('*', url):
                logging.info(f"Blocked by robots.txt: {url}")
                return None
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                time.sleep(self.config['delay'])
                return response.text
            else:
                logging.error(f"Failed to fetch {url}: Status code {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching {url}: {e}")
            return None

    def crawl(self):
        crawled_pages = 0
        with ThreadPoolExecutor(max_workers=self.config['num_threads']) as executor:
            futures = []
            while crawled_pages < self.config['max_pages'] and not self.to_visit.empty():
                _, url = self.to_visit.get()
                if url not in self.visited:
                    futures.append(executor.submit(self.process_page, url))
                    crawled_pages += 1

            for future in as_completed(futures):
                pass

    def process_page(self, url):
        logging.info(f"Crawling {url}")
        page_content = self.fetch_page(url)
        if page_content:
            soup = BeautifulSoup(page_content, 'html.parser')
            with self.lock:
                self.visited.add(url)

            images = self.extract_images(soup)
            entities = self.extract_entities(page_content)
            sentiment = self.analyze_sentiment(page_content)
            language = self.detect_language(page_content)
            self.save_page_data(url, sentiment, entities, images, language)

            for link_tag in soup.find_all('a', href=True):
                next_url = urljoin(url, link_tag['href'])
                if self.domain in urlparse(next_url).netloc and next_url not in self.visited:
                    self.to_visit.put((1, next_url))

    def extract_images(self, soup):
        images = []
        for img_tag in soup.find_all('img'):
            src = img_tag.get('src')
            if src:
                img_url = urljoin(self.config['start_url'], src)
                images.append(img_url)
        return images

    def extract_entities(self, content):
        try:
            entities = []
            ner_results = self.ner_pipeline(content)
            for entity in ner_results:
                entities.append(entity['word'])
            return entities
        except Exception as e:
            logging.error(f"NER error: {e}")
            return []

    def analyze_sentiment(self, content):
        blob = TextBlob(content)
        sentiment = {'positive': 0, 'neutral': 0, 'negative': 0}
        for sentence in blob.sentences:
            score = sentence.sentiment.polarity
            if score > 0:
                sentiment['positive'] += 1
            elif score < 0:
                sentiment['negative'] += 1
            else:
                sentiment['neutral'] += 1
        return sentiment

    def detect_language(self, content):
        try:
            return detect(content)
        except:
            return 'unknown'

    def save_page_data(self, url, sentiment, entities, images, language):
        keyword_matches = [k for k in self.config['keywords'] if k.lower() in url.lower()]
        try:
            logging.info(f"Saving data for {url}")
            self.cursor.execute(""" 
                INSERT OR REPLACE INTO pages 
                (url, positive, neutral, negative, entities, images, keyword_matches, language) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (url, 
                  int(sentiment['positive']) if sentiment['positive'] is not None and not isinstance(sentiment['positive'], float) else 0,
                  int(sentiment['neutral']) if sentiment['neutral'] is not None and not isinstance(sentiment['neutral'], float) else 0,
                  int(sentiment['negative']) if sentiment['negative'] is not None and not isinstance(sentiment['negative'], float) else 0,
                  json.dumps(entities), json.dumps(images), json.dumps(keyword_matches), language))
            self.conn.commit()
            logging.info(f"Data saved successfully for {url}")
        except sqlite3.Error as e:
            logging.error(f"DB error: {e} for URL: {url}")

# Flask routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start')
def start_crawl():
    crawler.crawl()
    return render_template('status.html', message="Crawling started!")

@app.route('/search', methods=['GET', 'POST'])
def search():
    query = request.form.get('query', '')
    results = [url for url in crawler.visited if query.lower() in url.lower()]
    return render_template('search.html', pages=results)

@app.route('/status')
def status():
    return jsonify({"visited_pages": len(crawler.visited), "to_visit": crawler.to_visit.qsize()})

@app.route('/dashboard')
def dashboard():
    cursor = crawler.conn.cursor()
    cursor.execute("SELECT * FROM pages")
    pages = cursor.fetchall()

    sentiment_counts = {'positive': 0, 'neutral': 0, 'negative': 0}
    for page in pages:
        try:
            sentiment_counts['positive'] += int(page[1]) if page[1] is not None and not isinstance(page[1], float) else 0
            sentiment_counts['neutral'] += int(page[2]) if page[2] is not None and not isinstance(page[2], float) else 0
            sentiment_counts['negative'] += int(page[3]) if page[3] is not None and not isinstance(page[3], float) else 0
        except (ValueError, TypeError):
            logging.warning(f"Skipping page due to invalid sentiment values: {page[0]}")

    # اگر هیچ داده‌ای موجود نبود، نمایش نده
    if sum(sentiment_counts.values()) == 0:
        return render_template('dashboard.html', img_data=None, message="No sentiment data available.")

    # ساختن نمودار پای
    fig, ax = plt.subplots()
    ax.pie(sentiment_counts.values(), labels=sentiment_counts.keys(), autopct='%1.1f%%', startangle=90)
    ax.axis('equal')

    img = BytesIO()
    fig.savefig(img, format='png')
    img.seek(0)
    img_base64 = base64.b64encode(img.getvalue()).decode('utf8')

    return render_template('dashboard.html', img_data=img_base64, message=None)

@app.route('/visited_pages')
def visited_pages():
    return render_template('visited_pages.html', pages=list(crawler.visited))

if __name__ == '__main__':
    config = {
        'start_url': 'https://www.tutorialspoint.com/',
        'max_pages': 500,
        'delay': 2,
        'num_threads': 4,
        'keywords': ['python', 'tutorial'],
    }
    crawler = WebCrawler(config)
    app.run(debug=True)

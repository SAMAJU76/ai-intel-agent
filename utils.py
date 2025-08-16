from datetime import datetime
from dateutil import parser as dtp, tz

import re, time, json, os, math, hashlib, feedparser, requests, yaml
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
from tenacity import retry, stop_after_attempt, wait_exponential

def load_yaml(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

from dateutil import parser as dtp, tz

def within_days(dt, days, timezone='Asia/Singapore'):
    if not dt:
        return False
    try:
        t = dtp.parse(dt)
    except Exception:
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=tz.UTC)
    t_utc = t.astimezone(tz.UTC)
    now_local = datetime.now(tz.gettz(timezone))
    now_utc = now_local.astimezone(tz.UTC)
    delta = now_utc - t_utc
    return 0 <= delta.days <= days

def clean_html(html):
    soup = BeautifulSoup(html or '', 'html.parser')
    return soup.get_text(' ', strip=True)

def normalize_title(t):
    t = re.sub(r'[^\w\s]', ' ', t.lower())
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def dedupe(items, threshold=92):
    kept = []
    for it in items:
        dup = False
        for k in kept:
            if fuzz.token_set_ratio(normalize_title(it['title']), normalize_title(k['title'])) >= threshold:
                dup = True; break
        if not dup:
            kept.append(it)
    return kept

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def fetch_url(url, timeout=20):
    headers={'User-Agent': 'intel-agent/1.0 (+https://example.com)'}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text

def get_items_from_rss(name, url, days, timezone='Asia/Singapore'):
    feed = feedparser.parse(url)
    items = []
    for e in feed.entries[:100]:
        date = e.get('published') or e.get('updated') or ''
        if date and not within_days(date, days, timezone):
            continue
        items.append({
            'source': name,
            'title': e.get('title', '').strip(),
            'link': e.get('link'),
            'date': date.split('T')[0] if 'T' in date else date,
            'snippet': clean_html(e.get('summary', '') or e.get('description', ''))[:800]
        })
    return items

def get_items_from_page(name, url, days):
    # Minimal fallback: fetch page and extract links (best to replace with site-specific scrapers)
    html = fetch_url(url)
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for a in soup.select('a[href]'):
        title = a.get_text(strip=True)
        href = a['href']
        if not title or len(title) < 30:  # crude filter
            continue
        if href.startswith('/'):
            from urllib.parse import urljoin
            href = urljoin(url, href)
        items.append({
            'source': name,
            'title': title,
            'link': href,
            'date': '',
            'snippet': ''
        })
        if len(items) >= 20:
            break
    return items

def score_item(item, category, weights):
    base = weights.get('base_source_weight', {}).get(category, 1.0)
    kw_bonus = 0.0
    text = f"{item.get('title','')} {item.get('snippet','')}".lower()
    for kw, w in weights.get('keywords', {}).items():
        if kw in text:
            kw_bonus += w - 1.0
    impact = max(1, min(5, round(2.5 + (base - 1.0)*2 + kw_bonus, 1)))
    urgency = 'High' if any(k in text for k in ['outage','vulnerability','critical','emergency','urgent']) else ('Medium' if any(k in text for k in ['regulation','deadline','effective','effective from']) else 'Low')
    return impact, urgency

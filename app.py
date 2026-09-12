"""
EtsyLens - Local Etsy listing research tool
Replicates the core workflow of ListingView.io using live public Etsy data.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://localhost:5000
"""
import re
import json
import time
import statistics
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Simple in-memory cache so repeated lookups in a session are instant
CACHE = {}
CACHE_TTL = 3600  # 1 hour


def cached_get(url, ttl=CACHE_TTL):
    """Fetch a URL with short-lived in-memory caching."""
    now = time.time()
    if url in CACHE and now - CACHE[url]["t"] < ttl:
        return CACHE[url]["html"]
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    CACHE[url] = {"html": resp.text, "t": now}
    return resp.text


def estimate_sales_from_reviews(review_count):
    """
    Industry-standard heuristic: Etsy review rates run roughly 1-in-10 to
    1-in-30 buyers leaving a review. We use a mid-point multiplier (18x)
    and present it as a range, not a hard number.
    """
    if review_count is None:
        return None
    low = int(review_count * 10)
    high = int(review_count * 30)
    mid = int(review_count * 18)
    return {"low": low, "mid": mid, "high": high}


# ---------- Listing scraping ----------

def extract_listing_id(url):
    m = re.search(r"/listing/(\d+)", url)
    return m.group(1) if m else None


def parse_listing(url):
    """Parse an Etsy listing page into a structured dict."""
    html = cached_get(url)
    soup = BeautifulSoup(html, "html.parser")

    data = {
        "url": url,
        "listing_id": extract_listing_id(url),
        "title": None,
        "price": None,
        "currency": None,
        "favorites": None,
        "reviews": None,
        "rating": None,
        "tags": [],
        "shop_name": None,
        "description": None,
        "images": [],
    }

    # Prefer JSON-LD structured data when Etsy provides it
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") == "Product":
                data["title"] = data["title"] or item.get("name")
                offers = item.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                data["price"] = data["price"] or offers.get("price")
                data["currency"] = data["currency"] or offers.get("priceCurrency")
                agg = item.get("aggregateRating") or {}
                if agg:
                    data["rating"] = agg.get("ratingValue")
                    data["reviews"] = agg.get("reviewCount")
                if item.get("image"):
                    imgs = item["image"]
                    data["images"] = imgs if isinstance(imgs, list) else [imgs]

    # Fallbacks via visible DOM when JSON-LD is incomplete
    if not data["title"]:
        h1 = soup.find("h1")
        if h1:
            data["title"] = h1.get_text(strip=True)

    if data["favorites"] is None:
        fav_text = soup.find(string=re.compile(r"favorite", re.I))
        if fav_text:
            m = re.search(r"([\d,]+)", fav_text)
            if m:
                data["favorites"] = int(m.group(1).replace(",", ""))

    shop_link = soup.find("a", href=re.compile(r"/shop/"))
    if shop_link:
        m = re.search(r"/shop/([^/?]+)", shop_link["href"])
        if m:
            data["shop_name"] = m.group(1)

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc:
        data["description"] = meta_desc.get("content")

    # Tags: Etsy exposes them as comma-separated meta keywords on many pages
    meta_kw = soup.find("meta", attrs={"name": "keywords"})
    if meta_kw and meta_kw.get("content"):
        data["tags"] = [t.strip() for t in meta_kw["content"].split(",") if t.strip()]

    data["estimated_sales"] = estimate_sales_from_reviews(data.get("reviews"))
    return data


# ---------- Keyword search scraping ----------

def search_etsy(keyword, max_results=24):
    """Scrape Etsy search results for a keyword: competition + pricing signal."""
    url = f"https://www.etsy.com/search?q={quote_plus(keyword)}"
    html = cached_get(url)
    soup = BeautifulSoup(html, "html.parser")

    results = []
    cards = soup.select("div.v2-listing-card, li.wt-list-unstyled")
    seen = set()

    for card in cards:
        link = card.find("a", href=re.compile(r"/listing/"))
        if not link:
            continue
        href = link.get("href", "").split("?")[0]
        lid = extract_listing_id(href)
        if not lid or lid in seen:
            continue
        seen.add(lid)

        title_el = card.find("h3") or link
        title = title_el.get_text(strip=True) if title_el else None

        price = None
        price_el = card.find(class_=re.compile("currency-value"))
        if price_el:
            price = price_el.get_text(strip=True)

        shop_el = card.find(class_=re.compile("shop-name|wt-text-caption"))
        shop = shop_el.get_text(strip=True) if shop_el else None

        results.append({
            "listing_id": lid,
            "url": href,
            "title": title,
            "price": price,
            "shop": shop,
        })
        if len(results) >= max_results:
            break

    prices = []
    for r in results:
        if r["price"]:
            m = re.search(r"[\d.]+", r["price"].replace(",", ""))
            if m:
                prices.append(float(m.group(0)))

    stats = {
        "result_count_shown": len(results),
        "avg_price": round(statistics.mean(prices), 2) if prices else None,
        "median_price": round(statistics.median(prices), 2) if prices else None,
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
    }

    return {"keyword": keyword, "listings": results, "stats": stats}


# ---------- Shop analysis ----------

def analyze_shop(shop_name, max_listings=48):
    """Aggregate stats across a shop's visible listings."""
    url = f"https://www.etsy.com/shop/{shop_name}?ref=shop-header-name"
    html = cached_get(url)
    soup = BeautifulSoup(html, "html.parser")

    listing_links = soup.find_all("a", href=re.compile(r"/listing/"))
    listing_urls = []
    seen = set()
    for a in listing_links:
        href = a.get("href", "").split("?")[0]
        lid = extract_listing_id(href)
        if lid and lid not in seen:
            seen.add(lid)
            listing_urls.append(href)
        if len(listing_urls) >= max_listings:
            break

    sales_el = soup.find(string=re.compile(r"Sales", re.I))
    total_sales = None
    if sales_el:
        m = re.search(r"([\d,]+)\s*Sales", sales_el, re.I)
        if m:
            total_sales = int(m.group(1).replace(",", ""))

    return {
        "shop_name": shop_name,
        "shop_url": url,
        "total_sales_reported": total_sales,
        "listing_count_found": len(listing_urls),
        "listing_urls": listing_urls,
    }


# ---------- Listing optimizer (SEO scoring) ----------

def score_listing(listing):
    """Score a parsed listing against common Etsy SEO best practices."""
    checks = []
    score = 0
    max_score = 0

    title = listing.get("title") or ""
    max_score += 20
    if len(title) >= 120:
        checks.append({"check": "Title length", "pass": True, "detail": f"{len(title)}/140 chars — strong use of space"})
        score += 20
    elif len(title) >= 80:
        checks.append({"check": "Title length", "pass": True, "detail": f"{len(title)}/140 chars — decent, room to expand"})
        score += 12
    else:
        checks.append({"check": "Title length", "pass": False, "detail": f"Only {len(title)}/140 chars — add more searchable keywords"})

    tags = listing.get("tags") or []
    max_score += 20
    if len(tags) >= 13:
        checks.append({"check": "Tag count", "pass": True, "detail": f"{len(tags)}/13 tags used"})
        score += 20
    else:
        checks.append({"check": "Tag count", "pass": False, "detail": f"Only {len(tags)}/13 tags — use all 13 available slots"})
        score += int(20 * (len(tags) / 13))

    desc = listing.get("description") or ""
    max_score += 15
    if len(desc) >= 300:
        checks.append({"check": "Description depth", "pass": True, "detail": f"{len(desc)} characters — good depth for SEO + buyer confidence"})
        score += 15
    else:
        checks.append({"check": "Description depth", "pass": False, "detail": f"Only {len(desc)} characters — expand with materials, use-case, FAQ"})
        score += int(15 * min(len(desc) / 300, 1))

    images = listing.get("images") or []
    max_score += 15
    if len(images) >= 8:
        checks.append({"check": "Image count", "pass": True, "detail": f"{len(images)}/10 images"})
        score += 15
    else:
        checks.append({"check": "Image count", "pass": False, "detail": f"Only {len(images)}/10 images — Etsy allows up to 10, use them"})
        score += int(15 * (len(images) / 10)) if images else 0

    reviews = listing.get("reviews") or 0
    max_score += 15
    if reviews >= 10:
        checks.append({"check": "Social proof", "pass": True, "detail": f"{reviews} reviews"})
        score += 15
    else:
        checks.append({"check": "Social proof", "pass": False, "detail": f"Only {reviews} reviews — consider a review-generation push"})
        score += int(15 * (reviews / 10))

    price = listing.get("price")
    max_score += 15
    if price:
        checks.append({"check": "Pricing set", "pass": True, "detail": f"Priced at {price} {listing.get('currency') or ''}".strip()})
        score += 15
    else:
        checks.append({"check": "Pricing set", "pass": False, "detail": "Could not detect price"})

    pct = round((score / max_score) * 100) if max_score else 0
    return {"score": score, "max_score": max_score, "percent": pct, "checks": checks}


# ---------- Routes ----------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/listing", methods=["POST"])
def api_listing():
    url = request.json.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        listing = parse_listing(url)
        return jsonify(listing)
    except requests.RequestException as e:
        return jsonify({"error": f"Fetch failed: {e}"}), 502


@app.route("/api/listing/bulk", methods=["POST"])
def api_listing_bulk():
    urls = request.json.get("urls", [])
    results = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        try:
            results.append(parse_listing(url))
        except requests.RequestException as e:
            results.append({"url": url, "error": str(e)})
    return jsonify({"results": results})


@app.route("/api/keyword", methods=["POST"])
def api_keyword():
    keyword = request.json.get("keyword", "").strip()
    if not keyword:
        return jsonify({"error": "No keyword provided"}), 400
    try:
        return jsonify(search_etsy(keyword))
    except requests.RequestException as e:
        return jsonify({"error": f"Fetch failed: {e}"}), 502


@app.route("/api/shop", methods=["POST"])
def api_shop():
    shop_name = request.json.get("shop_name", "").strip()
    if not shop_name:
        return jsonify({"error": "No shop name provided"}), 400
    try:
        return jsonify(analyze_shop(shop_name))
    except requests.RequestException as e:
        return jsonify({"error": f"Fetch failed: {e}"}), 502


@app.route("/api/optimize", methods=["POST"])
def api_optimize():
    url = request.json.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        listing = parse_listing(url)
        report = score_listing(listing)
        return jsonify({"listing": listing, "report": report})
    except requests.RequestException as e:
        return jsonify({"error": f"Fetch failed: {e}"}), 502


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

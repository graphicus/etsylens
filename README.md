# EtsyLens

A local, self-hosted alternative to Etsy research SaaS tools like ListingView.io — built to replicate their core workflow (listing lookup, keyword competition, shop analysis, SEO scoring) using live public Etsy data, with no subscription and no proprietary database.

## The problem

Tools like ListingView.io charge a recurring fee for a workflow that's really four repeatable lookups: pull a listing's stats, check a keyword's competition, snapshot a shop, and score a listing against SEO best practices. Their edge is a crawled database of 130M+ listings — but for a single seller checking their own listings or scouting competitors on demand, that database isn't necessary. Live scraping covers the same ground for the actual day-to-day use case.

## What it does

**Listing Explorer** — Paste one or more listing URLs, get title, price, favorites, reviews, rating, tags, and an estimated sales range (using the standard reviews × multiplier heuristic, since Etsy doesn't expose raw sales counts).

**Keyword Finder** — Enter a search term, get a live competition snapshot: how many results, average/median/price range across the top listings, so you can gauge whether a niche is under- or over-saturated.

**Shop Analyzer** — Enter a shop name, get a snapshot of its visible listing count and reported total sales.

**Listing Optimizer** — Paste a listing URL, get it scored against six SEO checks (title length, tag usage, description depth, image count, review count, pricing) with a percentage score and specific fixes.

## How it's built

- **Backend:** Python/Flask, single-file app (`app.py`)
- **Scraping:** `requests` + `BeautifulSoup`, preferring Etsy's embedded JSON-LD structured data where available and falling back to DOM parsing
- **Caching:** simple in-memory TTL cache to avoid re-fetching the same URL within a session
- **Frontend:** plain HTML/CSS/JS, no build step — a tabbed dashboard served directly by Flask

This was built end-to-end through an AI-directed workflow: the spec, scraping logic, SEO scoring model, and UI were all built through conversational iteration with Claude, then packaged for local use and deployment.

## Live demo & the cloud-IP problem

Live at **[etsylens.onrender.com](https://etsylens.onrender.com)**.

Etsy blocks scraping requests from essentially all cloud/datacenter IP ranges (AWS, GCP, Render, Heroku, etc.) at the network level via bot detection — confirmed by testing the identical request from two separate cloud environments and getting a 403 both times, while the same code works normally from a residential IP.

Rather than let the live demo silently fail with a raw error, the app detects a 403 from Etsy and falls back to clearly-labeled, realistic sample data (`demo: true` in the API response, plus an on-screen banner) so every feature is fully explorable from the deployed link. Run it locally on your own connection and it scrapes real, live Etsy data with no changes needed.

## Running it locally

```bash
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5000**.

## Deploying it

The repo includes a `Procfile` so it deploys as-is to Render, Railway, or any Heroku-style host:

1. Push this folder to a GitHub repo
2. Create a new Web Service on [Render](https://render.com) (free tier works)
3. Connect the repo — Render will detect the `Procfile` and `requirements.txt` automatically
4. Deploy

## Notes & limitations

- Scraping is inherently fragile — Etsy can change its page structure at any time, which may break selectors in `search_etsy` or `analyze_shop`. The Listing Explorer's JSON-LD parsing is the most resilient of the four, since it depends on Etsy's structured data rather than CSS classes.
- Estimated sales are a heuristic (reviews × 10–30), not a guarantee — Etsy doesn't expose true sales counts publicly.
- No rate-limiting or proxy rotation is implemented; heavy use may get temporarily throttled by Etsy. This is intended for personal/light research use, not high-volume scraping.
- The publicly deployed version always serves demo data for the reason described above — this is expected behavior, not a bug.

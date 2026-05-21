import feedparser
import requests
from datetime import datetime, timezone

# 1. Target URL (Crunchyroll's RSS feed for latest episodes)
CRUNCHYROLL_RSS = "https://www.crunchyroll.com/rss/animenews" 
# Note: Swap this with the specific episode/show feed URL if using a premium/session endpoint

# Your Discord Webhook URL (or email API endpoint)
DISCORD_WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK_URL_HERE"

def scan_today_dubs():
    feed = feedparser.parse(CRUNCHYROLL_RSS)
    today = datetime.now(timezone.utc).date()
    released_dubs = []

    print(f"Scanning feed for entries on: {today}")

    for entry in feed.entries:
        # Parse the entry publication date
        # published_parsed structure is a time tuple: (tm_year, tm_mon, tm_mday, ...)
        published_date = datetime(*entry.published_parsed[:3]).date()
        
        if published_date == today:
            title = entry.title.lower()
            # Filter specifically for English Dub releases
            if "english dub" in title or "dubbed" in title:
                released_dubs.append(entry.title)

    if released_dubs:
        send_notification(released_dubs)
    else:
        print("No new English dubs found today.")
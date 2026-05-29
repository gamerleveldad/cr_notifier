import os
import re
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

CALENDAR_URL = "https://www.crunchyroll.com/simulcastcalendar?filter=premium"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
DB_FILE = "anime_tracker.db"

WATCHLIST = [
    "The Beginning After the End",
    "Classroom of the Elite",
    "MARRIAGETOXIN",
    "Witch Hat Atelier",
    "The Klutzy Class Monitor and the Girl with the Short Skirt",
    "Wistoria: Wand and Sword",
    "Snowball Earth",
    "That Time I Got Reincarnated as a Slime",
    "The Warrior Princess and the Barbaric King",
    "Reborn as a Vending Machine, I Now Wander the Dungeon",
    "Daemons of the Shadow Realm"
]
# ──────────────────────────────────────────────────────────────────────────────
def init_db():
    """Initializes the tracking database and creates necessary tables if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS watchlist_schedule (
            anime_name TEXT PRIMARY KEY,
            expected_weekday INTEGER,  -- 0=Monday, 1=Tuesday, ..., 4=Friday, 6=Sunday
            last_seen_date TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS watch_history (
            anime_name TEXT PRIMARY KEY,
            status TEXT,               -- 'Completed', 'Dropped', 'Watching'
            user_rating TEXT           -- 'Liked', 'Disliked'
        )
    ''')
    conn.commit()
    conn.close()
    print("💾 Database initialized successfully.")

def extract_episode_details(episode_item):
    """Scans the episode element to parse numbers, ranges, or special drops."""
    ep_element = episode_item.find(class_=lambda c: c and "episode" in c.lower())
    if not ep_element:
        return "New Drop"
        
    raw_text = ep_element.get_text(strip=True)
    match = re.search(r'(\d+(?:-\d+)?(?:\.\d+)?)', raw_text)
    
    if match:
        found_num = match.group(1)
        if "-" in found_num:
            return f"Episodes {found_num}"
        return f"Episode {found_num}"
        
    clean_fallback = re.sub(r'\s*available\s*', '', raw_text, flags=re.IGNORECASE).strip()
    return clean_fallback if clean_fallback else "New Drop"

def get_weekday_from_label(day_text, now_local):
    """Converts a calendar text label (like '5/29' or 'TODAY') into an integer weekday (0-6)."""
    day_clean = day_text.upper().strip()
    if "TODAY" in day_clean:
        return now_local.weekday()
        
    # Match pattern like '5/29' or '05/29'
    date_match = re.search(r'(\d+)/(\d+)', day_clean)
    if date_match:
        month = int(date_match.group(1))
        day = int(date_match.group(2))
        try:
            # Construct date using current execution year
            target_date = datetime(year=now_local.year, month=month, day=day)
            return target_date.weekday()
        except ValueError:
            pass
            
    return now_local.weekday()

def update_show_schedule(anime_name, weekday_idx, date_str):
    """Saves or updates a show's expected release day in the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO watchlist_schedule (anime_name, expected_weekday, last_seen_date)
        VALUES (?, ?, ?)
        ON CONFLICT(anime_name) DO UPDATE SET
            expected_weekday = excluded.expected_weekday,
            last_seen_date = excluded.last_seen_date
    ''', (anime_name, weekday_idx, date_str))
    conn.commit()
    conn.close()

def check_missing_schedules(found_titles, current_weekday):
    """Compares database schedules against what actually aired today to find anomalies."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Grab all shows that are supposed to air on this weekday index
    cursor.execute(
        "SELECT anime_name FROM watchlist_schedule WHERE expected_weekday = ?", 
        (current_weekday,)
    )
    scheduled_shows = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    missing_alerts = []
    for show in scheduled_shows:
        # Cross-reference against your live list and ensure it's still on your watchlist
        if show not in found_titles and show in WATCHLIST:
            missing_alerts.append(f"- {show} was scheduled to have an episode today but no episodes found.")
            
    return missing_alerts

def scan_live_calendar():
    init_db()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    cookies = {"locale": "en-US"}
    
    print("🛰️ Connecting to Crunchyroll Premium Simulcast Calendar...")
    response = requests.get(CALENDAR_URL, headers=headers, cookies=cookies)
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch calendar. Status Code: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    matched_drops = []
    found_titles_today = set()

    # ─── 2-DAY BACKWARD LOOKING WINDOW ────────────────────────────────────────
    now_local = datetime.now(ZoneInfo("America/New_York"))
    yesterday = now_local - timedelta(days=1)
    
    target_labels = [
        f"{yesterday.month}/{yesterday.day}",
        f"{now_local.month}/{now_local.day}",
        "TODAY"
    ]
    print(f"📅 Scanning calendar columns matching window: {target_labels}\n")
    
    day_blocks = soup.find_all("li", class_="day")

    for day_block in day_blocks:
        day_header = day_block.find("time")
        if not day_header:
            continue
            
        day_text = day_header.get_text(strip=True)
        is_target = any(target.upper() in day_text.upper() for target in target_labels)
        
        if not is_target:
            continue

        print(f"==== Processing Column: {day_text} ====")
        weekday_idx = get_weekday_from_label(day_text, now_local)
        
        episodes = day_block.find_all(["article", "div"], class_=lambda c: c and "release" in c.lower())
        
        for episode in episodes:
            title_element = episode.find(["h1", "cite", "span"], class_=lambda c: c and "title" in c.lower() or "name" in c.lower())
            if not title_element:
                title_element = episode.find(["h1", "cite"])
                
            show_title = title_element.get_text(strip=True) if title_element else "Unknown Title"
            
            lang_element = episode.find(class_=lambda c: c and ("type" in c.lower() or "lang" in c.lower() or "subtitle" in c.lower()))
            lang_text = lang_element.get_text(strip=True) if lang_element else "Subbed"

            if "dub" in lang_text.lower() or "english" in lang_text.lower() or "english" in show_title.lower():
                # Matching logic against your explicit watchlist array
                matched_watchlist_name = next((anime for anime in WATCHLIST if anime.lower() in show_title.lower()), None)
                
                if matched_watchlist_name:
                    episode_string = extract_episode_details(episode)
                    
                    # 1. Update/Learn schedule entry in DB using the clean watchlist title variant
                    update_show_schedule(matched_watchlist_name, weekday_idx, day_text)
                    
                    # Track that it aired successfully today if it falls on our main run day
                    if weekday_idx == now_local.weekday():
                        found_titles_today.add(matched_watchlist_name)
                    
                    clean_entry = (show_title, episode_string)
                    if clean_entry not in matched_drops:
                        print(f"   🎯 MATCH: {show_title} ({episode_string})")
                        matched_drops.append(clean_entry)

    print("\n" + "="*50 + "\n")
    
    # 2. Look up what was supposed to air today vs what actually dropped
    missing_alerts = check_missing_schedules(found_titles_today, now_local.weekday())
    
    # 3. Route everything out to your Discord notification block
    if matched_drops or missing_alerts:
        print("🎉 Updates detected. Routing to Discord...")
        send_discord_notification(matched_drops, missing_alerts)
    else:
        print("❌ Scan complete. No active drops or missing schedule alerts today.")

def send_discord_notification(matches_list, alerts_list):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ Warning: Discord notification skipped. Missing DISCORD_WEBHOOK variable.")
        return

    message_lines = []
    
    # Section 1: Standard Releases
    if matches_list:
        message_lines.append("Daily Dub Anime Drops")
        for title, episode in matches_list:
            message_lines.append(f"- {title}: {episode}")
            
    # Section 2: Missing Anomalies (Your Feature #1 requirement)
    if alerts_list:
        if message_lines:
            message_lines.append("") # Clean spacing block break
        message_lines.append("⚠️ Missed Schedule Alerts")
        message_lines.extend(alerts_list)
        
    message_content = "\n".join(message_lines)
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message_content})
        if response.status_code == 204:
            print("🚀 Discord message delivered successfully!")
        else:
            print(f"⚠️ Discord returned error status code: {response.status_code}")
    except Exception as e:
        print(f"❌ Failed to dispatch web request to Discord: {e}")

if __name__ == "__main__":
    scan_live_calendar()
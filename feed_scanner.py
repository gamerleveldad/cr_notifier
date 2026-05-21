import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo # Built into Python 3.9+
import os

# ─── CONFIGURATION ───────────────────────────────────────────────────────────
# Force the premium query parameters to load the full release grid
CALENDAR_URL = "https://www.crunchyroll.com/simulcastcalendar?filter=premium"

# Replace this string with your actual Discord channel integration Webhook URL
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")

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
    "Reborn as a Vending Machine, I Now Wander the Dungeon"
]
# ──────────────────────────────────────────────────────────────────────────────

def scan_today_calendar():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    cookies = {
        "locale": "en-US"
    }
    
    print("🛰️ Connecting to Crunchyroll Premium Simulcast Calendar...")
    response = requests.get(CALENDAR_URL, headers=headers, cookies=cookies)
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch calendar. Status Code: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    today_matches = []

    # Calculate the precise numeric date string for just today (e.g., "5/20")
    now = datetime.now(ZoneInfo("America/New_York"))
    today_numeric = f"{now.month}/{now.day}"
    
    # Strictly isolate to today's active identifiers
    target_labels = [today_numeric, "TODAY"]
    print(f"📅 Scanning calendar columns matching exactly: {target_labels}\n")
    
    day_blocks = soup.find_all("li", class_="day")

    for day_block in day_blocks:
        day_header = day_block.find("time")
        if not day_header:
            continue
            
        day_text = day_header.get_text(strip=True)
        is_today = any(target.upper() in day_text.upper() for target in target_labels)
        
        # Skip the iteration entirely if the block doesn't belong to today
        if not is_today:
            continue

        print(f"==== Processing Today's Column: {day_text} ====")
        episodes = day_block.find_all(["article", "div"], class_=lambda c: c and "release" in c.lower())
        
        for episode in episodes:
            title_element = episode.find(["h1", "cite", "span"], class_=lambda c: c and "title" in c.lower() or "name" in c.lower())
            if not title_element:
                title_element = episode.find(["h1", "cite"])
                
            show_title = title_element.get_text(strip=True) if title_element else "Unknown Title"
            
            lang_element = episode.find(class_=lambda c: c and ("type" in c.lower() or "lang" in c.lower() or "subtitle" in c.lower()))
            lang_text = lang_element.get_text(strip=True) if lang_element else "Subbed"
            
            ep_num_element = episode.find(class_=lambda c: c and "episode" in c.lower())
            ep_num = ep_num_element.get_text(strip=True) if ep_num_element else "New Drop"

            # Check if the title belongs to your English Dub tracking criteria
            if "dub" in lang_text.lower() or "english" in lang_text.lower() or "english" in show_title.lower():
                
                # Check for an intersection against your custom watchlist entries
                is_on_watchlist = any(anime.lower() in show_title.lower() for anime in WATCHLIST)
                
                if is_on_watchlist:
                    clean_entry = f"**{show_title}** - {ep_num} 🟢"
                    if clean_entry not in today_matches:
                        print(f"   🎯 WATCHLIST MATCH: {show_title} ({ep_num})")
                        today_matches.append(clean_entry)

    print("\n" + "="*50 + "\n")
    if today_matches:
        print(f"🎉 Found {len(today_matches)} tracking matches today. Routing to Discord...")
        send_discord_notification(today_matches)
    else:
        print("❌ Scan complete. No watchlist English dubs aired today.")

def send_discord_notification(matches_list):
    if DISCORD_WEBHOOK_URL == "YOUR_DISCORD_WEBHOOK_URL_HERE":
        print("⚠️ Warning: Discord notification skipped. Set your DISCORD_WEBHOOK_URL string first.")
        return

    # Build a clean markdown message block for the Discord chat interface
    message_content = (
        "🤖 **Daily Crunchyroll Dub Alert** 🤖\n"
        "The following tracked series dropped new English Dub episodes today:\n\n"
        + "\n".join([f"• {item}" for item in matches_list])
    )
    
    payload = {
        "content": message_content
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print("🚀 Discord message delivered successfully!")
        else:
            print(f"⚠️ Discord returned an unexpected status code: {response.status_code}")
    except Exception as e:
        print(f"❌ Failed to dispatch web request to Discord endpoints: {e}")

if __name__ == "__main__":
    scan_today_calendar()
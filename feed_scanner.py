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
    "Reborn as a Vending Machine, I Now Wander the Dungeon",
    "Daemons of the Shadow Realm"
]
# ──────────────────────────────────────────────────────────────────────────────

def extract_episode_details(episode_item):
    """
    Scans the episode element to parse numbers, ranges, or special drops.
    Handles 'Episode X', 'Episodes X-Y', and fallback text cleanly.
    """
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

def scan_live_calendar():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    cookies = {"locale": "en-US"}
    
    print("🛰️ Connecting to Crunchyroll Premium Simulcast Calendar...")
    response = requests.get(CALENDAR_URL, headers=headers, cookies=cookies)
    
    if response.status_code != 200:
        print(f"Failed to fetch calendar. Status Code: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    matched_dubs = []

    # ─── 2-DAY BACKWARD LOOKING WINDOW ────────────────────────────────────────
    now_local = datetime.now(ZoneInfo("America/New_York"))
    yesterday = now_local - timedelta(days=2)
    
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
        episodes = day_block.find_all(["article", "div"], class_=lambda c: c and "release" in c.lower())
        
        for episode in episodes:
            title_element = episode.find(["h1", "cite", "span"], class_=lambda c: c and "title" in c.lower() or "name" in c.lower())
            if not title_element:
                title_element = episode.find(["h1", "cite"])
                
            show_title = title_element.get_text(strip=True) if title_element else "Unknown Title"
            
            lang_element = episode.find(class_=lambda c: c and ("type" in c.lower() or "lang" in c.lower() or "subtitle" in c.lower()))
            lang_text = lang_element.get_text(strip=True) if lang_element else "Subbed"

            if "dub" in lang_text.lower() or "english" in lang_text.lower() or "english" in show_title.lower():
                is_on_watchlist = any(anime.lower() in show_title.lower() for anime in WATCHLIST)
                
                if is_on_watchlist:
                    episode_string = extract_episode_details(episode)
                    
                    # Store as raw data components to keep presentation styling separated
                    clean_entry = (show_title, episode_string)
                    if clean_entry not in matched_dubs:
                        print(f"   🎯 MATCH: {show_title} ({episode_string})")
                        matched_dubs.append(clean_entry)

    print("\n" + "="*50 + "\n")
    if matched_dubs:
        print(f"Found {len(matched_dubs)} matches. Routing to Discord...")
        send_discord_notification(matched_dubs)
    else:
        print("Scan complete. No watchlist English dubs found in this window.")

def send_discord_notification(matches_list):
    if not DISCORD_WEBHOOK_URL:
        print("Warning: Discord notification skipped. Missing DISCORD_WEBHOOK variable.")
        return

    # ─── RESTRUCTURED OUTPUT FORMAT ──────────────────────────────────────────
    message_lines = ["Daily Dub Anime Drops"]
    for title, episode in matches_list:
        message_lines.append(f"- {title}: {episode}")
        
    message_content = "\n".join(message_lines)
    # ──────────────────────────────────────────────────────────────────────────
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message_content})
        if response.status_code == 204:
            print("Discord message delivered successfully!")
        else:
            print(f"Discord returned error status code: {response.status_code}")
    except Exception as e:
        print(f"Failed to dispatch web request to Discord: {e}")

if __name__ == "__main__":
    scan_live_calendar()
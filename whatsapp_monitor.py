#!/usr/bin/env python3
import hashlib
import json
import os
import re
import smtplib
import ssl
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

# Only BSUID page
DOCS_URLS = [
    ("Business Scoped User IDs", "https://developers.facebook.com/documentation/business-messaging/whatsapp/business-scoped-user-ids"),
]

STATE_FILE = "whatsapp_bsuid_state.json"

SENDER_EMAIL = os.getenv("SENDER", "mohdalizahoor@gmail.com")
SENDER_APP_PASSWORD = os.getenv("PASSWORD", "qlwb lerb nwom owna")
RECIPIENT_EMAIL = os.getenv("RECIPIENT", "mohdalizahoor@gmail.com")


def fetch_page(url):
    if not HAS_PLAYWRIGHT:
        print("Playwright not installed")
        return None
        
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page.goto(url, timeout=30000, wait_until="networkidle")
            html = page.content()
            browser.close()
            return clean_html(html)
    except Exception as e:
        print(f"Error: {e}")
        return None


def clean_html(html):
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<header[^>]*>.*?</header>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", "", html)
    html = re.sub(r"\s+", " ", html)
    html = re.sub(r"&\w+;", " ", html)
    html = re.sub(r"\u00a0", " ", html)
    return html.strip()


def hash_content(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_words(content):
    words = re.findall(r'\b[a-zA-Z]{2,}\b', content.lower())
    return set(words)


def get_changes(old_content, new_content):
    old_words = get_words(old_content)
    new_words = get_words(new_content)
    added = new_words - old_words
    removed = old_words - new_words
    return {"added": list(added), "removed": list(removed)}


def send_email(title, url, changes):
    if not SENDER_EMAIL or not SENDER_APP_PASSWORD or not RECIPIENT_EMAIL:
        print("Email not configured")
        return False

    subject = f"BSUID Docs Updated - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    body = f"CHANGE DETECTED: {title}\n"
    body += f"URL: {url}\n\n"
    
    if changes.get("added"):
        body += f"+ NEW WORDS ({len(changes['added'])}):\n"
        for w in changes['added'][:30]:
            body += f"  {w}\n"
        if len(changes['added']) > 30:
            body += f"  ... +{len(changes['added']) - 30} more\n"
    
    if changes.get("removed"):
        body += f"\n- REMOVED WORDS ({len(changes['removed'])}):\n"
        for w in changes['removed'][:30]:
            body += f"  {w}\n"
        if len(changes['removed']) > 30:
            body += f"  ... -{len(changes['removed']) - 30} more\n"
    
    body += f"\nChecked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Email sent to {RECIPIENT_EMAIL}")
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False


def main():
    print(f"[{datetime.now()}] Checking BSUID docs...")
    
    if not HAS_PLAYWRIGHT:
        print("ERROR: Playwright required")
        return
    
    state = load_state()
    
    for title, url in DOCS_URLS:
        print(f"Fetching: {title}...")
        content = fetch_page(url)
        
        if content is None:
            print(f"  Failed to fetch")
            return
        
        content_hash = hash_content(content)
        old_hash = state.get(title, {}).get("hash")
        
        if old_hash != content_hash:
            old_content = state.get(title, {}).get("content", "")
            changes = get_changes(old_content, content)
            
            state[title] = {
                "hash": content_hash,
                "content": content,
                "last_checked": datetime.now().isoformat()
            }
            
            if old_hash:
                print(f"  CHANGE DETECTED! Sending email...")
                send_email(title, url, changes)
            else:
                print(f"  Initial snapshot saved")
                state[title]["content"] = content
        else:
            print(f"  No change")
        
        save_state(state)
    
    print("Done.")


if __name__ == "__main__":
    main()
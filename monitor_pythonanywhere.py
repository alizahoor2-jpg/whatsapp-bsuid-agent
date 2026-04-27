#!/usr/bin/env python3
import hashlib
import json
import os
import re
import smtplib
import ssl
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

DOCS_URLS = [
    ("Business Scoped User IDs", "https://developers.facebook.com/documentation/business-messaging/whatsapp/business-scoped-user-ids"),
]

STATE_FILE = "whatsapp_bsuid_state.json"

SENDER_EMAIL = "mohdalizahoor@gmail.com"
SENDER_APP_PASSWORD = "qlwb lerb nwom owna"
RECIPIENT_EMAIL = "mohdalizahoor@gmail.com"

def fetch_page(url):
    if not HAS_PLAYWRIGHT:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0")
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
    html = re.sub(r"<[^>]+>", "", html)
    html = re.sub(r"\s+", " ", html)
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

def get_sentences(content):
    sentences = re.split(r'(?<=[.!?])\s+', content)
    return set(s for s in sentences if 20 < len(s.strip()) < 500)

def analyze_changes(old_content, new_content):
    old_sent = get_sentences(old_content)
    new_sent = get_sentences(new_content)
    return {"new": list(new_sent - old_sent)}

def send_email(title, url, changes, has_changes=True):
    if not SENDER_EMAIL or not RECIPIENT_EMAIL:
        return False

    if has_changes and changes.get("new"):
        subject = f"BSUID DOCS UPDATED - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        body = "="*70 + "\nBSUID DOCS - NEW CHANGES FOUND\n" + "="*70 + "\n\n"
        body += f"URL: {url}\n"
        body += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        for i, s in enumerate(changes["new"], 1):
            body += f"{i}. {s}\n\n"
    else:
        subject = f"BSUID DOCS CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        body = "="*70 + "\nBSUID DOCS - NO NEW CHANGES\n" + "="*70 + "\n\n"
        body += f"URL: {url}\n"
        body += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        body += "No changes detected.\n"

    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Email sent: {RECIPIENT_EMAIL}")
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False

def main():
    print(f"[{datetime.now()}] Starting BSUID monitor...")
    
    if not HAS_PLAYWRIGHT:
        # Fallback to requests if no playwright (PythonAnywhere may not have it)
        import urllib.request
        try:
            req = urllib.request.Request(
                "https://developers.facebook.com/documentation/business-messaging/whatsapp/business-scoped-user-ids",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                html = response.read().decode("utf-8")
                content = clean_html(html)
        except Exception as e:
            print(f"Fetch error: {e}")
            return
    else:
        content = fetch_page(DOCS_URLS[0][1])
    
    if content is None:
        print("Failed to fetch")
        return
    
    state = load_state()
    title, url = DOCS_URLS[0]
    content_hash = hash_content(content)
    old_hash = state.get(title, {}).get("hash")
    
    if old_hash != content_hash:
        old_content = state.get(title, {}).get("content", "")
        changes = analyze_changes(old_content, content)
        state[title] = {"hash": content_hash, "content": content, "last_checked": str(datetime.now())}
        save_state(state)
        
        if old_hash:
            print("Changes found! Sending email...")
            send_email(title, url, changes, has_changes=True)
        else:
            print("Initial snapshot saved")
    else:
        print("No changes")
        send_email(title, url, {}, has_changes=False)
    
    print("Done.")

if __name__ == "__main__":
    main()
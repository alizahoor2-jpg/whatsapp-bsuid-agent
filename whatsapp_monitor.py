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
        return None, []
        
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page.goto(url, timeout=30000, wait_until="networkidle")
            
            # Get all sections with IDs
            sections = []
            try:
                section_elements = page.query_selector_all("h2[id], h3[id]")
                for sec in section_elements:
                    sid = sec.get_attribute("id")
                    stext = sec.inner_text().strip()
                    if sid and stext:
                        sections.append((sid, stext))
            except:
                pass
            
            html = page.content()
            browser.close()
            return clean_html(html), sections
    except Exception as e:
        print(f"Error: {e}")
        return None, []


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


def get_sentences(content):
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', content)
    sent_set = set()
    for s in sentences:
        s = s.strip()
        if len(s) > 20 and len(s) < 500:
            sent_set.add(s)
    return sent_set


def get_words(content):
    words = re.findall(r'\b[a-zA-Z]{3,}\b', content.lower())
    return set(words)


def get_code_examples(content):
    code_blocks = re.findall(r'```[\s\S]*?```', content)
    return code_blocks


def analyze_changes(old_content, new_content):
    old_sent = get_sentences(old_content)
    new_sent = get_sentences(new_content)
    
    added_sent = new_sent - old_sent
    removed_sent = old_sent - new_sent
    
    return {
        "new_sentences": list(added_sent),
        "removed_sentences": list(removed_sent),
    }


def send_email(title, url, changes, has_changes=True):
    if not SENDER_EMAIL or not SENDER_APP_PASSWORD or not RECIPIENT_EMAIL:
        print("Email not configured")
        return False

    if has_changes:
        subject = f"BSUID DOCS UPDATED - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        body = "=" * 70 + "\n"
        body += "META WHATSAPP BUSINESS SCOPED USER IDS (BSUID) DOCUMENTATION UPDATED\n"
        body += "=" * 70 + "\n\n"
        
        body += f"URL: {url}\n"
        body += f"Checked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        body += "-" * 70 + "\n"
        body += "NEW INFORMATION / UPDATED SENTENCES\n"
        body += "-" * 70 + "\n\n"
        
        if changes.get("new_sentences"):
            body += f"Found {len(changes['new_sentences'])} new/updated sentences:\n\n"
            for i, sent in enumerate(changes["new_sentences"], 1):
                body += f"{i}. {sent}\n\n"
        else:
            body += "No new sentences found.\n"
        
        if changes.get("removed_sentences"):
            body += "\n" + "-" * 70 + "\n"
            body += "REMOVED SECTIONS\n"
            body += "-" * 70 + "\n\n"
            for i, sent in enumerate(changes["removed_sentences"], 1):
                body += f"{i}. {sent}\n\n"
    else:
        subject = f"BSUID DOCS CHECK - NO CHANGES - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        body = "=" * 70 + "\n"
        body += "BSUID DOCS CHECK - NO CHANGES DETECTED\n"
        body += "=" * 70 + "\n\n"
        body += f"URL: {url}\n"
        body += f"Checked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        body += "No changes detected in the last 3 hours.\n\n"
        body += "=" * 70 + "\n"
        body += "Monitoring continues every 3 hours.\n"
        body += "=" * 70 + "\n"

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
    print(f"Email: {SENDER_EMAIL}")
    print(f"Playwright: {HAS_PLAYWRIGHT}")
    
    if not HAS_PLAYWRIGHT:
        print("ERROR: Playwright required")
        return
    
    state = load_state()
    
    for title, url in DOCS_URLS:
        print(f"Fetching: {title}...")
        content, sections = fetch_page(url)
        
        if content is None:
            print(f"  Failed to fetch")
            return
        
        content_hash = hash_content(content)
        old_hash = state.get(title, {}).get("hash")
        
        if old_hash != content_hash:
            old_content = state.get(title, {}).get("content", "")
            changes = analyze_changes(old_content, content)
            
            state[title] = {
                "hash": content_hash,
                "content": content,
                "last_checked": datetime.now().isoformat()
            }
            
            if old_hash:
                print(f"  CHANGE DETECTED! Sending email...")
                send_email(title, url, changes, has_changes=True)
            else:
                print(f"  Initial snapshot saved")
        else:
            print(f"  No change - sending check-in email...")
            send_email(title, url, {}, has_changes=False)
        
        save_state(state)
    
    print("Done.")


if __name__ == "__main__":
    main()
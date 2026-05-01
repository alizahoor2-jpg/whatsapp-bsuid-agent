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
import difflib

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
    html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<header[^>]*>.*?</header>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", "", html)
    html = re.sub(r"\s+", " ", html)
    html = re.sub(r"&\w+;", " ", html)
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


def analyze_lines(old_content, new_content):
    old_lines = old_content.split("\n") if old_content else []
    new_lines = new_content.split("\n") if new_content else []
    
    added_lines = []
    removed_lines = []
    
    for diff_line in difflib.ndiff(old_lines, new_lines):
        if diff_line.startswith("+ "):
            line_text = diff_line[2:].strip()
            if len(line_text) > 5:
                added_lines.append(line_text)
        elif diff_line.startswith("- "):
            line_text = diff_line[2:].strip()
            if len(line_text) > 5:
                removed_lines.append(line_text)
    
    return added_lines, removed_lines


def get_sentences(content):
    sentences = re.split(r'(?<=[.!?])\s+', content)
    sent_set = set()
    for s in sentences:
        s = s.strip()
        if len(s) > 20 and len(s) < 500:
            sent_set.add(s)
    return sent_set


def get_parameters(content):
    params = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*[:=]', content)
    return set(params)


def analyze_changes(old_content, new_content):
    added_lines, removed_lines = analyze_lines(old_content, new_content)
    
    old_sent = get_sentences(old_content)
    new_sent = get_sentences(new_content)
    added_sentences = new_sent - old_sent
    removed_sentences = old_sent - new_sent
    
    old_params = get_parameters(old_content)
    new_params = get_parameters(new_content)
    added_params = new_params - old_params
    removed_params = old_params - new_params
    
    return {
        "added_lines": added_lines,
        "removed_lines": removed_lines,
        "added_sentences": added_sentences,
        "removed_sentences": removed_sentences,
        "added_params": added_params,
        "removed_params": removed_params,
    }


def send_email(title, url, changes, has_changes=True):
    if not SENDER_EMAIL or not SENDER_APP_PASSWORD or not RECIPIENT_EMAIL:
        return False

    if has_changes:
        subject = f"BSUID DOCS UPDATED - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        body = "=" * 80 + "\n"
        body += "BSUID DOCS UPDATED - DETAILED CHANGE REPORT\n"
        body += "=" * 80 + "\n\n"
        body += f"URL: {url}\n"
        body += f"Checked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # ADDED LINES
        body += "=" * 80 + "\n"
        body += f"ADDED LINES ({len(changes['added_lines'])})\n"
        body += "=" * 80 + "\n\n"
        if changes["added_lines"]:
            for i, line in enumerate(changes["added_lines"], 1):
                body += f"  [{i}] {line}\n\n"
        else:
            body += "  (none)\n\n"
        
        # REMOVED LINES
        body += "=" * 80 + "\n"
        body += f"REMOVED LINES ({len(changes['removed_lines'])})\n"
        body += "=" * 80 + "\n\n"
        if changes["removed_lines"]:
            for i, line in enumerate(changes["removed_lines"], 1):
                body += f"  [{i}] {line}\n\n"
        else:
            body += "  (none)\n\n"
        
        # ADDED SENTENCES
        body += "=" * 80 + "\n"
        body += f"ADDED SENTENCES ({len(changes['added_sentences'])})\n"
        body += "=" * 80 + "\n\n"
        if changes["added_sentences"]:
            for i, sent in enumerate(sorted(changes["added_sentences"]), 1):
                body += f"  [{i}] {sent}\n\n"
        else:
            body += "  (none)\n\n"
        
        # REMOVED SENTENCES
        body += "=" * 80 + "\n"
        body += f"REMOVED SENTENCES ({len(changes['removed_sentences'])})\n"
        body += "=" * 80 + "\n\n"
        if changes["removed_sentences"]:
            for i, sent in enumerate(sorted(changes["removed_sentences"]), 1):
                body += f"  [{i}] {sent}\n\n"
        else:
            body += "  (none)\n\n"
        
        # ADDED PARAMETERS
        body += "=" * 80 + "\n"
        body += f"ADDED PARAMETERS ({len(changes['added_params'])})\n"
        body += "=" * 80 + "\n\n"
        if changes["added_params"]:
            for i, param in enumerate(sorted(changes["added_params"]), 1):
                body += f"  [{i}] {param}\n\n"
        else:
            body += "  (none)\n\n"
        
        # REMOVED PARAMETERS
        body += "=" * 80 + "\n"
        body += f"REMOVED PARAMETERS ({len(changes['removed_params'])})\n"
        body += "=" * 80 + "\n\n"
        if changes["removed_params"]:
            for i, param in enumerate(sorted(changes["removed_params"]), 1):
                body += f"  [{i}] {param}\n\n"
        else:
            body += "  (none)\n\n"
        
        # SUMMARY
        body += "=" * 80 + "\n"
        body += "SUMMARY\n"
        body += "=" * 80 + "\n\n"
        total_added = len(changes["added_lines"]) + len(changes["added_sentences"]) + len(changes["added_params"])
        total_removed = len(changes["removed_lines"]) + len(changes["removed_sentences"]) + len(changes["removed_params"])
        body += f"Lines added: {len(changes['added_lines'])} | Lines removed: {len(changes['removed_lines'])}\n"
        body += f"Sentences added: {len(changes['added_sentences'])} | Sentences removed: {len(changes['removed_sentences'])}\n"
        body += f"Parameters added: {len(changes['added_params'])} | Parameters removed: {len(changes['removed_params'])}\n"
        body += f"Total additions: {total_added} | Total removals: {total_removed}\n"
        body += "\n" + "=" * 80 + "\n"
        body += "Monitoring continues every 3 hours.\n"
        body += "=" * 80 + "\n"
    else:
        subject = f"BSUID DOCS CHECK - NO CHANGES - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        body = "=" * 80 + "\n"
        body += "BSUID DOCS CHECK - NO CHANGES\n"
        body += "=" * 80 + "\n\n"
        body += f"URL: {url}\n"
        body += f"Checked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        body += "No new information added. Docs unchanged.\n"
        body += "\n" + "=" * 80 + "\n"
        body += "Monitoring continues every 3 hours.\n"
        body += "=" * 80 + "\n"

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
    
    if not HAS_PLAYWRIGHT:
        print("ERROR: Playwright required")
        return
    
    state = load_state()
    
    for title, url in DOCS_URLS:
        print(f"Fetching: {title}...")
        content = fetch_page(url)
        
        if content is None:
            print("  Failed to fetch")
            return
        
        content_hash = hash_content(content)
        old_hash = state.get(title, {}).get("hash")
        
        if old_hash != content_hash:
            old_content = state.get(title, {}).get("content", "")
            changes = analyze_changes(old_content, content)
            
            state[title] = {"hash": content_hash, "content": content, "last_checked": datetime.now().isoformat()}
            save_state(state)
            
            if old_hash:
                print("  CHANGE DETECTED! Sending email with full details...")
                send_email(title, url, changes, has_changes=True)
            else:
                print("  Initial snapshot saved")
        else:
            print("  No change - sending check-in email...")
            send_email(title, url, {}, has_changes=False)
    
    print("Done.")


if __name__ == "__main__":
    main()

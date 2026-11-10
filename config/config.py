import os

BASE_URL = "https://www.google.com/maps"
HEADLESS_MODE = False
INACTIVITY_TIMEOUT = 120
SLOW_MO = 50
MAX_CONCURRENT_TABS = 9
BUSINESSES_FILE = "dummybusinesses.json"
LOCATIONS_FILE = "dummylocations.json"
TRACKING_FILE = os.path.join("data", "seen_leads.txt")
BATCH_THRESHOLD = 10
SYNC_MANIFEST_FILE = os.path.join("data", "sync_manifest.json")
API_UPLOAD_ENDPOINT = "https://n8n.srv1424798.hstgr.cloud/webhook/scraper-webhook-receiver"
LEADS_DIR = "leads"



SELECTORS = {
    "search_inputs": [
        "input#searchboxinput",
        "input[aria-label*='Search']",
        "input[name='q']",
        "*[role='combobox']"
    ],
    "results_feed": "div[role='feed']",
    "business_links": "a.hfpxzc, div[role='feed'] a[href*='/maps/place/']",
    "business_name": "h1.DUwDvf",
    "business_rating": "div.F7nice span[aria-hidden='true']",
    
   "business_reviews_count": [
        "button[jsaction*='pane.review'] span",
        "div.F7nice span[aria-label]",
        "div.F7nice span:nth-last-child(1)",
        "div.F7nice span:nth-last-child(2)"
    ],
    
    "business_address": "button[data-item-id='address'] div.fontBodyMedium",
    
    "hours_dropdown_button": "button[data-item-id='oh'], div[aria-label*='Hours'], button[aria-label*='Hide open hours']",
    "hours_table_rows": "table.e2W3Xd tr, div.t39Ned",
    "business_hours_fallback": "div[data-item-id='oh'] div.fontBodyMedium",
    
    "business_phone": "button[data-item-id^='phone:'] div.fontBodyMedium",
    "business_website": "a[data-item-id='authority'] div.fontBodyMedium",
    "plus_code": "button[data-item-id='oloc'] div.fontBodyMedium",
    
    "reviews_tab": "button[role='tab'][aria-label*='Reviews'], button[tabindex][jsaction*='tab.reviews']",
    "review_cards": "div.jftiEf",
    "review_stars": "span.kvMYJc",
    "review_text": "span.wi9w8b"
}
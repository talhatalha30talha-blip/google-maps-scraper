import json
import re
import time
import gspread
from google.oauth2.service_account import Credentials
import ollama

# ==================== CONFIGURATION ====================
SERVICE_ACCOUNT_FILE = 'service_account.json'
SPREADSHEET_URL = 'https://docs.google.com/spreadsheets/d/1uRAt9SwWqKMWqtoN0TGgeAwvLkSJMK86ItnbJhiiSgs/edit?usp=sharing'
MODEL_NAME = 'llama3.2'
CPU_THREADS = 2              # Restricts Ollama to 2 CPU threads to prevent 100% CPU spikes
PAUSE_BETWEEN_REVIEWS = 0.5  # Small delay between individual reviews
PAUSE_BETWEEN_LEADS = 1.0    # Cooling pause between leads
# =======================================================

def get_google_spreadsheet():
    """Authenticates and opens the master Google Spreadsheet."""
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_url(SPREADSHEET_URL)

def extract_owner_single_review(review_text):
    """Sends a single review to Llama-3.2 with strict throttling."""
    if not review_text or not str(review_text).strip():
        return None

    messages = [
        {
            'role': 'system',
            'content': 'You are a data extraction assistant. Analyze ONLY the provided review text. Return valid JSON only.'
        },
        {
            'role': 'user',
            'content': f"""
Analyze this single business review. Look for an explicitly named owner, manager, lead doctor, dentist, or practitioner (e.g., "Dr. Catherine Hon", "Dr. John", "Thanks - Mark").

Return your response strictly as valid JSON with a single key "owner_name".
If no name is explicitly found, return {{"owner_name": null}}.
Do not add markdown formatting or extra text.

Review:
{review_text}
"""
        }
    ]

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=messages,
            options={
                'temperature': 0.0,
                'num_thread': CPU_THREADS  # Throttles CPU usage
            }
        )
        
        content = response['message']['content'].strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
            
        data = json.loads(content)
        name = data.get("owner_name")
        return name if name and str(name).lower() != "null" else None
    except Exception as e:
        print(f"    [Ollama Error]: {e}")
        return None

def parse_reviews_field(reviews_raw):
    """Parses raw review content from sheet cells into a clean Python list."""
    if not reviews_raw or not str(reviews_raw).strip():
        return []
    
    if isinstance(reviews_raw, list):
        return reviews_raw

    reviews_str = str(reviews_raw).strip()

    try:
        parsed = json.loads(reviews_str)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass

    cleaned_str = re.sub(r'^\[\s*"|"\s*\]$', '', reviews_str)
    reviews_list = re.split(r'"\s*,\s*"', cleaned_str)
    
    return [r.strip() for r in reviews_list if r.strip()]

def process_all_worksheets():
    """Iterates through every worksheet, lead, and review with granular tracking prints."""
    spreadsheet = get_google_spreadsheet()
    worksheets = spreadsheet.worksheets()

    print(f"Found {len(worksheets)} worksheet(s) in the spreadsheet.")
    total_leads_updated = 0

    for sheet in worksheets:
        print(f"\n==================================================")
        print(f"Processing Sheet: '{sheet.title}'")
        print(f"==================================================")
        
        rows = sheet.get_all_records()
        if not rows:
            print(f"Sheet '{sheet.title}' is empty. Skipping.")
            continue

        headers = sheet.row_values(1)

        if 'Owner Name' not in headers:
            headers.append('Owner Name')
            sheet.update_cell(1, len(headers), 'Owner Name')
            owner_col_idx = len(headers)
        else:
            owner_col_idx = headers.index('Owner Name') + 1

        sheet_updates = []
        sheet_leads_success = 0

        for idx, row in enumerate(rows, start=2):
            current_owner = row.get('Owner Name')
            if current_owner and str(current_owner).strip():
                continue  # Skip already processed rows

            business_name = row.get('Business Name') or row.get('business_name') or f"Row {idx}"
            raw_reviews = row.get('reviews') or row.get('Reviews') or row.get('reviews_list') or ""
            reviews_list = parse_reviews_field(raw_reviews)

            if not reviews_list:
                print(f"  -> Lead [{idx}] '{business_name}': No reviews found. Skipping.")
                continue

            print(f"\n  -> Inspecting Lead [{idx}]: '{business_name}' ({len(reviews_list)} reviews total)")

            found_owner = None
            # Iterate review by review to check precisely
            for rev_idx, review in enumerate(reviews_list, start=1):
                print(f"     [Review {rev_idx}/{len(reviews_list)}] Checking review text...", end="\r")
                extracted_name = extract_owner_single_review(review)
                
                time.sleep(PAUSE_BETWEEN_REVIEWS) # Throttle between individual reviews

                if extracted_name:
                    found_owner = extracted_name
                    print(f"\n     [MATCH FOUND!] Review {rev_idx} revealed owner/doctor: --> {found_owner}")
                    break  # Early exit as soon as name is found for this lead

            if found_owner:
                sheet_leads_success += 1
                total_leads_updated += 1
                print(f"  [SUCCESS] Lead [{idx}] '{business_name}' successfully assigned Owner Name: '{found_owner}'")
                print(f"  [STATUS] Total leads successfully extracted so far in this session: {total_leads_updated}")
                
                sheet_updates.append({
                    'range': gspread.utils.rowcol_to_a1(idx, owner_col_idx),
                    'values': [[found_owner]]
                })
            else:
                print(f"  [NO MATCH] Lead [{idx}] '{business_name}': Scanned all reviews, no name detected.")

            # Hardware cooling pause between leads
            time.sleep(PAUSE_BETWEEN_LEADS)

        # Batch update the worksheet once finished
        if sheet_updates:
            sheet.batch_update(sheet_updates)
            print(f"\n[SHEET COMPLETE] Successfully batch-updated {len(sheet_updates)} record(s) in sheet '{sheet.title}'.")
        else:
            print(f"\n[SHEET COMPLETE] No new names found to update in sheet '{sheet.title}'.")

    print(f"\n==================================================")
    print(f"JOB FINISHED! Successfully extracted owners for {total_leads_updated} total leads across all sheets.")
    print(f"==================================================")

if __name__ == "__main__":
    process_all_worksheets()
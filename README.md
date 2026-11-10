# 🗺️ Automated Multi-Tab Google Maps Lead Generation & AI Review Intelligence Pipeline

A high-performance, asynchronous web scraping, automation, and AI lead enrichment pipeline built with **Python**, **Playwright**, **n8n**, **Ollama (Llama 3.2)**, and **Google Sheets API (gspread)**.

This end-to-end system automatically crawls Google Maps across targeted business categories and locations in parallel, extracts rich lead attributes (including structured weekday hours and $\ge 3$-star reviews), streams batch payloads to an n8n webhook for Google Sheets conversion, and runs an offline LLM processor to extract business owner/practitioner names directly from review texts.

---

## 🌟 Architecture & Workflow Overview

```
 ┌──────────────────────┐      ┌─────────────────────────┐      ┌────────────────────────┐
 │                      │      │                         │      │                        │
 │  Playwright Async    │ ───► │  n8n Webhook Endpoint   │ ───► │   Google Sheets API    │
 │  Google Maps Scraper │      │  Payload Delivery &     │      │   Master Lead Database │
 │                      │      │  Row Ingestion          │      │                        │
 └──────────────────────┘      └─────────────────────────┘      └───────────┬────────────┘
                                                                            │
                                                                            ▼
                                                                ┌────────────────────────┐
                                                                │                        │
                                                                │  Ollama (Llama 3.2)    │
                                                                │  AI Review Processor   │
                                                                │  (Owner Name Enrichment)│
                                                                └────────────────────────┘
```

1. **Scraping Engine:** Multi-tab Playwright workers crawl Google Maps in parallel without triggering bot detections, extracting structured business data and reviews rated $\ge 3$ stars.
2. **Deduplication & Local Storage:** Leads are checked against a persistent $O(1)$ master ledger (`seen_leads.txt`) and saved to hierarchical CSV files (`leads/<State>/<Business>/<Query>.csv`).
3. **Batch Webhook Sync:** When a global threshold (`BATCH_THRESHOLD`) is reached, `SyncManager` formats pending leads into an array-based JSON payload (`[{"name": "query", "leads": [...]}]`) and posts them to an **n8n Webhook**.
4. **n8n & Google Sheets Ingestion:** n8n converts the batch JSON data directly into dynamic Google Sheets worksheets.
5. **AI Review Enrichment:** An offline Llama 3.2 model scans extracted reviews using `ollama` and `gspread` to identify owner, manager, or lead practitioner names (e.g., *"Dr. Catherine Hon"*, *"Mark"*), automatically populating an `Owner Name` column in Google Sheets.

---

## ✨ Key Features

* **⚡ Async Multi-Tab Concurrency:** Uses Playwright's async API and `asyncio.Semaphore` to manage parallel browser tabs cleanly without hardware thrashing.
* **🛡️ Persistent Deduplication Ledger:** Keeps an in-memory `set()` backed by disk storage (`seen_leads.txt`) to eliminate cross-session duplicates.
* **🕒 Structured Weekday Hours & Review Extraction:** Interacts with dynamic DOM accordions to extract structured daily operating hours and filter reviews ($\ge 3$ stars).
* **📦 Direct n8n Integration:** Automatic payload transformation into clean array-based JSON for direct n8n webhook ingestion.
* **🤖 AI-Powered Owner Extraction (Ollama / Llama 3.2):** CPU-throttled local LLM processor that analyzes user reviews for explicitly mentioned owner or practitioner names.
* **📊 Automated Google Sheets Management:** Thread-safe batch cell updating using `gspread` and Google Service Account authentication.

---

## 📁 Project Directory Structure

```
google-maps-scrapper/
│
├── config/                             # ⚙️ Central configuration & CSS selectors
│   ├── __init__.py
│   └── config.py                       # Selectors, concurrency limits, endpoints, & feature flags
│
├── core/                               # 🧠 Core architecture engines
│   ├── __init__.py
│   └── sync_manager.py                 # JSON batching engine & n8n webhook dispatcher
│
├── processes/                          # 🕷️ Web scraping & parsing pipeline
│   ├── __init__.py
│   ├── parser.py                       # DOM parsing logic, weekday hours, & review filters
│   ├── scraper.py                      # Playwright browser engine & infinite scrolling
│   └── storage.py                      # Thread-safe CSV storage & deduplication ledger
│
├── ai_processor/                       # 🤖 AI enrichment pipeline
│   └── review_owner_extractor.py       # Llama 3.2 review scanner & gspread updater
│
├── data/                               # 📁 Target inputs & persistent tracking files
│   ├── businesses.json                 # Production business categories
│   ├── locations.json                  # Production geographic targets
│   ├── dummybusinesses.json            # Dry-run test categories
│   ├── dummylocations.json             # Dry-run test locations
│   ├── seen_leads.txt                  # Persistent deduplication ledger (auto-generated)
│   ├── sync_manifest.json              # Batch manifest ledger (auto-generated)
│   └── service_account.json            # Google Sheets API credentials (USER ADDED)
│
├── leads/                              # 📁 Local CSV output hierarchy
│   └── <State>/
│       └── <Business_Type>/
│           └── <query_name>.csv
│
├── main.py                             # 🚀 Scraper entry point & async orchestrator
├── requirements.txt                    # Python dependencies
└── README.md                           # Documentation
```

---

## 🛠️ Prerequisites & Tech Stack

* **Python 3.9+**
* **Playwright for Python** (Async Chromium browser engine)
* **n8n** (Automation workflow manager & webhook target)
* **Ollama** running locally with the **Llama 3.2** model (`ollama pull llama3.2`)
* **Google Cloud Console** Service Account with Google Sheets API enabled
* **Libraries:** `gspread`, `google-auth`, `ollama`, `requests`, `pandas`, `openpyxl`

---

## 🚀 Installation & Setup Guide

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/google-maps-scrapper.git
cd google-maps-scrapper
```

### 2. Set Up Virtual Environment & Dependencies

* **Windows:**
  ```powershell
  python -m venv venv
  venv\Scripts\activate
  ```

* **macOS / Linux:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

* **Install Python Packages & Playwright Browsers:**
  ```bash
  pip install -r requirements.txt
  playwright install chromium
  ```

### 3. Install & Start Ollama (for AI Review Intelligence)

1. Download and install [Ollama](https://ollama.ai/).
2. Pull the lightweight Llama 3.2 model:
   ```bash
   ollama pull llama3.2
   ```

---

## 🔑 Step-by-Step Google Sheets API Setup

To allow the AI review processor script to read and update your Google Sheets automatically, follow these steps:

### Step 1: Create a Google Cloud Project & Enable APIs
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click **Select a Project** $\rightarrow$ **New Project**, name it `maps-lead-enrichment`, and click **Create**.
3. In the sidebar, select **APIs & Services** $\rightarrow$ **Library**.
4. Search for **Google Sheets API** and click **Enable**.
5. Search for **Google Drive API** and click **Enable**.

### Step 2: Create a Service Account & Credentials
1. Go to **APIs & Services** $\rightarrow$ **Credentials**.
2. Click **+ Create Credentials** at the top and choose **Service Account**.
3. Enter a service account name (e.g., `sheets-writer`) and click **Create and Continue**.
4. Skip optional role assignments and click **Done**.
5. Click on your newly created Service Account email.
6. Navigate to the **Keys** tab, click **Add Key** $\rightarrow$ **Create New Key**.
7. Select **JSON** as the key type and click **Create**.
8. Save the downloaded file to your project's `data/` directory and rename it to:
   ```
   data/service_account.json
   ```

### Step 3: Share Your Google Sheet with the Service Account
1. Open your `data/service_account.json` file and copy the `client_email` address (it looks like `sheets-writer@project-name.iam.gserviceaccount.com`).
2. Open your target Google Sheet in your web browser.
3. Click the green **Share** button in the upper-right corner.
4. Paste the service account email, grant it **Editor** permissions, and click **Share** (uncheck "Notify people").
5. Copy the URL of your Google Sheet and update `SPREADSHEET_URL` in your configuration or AI processor script.

---

## ⚙️ Configuration & Execution

### 1. Configure the Scraper (`config/config.py`)

```python
# Headless browser mode & concurrency settings
HEADLESS_MODE = False
MAX_CONCURRENT_TABS = 3

# Batch threshold triggering auto-upload to n8n webhook
BATCH_THRESHOLD = 10
API_UPLOAD_ENDPOINT = "https://your-n8n-instance.com/webhook/scraper-webhook-receiver"

# Enable review text collection
EXTRACT_REVIEWS = True
```

### 2. Run the Scraper Engine

```bash
python main.py
```

* The scraper populates `leads/`, deduplicates entries against `seen_leads.txt`, and automatically sends JSON batch payloads to n8n when `BATCH_THRESHOLD` leads accumulate.
* Your n8n workflow parses the JSON and populates your Google Sheets tabs.

### 3. Run the AI Owner Extraction Processor

Once leads are populated in Google Sheets, run the Llama 3.2 review extraction script to enrich the records:

```bash
python ai_processor/review_owner_extractor.py
```

#### What the AI Processor Does:
* Connects securely to Google Sheets using `data/service_account.json`.
* Scans rows across all worksheets where `Owner Name` is empty.
* Feeds extracted reviews (`reviews` column) one-by-one to Llama 3.2 via Ollama using a CPU-throttled prompt (`CPU_THREADS = 2`).
* Extracts explicit names (e.g., *"Dr. John"*, *"Manager Mark"*) and returns clean JSON (`{"owner_name": "Name"}`).
* Performs thread-safe `batch_update` calls back to Google Sheets, automatically creating the `Owner Name` header if missing.

---

## 📄 Data Schema Overview

### Webhook & Google Sheets Data Fields

| Field Name | Type | Description |
| :--- | :--- | :--- |
| **Business Name** | `string` | Title of the Google Maps business listing |
| **Rating** | `string` | Aggregate star rating (e.g., `4.8`) |
| **Reviews Count** | `string` | Total number of Google reviews |
| **Address** | `string` | Street address and geographic details |
| **Hours** | `array/string` | Array of formatted weekday operating hours |
| **Phone** | `string` | Formatted U.S. telephone number `(XXX) XXX-XXXX` |
| **Website** | `string` | Official domain / landing page |
| **Plus Code** | `string` | Google Maps Plus Code location code |
| **Reviews** | `array` | JSON array of reviews filtered to $\ge 3$ stars |
| **Owner Name** | `string` | *[AI Enriched]* Extracted owner/practitioner name |

---

## 🛡️ License

Distributed under the MIT License. See `LICENSE` for more information.

import asyncio
import time
import os
import shutil
from playwright.async_api import async_playwright
from config.config import SELECTORS, BASE_URL, HEADLESS_MODE, INACTIVITY_TIMEOUT, SLOW_MO
from processes.parser import GoogleMapsParser
from processes.storage import LeadStorage

class GoogleMapsScraper:
    def __init__(self, query, output_filename):
        self.query = query
        self.output_filename = output_filename
        self.storage = LeadStorage(output_filename)

    async def scroll_results_feed(self, page):
        feed_selector = SELECTORS["results_feed"]
        try:
            await page.evaluate(f"""
                const feed = document.querySelector("{feed_selector}");
                if (feed) {{
                    feed.scrollTop = feed.scrollHeight;
                }}
            """)
        except Exception as e:
            print(f"Error while scrolling: {e}")

    async def run(self, worker_id=1):
        async with async_playwright() as p:
            master_profile_dir = r"\\FS01\UserHome$\Talha.Adeel\Desktop\google-maps-scrapper\scraping_profile"
            worker_profile_dir = r"\\FS01\UserHome$\Talha.Adeel\Desktop\google-maps-scrapper\scraping_profile_worker_" + str(worker_id)
            
            # Efficient Profile Management: Only copy the master profile if the worker folder doesn't exist yet.
            # This prevents heavy 282MB duplication overhead on every scraper restart while keeping sessions logged in.
            if not os.path.exists(worker_profile_dir):
                print(f"[*] Initializing worker {worker_id} profile copy (one-time setup)...")
                shutil.copytree(master_profile_dir, worker_profile_dir, dirs_exist_ok=True)
            else:
                print(f"[*] Reusing existing worker {worker_id} profile (skipping copy)...")
            
            # launch_persistent_context returns the context directly, NOT a browser object
            context = await p.chromium.launch_persistent_context(
                user_data_dir=worker_profile_dir,
                headless=HEADLESS_MODE,
                slow_mo=SLOW_MO,
                args=[
                    "--disable-blink-features=AutomationControlled", 
                    "--start-maximized",
                    "--window-size=1920,1080",
                    # Add these flags to prevent headless session fingerprinting and auth restrictions
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-infobars",
                    "--disable-extensions-except=" + worker_profile_dir,
                    "--enable-automation=false"
                ],
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ignore_default_args=["--enable-automation"]
            )
            
            # Clean up the default blank tab opened by persistent context and use the first active page
            existing_pages = context.pages
            if existing_pages:
                page = existing_pages[0]
                for extra_page in existing_pages[1:]:
                    await extra_page.close()
            else:
                page = await context.new_page()

            print(f"[*] Worker {worker_id} navigating to Google Maps...")
            await page.goto(BASE_URL, timeout=60000)

            try:
                accept_button = page.locator("button:has-text('Accept all'), button:has-text('I agree'), form[action*='consent'] button")
                if await accept_button.count() > 0:
                    await accept_button.first.click()
                    await asyncio.sleep(2)
            except Exception:
                pass

            print(f"[*] Worker {worker_id} searching for query: '{self.query}'")
            search_box_filled = False
            for selector in SELECTORS["search_inputs"]:
                try:
                    locator = page.locator(selector)
                    if await locator.count() > 0:
                        await locator.first.wait_for(state="visible", timeout=5000)
                        await locator.first.fill(self.query)
                        search_box_filled = True
                        break
                except Exception:
                    continue

            if not search_box_filled:
                raise Exception("Could not find search input using any provided selector.")

            await page.keyboard.press("Enter")

            await page.locator(SELECTORS["results_feed"]).wait_for(state="visible", timeout=15000)
            print(f"[*] Worker {worker_id} results feed loaded successfully. Beginning extraction loop...")

            last_lead_time = time.time()
            processed_indices = set()

            while True:
                if time.time() - last_lead_time > INACTIVITY_TIMEOUT:
                    print(f"\n[!] Worker {worker_id}: No new leads found for 2 minutes. Stopping scraper...")
                    break

                links = page.locator(SELECTORS["business_links"])
                count = await links.count()

                for i in range(count):
                    if i in processed_indices:
                        continue

                    processed_indices.add(i)

                    try:
                        item = links.nth(i)
                        await item.scroll_into_view_if_needed()
                        await item.click()
                        await asyncio.sleep(1.5)

                        lead_data = await GoogleMapsParser.parse_business_details(page)
                        saved = await self.storage.save_lead(lead_data)

                        if saved:
                            last_lead_time = time.time()
                            print(f"[Worker {worker_id} Saved] {lead_data.get('name')} | Phone: {lead_data.get('phone')}")
                        else:
                            print(f"[Worker {worker_id} Duplicate Skipped] {lead_data.get('name')}")

                    except Exception as e:
                        print(f"[Worker {worker_id} Error processing listing {i}]: {e}")
                        continue

                await self.scroll_results_feed(page)
                await asyncio.sleep(2)

            await context.close()
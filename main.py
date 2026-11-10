import asyncio
import json
import os
import sys

from processes.scraper import GoogleMapsScraper
from config.config import MAX_CONCURRENT_TABS, BUSINESSES_FILE, LOCATIONS_FILE
from processes.sync_manager import SyncManager

def clean_filename(text):
    return "".join(c if c.isalnum() or c.isspace() else "" for c in text).lower().replace(" ", "_")

async def worker(worker_id, task_queue, semaphore):
    while True:
        task_data = await task_queue.get()
        if task_data is None:
            task_queue.task_done()
            break
            
        query, state_name, business = task_data
        
        async with semaphore:
            folder_path = os.path.join("leads", state_name, business)
            os.makedirs(folder_path, exist_ok=True)
            
            file_name = f"{clean_filename(query)}.csv"
            output_filename = os.path.join(folder_path, file_name)
            
            print(f"\n[Worker {worker_id}] 🚀 Starting task: '{query}'")
            print(f"[Worker {worker_id}] 📁 Target CSV File : '{output_filename}'")
            
            try:
                scraper = GoogleMapsScraper(query=query, output_filename=output_filename)
                # --- FIX: Pass the worker_id so it uses its own isolated profile copy ---
                await scraper.run(worker_id=worker_id)
                print(f"[Worker {worker_id}] ✅ Finished task: '{query}'")
            except Exception as e:
                print(f"[Worker {worker_id}] ❌ Error running task '{query}': {e}")
            finally:
                task_queue.task_done()

async def main():
    print("=" * 70)
    print("       AUTOMATED MULTI-TAB PARALLEL GOOGLE MAPS SCRAPER       ")
    print("=" * 70)

    businesses_path = os.path.join("data", BUSINESSES_FILE)
    locations_path = os.path.join("data", LOCATIONS_FILE)

    if not os.path.exists(businesses_path) or not os.path.exists(locations_path):
        print(f"[!] Error: Could not find '{businesses_path}' or '{locations_path}' in project folder.")
        return

    with open(businesses_path, "r", encoding="utf-8") as f:
        biz_data = json.load(f)
        business_types = biz_data.get("business_types", [])

    with open(locations_path, "r", encoding="utf-8") as f:
        locations_data = json.load(f)

    task_queue = asyncio.Queue()
    task_count = 0

    for state_name, areas in locations_data.items():
        for business in business_types:
            for area in areas:
                query = f"{business} in {area} {state_name}"
                await task_queue.put((query, state_name, business))
                task_count += 1

    print(f"[*] Loaded {task_count} automated search tasks into the queue.")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TABS)

    print(f"[*] Concurrency Limit : {MAX_CONCURRENT_TABS} parallel browser tabs")
    print("-" * 70 + "\n")

    num_workers = MAX_CONCURRENT_TABS
    workers = [
        asyncio.create_task(worker(i + 1, task_queue, semaphore))
        for i in range(num_workers)
    ]

    for _ in range(num_workers):
        await task_queue.put(None)

    await task_queue.join()
    await asyncio.gather(*workers)

    print("\n" + "=" * 70)
    print("       🎉 ALL MULTI-TAB SCRAPING TASKS COMPLETED SUCCESSFULLY!       ")
    print("=" * 70)

    print("\n[Main] Performing final batch sync check for any remaining un-synced leads...")
    sync_worker = SyncManager()
    sync_worker.upload_batch()
    print("[Main] Sync check complete. All data safely processed!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[!] Process manually interrupted by user. Exiting safely...")
        sys.exit(0)
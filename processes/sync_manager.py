import os
import json
import csv
import requests
from config.config import API_UPLOAD_ENDPOINT, SYNC_MANIFEST_FILE

class SyncManager:
    def __init__(self, manifest_file=SYNC_MANIFEST_FILE):
        self.manifest_file = manifest_file
        self.ensure_manifest_exists()

    def ensure_manifest_exists(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.manifest_file)), exist_ok=True)
        if not os.path.exists(self.manifest_file):
            with open(self.manifest_file, mode='w', encoding='utf-8') as f:
                json.dump({"pending_files": [], "completed_batches": []}, f, indent=4)

    def register_file(self, file_path):
        try:
            with open(self.manifest_file, mode='r', encoding='utf-8') as f:
                data = json.load(f)
            
            if file_path not in data["pending_files"]:
                data["pending_files"].append(file_path)
                
            with open(self.manifest_file, mode='w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[Sync Error] Could not register file {file_path} in manifest: {e}")

    def upload_batch(self):
        if not os.path.exists(self.manifest_file):
            return False

        try:
            with open(self.manifest_file, mode='r', encoding='utf-8') as f:
                data = json.load(f)

            pending_files = data.get("pending_files", [])
            if not pending_files:
                print("[Sync Info] No pending files to upload.")
                return True

            print(f"[Sync Info] Preparing array-based JSON batch payload for {len(pending_files)} files...")
            
            batch_payload = []
            valid_files_to_process = []

            for csv_path in pending_files:
                if os.path.exists(csv_path):
                    base_name = os.path.basename(csv_path)
                    query_name = os.path.splitext(base_name)[0]  # Removes '.csv'
                    
                    file_rows = []
                    
                    with open(csv_path, mode='r', encoding='utf-8') as file:
                        reader = csv.reader(file)
                        headers = next(reader, None)
                        if headers:
                            row_count = 0
                            for row in reader:
                                row_count += 1
                                row_dict = {}
                                for i, val in enumerate(row):
                                    if i < len(headers):
                                        header_key = headers[i]
                                        if header_key in ["Hours", "Reviews", "reviews"] and val.startswith("[") and val.endswith("]"):
                                            try:
                                                row_dict[header_key] = json.loads(val)
                                            except Exception:
                                                row_dict[header_key] = val
                                        else:
                                            row_dict[header_key] = val
                                file_rows.append(row_dict)
                            
                            if row_count > 0:
                                batch_payload.append({
                                    "name": query_name,
                                    "leads": file_rows
                                })
                                valid_files_to_process.append(csv_path)
                else:
                    print(f"[Sync Warning] CSV file not found on disk: {csv_path}")

            if not batch_payload:
                print("[Sync Warning] No valid CSV lead data found to upload.")
                return True

            print(f"[Sync Info] Sending array-based JSON batch to endpoint: {API_UPLOAD_ENDPOINT}")
            response = requests.post(API_UPLOAD_ENDPOINT, json=batch_payload, timeout=30)

            if response.status_code == 200:
                print(f"[Sync Success] Batch JSON successfully received by n8n! Response: {response.text}")
                
                headers = [
                    "Business Name", "Rating", "Reviews Count", 
                    "Address", "Hours", "Phone", "Website", "Plus Code", "Reviews"
                ]
                for csv_path in valid_files_to_process:
                    if os.path.exists(csv_path):
                        try:
                            with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
                                writer = csv.writer(f)
                                writer.writerow(headers)
                            print(f"[Sync Info] Cleared sent leads from CSV file: {csv_path}")
                        except Exception as e:
                            print(f"[Sync Warning] Could not clear CSV file {csv_path}: {e}")

                data["completed_batches"].extend(valid_files_to_process)
                data["pending_files"] = []  

                with open(self.manifest_file, mode='w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
                    
                return True
            else:
                print(f"[Sync Error] Endpoint rejected batch. Status Code: {response.status_code}, Response: {response.text}")
                return False

        except requests.exceptions.RequestException as re:
            print(f"[Sync Network Error] Could not reach endpoint {API_UPLOAD_ENDPOINT}: {re}")
            return False
        except Exception as e:
            print(f"[Sync Error] Unexpected error during JSON batch upload: {e}")
            return False
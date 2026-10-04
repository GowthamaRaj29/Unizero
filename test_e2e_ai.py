import requests
import json
import os
import time

BASE_URL = "http://127.0.0.1:8000/api"
AI_URL = "http://127.0.0.1:8001"
DATA_DIR = r"E:\BNP-Chennai-team-33-main\data\OneRecon_DataSet\Current Data\august"

def print_res(res):
    print(f"Status: {res.status_code}")
    try:
        print(json.dumps(res.json(), indent=2))
    except:
        print(res.text)

print("=== AI Ingestion ===")
# 1. FA
res = requests.post(f"{AI_URL}/ingestion/start", json={
    "source": os.path.join(DATA_DIR, "fa_report_202608.csv")
})
print_res(res)
fa_session_id = res.json()["session_id"]

# 2. GL
res = requests.post(f"{AI_URL}/ingestion/start", json={
    "source": os.path.join(DATA_DIR, "gl_report_202608.xml"),
    "xml_record_tag": "Transaction"
})
print_res(res)
gl_session_id = res.json()["session_id"]

# 3. MA
res = requests.post(f"{AI_URL}/ingestion/start", json={
    "source": "http://localhost:5000/api/ma/transactions",
    "page_param": "page",
    "per_page_param": "per_page",
    "per_page": 500,
    "data_key": "data",
    "total_pages_key": "total_pages"
})
print_res(res)
ma_session_id = res.json()["session_id"]

print("Wait for ingestion to complete...")
for s_id in [fa_session_id, gl_session_id, ma_session_id]:
    while True:
        st = requests.get(f"{AI_URL}/ingestion/{s_id}").json()
        if st["status"] != "INGESTING":
            break
        time.sleep(2)
    requests.post(f"{AI_URL}/ingestion/{s_id}/review", json={"action": "GO_AHEAD", "actor": "inv"})

print("=== AI Mapping ===")
res = requests.post(f"{AI_URL}/field-mapping/manual/session", json={
    "session_ids": [fa_session_id, gl_session_id, ma_session_id],
    "crosswalk_path": os.path.join(DATA_DIR, "join_map.txt")
})
print_res(res)
mapping_session_id = res.json()["session_id"]

print("=== Create workflow in backend ===")
res = requests.post(f"{BASE_URL}/auth/login", json={"email": "inv@example.com", "password": "password"})
inv_token = res.json()["token"]
inv_headers = {"Authorization": f"Bearer {inv_token}"}
res = requests.post(f"{BASE_URL}/workflows", json={"name": "E2E Recon", "period": "202608"}, headers=inv_headers)
workflow_id = res.json()["id"]

print("=== Analyze Breaks ===")
res = requests.post(f"{BASE_URL}/ai/workflows/{workflow_id}/analyze", json={
    "mapping_session_id": mapping_session_id
}, headers=inv_headers)
print_res(res)

print("=== Get Breaks ===")
res = requests.get(f"{BASE_URL}/ai/workflows/{workflow_id}/breaks", headers=inv_headers)
print(f"Breaks found: {len(res.json())}")
if len(res.json()) > 0:
    break_id = res.json()[0]["id"]
    print(f"Submitting cause for {break_id}")
    res = requests.post(f"{BASE_URL}/ai/breaks/{break_id}/investigator/cause", json={"cause": "Test cause"}, headers=inv_headers)
    print_res(res)
    
    print("Approver auth")
    res = requests.post(f"{BASE_URL}/auth/login", json={"email": "app@example.com", "password": "password"})
    app_token = res.json()["token"]
    app_headers = {"Authorization": f"Bearer {app_token}"}
    
    print(f"Approving break {break_id}")
    res = requests.post(f"{BASE_URL}/ai/breaks/{break_id}/authorize", json={"comment": "LGTM"}, headers=app_headers)
    print_res(res)

print("End of flow")

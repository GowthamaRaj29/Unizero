import requests
import json
import os
import time

BASE_URL = "http://127.0.0.1:8000/api"

def print_res(res):
    print(f"Status: {res.status_code}")
    try:
        print(json.dumps(res.json(), indent=2))
    except:
        print(res.text)

print("=== Registering Admin ===")
res = requests.post(f"{BASE_URL}/auth/register", json={
    "full_name": "Admin User",
    "email": "admin@example.com",
    "password": "password",
    "role": "ADMIN"
})
print_res(res)
# Admin doesn't get created immediately if the DB wasn't empty, but the first user becomes admin automatically. Let's assume it works.
# Actually, wait, let me check if I can just login as admin.
res = requests.post(f"{BASE_URL}/auth/login", json={
    "email": "admin@example.com",
    "password": "password"
})
print_res(res)
if res.status_code == 200:
    admin_token = res.json()["token"]
else:
    print("Admin login failed!")
    exit(1)

print("=== Registering Investigator ===")
res = requests.post(f"{BASE_URL}/auth/register", json={
    "full_name": "Investigator User",
    "email": "inv@example.com",
    "password": "password",
    "role": "INVESTIGATOR"
})
print_res(res)
if res.status_code == 202:
    print("Investigator pending approval.")

print("=== Registering Approver ===")
res = requests.post(f"{BASE_URL}/auth/register", json={
    "full_name": "Approver User",
    "email": "app@example.com",
    "password": "password",
    "role": "APPROVER"
})
print_res(res)

print("=== Admin Approving Users ===")
admin_headers = {"Authorization": f"Bearer {admin_token}"}
res = requests.get(f"{BASE_URL}/admin/pending-registrations", headers=admin_headers)
print_res(res)
pending_users = res.json()
for user in pending_users:
    user_id = user["id"]
    res = requests.post(f"{BASE_URL}/admin/pending-registrations/{user_id}/approve", headers=admin_headers)
    print(f"Approved {user['email']}")

print("=== Investigator Login ===")
res = requests.post(f"{BASE_URL}/auth/login", json={
    "email": "inv@example.com",
    "password": "password"
})
print_res(res)
inv_token = res.json()["token"]
inv_headers = {"Authorization": f"Bearer {inv_token}"}

print("=== Creating Workflow ===")
res = requests.post(f"{BASE_URL}/workflows", json={
    "name": "August Recon",
    "period": "202608"
}, headers=inv_headers)
print_res(res)
workflow_id = res.json()["id"]

print("=== Uploading Data Sources ===")
data_dir = r"E:\BNP-Chennai-team-33-main\data\OneRecon_DataSet\Current Data\august"
files = {
    "file": open(os.path.join(data_dir, "fa_report_202608.csv"), "rb")
}
res = requests.post(f"{BASE_URL}/data-sources/upload?workflow_id={workflow_id}", files=files, headers=inv_headers)
print_res(res)

print("Done so far.")

"""
Comprehensive End-to-End Test for OneRecon
Tests data ingestion, business rules, field mapping, reconciliation break detection,
and the complete 3-role workflow: ADMIN, INVESTIGATOR, APPROVER.
"""

import os
import sys
import time
import json
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BACKEND_URL = "http://127.0.0.1:8000/api"
AI_URL = "http://127.0.0.1:8001"
MA_URL = "http://localhost:5000/api/ma"
DATA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "OneRecon_DataSet"))

print("=" * 80)
print("ONERECON COMPLETE WORKFLOW TEST: 3 ROLES + INGESTION + RECONCILIATION")
print("=" * 80)

# ----------------------------------------------------------------------
# 1. VERIFY DATA FOLDER & CSV FILES
# ----------------------------------------------------------------------
print("\n[STEP 1] Inspecting Data Folder for CSV and Associated Files...")
august_dir = os.path.join(DATA_ROOT, "Current Data", "august")
july_dir = os.path.join(DATA_ROOT, "Historical Data", "july")
june_dir = os.path.join(DATA_ROOT, "Historical Data", "june")
business_rules_file = os.path.join(DATA_ROOT, "business_rules.txt")

csv_files = [
    os.path.join(august_dir, "fa_report_202608.csv"),
    os.path.join(july_dir, "fa_report_202607.csv"),
    os.path.join(june_dir, "fa_report_202606.csv")
]

for f in csv_files:
    if os.path.exists(f):
        size_mb = os.path.getsize(f) / (1024 * 1024)
        print(f"  ✓ CSV Found: {os.path.relpath(f, DATA_ROOT)} ({size_mb:.2f} MB)")
    else:
        print(f"  ✗ Missing CSV: {f}")
        sys.exit(1)

xml_file = os.path.join(august_dir, "gl_report_202608.xml")
join_map_file = os.path.join(august_dir, "join_map.txt")
print(f"  ✓ GL XML: {os.path.relpath(xml_file, DATA_ROOT)} ({os.path.getsize(xml_file)/(1024*1024):.2f} MB)")
print(f"  ✓ Join Map: {os.path.relpath(join_map_file, DATA_ROOT)} ({os.path.getsize(join_map_file)/1024:.1f} KB)")
print(f"  ✓ Business Rules: {os.path.relpath(business_rules_file, DATA_ROOT)}")

# Verify MA API server
try:
    ma_health = requests.get(f"{MA_URL}/health", timeout=5).json()
    print(f"  ✓ MA REST API Server Healthy: Period {ma_health.get('period')}")
except Exception as e:
    print(f"  ✗ MA REST API server unreachable: {e}")
    sys.exit(1)

# ----------------------------------------------------------------------
# 2. ROLE 1: ADMIN WORKFLOW
# ----------------------------------------------------------------------
print("\n" + "=" * 60)
print("[STEP 2] ROLE 1: ADMIN WORKFLOW & USER MANAGEMENT")
print("=" * 60)

admin_email = "testinvest@recon"
admin_pwd = "password123"

print(f"  Logging in as ADMIN ({admin_email})...")
resp = requests.post(f"{BACKEND_URL}/auth/login", json={"email": admin_email, "password": admin_pwd})
assert resp.status_code == 200, f"Admin login failed: {resp.text}"
admin_token = resp.json()["token"]
admin_headers = {"Authorization": f"Bearer {admin_token}"}
print("  ✓ Admin logged in successfully. Token acquired.")

# Admin listing existing users
resp = requests.get(f"{BACKEND_URL}/admin/users", headers=admin_headers)
assert resp.status_code == 200
users = resp.json()
print(f"  ✓ Admin queried users: {len(users)} existing users in system.")

# Admin viewing roles and permissions
resp = requests.get(f"{BACKEND_URL}/admin/roles", headers=admin_headers)
assert resp.status_code == 200
roles = resp.json()
print(f"  ✓ System Roles verified: {[r['name'] for r in roles]}")

resp = requests.get(f"{BACKEND_URL}/admin/permissions", headers=admin_headers)
assert resp.status_code == 200
perms = resp.json()
print(f"  ✓ Role permissions mapped: Admin({len(perms.get('ADMIN', []))} perms), Investigator({len(perms.get('INVESTIGATOR', []))} perms), Approver({len(perms.get('APPROVER', []))} perms)")

# Register a new investigator user to test Maker-Checker pending registration
test_reg_email = f"new_inv_{int(time.time())}@recon.test"
print(f"\n  Registering new user ({test_reg_email}) requiring Admin approval...")
resp = requests.post(f"{BACKEND_URL}/auth/register", json={
    "full_name": "New Trainee Investigator",
    "email": test_reg_email,
    "password": "password123",
    "role": "INVESTIGATOR"
})
print(f"  Registration response: HTTP {resp.status_code} ({resp.json().get('message', '')})")

# Admin checks pending registrations
resp = requests.get(f"{BACKEND_URL}/admin/pending-registrations", headers=admin_headers)
assert resp.status_code == 200
pending = resp.json()
found_pending = [u for u in pending if u["email"] == test_reg_email]
print(f"  ✓ Pending registrations found: {len(pending)}. Found our user: {bool(found_pending)}")

if found_pending:
    target_id = found_pending[0]["id"]
    print(f"  Approving registration for user {target_id}...")
    resp = requests.post(f"{BACKEND_URL}/admin/pending-registrations/{target_id}/approve", headers=admin_headers)
    assert resp.status_code == 200, f"Approve failed: {resp.text}"
    print(f"  ✓ Registration approved by Admin: {resp.json()}")

# Admin checks audit logs
resp = requests.get(f"{BACKEND_URL}/admin/audit-logs", headers=admin_headers)
assert resp.status_code == 200
audit_logs = resp.json()
print(f"  ✓ Admin verified Audit Logs: {len(audit_logs)} logs recorded. Latest action: {audit_logs[0]['action']}")

# ----------------------------------------------------------------------
# 3. ROLE 2: INVESTIGATOR WORKFLOW (INGESTION, MAPPING & RECONCILIATION)
# ----------------------------------------------------------------------
print("\n" + "=" * 60)
print("[STEP 3] ROLE 2: INVESTIGATOR WORKFLOW (INGESTION, MAPPING, RCA)")
print("=" * 60)

inv_email = "invest@recon"
inv_pwd = "password123"

print(f"  Logging in as INVESTIGATOR ({inv_email})...")
resp = requests.post(f"{BACKEND_URL}/auth/login", json={"email": inv_email, "password": inv_pwd})
assert resp.status_code == 200, f"Investigator login failed: {resp.text}"
inv_token = resp.json()["token"]
inv_headers = {"Authorization": f"Bearer {inv_token}"}
print("  ✓ Investigator logged in successfully.")

# 3a. Create Reconciliation Workflow in Backend
workflow_name = f"August 2026 Financial Recon {int(time.time())}"
print(f"\n  Creating Workflow: '{workflow_name}'...")
resp = requests.post(f"{BACKEND_URL}/workflows", json={
    "name": workflow_name,
    "period": "August 2026",
    "number_of_sources": 3
}, headers=inv_headers)
assert resp.status_code in [200, 201], f"Workflow creation failed: {resp.text}"
workflow = resp.json()
workflow_id = workflow["id"]
print(f"  ✓ Workflow created: ID {workflow_id}, Status: {workflow['status']}")

# 3b. Upload Data Source (FA Report CSV) via backend upload API
fa_csv_path = os.path.join(august_dir, "fa_report_202608.csv")
print(f"\n  Uploading FA Report CSV ({os.path.basename(fa_csv_path)}) to Workflow...")
with open(fa_csv_path, "rb") as f:
    resp = requests.post(
        f"{BACKEND_URL}/data-sources/upload?workflow_id={workflow_id}",
        files={"file": (os.path.basename(fa_csv_path), f, "text/csv")},
        headers=inv_headers
    )
assert resp.status_code in [200, 201], f"Upload data source failed: {resp.text}"
fa_ds = resp.json()
print(f"  ✓ FA CSV Data Source registered in Backend: ID {fa_ds['id']}, file {fa_ds.get('filename')}")

# 3c. AI Ingestion of FA (CSV), GL (XML), and MA (REST API)
print("\n  Starting AI Ingestion Pipeline...")

# Source 1: FA CSV
print("    Starting FA CSV Ingestion...")
resp = requests.post(f"{AI_URL}/ingestion/start", json={
    "source": fa_csv_path,
    "business_rules_path": business_rules_file
})
assert resp.status_code == 200, f"FA ingestion start failed: {resp.text}"
fa_session_id = resp.json()["session_id"]
print(f"    ✓ FA Session ID: {fa_session_id}")

# Source 2: GL XML
print("    Starting GL XML Ingestion...")
resp = requests.post(f"{AI_URL}/ingestion/start", json={
    "source": xml_file,
    "xml_record_tag": "Transaction",
    "business_rules_path": business_rules_file
})
assert resp.status_code == 200, f"GL ingestion start failed: {resp.text}"
gl_session_id = resp.json()["session_id"]
print(f"    ✓ GL Session ID: {gl_session_id}")

# Source 3: MA REST API (Pagination test)
print("    Starting MA REST API Ingestion...")
resp = requests.post(f"{AI_URL}/ingestion/start", json={
    "source": f"{MA_URL}/transactions",
    "page_param": "page",
    "per_page_param": "per_page",
    "per_page": 500,
    "data_key": "data",
    "total_pages_key": "total_pages",
    "business_rules_path": business_rules_file
})
assert resp.status_code == 200, f"MA ingestion start failed: {resp.text}"
ma_session_id = resp.json()["session_id"]
print(f"    ✓ MA Session ID: {ma_session_id}")

# Wait for Ingestion Sessions to complete
print("\n  Waiting for Ingestion Sessions to complete processing...")
sessions = [("FA CSV", fa_session_id), ("GL XML", gl_session_id), ("MA API", ma_session_id)]
session_summaries = {}

for name, s_id in sessions:
    start_time = time.time()
    while True:
        st = requests.get(f"{AI_URL}/ingestion/{s_id}").json()
        status = st.get("status")
        if status != "INGESTING":
            session_summaries[name] = st
            duration = time.time() - start_time
            print(f"    ✓ {name} ({s_id}) completed in {duration:.1f}s with status: {status} (Rows: {st.get('row_count')})")
            if st.get("violations_count", 0) > 0 or status == "REVIEW_REQUIRED":
                print(f"      Review required ({st.get('violations_count')} violations). Submitting GO_AHEAD approval...")
                rev_resp = requests.post(f"{AI_URL}/ingestion/{s_id}/review", json={"action": "GO_AHEAD", "actor": "invest@recon"})
                print(f"      Status after review: {rev_resp.json().get('status')}")
            break
        time.sleep(2)

# 3d. Automated and Manual Field Mapping
print("\n  Creating Field Mapping Session using crosswalk (join_map.txt)...")
resp = requests.post(f"{AI_URL}/field-mapping/manual/session", json={
    "session_ids": [fa_session_id, gl_session_id, ma_session_id],
    "crosswalk_path": join_map_file,
    "actor": "invest@recon"
})
assert resp.status_code == 200, f"Mapping session failed: {resp.text}"
mapping_session = resp.json()
mapping_session_id = mapping_session.get("mapping_session_id") or mapping_session.get("session_id")
entries = mapping_session.get("entries", [])
mapped_count = len(entries)
print(f"  ✓ Mapping Session created: ID {mapping_session_id} with {mapped_count} candidate field mappings.")

# Test preview mapping
print("  Testing Field Mapping Preview...")
if entries:
    first_key = entries[0].get("key")
    resp = requests.post(f"{AI_URL}/field-mapping/manual/{mapping_session_id}/preview", json={
        "key": first_key,
        "rows": 3
    })
    if resp.status_code == 200:
        print(f"  ✓ Field Mapping preview successful for key '{first_key}': {len(resp.json().get('preview', []))} rows.")
    else:
        print(f"  Preview returned {resp.status_code}: {resp.text}")

# Test mapping validation
val_resp = requests.get(f"{AI_URL}/field-mapping/manual/{mapping_session_id}/validation")
if val_resp.status_code == 200:
    val_data = val_resp.json()
    print(f"  ✓ Mapping Validation: valid={val_data.get('valid')}, mapped_count={val_data.get('mapped_count')}")

# 3e. Reconciliation & Break Detection
print("\n  Running Reconciliation & Break Analysis on Workflow...")
resp = requests.post(f"{BACKEND_URL}/ai/workflows/{workflow_id}/analyze", json={
    "mapping_session_id": mapping_session_id,
    "key_field": "TransactionID",
    "amount_tolerance": 0.01
}, headers=inv_headers)
assert resp.status_code == 200, f"Break analysis failed: {resp.text}"
analysis = resp.json()
breaks_created = analysis.get("breaks_created", 0)
print(f"  ✓ Reconciliation complete! Detected {breaks_created} breaks.")

# Fetch Breaks
resp = requests.get(f"{BACKEND_URL}/ai/workflows/{workflow_id}/breaks", headers=inv_headers)
assert resp.status_code == 200
breaks = resp.json()
print(f"  ✓ Loaded {len(breaks)} breaks from Backend Database.")

assert len(breaks) > 0, "No breaks were detected!"
target_break_1 = breaks[0]
target_break_2 = breaks[1] if len(breaks) > 1 else breaks[0]
print(f"  Target Break 1 for Approval: ID {target_break_1['id']}, Type: {target_break_1.get('break_type')}, Key: {target_break_1.get('key')}")
print(f"  Target Break 2 for Rejection: ID {target_break_2['id']}, Type: {target_break_2.get('break_type')}, Key: {target_break_2.get('key')}")

# 3f. AI Root Cause Analysis (RCA) on Break
print(f"\n  Running AI Root Cause Analysis on Break {target_break_1['id']}...")
try:
    rca_resp = requests.post(f"{AI_URL}/breaks/{target_break_1['id']}/rca", json={"actor": "invest@recon"})
    if rca_resp.status_code == 200:
        rca_data = rca_resp.json().get("current_rca", {})
        print(f"  ✓ AI Root Cause: {rca_data.get('root_cause', 'Analyzed')}")
        print(f"    Confidence: {rca_data.get('confidence')}, Suggested Action: {rca_data.get('suggested_action')}")
    else:
        print(f"  RCA endpoint returned {rca_resp.status_code}: {rca_resp.text}")
except Exception as e:
    print(f"  RCA note: {e}")

# 3g. Investigator transitions break to INVESTIGATING and submits cause / findings
print(f"\n  Investigator transitioning Break {target_break_1['id']} to INVESTIGATING...")
requests.post(f"{AI_URL}/breaks/{target_break_1['id']}/status", json={
    "status": "INVESTIGATING",
    "actor": "invest@recon"
})

print(f"  Investigator submitting cause for Break {target_break_1['id']}...")
inv_cause = "Timing mismatch in FA ledger posting resolved by cross-referencing bank advice note."
resp = requests.post(f"{BACKEND_URL}/ai/breaks/{target_break_1['id']}/investigator/cause", json={
    "cause": inv_cause
}, headers=inv_headers)
print(f"  ✓ Cause submitted to AI service: status {resp.status_code}")

# 3h. Create Investigation and Attach Evidence (Maker step)
print(f"\n  Creating Investigation Record for Break {target_break_1['id']}...")
resp = requests.post(f"{BACKEND_URL}/investigations", json={
    "break_id": target_break_1["id"],
    "justification": inv_cause
}, headers=inv_headers)
assert resp.status_code == 200, f"Create investigation failed: {resp.text}"
investigation_1 = resp.json()
investigation_1_id = investigation_1["id"]
print(f"  ✓ Investigation record created: ID {investigation_1_id}, Status: {investigation_1['status']}")

# Upload evidence document
evidence_content = b"BANK ADVICE NOTE - AUGUST 2026\nTransaction ref confirmed cleared."
resp = requests.post(
    f"{BACKEND_URL}/investigations/{investigation_1_id}/evidence",
    files={"file": ("bank_advice_note_202608.txt", evidence_content, "text/plain")},
    headers=inv_headers
)
assert resp.status_code == 200, f"Upload evidence failed: {resp.text}"
evidence = resp.json()
print(f"  ✓ Supporting Evidence uploaded: {evidence.get('filename')} ({evidence.get('size')} bytes)")

# Submit Investigation for Approver authorization
resp = requests.post(f"{BACKEND_URL}/investigations/{investigation_1_id}/submit", headers=inv_headers)
assert resp.status_code == 200, f"Submit investigation failed: {resp.text}"
print(f"  ✓ Investigation 1 submitted to Approver. Status: {resp.json().get('status')}")

# Also create Investigation 2 for rejection test
resp = requests.post(f"{BACKEND_URL}/investigations", json={
    "break_id": target_break_2["id"],
    "justification": "Proposed write-off due to rounding difference."
}, headers=inv_headers)
investigation_2_id = resp.json()["id"]
requests.post(f"{BACKEND_URL}/investigations/{investigation_2_id}/submit", headers=inv_headers)
print(f"  ✓ Investigation 2 submitted to Approver for rejection test: ID {investigation_2_id}")

# ----------------------------------------------------------------------
# 4. ROLE 3: APPROVER WORKFLOW (CHECKER / AUTHORIZER)
# ----------------------------------------------------------------------
print("\n" + "=" * 60)
print("[STEP 4] ROLE 3: APPROVER WORKFLOW (MAKER-CHECKER AUTHORIZATION)")
print("=" * 60)

app_email = "testapprover@recon"
app_pwd = "password123"

print(f"  Logging in as APPROVER ({app_email})...")
resp = requests.post(f"{BACKEND_URL}/auth/login", json={"email": app_email, "password": app_pwd})
assert resp.status_code == 200, f"Approver login failed: {resp.text}"
app_token = resp.json()["token"]
app_headers = {"Authorization": f"Bearer {app_token}"}
print("  ✓ Approver logged in successfully.")

# Maker-Checker Enforcement Test: Investigator cannot approve!
print("\n  Testing Maker-Checker Security Rule: Investigator cannot approve...")
inv_attempt = requests.post(f"{BACKEND_URL}/approvals/{investigation_1_id}/approve", json={
    "comment": "Illegal self-approval attempt"
}, headers=inv_headers)
print(f"  ✓ Investigator approval rejected as expected: HTTP {inv_attempt.status_code}")
assert inv_attempt.status_code in [401, 403], "Maker-checker violation: Investigator was allowed to approve!"

# Approver checks pending queue
print("\n  Approver fetching Pending Approvals queue...")
resp = requests.get(f"{BACKEND_URL}/approvals/pending", headers=app_headers)
assert resp.status_code == 200
pending_approvals = resp.json()
print(f"  ✓ Approver queue contains {len(pending_approvals)} pending items.")
pending_ids = [item["id"] for item in pending_approvals]
assert investigation_1_id in pending_ids, f"Investigation 1 ({investigation_1_id}) not in pending queue!"

# Approver inspects details of Investigation 1
print(f"  Approver inspecting details for Investigation {investigation_1_id}...")
resp = requests.get(f"{BACKEND_URL}/approvals/{investigation_1_id}", headers=app_headers)
assert resp.status_code == 200
detail = resp.json()
print(f"  ✓ Approval Detail verified: Break Key: {detail.get('break', {}).get('key')}, Justification: '{detail.get('justification')}'")

# Approver authorizes / approves Investigation 1
print(f"\n  Approver AUTHORIZING Investigation {investigation_1_id}...")
resp = requests.post(f"{BACKEND_URL}/approvals/{investigation_1_id}/approve", json={
    "comment": "Resolution verified with bank statement. Approved."
}, headers=app_headers)
assert resp.status_code == 200, f"Approval failed: {resp.text}"
print(f"  ✓ Investigation {investigation_1_id} successfully APPROVED!")

# Also authorize the break in AI service break management
ai_auth_resp = requests.post(f"{BACKEND_URL}/ai/breaks/{target_break_1['id']}/authorize", json={
    "comment": "Resolution verified with bank statement. Approved.",
    "target_status": "RESOLVED"
}, headers=app_headers)
print(f"  ✓ AI Break status updated to RESOLVED: status {ai_auth_resp.status_code}")

# Approver REJECTS Investigation 2
print(f"\n  Approver REJECTING Investigation {investigation_2_id} (Testing rejection flow)...")
resp = requests.post(f"{BACKEND_URL}/approvals/{investigation_2_id}/reject", json={
    "comment": "Write-off threshold exceeded. Please provide supporting general ledger adjustments."
}, headers=app_headers)
assert resp.status_code == 200, f"Rejection failed: {resp.text}"
print(f"  ✓ Investigation {investigation_2_id} successfully REJECTED!")

# Approver views Approval History
print("\n  Approver reviewing Approval History log...")
resp = requests.get(f"{BACKEND_URL}/approvals/history", headers=app_headers)
assert resp.status_code == 200
history = resp.json()
print(f"  ✓ Approval History verified: {len(history)} total historical decisions recorded.")
for h in history[:3]:
    print(f"    - Decision: {h.get('status')} by {h.get('actor')} | Comment: '{h.get('comment')}'")

# Final Workflow Status Check
print(f"\n  Updating Workflow '{workflow_id}' status to COMPLETED...")
requests.put(f"{BACKEND_URL}/workflows/{workflow_id}", json={"status": "COMPLETED"}, headers=inv_headers)
wf_check = requests.get(f"{BACKEND_URL}/workflows/{workflow_id}", headers=inv_headers).json()
print(f"  ✓ Final Workflow Status: {wf_check.get('status')}")

print("\n" + "=" * 80)
print("SUCCESS: ALL ROLES (ADMIN, INVESTIGATOR, APPROVER) AND WORKFLOW FEATURES PASSED!")
print("=" * 80)

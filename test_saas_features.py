import sys
import requests

BASE_URL = "http://127.0.0.1:8088"

def run_tests():
    print("==================================================")
    print("🧪 Running AI Call Center SaaS Automated Tests")
    print("==================================================")
    
    # 1. Test Dashboard Data
    res = requests.get(f"{BASE_URL}/api/dashboard_data")
    assert res.status_code == 200, f"Dashboard failed: {res.status_code}"
    data = res.json()
    print("✅ 1. Dashboard API: OK")
    print(f"   - Active Business: {data['active_business']['name']}")
    print(f"   - Current User: {data['current_user']['name']} ({data['current_user']['credits']} credits)")

    # 2. Test Business Profile Switch to Automotive
    res = requests.post(f"{BASE_URL}/api/business_profiles/select", json={"template_id": "automotive"})
    assert res.status_code == 200, "Select automotive template failed"
    biz = res.json()["active_profile"]
    assert biz["id"] == "automotive"
    print(f"✅ 2. Business Profile Switch: OK -> {biz['name']} (Agent: {biz['agent_name']})")

    # 3. Test Voice Preview
    res = requests.post(f"{BASE_URL}/api/preview_voice", json={"voice_id": "th-TH-NiwatNeural", "speed": 1.0})
    assert res.status_code == 200, "Preview voice failed"
    assert res.json().get("audio_url"), "No audio url returned"
    print(f"✅ 3. Voice Preview API: OK -> Audio generated at {res.json()['audio_url']}")

    # 4. Test PromptPay QR Generation
    res = requests.post(f"{BASE_URL}/api/topup/promptpay_qr", json={"amount": 300, "package_id": "pkg_300"})
    assert res.status_code == 200, "PromptPay QR failed"
    pp = res.json()
    assert "qr_image_url" in pp and "reference_id" in pp
    print(f"✅ 4. PromptPay QR Generator: OK -> Ref: {pp['reference_id']}, Amount: {pp['amount']} THB (+{pp['credits_to_add']} credits)")

    # 5. Test PromptPay Instant Top-up Simulation
    init_credits = requests.get(f"{BASE_URL}/api/credits").json()["credits"]
    res = requests.post(f"{BASE_URL}/api/topup/confirm", json={
        "amount": 300,
        "credits_to_add": 330,
        "reference_id": pp["reference_id"]
    })
    assert res.status_code == 200, "Top-up confirmation failed"
    new_credits = res.json()["credits"]
    assert new_credits == init_credits + 330, f"Credits mismatch: {new_credits} vs {init_credits + 330}"
    print(f"✅ 5. PromptPay Instant Confirmation: OK -> Credits: {init_credits} -> {new_credits}")

    # 6. Test RBAC Switch User to Admin
    res = requests.post(f"{BASE_URL}/api/switch_user", json={"role": "admin"})
    assert res.status_code == 200, "Switch to admin failed"
    assert res.json()["current_user"]["role"] == "admin"
    print(f"✅ 6. RBAC Role Switch: OK -> Switched to {res.json()['current_user']['name']}")

    # 7. Test Customer Queue
    res = requests.post(f"{BASE_URL}/api/customers", json={
        "name": "คุณวิชัย กุลธร",
        "phone": "081-999-8877",
        "detail": "นัดนำรถเข้าตรวจเช็คระยะ 50,000 กม.",
        "scheduled_time": "พรุ่งนี้ 10:00 น."
    })
    assert res.status_code == 200, "Add customer failed"
    cust_id = res.json()["customer"]["id"]
    print(f"✅ 7. Customer Queue & Scheduler: OK -> Added queue item {cust_id}")

    # 8. Test Call Start with Automotive Persona
    res = requests.post(f"{BASE_URL}/api/start_call", json={
        "name": "คุณวิชัย",
        "phone": "081-999-8877",
        "detail": "นัดเช็คระยะ 50,000 กม."
    })
    assert res.status_code == 200, "Start call failed"
    call_data = res.json()
    print(f"✅ 8. Start Call with Dynamic Persona: OK -> Agent: {call_data['agent_name']} ({call_data['business_name']})")
    print(f"   - Opening speech: {call_data['speech']}")

    # Switch back to clinic as default
    requests.post(f"{BASE_URL}/api/business_profiles/select", json={"template_id": "clinic"})
    requests.post(f"{BASE_URL}/api/switch_user", json={"role": "owner"})

    print("==================================================")
    print("🎉 ALL 8 SAAS SUITE TESTS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()

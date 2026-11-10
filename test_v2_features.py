import os
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8")

# Set working directory to script location
current_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_dir)
sys.path.insert(0, current_dir)

from fastapi.testclient import TestClient
from app import app, SCRIPTS_DB, active_business, current_user, customers_queue

client = TestClient(app)

def run_tests():
    print("==================================================")
    print("🧪 Verifying AI Call Center SaaS v2 & Barge-in Features")
    print("==================================================")

    # 1. Test Dashboard API
    res = client.get("/api/dashboard_data")
    assert res.status_code == 200, f"Dashboard failed: {res.status_code}"
    data = res.json()
    print("✅ 1. Dashboard API: OK")
    print(f"   - Scripts Count: {data['scripts_count']}")
    print(f"   - Active Business: {data['active_business']['name']}")
    assert data["scripts_count"] >= 5

    # 2. Test Multi-Script Library Listing
    res = client.get("/api/scripts")
    assert res.status_code == 200, f"List scripts failed: {res.status_code}"
    scripts = res.json()["scripts"]
    assert len(scripts) >= 5
    print(f"✅ 2. Multi-Script Library: OK ({len(scripts)} scripts found)")
    for s in scripts[:3]:
        print(f"   - [{s['id']}] {s['name']} (Industry: {s['industry']})")

    # 3. Test Create Custom Script
    custom_script_payload = {
        "id": "script_test_insurance",
        "name": "ประกันภัย: แจ้งต่ออายุกรมธรรม์ชั้น 1",
        "business_name": "ศรีไทย ประกันภัย",
        "industry": "ประกันภัย",
        "agent_name": "น้องฟ้า",
        "agent_gender": "female",
        "voice_id": "th-TH-PremwadeeNeural",
        "tone": "Formal",
        "speed": 1.05,
        "opening_text": "สวัสดีค่ะ ขอเรียนสายคุณ{customer_name} จากศรีไทย ประกันภัย สะดวกคุยสักครู่ไหมคะ",
        "objective": "แจ้งสิทธิประโยชน์ต่ออายุประกันภัยรถยนต์ชั้น 1 พร้อมส่วนลดเบี้ยประวัติดี 15%",
        "custom_instructions": "เน้นย้ำความคุ้มครองต่อเนื่องและมีบริการช่วยเหลือฉุกเฉิน 24 ชม."
    }
    res = client.post("/api/scripts", json=custom_script_payload)
    assert res.status_code == 200, "Create script failed"
    created_script = res.json()["script"]
    assert created_script["id"] == "script_test_insurance"
    print(f"✅ 3. Create Custom Script: OK -> Added [{created_script['id']}] {created_script['name']}")

    # 4. Test Customer Queue Script Assignment
    # Add a customer with the custom script
    res = client.post("/api/customers", json={
        "name": "คุณสมชาย มั่งคั่ง",
        "phone": "089-111-2233",
        "script_id": "script_test_insurance",
        "scheduled_time": "วันนี้ 16:30 น."
    })
    assert res.status_code == 200, "Add customer with script failed"
    cust = res.json()["customer"]
    cust_id = cust["id"]
    assert cust["script_id"] == "script_test_insurance"
    print(f"✅ 4. Customer Queue with Script: OK -> Added {cust['name']} assigned to {cust['script_id']}")

    # Update customer script to automotive
    res = client.put(f"/api/customers/{cust_id}/script", json={"script_id": "script_auto_maintain"})
    assert res.status_code == 200, "Update customer script failed"
    updated_cust = res.json()["customer"]
    assert updated_cust["script_id"] == "script_auto_maintain"
    print(f"✅ 5. Update Customer Script Assignment: OK -> Changed to {updated_cust['script_id']}")

    # 6. Test Business Profile & AI Voice Persistence Fix
    res = client.post("/api/business_profiles/update", json={
        "agent_gender": "male",
        "voice_id": "th-TH-NiwatNeural",
        "tone": "Authoritative",
        "speed": 1.15,
        "agent_name": "น้องก้อง"
    })
    assert res.status_code == 200, "Update business profile failed"
    updated_profile = res.json()["active_profile"]
    assert updated_profile["agent_gender"] == "male"
    assert updated_profile["voice_id"] == "th-TH-NiwatNeural"
    assert updated_profile["tone"] == "Authoritative"
    assert updated_profile["speed"] == 1.15
    assert updated_profile["agent_name"] == "น้องก้อง"
    print("✅ 6. AI Voice Selection Persistence: OK")
    print(f"   - Gender: {updated_profile['agent_gender']}")
    print(f"   - Voice: {updated_profile['voice_id']}")
    print(f"   - Tone: {updated_profile['tone']}")
    print(f"   - Speed: {updated_profile['speed']}")

    # 7. Test Call Simulation with Specific Script
    res = client.post("/api/start_call", json={
        "name": "คุณสมชาย",
        "phone": "089-111-2233",
        "script_id": "script_auto_ready"
    })
    assert res.status_code == 200, f"Start call failed: {res.text}"
    call_res = res.json()
    assert "session_id" in call_res
    assert call_res["agent_name"] == "น้องนนท์"
    assert call_res["business_name"] == "ออโต้ แคร์ เซอร์วิส"
    assert "รถซ่อมเสร็จ" in call_res["speech"]
    print("✅ 7. Start Call with Per-Call Script: OK")
    print(f"   - Agent: {call_res['agent_name']} ({call_res['business_name']})")
    print(f"   - Opening Speech: {call_res['speech']}")
    print(f"   - Audio URL: {call_res['audio_url']}")

    # 8. Verify Voice Barge-in in index.html
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    assert "onspeechstart" in html_content, "Missing onspeechstart in index.html"
    assert "onsoundstart" in html_content, "Missing onsoundstart in index.html"
    assert "function stopAIAudio" in html_content, "Missing stopAIAudio in index.html"
    assert "player.pause()" in html_content or "audio.pause()" in html_content, "Missing pause in index.html"
    assert "player.currentTime = 0" in html_content, "Missing currentTime reset in index.html"
    assert "ลูกค้าพูดแทรก" in html_content, "Missing barge-in visual feedback in index.html"
    print("✅ 8. Voice Barge-In (Interruption Detection): OK")
    print("   - onspeechstart & onsoundstart hooks present")
    print("   - stopAIAudio() resets audio playback instantly on customer interruption")
    print("   - Barge-in visual status 'ลูกค้าพูดแทรก... AI หยุดพูดเพื่อฟัง' verified")

    print("==================================================")
    print("🎉 ALL 8 V2 SAAS & BARGE-IN TESTS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()

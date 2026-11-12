import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

current_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_dir)
sys.path.insert(0, current_dir)

from fastapi.testclient import TestClient
from app import app, TELEPHONY_PROVIDERS

client = TestClient(app)


def run_tests():
    print("==================================================")
    print("🧪 Verifying NT NextGen Link VoIP Outbound Config v5")
    print("==================================================")

    res = client.get("/api/telephony/config")
    assert res.status_code == 200, f"GET /api/telephony/config failed: {res.status_code}"
    data = res.json()
    cfg = data["config"]

    assert cfg["provider"] == "nt_link", f"Expected nt_link, got {cfg['provider']}"
    assert cfg["provider_name"] == "NT Link VoIP (NT NextGen)"
    assert cfg["server_host"] == "sip.ntnextgen.com", f"Unexpected host: {cfg['server_host']}"
    assert cfg["server_port"] == 5060
    assert cfg["sip_proxy"] == "res.ntnextgen.com", f"Unexpected proxy: {cfg['sip_proxy']}"
    assert cfg["auth_username"] == "021078407", f"Unexpected username: {cfg['auth_username']}"
    assert cfg["auth_password"] == "8vEpQ5R3#hSm", "VoIP Devices password mismatch"
    assert cfg["app_password"] == "H5F@P87h", "Link App password mismatch"
    assert cfg["caller_id"] == "02-107-8407"
    assert cfg["phone_number"] == "021078407"
    assert cfg["account_balance"] == 100.00
    assert cfg["account_expiry"] == "2027-01-17"
    assert cfg["account_status"] == "พร้อมใช้งาน"
    print("✅ 1. Default NT NextGen SIP Trunk Credentials Verified:")
    print(f"   - SIP Domain: {cfg['server_host']}:{cfg['server_port']}")
    print(f"   - SIP Proxy: {cfg['sip_proxy']}")
    print(f"   - Username / Number: {cfg['auth_username']} (Caller ID: {cfg['caller_id']})")
    print(f"   - Balance: {cfg['account_balance']:.2f} THB | Expiry: {cfg['account_expiry']} | Status: {cfg['account_status']}")

    for key, prov in data["providers"].items():
        for field in ["sip_proxy", "app_password", "account_balance", "account_expiry", "account_status"]:
            assert field in prov, f"Provider {key} missing field {field}"
    print("✅ 2. Provider Registry Schema Consistency Verified across all 4 presets")

    ping_res = client.post("/api/telephony/test_connection", json={})
    assert ping_res.status_code == 200
    ping_data = ping_res.json()
    assert ping_data["success"] is True
    assert ping_data["status"] == "registered"
    assert "sip.ntnextgen.com:5060" in ping_data["message"]
    assert "res.ntnextgen.com" in ping_data["message"]
    assert "021078407" in ping_data["message"]
    print("✅ 3. SIP OPTIONS Ping with Outbound Proxy Verified:")
    print(f"   - {ping_data['message']}")

    call_res = client.post("/api/start_call", json={
        "name": "คุณธนกฤต วงศ์สวัสดิ์",
        "phone": "081-999-8877",
        "detail": "ทดสอบโทรออกผ่านคู่สาย NT NextGen Link VoIP 021078407"
    })
    assert call_res.status_code == 200
    call_data = call_res.json()
    assert "NT Link VoIP (NT NextGen)" in call_data["trunk_route"]
    assert "02-107-8407" in call_data["trunk_route"]
    print("✅ 4. Outbound Call Routing via NT Link VoIP Verified:")
    print(f"   - Active Trunk Route: {call_data['trunk_route']}")

    html_content = Path("index.html").read_text(encoding="utf-8")
    for required_id in [
        'id="telephony-proxy"',
        'id="telephony-app-password"',
        'id="telephony-balance"',
        'id="telephony-expiry"',
        'id="telephony-live-proxy"',
        'id="telephony-live-username"',
        'id="telephony-live-balance"',
        'id="telephony-live-expiry"',
        'id="telephony-live-acc-status"',
        'toggleTelephonyPassword'
    ]:
        assert required_id in html_content, f"Missing UI element or handler in index.html: {required_id}"
    assert "sip.ntnextgen.com" in html_content
    assert "res.ntnextgen.com" in html_content
    assert "02-107-8407" in html_content
    print("✅ 5. Frontend UI Controls & Live Status Display Verified in index.html")

    print("==================================================")
    print("🎉 ALL 5 NT LINK VOIP TESTS PASSED (Exit Code 0)!")
    print("==================================================")


if __name__ == "__main__":
    run_tests()

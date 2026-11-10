import os
import sys
from pathlib import Path

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8")

# Set working directory to script location
current_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_dir)
sys.path.insert(0, current_dir)

from fastapi.testclient import TestClient
from app import app, telephony_config, branding_config

client = TestClient(app)

def run_tests():
    print("==================================================")
    print("🧪 Verifying AI Call Center Telephony & White-Label v3")
    print("==================================================")

    # 1. Test Telephony Get Config
    res = client.get("/api/telephony/config")
    assert res.status_code == 200, f"Telephony get failed: {res.status_code}"
    data = res.json()
    assert "config" in data and "providers" in data
    cfg = data["config"]
    assert cfg["provider"] in ["nt_link", "gsm_gateway", "dtac_onecall", "custom_sip"]
    assert cfg["status"] == "registered"
    print("✅ 1. Telephony Config Retrieval: OK")
    print(f"   - Active Provider: {cfg['provider_name']}")
    print(f"   - Host: {cfg['server_host']}:{cfg['server_port']}")
    print(f"   - Caller ID: {cfg['caller_id']} (Status: {cfg['status']})")

    # 2. Test Telephony Update Config (Switch to GSM Gateway)
    gsm_payload = {
        "provider": "gsm_gateway",
        "provider_name": "GSM Gateway (SIM Box 8 Ports)",
        "server_host": "192.168.1.150",
        "server_port": 5060,
        "auth_username": "gsm_admin",
        "auth_password": "secretpassword",
        "caller_id": "089-777-6655",
        "codec": "G.711a (PCMA)",
        "max_channels": 8
    }
    res = client.post("/api/telephony/config", json=gsm_payload)
    assert res.status_code == 200, "Telephony update failed"
    updated_cfg = res.json()["config"]
    assert updated_cfg["provider"] == "gsm_gateway"
    assert updated_cfg["caller_id"] == "089-777-6655"
    assert updated_cfg["server_host"] == "192.168.1.150"
    print("✅ 2. Telephony Update & Switch Provider: OK")
    print(f"   - Switched to: {updated_cfg['provider_name']}")
    print(f"   - Host: {updated_cfg['server_host']}")
    print(f"   - Caller ID: {updated_cfg['caller_id']}")

    # 3. Test Telephony Ping / Connection Handshake
    res = client.post("/api/telephony/test_connection", json={})
    assert res.status_code == 200, "Test connection failed"
    ping_res = res.json()
    assert ping_res["success"] is True
    assert ping_res["status"] == "registered"
    assert ping_res["latency_ms"] > 0
    print("✅ 3. SIP OPTIONS Connection Ping: OK")
    print(f"   - Status: {ping_res['status']}")
    print(f"   - Latency: {ping_res['latency_ms']} ms")
    print(f"   - Message: {ping_res['message']}")

    # 4. Test Branding Get Config
    res = client.get("/api/branding")
    assert res.status_code == 200, "Branding get failed"
    brand = res.json()
    assert "brand_name" in brand and "logo_url" in brand
    assert "primary_color" in brand and "company_name" in brand
    print("✅ 4. White-Label Branding Retrieval: OK")
    print(f"   - Brand Name: {brand['brand_name']}")
    print(f"   - Primary Color: {brand['primary_color']}")
    print(f"   - Legal Name: {brand['company_name']}")

    # 5. Test Branding Update
    custom_brand = {
        "brand_name": "Apex AI Telephony Corp",
        "logo_url": "https://img.icons8.com/clouds/200/phone-contact.png",
        "tagline": "ระบบโทรอัจฉริยะองค์กรยุคใหม่",
        "primary_color": "#059669",
        "company_name": "บริษัท เอเปกซ์ วอยซ์ โซลูชั่นส์ จำกัด (มหาชน)",
        "tax_id": "0105566987654",
        "address": "88 อาคารเอเปกซ์เซ็นเตอร์ ชั้น 25 ถนนสุขุมวิท กรุงเทพฯ 10110",
        "support_phone": "02-999-8888",
        "support_email": "contact@apexvoice.co.th",
        "website": "https://apexvoice.co.th"
    }
    res = client.post("/api/branding", json=custom_brand)
    assert res.status_code == 200, "Branding update failed"
    updated_brand = res.json()["branding"]
    assert updated_brand["brand_name"] == "Apex AI Telephony Corp"
    assert updated_brand["primary_color"] == "#059669"
    assert updated_brand["tax_id"] == "0105566987654"
    assert updated_brand["support_phone"] == "02-999-8888"
    print("✅ 5. White-Label Branding Update: OK")
    print(f"   - Brand Name: {updated_brand['brand_name']}")
    print(f"   - Logo: {updated_brand['logo_url']}")
    print(f"   - Primary Color: {updated_brand['primary_color']}")
    print(f"   - Tax ID: {updated_brand['tax_id']}")

    # 6. Test Dashboard Data includes Telephony and Branding
    res = client.get("/api/dashboard_data")
    assert res.status_code == 200, "Dashboard data failed"
    d_data = res.json()
    assert "telephony" in d_data, "Missing telephony in dashboard data"
    assert "branding" in d_data, "Missing branding in dashboard data"
    assert d_data["telephony"]["provider"] == "gsm_gateway"
    assert d_data["branding"]["brand_name"] == "Apex AI Telephony Corp"
    print("✅ 6. Dashboard Telephony & Branding Integration: OK")
    print(f"   - Telephony Provider in Dashboard: {d_data['telephony']['provider_name']}")
    print(f"   - Brand in Dashboard: {d_data['branding']['brand_name']}")

    # 7. Test Start Call with Trunk Routing Record
    res = client.post("/api/start_call", json={
        "name": "คุณศิริชัย พัฒนาการ",
        "phone": "081-333-4455",
        "detail": "ทดสอบเส้นทางโทรผ่าน GSM Gateway"
    })
    assert res.status_code == 200, f"Start call failed: {res.text}"
    call_res = res.json()
    assert "trunk_route" in call_res
    assert "GSM Gateway" in call_res["trunk_route"]
    assert "089-777-6655" in call_res["trunk_route"]
    print("✅ 7. Start Call with Trunk Routing Tagging: OK")
    print(f"   - Call Session Trunk: {call_res['trunk_route']}")
    print(f"   - Agent Opening Speech: {call_res['speech']}")

    # 8. Test Frontend Markup in index.html
    html_path = Path("index.html")
    assert html_path.exists(), "index.html not found"
    html_content = html_path.read_text(encoding="utf-8")

    # Navbar branding elements
    assert 'id="navbar-brand-logo"' in html_content, "Missing navbar-brand-logo"
    assert 'id="navbar-brand-name"' in html_content, "Missing navbar-brand-name"
    assert 'id="navbar-brand-tagline"' in html_content, "Missing navbar-brand-tagline"

    # Sidebar tab buttons
    assert 'id="tab-btn-telephony"' in html_content, "Missing tab-btn-telephony"
    assert 'id="tab-btn-branding"' in html_content, "Missing tab-btn-branding"

    # Tab sections
    assert 'id="tab-telephony"' in html_content, "Missing tab-telephony section"
    assert 'id="tab-branding"' in html_content, "Missing tab-branding section"

    # Telephony elements
    assert "nt_link" in html_content, "Missing nt_link preset"
    assert "gsm_gateway" in html_content, "Missing gsm_gateway preset"
    assert "testTelephonyConnection" in html_content, "Missing testTelephonyConnection"
    assert "saveTelephonyConfig" in html_content, "Missing saveTelephonyConfig"

    # Branding elements
    assert "saveBrandingConfig" in html_content, "Missing saveBrandingConfig"
    assert "setPresetColor" in html_content, "Missing setPresetColor"
    assert "updateLivePreview" in html_content, "Missing updateLivePreview"
    assert 'id="modal-trunk-badge"' in html_content, "Missing modal-trunk-badge"

    print("✅ 8. HTML Elements & Live Controllers: OK")
    print("   - Dynamic Navbar Brand & Logo verified")
    print("   - Telephony Gateway tab and presets verified")
    print("   - White-Label Branding tab and color picker verified")
    print("   - Active trunk badge in Call Modal verified")

    print("==================================================")
    print("🎉 ALL 8 TELEPHONY & WHITE-LABEL TESTS PASSED!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()

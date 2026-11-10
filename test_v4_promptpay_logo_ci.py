import os
import sys
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8")

# Set working directory to script location
current_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_dir)
sys.path.insert(0, current_dir)

from fastapi.testclient import TestClient
from app import app, promptpay_config, branding_config, generate_promptpay_payload

client = TestClient(app)

def run_tests():
    print("==================================================")
    print("🧪 Verifying PromptPay Admin, Logo Upload & CI Extractor v4")
    print("==================================================")

    # 1. Test Admin PromptPay Get Config
    res = client.get("/api/admin/promptpay")
    assert res.status_code == 200, f"PromptPay get failed: {res.status_code}"
    pp = res.json()
    assert "promptpay_number" in pp
    assert "account_name" in pp
    assert "bank_name" in pp
    assert "type" in pp
    print("✅ 1. Admin PromptPay Config Retrieval: OK")
    print(f"   - PromptPay Number: {pp['promptpay_number']}")
    print(f"   - Account Name: {pp['account_name']}")
    print(f"   - Bank: {pp['bank_name']} (Type: {pp['type']})")

    # 2. Test Admin PromptPay Update (Mobile Phone)
    mobile_update = {
        "promptpay_number": "089-876-5432",
        "account_name": "บริษัท แอนติกราวิตี้ จำกัด",
        "bank_name": "ธนาคารไทยพาณิชย์ (SCB)"
    }
    res = client.post("/api/admin/promptpay", json=mobile_update)
    assert res.status_code == 200, "PromptPay update failed"
    updated = res.json()["promptpay"]
    assert updated["promptpay_number"] == "089-876-5432"
    assert updated["type"] == "mobile"
    assert updated["bank_name"] == "ธนาคารไทยพาณิชย์ (SCB)"
    print("✅ 2. Admin PromptPay Update (Mobile): OK")
    print(f"   - Number: {updated['promptpay_number']} (Type: {updated['type']})")

    # 3. Test Admin PromptPay Update (13-Digit National ID / Tax ID)
    tax_id_update = {
        "promptpay_number": "0-1055-66012-34-5",
        "account_name": "บริษัท บิซ โซลูชั่นส์ จำกัด",
        "bank_name": "ธนาคารกรุงเทพ (BBL)"
    }
    res = client.post("/api/admin/promptpay", json=tax_id_update)
    assert res.status_code == 200, "PromptPay update with Tax ID failed"
    updated_tax = res.json()["promptpay"]
    assert updated_tax["promptpay_number"] == "0-1055-66012-34-5"
    assert updated_tax["type"] == "national_id"
    print("✅ 3. Admin PromptPay Update (13-digit National ID): OK")
    print(f"   - Number: {updated_tax['promptpay_number']} (Type: {updated_tax['type']})")

    # 4. Test EMVCo Tag 29 Payload Generator
    # Mobile Test:
    payload_mobile = generate_promptpay_payload("081-234-5678", 300.0)
    assert "0016A000000677010111" in payload_mobile
    # Sub-tag 01 indicates Mobile (01130066812345678)
    assert "01130066812345678" in payload_mobile
    assert "5406300.00" in payload_mobile
    assert "5802TH" in payload_mobile
    assert payload_mobile.startswith("000201010212")

    # National ID / Tax ID Test (13 digits):
    payload_id = generate_promptpay_payload("0105566012345", 500.0)
    assert "0016A000000677010111" in payload_id
    # Sub-tag 02 indicates National ID / Tax ID (02130105566012345)
    assert "02130105566012345" in payload_id
    assert "5406500.00" in payload_id
    print("✅ 4. EMVCo Tag 29 Generator (Sub-tag 01 Mobile & Sub-tag 02 Tax ID): OK")
    print(f"   - Mobile Payload Sample: {payload_mobile[:40]}... (CRC: {payload_mobile[-4:]})")
    print(f"   - Tax ID Payload Sample: {payload_id[:40]}... (CRC: {payload_id[-4:]})")

    # 5. Test Topup QR Creation with Configured PromptPay
    res = client.post("/api/topup/promptpay_qr", json={"amount": 300, "package_id": "pkg_300"})
    assert res.status_code == 200, "Create topup QR failed"
    qr_data = res.json()
    assert qr_data["amount"] == 300
    assert qr_data["credits_to_add"] == 330
    assert qr_data["promptpay_number"] == updated_tax["promptpay_number"]
    assert qr_data["account_name"] == updated_tax["account_name"]
    assert qr_data["bank_name"] == updated_tax["bank_name"]
    assert "qr_image_url" in qr_data
    print("✅ 5. Dynamic PromptPay Topup QR Response: OK")
    print(f"   - PromptPay Number in QR: {qr_data['promptpay_number']}")
    print(f"   - Account Name: {qr_data['account_name']}")
    print(f"   - Bank Name: {qr_data['bank_name']}")

    # 6. Test Dashboard & Credits Include PromptPay Config
    res_credits = client.get("/api/credits")
    assert res_credits.status_code == 200
    assert "promptpay" in res_credits.json()

    res_dash = client.get("/api/dashboard_data")
    assert res_dash.status_code == 200
    assert "promptpay" in res_dash.json()
    assert res_dash.json()["promptpay"]["promptpay_number"] == updated_tax["promptpay_number"]
    print("✅ 6. Credits & Dashboard Integration: OK")

    # 7. Test Logo File Upload API
    base64_logo_sample = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    res_logo = client.post("/api/branding/upload_logo", json={"logo_data": base64_logo_sample})
    assert res_logo.status_code == 200, "Logo upload failed"
    logo_res = res_logo.json()
    assert logo_res["success"] is True
    assert logo_res["logo_url"] == base64_logo_sample
    assert branding_config["logo_url"] == base64_logo_sample
    print("✅ 7. Logo File Upload API (Base64 DataURL): OK")

    # 8. Test Frontend Markup in index.html
    html_path = Path("index.html")
    assert html_path.exists(), "index.html not found"
    html_content = html_path.read_text(encoding="utf-8")

    # Admin PromptPay Box
    assert 'id="admin-pp-number"' in html_content, "Missing admin-pp-number"
    assert 'id="admin-pp-name"' in html_content, "Missing admin-pp-name"
    assert 'id="admin-pp-bank"' in html_content, "Missing admin-pp-bank"
    assert "saveAdminPromptPay" in html_content, "Missing saveAdminPromptPay"

    # PromptPay Modal Config Display
    assert 'id="pp-modal-name"' in html_content, "Missing pp-modal-name"
    assert 'id="pp-modal-bank"' in html_content, "Missing pp-modal-bank"
    assert 'id="pp-modal-number"' in html_content, "Missing pp-modal-number"

    # Logo Upload Elements
    assert 'id="logo-file-input"' in html_content, "Missing logo-file-input"
    assert 'id="logo-dropzone"' in html_content, "Missing logo-dropzone"
    assert "handleLogoFileSelect" in html_content, "Missing handleLogoFileSelect"
    assert "handleLogoDrop" in html_content, "Missing handleLogoDrop"

    # CI Palette Extractor
    assert 'id="logo-extracted-colors"' in html_content, "Missing logo-extracted-colors"
    assert "extractColorsFromImage" in html_content, "Missing extractColorsFromImage"
    assert "selectCIColor" in html_content, "Missing selectCIColor"
    assert 'id="branding-color-hex"' in html_content, "Missing branding-color-hex"

    print("✅ 8. Frontend Controls & Event Handlers verified in index.html: OK")
    print("   - Admin PromptPay Box & Save Button verified")
    print("   - Modal Account & Bank display verified")
    print("   - Logo File Input & Drag-and-Drop Dropzone verified")
    print("   - CI Palette Smart Extractor & Clickable Swatches verified")

    print("==================================================")
    print("🎉 ALL 8 TESTS PASSED SUCCESSFULLY (Exit Code 0)!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()

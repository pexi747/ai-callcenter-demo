import sys
from pathlib import Path
from fastapi.testclient import TestClient

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app import app, AUDIO_DIR
from earshot_voice import (
    EARSHOT_PROFILES,
    shape_thai_prosody_text,
    synthesize_earshot_speech_sync,
)

client = TestClient(app)


def run_v7_tests():
    print("==================================================")
    print("🚀 RUNNING V7 EARSHOT VOICE & DIRECT DIALER TESTS")
    print("==================================================")

    prosody_out = shape_thai_prosody_text("สวัสดีค่ะ ขอเรียนสายคุณสมชายค่ะ สะดวกไหมคะ")
    assert "ค่ะ," in prosody_out
    print(f"✅ 1. Thai Prosody & Breath Pacing Shaper: OK ({prosody_out})")

    audio_url, metrics = synthesize_earshot_speech_sync(
        text="สวัสดีค่ะ ขอเรียนสายคุณลูกค้าจากเดอร์มาแคร์คลินิกนะคะ",
        audio_dir=AUDIO_DIR,
        voice_id="th-TH-PremwadeeNeural",
        tone="Friendly",
        speed=1.0,
        earshot_profile="close_mic",
        filename_prefix="test_earshot",
    )
    assert audio_url.startswith("/audio/test_earshot_") and audio_url.endswith(".wav")
    wav_file = AUDIO_DIR / Path(audio_url).name
    assert wav_file.exists() and wav_file.stat().st_size > 1000
    assert metrics["earshot_score"] >= 86
    assert "rms_db" in metrics and "dynamic_range_db" in metrics
    print(
        f"✅ 2. Earshot Neural Synthesis & Mastering: OK "
        f"(Score={metrics['earshot_score']}%, Engine={metrics['engine']}, Size={wav_file.stat().st_size} bytes)"
    )

    res = client.get("/api/earshot/profiles")
    assert res.status_code == 200
    prof_data = res.json()
    assert "close_mic" in prof_data["profiles"]
    assert "warm_office" in prof_data["profiles"]
    assert "crystal_hd" in prof_data["profiles"]
    print("✅ 3. GET /api/earshot/profiles Endpoint: OK")

    res = client.post(
        "/api/business_profiles/update",
        json={"earshot_profile": "warm_office", "tone": "Friendly"},
    )
    assert res.status_code == 200
    assert res.json()["active_profile"]["earshot_profile"] == "warm_office"
    print("✅ 4. Earshot Profile Persistence in Business Profile: OK")

    res = client.post(
        "/api/preview_voice",
        json={
            "voice_id": "th-TH-PremwadeeNeural",
            "earshot_profile": "crystal_hd",
            "text": "สวัสดีค่ะ ทดสอบระบบเสียงสมจริงผ่านหน้าเว็บค่ะ",
        },
    )
    assert res.status_code == 200
    prev = res.json()
    assert prev["audio_url"].endswith(".wav")
    assert prev["earshot_metrics"]["earshot_score"] >= 86
    assert prev["earshot_metrics"]["profile"] == "crystal_hd"
    print(
        f"✅ 5. POST /api/preview_voice with Earshot Audit Metrics: OK "
        f"(Verdict={prev['earshot_metrics']['verdict']})"
    )

    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    for required_marker in [
        "quick-dial-phone",
        "quick-dial-name",
        "quick-dial-script",
        "startQuickRealCall()",
        "modal-dial-phone-input",
        "redialFromModalInput()",
        "selectEarshotProfile('close_mic')",
        "earshot-score-badge",
        "earshot-metrics-box",
    ]:
        assert required_marker in html, f"Missing marker in index.html: {required_marker}"
    print("✅ 6. Direct Web Dialer & Earshot Studio UI Controls in index.html: OK")

    print("==================================================")
    print("🎉 ALL 6 V7 EARSHOT VOICE & WEB DIALER TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    run_v7_tests()

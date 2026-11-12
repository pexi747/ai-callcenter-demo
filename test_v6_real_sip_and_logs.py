import json
import os
import sys
import wave
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

current_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_dir)
sys.path.insert(0, current_dir)

from fastapi.testclient import TestClient
from app import app, AUDIO_DIR, CALL_LOGS_FILE, TELEPHONY_PROVIDERS
from sip_engine import verify_sip_registration, decode_audio_file_to_pcm8k, save_pcm8k_to_wav

client = TestClient(app)


def run_tests():
    print("==================================================")
    print("🧪 Verifying Real SIP/RTP Engine, WAV Recording & Audit Logs v6")
    print("==================================================")

    nt_cfg = dict(TELEPHONY_PROVIDERS["nt_link"])
    client.post("/api/telephony/config", json=nt_cfg)

    reg_res = client.post("/api/telephony/test_connection", json={})
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert reg_data["success"] is True
    assert reg_data["status"] == "registered"
    print("✅ 1. Live SIP Registration Handshake (NT NextGen 021078407):")
    print(f"   - Live Verified: {reg_data.get('live_verified')}")
    print(f"   - SIP Response: {reg_data.get('sip_response')}")
    print(f"   - Message: {reg_data.get('message')}")

    start_res = client.post("/api/start_call", json={
        "name": "คุณปิยะพงษ์ เจริญสุข",
        "phone": "089-555-4433",
        "detail": "ยืนยันคิวนัดหมายตรวจสุขภาพ",
        "dial_real_sip": False
    })
    assert start_res.status_code == 200
    start_data = start_res.json()
    session_id = start_data["session_id"]
    assert session_id

    chat1 = client.post("/api/chat", json={
        "session_id": session_id,
        "user_speech": "ใช่ครับ กำลังพูดสายอยู่ สะดวกคุยครับ"
    })
    assert chat1.status_code == 200

    chat2 = client.post("/api/chat", json={
        "session_id": session_id,
        "user_speech": "สะดวกมาตามนัดเลยครับ ขอบคุณมากครับ"
    })
    assert chat2.status_code == 200
    chat2_data = chat2.json()
    assert chat2_data["call_status"] == "ended"
    recording_url = chat2_data.get("recording_file")
    call_id = chat2_data.get("call_id")
    assert recording_url and recording_url.endswith(".wav"), f"Expected .wav recording, got {recording_url}"
    assert call_id, "Expected call_id returned on call completion"

    wav_file = AUDIO_DIR / os.path.basename(recording_url)
    assert wav_file.exists(), f"Recorded WAV file missing on disk: {wav_file}"
    with wave.open(str(wav_file), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 8000
        frames = wf.getnframes()
        duration_s = frames / 8000.0
    assert duration_s > 0.5, f"Expected non-empty WAV recording, got {duration_s:.2f}s"
    print("✅ 2. Full Call Audio Recording (.wav 8000Hz 16-bit Mono) Verified:")
    print(f"   - Recording File: {recording_url} ({wav_file.stat().st_size:,} bytes, {duration_s:.2f}s)")

    audio_res = client.get(recording_url)
    assert audio_res.status_code == 200
    assert "audio/wav" in audio_res.headers.get("content-type", "")
    print("✅ 3. Recorded WAV HTTP Streaming Endpoint Verified")

    detail_res = client.get(f"/api/calls/{call_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["name"] == "คุณปิยะพงษ์ เจริญสุข"
    assert detail["recording_file"] == recording_url
    assert len(detail["transcript"]) >= 3, f"Expected >= 3 transcript turns, got {len(detail['transcript'])}"
    assert len(detail["sip_events"]) >= 1
    print("✅ 4. Call Log Detail & Full Conversation Transcript Retrieval Verified:")
    print(f"   - Call ID: {detail['id']} | Customer: {detail['name']} ({detail['phone']})")
    print(f"   - Transcript Turns: {len(detail['transcript'])} messages logged with timestamps")
    for idx, turn in enumerate(detail["transcript"], 1):
        print(f"     [{idx}] ({turn.get('time')}) {turn['speaker']}: {turn['text'][:55]}...")

    assert CALL_LOGS_FILE.exists(), "call_logs.json not persisted on disk"
    persisted = json.loads(CALL_LOGS_FILE.read_text(encoding="utf-8"))
    assert any(c.get("id") == call_id for c in persisted), "Call ID not found in persisted call_logs.json"
    print(f"✅ 5. Persistent Call Log File (call_logs.json) Verified ({len(persisted)} total records)")

    start2 = client.post("/api/start_call", json={
        "name": "คุณนิภาวรรณ ทดสอบวางสาย",
        "phone": "081-222-9988",
        "dial_real_sip": False
    }).json()
    hangup_res = client.post("/api/hangup", json={"session_id": start2["session_id"]})
    assert hangup_res.status_code == 200
    hangup_data = hangup_res.json()
    assert hangup_data["success"] is True
    assert hangup_data["recording_file"].endswith(".wav")
    print("✅ 6. Manual Hangup Endpoint (/api/hangup) & Immediate Log Persistence Verified")

    html_text = Path("index.html").read_text(encoding="utf-8")
    for marker in [
        'id="toggle-real-sip"',
        'id="modal-call-detail"',
        'id="detail-audio-player"',
        'id="detail-transcript-list"',
        'id="detail-sip-events"',
        'openCallDetailModal',
    ]:
        assert marker in html_text, f"Missing UI element in index.html: {marker}"
    print("✅ 7. Frontend Real SIP Toggle & Call Log Audit Modal Verified in index.html")

    print("==================================================")
    print("🎉 ALL 7 REAL SIP, WAV RECORDING & AUDIT LOG TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    run_tests()

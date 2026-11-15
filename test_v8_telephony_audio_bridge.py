import io
import math
import struct
import time
import wave
import unittest
from pathlib import Path

from app import (
    convert_pcm_to_wav_bytes,
    process_chat_turn,
    active_sessions,
    active_sip_calls,
    AUDIO_DIR,
)
from sip_engine import SIPCallSession


class TestTelephonyAudioBridge(unittest.TestCase):
    def test_pcm_to_wav_conversion(self):
        sample_rate = 8000
        freq = 440.0
        pcm = bytearray()
        for i in range(800):
            val = int(10000 * math.sin(2 * math.pi * freq * (i / sample_rate)))
            pcm.extend(struct.pack("<h", val))

        wav_bytes = convert_pcm_to_wav_bytes(bytes(pcm), sample_rate=8000, channels=1, sample_width=2)
        self.assertTrue(len(wav_bytes) > len(pcm))
        self.assertTrue(wav_bytes.startswith(b"RIFF"))

        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            self.assertEqual(wf.getnchannels(), 1)
            self.assertEqual(wf.getsampwidth(), 2)
            self.assertEqual(wf.getframerate(), 8000)
            self.assertEqual(wf.getnframes(), 800)

    def test_vad_energy_thresholding_and_segmentation(self):
        received_speech = []

        def on_speech(session, speech_bytes):
            received_speech.append(speech_bytes)

        session = SIPCallSession(
            session_id="test_vad_session",
            config={},
            target_phone="0812345678",
            audio_dir=AUDIO_DIR,
            on_speech_callback=on_speech,
        )

        voice_chunk = bytearray()
        for i in range(160):
            val = int(2000 * math.sin(2 * math.pi * 500 * (i / 8000)))
            voice_chunk.extend(struct.pack("<h", val))
        voice_chunk = bytes(voice_chunk)

        silence_chunk = b"\x00" * 320

        import audioop
        voice_rms = audioop.rms(voice_chunk, 2)
        silence_rms = audioop.rms(silence_chunk, 2)
        self.assertGreaterEqual(voice_rms, session.VOICE_RMS_THRESHOLD)
        self.assertLess(silence_rms, session.VOICE_RMS_THRESHOLD)

        # Feed 8 voice chunks (~160ms)
        for _ in range(8):
            rms = audioop.rms(voice_chunk, 2)
            if rms >= session.VOICE_RMS_THRESHOLD:
                session.vad_is_speaking = True
                session.vad_voice_chunks += 1
                session.vad_silence_chunks = 0
                session.vad_buffer.extend(voice_chunk)

        self.assertTrue(session.vad_is_speaking)
        self.assertEqual(session.vad_voice_chunks, 8)

        # Feed 22 silence chunks to trigger utterance completion
        for _ in range(22):
            session.vad_silence_chunks += 1
            session.vad_buffer.extend(silence_chunk)
            if session.vad_silence_chunks >= session.MAX_SILENCE_CHUNKS:
                if session.vad_voice_chunks >= session.MIN_VOICE_CHUNKS and session.on_speech_callback:
                    speech_bytes = bytes(session.vad_buffer)
                    session._dispatch_speech(speech_bytes)
                session.vad_buffer.clear()
                session.vad_voice_chunks = 0
                session.vad_silence_chunks = 0
                session.vad_is_speaking = False

        self.assertFalse(session.vad_is_speaking)
        self.assertEqual(len(received_speech), 1)
        self.assertEqual(len(received_speech[0]), 8 * 320 + 22 * 320)

    def test_telephony_barge_in_flushes_tx_buffer(self):
        session = SIPCallSession(session_id="test_barge_in", config={}, target_phone="0812345678", audio_dir=Path("./audio"))
        session.tx_pcm_buffer.extend(b"\x12\x34" * 1000)
        self.assertGreater(len(session.tx_pcm_buffer), 0)

        # Incoming voice triggers barge-in
        loud_chunk = b"\x20\x20" * 160
        import audioop
        rms = audioop.rms(loud_chunk, 2)
        if rms >= session.VOICE_RMS_THRESHOLD:
            if session.tx_pcm_buffer:
                session.tx_pcm_buffer.clear()

        self.assertEqual(len(session.tx_pcm_buffer), 0)

    def test_telephony_chat_turn_enqueues_rtp_audio(self):
        import asyncio
        from datetime import datetime
        from app import active_business

        session_id = "test_live_turn_session"
        active_sessions[session_id] = {
            "customer_name": "คุณสมชาย",
            "customer_phone": "0812345678",
            "appointment_detail": "นัดตรวจสุขภาพ",
            "active_script": active_business,
            "chat_session": None,
            "created_at": datetime.now(),
            "transcript": [],
        }
        sip_call = SIPCallSession(session_id=session_id, config={}, target_phone="0812345678", audio_dir=AUDIO_DIR)
        active_sip_calls[session_id] = sip_call

        res = asyncio.run(process_chat_turn(session_id, "สะดวกครับ ไปตามนัดได้แน่นอน", source="telephony"))
        self.assertIn("speech", res)
        self.assertIn("audio_url", res)
        self.assertGreater(len(sip_call.tx_pcm_buffer), 0)
        self.assertTrue(any("AI สนทนากลับ:" in ev for ev in sip_call.sip_events))


if __name__ == "__main__":
    unittest.main()

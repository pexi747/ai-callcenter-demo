import os
import sys
import json
import uuid
import asyncio
from datetime import datetime
from pathlib import Path

# Force UTF-8 on Windows Console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import dotenv
from gtts import gTTS
from google import genai
from google.genai import types

# Load environment
dotenv.load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

app = FastAPI(title="AI Voice Call Center Demo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUDIO_DIR = Path(__file__).resolve().parent / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Gemini Client
client = genai.Client(api_key=GEMINI_API_KEY)

# In-memory database of calls matching the screenshot structure
calls_db = [
    {
        "id": "call-001",
        "name": "คุณอาย",
        "phone": "084-148-7979",
        "job_ref": "20261030_1 (TK-1001)",
        "time": "30 ต.ค. 16:59",
        "status": "สำเร็จแล้ว",
        "duration": "0:25",
        "appointment_outcome": "มาตามนัด",
        "has_new_date": "-",
        "summary": "ยืนยันเข้ารับบริการตามนัดหมายเดิม วันที่ 2 พ.ย. เวลา 14:00 น.",
        "audio_file": None
    },
    {
        "id": "call-002",
        "name": "คุณจ๋า",
        "phone": "093-340-9929",
        "job_ref": "20261025_1 (db0016)",
        "time": "25 ต.ค. 11:33",
        "status": "สำเร็จแล้ว",
        "duration": "0:16",
        "appointment_outcome": "ยกเลิกนัด",
        "has_new_date": "-",
        "summary": "โทรติดแต่ปลายสายแจ้งว่าเป็นผู้ชาย ไม่ใช่คุณจ๋า AI จึงขออภัยเนื่องจากน่าจะโทรผิดเบอร์แล้ววางสายไป",
        "audio_file": None
    },
    {
        "id": "call-003",
        "name": "คุณทักษิณทร์",
        "phone": "095-307-3480",
        "job_ref": "20261027_2",
        "time": "27 ต.ค. 13:48",
        "status": "สำเร็จแล้ว",
        "duration": "1:27",
        "appointment_outcome": "ขอเลื่อนนัด",
        "has_new_date": "ใช่ (5 พ.ย. 15:00 น.)",
        "summary": "ลูกค้าติดงานด่วน ขอเลื่อนนัดจากวันที่ 28 ต.ค. เป็นวันที่ 5 พ.ย. เวลา 15:00 น. ลงบันทึกเข้าระบบเรียบร้อย",
        "audio_file": None
    },
    {
        "id": "call-004",
        "name": "คุณมั่ม",
        "phone": "084-007-9950",
        "job_ref": "20261030_1",
        "time": "31 ต.ค. 12:00",
        "status": "ไม่สำเร็จ ไม่มีผู้รับสาย",
        "duration": "-",
        "appointment_outcome": "ติดต่อไม่ได้",
        "has_new_date": "-",
        "summary": "โทร 3 ครั้ง ไม่มีผู้รับสาย บันทึกเข้าคิวโทรติดตามผลในวันถัดไป",
        "audio_file": None
    }
]

# Active call sessions
active_sessions = {}

def text_to_speech_sync(text: str, filename_prefix="ai_reply") -> str:
    """Generate speech using gTTS (Google Text-to-Speech)"""
    filename = f"{filename_prefix}_{uuid.uuid4().hex[:8]}.mp3"
    filepath = AUDIO_DIR / filename
    try:
        tts = gTTS(text=text, lang="th")
        tts.save(str(filepath))
        return f"/audio/{filename}"
    except Exception as e:
        print("TTS Error:", e)
        return ""

async def text_to_speech(text: str, filename_prefix="ai_reply") -> str:
    return await asyncio.to_thread(text_to_speech_sync, text, filename_prefix)

SYSTEM_PROMPT = """คุณคือ "น้องฟ้า" พนักงานสาว AI ของ "เดอร์มา แคร์ คลินิก" ทำหน้าที่โทรศัพท์แจ้งเตือนและคอนเฟิร์มนัดหมายลูกค้า
บทสนทนาต้องกระชับ สุภาพ ชัดเจน และเป็นธรรมชาติที่สุด เหมือนพนักงานโทรจริง ไม่พูดเยิ่นเย้อ

ขั้นตอนการสนทนา:
1. การตรวจสอบตัวตน: ทักทายและถามยืนยันว่าใช่ [ชื่อลูกค้า] หรือไม่
   - หากปลายทางบอกว่าไม่ใช่ (เช่น เป็นคนอื่น, โทรผิด, เป็นผู้ชายทั้งที่ชื่อเป็นผู้หญิง): ให้กล่าวขอโทษอย่างสุภาพ แจ้งว่าระบบน่าจะบันทึกเบอร์ผิด และขออนุญาตวางสายทันที
   - หากใช่: ให้แจ้งเรื่องนัดหมาย (เข้ารับบริการวันพรุ่งนี้ เวลา 14:00 น.) และถามว่าสะดวกเข้ารับบริการตามนัดไหม
2. การตอบรับของลูกค้า:
   - กรณี "สะดวก/มาตามนัด": กล่าวขอบคุณ แจ้งเตือนข้อควรปฏิบัติสั้นๆ และอวยพร ปิดการสนทนา
   - กรณี "ไม่สะดวก/ขอเลื่อน": ถามลูกค้าทันทีว่าสะดวกเลื่อนเป็นวันไหนและช่วงเวลากี่โมง เมื่อลูกค้าแจ้ง ให้ทวนวันเวลาใหม่และบันทึก
   - กรณี "ขอยกเลิก": ถามเหตุผลสั้นๆ แสดงความเสียดายและบันทึกยกเลิก
3. เมื่อบทสนทนาสิ้นสุด ให้จบสายอย่างสุภาพ

กฎการตอบ:
ให้คุณตอบเป็น JSON Format เท่านั้น โดยมีโครงสร้างดังนี้:
{
  "speech": "ข้อความที่ AI จะพูดออกมาให้ลูกค้าฟัง (ภาษาไทย ไม่ใส่เครื่องหมายพิเศษ)",
  "call_status": "in_progress" หรือ "ended",
  "appointment_outcome": "มาตามนัด" หรือ "ขอเลื่อนนัด" หรือ "ยกเลิกนัด" หรือ "โทรผิดเบอร์/ไม่ใช่เจ้าของ",
  "has_new_date": "ใช่" หรือ "ไม่ใช่" หรือ "-",
  "new_date_info": "รายละเอียดวันเวลาใหม่ (ถ้ามี)",
  "summary": "สรุปผลการโทรสั้นๆ 1-2 ประโยคสำหรับเจ้าหน้าที่คลินิก"
}
ห้ามใส่ markdown wrapper หรือ ```json นอกเหนือจากตัว JSON เอง"""

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    file_path = AUDIO_DIR / filename
    if file_path.exists():
        return FileResponse(file_path, media_type="audio/mpeg")
    return JSONResponse(status_code=404, content={"error": "Audio not found"})

@app.get("/api/dashboard_data")
async def get_dashboard_data():
    total_calls = len(calls_db) + 18 # Seed numbers for realistic dashboard
    answered = len([c for c in calls_db if "สำเร็จ" in c["status"]]) + 18
    unanswered = len([c for c in calls_db if "ไม่สำเร็จ" in c["status"]])
    
    # Outcomes count
    attended = len([c for c in calls_db if c["appointment_outcome"] == "มาตามนัด"]) + 6
    rescheduled = len([c for c in calls_db if c["appointment_outcome"] == "ขอเลื่อนนัด"]) + 3
    cancelled = len([c for c in calls_db if c["appointment_outcome"] in ["ยกเลิกนัด", "โทรผิดเบอร์/ไม่ใช่เจ้าของ"]]) + 1

    return {
        "stats": {
            "total": total_calls,
            "answered": answered,
            "pending": 0,
            "unreachable": unanswered,
            "answered_percent": f"{(answered / total_calls * 100):.1f}%"
        },
        "outcomes": {
            "attended": attended,
            "rescheduled": rescheduled,
            "cancelled": cancelled,
            "new_date_yes": 3,
            "new_date_no": 2
        },
        "calls": calls_db
    }

@app.post("/api/start_call")
async def start_call(data: dict):
    customer_name = data.get("name", "คุณจ๋า")
    customer_phone = data.get("phone", "093-340-9929")
    appointment_detail = data.get("detail", "ตรวจสภาพผิวและเลเซอร์ วันที่ 12 พ.ย. เวลา 14:00 น.")
    
    session_id = uuid.uuid4().hex[:10]
    opening_text = f"สวัสดีค่ะ ขอเรียนสาย{customer_name} จากเดอร์มา แคร์ คลินิก ค่ะ ไม่ทราบว่าสะดวกคุยสักครู่ไหมคะ"
    audio_url = await text_to_speech(opening_text, "open")
    
    # Initialize native Gemini Chat Session
    chat_session = client.chats.create(
        model="gemini-3.5-flash-lite",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
            response_mime_type="application/json"
        )
    )
    
    # Seed context
    init_instruction = (
        f"ข้อมูลเป้าหมาย: ชื่อลูกค้า={customer_name}, เบอร์={customer_phone}, "
        f"นัดเดิม={appointment_detail}. ประโยคเปิดสายที่คุณพูดออกไปแล้วคือ: \"{opening_text}\". "
        f"จงเตรียมพร้อมรับคำตอบจากลูกค้าและตอบกลับในรูปแบบ JSON ตามคำสั่ง"
    )
    chat_session.send_message(init_instruction)
    
    active_sessions[session_id] = {
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "appointment_detail": appointment_detail,
        "chat_session": chat_session,
        "created_at": datetime.now(),
        "transcript": [{"speaker": "AI", "text": opening_text, "audio": audio_url}]
    }
    
    return {
        "session_id": session_id,
        "speech": opening_text,
        "audio_url": audio_url,
        "call_status": "in_progress"
    }

@app.post("/api/chat")
async def chat(data: dict):
    session_id = data.get("session_id")
    user_speech = data.get("user_speech", "").strip()
    
    if session_id not in active_sessions:
        return JSONResponse(status_code=400, content={"error": "Session not found"})
    
    session = active_sessions[session_id]
    session["transcript"].append({"speaker": "Customer", "text": user_speech, "audio": None})
    
    # Send message to Gemini Chat
    try:
        response = session["chat_session"].send_message(
            f"ลูกค้าพูดว่า: \"{user_speech}\"\nโปรดตอบกลับตามสคริปต์และคืนค่า JSON เท่านั้น"
        )
        result = json.loads(response.text.strip())
    except Exception as e:
        print("Gemini Chat Error:", e)
        result = {
            "speech": "รับทราบค่ะ ขออภัยในความไม่สะดวก ทางเจ้าหน้าที่จะติดต่อกลับอีกครั้งนะคะ ขอบคุณค่ะ",
            "call_status": "ended",
            "appointment_outcome": "ติดต่อไม่ได้",
            "has_new_date": "-",
            "new_date_info": "",
            "summary": f"ระบบขัดข้อง: {str(e)[:50]}"
        }
    
    ai_speech = result.get("speech", "รับทราบค่ะ ขอบคุณค่ะ")
    call_status = result.get("call_status", "in_progress")
    outcome = result.get("appointment_outcome", "รอผล")
    summary = result.get("summary", "")
    has_new_date = result.get("has_new_date", "-")
    
    # Generate speech audio
    audio_url = await text_to_speech(ai_speech, "turn")
    session["transcript"].append({"speaker": "AI", "text": ai_speech, "audio": audio_url})
    
    # If call ended, save to DB
    if call_status == "ended":
        duration_sec = max(int((datetime.now() - session["created_at"]).total_seconds()), 12)
        calls_db.insert(0, {
            "id": f"call-{uuid.uuid4().hex[:6]}",
            "name": session["customer_name"],
            "phone": session["customer_phone"],
            "job_ref": f"{datetime.now().strftime('%Y%m%d')}_AI",
            "time": datetime.now().strftime("%d %b %H:%M"),
            "status": "สำเร็จแล้ว",
            "duration": f"0:{duration_sec:02d}",
            "appointment_outcome": outcome,
            "has_new_date": has_new_date,
            "summary": summary,
            "audio_file": audio_url
        })
    
    return {
        "speech": ai_speech,
        "audio_url": audio_url,
        "call_status": call_status,
        "outcome": outcome,
        "summary": summary
    }

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = Path(__file__).resolve().parent / "index.html"
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8088))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)

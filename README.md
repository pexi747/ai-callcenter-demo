# AI Voice Call Center Demo 📞

ระบบจำลอง AI Outbound Call Center ภาษาไทย สำหรับแจ้งเตือนและคอนเฟิร์มนัดหมายลูกค้า (Appointment Confirmation) พร้อม Web Dashboard สรุปผลเรียลไทม์

## คุณสมบัติเด่น (Features)
- **Web Dashboard**: หน้าจอ Campaign Report สรุปสายทั้งหมด, สายที่ตอบ, สถานะการนัด (มาตามนัด, ขอเลื่อนนัด, ยกเลิกนัด)
- **AI Brain**: ขับเคลื่อนด้วย Google Gemini 3.5 Flash Lite ประมวลผลบทสนทนาภาษาไทยอย่างเป็นธรรมชาติ
- **Thai Neural TTS**: สังเคราะห์เสียงพูดภาษาไทยพร้อมบันทึกไฟล์เสียงให้กดฟังย้อนหลังได้
- **Smart Logic**: ตรวจจับกรณีโทรผิดเบอร์ / ผู้รับไม่ใช่เจ้าของสาย และวางสายอย่างสุภาพทันที

## Tech Stack
- Backend: FastAPI, Uvicorn, Python 3.11
- AI: Google GenAI SDK (`gemini-3.5-flash-lite`)
- Voice: Google Text-to-Speech (gTTS)
- Frontend: Tailwind CSS, HTML5, Web Speech API

## Deploy on Render (Free)
1. ไปที่ [render.com](https://render.com) แล้วเข้าสู่ระบบ
2. กด **New +** -> **Web Service**
3. เลือก Repository: `ai-callcenter-demo`
4. ตั้งค่า:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. ในช่อง **Environment Variables** ให้เพิ่ม:
   - `GEMINI_API_KEY`: ใส่ Gemini API Key ของคุณ
6. กด **Deploy Web Service**

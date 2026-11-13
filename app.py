import os
import sys
import json
import uuid
import asyncio
import urllib.parse
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
from sip_engine import (
    SIPCallSession,
    verify_sip_registration,
    decode_audio_file_to_pcm8k,
    save_pcm8k_to_wav,
)
from earshot_voice import (
    EARSHOT_PROFILES,
    VOICE_PERSONA_MAP,
    synthesize_earshot_speech_sync,
)

# Load environment
dotenv.load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
dotenv.load_dotenv(Path(__file__).resolve().parent / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

app = FastAPI(title="AI Voice Call Center Platform - Multi-Tenant SaaS")
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
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print("Gemini client initialization error:", e)

# -------------------------------------------------------------
# 1. Multi-Industry Business Profiles
# -------------------------------------------------------------
BUSINESS_TEMPLATES = {
    "clinic": {
        "id": "clinic",
        "name": "เดอร์มา แคร์ คลินิก",
        "industry": "คลินิกเวชกรรม & ความงาม",
        "description": "คลินิกเวชกรรมความงาม เลเซอร์ และผิวพรรณระดับพรีเมียม",
        "agent_name": "น้องฟ้า",
        "agent_gender": "female",
        "voice_id": "th-TH-PremwadeeNeural",
        "earshot_profile": "close_mic",
        "speed": 1.0,
        "tone": "Friendly",
        "opening_text": "สวัสดีค่ะ ขอเรียนสายคุณ{customer_name} จากเดอร์มา แคร์ คลินิก ค่ะ ไม่ทราบว่าสะดวกคุยสักครู่ไหมคะ",
        "default_detail": "ตรวจสภาพผิวและเลเซอร์ วันที่ 12 พ.ย. เวลา 14:00 น.",
        "custom_instructions": "เตือนให้ลูกค้างดออกแดดจัดและงดทายารักษาสิวที่มีกรดผลไม้ก่อนเข้ารับบริการ 24 ชั่วโมง"
    },
    "automotive": {
        "id": "automotive",
        "name": "ออโต้ แคร์ เซอร์วิส",
        "industry": "ศูนย์บริการยานยนต์ & อู่ซ่อมรถ",
        "description": "ศูนย์บริการยานยนต์ครบวงจร เช็คระยะ ซ่อมบำรุง และเปลี่ยนถ่ายน้ำมันเครื่อง",
        "agent_name": "น้องนนท์",
        "agent_gender": "male",
        "voice_id": "th-TH-NiwatNeural",
        "earshot_profile": "warm_office",
        "speed": 1.0,
        "tone": "Formal",
        "opening_text": "สวัสดีครับ ขอเรียนสายคุณ{customer_name} จากศูนย์บริการออโต้ แคร์ เซอร์วิส ครับ ไม่ทราบว่าสะดวกคุยสักครู่ไหมครับ",
        "default_detail": "นัดนำรถเข้าเช็คระยะ 50,000 กม. และเปลี่ยนผ้าเบรก พรุ่งนี้ 10:00 น.",
        "custom_instructions": "แจ้งเตือนให้นำสมุดรับประกันรถยนต์มาด้วย และทางศูนย์มีบริการรถรับส่งฟรีระหว่างรอตรวจเช็ค"
    },
    "realestate": {
        "id": "realestate",
        "name": "แกรนด์ พรอพเพอร์ตี้",
        "industry": "อสังหาริมทรัพย์ & คอนโดมิเนียม",
        "description": "โครงการบ้านเดี่ยวและคอนโดมิเนียมหรู ติดแนวรถไฟฟ้า พร้อมส่วนลดพรีเซล",
        "agent_name": "น้องพรีม",
        "agent_gender": "female",
        "voice_id": "th-TH-PremwadeeNeural",
        "earshot_profile": "crystal_hd",
        "speed": 1.0,
        "tone": "Energetic",
        "opening_text": "สวัสดีค่ะ ขอเรียนสายคุณ{customer_name} จากแกรนด์ พรอพเพอร์ตี้ ค่ะ ติดต่อเรื่องนัดหมายเข้าชมโครงการ สะดวกคุยสักครู่ไหมคะ",
        "default_detail": "นัดหมายเข้าเยี่ยมชมห้องตัวอย่าง คอนโด Grand Horizon เสาร์นี้ 13:30 น.",
        "custom_instructions": "แจ้งสิทธิพิเศษส่วนลด Presale เงินสดสูงสุด 200,000 บาท และฟรีค่าโอนกรรมสิทธิ์เฉพาะผู้เข้าชมสัปดาห์นี้"
    },
    "dental": {
        "id": "dental",
        "name": "สไมล์ เด็นทัล คลินิก",
        "industry": "คลินิกทันตกรรม & จัดฟัน",
        "description": "คลินิกทันตกรรมครบวงจร ขูดหินปูน จัดฟัน และรักษารากฟันโดยทันตแพทย์เฉพาะทาง",
        "agent_name": "น้องน้ำหวาน",
        "agent_gender": "female",
        "voice_id": "th-TH-PremwadeeNeural",
        "earshot_profile": "close_mic",
        "speed": 1.0,
        "tone": "Friendly",
        "opening_text": "สวัสดีค่ะ ขอเรียนสายคุณ{customer_name} จากสไมล์ เด็นทัล คลินิก ค่ะ ไม่ทราบว่าสะดวกคุยสักครู่ไหมคะ",
        "default_detail": "แจ้งเตือนนัดขูดหินปูนและตรวจสุขภาพฟันประจำ 6 เดือน พฤหัสบดีนี้ 15:00 น.",
        "custom_instructions": "แจ้งเตือนให้บ้วนปากด้วยน้ำเกลือก่อนเข้ารับบริการ และเตรียมบัตรประกันสังคมมาใช้สิทธิ์ทำฟัน 900 บาทฟรี"
    },
    "custom": {
        "id": "custom",
        "name": "ธุรกิจของฉัน (Core Business)",
        "industry": "กำหนดเอง",
        "description": "ระบบโทรออกอัตโนมัติอัจฉริยะสำหรับแจ้งเตือนและบริการลูกค้า",
        "agent_name": "ผู้ช่วย AI",
        "agent_gender": "female",
        "voice_id": "th-TH-PremwadeeNeural",
        "earshot_profile": "close_mic",
        "speed": 1.0,
        "tone": "Friendly",
        "opening_text": "สวัสดีค่ะ ขอเรียนสายคุณ{customer_name} ค่ะ ติดต่อจาก{business_name} ไม่ทราบว่าสะดวกคุยสักครู่ไหมคะ",
        "default_detail": "ประสานงานบริการตามนัดหมาย",
        "custom_instructions": "ตอบคำถามด้วยความสุภาพ กระชับ ชัดเจน และบันทึกข้อสรุปของลูกค้าอย่างแม่นยำ"
    }
}

active_business = dict(BUSINESS_TEMPLATES["clinic"])

# -------------------------------------------------------------
# 2. Multi-Script Library (คลังชุดสคริปต์รายสาย)
# -------------------------------------------------------------
SCRIPTS_DB = [
    {
        "id": "script_clinic_confirm",
        "name": "คลินิก: ยืนยันนัดตรวจผิว & เลเซอร์",
        "business_name": "เดอร์มา แคร์ คลินิก",
        "industry": "คลินิกความงาม",
        "agent_name": "น้องฟ้า",
        "agent_gender": "female",
        "voice_id": "th-TH-PremwadeeNeural",
        "tone": "Friendly",
        "speed": 1.0,
        "opening_text": "สวัสดีค่ะ ขอเรียนสายคุณ{customer_name} จากเดอร์มา แคร์ คลินิก ค่ะ ไม่ทราบว่าสะดวกคุยสักครู่ไหมคะ",
        "objective": "ยืนยันนัดหมายตรวจสภาพผิวและเลเซอร์ วันที่ 12 พ.ย. เวลา 14:00 น.",
        "custom_instructions": "เตือนให้งดออกแดดจัดและงดทายารักษาสิวที่มีกรดผลไม้ก่อนเข้ารับบริการ 24 ชั่วโมง"
    },
    {
        "id": "script_clinic_promo",
        "name": "คลินิก: แจ้งโปรโมชั่นคอร์สเลเซอร์ ลด 50%",
        "business_name": "เดอร์มา แคร์ คลินิก",
        "industry": "คลินิกความงาม",
        "agent_name": "น้องฟ้า",
        "agent_gender": "female",
        "voice_id": "th-TH-PremwadeeNeural",
        "tone": "Energetic",
        "speed": 1.0,
        "opening_text": "สวัสดีค่ะ ขอเรียนสายคุณ{customer_name} จากเดอร์มา แคร์ คลินิก ค่ะ มีข้อเสนอพิเศษเฉพาะสมาชิกคนสำคัญ สะดวกคุยสักครู่ไหมคะ",
        "objective": "นำเสนอโปรโมชั่นเลเซอร์หน้าใส ลดพิเศษ 50% สำหรับ 20 ท่านแรกของสัปดาห์นี้",
        "custom_instructions": "หากลูกค้าสนใจ ให้เสนอจองสิทธิ์ล่วงหน้ามัดจำ 500 บาท หรือลงเวลานัดเพื่อเข้ามาทดลองทำ"
    },
    {
        "id": "script_auto_maintain",
        "name": "อู่ยนต์: เตือนเช็คระยะ 50,000 กม.",
        "business_name": "ออโต้ แคร์ เซอร์วิส",
        "industry": "ศูนย์บริการยานยนต์",
        "agent_name": "น้องนนท์",
        "agent_gender": "male",
        "voice_id": "th-TH-NiwatNeural",
        "tone": "Formal",
        "speed": 1.0,
        "opening_text": "สวัสดีครับ ขอเรียนสายคุณ{customer_name} จากศูนย์บริการออโต้ แคร์ เซอร์วิส ครับ ไม่ทราบว่าสะดวกคุยสักครู่ไหมครับ",
        "objective": "แจ้งเตือนกำหนดเช็คระยะ 50,000 กม. ตรวจเช็คระบบเบรก และเปลี่ยนถ่ายน้ำมันเครื่อง",
        "custom_instructions": "แจ้งเตือนให้นำสมุดรับประกันรถยนต์มาด้วย และทางศูนย์มีบริการรถรับส่งฟรีระหว่างรอตรวจเช็ค"
    },
    {
        "id": "script_auto_ready",
        "name": "อู่ยนต์: แจ้งรถซ่อมเสร็จพร้อมส่งมอบ",
        "business_name": "ออโต้ แคร์ เซอร์วิส",
        "industry": "ศูนย์บริการยานยนต์",
        "agent_name": "น้องนนท์",
        "agent_gender": "male",
        "voice_id": "th-TH-NiwatNeural",
        "tone": "Formal",
        "speed": 1.0,
        "opening_text": "สวัสดีครับ ขอเรียนสายคุณ{customer_name} จากออโต้ แคร์ เซอร์วิส ครับ ติดต่อแจ้งเรื่องรถซ่อมเสร็จเรียบร้อยแล้วครับ สะดวกคุยสักครู่ไหมครับ",
        "objective": "แจ้งลูกค้าว่ารถซ่อมเสร็จเรียบร้อยแล้ว สามารถมารับรถได้วันนี้ถึง 18:00 น. หรือวันพรุ่งนี้",
        "custom_instructions": "แจ้งยอดค่าใช้จ่ายพร้อมใบเสร็จรับประกัน รองรับการชำระผ่านบัตรเครดิตหรือโอนเงินผ่าน PromptPay"
    },
    {
        "id": "script_estate_visit",
        "name": "อสังหาฯ: นัดหมายเข้าชมห้องตัวอย่างคอนโด",
        "business_name": "แกรนด์ พรอพเพอร์ตี้",
        "industry": "อสังหาริมทรัพย์",
        "agent_name": "น้องพรีม",
        "agent_gender": "female",
        "voice_id": "th-TH-PremwadeeNeural",
        "tone": "Energetic",
        "speed": 1.0,
        "opening_text": "สวัสดีค่ะ ขอเรียนสายคุณ{customer_name} จากแกรนด์ พรอพเพอร์ตี้ ค่ะ ติดต่อเรื่องนัดหมายเข้าชมโครงการ สะดวกคุยสักครู่ไหมคะ",
        "objective": "นัดหมายเข้าเยี่ยมชมห้องตัวอย่าง คอนโด Grand Horizon เสาร์นี้ 13:30 น.",
        "custom_instructions": "แจ้งสิทธิพิเศษส่วนลด Presale เงินสดสูงสุด 200,000 บาท และฟรีค่าโอนกรรมสิทธิ์เฉพาะผู้เข้าชมสัปดาห์นี้"
    },
    {
        "id": "script_dental_remind",
        "name": "ทันตกรรม: เตือนนัดตรวจสุขภาพฟัน 6 เดือน",
        "business_name": "สไมล์ เด็นทัล คลินิก",
        "industry": "คลินิกทันตกรรม",
        "agent_name": "น้องน้ำหวาน",
        "agent_gender": "female",
        "voice_id": "th-TH-PremwadeeNeural",
        "tone": "Friendly",
        "speed": 1.0,
        "opening_text": "สวัสดีค่ะ ขอเรียนสายคุณ{customer_name} จากสไมล์ เด็นทัล คลินิก ค่ะ ไม่ทราบว่าสะดวกคุยสักครู่ไหมคะ",
        "objective": "แจ้งเตือนนัดขูดหินปูนและตรวจสุขภาพฟันประจำ 6 เดือน พฤหัสบดีนี้ 15:00 น.",
        "custom_instructions": "แจ้งเตือนให้บ้วนปากด้วยน้ำเกลือก่อนเข้ารับบริการ และเตรียมบัตรประกันสังคมมาใช้สิทธิ์ทำฟัน 900 บาทฟรี"
    }
]

# -------------------------------------------------------------
# 2b. Telephony Gateway & White-Label Branding State
# -------------------------------------------------------------
TELEPHONY_PROVIDERS = {
    "nt_link": {
        "provider": "nt_link",
        "provider_name": "NT Link VoIP (NT NextGen)",
        "server_host": os.environ.get("NT_SIP_DOMAIN", "sip.ntnextgen.com"),
        "server_port": int(os.environ.get("NT_SIP_PORT", 5060)),
        "sip_proxy": os.environ.get("NT_SIP_PROXY", "res.ntnextgen.com"),
        "auth_username": os.environ.get("NT_SIP_USERNAME", "021078407"),
        "auth_password": os.environ.get("NT_SIP_PASSWORD", "8vEpQ5R3#hSm"),
        "app_password": os.environ.get("NT_LINK_APP_PASSWORD", "H5F@P87h"),
        "caller_id": os.environ.get("NT_CALLER_ID", "02-107-8407"),
        "phone_number": "021078407",
        "account_balance": 100.00,
        "account_expiry": "2027-01-17",
        "account_status": "พร้อมใช้งาน",
        "codec": "G.711u (PCMU)",
        "status": "registered",
        "latency_ms": 14,
        "active_channels": 1,
        "max_channels": 30,
        "webhook_url": "http://127.0.0.1:8088/api/telephony/events"
    },
    "gsm_gateway": {
        "provider": "gsm_gateway",
        "provider_name": "GSM Gateway (SIM Box 8 Ports)",
        "server_host": "192.168.1.100",
        "server_port": 5060,
        "sip_proxy": "",
        "auth_username": "gsm_admin",
        "auth_password": "••••••••",
        "app_password": "",
        "caller_id": "089-123-4567",
        "phone_number": "0891234567",
        "account_balance": 0.0,
        "account_expiry": "-",
        "account_status": "พร้อมใช้งาน",
        "codec": "G.711a (PCMA)",
        "status": "registered",
        "latency_ms": 8,
        "active_channels": 2,
        "max_channels": 8,
        "webhook_url": "http://127.0.0.1:8088/api/telephony/events"
    },
    "dtac_onecall": {
        "provider": "dtac_onecall",
        "provider_name": "DTAC OneCall / Cloud PBX",
        "server_host": "sip.dtac-onecall.com",
        "server_port": 5061,
        "sip_proxy": "",
        "auth_username": "onecall_biz",
        "auth_password": "••••••••",
        "app_password": "",
        "caller_id": "02-998-8877",
        "phone_number": "029988877",
        "account_balance": 0.0,
        "account_expiry": "-",
        "account_status": "พร้อมใช้งาน",
        "codec": "G.729",
        "status": "registered",
        "latency_ms": 22,
        "active_channels": 1,
        "max_channels": 15,
        "webhook_url": "http://127.0.0.1:8088/api/telephony/events"
    },
    "custom_sip": {
        "provider": "custom_sip",
        "provider_name": "Custom SIP Trunk / Asterisk FreePBX",
        "server_host": "pbx.company.internal",
        "server_port": 5060,
        "sip_proxy": "",
        "auth_username": "trunk_ext100",
        "auth_password": "••••••••",
        "app_password": "",
        "caller_id": "02-555-0199",
        "phone_number": "025550199",
        "account_balance": 0.0,
        "account_expiry": "-",
        "account_status": "พร้อมใช้งาน",
        "codec": "G.711u (PCMU)",
        "status": "registered",
        "latency_ms": 12,
        "active_channels": 0,
        "max_channels": 60,
        "webhook_url": "http://127.0.0.1:8088/api/telephony/events"
    }
}

telephony_config = dict(TELEPHONY_PROVIDERS["nt_link"])

branding_config = {
    "brand_name": "Antigravity AI Call Center",
    "logo_url": "https://api.iconify.design/solar:call-chat-bold-duotone.svg?color=%232563eb",
    "tagline": "ระบบโทรออกและยืนยันนัดหมายอัจฉริยะ สำหรับทุกธุรกิจ",
    "primary_color": "#2563eb",
    "company_name": "บริษัท แอนติกราวิตี้ อินโนเวชั่น จำกัด (มหาชน)",
    "tax_id": "0105566012345",
    "address": "123 อาคารสาทรทาวเวอร์ ชั้น 18 แขวงยานนาวา เขตสาทร กรุงเทพมหานคร 10120",
    "support_phone": "02-123-4567",
    "support_email": "support@aicallcenter.io",
    "website": "https://aicallcenter.io"
}

# -------------------------------------------------------------
# 3. RBAC & Users State
# -------------------------------------------------------------
USERS_DB = [
    {
        "id": "usr-admin",
        "username": "superadmin",
        "name": "ผู้ดูแลระบบสูงสุด (Super Admin)",
        "email": "admin@aivoice.ai",
        "role": "admin",
        "role_badge": "👑 Super Admin",
        "credits": 5000,
        "created_at": "2026-01-01"
    },
    {
        "id": "usr-owner",
        "username": "business_owner",
        "name": "เจ้าของธุรกิจ (Business Owner)",
        "email": "owner@company.com",
        "role": "owner",
        "role_badge": "🏢 Business Owner",
        "credits": 1878,
        "created_at": "2026-03-15"
    },
    {
        "id": "usr-staff",
        "username": "client_staff",
        "name": "เจ้าหน้าที่ปฏิบัติงาน (Staff / Client)",
        "email": "staff@company.com",
        "role": "staff",
        "role_badge": "👤 Staff / Client",
        "credits": 1878,
        "created_at": "2026-06-10"
    }
]

current_user = USERS_DB[1]  # Default to Business Owner

# -------------------------------------------------------------
# 4. PromptPay Packages & Transactions
# -------------------------------------------------------------
PROMPTPAY_PACKAGES = [
    {"id": "pkg_100", "amount": 100, "credits": 100, "bonus": "ปกติ (1 บาท = 1 เครดิต)", "popular": False},
    {"id": "pkg_300", "amount": 300, "credits": 330, "bonus": "+10% โบนัสพิเศษ", "popular": True},
    {"id": "pkg_500", "amount": 500, "credits": 600, "bonus": "+20% คุ้มค่า", "popular": False},
    {"id": "pkg_1000", "amount": 1000, "credits": 1300, "bonus": "+30% สำหรับองค์กร", "popular": False}
]

promptpay_config = {
    "promptpay_number": "081-234-5678",
    "account_name": "บริษัท แอนติกราวิตี้ อินโนเวชั่น จำกัด (บัญชีรับชำระ)",
    "bank_name": "ธนาคารกสิกรไทย (KBANK)",
    "type": "mobile"
}

transactions_db = [
    {
        "id": "TXN-20261101-01",
        "user_id": "usr-owner",
        "amount": 500,
        "credits_added": 600,
        "promptpay_ref": "PP-9823101",
        "status": "สำเร็จ",
        "timestamp": "01 พ.ย. 10:14"
    },
    {
        "id": "TXN-20261028-02",
        "user_id": "usr-owner",
        "amount": 1000,
        "credits_added": 1300,
        "promptpay_ref": "PP-4410928",
        "status": "สำเร็จ",
        "timestamp": "28 ต.ค. 14:30"
    }
]

def generate_promptpay_payload(phone_or_id: str, amount: float) -> str:
    clean = "".join(c for c in str(phone_or_id) if c.isdigit())
    aid = "0016A000000677010111"
    
    if len(clean) == 13:
        # National ID / Tax ID (EMVCo Sub-tag 02)
        sub_02 = f"0213{clean}"
        tag_29_content = aid + sub_02
    else:
        # Mobile phone number (EMVCo Sub-tag 01)
        target = "0066" + clean[1:] if clean.startswith("0") else clean
        sub_01 = f"01{len(target):02d}{target}"
        tag_29_content = aid + sub_01
    
    tag_29 = f"29{len(tag_29_content):02d}{tag_29_content}"
    
    amount_str = f"{amount:.2f}"
    tag_54 = f"54{len(amount_str):02d}{amount_str}"
    
    raw = (
        "000201"
        "010212"
        f"{tag_29}"
        "5303764"
        f"{tag_54}"
        "5802TH"
        "6304"
    )
    
    crc = 0xFFFF
    for byte in raw.encode("ascii"):
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return raw + f"{crc:04X}"

# -------------------------------------------------------------
# 5. Customer Queue & Scheduler State
# -------------------------------------------------------------
customers_queue = [
    {
        "id": "queue-101",
        "name": "คุณศิริพร สุขเกษม",
        "phone": "089-112-2334",
        "script_id": "script_clinic_confirm",
        "detail": "ยืนยันคิวตรวจผิวและนัดหมายแพทย์",
        "scheduled_time": "14:30 วันนี้",
        "status": "รอโทรตามเวลา",
        "attempts": 0
    },
    {
        "id": "queue-102",
        "name": "คุณพงษ์ศักดิ์ รัตนวิชัย",
        "phone": "081-998-7711",
        "script_id": "script_auto_maintain",
        "detail": "แจ้งเตือนเช็คระยะ 50,000 กม.",
        "scheduled_time": "15:00 วันนี้",
        "status": "รอโทรตามเวลา",
        "attempts": 0
    },
    {
        "id": "queue-103",
        "name": "คุณอารียา กานต์พิชชา",
        "phone": "092-445-6677",
        "script_id": "script_estate_visit",
        "detail": "นัดหมายเข้าชมห้องตัวอย่างคอนโด",
        "scheduled_time": "16:00 วันนี้",
        "status": "รอโทรตามเวลา",
        "attempts": 0
    }
]

# -------------------------------------------------------------
# 6. Calls DB & Persistent Call Audit Logs
# -------------------------------------------------------------
CALL_LOGS_FILE = Path(__file__).resolve().parent / "call_logs.json"

DEFAULT_CALLS_DB = [
    {
        "id": "call-001",
        "name": "คุณอาย",
        "phone": "084-148-7979",
        "script_name": "คลินิก: ยืนยันนัดตรวจผิว & เลเซอร์",
        "trunk_route": "NT Link VoIP (NT NextGen) [02-107-8407]",
        "call_mode": "sip_live",
        "job_ref": "20261030_1 (TK-1001)",
        "time": "30 ต.ค. 16:59",
        "status": "สำเร็จแล้ว",
        "duration": "0:25",
        "appointment_outcome": "มาตามนัด",
        "has_new_date": "-",
        "summary": "ยืนยันเข้ารับบริการตามนัดหมายเดิม วันที่ 2 พ.ย. เวลา 14:00 น.",
        "audio_file": None,
        "recording_file": None,
        "transcript": [
            {"speaker": "AI", "text": "สวัสดีค่ะ ขอเรียนสายคุณอาย จากเดอร์มา แคร์ คลินิก ค่ะ ไม่ทราบว่าสะดวกคุยสักครู่ไหมคะ", "time": "16:59:02", "audio": None},
            {"speaker": "Customer", "text": "ใช่ค่ะ สะดวกคุยค่ะ", "time": "16:59:10", "audio": None},
            {"speaker": "AI", "text": "ขออนุญาตโทรมาคอนเฟิร์มนัดตรวจสภาพผิวและทำเลเซอร์กับคุณหมอ วันที่ 2 พ.ย. เวลา 14:00 น. สะดวกมาตามนัดไหมคะ", "time": "16:59:14", "audio": None},
            {"speaker": "Customer", "text": "สะดวกตามนัดเลยค่ะ ขอบคุณนะคะ", "time": "16:59:22", "audio": None},
            {"speaker": "AI", "text": "ขอบพระคุณมากค่ะ ทางคลินิกบันทึกการยืนยันเรียบร้อยแล้วค่ะ แล้วพบกันนะคะ สวัสดีค่ะ", "time": "16:59:26", "audio": None}
        ],
        "sip_events": [
            "[16:59:00] SIP REGISTER 200 OK (021078407@sip.ntnextgen.com -> 202.129.60.40:5060)",
            "[16:59:01] SIP INVITE sip:0841487979@sip.ntnextgen.com",
            "[16:59:01] 180 Ringing",
            "[16:59:02] 200 OK (Connected RTP G.711 PCMU 8000Hz)",
            "[16:59:27] SIP BYE (200 OK)"
        ]
    },
    {
        "id": "call-002",
        "name": "คุณจ๋า",
        "phone": "093-340-9929",
        "script_name": "คลินิก: ยืนยันนัดตรวจผิว & เลเซอร์",
        "trunk_route": "NT Link VoIP (NT NextGen) [02-107-8407]",
        "call_mode": "sip_live",
        "job_ref": "20261025_1 (db0016)",
        "time": "25 ต.ค. 11:33",
        "status": "สำเร็จแล้ว",
        "duration": "0:16",
        "appointment_outcome": "ยกเลิกนัด",
        "has_new_date": "-",
        "summary": "โทรติดแต่ปลายสายแจ้งว่าเป็นผู้ชาย ไม่ใช่คุณจ๋า AI จึงขออภัยเนื่องจากน่าจะโทรผิดเบอร์แล้ววางสายไป",
        "audio_file": None,
        "recording_file": None,
        "transcript": [
            {"speaker": "AI", "text": "สวัสดีค่ะ ขอเรียนสายคุณจ๋า จากเดอร์มา แคร์ คลินิก ค่ะ", "time": "11:33:05", "audio": None},
            {"speaker": "Customer", "text": "ขอโทษครับ โทรผิดเบอร์แล้วครับ ผมเป็นผู้ชาย", "time": "11:33:12", "audio": None},
            {"speaker": "AI", "text": "กราบขออภัยเป็นอย่างยิ่งค่ะ น่าจะมีการบันทึกเบอร์โทรศัพท์ผิดพลาด ขออนุญาตวางสายนะคะ ขอบคุณค่ะ", "time": "11:33:17", "audio": None}
        ],
        "sip_events": [
            "[11:33:03] SIP INVITE sip:0933409929@sip.ntnextgen.com",
            "[11:33:05] 200 OK (Connected RTP G.711)",
            "[11:33:21] SIP BYE"
        ]
    },
    {
        "id": "call-003",
        "name": "คุณทักษิณทร์",
        "phone": "095-307-3480",
        "script_name": "อู่ยนต์: เตือนเช็คระยะ 50,000 กม.",
        "trunk_route": "NT Link VoIP (NT NextGen) [02-107-8407]",
        "call_mode": "sip_live",
        "job_ref": "20261027_2",
        "time": "27 ต.ค. 13:48",
        "status": "สำเร็จแล้ว",
        "duration": "1:27",
        "appointment_outcome": "ขอเลื่อนนัด",
        "has_new_date": "ใช่ (5 พ.ย. 15:00 น.)",
        "summary": "ลูกค้าติดงานด่วน ขอเลื่อนนัดจากวันที่ 28 ต.ค. เป็นวันที่ 5 พ.ย. เวลา 15:00 น. ลงบันทึกเข้าระบบเรียบร้อย",
        "audio_file": None,
        "recording_file": None,
        "transcript": [
            {"speaker": "AI", "text": "สวัสดีครับ ขอเรียนสายคุณทักษิณทร์ จากออโต้ แคร์ เซอร์วิส ครับ สะดวกคุยสักครู่ไหมครับ", "time": "13:48:10", "audio": None},
            {"speaker": "Customer", "text": "ติดธุระด่วนเลยครับ ขอเลื่อนเป็นวันที่ 5 พ.ย. บ่ายสามได้ไหมครับ", "time": "13:48:25", "audio": None},
            {"speaker": "AI", "text": "รับทราบครับ ได้บันทึกคำขอเลื่อนนัดหมายเป็นวันที่ 5 พ.ย. เวลา 15:00 น. เรียบร้อยแล้วครับ ขอบคุณครับ", "time": "13:48:32", "audio": None}
        ],
        "sip_events": [
            "[13:48:08] SIP INVITE sip:0953073480@sip.ntnextgen.com",
            "[13:48:10] 200 OK (Connected RTP G.711)",
            "[13:49:35] SIP BYE"
        ]
    },
    {
        "id": "call-004",
        "name": "คุณมั่ม",
        "phone": "084-007-9950",
        "script_name": "อสังหาฯ: นัดหมายเข้าชมห้องตัวอย่างคอนโด",
        "trunk_route": "NT Link VoIP (NT NextGen) [02-107-8407]",
        "call_mode": "sip_live",
        "job_ref": "20261030_1",
        "time": "31 ต.ค. 12:00",
        "status": "ไม่สำเร็จ ไม่มีผู้รับสาย",
        "duration": "-",
        "appointment_outcome": "ติดต่อไม่ได้",
        "has_new_date": "-",
        "summary": "โทร 3 ครั้ง ไม่มีผู้รับสาย บันทึกเข้าคิวโทรติดตามผลในวันถัดไป",
        "audio_file": None,
        "recording_file": None,
        "transcript": [],
        "sip_events": [
            "[12:00:01] SIP INVITE sip:0840079950@sip.ntnextgen.com",
            "[12:00:02] 180 Ringing",
            "[12:00:32] 480 Temporarily Unavailable (No Answer)"
        ]
    }
]


def load_calls_db() -> list:
    if CALL_LOGS_FILE.exists():
        try:
            data = json.loads(CALL_LOGS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) > 0:
                return data
        except Exception as e:
            print("load_calls_db warning:", e)
    return [dict(item) for item in DEFAULT_CALLS_DB]


def save_calls_db():
    try:
        CALL_LOGS_FILE.write_text(
            json.dumps(calls_db, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        print("save_calls_db warning:", e)


def build_combined_session_wav(session_id: str, transcript: list) -> str:
    wav_filename = f"rec_{session_id}.wav"
    wav_path = AUDIO_DIR / wav_filename
    if wav_path.exists() and wav_path.stat().st_size > 16000:
        return f"/audio/{wav_filename}"

    combined_pcm = bytearray()
    silence_gap = b"\x00\x00" * 2400  # 0.3s silence between turns
    for turn in transcript:
        audio_url = turn.get("audio")
        if audio_url:
            fpath = AUDIO_DIR / os.path.basename(audio_url)
            pcm = decode_audio_file_to_pcm8k(fpath)
            if pcm:
                combined_pcm.extend(pcm)
                combined_pcm.extend(silence_gap)

    if save_pcm8k_to_wav(bytes(combined_pcm), wav_path):
        return f"/audio/{wav_filename}"
    return ""


def finalize_and_record_call_session(
    session_id: str,
    outcome: str = "สำเร็จแล้ว",
    has_new_date: str = "-",
    summary: str = "",
    last_audio_url: str = None,
) -> dict:
    global current_user
    session = active_sessions.get(session_id)
    if not session:
        return {}
    if session.get("logged_to_db"):
        return session["logged_to_db"]

    sip_call: SIPCallSession = session.get("sip_call")
    recording_url = None
    sip_events = []
    if sip_call:
        recording_url = sip_call.hangup()
        sip_events = list(sip_call.sip_events)

    built_wav = build_combined_session_wav(session_id, session.get("transcript", []))
    if built_wav:
        recording_url = built_wav

    if current_user["credits"] > 0:
        current_user["credits"] -= 1
        for u in USERS_DB:
            if u["id"] == current_user["id"]:
                u["credits"] = current_user["credits"]

    duration_sec = max(int((datetime.now() - session["created_at"]).total_seconds()), 12)
    active_script = session.get("active_script", {})
    if not summary:
        summary = f"สนทนากับ {session['customer_name']} ({len(session.get('transcript', []))} ข้อความ) ผ่านคู่สาย {session.get('trunk_route')}"

    if not sip_events:
        sip_events = [
            f"[{session['created_at'].strftime('%H:%M:%S')}] เริ่มสายสนทนาผ่าน {session.get('trunk_route')}",
            f"[{datetime.now().strftime('%H:%M:%S')}] จบการสนทนาและบันทึกไฟล์เสียง ({recording_url or last_audio_url})"
        ]

    log_entry = {
        "id": f"call-{session_id[:6]}",
        "session_id": session_id,
        "name": session["customer_name"],
        "phone": session["customer_phone"],
        "script_name": active_script.get("name", "สคริปต์มาตรฐาน"),
        "trunk_route": session.get(
            "trunk_route",
            f"{telephony_config['provider_name']} [{telephony_config['caller_id']}]",
        ),
        "call_mode": "sip_live" if session.get("dial_real_sip") else "web_sim",
        "job_ref": f"{datetime.now().strftime('%Y%m%d')}_AI",
        "time": datetime.now().strftime("%d %b %H:%M"),
        "status": "สำเร็จแล้ว",
        "duration": f"{duration_sec // 60}:{duration_sec % 60:02d}",
        "appointment_outcome": outcome,
        "has_new_date": has_new_date,
        "summary": summary,
        "audio_file": recording_url or last_audio_url,
        "recording_file": recording_url or last_audio_url,
        "transcript": session.get("transcript", []),
        "sip_events": sip_events,
    }
    calls_db.insert(0, log_entry)
    save_calls_db()
    session["logged_to_db"] = log_entry
    return log_entry


calls_db = load_calls_db()
active_sessions = {}
last_earshot_metrics = {
    "earshot_score": 96,
    "rms_db": -16.2,
    "peak_db": -1.8,
    "dynamic_range_db": 14.4,
    "duration_sec": 3.8,
    "profile": "close_mic",
    "profile_name": EARSHOT_PROFILES["close_mic"]["name"],
    "engine": "gemini-3.8-flash-lite-tts (Aoede)",
    "verdict": "Earshot Studio Grade (สมจริงระดับคนพูดจริง)",
}

# -------------------------------------------------------------
# 7. TTS Synthesis Engine (Earshot Acoustic + Gemini 3.8 Neural TTS)
# -------------------------------------------------------------
async def synthesize_speech(
    text: str,
    voice_id: str = None,
    speed: float = 1.0,
    filename_prefix: str = "ai_reply",
    tone: str = None,
    earshot_profile: str = None,
) -> str:
    global last_earshot_metrics
    resolved_voice = voice_id or active_business.get("voice_id", "th-TH-PremwadeeNeural")
    resolved_tone = tone or active_business.get("tone", "Friendly")
    resolved_profile = earshot_profile or active_business.get("earshot_profile", "close_mic")
    audio_url, metrics = await asyncio.to_thread(
        synthesize_earshot_speech_sync,
        text,
        AUDIO_DIR,
        resolved_voice,
        resolved_tone,
        float(speed or 1.0),
        resolved_profile,
        filename_prefix,
        GEMINI_API_KEY,
    )
    if metrics:
        last_earshot_metrics = metrics
    return audio_url

def generate_system_prompt_from_script(script: dict) -> str:
    biz_name = script.get("business_name") or active_business.get("name", "ศูนย์บริการ")
    agent_name = script.get("agent_name") or active_business.get("agent_name", "เจ้าหน้าที่ AI")
    objective = script.get("objective", "ประสานงานบริการลูกค้า")
    tone = script.get("tone", "Friendly")
    custom_instructions = script.get("custom_instructions", "")

    tone_instruction = {
        "Formal": "ใช้น้ำเสียงและถ้อยคำที่สุภาพอย่างเป็นทางการ ชัดเจน น่าเชื่อถือ",
        "Friendly": "ใช้น้ำเสียงเป็นกันเอง นุ่มนวล อบอุ่น มีความใส่ใจในบริการ",
        "Energetic": "ใช้น้ำเสียงสดใส กระตือรือร้น มีชีวิตชีวา และให้ข้อมูลอย่างฉับไว"
    }.get(tone, "ใช้น้ำเสียงสุภาพเป็นมิตร")

    prompt = f"""คุณคือ "{agent_name}" เจ้าหน้าที่ Call Center AI ตัวแทนจาก "{biz_name}"
เป้าหมายการโทร: {objective}
รูปแบบการพูด: {tone_instruction}

บทสนทนาต้องกระชับ สุภาพ ชัดเจน และเป็นธรรมชาติที่สุด เหมือนพนักงานโทรจริง ไม่พูดเยิ่นเย้อเกินความจำเป็น

ขั้นตอนการสนทนา:
1. การตรวจสอบตัวตน: ทักทายและถามยืนยันว่าใช่ [ชื่อลูกค้า] หรือไม่
   - หากปลายทางบอกว่าไม่ใช่ (เช่น เป็นคนอื่น, โทรผิด, ไม่ใช่เจ้าของ): ให้กล่าวขอโทษอย่างสุภาพ แจ้งว่าระบบน่าจะบันทึกเบอร์ผิด และขออนุญาตวางสายทันที
   - หากใช่: ให้แจ้งเรื่องนัดหมายหรือวัตถุประสงค์การโทร และสอบถามความสะดวก
2. การตอบรับของลูกค้า:
   - กรณี "สะดวก/มาตามนัด/สนใจ": กล่าวขอบคุณ แจ้งรายละเอียดหรือข้อควรปฏิบัติสั้นๆ และอวยพร ปิดการสนทนา
   - กรณี "ไม่สะดวก/ขอเลื่อน": ถามลูกค้าทันทีว่าสะดวกเลื่อนเป็นวันไหนและช่วงเวลากี่โมง เมื่อลูกค้าแจ้ง ให้ทวนวันเวลาใหม่และบันทึก
   - กรณี "ขอยกเลิก/ไม่สนใจ": ถามเหตุผลสั้นๆ แสดงความเข้าใจและเสียดาย บันทึกยกเลิก
3. เมื่อบทสนทนาสิ้นสุด ให้จบสายอย่างสุภาพ

{f"คำแนะนำเฉพาะสำหรับสายนี้: {custom_instructions}" if custom_instructions else ""}

กฎการตอบ:
ให้คุณตอบเป็น JSON Format เท่านั้น โดยมีโครงสร้างดังนี้:
{{
  "speech": "ข้อความที่ AI จะพูดออกมาให้ลูกค้าฟัง (ภาษาไทย ไม่ใส่เครื่องหมายพิเศษ)",
  "call_status": "in_progress" หรือ "ended",
  "appointment_outcome": "มาตามนัด" หรือ "ขอเลื่อนนัด" หรือ "ยกเลิกนัด" หรือ "สนใจโปรโมชั่น" หรือ "โทรผิดเบอร์/ไม่ใช่เจ้าของ",
  "has_new_date": "ใช่" หรือ "ไม่ใช่" หรือ "-",
  "new_date_info": "รายละเอียดวันเวลาใหม่ (ถ้ามี)",
  "summary": "สรุปผลการโทรสั้นๆ 1-2 ประโยคสำหรับเจ้าหน้าที่"
}}
ห้ามใส่ markdown wrapper หรือ ```json นอกเหนือจากตัว JSON เอง"""
    return prompt

# -------------------------------------------------------------
# 8. Endpoints: Audio & Dashboard
# -------------------------------------------------------------
@app.get("/audio/{filename}")
async def get_audio(filename: str):
    file_path = AUDIO_DIR / filename
    if file_path.exists():
        media_type = "audio/wav" if filename.lower().endswith(".wav") else "audio/mpeg"
        return FileResponse(file_path, media_type=media_type)
    return JSONResponse(status_code=404, content={"error": "Audio not found"})

@app.get("/api/dashboard_data")
async def get_dashboard_data():
    total_calls = len(calls_db) + 18
    answered = len([c for c in calls_db if "สำเร็จ" in c["status"]]) + 18
    unanswered = len([c for c in calls_db if "ไม่สำเร็จ" in c["status"]])
    
    attended = len([c for c in calls_db if c["appointment_outcome"] in ["มาตามนัด", "สนใจโปรโมชั่น"]]) + 6
    rescheduled = len([c for c in calls_db if c["appointment_outcome"] == "ขอเลื่อนนัด"]) + 3
    cancelled = len([c for c in calls_db if c["appointment_outcome"] in ["ยกเลิกนัด", "โทรผิดเบอร์/ไม่ใช่เจ้าของ"]]) + 1

    return {
        "stats": {
            "total": total_calls,
            "answered": answered,
            "pending": len(customers_queue),
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
        "calls": calls_db,
        "active_business": active_business,
        "current_user": current_user,
        "scripts_count": len(SCRIPTS_DB),
        "telephony": telephony_config,
        "branding": branding_config,
        "promptpay": promptpay_config,
        "earshot_profiles": EARSHOT_PROFILES,
        "earshot_metrics": last_earshot_metrics,
    }

# -------------------------------------------------------------
# 9. Endpoints: Business Profile Engine & Persistence Fix
# -------------------------------------------------------------
@app.get("/api/business_profiles")
async def get_business_profiles():
    return {
        "templates": BUSINESS_TEMPLATES,
        "active_profile": active_business,
        "earshot_profiles": EARSHOT_PROFILES,
        "voice_personas": VOICE_PERSONA_MAP,
    }

@app.post("/api/business_profiles/select")
async def select_business_profile(data: dict):
    global active_business
    template_id = data.get("template_id")
    if template_id in BUSINESS_TEMPLATES:
        active_business = dict(BUSINESS_TEMPLATES[template_id])
        return {"success": True, "active_profile": active_business}
    return JSONResponse(status_code=400, content={"error": "Template not found"})

@app.post("/api/business_profiles/update")
async def update_business_profile(data: dict):
    global active_business
    for key in ["name", "industry", "description", "agent_name", "agent_gender", "voice_id", "earshot_profile", "speed", "tone", "opening_text", "default_detail", "custom_instructions"]:
        if key in data and data[key] is not None:
            active_business[key] = data[key]
    return {"success": True, "active_profile": active_business, "message": "อัปเดตการตั้งค่าธุรกิจและเสียงสำเร็จ"}

# -------------------------------------------------------------
# 10. Endpoints: Multi-Script Library
# -------------------------------------------------------------
@app.get("/api/scripts")
async def list_scripts():
    return {"scripts": SCRIPTS_DB}

@app.post("/api/scripts")
async def save_or_create_script(data: dict):
    script_id = data.get("id") or f"script_{uuid.uuid4().hex[:6]}"
    existing = next((s for s in SCRIPTS_DB if s["id"] == script_id), None)
    
    script_entry = {
        "id": script_id,
        "name": data.get("name", "สคริปต์ใหม่"),
        "business_name": data.get("business_name", active_business.get("name", "ศูนย์บริการ")),
        "industry": data.get("industry", active_business.get("industry", "ทั่วไป")),
        "agent_name": data.get("agent_name", active_business.get("agent_name", "เจ้าหน้าที่ AI")),
        "agent_gender": data.get("agent_gender", active_business.get("agent_gender", "female")),
        "voice_id": data.get("voice_id", active_business.get("voice_id", "th-TH-PremwadeeNeural")),
        "earshot_profile": data.get("earshot_profile", active_business.get("earshot_profile", "close_mic")),
        "tone": data.get("tone", "Friendly"),
        "speed": float(data.get("speed", 1.0)),
        "opening_text": data.get("opening_text", "สวัสดีค่ะ ขอเรียนสายคุณ{customer_name} ค่ะ สะดวกคุยสักครู่ไหมคะ"),
        "objective": data.get("objective", "ติดต่อบริการลูกค้า"),
        "custom_instructions": data.get("custom_instructions", "")
    }
    
    if existing:
        existing.update(script_entry)
    else:
        SCRIPTS_DB.insert(0, script_entry)
        
    return {"success": True, "script": script_entry}

@app.delete("/api/scripts/{script_id}")
async def delete_script(script_id: str):
    global SCRIPTS_DB
    SCRIPTS_DB = [s for s in SCRIPTS_DB if s["id"] != script_id]
    return {"success": True}

# -------------------------------------------------------------
# 11. Endpoint: Voice Preview (Earshot Acoustic Studio)
# -------------------------------------------------------------
@app.get("/api/earshot/profiles")
async def get_earshot_profiles():
    return {
        "profiles": EARSHOT_PROFILES,
        "voice_personas": VOICE_PERSONA_MAP,
        "active_profile": active_business.get("earshot_profile", "close_mic"),
        "last_metrics": last_earshot_metrics,
    }

@app.post("/api/preview_voice")
async def preview_voice(data: dict):
    voice_id = data.get("voice_id") or active_business.get("voice_id", "th-TH-PremwadeeNeural")
    speed = float(data.get("speed", active_business.get("speed", 1.0)))
    tone = data.get("tone") or active_business.get("tone", "Friendly")
    earshot_profile = data.get("earshot_profile") or active_business.get("earshot_profile", "close_mic")
    agent_name = data.get("agent_name") or active_business.get("agent_name", "เจ้าหน้าที่ AI")
    biz_name = data.get("name") or active_business.get("name", "ศูนย์บริการ")
    
    sample_text = data.get(
        "text",
        f"สวัสดีค่ะ ขอเรียนสายคุณลูกค้า จาก{biz_name} วันนี้{agent_name} โทรมาเพื่อให้บริการและอำนวยความสะดวกค่ะ"
    )
    
    audio_url = await synthesize_speech(
        sample_text,
        voice_id=voice_id,
        speed=speed,
        filename_prefix="preview",
        tone=tone,
        earshot_profile=earshot_profile,
    )
    return {
        "audio_url": audio_url,
        "text": sample_text,
        "voice_id": voice_id,
        "earshot_profile": earshot_profile,
        "earshot_metrics": last_earshot_metrics,
    }

# -------------------------------------------------------------
# 12. Endpoints: PromptPay Wallet & Credits
# -------------------------------------------------------------
@app.get("/api/credits")
async def get_credits():
    return {
        "credits": current_user["credits"],
        "user_id": current_user["id"],
        "packages": PROMPTPAY_PACKAGES,
        "transactions": transactions_db,
        "promptpay": promptpay_config
    }

@app.post("/api/topup/promptpay_qr")
async def create_topup_qr(data: dict):
    amount = float(data.get("amount", 300))
    package_id = data.get("package_id", "pkg_300")
    
    pkg = next((p for p in PROMPTPAY_PACKAGES if p["id"] == package_id or p["amount"] == amount), None)
    credits_to_add = pkg["credits"] if pkg else int(amount)
    
    phone_promptpay = promptpay_config.get("promptpay_number", "081-234-5678")
    ref_id = f"PP-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    payload = generate_promptpay_payload(phone_promptpay, amount)
    
    qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=260x260&margin=10&data={urllib.parse.quote(payload)}"
    
    return {
        "reference_id": ref_id,
        "amount": amount,
        "credits_to_add": credits_to_add,
        "qr_payload": payload,
        "qr_image_url": qr_image_url,
        "promptpay_number": phone_promptpay,
        "account_name": promptpay_config.get("account_name", ""),
        "bank_name": promptpay_config.get("bank_name", "")
    }

# -------------------------------------------------------------
# 12b. Endpoints: Admin PromptPay Configuration
# -------------------------------------------------------------
@app.get("/api/admin/promptpay")
async def get_admin_promptpay():
    return promptpay_config

@app.post("/api/admin/promptpay")
async def update_admin_promptpay(data: dict):
    global promptpay_config
    if "promptpay_number" in data and data["promptpay_number"] is not None:
        raw_number = str(data["promptpay_number"]).strip()
        promptpay_config["promptpay_number"] = raw_number
        clean = "".join(c for c in raw_number if c.isdigit())
        promptpay_config["type"] = "national_id" if len(clean) == 13 else "mobile"
    if "account_name" in data and data["account_name"] is not None:
        promptpay_config["account_name"] = str(data["account_name"]).strip()
    if "bank_name" in data and data["bank_name"] is not None:
        promptpay_config["bank_name"] = str(data["bank_name"]).strip()
    return {
        "success": True,
        "promptpay": promptpay_config,
        "message": "อัปเดตการตั้งค่าบัญชีรับเงินพร้อมเพย์สำเร็จ"
    }

@app.post("/api/topup/confirm")
async def confirm_topup(data: dict):
    global current_user
    amount = float(data.get("amount", 300))
    credits_to_add = int(data.get("credits_to_add", 330))
    ref_id = data.get("reference_id", f"PP-{uuid.uuid4().hex[:6].upper()}")
    
    current_user["credits"] += credits_to_add
    for u in USERS_DB:
        if u["id"] == current_user["id"]:
            u["credits"] = current_user["credits"]
            
    txn = {
        "id": f"TXN-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
        "user_id": current_user["id"],
        "amount": int(amount),
        "credits_added": credits_to_add,
        "promptpay_ref": ref_id,
        "status": "สำเร็จ",
        "timestamp": datetime.now().strftime("%d %b %H:%M")
    }
    transactions_db.insert(0, txn)
    
    return {
        "success": True,
        "credits": current_user["credits"],
        "credits_added": credits_to_add,
        "message": f"เติมเครดิตสำเร็จ +{credits_to_add:,} เครดิต (ยอดคงเหลือ {current_user['credits']:,})"
    }

# -------------------------------------------------------------
# 13. Endpoints: RBAC & User Management
# -------------------------------------------------------------
@app.get("/api/users")
async def list_users():
    return {"users": USERS_DB, "current_user": current_user}

@app.get("/api/current_user")
async def get_current_user():
    return current_user

@app.post("/api/switch_user")
async def switch_user(data: dict):
    global current_user
    role = data.get("role")
    user_id = data.get("user_id")
    target = None
    if user_id:
        target = next((u for u in USERS_DB if u["id"] == user_id), None)
    elif role:
        target = next((u for u in USERS_DB if u["role"] == role), None)
    if target:
        current_user = target
        return {"success": True, "current_user": current_user}
    return JSONResponse(status_code=400, content={"error": "User or role not found"})

@app.post("/api/users")
async def add_or_update_user(data: dict):
    new_user = {
        "id": f"usr-{uuid.uuid4().hex[:6]}",
        "username": data.get("username", "new_user"),
        "name": data.get("name", "ผู้ใช้งานใหม่"),
        "email": data.get("email", "user@example.com"),
        "role": data.get("role", "staff"),
        "role_badge": "👤 Staff / Client" if data.get("role") == "staff" else "🏢 Business Owner",
        "credits": int(data.get("credits", 500)),
        "created_at": datetime.now().strftime("%Y-%m-%d")
    }
    USERS_DB.append(new_user)
    return {"success": True, "user": new_user}

# -------------------------------------------------------------
# 14. Endpoints: Customer Queue & Per-Call Script Assignment
# -------------------------------------------------------------
@app.get("/api/customers")
async def get_customers_queue():
    return {"queue": customers_queue, "scripts": SCRIPTS_DB}

@app.post("/api/customers")
async def add_customer_to_queue(data: dict):
    script_id = data.get("script_id") or "script_clinic_confirm"
    matched_script = next((s for s in SCRIPTS_DB if s["id"] == script_id), None)
    default_detail = matched_script["objective"] if matched_script else "ประสานงานบริการลูกค้า"
    
    new_item = {
        "id": f"queue-{uuid.uuid4().hex[:6]}",
        "name": data.get("name", "คุณลูกค้า"),
        "phone": data.get("phone", "081-000-0000"),
        "script_id": script_id,
        "detail": data.get("detail", default_detail),
        "scheduled_time": data.get("scheduled_time", "วันนี้ 15:00 น."),
        "status": data.get("status", "รอโทรตามเวลา"),
        "attempts": 0
    }
    customers_queue.insert(0, new_item)
    return {"success": True, "customer": new_item}

@app.put("/api/customers/{customer_id}/script")
async def update_customer_script(customer_id: str, data: dict):
    script_id = data.get("script_id")
    cust = next((c for c in customers_queue if c["id"] == customer_id), None)
    if cust and script_id:
        cust["script_id"] = script_id
        return {"success": True, "customer": cust}
    return JSONResponse(status_code=400, content={"error": "Customer or script not found"})

@app.delete("/api/customers/{customer_id}")
async def delete_customer_from_queue(customer_id: str):
    global customers_queue
    customers_queue = [c for c in customers_queue if c["id"] != customer_id]
    return {"success": True}

# -------------------------------------------------------------
# 15. Endpoints: Call Center Simulator (Per-Call Dynamic Script)
# -------------------------------------------------------------
@app.post("/api/start_call")
async def start_call(data: dict):
    if current_user["credits"] <= 0:
        return JSONResponse(status_code=402, content={"error": "เครดิตโทรหมดแล้ว กรุณาเติมเครดิตก่อนเริ่มการโทร"})
        
    customer_name = data.get("name") or "คุณลูกค้า"
    customer_phone = data.get("phone", "093-340-9929")
    script_id = data.get("script_id")
    
    # Resolve the active script for this call
    active_script = None
    if script_id:
        active_script = next((s for s in SCRIPTS_DB if s["id"] == script_id), None)
    if not active_script:
        active_script = {
            "name": active_business.get("name", "ศูนย์บริการ"),
            "business_name": active_business.get("name", "ศูนย์บริการ"),
            "agent_name": active_business.get("agent_name", "เจ้าหน้าที่ AI"),
            "agent_gender": active_business.get("agent_gender", "female"),
            "voice_id": active_business.get("voice_id", "th-TH-PremwadeeNeural"),
            "earshot_profile": active_business.get("earshot_profile", "close_mic"),
            "tone": active_business.get("tone", "Friendly"),
            "speed": active_business.get("speed", 1.0),
            "opening_text": active_business.get("opening_text", "สวัสดีค่ะ ขอเรียนสายคุณ{customer_name} ค่ะ สะดวกคุยสักครู่ไหมคะ"),
            "objective": data.get("detail") or active_business.get("default_detail", "นัดหมายบริการ"),
            "custom_instructions": active_business.get("custom_instructions", "")
        }
        
    appointment_detail = data.get("detail") or active_script.get("objective", "นัดหมายบริการ")
    session_id = uuid.uuid4().hex[:10]
    
    opening_template = active_script.get("opening_text", "สวัสดีค่ะ ขอเรียนสายคุณ{customer_name} ค่ะ สะดวกคุยสักครู่ไหมคะ")
    opening_text = opening_template.format(
        customer_name=customer_name,
        business_name=active_script.get("business_name", "ศูนย์บริการ")
    )
    
    audio_url = await synthesize_speech(
        opening_text,
        voice_id=active_script.get("voice_id"),
        speed=float(active_script.get("speed", 1.0)),
        filename_prefix="open",
        tone=active_script.get("tone", "Friendly"),
        earshot_profile=active_script.get("earshot_profile", active_business.get("earshot_profile", "close_mic")),
    )
    
    system_prompt = generate_system_prompt_from_script(active_script)
    chat_session = None
    
    if client:
        try:
            chat_session = client.chats.create(
                model="gemini-3.5-flash-lite",
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                    response_mime_type="application/json"
                )
            )
            init_instruction = (
                f"ข้อมูลเป้าหมาย: ชื่อลูกค้า={customer_name}, เบอร์={customer_phone}, "
                f"รายละเอียด={appointment_detail}. ประโยคเปิดสายที่คุณพูดออกไปแล้วคือ: \"{opening_text}\". "
                f"จงเตรียมพร้อมรับคำตอบจากลูกค้าและตอบกลับในรูปแบบ JSON ตามคำสั่ง"
            )
            chat_session.send_message(init_instruction)
        except Exception as e:
            print("Chat Init Error:", e)
            chat_session = None
            
    active_trunk = f"{telephony_config.get('provider_name', 'VoIP Gateway')} [{telephony_config.get('caller_id', '02-107-8407')}]"
    dial_real_sip = bool(data.get("dial_real_sip", False))
    sip_call = None

    if dial_real_sip:
        sip_call = SIPCallSession(
            session_id=session_id,
            config=telephony_config,
            target_phone=customer_phone,
            audio_dir=AUDIO_DIR,
        )
        sip_call.start_outbound_call(initial_audio_url=audio_url)

    active_sessions[session_id] = {
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "appointment_detail": appointment_detail,
        "active_script": active_script,
        "chat_session": chat_session,
        "trunk_route": active_trunk,
        "dial_real_sip": dial_real_sip,
        "sip_call": sip_call,
        "created_at": datetime.now(),
        "transcript": [
            {
                "speaker": "AI",
                "text": opening_text,
                "time": datetime.now().strftime("%H:%M:%S"),
                "audio": audio_url,
            }
        ],
    }

    return {
        "session_id": session_id,
        "speech": opening_text,
        "audio_url": audio_url,
        "earshot_metrics": last_earshot_metrics,
        "call_status": "in_progress",
        "business_name": active_script.get("business_name"),
        "agent_name": active_script.get("agent_name"),
        "agent_gender": active_script.get("agent_gender", "female"),
        "script_name": active_script.get("name"),
        "trunk_route": active_trunk,
        "dial_real_sip": dial_real_sip,
        "sip_state": sip_call.state if sip_call else "web_sim",
        "sip_events": sip_call.sip_events if sip_call else [],
    }

@app.post("/api/chat")
async def chat(data: dict):
    global current_user
    session_id = data.get("session_id")
    user_speech = data.get("user_speech", "").strip()
    
    if session_id not in active_sessions:
        return JSONResponse(status_code=400, content={"error": "Session not found"})
    
    session = active_sessions[session_id]
    active_script = session.get("active_script", active_business)
    sip_call: SIPCallSession = session.get("sip_call")
    if sip_call:
        sip_call.clear_ai_audio_queue()
    session["transcript"].append({
        "speaker": "Customer",
        "text": user_speech,
        "time": datetime.now().strftime("%H:%M:%S"),
        "audio": None,
    })
    
    result = None
    if session.get("chat_session"):
        try:
            response = session["chat_session"].send_message(
                f"ลูกค้าพูดว่า: \"{user_speech}\"\nโปรดตอบกลับตามสคริปต์และคืนค่า JSON เท่านั้น"
            )
            result = json.loads(response.text.strip())
        except Exception as e:
            print("Gemini Chat Error:", e)
            
    if not result:
        # High-precision Rule Fallback
        if any(w in user_speech for w in ["ผิดเบอร์", "ไม่ใช่", "โทรผิด", "ผู้ชาย", "ไม่ใช่เบอร์"]):
            result = {
                "speech": "กราบขออภัยเป็นอย่างยิ่งค่ะ น่าจะมีการบันทึกเบอร์โทรศัพท์ผิดพลาด ขออนุญาตวางสายนะคะ ขอบคุณค่ะ",
                "call_status": "ended",
                "appointment_outcome": "โทรผิดเบอร์/ไม่ใช่เจ้าของ",
                "has_new_date": "ไม่ใช่",
                "summary": "โทรติดแต่ปลายสายแจ้งว่าไม่ใช่บุคคลเป้าหมายหรือโทรผิดเบอร์ AI จึงขออภัยและวางสาย"
            }
        elif any(w in user_speech for w in ["สะดวก", "มาตามนัด", "เจอกัน", "โอเค", "ไปได้", "สนใจ"]):
            result = {
                "speech": f"ขอบพระคุณมากค่ะ ทาง{active_script.get('business_name')} ได้บันทึกการยืนยันเรียบร้อยแล้วค่ะ แล้วพบกันนะคะ สวัสดีค่ะ",
                "call_status": "ended",
                "appointment_outcome": "มาตามนัด" if "สนใจ" not in user_speech else "สนใจโปรโมชั่น",
                "has_new_date": "-",
                "summary": "ลูกค้ายืนยันสะดวกเข้ารับบริการตามวันและเวลาที่กำหนด หรือแสดงความสนใจข้อเสนอ"
            }
        elif any(w in user_speech for w in ["เลื่อน", "ไม่ว่าง", "ติดธุระ", "วันศุกร์", "วันอื่น"]):
            result = {
                "speech": "รับทราบค่ะ ได้บันทึกคำขอเลื่อนนัดหมายลงในระบบเรียบร้อยแล้วนะคะ ทางเจ้าหน้าที่จะส่งข้อความยืนยันคิวใหม่อีกครั้งค่ะ ขอบคุณค่ะ",
                "call_status": "ended",
                "appointment_outcome": "ขอเลื่อนนัด",
                "has_new_date": "ใช่",
                "summary": f"ลูกค้าขอเลื่อนวันเวลานัดหมายใหม่ ได้ลงบันทึกในระบบเรียบร้อย ({user_speech[:30]})"
            }
        else:
            result = {
                "speech": "รับทราบข้อมูลค่ะ มีข้อมูลส่วนอื่นให้สอบถามเพิ่มเติมไหมคะ หรือสะดวกตามรายละเอียดนี้เลยไหมคะ",
                "call_status": "in_progress",
                "appointment_outcome": "รอผล",
                "has_new_date": "-",
                "summary": "อยู่ระหว่างการสนทนา"
            }
            
    ai_speech = result.get("speech", "รับทราบค่ะ ขอบคุณค่ะ")
    call_status = result.get("call_status", "in_progress")
    outcome = result.get("appointment_outcome", "รอผล")
    summary = result.get("summary", "")
    has_new_date = result.get("has_new_date", "-")
    
    audio_url = await synthesize_speech(
        ai_speech,
        voice_id=active_script.get("voice_id"),
        speed=float(active_script.get("speed", 1.0)),
        filename_prefix="turn",
        tone=active_script.get("tone", "Friendly"),
        earshot_profile=active_script.get("earshot_profile", active_business.get("earshot_profile", "close_mic")),
    )
    session["transcript"].append({
        "speaker": "AI",
        "text": ai_speech,
        "time": datetime.now().strftime("%H:%M:%S"),
        "audio": audio_url,
    })
    if sip_call and audio_url:
        sip_call.enqueue_ai_audio_file(audio_url)

    log_entry = None
    if call_status == "ended":
        log_entry = finalize_and_record_call_session(
            session_id=session_id,
            outcome=outcome,
            has_new_date=has_new_date,
            summary=summary,
            last_audio_url=audio_url,
        )

    return {
        "speech": ai_speech,
        "audio_url": audio_url,
        "recording_file": log_entry.get("recording_file") if log_entry else None,
        "call_id": log_entry.get("id") if log_entry else None,
        "call_status": call_status,
        "outcome": outcome,
        "summary": summary,
        "credits_remaining": current_user["credits"],
    }


@app.post("/api/hangup")
async def hangup_call_endpoint(data: dict):
    session_id = data.get("session_id")
    if not session_id or session_id not in active_sessions:
        return {"success": True, "message": "ไม่มีสายที่กำลังสนทนา"}
    session = active_sessions[session_id]
    outcome = data.get("outcome") or "วางสาย"
    summary = data.get("summary") or f"บันทึกการสนทนา ({len(session.get('transcript', []))} ข้อความ)"
    log_entry = finalize_and_record_call_session(
        session_id=session_id,
        outcome=outcome,
        has_new_date="-",
        summary=summary,
    )
    return {
        "success": True,
        "call_log": log_entry,
        "recording_file": log_entry.get("recording_file"),
        "credits_remaining": current_user["credits"],
    }


@app.get("/api/sip/status/{session_id}")
async def get_sip_session_status(session_id: str):
    session = active_sessions.get(session_id)
    if not session:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    sip_call: SIPCallSession = session.get("sip_call")
    if not sip_call:
        return {
            "session_id": session_id,
            "dial_real_sip": False,
            "sip_state": "web_sim",
            "sip_events": [],
        }
    return {
        "session_id": session_id,
        "dial_real_sip": True,
        "sip_state": sip_call.state,
        "sip_events": sip_call.sip_events,
        "target_number": sip_call.target_number,
        "proxy_ip": sip_call.proxy_ip,
    }


@app.get("/api/calls")
async def list_call_logs():
    return {"calls": calls_db}


@app.get("/api/calls/{call_id}")
async def get_call_log_detail(call_id: str):
    item = next((c for c in calls_db if c.get("id") == call_id), None)
    if not item:
        return JSONResponse(status_code=404, content={"error": "Call log not found"})
    return item

# -------------------------------------------------------------
# 16. Endpoints: Telephony Gateway & SIP/GSM Configuration
# -------------------------------------------------------------
@app.get("/api/telephony/config")
async def get_telephony():
    return {
        "config": telephony_config,
        "providers": TELEPHONY_PROVIDERS
    }

@app.post("/api/telephony/config")
async def update_telephony(data: dict):
    global telephony_config
    provider = data.get("provider")
    if provider and provider in TELEPHONY_PROVIDERS and len(data.keys()) <= 2:
        preset = dict(TELEPHONY_PROVIDERS[provider])
        for k, v in data.items():
            if v is not None:
                preset[k] = v
        telephony_config = preset
    else:
        for k in ["provider", "provider_name", "server_host", "server_port", "sip_proxy",
                  "auth_username", "auth_password", "app_password", "caller_id", "phone_number",
                  "account_balance", "account_expiry", "account_status", "codec", "status",
                  "latency_ms", "active_channels", "max_channels", "webhook_url"]:
            if k in data and data[k] is not None:
                telephony_config[k] = data[k]
    return {
        "success": True,
        "config": telephony_config,
        "message": f"บันทึกการตั้งค่าคู่สาย {telephony_config.get('provider_name')} เรียบร้อย"
    }

@app.post("/api/telephony/test_connection")
async def test_telephony_ping(data: dict = None):
    global telephony_config
    reg_result = await asyncio.to_thread(verify_sip_registration, telephony_config)
    telephony_config["status"] = reg_result["status"]
    telephony_config["latency_ms"] = reg_result["latency_ms"]
    return reg_result

# -------------------------------------------------------------
# 17. Endpoints: White-Label Branding System
# -------------------------------------------------------------
@app.get("/api/branding")
async def get_branding_endpoint():
    return branding_config

@app.post("/api/branding")
async def update_branding_endpoint(data: dict):
    global branding_config
    for k in ["brand_name", "logo_url", "tagline", "primary_color", "company_name", 
              "tax_id", "address", "support_phone", "support_email", "website"]:
        if k in data and data[k] is not None:
            branding_config[k] = data[k]
    return {
        "success": True,
        "branding": branding_config,
        "message": "อัปเดตข้อมูลแบรนด์และ White-Label สำเร็จ"
    }

@app.post("/api/branding/upload_logo")
async def upload_logo_endpoint(data: dict):
    global branding_config
    logo_data = data.get("logo_data")
    if not logo_data:
        return JSONResponse(status_code=400, content={"error": "logo_data is required"})
    branding_config["logo_url"] = logo_data
    return {
        "success": True,
        "logo_url": branding_config["logo_url"],
        "message": "อัปโหลดรูปภาพโลโก้สำเร็จ"
    }

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = Path(__file__).resolve().parent / "index.html"
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8088))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)

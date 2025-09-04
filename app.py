import os
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from anthropic import Anthropic

# ----- پیکربندی -----
APP_TITLE = "لایحه‌ساز (Claude + FastAPI)"
APP_DESC = "فرم وب برای تولید لایحه رسمی دادگاه با استفاده از Anthropic Claude"
APP_VERSION = "1.0.0"

app = FastAPI(title=APP_TITLE, description=APP_DESC, version=APP_VERSION)

# فایل‌های استاتیک و قالب‌ها
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# کلید API از متغیر محیطی؛ مدل قابل تغییر از محیط
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

def build_prompt(data: dict) -> str:
    return f"""
    لطفاً بر اساس اطلاعات زیر یک **لایحه رسمی دادگاه** به زبان فارسی و با ساختار استاندارد (عنوان، خطاب به دادگاه، شرح وقایع، دلایل و مستندات، استدلال حقوقی، و خواسته نهایی) تنظیم کن. لحن رسمی و موجز باشد و شماره‌گذاری منظم ارائه شود.

    📂 اطلاعات پرونده:
    - شماره پرونده: {data.get('case_no','-')}
    - شعبه: {data.get('branch','-')}
    - دادگاه: {data.get('court','-')}

    👤 طرفین:
    - خواهان/شاکی: {data.get('claimant','-')}
    - خوانده/متهم: {data.get('defendant','-')}
    - وکیل: {data.get('lawyer','-')}

    📝 شرح ماجرا:
    {data.get('facts','-')}

    📑 دلایل و مستندات:
    {data.get('evidence','-')}

    ⚖️ استدلال حقوقی:
    {data.get('legal','-')}

    🙏 درخواست:
    {data.get('request_text','-')}
    """.strip()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": APP_TITLE})

@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    case_no: str = Form(""),
    branch: str = Form(""),
    court: str = Form(""),
    claimant: str = Form(""),
    defendant: str = Form(""),
    lawyer: str = Form("-"),
    facts: str = Form(""),
    evidence: str = Form(""),
    legal: str = Form(""),
    request_text: str = Form("")
):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="کلید ANTHROPIC_API_KEY تنظیم نشده است.")
    try:
        data = {
            "case_no": case_no.strip(),
            "branch": branch.strip(),
            "court": court.strip(),
            "claimant": claimant.strip(),
            "defendant": defendant.strip(),
            "lawyer": lawyer.strip(),
            "facts": facts.strip(),
            "evidence": evidence.strip(),
            "legal": legal.strip(),
            "request_text": request_text.strip(),
        }

        prompt = build_prompt(data)

        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        text = resp.content[0].text if hasattr(resp, "content") else str(resp)
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "title": APP_TITLE,
                "generated": text,
                "data": data
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "title": APP_TITLE,
                "generated": f"❌ خطا در تولید لایحه: {e}",
                "data": None
            },
            status_code=500
        )

@app.get("/healthz")
async def health():
    return {"status": "ok"}

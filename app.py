import os
import uuid
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from anthropic import Anthropic
import aiofiles

APP_TITLE = "لایحه‌ساز (Claude + FastAPI)"
APP_DESC = "وب‌اپ تولید لایحه با امکان آپلود مدارک و بازتولید پس از اصلاح کاربر"
APP_VERSION = "1.1.0"

app = FastAPI(title=APP_TITLE, description=APP_DESC, version=APP_VERSION)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "replace-me-with-secure-key"))

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307") # claude-opus-4-20250514 vs claude-3-haiku-20240307
client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def build_prompt(data: dict, attachments: list[str]=None, previous: str=None, feedback: str=None) -> str:
    attach_text = "بدون فایل" if not attachments else "\n".join([f"- {p}" for p in attachments])
    prev_section = f"\n\nمتن قبلی لایحه:\n{previous}\n" if previous else ""
    feedback_section = f"\n\nاصلاحات کاربر:\n{feedback}\n" if feedback else ""
    return f"""لطفاً بر اساس اطلاعات زیر یک لایحه رسمی دادگاه به زبان فارسی و با ساختار استاندارد (عنوان، خطاب به دادگاه، شرح وقایع، دلایل و مستندات، استدلال حقوقی، و خواسته نهایی) تنظیم کن. لحن رسمی و موجز باشد و شماره‌گذاری منظم ارائه شود.

📂 اطلاعات پرونده:
- شماره پرونونده: {data.get('case_no','-')}
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

📎 فایل‌های پیوست (مسیرهای ذخیره‌شده):
{attach_text}

{prev_section}{feedback_section}

لطفاً متن را شفاف، رسمی و قابل خواندن برای ارائه در دادگاه تنظیم کن."""

@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse('index.html', {'request': request, 'title': APP_TITLE})

@app.post('/generate', response_class=HTMLResponse)
async def generate(request: Request,
                   case_no: str = Form(''),
                   branch: str = Form(''),
                   court: str = Form(''),
                   claimant: str = Form(''),
                   defendant: str = Form(''),
                   lawyer: str = Form('-'),
                   facts: str = Form(''),
                   evidence: str = Form(''),
                   legal: str = Form(''),
                   request_text: str = Form(''),
                   attachments: list[UploadFile] | None = File(None)):
    if not ANTHROPIC_API_KEY or client is None:
        raise HTTPException(status_code=500, detail='کلید ANTHROPIC_API_KEY تنظیم نشده است.')
    try:
        saved = []
        if attachments:
            for up in attachments:
                if up.filename:
                    ext = os.path.splitext(up.filename)[1]
                    fname = f"{uuid.uuid4().hex}{ext}"
                    dest = os.path.join(UPLOAD_DIR, fname)
                    async with aiofiles.open(dest, 'wb') as out:
                        content = await up.read()
                        await out.write(content)
                    saved.append(dest)

        data = {'case_no': case_no.strip(),
                'branch': branch.strip(),
                'court': court.strip(),
                'claimant': claimant.strip(),
                'defendant': defendant.strip(),
                'lawyer': lawyer.strip(),
                'facts': facts.strip(),
                'evidence': evidence.strip(),
                'legal': legal.strip(),
                'request_text': request_text.strip()}

        prompt = build_prompt(data, attachments=saved)
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1500,
            messages=[{'role':'user','content':prompt}]
        )
        text = resp.content[0].text if hasattr(resp, 'content') else str(resp)
        request.session['last_result'] = text
        return templates.TemplateResponse('result.html', {'request': request, 'title': APP_TITLE, 'generated': text, 'data': data, 'attachments': saved})
    except Exception as e:
        return templates.TemplateResponse('result.html', {'request': request, 'title': APP_TITLE, 'generated': f'❌ خطا در تولید لایحه: {e}', 'data': None, 'attachments': []}, status_code=500)

@app.post('/revise', response_class=HTMLResponse)
async def revise(request: Request,
                 feedback: str = Form(...),
                 attachments: list[UploadFile] | None = File(None)):
    if not ANTHROPIC_API_KEY or client is None:
        raise HTTPException(status_code=500, detail='کلید ANTHROPIC_API_KEY تنظیم نشده است.')
    try:
        previous = request.session.get('last_result', '')
        saved = []
        if attachments:
            for up in attachments:
                if up.filename:
                    ext = os.path.splitext(up.filename)[1]
                    fname = f"{uuid.uuid4().hex}{ext}"
                    dest = os.path.join(UPLOAD_DIR, fname)
                    async with aiofiles.open(dest, 'wb') as out:
                        content = await up.read()
                        await out.write(content)
                    saved.append(dest)

        data = {'case_no':'-','branch':'-','court':'-','claimant':'-','defendant':'-','lawyer':'-','facts':'-','evidence':'-','legal':'-','request_text':'-'}
        prompt = build_prompt(data, attachments=saved, previous=previous, feedback=feedback)
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1500,
            messages=[{'role':'user','content':prompt}]
        )
        text = resp.content[0].text if hasattr(resp, 'content') else str(resp)
        request.session['last_result'] = text
        return templates.TemplateResponse('result.html', {'request': request, 'title': APP_TITLE, 'generated': text, 'data': None, 'attachments': saved})
    except Exception as e:
        return templates.TemplateResponse('result.html', {'request': request, 'title': APP_TITLE, 'generated': f'❌ خطا در بازتولید لایحه: {e}', 'data': None, 'attachments': []}, status_code=500)

@app.get('/healthz')
async def health():
    return {'status':'ok'}

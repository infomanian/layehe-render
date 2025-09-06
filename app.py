import os
import base64
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from anthropic import Anthropic

APP_TITLE = "لایحه‌ساز (Claude + FastAPI)"
APP_DESC = "وب‌اپ تولید لایحه با امکان آپلود مدارک و بازتولید پس از اصلاح کاربر"
APP_VERSION = "1.2.0"

app = FastAPI(title=APP_TITLE, description=APP_DESC, version=APP_VERSION)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "replace-me-with-secure-key"))

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if 1 == 1:
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-1-20250805") 
else:
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
has_attachments = False

def build_prompt(data: dict, previous: str = None, feedback: str = None) -> str:
    prev_section = f"\n\nمتن قبلی لایحه:\n{previous}\n" if previous else ""
    feedback_section = f"\n\nاصلاحات کاربر:\n{feedback}\n" if feedback else ""
    attach_text = "این پرونده دارای پیوست (تصویر یا متن) است. لطفاً محتوای آن‌ها را نیز در تنظیم لایحه بررسی و لحاظ کن." if has_attachments else "بدون پیوست"

    return f"""لطفاً بر اساس اطلاعات زیر یک لایحه رسمی دادگاه به زبان فارسی و با ساختار استاندارد (عنوان، خطاب به دادگاه، شرح وقایع، دلایل و مستندات، استدلال حقوقی، و خواسته نهایی) تنظیم کن. لحن رسمی و موجز باشد و شماره‌گذاری منظم ارائه شود.

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

📎 پیوست‌ها:
{attach_text}

{prev_section}{feedback_section}

لطفاً متن را شفاف، رسمی و قابل خواندن برای ارائه در دادگاه تنظیم کن."""


async def process_attachments(attachments: list[UploadFile]):
    """فایل‌ها رو به content blocks برای Claude تبدیل می‌کنه"""
    content_blocks = []
    if attachments:
        global has_attachments 
        has_attachments = True
        for up in attachments:
            if not up.filename:
                continue
            MAX_FILE_SIZE = 1 * 1024 * 1024  # 2MB
            file_bytes = await up.read()
            if len(file_bytes) > MAX_FILE_SIZE:
                raise HTTPException(status_code=400, detail=f'فایل {up.filename} بیش از حد بزرگ است (حداکثر {MAX_FILE_SIZE // (1024*1024)}MB).')
            mime = up.content_type or "application/octet-stream"

            if mime.startswith("image/"):
                # عکس → به صورت بلاک تصویری
                content_blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime,
                        "data": base64.b64encode(file_bytes).decode("utf-8")
                    }
                })
            else:
                # فایل متنی ساده
                try:
                    text = file_bytes.decode("utf-8", errors="ignore")
                except Exception:
                    text = f"[فایل {up.filename} قابل خواندن به صورت متن نبود]"
                content_blocks.append({"type": "text", "text": f"📎 محتوای فایل {up.filename}:\n{text}"})
    return content_blocks


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
        data = {
            'case_no': case_no.strip(),
            'branch': branch.strip(),
            'court': court.strip(),
            'claimant': claimant.strip(),
            'defendant': defendant.strip(),
            'lawyer': lawyer.strip(),
            'facts': facts.strip(),
            'evidence': evidence.strip(),
            'legal': legal.strip(),
            'request_text': request_text.strip()
        }

        base_prompt = build_prompt(data)
        content_blocks = [{"type": "text", "text": base_prompt}]
        content_blocks.extend(await process_attachments(attachments))

        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1500,
            messages=[{'role': 'user', 'content': content_blocks}]
        )
        text = resp.content[0].text if hasattr(resp, 'content') else str(resp)
        request.session['last_result'] = text
        return templates.TemplateResponse('result.html', {'request': request, 'title': APP_TITLE, 'generated': text, 'data': data, 'attachments': [a.filename for a in attachments] if attachments else []})
    except Exception as e:
        return templates.TemplateResponse('result.html', {'request': request, 'title': APP_TITLE, 'generated': f'❌ خطا در تولید لایحه: {e}', 'data': None, 'attachments': []}, status_code=500)


@app.post('/revise', response_class=HTMLResponse)
async def revise(request: Request,
                 feedback: str = Form(...)):
    if not ANTHROPIC_API_KEY or client is None:
        raise HTTPException(status_code=500, detail='کلید ANTHROPIC_API_KEY تنظیم نشده است.')
    try:
        previous = request.session.get('last_result', '')
        data = {'case_no': '-', 'branch': '-', 'court': '-', 'claimant': '-', 'defendant': '-', 'lawyer': '-', 'facts': '-', 'evidence': '-', 'legal': '-', 'request_text': '-'}

        base_prompt = build_prompt(data, previous=previous, feedback=feedback)
       

        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1500,
            messages=[{'role': 'user', 'content': [{"type": "text", "text": base_prompt}]}]
        )
        text = resp.content[0].text if hasattr(resp, 'content') else str(resp)
        request.session['last_result'] = text
        return templates.TemplateResponse('result.html', {'request': request, 'title': APP_TITLE, 'generated': text, 'data': None, 'attachments': []})
    except Exception as e:
        return templates.TemplateResponse('result.html', {'request': request, 'title': APP_TITLE, 'generated': f'❌ خطا در بازتولید لایحه: {e}', 'data': None, 'attachments': []}, status_code=500)


@app.get('/healthz')
async def health():
    return {'status': 'ok'}

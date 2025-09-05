import os
import shutil
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import anthropic

# تنظیمات
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "supersecret"))
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")# claude-opus-4-1-20250805 vs claude-3-haiku-20240307

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# صفحه اصلی (فرم)
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# تولید لایحه
@app.post("/generate", response_class=HTMLResponse)
async def generate_layehe(
    request: Request,
    case_type: str = Form(...),
    plaintiff: str = Form(...),
    defendant: str = Form(...),
    case_subject: str = Form(...),
    case_no: str = Form(""),  # اختیاری
    details: str = Form(...),
    attachments: list[UploadFile] = File(None)
):
    # ذخیره فایل‌ها
    saved_files = []
    file_texts = []
    if attachments:
        for f in attachments:
            file_path = os.path.join(UPLOAD_DIR, f.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(f.file, buffer)
            saved_files.append(file_path)
            try:
                # تلاش برای خوندن محتوای متنی
                with open(file_path, "r", encoding="utf-8", errors="ignore") as txt:
                    file_texts.append(txt.read())
            except Exception:
                file_texts.append(f"(فایل {f.filename} بارگذاری شد ولی متن آن قابل خواندن نیست.)")

    # ساخت پرامپت
    prompt = f"""
نوع پرونده: {case_type}
خواهان: {plaintiff}
خوانده: {defendant}
موضوع دعوا: {case_subject}
شماره پرونده: {case_no if case_no else "ذکر نشده"}
توضیحات تکمیلی:
{details}

مستندات بارگذاری‌شده:
{ "\n\n".join(file_texts) if file_texts else "هیچ مستندی بارگذاری نشد." }
"""

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1000,
            messages=[
                {"role": "user", "content": f"بر اساس اطلاعات زیر یک پیش‌نویس لایحه حقوقی بنویس:\n{prompt}"}
            ]
        )
        result_text = response.content[0].text
    except Exception as e:
        result_text = f"❌ خطا در تولید لایحه: {str(e)}"

    # ذخیره در سشن برای بازتولید
    request.session["last_inputs"] = {
        "case_type": case_type,
        "plaintiff": plaintiff,
        "defendant": defendant,
        "case_subject": case_subject,
        "case_no": case_no,
        "details": details,
    }

    return templates.TemplateResponse("result.html", {
        "request": request,
        "result": result_text,
        "files": saved_files
    })


# بازتولید با اصلاحات
@app.post("/revise", response_class=HTMLResponse)
async def revise_layehe(
    request: Request,
    feedback: str = Form(...),
    attachments: list[UploadFile] = File(None)
):
    last_inputs = request.session.get("last_inputs", {})

    # ذخیره و خواندن فایل‌های جدید
    saved_files = []
    file_texts = []
    if attachments:
        for f in attachments:
            file_path = os.path.join(UPLOAD_DIR, f.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(f.file, buffer)
            saved_files.append(file_path)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as txt:
                    file_texts.append(txt.read())
            except Exception:
                file_texts.append(f"(فایل {f.filename} بارگذاری شد ولی متن آن قابل خواندن نیست.)")

    # پرامپت اصلاحی
    prompt = f"""
پیش‌نویس لایحه اولیه بر اساس اطلاعات کاربر:
{last_inputs}

بازخورد یا اصلاحات کاربر:
{feedback}

مستندات بارگذاری‌شده جدید:
{ "\n\n".join(file_texts) if file_texts else "هیچ مستندی اضافه نشد." }
"""

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1000,
            messages=[
                {"role": "user", "content": f"بر اساس این بازخورد، لایحه را بازنویسی کن:\n{prompt}"}
            ]
        )
        result_text = response.content[0].text
    except Exception as e:
        result_text = f"❌ خطا در بازتولید لایحه: {str(e)}"

    return templates.TemplateResponse("result.html", {
        "request": request,
        "result": result_text,
        "files": saved_files
    })

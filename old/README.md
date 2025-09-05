# 📑 لایحه‌ساز (Claude + FastAPI) — قابل استقرار روی Render

این پروژه یک **وب‌اپ ساده** است که فرم لایحه دادگاه را از کاربر می‌گیرد، 
در سرور به **Anthropic Claude** ارسال می‌کند و متن نهایی لایحه را به کاربر نمایش می‌دهد.
هیچ نیازی به اجرای لوکال برای کاربر نهایی نیست؛ فقط روی Render مستقر کنید.

---

## ⚙️ اجرای محلی (اختیاری برای تست)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your_api_key"
export ANTHROPIC_MODEL="claude-3-sonnet-20240229"   # اختیاری
uvicorn app:app --reload
# بازدید: http://127.0.0.1:8000
```

---

## 🚀 استقرار روی Render (Web Service)

1. این ریپو را در GitHub منتشر کنید.
2. به Render بروید → **New +** → **Web Service**.
3. ریپوی خود را انتخاب کنید.
4. تنظیمات Build و Start:
   - **Build Command**:  
     ```
     pip install -r requirements.txt
     ```
   - **Start Command**:  
     ```
     uvicorn app:app --host 0.0.0.0 --port $PORT
     ```
5. در بخش **Environment Variables**:
   - `ANTHROPIC_API_KEY` را اضافه کنید (Secret).
   - (اختیاری) `ANTHROPIC_MODEL` برای تغییر مدل.
6. Deploy کنید. پس از استقرار، صفحه اصلی `/` فرم را نشان می‌دهد و ارسال آن نتیجه را در صفحه `/generate` نمایش می‌دهد.

> نکته: کلید API فقط در سرور استفاده می‌شود و در فرانت‌اند نمایش داده نمی‌شود.

---

## 🧪 تست سریع پس از استقرار

- به URL سرویس خود بروید (مثلاً `https://your-service.onrender.com/`)، فرم را پر کنید و ارسال بزنید.
- برای سلامت سرویس: `GET /healthz`

---

## 📦 ساختار

```
.
├─ app.py
├─ requirements.txt
├─ templates/
│  ├─ index.html
│  └─ result.html
└─ static/
   └─ styles.css
```

---

## 🔒 نکات امنیتی و هزینه
- حتماً **Rate Limit** و **CAPTCHA** را در صورت عمومی کردن سرویس در نظر بگیرید تا سوءاستفاده نشود.
- می‌توانید در Render حد مصرف تنظیم کنید.
- تولید متون حقوقی حساس است؛ حتماً خروجی را بازبینی کنید.

---

## 🛠 سفارشی‌سازی
- متن Prompt در تابع `build_prompt` داخل `app.py` قابل تغییر است.
- می‌توانید قالب‌ها را در `templates/` و استایل را در `static/styles.css` اصلاح کنید.

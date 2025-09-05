# لایحه‌ساز — نسخه با آپلود و بازتولید

این پروژه یک وب‌اپ با FastAPI است که:
- فرم فارسی به کاربر می‌دهد (قابل استقرار روی Render).
- فایل‌های پیوست را می‌گیرد و در سرور ذخیره می‌کند.
- خروجی لایحه را از Anthropic Claude می‌گیرد و نمایش می‌دهد.
- کاربر می‌تواند باکس اصلاح را پر کند و مدل را دوباره فراخوانی کند.

## اجرای محلی (برای تست)

pip install -r requirements.txt
export ANTHROPIC_API_KEY="your_api_key"
export SESSION_SECRET="a_strong_random_value"
uvicorn app:app --reload
# بازدید: http://127.0.0.1:8000

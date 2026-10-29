@echo off
chcp 65001 > nul
echo ===================================================
echo   تشغيل تطبيق استخراج وتصميم فتاوى إسلام ويب
echo ===================================================
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo حدث خطأ أثناء تشغيل التطبيق. تأكد من تثبيت المتطلبات:
    echo pip install -r requirements.txt
    pause
)


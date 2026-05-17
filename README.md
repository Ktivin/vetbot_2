# vetbot

Telegram-бот для запису на консультації до фахівців.

## Запуск локально

1. Встановіть залежності:
   `pip install -r requirements.txt`
2. Задайте змінні середовища:
   - `BOT_TOKEN`
   - `ADMIN_USER_IDS` (через кому, якщо адміністраторів декілька)
   - `BOT_TIMEZONE` (необов'язково, за замовчуванням `Europe/Kyiv`)
   - `GOOGLE_SHEETS_SPREADSHEET_ID` (необов'язково)
   - `GOOGLE_SHEETS_WORKSHEET_NAME` (необов'язково)
   - `GOOGLE_SHEETS_CONSULTATIONS_WORKSHEET_NAME` (необов'язково)
   - `GOOGLE_SHEETS_CHATS_WORKSHEET_NAME` (необов'язково)
   - `GOOGLE_SHEETS_CHAT_ASSIGNMENTS_WORKSHEET_NAME` (необов'язково)
   - `GOOGLE_SHEETS_EVENTS_WORKSHEET_NAME` (необов'язково)
   - `GOOGLE_SHEETS_REMINDERS_WORKSHEET_NAME` (необов'язково)
   - `GOOGLE_SERVICE_ACCOUNT_JSON` (необов'язково)
   - `WELCOME_BANNER_URL` (необов'язково, пряме посилання на картинку для `/start`)
   - `WELCOME_BANNER_FILE_ID` (необов'язково, Telegram file_id картинки для `/start`)
   Приклад є у файлі `.env.example`.
3. Запустіть бота:
   `python bot.py`

## Основні можливості

- вибір фахівця та формату консультації;
- вибір міста, дати та часу;
- збереження записів у SQLite;
- повідомлення адміністратору про новий запис;
- панель адміністратора зі статусами, фільтрами та керуванням записами;
- обов’язковий збір контакту та базової інформації про хвостика перед записом;
- збереження клієнтів, записів, чатів, подій і нагадувань у SQLite або Google Sheets;
- опціональний брендований банер при старті бота;
- автоматичне видалення застарілих записів.

## Деплой на Render

- для бота з `long polling` використовуйте тип сервісу `worker`, а не `web`;
- не забудьте задати `BOT_TOKEN`, `ADMIN_USER_IDS` і за потреби `BOT_TIMEZONE`;
- для синхронізації з Google Sheets передайте JSON сервісного акаунта в `GOOGLE_SERVICE_ACCOUNT_JSON`.
"# vetbot2" 
"# vetbot_2" 
"# vetbot_2" 

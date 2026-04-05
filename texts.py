SPECIALIST_LABELS = {
    "kynologist": "Кінолог",
    "veterinarian": "Ветеринарний лікар",
    "rehab": "Реабілітолог",
    "behavior": "Фахівець із поведінки тварин",
}

KYNOLOGIST_TYPE_LABELS = {
    "online": "Онлайн-консультація",
    "training": "Індивідуальне тренування",
    "venue": "Запис на майданчик",
}

CONSULTATION_TYPE_LABELS = {
    "online": "Онлайн-консультація",
    "analysis": "Розбір аналізів",
    "call": "Дзвінок у Telegram",
    "message": "Консультація в месенджері",
}

CITY_LABELS = {
    "poltava": "Полтава",
    "brovary": "Бровари",
    "kyiv": "Київ",
}

START_GREETING = (
    "Доброго дня! 🐾\n\n"
    "Я допоможу вам записатися на консультацію до одного з фахівців:\n"
    "• кінолога,\n"
    "• ветеринарного лікаря,\n"
    "• реабілітолога,\n"
    "• фахівця із поведінки тварин.\n\n"
    "Оберіть потрібного фахівця нижче 👇"
)
START_CONTACT_REQUIRED = (
    "Вітаємо! Перш ніж продовжити, будь ласка, поділіться своїм номером телефону.\n\n"
    "Це потрібно, щоб ми могли сформувати клієнтську базу, надсилати нагадування, "
    "сповіщення про вакцинацію, знижки та важливі новини."
)
START_CONTACT_BUTTON = "Поділитися контактом"
START_CONTACT_WRONG = (
    "Будь ласка, скористайтеся кнопкою нижче та надішліть саме свій контакт."
)
PROFILE_ALREADY_SAVED = "Дані вже збережено. Оберіть потрібного фахівця нижче 👇"
PROFILE_ASK_PET_NAME = "Як звати вашого хвостика?"
PROFILE_ASK_BREED = "Яка порода у хвостика? Якщо породи немає, можете написати «метис»."
PROFILE_ASK_AGE = "Скільки хвостику років або місяців?"
PROFILE_ASK_WEIGHT = "Яка приблизна вага хвостика?"
PROFILE_ASK_ISSUE = (
    "Опишіть, будь ласка, питання або проблему, з якою звертаєтеся.\n"
    "Напишіть своє бачення, щоб фахівець міг підготуватися заздалегідь."
)
PROFILE_SAVE_SUCCESS = (
    "Дякуємо! Контакт і базова інформація про хвостика збережені.\n"
    "Тепер можемо перейти до запису."
)
PROFILE_SAVE_ERROR = (
    "❌ Не вдалося зберегти ваші дані через технічну помилку.\n"
    "Будь ласка, спробуйте ще раз трохи пізніше."
)

WELCOME_CHOOSE_SPECIALIST = "Вітаємо! Оберіть фахівця:"
PROMPT_SERVICE_FORMAT = "Оберіть формат послуги:"
PROMPT_CONSULTATION_FORMAT = "Оберіть формат консультації:"
PROMPT_CITY = "Оберіть місто:"
PROMPT_DATE = "Оберіть дату:"
PROMPT_TIME = "Оберіть час:"

SUMMARY_TITLE = "Будь ласка, перевірте дані запису:"
SUMMARY_SPECIALIST = "Спеціаліст"
SUMMARY_TYPE = "Тип консультації"
SUMMARY_DATE = "Дата"
SUMMARY_TIME = "Час"
SUMMARY_CITY = "Місто"
SUMMARY_PET_NAME = "Хвостик"
SUMMARY_PET_BREED = "Порода"
SUMMARY_PET_AGE = "Вік"
SUMMARY_PET_WEIGHT = "Вага"
SUMMARY_ISSUE = "Запит"
SUMMARY_NOTE = "Якщо все правильно, підтвердьте запис нижче."

CONFIRM_BUTTON = "✅ Підтвердити"
CANCEL_BUTTON = "❌ Скасувати"
BACK_BUTTON = "← Назад"

BOOKING_SUCCESS_TITLE = "✅ Ваш запис успішно створено."
BOOKING_SUCCESS_FOOTER = "Очікуйте на підтвердження від адміністратора."
BOOKING_CANCELED = "❌ Запис скасовано."
SLOT_ALREADY_BOOKED = (
    "❌ На цей час уже є запис.\n"
    "Будь ласка, оберіть інший час."
)
NO_TIMES_LEFT_FOR_TODAY = (
    "❌ На сьогодні вільного часу для запису вже немає.\n"
    "Будь ласка, оберіть іншу дату."
)
NO_FREE_TIMES_FOR_DATE = (
    "❌ На {date} вільного часу для запису вже немає.\n"
    "Будь ласка, оберіть іншу дату."
)
PROMPT_TIME_FOR_DATE = "Оберіть зручний час на {date}:"
SLOT_ALREADY_BOOKED_WITH_ALTERNATIVES = (
    "❌ Цей час щойно став недоступним.\n"
    "Оберіть, будь ласка, один із вільних варіантів на {date}:"
)
SLOT_ALREADY_BOOKED_PICK_ANOTHER_DATE = (
    "❌ Цей час щойно став недоступним, а на {date} вільних слотів більше немає.\n"
    "Будь ласка, оберіть іншу дату."
)
CHECK_SLOT_ERROR = (
    "❌ Сталася технічна помилка під час перевірки запису. "
    "Спробуйте ще раз трохи пізніше."
)
SAVE_BOOKING_ERROR = (
    "❌ Не вдалося зберегти запис через технічну помилку. "
    "Спробуйте ще раз трохи пізніше."
)
GENERIC_ERROR_MESSAGE = (
    "❌ Сталася технічна помилка.\n"
    "Будь ласка, спробуйте ще раз трохи пізніше."
)

ADMIN_ACCESS_DENIED = "❌ У вас немає доступу до цієї команди."
ADMIN_NO_RECORDS = "📭 Немає записів."
ADMIN_LOAD_ERROR = "❌ Не вдалося завантажити записи. Спробуйте ще раз пізніше."
ADMIN_RECORDS_TITLE = "📋 Усі записи:\n\n"
ADMIN_TOO_MANY_RECORDS = "\n... (занадто багато записів)"
ADMIN_NEW_RECORD_TITLE = "🔔 Новий запис"
ADMIN_PANEL_TITLE = "Панель адміністратора. Оберіть потрібний розділ:"
ADMIN_MENU_BUTTON = "⬅️ До меню"
ADMIN_FILTER_PENDING = "Нові"
ADMIN_FILTER_CONFIRMED = "Підтверджені"
ADMIN_FILTER_TODAY = "Сьогодні"
ADMIN_FILTER_TOMORROW = "Завтра"
ADMIN_FILTER_ALL = "Усі записи"
ADMIN_CARD_TITLE = "Запис"
ADMIN_CARD_FILTER = "Фільтр"
ADMIN_CARD_STATUS = "Статус"
ADMIN_CARD_SPECIALIST = "Спеціаліст"
ADMIN_CARD_TYPE = "Тип консультації"
ADMIN_CARD_DATE = "Дата"
ADMIN_CARD_TIME = "Час"
ADMIN_CARD_CITY = "Місто"
ADMIN_CARD_USER = "Користувач"
ADMIN_CARD_PHONE = "Телефон"
ADMIN_CARD_PET_NAME = "Хвостик"
ADMIN_CARD_PET_BREED = "Порода"
ADMIN_CARD_PET_AGE = "Вік"
ADMIN_CARD_PET_WEIGHT = "Вага"
ADMIN_CARD_ISSUE = "Запит"
ADMIN_ACTION_CONFIRM = "✅ Підтвердити"
ADMIN_ACTION_CANCEL = "❌ Скасувати"
ADMIN_ACTION_COMPLETE = "☑️ Завершити"
ADMIN_ACTION_PREVIOUS = "⬅️ Попередній"
ADMIN_ACTION_NEXT = "Наступний ➡️"
ADMIN_FILTER_EMPTY = "За цим фільтром записів поки немає."
ADMIN_RECORD_NOT_FOUND = "❌ Цей запис не знайдено."
ADMIN_STATUS_UPDATED = "Статус запису оновлено."
ADMIN_STATUS_ALREADY_SET = "Статус уже встановлено."
ADMIN_STATUS_UPDATE_ERROR = "❌ Не вдалося оновити статус запису. Спробуйте ще раз пізніше."

USER_BOOKING_CONFIRMED = (
    "✅ Ваш запис підтверджено адміністратором."
)
USER_BOOKING_CANCELLED = (
    "❌ Ваш запис скасовано адміністратором."
)
USER_BOOKING_COMPLETED = (
    "✅ Вашу консультацію позначено як завершену.\n"
    "Дякуємо, що скористалися нашими послугами."
)
NO_USERNAME = "без імені користувача"

"""
Smart date parser — mijoz turli formatda yozgan sanani tushunadi.

Qaytaradi:
- ('days', N) — agar N kun qoldi deb tushunilsa
- ('date', date) — aniq sana topilsa
- ('unclear', None) — tushunarsiz, admin tasdig'i kerak
"""

import re
from datetime import date, datetime, timedelta


# Oy nomlari (uzbek + ruscha + lotin)
MONTHS = {
    "yanvar": 1, "fevral": 2, "mart": 3, "aprel": 4, "may": 5, "iyun": 6,
    "iyul": 7, "avgust": 8, "sentabr": 9, "sentyabr": 9, "oktabr": 10,
    "oktyabr": 10, "noyabr": 11, "dekabr": 12,

    "январь": 1, "февраль": 2, "март": 3, "апрель": 4, "май": 5, "июнь": 6,
    "июль": 7, "август": 8, "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12,
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,

    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,

    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_smart_date(text: str) -> tuple[str, object]:
    """
    text → ('days', N) | ('date', date) | ('unclear', None)
    """
    if not text:
        return ("unclear", None)

    t = text.lower().strip()

    # ───────────────────────────────
    # 1. ANIQ SANA: DD.MM.YYYY, DD-MM-YYYY, DD/MM/YYYY
    # ───────────────────────────────
    m = re.search(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\b", t)
    if m:
        d, mo, y = map(int, m.groups())
        try:
            result = date(y, mo, d)
            if result > date.today():
                return ("date", result)
        except ValueError:
            pass

    # ───────────────────────────────
    # 2. SANA + OY NOMI: "15 may 2027" yoki "15 may"
    # ───────────────────────────────
    m = re.search(r"\b(\d{1,2})\s+([a-zA-Zа-яА-Я]+)\s*(\d{4})?\b", t)
    if m:
        d, month_name, y = m.groups()
        d = int(d)
        month_name = month_name.lower()
        if month_name in MONTHS:
            mo = MONTHS[month_name]
            y = int(y) if y else date.today().year
            try:
                result = date(y, mo, d)
                # Agar yil belgilanmagan bo'lsa va sana o'tib ketgan bo'lsa, keyingi yilga
                if result <= date.today() and not m.group(3):
                    result = date(y + 1, mo, d)
                if result > date.today():
                    return ("date", result)
            except ValueError:
                pass

    # ───────────────────────────────
    # 3. "N kun" / "N hafta" / "N oy" / "N yil"
    # ───────────────────────────────
    m = re.search(r"\b(\d{1,4})\s*(kun|hafta|oy|yil|day|week|month|year|день|дня|дней|неделя|месяц|год)?\b", t)
    if m:
        n = int(m.group(1))
        unit = (m.group(2) or "kun").lower()

        if n == 0 or n > 3650:
            return ("unclear", None)

        if unit in ("kun", "day", "день", "дня", "дней"):
            days = n
        elif unit in ("hafta", "week", "неделя"):
            days = n * 7
        elif unit in ("oy", "month", "месяц"):
            days = n * 30
        elif unit in ("yil", "year", "год"):
            days = n * 365
        else:
            days = n

        # Agar matn juda uzun bo'lsa va faqat raqam emas — ishonchsiz
        if len(t.split()) > 6 and not re.search(r"\b(kun|hafta|oy|yil|qoldi)\b", t):
            return ("unclear", None)

        return ("days", days)

    # ───────────────────────────────
    # 4. "keyingi yil mart", "ertaga" va h.k.
    # ───────────────────────────────
    if "ertaga" in t or "tomorrow" in t:
        return ("date", date.today() + timedelta(days=1))

    if "keyingi oy" in t or "next month" in t:
        d = date.today()
        return ("date", d + timedelta(days=30))

    if "keyingi yil" in t or "next year" in t:
        for name, mo in MONTHS.items():
            if name in t and len(name) > 3:  # qisqa "may" boshqa so'zga aralashmasin
                try:
                    return ("date", date(date.today().year + 1, mo, 15))
                except ValueError:
                    pass
        return ("date", date.today() + timedelta(days=365))

    return ("unclear", None)


def days_from_today(target: date) -> int:
    """Bugundan target sanasigacha necha kun."""
    return (target - date.today()).days
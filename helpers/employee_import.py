"""Excel (client ပေးတဲ့ employee list) ကို EmployeeModel ထဲ ထည့်တဲ့ helper.

Client ရဲ့ မူရင်း sheet ဟာ header က အတန်း (၂) မှာ ရှိပြီး ရက်စွဲတွေ ကို
dd/mm/yyyy, dd.mm.yyyy, "21/ 8 /2027" စသဖြင့် ရောနှော ရေးထားတာမို့
header ကို ရှာပြီး ရက်စွဲကို လိုက်လျောညီထွေ parse လုပ်ပါတယ်။
"""

import re
import secrets
import string
from datetime import date, datetime, time, timedelta

import openpyxl
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import EmployeeModel, UserModel

# Excel header (normalize လုပ်ပြီးသား) -> EmployeeModel field
HEADER_MAP = {
    "no": "_skip",
    "department": "work_department",
    "firstjobsdate": "start_date",
    "empno": "employee_number",
    "name": "_name",
    "passportno": "passport_number",
    "newpass": "new_passport_number",
    "passportdateofexp": "passport_expiry_date",
    "newpassportdateofexp": "new_passport_expiry_date",
    "visadateofissue": "visa_issue_date",
    "visadateofexp": "visa_expiry_date",
    "taxid": "tax_id_number",
    "pakan": "pakan_number",
    "workpermitno": "work_permit_number",
    "id": "identification_number",
    "workpermitdateofissue": "work_permit_issue_date",
    "workpermitdateofexp": "work_permit_expiry_date",
    "pinkcard": "pink_card_number",
    "90daystart": "report_90day_start_date",
    "90update": "_90update",
    "type": "work_permit_type",
    "update": "internal_note",
}

PREFIX_CHOICES = ("Mr.", "Mrs.", "Ms.")
_PREFIX_RE = re.compile(r"^(mr|mrs|ms|miss)\.?\s*", re.IGNORECASE)
_SUFFIX_WORDS = ("\u200b",)

DATE_FIELDS = {
    "start_date",
    "passport_expiry_date",
    "new_passport_expiry_date",
    "visa_issue_date",
    "visa_expiry_date",
    "work_permit_issue_date",
    "work_permit_expiry_date",
    "report_90day_start_date",
}


def normalize_header(value):
    """Header စာသားကို အသေးစိတ် မခွဲခြားဘဲ နှိုင်းယှဉ်နိုင်တဲ့ key ပြောင်းသည်."""
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("\u00a0", " ")
    return re.sub(r"[^0-9a-zA-Z]", "", text).lower()


def parse_flexible_date(value):
    """Excel ရဲ့ ရက်စွဲ ကို date object ပြောင်းသည်. မရရင် None."""
    if value is None or isinstance(value, (time,)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        try:
            return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()
        except (OverflowError, ValueError):
            return None

    text = str(value).strip()
    if not text:
        return None

    numbers = re.findall(r"\d+", text)
    if len(numbers) < 3:
        return None

    day, month, year = (int(n) for n in numbers[:3])
    if year < 100:
        year += 2000 if year < 50 else 1900
    # dd/mm/yyyy ကို အခြေခံပြီး မဖြစ်နိုင်ရင် mm/dd/yyyy လို့ ယူဆ
    if month > 12 and day <= 12:
        day, month = month, day
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def clean_text(value):
    """Text field အတွက် တန်ဖိုး သန့်ရှင်းရေး (Excel time/date artifact တွေကို ဖြုတ်)."""
    if value is None:
        return ""
    if isinstance(value, (datetime, date, time)):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    for word in _SUFFIX_WORDS:
        text = text.replace(word, "")
    return text.strip()


def parse_name(raw_name):
    """'MS.ZON MAY ME TAR' -> ('Ms.', 'ZON MAY ME TAR')."""
    text = clean_text(raw_name)
    if not text:
        return "", ""
    match = _PREFIX_RE.match(text)
    if not match:
        return "", text
    token = match.group(1).lower()
    prefix = {"mr": "Mr.", "mrs": "Mrs.", "ms": "Ms.", "miss": "Ms."}[token]
    return prefix, text[match.end():].strip()


def generate_password():
    alphabet = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(10))
        if any(c.isdigit() for c in password) and any(c.isalpha() for c in password):
            return password


def build_login_email(employee_number, passport_number):
    local = (employee_number or passport_number or "").strip().lower()
    if not local:
        return ""
    local = re.sub(r"[^0-9a-z]+", "", local)
    if not local:
        return ""
    domain = getattr(settings, "EMPLOYEE_LOGIN_EMAIL_DOMAIN", "worker.mudita.local")
    return f"{local}@{domain}"


def _find_header_row(rows):
    """Header အတန်းကို ရှာသည် (known header အများဆုံး ပါတဲ့ အတန်း)."""
    best_row = None
    best_hits = 0
    for index, row in enumerate(rows[:15]):
        hits = sum(1 for cell in row if normalize_header(cell) in HEADER_MAP)
        if hits > best_hits:
            best_hits = hits
            best_row = index
    if best_row is None or best_hits < 3:
        return None, {}
    mapping = {}
    mapped_columns = set()
    for column_index, cell in enumerate(rows[best_row]):
        key = normalize_header(cell)
        if key in HEADER_MAP:
            mapping.setdefault(HEADER_MAP[key], []).append(column_index)
            mapped_columns.add(column_index)
    mapping["_extra"] = [
        index for index in range(len(rows[best_row])) if index not in mapped_columns
    ]
    return best_row, mapping


def read_employee_rows(file_obj, sheet_name=None):
    """Excel ဖိုင်မှ data row တွေကို dict အဖြစ် ပြန်သည်.

    return: (rows, meta) ; rows = [{"row_number": int, "data": {...}}]
    """
    workbook = openpyxl.load_workbook(file_obj, data_only=True, read_only=True)
    sheet = workbook[sheet_name] if sheet_name else workbook.worksheets[0]
    raw_rows = [[cell for cell in row] for row in sheet.iter_rows(values_only=True)]
    workbook.close()

    header_index, mapping = _find_header_row(raw_rows)
    if header_index is None:
        return [], {"error": "Employee header ကို ရှာမတွေ့ပါ။"}

    rows = []
    for offset, raw_row in enumerate(raw_rows[header_index + 1:], start=header_index + 2):
        if raw_row is None or all(cell is None or str(cell).strip() == "" for cell in raw_row):
            continue

        data = {}
        updates = []
        extra_notes = []
        for field, columns in mapping.items():
            if field in ("_name", "_skip", "_extra"):
                continue
            if field == "_90update":
                for column in columns:
                    parsed = parse_flexible_date(raw_row[column]) if column < len(raw_row) else None
                    if parsed:
                        updates.append(parsed)
                continue
            column = columns[0]
            if column >= len(raw_row):
                continue
            value = raw_row[column]
            if field == "internal_note":
                text = clean_text(value)
                if text:
                    data[field] = text
            elif field in DATE_FIELDS:
                parsed = parse_flexible_date(value)
                if parsed:
                    data[field] = parsed
            else:
                text = clean_text(value)
                if text:
                    data[field] = text

        name_columns = mapping.get("_name", [])
        if name_columns:
            prefix, full_name = parse_name(raw_row[name_columns[0]])
            if prefix:
                data["prefix_en"] = prefix
            if full_name:
                data["full_name_en"] = full_name

        if not data.get("full_name_en"):
            continue

        # header မရှိတဲ့ အပိုကော်လံတွေမှာ စာသား ရှိရင် note အဖြစ် သိမ်း
        for column in mapping.get("_extra", []):
            text = clean_text(raw_row[column]) if column < len(raw_row) else ""
            if text:
                extra_notes.append(text)
        if extra_notes:
            existing = data.get("internal_note", "")
            data["internal_note"] = " | ".join(filter(None, [existing, *extra_notes]))

        updates = sorted(set(updates))
        for index, update_date in enumerate(updates[:3], start=1):
            data[f"report_90day_update_{index}"] = update_date
        if updates:
            # အသစ်ဆုံး 90-day update ကို နောက်တစ်ကြိမ် report တင်ရမည့် ရက် အဖြစ် သတ်မှတ်
            data["report_90day_date"] = updates[-1]

        rows.append({"row_number": offset, "data": data})

    return rows, {
        "header_row": header_index + 1,
        "columns": sorted(key for key in mapping if not key.startswith("_")),
    }


def import_employees(rows, employer=None, created_by=None, with_accounts=True):
    """Row dict တွေကို EmployeeModel (+ worker account) အဖြစ် ထည့်သည်.

    return: (created, skipped, errors)
    """
    created = []
    skipped = []
    errors = []

    existing_numbers = set(
        EmployeeModel.objects.filter(is_deleted=False)
        .exclude(employee_number__isnull=True)
        .exclude(employee_number="")
        .values_list("employee_number", flat=True)
    )
    existing_passports = set(
        EmployeeModel.objects.filter(is_deleted=False)
        .exclude(passport_number__isnull=True)
        .exclude(passport_number="")
        .values_list("passport_number", flat=True)
    )
    seen_numbers = set()
    seen_passports = set()

    for row in rows:
        data = dict(row["data"])
        row_number = row["row_number"]
        number = data.get("employee_number")
        passport = data.get("passport_number")

        duplicate = (
            (number and (number in existing_numbers or number in seen_numbers))
            or (passport and (passport in existing_passports or passport in seen_passports))
        )
        if duplicate:
            skipped.append(
                {
                    "row_number": row_number,
                    "name": data.get("full_name_en", ""),
                    "reason": "Emp. No. / Passport No. ရှိပြီးသား ဖြစ်နေသည်။",
                }
            )
            continue

        try:
            with transaction.atomic():
                password = ""
                email = ""
                if with_accounts:
                    email = build_login_email(number, passport)
                    if email and UserModel.objects.filter(email__iexact=email).exists():
                        email = ""

                employee = EmployeeModel(
                    employer=employer,
                    status="registration_pending",
                    created_by=created_by,
                    **data,
                )
                employee.save()

                if email:
                    password = generate_password()
                    try:
                        validate_password(password)
                    except ValidationError:
                        password = generate_password() + "Kd9"
                    user = UserModel.objects.create_user(
                        email=email,
                        username=employee.full_name_en,
                        password=password,
                        is_active=True,
                        is_staff=False,
                        is_superuser=False,
                    )
                    employee.user = user
                    employee.login_email = email
                    employee.save(update_fields=["user", "login_email", "updated_at"])

                created.append(
                    {
                        "row_number": row_number,
                        "id": str(employee.id),
                        "employee_number": number or "",
                        "name": employee.full_name_en,
                        "passport_number": passport or "",
                        "login_email": email,
                        "password": password,
                    }
                )
                if number:
                    seen_numbers.add(number)
                if passport:
                    seen_passports.add(passport)
        except Exception as error:  # noqa: BLE001 - row တစ်ခုချင်း error ကို report လုပ်ရန်
            errors.append(
                {
                    "row_number": row_number,
                    "name": data.get("full_name_en", ""),
                    "reason": str(error)[:200],
                }
            )

    return created, skipped, errors

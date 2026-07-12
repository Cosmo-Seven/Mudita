def format_mm_phone(phone):
    phone = phone.strip().replace(" ", "")

    if phone.startswith("+959"):
        return phone

    if phone.startswith("959"):
        return "+" + phone

    if phone.startswith("09"):
        return "+95" + phone[1:]

    return phone

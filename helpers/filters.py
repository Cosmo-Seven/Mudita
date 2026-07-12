from datetime import datetime
from django.db.models import Q, DateField, DateTimeField
from django.core.paginator import Paginator


def filter_querysets(
    request,
    queryset,
    search_fields=None,
    date_field="created_at",
    default_entries=10,
    entries_options=None,
    order="-created_at",
):

    search = request.GET.get("search", "")
    date = request.GET.get("date", "")
    date_range = request.GET.get("date_range", "")
    entries = request.GET.get("entries", default_entries)
    try:
        entries = int(entries)
    except ValueError:
        entries = default_entries

    if entries_options is None:
        entries_options = [10, 20, 30, 50, 100]

    page_number = request.GET.get("page", 1)

    # ---------- Search ----------
    if search and search_fields:
        q_obj = Q()
        for field in search_fields:
            q_obj |= Q(**{f"{field}__icontains": search})
        queryset = queryset.filter(q_obj)

    # ---------- Get field type ----------
    field = queryset.model._meta.get_field(date_field)
    is_datetime = isinstance(field, DateTimeField)
    is_date = isinstance(field, DateField)

    # ---------- Single date filter ----------
    if date and (is_date or is_datetime):
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            if is_datetime:
                queryset = queryset.filter(**{f"{date_field}__date": date_obj})
            else:
                queryset = queryset.filter(**{f"{date_field}": date_obj})
        except ValueError:
            pass

    # ---------- Date range filter ----------
    if date_range and "to" in date_range and (is_date or is_datetime):
        try:
            start_date, end_date = [d.strip() for d in date_range.split("to")]
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            if is_datetime:
                queryset = queryset.filter(
                    **{f"{date_field}__date__range": [start_date, end_date]}
                )
            else:
                queryset = queryset.filter(
                    **{f"{date_field}__range": [start_date, end_date]}
                )
        except ValueError:
            pass

    # ---------- Ordering ----------
    queryset = queryset.order_by(order)
    # queryset = list(queryset) * 10

    # ---------- Pagination ----------

    paginator = Paginator(queryset, entries)
    page_obj = paginator.get_page(page_number)

    current = page_obj.number
    total = paginator.num_pages

    if total <= 5:
        page_range = range(1, total + 1)

    else:
        if current <= 3:
            # 1 2 3 4 ... last
            page_range = [1, 2, 3, 4, "...", total]

        elif current >= total - 2:
            # 1 ... last-3 last-2 last-1 last
            page_range = [1, "...", total - 3, total - 2, total - 1, total]

        else:
            # 1 ... current-1 current current+1 ... last
            page_range = [1, "...", current - 1, current, current + 1, "...", total]

    return {
        "page_obj": page_obj,
        "search": search,
        "date": date,
        "date_range": date_range,
        "entries": entries,
        "entries_options": entries_options,
        "paginator": paginator,
        "page_range": page_range,
    }

from django import template

register = template.Library()


@register.filter
def has_role_permission(user, permission_codename):
    if user.is_authenticated and hasattr(user, "has_permission"):
        return user.has_permission(permission_codename)
    return False


@register.filter
def can(user, permission):
    if not user.is_authenticated:
        return False

    if not permission:
        return True

    if permission == "is_staff":
        return user.is_staff

    if permission == "is_superuser":
        return user.is_superuser

    if permission == "not_superuser":
        return not user.is_superuser

    if permission == "is_developer":
        return getattr(user, "is_developer", False)

    return hasattr(user, "has_permission") and user.has_permission(permission)


@register.filter
def can_any(user, permissions):
    # If permissions is empty or None, allow access
    if not permissions:  # handles [], None, ""
        return True

    # Convert comma-separated string to list
    if isinstance(permissions, str):
        permissions = [p.strip() for p in permissions.split(",")]

    for perm in permissions:
        if isinstance(perm, dict):
            if (not perm.get("permission") or can(user, perm.get("permission"))) and (
                not perm.get("visibility") or can(user, perm.get("visibility"))
            ):
                return True
        else:
            if can(user, perm):
                return True

    return False

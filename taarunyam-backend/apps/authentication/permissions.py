from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Authenticated user with role 'admin' or 'superadmin'."""
    message = 'Admin access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ('admin', 'superadmin')
        )


class IsSuperAdmin(BasePermission):
    """Only superadmin role is allowed."""
    message = 'Super-admin access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'superadmin'
        )

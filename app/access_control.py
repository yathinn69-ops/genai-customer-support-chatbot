from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    """Roles supported by the knowledge-base system."""

    ADMIN = "admin"
    REVIEWER = "reviewer"
    DEVELOPER = "developer"
    VIEWER = "viewer"


@dataclass(frozen=True)
class User:
    """Represents a system user."""

    username: str
    role: Role
    enabled: bool = True


class AccessDeniedError(PermissionError):
    """Raised when a user is not authorized for an operation."""


class AccessController:
    """
    Enforce role-based access control for protected operations.
    """

    PERMISSIONS: dict[str, set[Role]] = {
        "submit": {
            Role.ADMIN,
            Role.REVIEWER,
            Role.DEVELOPER,
        },
        "review": {
            Role.ADMIN,
            Role.REVIEWER,
        },
        "approve": {
            Role.ADMIN,
            Role.REVIEWER,
        },
        "activate": {
            Role.ADMIN,
        },
        "rollback": {
            Role.ADMIN,
        },
        "view": {
            Role.ADMIN,
            Role.REVIEWER,
            Role.DEVELOPER,
            Role.VIEWER,
        },
    }

    def is_allowed(
        self,
        user: User,
        action: str,
    ) -> bool:
        """Return True when the user may perform the action."""

        if not user.enabled:
            return False

        allowed_roles = self.PERMISSIONS.get(action)

        if allowed_roles is None:
            return False

        return user.role in allowed_roles

    def authorize(
        self,
        user: User,
        action: str,
    ) -> None:
        """
        Authorize an action.

        Raises:
            AccessDeniedError: if the user is disabled or unauthorized.
        """

        if not user.enabled:
            raise AccessDeniedError(
                f"User '{user.username}' is disabled"
            )

        if action not in self.PERMISSIONS:
            raise AccessDeniedError(
                f"Unknown action: {action}"
            )

        if user.role not in self.PERMISSIONS[action]:
            raise AccessDeniedError(
                f"User '{user.username}' with role "
                f"'{user.role.value}' is not authorized "
                f"to perform '{action}'"
            )
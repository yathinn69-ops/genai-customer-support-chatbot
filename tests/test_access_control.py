import unittest

from app.access_control import (
    AccessController,
    AccessDeniedError,
    Role,
    User,
)


class TestAccessController(unittest.TestCase):

    def setUp(self):
        self.controller = AccessController()

        self.admin = User(
            username="admin_user",
            role=Role.ADMIN,
        )

        self.reviewer = User(
            username="reviewer_user",
            role=Role.REVIEWER,
        )

        self.developer = User(
            username="developer_user",
            role=Role.DEVELOPER,
        )

        self.viewer = User(
            username="viewer_user",
            role=Role.VIEWER,
        )

    def test_admin_can_activate(self):
        self.assertTrue(
            self.controller.is_allowed(
                self.admin,
                "activate",
            )
        )

        self.controller.authorize(
            self.admin,
            "activate",
        )

    def test_admin_can_rollback(self):
        self.controller.authorize(
            self.admin,
            "rollback",
        )

    def test_reviewer_can_approve(self):
        self.controller.authorize(
            self.reviewer,
            "approve",
        )

    def test_reviewer_cannot_activate(self):
        with self.assertRaises(AccessDeniedError):
            self.controller.authorize(
                self.reviewer,
                "activate",
            )

    def test_developer_can_submit(self):
        self.controller.authorize(
            self.developer,
            "submit",
        )

    def test_developer_cannot_approve(self):
        with self.assertRaises(AccessDeniedError):
            self.controller.authorize(
                self.developer,
                "approve",
            )

    def test_viewer_can_view(self):
        self.controller.authorize(
            self.viewer,
            "view",
        )

    def test_viewer_cannot_submit(self):
        with self.assertRaises(AccessDeniedError):
            self.controller.authorize(
                self.viewer,
                "submit",
            )

    def test_disabled_user_is_denied(self):
        disabled_admin = User(
            username="disabled_admin",
            role=Role.ADMIN,
            enabled=False,
        )

        self.assertFalse(
            self.controller.is_allowed(
                disabled_admin,
                "activate",
            )
        )

        with self.assertRaises(AccessDeniedError):
            self.controller.authorize(
                disabled_admin,
                "activate",
            )

    def test_unknown_action_is_denied(self):
        with self.assertRaises(AccessDeniedError):
            self.controller.authorize(
                self.admin,
                "delete_everything",
            )

    def test_all_roles_can_view(self):
        users = [
            self.admin,
            self.reviewer,
            self.developer,
            self.viewer,
        ]

        for user in users:
            with self.subTest(role=user.role):
                self.assertTrue(
                    self.controller.is_allowed(
                        user,
                        "view",
                    )
                )


if __name__ == "__main__":
    unittest.main()
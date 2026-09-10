import unittest

from app.data_masking import SensitiveDataMasker


class TestSensitiveDataMasker(unittest.TestCase):

    def setUp(self):
        self.masker = SensitiveDataMasker()

    def test_email_is_masked(self):
        result = self.masker.mask(
            "Contact user@example.com for support."
        )

        self.assertIn(
            "[MASKED_EMAIL]",
            result.text,
        )

        self.assertNotIn(
            "user@example.com",
            result.text,
        )

        self.assertEqual(
            result.masked_count,
            1,
        )

    def test_indian_phone_is_masked(self):
        result = self.masker.mask(
            "Call 9876543210 for assistance."
        )

        self.assertIn(
            "[MASKED_PHONE]",
            result.text,
        )

        self.assertNotIn(
            "9876543210",
            result.text,
        )

    def test_api_key_is_masked(self):
        result = self.masker.mask(
            "api_key=ABC123456789XYZ"
        )

        self.assertIn(
            "[MASKED_SECRET]",
            result.text,
        )

        self.assertNotIn(
            "ABC123456789XYZ",
            result.text,
        )

    def test_token_is_masked(self):
        result = self.masker.mask(
            "token: SECRET123456789"
        )

        self.assertIn(
            "[MASKED_SECRET]",
            result.text,
        )

    def test_credit_card_like_number_is_masked(self):
        result = self.masker.mask(
            "Card 4111 1111 1111 1111"
        )

        self.assertIn(
            "[MASKED_CARD]",
            result.text,
        )

        self.assertNotIn(
            "4111 1111 1111 1111",
            result.text,
        )

    def test_multiple_sensitive_values_are_masked(self):
        result = self.masker.mask(
            "Email user@example.com and call 9876543210."
        )

        self.assertEqual(
            result.masked_count,
            2,
        )

    def test_normal_text_is_unchanged(self):
        text = (
            "Employees must follow the refund policy."
        )

        result = self.masker.mask(text)

        self.assertEqual(
            result.text,
            text,
        )

        self.assertEqual(
            result.masked_count,
            0,
        )

    def test_contains_sensitive_data(self):
        self.assertTrue(
            self.masker.contains_sensitive_data(
                "user@example.com"
            )
        )

        self.assertFalse(
            self.masker.contains_sensitive_data(
                "No confidential data here."
            )
        )

    def test_non_string_input_is_rejected(self):
        with self.assertRaises(TypeError):
            self.masker.mask(123)


if __name__ == "__main__":
    unittest.main()
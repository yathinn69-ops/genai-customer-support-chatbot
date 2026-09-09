import unittest
from datetime import datetime, timezone

from app.scheduler import RetryScheduler


class TestRetryScheduler(unittest.TestCase):

    def test_default_retry_delays(self):
        scheduler = RetryScheduler()

        self.assertEqual(
            scheduler.retry_delays,
            (15, 30, 60),
        )

        self.assertEqual(
            scheduler.max_attempts,
            3,
        )

    def test_first_retry_is_after_15_minutes(self):
        scheduler = RetryScheduler()

        failed_at = datetime(
            2026,
            9,
            9,
            20,
            0,
            tzinfo=timezone.utc,
        )

        retry = scheduler.schedule_next(
            failed_at,
            0,
        )

        self.assertIsNotNone(retry)
        self.assertEqual(retry.delay_minutes, 15)
        self.assertEqual(
            retry.scheduled_at,
            datetime(
                2026,
                9,
                9,
                20,
                15,
                tzinfo=timezone.utc,
            ),
        )

    def test_second_retry_is_after_30_minutes(self):
        scheduler = RetryScheduler()

        failed_at = datetime(
            2026,
            9,
            9,
            20,
            0,
            tzinfo=timezone.utc,
        )

        retry = scheduler.schedule_next(
            failed_at,
            1,
        )

        self.assertEqual(retry.delay_minutes, 30)
        self.assertEqual(
            retry.scheduled_at,
            datetime(
                2026,
                9,
                9,
                20,
                30,
                tzinfo=timezone.utc,
            ),
        )

    def test_third_retry_is_after_60_minutes(self):
        scheduler = RetryScheduler()

        failed_at = datetime(
            2026,
            9,
            9,
            20,
            0,
            tzinfo=timezone.utc,
        )

        retry = scheduler.schedule_next(
            failed_at,
            2,
        )

        self.assertEqual(retry.delay_minutes, 60)
        self.assertEqual(
            retry.scheduled_at,
            datetime(
                2026,
                9,
                9,
                21,
                0,
                tzinfo=timezone.utc,
            ),
        )

    def test_no_retry_after_final_attempt(self):
        scheduler = RetryScheduler()

        failed_at = datetime(
            2026,
            9,
            9,
            20,
            0,
            tzinfo=timezone.utc,
        )

        retry = scheduler.schedule_next(
            failed_at,
            3,
        )

        self.assertIsNone(retry)

    def test_all_retry_times(self):
        scheduler = RetryScheduler()

        failed_at = datetime(
            2026,
            9,
            9,
            20,
            0,
            tzinfo=timezone.utc,
        )

        retries = scheduler.all_retry_times(failed_at)

        self.assertEqual(len(retries), 3)

        self.assertEqual(retries[0].delay_minutes, 15)
        self.assertEqual(retries[1].delay_minutes, 30)
        self.assertEqual(retries[2].delay_minutes, 60)

    def test_should_retry(self):
        scheduler = RetryScheduler()

        failed_at = datetime(
            2026,
            9,
            9,
            20,
            0,
            tzinfo=timezone.utc,
        )

        retry = scheduler.schedule_next(
            failed_at,
            0,
        )

        before_retry = datetime(
            2026,
            9,
            9,
            20,
            10,
            tzinfo=timezone.utc,
        )

        after_retry = datetime(
            2026,
            9,
            9,
            20,
            16,
            tzinfo=timezone.utc,
        )

        self.assertFalse(
            scheduler.should_retry(
                before_retry,
                retry,
            )
        )

        self.assertTrue(
            scheduler.should_retry(
                after_retry,
                retry,
            )
        )


if __name__ == "__main__":
    unittest.main()
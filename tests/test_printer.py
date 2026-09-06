import unittest

from cronlint.parser import parse_schedule
from cronlint.printer import describe


class DescribeStandardFieldsTests(unittest.TestCase):
    def test_plain_time(self):
        self.assertEqual(describe(parse_schedule("30 14 * * *")), "at 14:30")

    def test_all_wildcards(self):
        self.assertEqual(
            describe(parse_schedule("* * * * *")),
            "at every minute, every hour",
        )

    def test_step_and_range_combination(self):
        self.assertEqual(
            describe(parse_schedule("*/15 9-17 * * 1-5")),
            "at every 15 minutes, hours 9 through 17, on Monday through Friday",
        )

    def test_day_of_month_only(self):
        self.assertEqual(
            describe(parse_schedule("0 0 13 * *")), "at 00:00, on day 13"
        )

    def test_weekday_only(self):
        self.assertEqual(
            describe(parse_schedule("0 0 * * 5")), "at 00:00, on Friday"
        )

    def test_weekday_seven_prints_as_sunday(self):
        self.assertEqual(
            describe(parse_schedule("0 0 * * 7")), "at 00:00, on Sunday"
        )

    def test_day_and_weekday_combine_with_or(self):
        self.assertEqual(
            describe(parse_schedule("0 0 13 * 5")),
            "at 00:00, on day 13, or on Friday",
        )

    def test_month_restriction(self):
        self.assertEqual(
            describe(parse_schedule("0 0 1 dec *")),
            "at 00:00, on day 1, in December",
        )

    def test_list_in_minute_field(self):
        self.assertEqual(
            describe(parse_schedule("0,15,30,45 * * * *")),
            "at minutes 0, 15, 30, 45, every hour",
        )


class DescribeExtendedFieldsTests(unittest.TestCase):
    def test_seconds_field_included_in_clock_time(self):
        self.assertEqual(describe(parse_schedule("30 0 14 * * *")), "at 14:00:30")

    def test_wildcard_seconds_falls_back_to_minute_hour_only(self):
        self.assertEqual(
            describe(parse_schedule("* 30 14 * * *")), "at 14:30"
        )

    def test_step_seconds_spelled_out(self):
        self.assertEqual(
            describe(parse_schedule("*/10 0 14 * * *")),
            "at every 10 seconds, minute 0, hour 14",
        )

    def test_year_restriction(self):
        self.assertEqual(
            describe(parse_schedule("0 30 0 * 1 * 2030")),
            "at 00:30:00, in January, in year 2030",
        )

    def test_wildcard_year_is_not_mentioned(self):
        self.assertEqual(
            describe(parse_schedule("0 30 0 * * * *")), "at 00:30:00"
        )


if __name__ == "__main__":
    unittest.main()

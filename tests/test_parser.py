import unittest

from cronlint.parser import (
    CronSyntaxError,
    ListExpr,
    Range,
    Star,
    Step,
    Value,
    lint_crontab,
    parse_crontab,
    parse_schedule,
)


class ParseScheduleBasicsTests(unittest.TestCase):
    def test_all_wildcards(self):
        fields = parse_schedule("* * * * *")
        self.assertEqual(fields, (Star(), Star(), Star(), Star(), Star()))

    def test_plain_values(self):
        fields = parse_schedule("5 6 7 8 5")
        self.assertEqual(
            fields, (Value(5), Value(6), Value(7), Value(8), Value(5))
        )

    def test_ranges(self):
        fields = parse_schedule("1-5 0-23 1-31 1-12 0-7")
        self.assertEqual(
            fields,
            (
                Range(1, 5),
                Range(0, 23),
                Range(1, 31),
                Range(1, 12),
                Range(0, 7),
            ),
        )

    def test_step_on_wildcard(self):
        fields = parse_schedule("*/15 * * * *")
        self.assertEqual(fields[0], Step(Star(), 15))

    def test_step_on_range(self):
        fields = parse_schedule("10-40/5 * * * *")
        self.assertEqual(fields[0], Step(Range(10, 40), 5))

    def test_list(self):
        fields = parse_schedule("1,15,30 * * * *")
        self.assertEqual(fields[0], ListExpr((Value(1), Value(15), Value(30))))

    def test_list_with_mixed_items(self):
        fields = parse_schedule("1,10-20,*/5 * * * *")
        self.assertEqual(
            fields[0], ListExpr((Value(1), Range(10, 20), Step(Star(), 5)))
        )

    def test_month_names_case_insensitive(self):
        self.assertEqual(parse_schedule("0 0 1 jan 0")[3], Value(1))
        self.assertEqual(parse_schedule("0 0 1 DEC 0")[3], Value(12))

    def test_weekday_names_case_insensitive(self):
        self.assertEqual(parse_schedule("0 0 1 1 mon")[4], Value(1))
        self.assertEqual(parse_schedule("0 0 1 1 SUN")[4], Value(0))

    def test_weekday_seven_is_accepted_as_sunday_alias(self):
        # The value is kept as 7, not normalized to 0; the printer is what
        # maps it back to Sunday. Just confirm the parser accepts it.
        fields = parse_schedule("0 0 1 1 7")
        self.assertEqual(fields[4], Value(7))


class ParseScheduleErrorTests(unittest.TestCase):
    def test_too_few_fields(self):
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("* * * *")
        self.assertIn("expected 5 fields, found 4", str(ctx.exception))

    def test_empty_string_has_zero_fields(self):
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("")
        self.assertIn("expected 5 fields, found 0", str(ctx.exception))
        self.assertEqual(ctx.exception.column, 1)

    def test_too_many_fields_points_at_extra_token(self):
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("* * * * * *")
        exc = ctx.exception
        self.assertIn("extra token", exc.message)
        self.assertEqual(exc.column, 11)

    def test_out_of_range_value(self):
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("60 * * * *")
        self.assertIn("60 is out of range for minute (expected 0-59)", str(ctx.exception))

    def test_out_of_range_value_column_matches_readme_example(self):
        # Regression check for the exact example quoted in the README.
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("*/15 8-99 * * 1-5")
        exc = ctx.exception
        self.assertEqual(exc.lineno, 1)
        self.assertEqual(exc.column, 8)
        self.assertIn("99 is out of range for hour", exc.message)

    def test_non_numeric_value(self):
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("abc * * * *")
        self.assertIn("invalid value 'abc' in minute field", str(ctx.exception))

    def test_range_missing_end(self):
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("5- * * * *")
        self.assertIn("invalid range '5-' in minute field", str(ctx.exception))

    def test_range_missing_start(self):
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("-5 * * * *")
        self.assertIn("invalid range '-5' in minute field", str(ctx.exception))

    def test_range_start_greater_than_end(self):
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("10-5 * * * *")
        self.assertIn(
            "range start (10) is greater than range end (5) in minute field",
            str(ctx.exception),
        )

    def test_step_missing_value_before_slash(self):
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("/5 * * * *")
        self.assertIn("missing value before '/' in minute field", str(ctx.exception))

    def test_step_missing_value_after_slash(self):
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("5/ * * * *")
        self.assertIn("missing step value after '/' in minute field", str(ctx.exception))

    def test_step_non_numeric(self):
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("5/abc * * * *")
        self.assertIn("invalid step value 'abc'", str(ctx.exception))

    def test_step_zero_is_rejected(self):
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("5/0 * * * *")
        self.assertIn("step value must be a positive integer", str(ctx.exception))

    def test_stray_comma_in_middle_of_list(self):
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("1,,5 * * * *")
        self.assertIn(
            "empty item in minute field (check for stray commas)", str(ctx.exception)
        )

    def test_trailing_comma_in_list(self):
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("1, * * * *")
        self.assertIn(
            "empty item in minute field (check for stray commas)", str(ctx.exception)
        )

    def test_unknown_month_name(self):
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("0 0 1 XYZ 0")
        self.assertIn("invalid value 'XYZ' in month field", str(ctx.exception))

    def test_day_of_week_eight_is_out_of_range(self):
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_schedule("0 0 1 1 8")
        self.assertIn("8 is out of range for day of week (expected 0-7)", str(ctx.exception))


class ParseCrontabTests(unittest.TestCase):
    def test_skips_blank_lines_comments_and_env_assignments(self):
        text = (
            "\n"
            "# nightly jobs\n"
            "PATH=/usr/local/bin:/usr/bin\n"
            "0 2 * * * /usr/local/bin/backup.sh\n"
        )
        entries = parse_crontab(text)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].lineno, 4)
        self.assertEqual(entries[0].command, "/usr/local/bin/backup.sh")

    def test_command_with_arguments_is_kept_whole(self):
        entries = parse_crontab("0 2 * * * /usr/local/bin/backup.sh --verbose --force\n")
        self.assertEqual(
            entries[0].command, "/usr/local/bin/backup.sh --verbose --force"
        )

    def test_multiple_entries_keep_correct_line_numbers(self):
        text = (
            "0 2 * * * /bin/one.sh\n"
            "# comment in between\n"
            "30 3 * * * /bin/two.sh\n"
        )
        entries = parse_crontab(text)
        self.assertEqual([e.lineno for e in entries], [1, 3])

    def test_missing_command_raises_with_line_number(self):
        text = "0 2 * * * /bin/one.sh\n* * * * *\n"
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_crontab(text)
        exc = ctx.exception
        self.assertEqual(exc.lineno, 2)
        self.assertIn("expected 5 schedule fields and a command, found 5 field(s)", exc.message)

    def test_error_line_number_matches_readme_example(self):
        text = (
            "# nightly backup\n"
            "0 2 * * * /usr/local/bin/backup.sh\n"
            "*/5 8-25 * * 1-5 /usr/local/bin/check.sh\n"
        )
        with self.assertRaises(CronSyntaxError) as ctx:
            parse_crontab(text)
        exc = ctx.exception
        self.assertEqual(exc.lineno, 3)
        self.assertEqual(exc.column, 7)
        self.assertIn("25 is out of range for hour", exc.message)


class LintCrontabTests(unittest.TestCase):
    def test_valid_file_has_no_errors(self):
        text = "0 2 * * * /bin/one.sh\n30 3 * * * /bin/two.sh\n"
        entries, errors = lint_crontab(text)
        self.assertEqual(len(entries), 2)
        self.assertEqual(errors, [])

    def test_collects_every_bad_line_not_just_the_first(self):
        text = (
            "60 * * * * /bin/one.sh\n"
            "0 2 * * * /bin/good.sh\n"
            "* * * * 8 /bin/two.sh\n"
        )
        entries, errors = lint_crontab(text)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].command, "/bin/good.sh")
        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0].lineno, 1)
        self.assertIn("60 is out of range for minute", errors[0].message)
        self.assertEqual(errors[1].lineno, 3)
        self.assertIn("8 is out of range for day of week", errors[1].message)

    def test_a_bad_line_does_not_stop_later_valid_lines_from_being_kept(self):
        text = "not enough fields\n0 2 * * * /bin/one.sh\n"
        entries, errors = lint_crontab(text)
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].command, "/bin/one.sh")

    def test_still_skips_comments_blanks_and_env_assignments(self):
        text = (
            "\n"
            "# a comment\n"
            "PATH=/usr/bin\n"
            "60 * * * * /bin/bad.sh\n"
        )
        entries, errors = lint_crontab(text)
        self.assertEqual(entries, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].lineno, 4)


if __name__ == "__main__":
    unittest.main()

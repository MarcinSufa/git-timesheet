import contextlib
import datetime as dt
import io
import json
import unittest

import helpers  # noqa: F401  (sets sys.path)
import holidays as hol


def by_date(year, cc):
    return {h["date"]: h for h in hol.holidays_for_year(year, cc)}


def run_cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = hol.main(list(args))
    return code, out.getvalue(), err.getvalue()


class EasterTest(unittest.TestCase):
    def test_known_dates(self):
        self.assertEqual(hol.easter(2024), dt.date(2024, 3, 31))
        self.assertEqual(hol.easter(2025), dt.date(2025, 4, 20))
        self.assertEqual(hol.easter(2026), dt.date(2026, 4, 5))
        self.assertEqual(hol.easter(2027), dt.date(2027, 3, 28))


class UnitedStatesTest(unittest.TestCase):
    def test_2026_federal_holidays_incl_juneteenth(self):
        h = by_date(2026, "US")
        base = [d for d, x in h.items() if not x["observed"]]
        self.assertEqual(len(base), 11)
        self.assertIn("Juneteenth", h["2026-06-19"]["name"])
        self.assertEqual(h["2026-11-26"]["name"], "Thanksgiving Day")

    def test_observed_days(self):
        h = by_date(2026, "US")
        self.assertTrue(h["2026-07-03"]["observed"])  # Jul 4 2026 is a Saturday
        h27 = by_date(2027, "US")
        self.assertIn("2027-06-18", h27)  # Juneteenth on Saturday -> Friday
        self.assertIn("2027-07-05", h27)  # Independence Day on Sunday -> Monday
        self.assertIn("2027-12-24", h27)
        # New Year's Day 2028 is a Saturday: observed on Fri 2027-12-31
        self.assertEqual(h27["2027-12-31"]["name"], "New Year's Day (observed)")

    def test_no_juneteenth_before_2021(self):
        self.assertNotIn("2020-06-19", by_date(2020, "US"))


class PolandTest(unittest.TestCase):
    def test_christmas_eve_since_2025(self):
        self.assertIn("2025-12-24", by_date(2025, "PL"))
        self.assertIn("2026-12-24", by_date(2026, "PL"))
        self.assertNotIn("2024-12-24", by_date(2024, "PL"))

    def test_polish_names(self):
        h = by_date(2026, "PL")
        self.assertEqual(h["2026-05-03"]["name"], "Święto Narodowe Trzeciego Maja")
        self.assertEqual(h["2026-05-03"]["name_en"], "Constitution Day")
        self.assertEqual(h["2026-06-04"]["name"], "Boże Ciało")
        self.assertEqual(h["2026-04-06"]["name"], "Poniedziałek Wielkanocny")

    def test_no_substitute_days(self):
        self.assertFalse(any(x["observed"] for x in by_date(2026, "PL").values()))


class NewZealandTest(unittest.TestCase):
    MATARIKI = {2022: "2022-06-24", 2023: "2023-07-14", 2024: "2024-06-28",
                2025: "2025-06-20", 2026: "2026-07-10", 2027: "2027-06-25",
                2028: "2028-07-14", 2029: "2029-07-06", 2030: "2030-06-21"}

    def test_matariki_official_table(self):
        for year, date in self.MATARIKI.items():
            self.assertEqual(by_date(year, "NZ")[date]["name"], "Matariki", year)

    def test_matariki_outside_table_fails_loudly(self):
        with self.assertRaises(hol.UnsupportedYear):
            hol.holidays_for_year(2031, "NZ")
        code, out, err = run_cli("2031", "NZ")
        self.assertEqual(code, 2)
        self.assertIn("Matariki", err)

    def test_no_matariki_before_2022(self):
        self.assertFalse(any(x["name"] == "Matariki" for x in hol.holidays_for_year(2021, "NZ")))

    def test_kings_birthday_and_mondayisation(self):
        h = by_date(2026, "NZ")
        self.assertEqual(h["2026-06-01"]["name"], "King's Birthday")
        self.assertIn("2026-04-27", h)  # Anzac Day on Saturday
        self.assertIn("2026-12-28", h)  # Boxing Day on Saturday
        h27 = by_date(2027, "NZ")
        self.assertIn("2027-01-04", h27)  # Day after New Year's Day on Saturday
        self.assertIn("2027-02-08", h27)  # Waitangi Day on Saturday
        self.assertEqual(by_date(2022, "NZ")["2022-06-06"]["name"], "Queen's Birthday")


class SubstituteDaysTest(unittest.TestCase):
    def test_gb_boxing_day_2026(self):
        h = by_date(2026, "GB")
        self.assertEqual(h["2026-12-28"]["name"], "Boxing Day (substitute day)")
        self.assertIn("2026-08-31", h)

    def test_gb_christmas_and_boxing_on_weekend(self):
        h = by_date(2027, "GB")
        self.assertEqual(h["2027-12-27"]["name_en"], "Christmas Day (substitute day)")
        self.assertEqual(h["2027-12-28"]["name_en"], "Boxing Day (substitute day)")

    def test_au_kings_birthday(self):
        h = by_date(2026, "AU")
        self.assertEqual(h["2026-06-08"]["name"], "King's Birthday")
        self.assertIn("2026-12-28", h)
        self.assertEqual(by_date(2022, "AU")["2022-06-13"]["name"], "Queen's Birthday")

    def test_ca_christmas_on_sunday_coincides_with_boxing_day(self):
        h = hol.holidays_for_year(2022, "CA")
        dates = [x["date"] for x in h]
        self.assertIn("2022-12-26", dates)
        self.assertNotIn("2022-12-27", dates)
        self.assertIn("2027-12-28", [x["date"] for x in hol.holidays_for_year(2027, "CA")])
        self.assertIn("2026-05-18", [x["date"] for x in hol.holidays_for_year(2026, "CA")])


class OtherCountriesTest(unittest.TestCase):
    def test_nl_liberation_day_only_in_lustrum_years(self):
        self.assertIn("2025-05-05", by_date(2025, "NL"))
        self.assertNotIn("2026-05-05", by_date(2026, "NL"))
        self.assertEqual(by_date(2026, "NL")["2026-04-27"]["name"], "Koningsdag")

    def test_native_names(self):
        self.assertEqual(by_date(2026, "DE")["2026-10-03"]["name"], "Tag der Deutschen Einheit")
        self.assertEqual(by_date(2026, "FR")["2026-07-14"]["name"], "Fête nationale")

    def test_every_supported_country_runs(self):
        for cc in hol.SUPPORTED:
            for year in range(2020, 2031):
                self.assertTrue(hol.holidays_for_year(year, cc), (cc, year))

    def test_holidays_between_spans_years(self):
        h = hol.holidays_between(dt.date(2026, 12, 20), dt.date(2027, 1, 7), "PL")
        self.assertEqual([x["date"] for x in h],
                         ["2026-12-24", "2026-12-25", "2026-12-26", "2027-01-01", "2027-01-06"])


class CliTest(unittest.TestCase):
    def test_other_country_is_empty_not_an_error(self):
        code, out, err = run_cli("2026", "other")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), [])
        self.assertIn("not built in", err)

    def test_none_is_silent(self):
        code, out, err = run_cli("2026", "none")
        self.assertEqual((code, json.loads(out), err), (0, [], ""))

    def test_english_flag(self):
        code, out, _ = run_cli("2026", "pl", "--english")
        names = {h["date"]: h["name"] for h in json.loads(out)}
        self.assertEqual(names["2026-12-24"], "Christmas Eve")

    def test_to_year(self):
        code, out, _ = run_cli("2026", "US", "--to-year", "2027")
        years = {h["date"][:4] for h in json.loads(out)}
        self.assertEqual(years, {"2026", "2027"})


class AliasTest(unittest.TestCase):
    def test_uk_is_gb(self):
        self.assertEqual(hol.holidays_for_year(2026, "UK"), hol.holidays_for_year(2026, "GB"))
        code, out, err = run_cli("2026", "uk")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn("2026-08-31", out)


if __name__ == "__main__":
    unittest.main()

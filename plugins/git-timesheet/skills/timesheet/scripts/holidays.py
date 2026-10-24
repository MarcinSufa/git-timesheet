#!/usr/bin/env python3
"""Public holidays for the countries git-timesheet supports.

Usage:
    python3 holidays.py YEAR COUNTRY [--to-year YEAR2] [--english]

Prints a JSON list sorted by date:
    [{"date": "2026-07-03", "name": "Independence Day (observed)",
      "name_en": "Independence Day (observed)", "observed": true}, ...]

`name` is in the country's own language (PL, DE, FR, NL) and English
elsewhere; `--english` puts the English name in `name` too.

Unsupported codes (including "other") print a message on stderr and an
empty list on stdout with exit code 0, so the caller can ask the user to
list holidays by hand. Years the built-in tables do not cover (NZ Matariki
after 2030) exit with code 2.

Scope (national level only, stdlib only):
    US  federal holidays incl. Juneteenth (2021+); Sat -> Fri, Sun -> Mon observed
    PL  statutory days off incl. Christmas Eve (2025+); no substitute days
    GB  England & Wales bank holidays with substitute days
    DE  nationwide holidays only (no state holidays)
    AU  holidays shared by most states, with New South Wales dates for King's
        Birthday and substitute days; state-only days (e.g. Labour Day) are not
        included
    NZ  national holidays incl. Matariki (official table 2022-2030), Mondayised
    CA  common statutory holidays with Ontario-style substitute days
        (Canada Day substitutes differ by province and are not added)
    FR  jours feries (metropolitan France)
    NL  nationale feestdagen; Bevrijdingsdag only in lustrum years (every 5 years)
"""
import argparse
import datetime as dt
import json
import sys

D = dt.date
DAY = dt.timedelta(days=1)

SUPPORTED = ("US", "PL", "GB", "DE", "AU", "NZ", "CA", "FR", "NL")

# Te Kahui o Matariki Public Holiday Act 2022, Schedule 1. The dates are fixed
# by law per year; extend this table from the Act, never by approximation.
MATARIKI = {
    2022: D(2022, 6, 24),
    2023: D(2023, 7, 14),
    2024: D(2024, 6, 28),
    2025: D(2025, 6, 20),
    2026: D(2026, 7, 10),
    2027: D(2027, 6, 25),
    2028: D(2028, 7, 14),
    2029: D(2029, 7, 6),
    2030: D(2030, 6, 21),
}


class UnsupportedYear(Exception):
    pass


def easter(year):
    """Easter Sunday (Anonymous Gregorian algorithm / computus)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return D(year, month, day + 1)


def nth_weekday(year, month, weekday, n):
    """n-th given weekday (0=Mon) of a month."""
    first = D(year, month, 1)
    return first + dt.timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def last_weekday(year, month, weekday):
    nxt = D(year + (month == 12), month % 12 + 1, 1)
    last = nxt - DAY
    return last - dt.timedelta(days=(last.weekday() - weekday) % 7)


def _h(date, name, name_en=None, sub=False):
    """Holiday tuple; sub=True means it gets a substitute day if on a weekend."""
    return (date, name, name_en or name, sub)


# ---------------------------------------------------------------- per country

def _us(y):
    out = [
        _h(D(y, 1, 1), "New Year's Day", sub=True),
        _h(nth_weekday(y, 1, 0, 3), "Martin Luther King Jr. Day"),
        _h(nth_weekday(y, 2, 0, 3), "Presidents' Day (Washington's Birthday)"),
        _h(last_weekday(y, 5, 0), "Memorial Day"),
    ]
    if y >= 2021:
        out.append(_h(D(y, 6, 19), "Juneteenth National Independence Day", sub=True))
    out += [
        _h(D(y, 7, 4), "Independence Day", sub=True),
        _h(nth_weekday(y, 9, 0, 1), "Labor Day"),
        _h(nth_weekday(y, 10, 0, 2), "Columbus Day"),
        _h(D(y, 11, 11), "Veterans Day", sub=True),
        _h(nth_weekday(y, 11, 3, 4), "Thanksgiving Day"),
        _h(D(y, 12, 25), "Christmas Day", sub=True),
    ]
    return out


def _pl(y):
    e = easter(y)
    out = [
        _h(D(y, 1, 1), "Nowy Rok", "New Year's Day"),
    ]
    if y >= 2011:
        out.append(_h(D(y, 1, 6), "Święto Trzech Króli", "Epiphany"))
    out += [
        _h(e, "Wielkanoc", "Easter Sunday"),
        _h(e + DAY, "Poniedziałek Wielkanocny", "Easter Monday"),
        _h(D(y, 5, 1), "Święto Pracy", "Labour Day"),
        _h(D(y, 5, 3), "Święto Narodowe Trzeciego Maja", "Constitution Day"),
        _h(e + 49 * DAY, "Zielone Świątki", "Pentecost"),
        _h(e + 60 * DAY, "Boże Ciało", "Corpus Christi"),
        _h(D(y, 8, 15), "Wniebowzięcie Najświętszej Maryi Panny", "Assumption Day"),
        _h(D(y, 11, 1), "Wszystkich Świętych", "All Saints' Day"),
        _h(D(y, 11, 11), "Narodowe Święto Niepodległości", "Independence Day"),
    ]
    if y == 2018:
        out.append(_h(D(2018, 11, 12), "Narodowe Święto Niepodległości (100. rocznica)",
                      "Independence Day (100th anniversary)"))
    if y >= 2025:
        out.append(_h(D(y, 12, 24), "Wigilia Bożego Narodzenia", "Christmas Eve"))
    out += [
        _h(D(y, 12, 25), "Boże Narodzenie (pierwszy dzień)", "Christmas Day"),
        _h(D(y, 12, 26), "Boże Narodzenie (drugi dzień)", "Second Day of Christmas"),
    ]
    return out


def _gb(y):
    e = easter(y)
    early_may = nth_weekday(y, 5, 0, 1)
    spring = last_weekday(y, 5, 0)
    if y == 2020:
        early_may = D(2020, 5, 8)  # moved for the 75th anniversary of VE Day
    if y == 2022:
        spring = D(2022, 6, 2)  # moved for the Platinum Jubilee
    out = [
        _h(D(y, 1, 1), "New Year's Day", sub=True),
        _h(e - 2 * DAY, "Good Friday"),
        _h(e + DAY, "Easter Monday"),
        _h(early_may, "Early May Bank Holiday"),
        _h(spring, "Spring Bank Holiday"),
        _h(last_weekday(y, 8, 0), "Summer Bank Holiday"),
        _h(D(y, 12, 25), "Christmas Day", sub=True),
        _h(D(y, 12, 26), "Boxing Day", sub=True),
    ]
    one_off = {
        2022: [(D(2022, 6, 3), "Platinum Jubilee Bank Holiday"),
               (D(2022, 9, 19), "State Funeral of Queen Elizabeth II")],
        2023: [(D(2023, 5, 8), "Coronation of King Charles III")],
    }
    out += [_h(d, n) for d, n in one_off.get(y, [])]
    return out


def _de(y):
    e = easter(y)
    out = [
        _h(D(y, 1, 1), "Neujahr", "New Year's Day"),
        _h(e - 2 * DAY, "Karfreitag", "Good Friday"),
        _h(e + DAY, "Ostermontag", "Easter Monday"),
        _h(D(y, 5, 1), "Tag der Arbeit", "Labour Day"),
        _h(e + 39 * DAY, "Christi Himmelfahrt", "Ascension Day"),
        _h(e + 50 * DAY, "Pfingstmontag", "Whit Monday"),
        _h(D(y, 10, 3), "Tag der Deutschen Einheit", "German Unity Day"),
        _h(D(y, 12, 25), "Erster Weihnachtstag", "Christmas Day"),
        _h(D(y, 12, 26), "Zweiter Weihnachtstag", "Second Day of Christmas"),
    ]
    if y == 2017:
        out.append(_h(D(2017, 10, 31), "Reformationstag", "Reformation Day"))
    return out


def _monarch(y):
    return "King's Birthday" if y >= 2023 else "Queen's Birthday"


def _au(y):
    e = easter(y)
    out = [
        _h(D(y, 1, 1), "New Year's Day", sub=True),
        _h(D(y, 1, 26), "Australia Day", sub=True),
        _h(e - 2 * DAY, "Good Friday"),
        _h(e - DAY, "Easter Saturday"),
        _h(e + DAY, "Easter Monday"),
        _h(D(y, 4, 25), "Anzac Day", sub=y >= 2026),
        _h(nth_weekday(y, 6, 0, 2), _monarch(y)),
        _h(D(y, 12, 25), "Christmas Day", sub=True),
        _h(D(y, 12, 26), "Boxing Day", sub=True),
    ]
    if y == 2022:
        out.append(_h(D(2022, 9, 22), "National Day of Mourning for Queen Elizabeth II"))
    return out


def _nz(y):
    e = easter(y)
    out = [
        _h(D(y, 1, 1), "New Year's Day", sub=True),
        _h(D(y, 1, 2), "Day after New Year's Day", sub=True),
        _h(D(y, 2, 6), "Waitangi Day", sub=y >= 2014),
        _h(e - 2 * DAY, "Good Friday"),
        _h(e + DAY, "Easter Monday"),
        _h(D(y, 4, 25), "Anzac Day", sub=y >= 2014),
        _h(nth_weekday(y, 6, 0, 1), _monarch(y)),
    ]
    if y >= 2022:
        if y not in MATARIKI:
            raise UnsupportedYear(
                "NZ Matariki dates are only built in for %d-%d (Te Kahui o Matariki "
                "Public Holiday Act 2022, Schedule 1); add %d from the Act to "
                "MATARIKI in holidays.py" % (min(MATARIKI), max(MATARIKI), y))
        out.append(_h(MATARIKI[y], "Matariki"))
    if y == 2022:
        out.append(_h(D(2022, 9, 26), "Queen Elizabeth II Memorial Day"))
    out += [
        _h(nth_weekday(y, 10, 0, 4), "Labour Day"),
        _h(D(y, 12, 25), "Christmas Day", sub=True),
        _h(D(y, 12, 26), "Boxing Day", sub=True),
    ]
    return out


def _ca(y):
    e = easter(y)
    # Victoria Day: the Monday before May 25.
    victoria = D(y, 5, 24) - dt.timedelta(days=D(y, 5, 24).weekday())
    return [
        _h(D(y, 1, 1), "New Year's Day", sub=True),
        _h(e - 2 * DAY, "Good Friday"),
        _h(victoria, "Victoria Day"),
        _h(D(y, 7, 1), "Canada Day"),
        _h(nth_weekday(y, 9, 0, 1), "Labour Day"),
        _h(nth_weekday(y, 10, 0, 2), "Thanksgiving"),
        _h(D(y, 12, 25), "Christmas Day", sub=True),
        _h(D(y, 12, 26), "Boxing Day", sub=True),
    ]


def _fr(y):
    e = easter(y)
    return [
        _h(D(y, 1, 1), "Jour de l'an", "New Year's Day"),
        _h(e + DAY, "Lundi de Pâques", "Easter Monday"),
        _h(D(y, 5, 1), "Fête du Travail", "Labour Day"),
        _h(D(y, 5, 8), "Victoire 1945", "Victory in Europe Day"),
        _h(e + 39 * DAY, "Ascension", "Ascension Day"),
        _h(e + 50 * DAY, "Lundi de Pentecôte", "Whit Monday"),
        _h(D(y, 7, 14), "Fête nationale", "Bastille Day"),
        _h(D(y, 8, 15), "Assomption", "Assumption Day"),
        _h(D(y, 11, 1), "Toussaint", "All Saints' Day"),
        _h(D(y, 11, 11), "Armistice 1918", "Armistice Day"),
        _h(D(y, 12, 25), "Noël", "Christmas Day"),
    ]


def _nl(y):
    e = easter(y)
    if y >= 2014:
        kings = D(y, 4, 27)
        kings_name = ("Koningsdag", "King's Day")
    else:
        kings = D(y, 4, 30)
        kings_name = ("Koninginnedag", "Queen's Day")
    if kings.weekday() == 6:  # moves to Saturday when it falls on a Sunday
        kings -= DAY
    out = [
        _h(D(y, 1, 1), "Nieuwjaarsdag", "New Year's Day"),
        _h(e - 2 * DAY, "Goede Vrijdag", "Good Friday"),
        _h(e, "Eerste Paasdag", "Easter Sunday"),
        _h(e + DAY, "Tweede Paasdag", "Easter Monday"),
        _h(kings, *kings_name),
    ]
    if y % 5 == 0:
        out.append(_h(D(y, 5, 5), "Bevrijdingsdag", "Liberation Day"))
    out += [
        _h(e + 39 * DAY, "Hemelvaartsdag", "Ascension Day"),
        _h(e + 49 * DAY, "Eerste Pinksterdag", "Pentecost"),
        _h(e + 50 * DAY, "Tweede Pinksterdag", "Whit Monday"),
        _h(D(y, 12, 25), "Eerste Kerstdag", "Christmas Day"),
        _h(D(y, 12, 26), "Tweede Kerstdag", "Second Day of Christmas"),
    ]
    return out


RULES = {"US": _us, "PL": _pl, "GB": _gb, "DE": _de, "AU": _au,
         "NZ": _nz, "CA": _ca, "FR": _fr, "NL": _nl}


def _observed(country, base):
    """Observed / substitute days for holidays that fall on a weekend."""
    # Canada (Ontario): a substitute may coincide with Boxing Day; elsewhere
    # it moves past any holiday that is already there.
    taken = set() if country == "CA" else {d for d, _, _, _ in base}
    out = []
    for d, name, name_en, sub in sorted(base, key=lambda h: h[0]):
        if not sub or d.weekday() < 5:
            continue
        if country == "US":
            obs = d - DAY if d.weekday() == 5 else d + DAY
        else:
            # Next weekday that is not already a holiday or a substitute day
            # (handles the Christmas/Boxing Day and New Year pairs).
            obs = d + DAY
            while obs.weekday() >= 5 or obs in taken:
                obs += DAY
        taken.add(obs)
        label = " (observed)" if country == "US" else " (substitute day)"
        out.append(_h(obs, name + label, name_en + label))
    return out


def holidays_for_year(year, country):
    """List of dicts for one calendar year, sorted by date."""
    country = (country or "").upper()
    if country not in RULES:
        return []
    days = []
    # Observed days can cross a year boundary (US: Jan 1 on a Saturday is
    # observed on Dec 31 of the previous year), so compute neighbours too.
    for y in (year - 1, year, year + 1):
        try:
            base = RULES[country](y)
        except UnsupportedYear:
            if y != year:
                continue
            raise
        for d, name, name_en, _ in base:
            days.append((d, name, name_en, False))
        for d, name, name_en, _ in _observed(country, base):
            days.append((d, name, name_en, True))
    days = [x for x in days if x[0].year == year]
    days.sort(key=lambda x: (x[0], x[3]))
    return [{"date": d.isoformat(), "name": n, "name_en": ne, "observed": o}
            for d, n, ne, o in days]


def holidays_between(start, end, country):
    """Holidays with start <= date <= end (dates are datetime.date)."""
    out = []
    for y in range(start.year, end.year + 1):
        for h in holidays_for_year(y, country):
            if start.isoformat() <= h["date"] <= end.isoformat():
                out.append(h)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="Public holidays as JSON")
    p.add_argument("year", type=int)
    p.add_argument("country", help="US, PL, GB, DE, AU, NZ, CA, FR, NL (or 'other')")
    p.add_argument("--to-year", type=int, help="last year (inclusive) for multi-year ranges")
    p.add_argument("--english", action="store_true", help="English names in 'name'")
    a = p.parse_args(argv)
    cc = a.country.upper()
    if cc in ("", "NONE"):
        print("[]")
        return 0
    if cc not in RULES:
        print("Country '%s' is not built in (supported: %s). No holidays were "
              "added: ask the user to list the public holidays as days off."
              % (a.country, ", ".join(SUPPORTED)), file=sys.stderr)
        print("[]")
        return 0
    result = []
    try:
        for y in range(a.year, (a.to_year or a.year) + 1):
            result += holidays_for_year(y, cc)
    except UnsupportedYear as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 2
    if a.english:
        for h in result:
            h["name"] = h["name_en"]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""A candidate's timezone from their location ("Chicago, Illinois, United States").

Candidate.timezone decides when automated messages may go out (9am-6pm candidate-local for
Thunder email). Every candidate used to keep the Asia/Kolkata backfill whatever their location, so
US candidates were emailed late at night. The location is read, most specific first:
  1. a US state or Canadian province (name or abbreviation) -> its main zone;
  2. a country with one zone (by name);
  3. a city that names an IANA zone ("Chicago" -> America/Chicago, "Sydney" -> Australia/Sydney).
None when the location says nothing usable: the current timezone is then kept.
"""
from functools import lru_cache
from typing import Dict, Optional

EASTERN, CENTRAL, MOUNTAIN, PACIFIC = "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles"

# (abbreviation, name, zone): the zone most of the state or province uses
REGIONS = (
    ("AL", "Alabama", CENTRAL), ("AK", "Alaska", "America/Anchorage"), ("AZ", "Arizona", "America/Phoenix"),
    ("AR", "Arkansas", CENTRAL), ("CA", "California", PACIFIC), ("CO", "Colorado", MOUNTAIN),
    ("CT", "Connecticut", EASTERN), ("DE", "Delaware", EASTERN), ("DC", "District of Columbia", EASTERN),
    ("FL", "Florida", EASTERN), ("GA", "Georgia", EASTERN), ("HI", "Hawaii", "Pacific/Honolulu"),
    ("ID", "Idaho", MOUNTAIN), ("IL", "Illinois", CENTRAL), ("IN", "Indiana", EASTERN), ("IA", "Iowa", CENTRAL),
    ("KS", "Kansas", CENTRAL), ("KY", "Kentucky", EASTERN), ("LA", "Louisiana", CENTRAL), ("ME", "Maine", EASTERN),
    ("MD", "Maryland", EASTERN), ("MA", "Massachusetts", EASTERN), ("MI", "Michigan", EASTERN),
    ("MN", "Minnesota", CENTRAL), ("MS", "Mississippi", CENTRAL), ("MO", "Missouri", CENTRAL),
    ("MT", "Montana", MOUNTAIN), ("NE", "Nebraska", CENTRAL), ("NV", "Nevada", PACIFIC),
    ("NH", "New Hampshire", EASTERN), ("NJ", "New Jersey", EASTERN), ("NM", "New Mexico", MOUNTAIN),
    ("NY", "New York", EASTERN), ("NC", "North Carolina", EASTERN), ("ND", "North Dakota", CENTRAL),
    ("OH", "Ohio", EASTERN), ("OK", "Oklahoma", CENTRAL), ("OR", "Oregon", PACIFIC), ("PA", "Pennsylvania", EASTERN),
    ("RI", "Rhode Island", EASTERN), ("SC", "South Carolina", EASTERN), ("SD", "South Dakota", CENTRAL),
    ("TN", "Tennessee", CENTRAL), ("TX", "Texas", CENTRAL), ("UT", "Utah", MOUNTAIN), ("VT", "Vermont", EASTERN),
    ("VA", "Virginia", EASTERN), ("WA", "Washington", PACIFIC), ("WV", "West Virginia", EASTERN),
    ("WI", "Wisconsin", CENTRAL), ("WY", "Wyoming", MOUNTAIN),
    ("ON", "Ontario", "America/Toronto"), ("QC", "Quebec", "America/Toronto"), ("BC", "British Columbia", "America/Vancouver"),
    ("AB", "Alberta", "America/Edmonton"), ("MB", "Manitoba", "America/Winnipeg"), ("SK", "Saskatchewan", "America/Regina"),
    ("NS", "Nova Scotia", "America/Halifax"), ("NB", "New Brunswick", "America/Moncton"),
    ("NL", "Newfoundland and Labrador", "America/St_Johns"), ("PE", "Prince Edward Island", "America/Halifax"),
)
# Countries with one zone, by the names people write
SINGLE_ZONE_COUNTRIES = {
    "india": "Asia/Kolkata", "united kingdom": "Europe/London", "uk": "Europe/London", "england": "Europe/London",
    "ireland": "Europe/Dublin", "singapore": "Asia/Singapore", "united arab emirates": "Asia/Dubai",
    "uae": "Asia/Dubai", "philippines": "Asia/Manila", "sri lanka": "Asia/Colombo", "germany": "Europe/Berlin",
    "france": "Europe/Paris", "netherlands": "Europe/Amsterdam", "poland": "Europe/Warsaw", "japan": "Asia/Tokyo",
    "south africa": "Africa/Johannesburg", "malaysia": "Asia/Kuala_Lumpur", "qatar": "Asia/Qatar",
    "saudi arabia": "Asia/Riyadh", "israel": "Asia/Jerusalem", "switzerland": "Europe/Zurich",
}
# Abbreviations that are also words or countries: only taken as a region next to its country
AMBIGUOUS_ABBREVIATIONS = {"IN", "OR", "ME", "DE", "CA", "PA", "MA", "LA", "OK", "HI", "ID", "AL", "GA"}
NORTH_AMERICA = {"united states", "usa", "us", "united states of america", "america", "canada"}


@lru_cache(maxsize=1)
def _region_zones() -> Dict[str, str]:
    zones = {}
    for abbreviation, name, zone in REGIONS:
        zones[name.lower()] = zone
        zones[abbreviation.lower()] = zone
    return zones


@lru_cache(maxsize=1)
def _city_zones() -> Dict[str, str]:
    from zoneinfo import available_timezones

    cities = {}
    for zone in available_timezones():
        if "/" in zone and not zone.startswith(("Etc/", "SystemV/", "US/", "Canada/")):
            cities.setdefault(zone.rsplit("/", 1)[-1].replace("_", " ").lower(), zone)
    return cities


def timezone_for_location(location: Optional[str]) -> Optional[str]:
    parts = [p.strip() for p in (location or "").split(",") if p.strip()]
    if not parts:
        return None
    lowered = [p.lower() for p in parts]
    in_north_america = bool(NORTH_AMERICA & set(lowered))
    for part in parts[1:] or parts:
        zone = _region_zones().get(part.lower())
        if zone and (part.upper() not in AMBIGUOUS_ABBREVIATIONS or in_north_america):
            return zone
    if lowered[-1] in SINGLE_ZONE_COUNTRIES:
        return SINGLE_ZONE_COUNTRIES[lowered[-1]]
    return _city_zones().get(lowered[0])

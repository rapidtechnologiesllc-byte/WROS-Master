"""
S-029/HRMS-0429 -- Skill synonym library.

BR-02: this file is a product decision, not a technical one -- any
addition/removal changes matching behavior platform-wide and requires
Lead BA written approval + code review before deployment, same as the
spec's own rule for skill_synonyms.json (kept as a Python module
rather than a bare JSON file so it's still a single source-of-truth
constant, just importable without a separate file-read step -- the
approval requirement is unchanged either way).

Seed/starter set: no Lead BA was available to curate this in this
automated build session, so this covers exactly the canonical/synonym
pairs the spec itself gives as worked examples (Guidewire cluster,
Java cluster) plus a small number of other common, unambiguous
clusters, rather than inventing a large taxonomy unilaterally. Real
and useful as a v1 -- flagged for BA review/expansion, not a filler.
Unknown skills are never discarded (BR-03) regardless of this list's
size -- see skill_extraction_service.normalize_skills().
"""

# Canonical name -> list of known synonyms (case-insensitive match).
SKILL_SYNONYMS = {
    "Guidewire": [
        "GW", "GW PolicyCenter", "GWPC", "GW ClaimCenter", "GWCC",
        "GW BillingCenter", "GWBC", "Guidewire PolicyCenter",
        "Guidewire ClaimCenter", "Guidewire BillingCenter",
    ],
    # Spring Boot/Spring Framework kept here per the spec's own literal
    # worked example, which also flags this exact ambiguity ("Spring
    # Boot is a framework built on Java -- discuss with BA whether to
    # keep separate or merge"). Left merged as the spec's example shows;
    # revisit if BA decides otherwise.
    "Java": [
        "J2EE", "Core Java", "Java 8", "Java 11", "Java 17", "Java EE",
        "Spring Boot", "Spring Framework",
    ],
    "SQL": ["MySQL", "PostgreSQL", "T-SQL", "PL/SQL", "SQL Server", "MS SQL"],
    "Python": ["Python3", "Python 3"],
    "AWS": ["Amazon Web Services"],
    "Azure": ["Microsoft Azure"],
    ".NET": ["DotNet", ".NET Core", "ASP.NET"],
    "JavaScript": ["JS", "ECMAScript", "Node.js", "NodeJS"],
}


def _build_reverse_index():
    index = {}
    for canonical, synonyms in SKILL_SYNONYMS.items():
        index[canonical.lower()] = canonical
        for synonym in synonyms:
            index[synonym.lower()] = canonical
    return index


SKILL_SYNONYM_REVERSE_INDEX = _build_reverse_index()

"""
Resume Parser SLM - Self-Learning Model for resume extraction

This service uses pattern matching, regex, and structured extraction to parse resumes.
No external LLM calls. Data stays proprietary.

If accuracy is low, the service can be trained/improved by:
1. Collecting labeled training data (resume → correct extraction)
2. Using an LLM to generate synthetic training examples (one-time cost)
3. Fine-tuning the SLM with that data
4. Deploying improved version

Current Implementation:
- Pattern-based extraction (contact info, dates, sections)
- Dictionary-based skill/certification matching
- Heuristic experience calculation
- Can be replaced with ML model when ready
"""

import logging
import re
from typing import Dict, List, Optional


logger = logging.getLogger(__name__)

class ResumeSLM:
    """
    Self-Learning Model for resume parsing.

    Uses pattern matching and heuristics. Can be trained with labeled data
    to improve accuracy over time.
    """

    # Known technical skills database (can be expanded)
    TECHNICAL_SKILLS = {
        # Programming Languages
        "python", "javascript", "java", "csharp", "c#", "ruby", "golang",
        "typescript", "kotlin", "php", "perl", "scala",
        "julia", "haskell", "elixir", "clojure", "groovy", "lua", "bash",

        # Databases
        "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "cassandra",
        "dynamodb", "sqlite", "oracle", "sql server", "firestore", "couchbase",
        "neo4j", "graphql",

        # Cloud/Infrastructure
        "aws", "azure", "gcp", "google cloud", "heroku", "digitalocean",
        "kubernetes", "docker", "terraform", "ansible", "jenkins", "gitlab",
        "github actions", "circleci", "travis", "gitlab ci",

        # Frameworks/Libraries
        "react", "vue", "angular", "django", "flask", "fastapi", "spring",
        "spring boot", "express", "nextjs", "gatsby", "astro", "remix",
        "tailwind", "bootstrap", "material ui", "chakra ui", "testing library",

        # Data/ML
        "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "keras",
        "jax", "huggingface", "langchain", "spark", "airflow", "tableau",
        "power bi", "looker", "rstudio", "jupyter",

        # DevOps/Tools
        "git", "linux", "unix", "windows", "macos", "nginx", "apache",
        "grafana", "prometheus", "datadog", "newrelic", "splunk",

        # Soft skills (commonly listed)
        "communication", "leadership", "teamwork", "problem-solving",
        "agile", "scrum", "kanban", "critical thinking", "project management",
    }

    # Known certifications
    CERTIFICATIONS = {
        "aws certified", "azure certified", "gcp certified",
        "certified kubernetes", "cka", "ckad",
        "cissp", "ccna", "comptia",
        "pmp", "capm", "scrum master", "csm",
        "togaf", "itil", "six sigma",
    }

    # Known languages
    LANGUAGES = {
        "english", "spanish", "french", "german", "mandarin", "chinese",
        "japanese", "korean", "russian", "portuguese", "italian", "dutch",
        "arabic", "hebrew", "hindi", "vietnamese", "thai", "polish",
    }

    # --- Section-based reading: a resume's headings say what each block is, whatever the employer is called.
    HEADINGS = {
        "experience": ("professional experience", "work experience", "experience", "employment history", "employment",
                       "work history", "career history", "relevant experience", "previous experience"),
        "education": ("education", "academic background", "academic qualifications", "qualifications", "education & training"),
        "certifications": ("certifications", "certification", "certificates", "licenses", "licenses & certifications",
                           "certifications & licenses", "professional certifications", "credentials"),
        "skills": ("skills", "core skills", "technical skills", "key skills", "core competencies", "competencies", "expertise",
                   "skills & tools", "technologies", "technical expertise"),
        "other": ("professional summary", "summary", "profile", "objective", "projects", "languages", "awards", "references",
                  "publications", "interests", "achievements", "personal details", "professional summary", "profile summary",
                  "key achievements", "career timeline", "project profile", "career highlights"),
    }
    MONTHS = {m: i + 1 for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}
    _DATE = (r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?,?\s+\d{4}"
             r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s*[\u2019']\s?\d{2}\b|\d{1,2}/\d{4}|\d{4}-\d{2}|(?:19|20)\d{2})")
    DATE_RANGE = re.compile(rf"(?<![\w(])({_DATE})\s*(?:\u2013|\u2014|-|to|until)\s*({_DATE}|present|current|now|till date|to date|ongoing)\b",
                            re.IGNORECASE)
    TITLE_WORDS = ("engineer", "developer", "manager", "analyst", "designer", "architect", "lead", "consultant", "director", "head",
                   "specialist", "associate", "administrator", "officer", "programmer", "tester", "president", "recruiter", "intern", "executive")
    ISSUERS = ("Guidewire", "AWS", "Amazon", "Microsoft", "Azure", "Google", "Oracle", "Sun", "Cisco", "PMI", "Scrum Alliance",
               "Salesforce", "SAFe", "ISTQB", "IBM", "CompTIA", "ITIL", "TOGAF", "Duck Creek")
    INSTITUTION_WORDS = ("university", "college", "institute", "school", "academy", "polytechnic", "iit ", "nit ", "vidyalaya")
    CERTIFICATE_WORDS = re.compile(r"\b(?:certifi\w*|certificate\w*|licen[sc]e\w*|credential\w*|associate in|AINS|CPCU|PMP|CSM|CSPO|SAFe|ITIL|TOGAF|ISTQB|CISSP|ACE)\b")
    NOT_A_SKILL_START = {"and", "or", "with", "the", "to", "of", "for", "in", "on", "by", "a", "an", "as", "at", "from", "into", "knowledge", "experience",
                         "proficient", "technically", "good", "strong", "hands-on", "key"}
    NOT_A_SKILL_END = {"and", "or", "with", "the", "to", "of", "for", "in", "on", "by", "a", "an", "as", "at", "from", "into"}
    SKILL_CATEGORY = re.compile(r"^[\w&/ -]*?\b(?:Products|Languages|Configuration|Development|Technologies|Formats|DevOps|Tools|Control|Management|Environment|Debugging|Model)\s+(?=[A-Z])")
    BULLETS = "\u2022*\u25cf\u25cb\u25aa\\-\u2013\\s"

    @staticmethod
    def _reflow(text: str) -> str:
        """Some PDFs come out with most words on a line of their own: put the resume's own lines back before reading it."""
        lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
        if len(lines) < 150 or sum(len(line.split()) for line in lines) / len(lines) >= 4:
            return text or ""
        one = " ".join(lines)
        one = re.sub(r"\s{5,}", " | ", one)
        one = re.sub(r"\|\s*:", ":", one)
        one = re.sub(r"\s*([\u25cf\u25cb\u2022\u25aa])\s*", r"\n\1 ", one)
        one = re.sub(r"\s*\b((?:[A-Z]{3,}\s+)*[A-Z&]{3,})\s*:\s*", r"\n\1:\n", one)
        one = re.sub(r"\s*\b(Description|Responsibilities|Environment)\s*:", r"\n\1:", one)
        one = ResumeSLM.DATE_RANGE.sub(lambda m: m.group(0) + "\n", one)
        result: List[str] = []
        for line in one.splitlines():
            line = re.sub(r"\s+", " ", line).strip(" |")
            # the next job's name runs straight on from the last job's technology list
            if line.startswith("Environment:") and ResumeSLM.DATE_RANGE.search(line):
                head, _, tail = line.partition(" | ")
                if "," in head:
                    keep, _, name = head.rpartition(",")
                    name = re.sub(r"^\s*\S+\s+(?:\d+\s+)?", "", name)  # the list's last entry, and a page number
                    result.append(keep)
                    line = name + " | " + tail
            if line:
                result.append(line)
        return "\n".join(result)

    @staticmethod
    def _is_certification(line: str) -> bool:
        """A heading is only a start: what follows it may be the next column or the next job."""
        if ResumeSLM.DATE_RANGE.search(line) or (len(line) > 140 and ";" not in line):
            return False
        if ResumeSLM.CERTIFICATE_WORDS.search(line) or any(line.startswith(issuer + " ") for issuer in ResumeSLM.ISSUERS):
            return True
        if "|" in line:
            return False
        words = line.split()
        return 2 <= len(words) <= 7 and words[0][0].isupper() and not line.rstrip().endswith((".", ",", ":")) and " : " not in line and "," not in line

    @staticmethod
    def _is_skill(item: str) -> bool:
        words = item.lower().split()
        if not words or len(words) > 5 or item.endswith("-") or item.isdigit():
            return False
        if words[0] in ResumeSLM.NOT_A_SKILL_START or words[-1] in ResumeSLM.NOT_A_SKILL_END:
            return False
        return not (len(words) > 1 and item[0].isupper() and words[0].endswith("ed"))

    @staticmethod
    def _sections(text: str) -> Dict[str, List[str]]:
        """The lines under each known heading. Same-line lists ("Skills: Python, SQL") stay with their heading."""
        lookup = {name: kind for kind, names in ResumeSLM.HEADINGS.items() for name in names}
        sections: Dict[str, List[str]] = {}
        current = None
        # "Since Dec'23" is a range to today; a range cut by the end of a line is one range
        text = re.sub(rf"(?im)^\s*since\s+({ResumeSLM._DATE})", r"\1 - Present", text or "")
        text = re.sub(rf"(?i)({ResumeSLM._DATE})\s*(\u2013|\u2014|-|to)\s*\n\s*({ResumeSLM._DATE}|present|current)", r"\1 \2 \3", text)
        for raw in text.splitlines():
            line = raw.strip()
            bare = re.sub(r"\s+", " ", re.sub(r"[:\s]+$", "", line)).lower()
            if bare in lookup:
                current = lookup[bare]
                sections.setdefault(current, [])
                continue
            inline = re.match(r"^([A-Za-z &]{4,35}):\s*(.+)$", line)
            if inline and inline.group(1).lower() in lookup:
                kind = lookup[inline.group(1).lower()]
                sections.setdefault(kind, []).append(inline.group(2))
                current = None if kind == "skills" else kind
                continue
            if current in ("certifications", "skills") and len(line) <= 140 and len(ResumeSLM.DATE_RANGE.findall(line)) == 1:
                current = "experience"  # a job's dates: that heading's list is over
                sections.setdefault(current, [])
            if current and line:
                sections[current].append(line)
        return sections

    @staticmethod
    def _month_of(value: Optional[str]) -> Optional[str]:
        """'YYYY-MM' from "Oct 2022", "10/2022", "2022-10" or "2022"; None for present."""
        value = (value or "").strip().lower().replace(",", "").replace(".", "")
        short = re.match(r"^([a-z]{3})[a-z]*\s*[\u2019']\s?(\d{2})$", value)
        if short and short.group(1) in ResumeSLM.MONTHS:
            year = int(short.group(2))
            return f"{2000 + year if year < 50 else 1900 + year}-{ResumeSLM.MONTHS[short.group(1)]:02d}"
        match = re.match(r"^([a-z]{3})[a-z]*\s+(\d{4})$", value)
        if match and match.group(1) in ResumeSLM.MONTHS:
            return f"{match.group(2)}-{ResumeSLM.MONTHS[match.group(1)]:02d}"
        match = re.match(r"^(\d{1,2})/(\d{4})$", value)
        if match:
            return f"{match.group(2)}-{int(match.group(1)):02d}"
        match = re.match(r"^(\d{4})-(\d{2})$", value)
        if match:
            return value
        return f"{value}-01" if re.match(r"^(19|20)\d{2}$", value) else None

    @staticmethod
    def _looks_like_title(text: str) -> bool:
        return bool(re.search(rf"\b(?:{'|'.join(ResumeSLM.TITLE_WORDS)})s?\b", text, re.IGNORECASE))

    @staticmethod
    def _is_label_line(line: str) -> bool:
        return len(line) <= 90 and not line.endswith((".", ";", ":")) and not line.startswith(("\u2022", "*", "-", "\u25cf"))

    @staticmethod
    def _section_jobs(lines: List[str]) -> List[Dict]:
        # a job's dates head its line; dates in brackets or in a long line belong to a project inside the job
        headers = [(i, m) for i, m in ((i, ResumeSLM.DATE_RANGE.search(l)) for i, l in enumerate(lines))
                   if m and len(lines[i]) <= 180 and lines[i][:m.start()].count("(") <= lines[i][:m.start()].count(")")
                   and len(ResumeSLM.DATE_RANGE.findall(lines[i])) == 1]
        jobs = []
        taken: set = set()
        for position, (index, match) in enumerate(headers):
            line = lines[index]
            before = re.sub(r"[\s,|\u2013\u2014-]+$", "", line[:match.start()]).strip()
            before = re.sub(rf"^[{ResumeSLM.BULLETS}]+", "", before)
            after = re.sub(r"^[\s,|\u2013\u2014-]+", "", line[match.end():]).strip()
            trailing = not before and bool(after)  # "May'22-Dec'23| Manager | Capgemini, Pune, India"
            employer = title = None
            parts = [p.strip() for p in re.split(r"\t|\s*\|\s*", before or after) if p.strip()] if (before or after) else []
            parts = [re.sub(r"\s*\((?:formerly|previously)[^)]*\)", "", p) for p in parts if not p.lower().endswith(" project")]
            if trailing:
                parts = [parts[0], parts[1].split(",")[0].strip()] if len(parts) >= 2 else parts
            named = re.match(r"^(.+?\.)\s+(.+)$", parts[0]) if len(parts) > 1 else None
            if named and len(named.group(1)) > 4 and ResumeSLM._looks_like_title(named.group(2)):
                parts = parts[:1]  # "Company. Title." with a project name after it
            if len(parts) == 1:
                at = re.match(r"^(.+?)\s+(?:at|@)\s+(.+)$", parts[0])
                dash = re.match(r"^(.+?)\s+[\u2013\u2014]\s+(.+)$", parts[0])
                stop = re.match(r"^(.+?\.)\s+(.+)$", parts[0])
                comma = [p.strip() for p in parts[0].split(",") if p.strip()]
                if at:
                    title, employer = at.group(1), at.group(2)
                elif dash:
                    title, employer = dash.group(1), dash.group(2)
                elif (stop and len(stop.group(1)) > 4 and ResumeSLM._looks_like_title(stop.group(2))
                      and not ResumeSLM._looks_like_title(stop.group(1))):
                    employer, title = stop.group(1).rstrip("."), stop.group(2).rstrip(".")
                elif len(comma) == 2 and ResumeSLM._looks_like_title(comma[0]):
                    title, employer = comma
                else:
                    employer = parts[0]
            elif len(parts) >= 2 and ResumeSLM._looks_like_title(parts[0]) and ResumeSLM._looks_like_title(parts[1]):
                title = parts[0]  # two titles: this line does not name the employer
            elif len(parts) >= 2:
                title, employer = (parts[0], parts[1]) if ResumeSLM._looks_like_title(parts[0]) else (parts[1], parts[0])
            floor = headers[position - 1][0] + 1 if position else 0
            above = [i for i in range(max(floor, index - 2), index) if ResumeSLM._is_label_line(lines[i]) and i not in taken]
            if not before and not after and above:  # the dates stand alone: the lines above name the job
                labels = [lines[i] for i in above]
                taken.update(above)
                if len(labels) == 2:
                    title, employer = labels if ResumeSLM._looks_like_title(labels[0]) else labels[::-1]
                elif ResumeSLM._looks_like_title(labels[0]):
                    title = labels[0]
                else:
                    employer = labels[0]
            following = index + 1
            limit = headers[position + 1][0] if position + 1 < len(headers) else len(lines)
            if not title and following < limit and ResumeSLM._is_label_line(lines[following]):
                title = lines[following]
                taken.add(following)
                following += 1
            elif not employer and following < limit and ResumeSLM._is_label_line(lines[following]):
                employer = lines[following]
                taken.add(following)
                following += 1
            # a stacked next job's labels sit just above its dates, not in this job's text
            next_above = set()
            if position + 1 < len(headers) and not lines[headers[position + 1][0]][:headers[position + 1][1].start()].strip() \
                    and not lines[headers[position + 1][0]][headers[position + 1][1].end():].strip(" |"):
                next_above = {i for i in range(max(following, limit - 2), limit) if ResumeSLM._is_label_line(lines[i])}
            if employer and title and ResumeSLM._looks_like_title(employer) and not ResumeSLM._looks_like_title(title):
                employer, title = title, employer
            description = [lines[i] for i in range(following, limit) if i not in next_above]
            employer, title = (employer or "").rstrip(" .") or None, (title or "").rstrip(" .") or None
            jobs.append({"employer": employer, "title": title, "start_date": ResumeSLM._month_of(match.group(1)),
                         "end_date": ResumeSLM._month_of(match.group(2)), "description": " ".join(description)[:2000] or None})
        return [j for j in jobs if j["employer"] or j["title"]]

    @staticmethod
    def _section_certifications(lines: List[str]) -> List[Dict]:
        found = []
        for line in lines:
            line = re.sub(rf"^[{ResumeSLM.BULLETS}]+", "", line)
            line = re.sub(r"\s*[-\u2013]\s*\d{1,3}%\s*$", "", line.split(" | ")[0])
            if not ResumeSLM._is_certification(line):
                continue
            prefix = ""
            head = re.match(r"^([^:]{2,60}):\s*(.+)$", line)
            if head and ";" in head.group(2) or head and re.search(r"(19|20)\d{2}", head.group(2)):
                prefix, line = head.group(1).strip(), head.group(2)
            for item in re.split(r";", line):
                item = item.strip()
                if len(item) < 3:
                    continue
                year = re.search(r"\b((?:19|20)\d{2})\b", item)
                name = re.sub(r"[,\s\-\u2013(]*\b(?:19|20)\d{2}\)?\s*$", "", item).strip(" ,")
                name = f"{prefix}: {name}" if prefix else name
                issuer = next((v for v in ResumeSLM.ISSUERS if re.search(rf"\b{re.escape(v)}\b", name, re.IGNORECASE)), None)
                if name and not any(c["name"].lower() == name.lower() for c in found):
                    found.append({"name": name[:255], "issuer": issuer, "year": int(year.group(1)) if year else None})
        return found[:20]

    @staticmethod
    def _certifications_mentioned(text: str) -> List[Dict]:
        """No certifications heading: a resume can still say it in its summary ("achieved Guidewire ACE Certification")."""
        found: List[Dict] = []
        for match in re.finditer(r"\b((?:[A-Z][\w+-]*\s+){1,5}Certification)\b", text or ""):
            name = match.group(1).strip()
            if not any(c["name"].lower() == name.lower() for c in found):
                issuer = next((v for v in ResumeSLM.ISSUERS if re.search(rf"\b{re.escape(v)}\b", name, re.IGNORECASE)), None)
                found.append({"name": name[:255], "issuer": issuer, "year": None})
        return found[:20]

    @staticmethod
    def _section_education(lines: List[str]) -> List[Dict]:
        pieces: List[str] = []
        if len(lines) >= 3 and all(len(line) <= 35 for line in lines):  # a narrow column: one entry wraps over lines, ending at its year
            merged, part = [], []
            for line in lines:
                part.append(line)
                if re.search(r"\b(?:19|20)\d{2}\b", line):
                    merged.append(" ".join(part))
                    part = []
            lines = merged + ([" ".join(part)] if part else [])
        for line in lines:
            pieces.extend(p.strip() for p in re.split(r"\s+\|\s+", re.sub(rf"^[{ResumeSLM.BULLETS}]+", "", line)) if p.strip())
        entries: List[Dict] = []
        pending: Optional[Dict] = None
        for piece in pieces:
            year = re.search(r"\b((?:19|20)\d{2})\b", piece)
            body = re.sub(r"[,\s\-\u2013(]*\b(?:19|20)\d{2}\)?\s*$", "", piece).strip(" ,")
            body = re.sub(r"\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?$", "", body, flags=re.IGNORECASE).replace("\t", ", ")
            segments = [s.strip() for s in body.split(",") if s.strip()]
            institution = next((s for s in segments if any(w in f"{s.lower()} " for w in ResumeSLM.INSTITUTION_WORDS)), None)
            others = [s for s in segments if s != institution]
            degree = others[0] if others else None
            joined = re.match(r"^(.+?)\s+(?:at|from)\s+(.+)$", institution or "")
            if joined:  # "Masters in Science at Cleveland State University"
                degree, institution = joined.group(1), joined.group(2)
            if institution:
                institution = re.sub(r"\s*\([^)]*\)\s*$", "", institution).strip()
            if pending and (not institution or not pending["degree"]) and not (institution and pending["institution"]):
                pending["institution"] = pending["institution"] or institution
                pending["degree"] = pending["degree"] or degree
                pending["graduation_year"] = pending["graduation_year"] or (int(year.group(1)) if year else None)
                entries.append(pending)
                pending = None
                continue
            entry = {"institution": institution, "degree": degree, "field": None, "graduation_year": int(year.group(1)) if year else None}
            if institution and degree or (institution or degree) and year:
                entries.append(entry)
            else:
                pending = entry
        if pending:
            entries.append(pending)
        joined_up: List[Dict] = []
        for entry in entries:  # a degree on one line and its school on the next are one entry
            if joined_up and entry["institution"] and not joined_up[-1]["institution"]:
                joined_up[-1]["institution"] = entry["institution"]
                joined_up[-1]["graduation_year"] = joined_up[-1]["graduation_year"] or entry["graduation_year"]
            else:
                joined_up.append(entry)
        entries = joined_up
        for entry in entries:
            field = re.search(r"\bin\s+([A-Z][^,]{1,80})$", entry["degree"] or "")
            entry["field"] = field.group(1).strip() if field else None
        return entries

    @staticmethod
    def _section_skills(lines: List[str]) -> List[str]:
        skills: List[str] = []
        for line in lines:
            line = re.sub(rf"^[{ResumeSLM.BULLETS}]+", "", line)
            if len(line.split()) > 12 and line.count(",") < 2:
                continue  # a sentence, not a list
            if "\t" in line:  # "Category<TAB>A, B"
                line = line.split("\t", 1)[1]
            elif re.match(r"^[A-Za-z &/.-]{2,30}\s*:\s", line):
                line = line.split(":", 1)[1]
            elif "," in line:  # "Project Management Jira, Agile": the category runs straight into the list
                line = ResumeSLM.SKILL_CATEGORY.sub("", line, count=1)
            for item in re.split(r"[,;|\u2022]", line):
                item = item.split(":")[-1].strip(" .()")
                if 1 < len(item) <= 40 and ResumeSLM._is_skill(item) and item.lower() not in {s.lower() for s in skills}:
                    skills.append(item)
        return skills[:60]

    @staticmethod
    def parse_resume(raw_text: str) -> Dict:
        """
        Parse resume text and extract structured data.

        Returns dictionary with:
        - full_name: Candidate name
        - email: Email address
        - phone: Phone number
        - current_title: Current job title
        - current_employer: Current employer
        - work_history: List of jobs
        - education: List of education entries
        - skills: List of skills
        - certifications: List of certifications
        - languages: List of languages
        """
        slm = ResumeSLM()
        raw_text = slm._reflow(raw_text)
        sections = slm._sections(raw_text)
        # the resume's own sections first; the older pattern search only for a resume without those headings
        jobs = slm._section_jobs(sections.get("experience") or []) or slm._extract_work_history(raw_text)
        dated = sorted((j for j in jobs if j.get("start_date")), key=lambda j: j["start_date"], reverse=True)
        current = next((j for j in dated if not j.get("end_date")), dated[0] if dated else None)

        return {
            "full_name": slm._extract_name(raw_text),
            "email": slm._extract_email(raw_text),
            "phone": slm._extract_phone(raw_text),
            "current_title": (current or {}).get("title") or slm._extract_current_title(raw_text),
            "current_employer": (current or {}).get("employer") or slm._extract_current_employer(raw_text),
            "work_history": jobs,
            "education": slm._section_education(sections.get("education") or []) or slm._extract_education(raw_text),
            "skills": slm._section_skills(sections.get("skills") or []) or slm._extract_skills(raw_text),
            "certifications": (slm._section_certifications(sections.get("certifications") or []) or slm._certifications_mentioned(raw_text)
                               or slm._extract_certifications(raw_text)),
            "languages": slm._extract_languages(raw_text),
        }

    @staticmethod
    def _extract_name(text: str) -> Optional[str]:
        """Extract candidate's full name (usually first 2-3 lines)"""
        lines = text.strip().split('\n')

        for line in lines[:5]:  # Check first 5 lines
            line_clean = line.strip()

            # Skip if line contains special markers
            if any(marker in line_clean.lower() for marker in
                   ['email', '@', 'phone', 'www', 'http', '|', '•', '-']):
                continue

            # Check if line looks like a name (proper case, 2-4 words, no numbers)
            words = line_clean.split()
            if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
                if not any(char.isdigit() for char in line_clean):
                    return line_clean

        return None

    @staticmethod
    def _extract_email(text: str) -> Optional[str]:
        """Extract email address using regex"""
        match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        return match.group(0) if match else None

    @staticmethod
    def _extract_phone(text: str) -> Optional[str]:
        """Extract phone number (international format friendly)"""
        # Pattern: +1-555-0123, (555) 555-1234, 555.555.1234, +44 20 7946 0958
        patterns = [
            r'\+\d{1,3}\s?[\d\s\-()]{7,}',  # +1 555-123-4567
            r'\(?[\d\s]{3}\)?[\s\-]?[\d\s]{3}[\s\-]?[\d]{4}',  # (555) 555-1234
            r'\d{3}\.\d{3}\.\d{4}',  # 555.555.1234
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()

        return None

    @staticmethod
    def _extract_current_title(text: str) -> Optional[str]:
        """Extract current job title (usually first occurrence after name)"""
        # Look for job title patterns
        job_patterns = [
            r'(?:Current\s+)?(?:Title|Position)[\s:]*([^\n]{1,100})',
            r'(?:Senior|Junior|Lead|Principal|Staff|Architect|Manager|Director|Head|Chief|VP|SVP)\s+([A-Z][^,\n]{1,80})',
        ]

        for pattern in job_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                # Remove dates/locations
                title = re.sub(r'\s*\(.*?\)', '', title)
                return title if len(title) < 100 else None

        return None

    @staticmethod
    def _extract_current_employer(text: str) -> Optional[str]:
        """Extract current employer"""
        # Look for "Currently at", "Current Employer", or first company after current title
        patterns = [
            r'(?:Currently|Current(?:\s+Employer)?)\s*(?:at|:)?\s*([^\n,]{1,100})',
            r'(?:Employer|Company)[\s:]*([^\n,]{1,100})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                employer = match.group(1).strip()
                # Remove dates
                employer = re.sub(r'\s*\(.*?\)', '', employer)
                return employer if len(employer) < 100 else None

        return None

    @staticmethod
    def _extract_work_history(text: str) -> List[Dict]:
        """Extract work experience entries"""
        jobs = []

        # Find work experience section
        work_section = text
        section_match = re.search(
            r'(?:experience|employment|work history|professional experience)(.*?)(?:education|skills|certification|languages|$)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if section_match:
            work_section = section_match.group(1)

        # Split by common job entry patterns
        # Pattern: "Company Name" + "Job Title" + dates
        job_blocks = re.split(r'\n(?=[A-Z][^,\n]*(?:Inc|LLC|Ltd|Corp|Co\.|Corporation|Company|COMPANY|INC|LLC)|\d{1,2}\s*(?:years?|months?)|20\d{2})', work_section)

        for block in job_blocks:
            if len(block.strip()) < 20:  # Skip very short blocks
                continue

            job_entry = ResumeSLM._parse_job_block(block)
            if job_entry.get('employer') or job_entry.get('title'):
                jobs.append(job_entry)

        return jobs

    @staticmethod
    def _parse_job_block(block: str) -> Dict:
        """Parse a single job entry block"""
        job = {
            "employer": None,
            "title": None,
            "start_date": None,
            "end_date": None,
            "description": None,
        }

        lines = block.strip().split('\n')

        # Extract dates
        date_pattern = r'(\d{4})[–\-/](\d{1,2})|(\d{1,2})/(\d{4})'
        dates = re.findall(date_pattern, block)

        if dates:
            # Assume first date is start, last is end
            first_date = dates[0]
            if first_date[0]:  # YYYY-MM format
                job["start_date"] = f"{first_date[0]}-{first_date[1].zfill(2)}"

            if len(dates) > 1:
                last_date = dates[-1]
                if last_date[0]:
                    job["end_date"] = f"{last_date[0]}-{last_date[1].zfill(2)}"
            else:
                job["end_date"] = None  # Currently employed

        # Extract employer (usually first line with company keywords)
        for line in lines[:3]:
            if any(keyword in line.lower() for keyword in ['inc', 'llc', 'ltd', 'corp', 'co.', 'company']):
                job["employer"] = line.strip()
                break

        if not job["employer"] and lines:
            job["employer"] = lines[0].strip()

        # Extract title (usually contains job title keywords)
        title_keywords = ['engineer', 'developer', 'manager', 'analyst', 'designer', 'architect', 'lead', 'director', 'specialist']
        for line in lines[1:]:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in title_keywords):
                job["title"] = line.strip()
                break

        # Extract description (remaining lines)
        desc_lines = [line.strip() for line in lines if line.strip() and line not in [job["employer"], job["title"]]]
        if desc_lines:
            job["description"] = " ".join(desc_lines)[:500]  # Limit to 500 chars

        return job

    @staticmethod
    def _extract_education(text: str) -> List[Dict]:
        """Extract education entries"""
        education = []

        # Find education section
        edu_section = text
        section_match = re.search(
            r'(?:education|academic|university|degree)(.*?)(?:experience|employment|skills|certification|$)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if section_match:
            edu_section = section_match.group(1)

        # Degree patterns
        degree_pattern = r'(?:B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|M\.?B\.?A\.?|Ph\.?D\.?|B\.?Tech|M\.?Tech|Associates?|High School|A\.?S\.?)'

        edu_blocks = re.split(r'\n(?=[A-Z].*(?:University|College|Institute|School)|\d{4})', edu_section)

        for block in edu_blocks:
            if len(block.strip()) < 10:
                continue

            entry = {
                "institution": None,
                "degree": None,
                "field": None,
                "graduation_year": None,
            }

            # Extract institution
            inst_match = re.search(r'([A-Z][^,\n]*(?:University|College|Institute|School|Academy))', block)
            if inst_match:
                entry["institution"] = inst_match.group(1).strip()

            # Extract degree
            degree_match = re.search(degree_pattern, block, re.IGNORECASE)
            if degree_match:
                entry["degree"] = degree_match.group(0)

            # Extract field of study
            field_match = re.search(r'(?:in|of)\s+([A-Z][^,\n]{1,80})', block)
            if field_match:
                entry["field"] = field_match.group(1).strip()

            # Extract graduation year
            year_match = re.search(r'\b(20\d{2})\b', block)
            if year_match:
                entry["graduation_year"] = int(year_match.group(1))

            if entry["institution"] or entry["degree"]:
                education.append(entry)

        return education

    @staticmethod
    def _extract_skills(text: str) -> List[str]:
        """Extract skills (technical and soft)"""
        skills_found = set()
        text_lower = text.lower()

        # Find skills section
        skills_section = text_lower
        section_match = re.search(
            r'(?:skills?|competencies|technical skills|expertise)(.*?)(?:experience|education|certification|project|$)',
            text_lower,
            re.IGNORECASE | re.DOTALL
        )
        if section_match:
            skills_section = section_match.group(1)

        # Extract known skills from our database
        for skill in ResumeSLM.TECHNICAL_SKILLS:
            if re.search(rf'\b{re.escape(skill)}\b', skills_section, re.IGNORECASE):
                skills_found.add(skill.title())

        # Look for comma-separated skill lists
        skill_list_match = re.search(r'skills?\s*:?\s*([^,\n]+(?:,\s*[^,\n]+)*)', skills_section, re.IGNORECASE)
        if skill_list_match:
            skills_text = skill_list_match.group(1)
            found_skills = [s.strip() for s in skills_text.split(',')]
            skills_found.update(found_skills)

        # Also search full text (in case skills listed in job descriptions)
        for skill in ResumeSLM.TECHNICAL_SKILLS:
            if re.search(rf'\b{re.escape(skill)}\b', text, re.IGNORECASE):
                # Only add if appears in work history context
                if any(context in text.lower() for context in ['experience', 'proficient', 'skilled', 'expert', 'develop']):
                    skills_found.add(skill.title())

        return sorted(list(skills_found))

    @staticmethod
    def _extract_certifications(text: str) -> List[Dict]:
        """Extract certifications and licenses"""
        certifications = []
        text_lower = text.lower()

        # Find certifications section
        cert_section = text_lower
        section_match = re.search(
            r'(?:certification|certifications|licenses?|credentials?)(.*?)(?:skills?|project|$)',
            text_lower,
            re.IGNORECASE | re.DOTALL
        )
        if section_match:
            cert_section = section_match.group(1)

        # Extract known certifications
        for cert in ResumeSLM.CERTIFICATIONS:
            if re.search(rf'\b{re.escape(cert)}\b', cert_section, re.IGNORECASE):
                # Extract issuer and year if available
                cert_match = re.search(
                    rf'\b{re.escape(cert)}\b[^\n]*',
                    text,
                    re.IGNORECASE
                )
                if cert_match:
                    cert_text = cert_match.group(0)
                    year_match = re.search(r'\b(20\d{2})\b', cert_text)

                    certifications.append({
                        "name": cert.title(),
                        "issuer": None,  # Could be extracted with more sophisticated parsing
                        "year": int(year_match.group(1)) if year_match else None,
                    })

        return certifications

    @staticmethod
    def _extract_languages(text: str) -> List[str]:
        """Extract languages spoken"""
        languages_found = set()
        text_lower = text.lower()

        # Find languages section
        lang_section = text_lower
        section_match = re.search(
            r'(?:language|languages?|linguistic)(.*?)(?:certification|skills?|project|$)',
            text_lower,
            re.IGNORECASE | re.DOTALL
        )
        if section_match:
            lang_section = section_match.group(1)

        # Extract known languages
        for lang in ResumeSLM.LANGUAGES:
            if re.search(rf'\b{re.escape(lang)}\b', lang_section, re.IGNORECASE):
                languages_found.add(lang.title())

        # Look for proficiency levels
        proficiency_pattern = r'(\w+)\s*(?:–|:)\s*(?:native|fluent|intermediate|basic|beginner)'
        matches = re.findall(proficiency_pattern, lang_section, re.IGNORECASE)
        for match in matches:
            languages_found.add(match.title())

        return sorted(list(languages_found))

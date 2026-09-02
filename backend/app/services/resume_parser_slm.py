"""
import logging
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

import re
from typing import Dict, List, Optional, Set
from datetime import datetime

from app.core.logging import logger

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
        "python", "javascript", "java", "csharp", "c#", "ruby", "golang", "go",
        "typescript", "rust", "kotlin", "swift", "php", "perl", "r", "scala",
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

        return {
            "full_name": slm._extract_name(raw_text),
            "email": slm._extract_email(raw_text),
            "phone": slm._extract_phone(raw_text),
            "current_title": slm._extract_current_title(raw_text),
            "current_employer": slm._extract_current_employer(raw_text),
            "work_history": slm._extract_work_history(raw_text),
            "education": slm._extract_education(raw_text),
            "skills": slm._extract_skills(raw_text),
            "certifications": slm._extract_certifications(raw_text),
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

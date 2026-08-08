"""
Job Description Templates — Known-Role Library
================================================

HOW TO ADD A NEW ROLE (Avinash — this is your action item):

1. Add a new entry to JOB_DESCRIPTION_TEMPLATES below.
2. The dict key is the role's normalized title: lowercase, exactly how a
   recruiter would type it in the "Hiring Manager 1-Liner" field (e.g.
   "senior guidewire developer" normalizes to "guidewire developer" once
   seniority words are stripped — see recruitment_job_creation_service.py's
   title cleanup — so key on the CLEANED title, not the raw one-liner).
3. "description" is the full job description text. It may reference
   {location} and {experience} — these get filled in from what the
   recruiter/agent actually answered, so don't hardcode a specific city or
   years-of-experience range into the template text itself.
4. "skills" is a flat list of strings — these populate the job's Skills
   field directly (or the Boolean search skill groups, once EPIC-P9 lands).

When a role's normalized title matches a key here, the system uses this
template VERBATIM and never calls the LLM for that job's description or
skills — no quota usage, no variance, no risk of a bad LLM day. Only roles
NOT in this dict fall through to LLM generation (and from there to the
template-free fallback if the LLM is also unavailable).

Only one role is seeded below as a worked example (Guidewire Developer,
since that's BlitzenX's core specialty). Everything else still goes
through the LLM until you add more entries here.
"""

from typing import Dict, TypedDict, List


class JobDescriptionTemplate(TypedDict):
    description: str
    skills: List[str]


JOB_DESCRIPTION_TEMPLATES: Dict[str, JobDescriptionTemplate] = {
    "guidewire developer": {
        "description": (
            "BlitzenX is looking for a Guidewire Developer to join our team, "
            "supporting implementation and configuration work across the "
            "Guidewire InsuranceSuite (PolicyCenter, BillingCenter, and/or "
            "ClaimCenter).\n\n"
            "Key Responsibilities:\n"
            "- Configure and customize Guidewire modules using Gosu, PCF, "
            "and product data model extensions\n"
            "- Build and maintain integrations between Guidewire and "
            "upstream/downstream systems (rating engines, document "
            "management, third-party data providers)\n"
            "- Participate in requirements analysis with business analysts "
            "and translate insurance business rules into working "
            "configuration\n"
            "- Write and maintain unit/integration tests (gunit) and "
            "support UAT cycles\n"
            "- Troubleshoot production and pre-production defects, "
            "including root-cause analysis on rating, underwriting, or "
            "claims workflow issues\n"
            "- Participate in code reviews and follow Guidewire's "
            "recommended configuration-first, customization-last practices\n\n"
            "Requirements:\n"
            "- {experience} of hands-on Guidewire development experience "
            "(PolicyCenter, BillingCenter, or ClaimCenter)\n"
            "- Strong Gosu, Java, and SQL skills\n"
            "- Working knowledge of the Guidewire product/rules/UI layers "
            "and standard integration patterns (messaging, plugins, "
            "REST/SOAP)\n"
            "- P&C insurance domain exposure preferred\n"
            "- {location}, able to work with the assigned team's overlap "
            "hours\n"
            "- Strong written and verbal communication for client-facing "
            "configuration discussions"
        ),
        "skills": [
            "Guidewire PolicyCenter",
            "Guidewire BillingCenter",
            "Guidewire ClaimCenter",
            "Gosu",
            "Java",
            "SQL",
            "PCF",
            "Guidewire Integration (Messaging/Plugins)",
            "P&C Insurance Domain",
            "Agile/Scrum",
        ],
    },
}

"""Approved starting copy for each cadence step (2 variants per A/B step).

Seeded once by db_contract; rows already in the database are never
overwritten, so copy edited or retired in the database stays as is.
Merge fields: {first_name} {sender_name} {hook} {job_title} {job_location}
{salary_range} {jobs_list} {highlight} {source_note}. Every email carries the footer.
"""
from sqlalchemy.orm import Session

from app.models.thunder_email import ThunderOutreachVariant

FOOTER = (
    "<hr><p style='font-size:12px;color:#666'>You're hearing from us because your professional profile "
    "is in the BlitzenX talent network.{source_note} Reply \"remove\" and we will stop emailing you and "
    "delete your details.</p>"
)
SIGN = "<p>Regards,<br>{sender_name}</p>"

SEED_VARIANTS = [
    ("s1_direct", "1", "{first_name}, a quick question about your next move",
     "<p>Hi {first_name},</p><p>{hook}I'd like to share a role that I think fits where you're heading. "
     "A 15-minute conversation is all I'm asking for.</p><p>Would you be open to that?</p>"),
    ("s1_curiosity", "1", "{first_name}, are you open to hearing about something new?",
     "<p>Hi {first_name},</p><p>{hook}We're growing a team where people like you tend to do their best work. "
     "No pressure if you're happy where you are.</p><p>Worth a short chat this week?</p>"),
    ("s2_bump", "2", "Re: a quick question",
     "<p>Hi {first_name},</p><p>Just bringing this back to the top of your inbox. "
     "Would a quick call work, or should I share the details by email instead?</p>"),
    ("s2_value", "2", "Re: a quick question",
     "<p>Hi {first_name},</p><p>One thing I didn't mention: the people we place work on real client "
     "programmes, not bench time. Happy to share specifics if that's useful.</p>"),
    ("s3_angle_growth", "3", "Re: a quick question",
     "<p>Hi {first_name},</p><p>Different question: what would a move need to offer for it to be worth "
     "your time? Growth, money, location, the work itself? One line is enough.</p>"),
    ("s3_angle_easy", "3", "Re: a quick question",
     "<p>Hi {first_name},</p><p>If timing isn't right, just reply \"later\" and I'll check back in a few "
     "months instead.</p>"),
    ("s4_close", "4", "Re: a quick question",
     "<p>Hi {first_name},</p><p>I won't keep following up on this one. I'll send an occasional note when "
     "something matching your background opens up. Reply any time if that changes.</p>"),
    ("s4_close_door", "4", "Re: a quick question",
     "<p>Hi {first_name},</p><p>Closing the loop on my last few emails. The door stays open: reply whenever "
     "the timing suits you.</p>"),
    ("n_roles_first", "NURTURE", "{first_name}, roles that match your background this month",
     "<p>Hi {first_name},</p><p>A short monthly note with open roles that match your background:</p>"
     "{jobs_list}{highlight}<p>Reply if any of these is worth a conversation.</p>"),
    ("n_highlight_first", "NURTURE", "{first_name}, what's new at BlitzenX",
     "<p>Hi {first_name},</p>{highlight}<p>Open roles that match your background:</p>{jobs_list}"
     "<p>Reply if you'd like details on any of them.</p>"),
    ("ack_interested", "ACK_INTERESTED", "Re: great, let's set up a call",
     "<p>Hi {first_name},</p><p>Great to hear from you. A member of our team will reach out shortly with "
     "a couple of time slots for a call.</p>"),
    ("ack_comp", "ACK_COMP", "Re: compensation for the role",
     "<p>Hi {first_name},</p><p>Good question. The range on record for {job_title} ({job_location}) is "
     "{salary_range}. Final numbers depend on experience. Shall we set up a short call?</p>"),
    ("ack_role", "ACK_ROLE", "Re: details on the role",
     "<p>Hi {first_name},</p><p>Thanks for asking. A member of our team will send you the details shortly "
     "and answer your questions directly.</p>"),
]
REQUIRES_JOB = {"ack_comp"}


def seed_thunder_variants(db: Session) -> int:
    existing = {key for (key,) in db.query(ThunderOutreachVariant.key)}
    added = 0
    for key, step, subject, body in SEED_VARIANTS:
        if key in existing:
            continue
        db.add(ThunderOutreachVariant(
            key=key, step=step, subject_template=subject, body_template=body + SIGN + FOOTER,
            requires_job=key in REQUIRES_JOB, active=True,
        ))
        added += 1
    db.commit()
    return added

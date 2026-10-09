"""Test helper: put a candidate through every hiring gate before employment (CEO order):
screen skipped, L1 and L2 passed, offer accepted, pre-joining documents verified, BGV passed."""
from datetime import date, datetime, timedelta

from app.models.background_verification import BackgroundVerification
from app.models.interview_verdict import InterviewRoundVerdict
from app.models.offer_letter import OfferLetter
from app.models.preboarding_document import PreboardingDocument
from app.models.user import InterviewPanel


def clear_hiring(db, candidate, offer=None, joining_date=None):
    """Returns the accepted offer. Commits."""
    for level in ("L1", "L2"):
        panel = InterviewPanel(candidate_id=candidate.candidateID, round_name=level)
        db.add(panel)
        db.flush()
        db.add(InterviewRoundVerdict(panel_id=panel.id, candidate_id=candidate.candidateID, level=level,
                                     verdict="PASS", source="MANUAL"))
    if offer is None:
        offer = OfferLetter(candidate_id=candidate.candidateID, position="Engineer", salary="1200000",
                            joining_date=joining_date or date.today() - timedelta(days=1),
                            offer_expire_date=date.today() + timedelta(days=7), offer_status="Accepted",
                            responded_at=datetime.utcnow() - timedelta(days=2))
        db.add(offer)
        db.flush()
    db.add(PreboardingDocument(tenant_id=str(candidate.tenant_id or 1), candidate_id=candidate.candidateID,
                               offer_id=offer.id, document_type="ID_PROOF", document_label="ID", status="VERIFIED",
                               is_mandatory=True))
    db.add(BackgroundVerification(tenant_id=candidate.tenant_id, candidate_id=candidate.candidateID,
                                  offer_letter_id=offer.id, status="PASSED"))
    db.commit()
    return offer

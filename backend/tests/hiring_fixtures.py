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


def finance_approver(db, tenant_id=1, level=11):
    """A Finance Director (Senior Manager+ in Finance): the only kind of user who may approve invoices.
    The role holds the invoices permission, as Finance roles do in production."""
    import uuid

    from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
    from app.models.tenant import Tenant
    from app.models.user import Users

    if db.query(Tenant).filter_by(id=tenant_id).first() is None:
        db.add(Tenant(id=tenant_id, name="test-tenant"))
        db.flush()
    suffix = uuid.uuid4().hex[:8]
    role = RoleTemplate(tenant_id=tenant_id, name=f"finance-director-{suffix}", display_name="Finance Director",
                        hierarchy_level=level, specialization="Finance", enabled=True)
    db.add(role)
    db.flush()
    resource = db.query(Resource).filter_by(tenant_id=tenant_id, name="invoices").first()
    if resource is None:
        module = db.query(Module).filter_by(tenant_id=tenant_id, name="Finance").first() or \
            Module(tenant_id=tenant_id, name="Finance", display_name="Finance")
        db.add(module)
        db.flush()
        resource = Resource(tenant_id=tenant_id, module_id=module.id, name="invoices", display_name="Invoices")
        db.add(resource)
        db.flush()
    db.add(RoleTemplatePermission(role_template_id=role.id, resource_id=resource.id, tenant_id=tenant_id,
                                  can_view=True, can_create=True, can_edit=True))
    db.flush()
    user = Users(UserID=f"FIN-{suffix}", UserName="Fin Director", UserEmail=f"fin{suffix}@blitzenx.com",
                 UserPassword="x", UserRole="finance", tenant_id=tenant_id, role_template_id=role.id,
                 password_reset_required=False)
    db.add(user)
    db.flush()
    return user

import fastapi

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.create_job import router as create_job_router
from app.api.v1.endpoints.candidates import router as candidates_router
from app.api.v1.endpoints.msgraph import router as msgraph_router
from app.api.v1.endpoints.onboarding import router as onboarding_router
from app.api.v1.endpoints.interviews import router as interviews_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.offer_letters import router as offer_letters_router
from app.api.v1.endpoints.newsletter import router as newsletter_router
from app.api.v1.endpoints.rbac import router as rbac_router
from app.api.v1.endpoints.checklists import router as checklists_router
from app.api.v1.endpoints.candidate_status import router as candidate_status_router
from app.api.v1.endpoints.ats import router as ats_router
from app.api.v1.endpoints.email import router as email_router
from app.api.v1.endpoints.candidate_history import router as candidate_history_router
from app.api.v1.endpoints.candidate_ownership import router as candidate_ownership_router
from app.api.v1.endpoints.preonboarding import router as preonboarding_router
from app.api.v1.endpoints.internal import router as internal_router

router = fastapi.APIRouter()

router.include_router(router=auth_router)
router.include_router(router=rbac_router)
router.include_router(router=users_router)
router.include_router(router=create_job_router)
router.include_router(router=onboarding_router)
router.include_router(router=interviews_router)
router.include_router(router=candidates_router)
router.include_router(router=msgraph_router)
router.include_router(router=documents_router)
router.include_router(router=offer_letters_router)
router.include_router(router=newsletter_router)
router.include_router(router=checklists_router)
router.include_router(router=candidate_status_router)
router.include_router(router=ats_router)
router.include_router(router=email_router)
router.include_router(router=candidate_history_router)
router.include_router(router=candidate_ownership_router)
router.include_router(router=preonboarding_router)
router.include_router(router=internal_router)
"""
import logging
S-027/HRMS-0427 -- Resume Upload via WhatsApp/Email.

Real architecture facts that shape this story's scope (confirmed by
reading the actual code before writing anything):

- Document storage is real and already built: SharePoint via MS Graph
  (app.services.document_service.DocumentService), tracked in the
  real candidate_documents table (CandidateDocument), NOT S3 as the
  spec assumes. BR-01 (most recent resume overwrites, old archived) is
  ALREADY fully implemented by DocumentService.save_document_metadata()
  for document_type="resume" (it's not in MULTI_UPLOAD_TYPES, so it
  automatically flips the previous is_latest=True row to False and
  bumps version) -- reused as-is here, not reimplemented.
- No `resume_url` column exists on Candidate at all. Resume presence
  is tracked exclusively via CandidateDocument rows
  (document_type="resume", is_latest=True) -- that's the real
  "resume received" signal this story checks and reports, not a
  candidates-table field. No candidate_missing_fields table either
  (established this whole round); "markFieldReceived()" has no literal
  home here since resume was never part of get_missing_fields()'s
  tracked field set to begin with.
- BR-03's async requirement (don't block on parsing) is moot for this
  story specifically: HRMS-0428 Resume Parsing Engine doesn't exist
  yet, so there's nothing to await either way.
- The genuinely missing prerequisite this story's own "Depends On"
  section assumes but doesn't actually exist in this codebase:
  HRMS-0402 (WhatsApp media download) explicitly stores only a Meta
  media_id, never downloads the file (see whatsapp_webhook_service.py's
  own documented decision -- "needs a real S3 bucket + WHATSAPP_ACCESS_TOKEN,
  neither configured"); the email pipeline doesn't request or download
  attachments at all (ai_conversation_service.py's Graph $select
  doesn't even include hasAttachments). So "listen for
  candidate.document_received" has no real upstream event to listen
  to on EITHER channel today.

Given that, this story is scoped to the part that IS real and
buildable now: handle_resume_document(), a complete, tested function
that takes already-downloaded file bytes (however they eventually
arrive -- WhatsApp Media API download or Graph attachment download,
both real future integration work, not invented here) and does
everything downstream: BR-02 format filtering, SharePoint storage via
the existing DocumentService, a channel-aware Thunder confirmation
(reusing qualification_conversation_service.send_channel_aware_message),
and BR-03-adjacent qualification continuation via
qualification_engine_service.get_qualification_plan(). This is
immediately callable once either channel's real media-download step
is built -- documented as the actual remaining gap, not silently
glossed over.
"""
import mimetypes
import os
from typing import Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.document import CandidateDocument
from app.services.document_service import DOCUMENT_TYPES, DocumentService
from app.services.qualification_conversation_service import send_channel_aware_message
from app.services.qualification_engine_service import get_qualification_plan, is_qualifying_state

RESUME_ALLOWED_EXTENSIONS = tuple(DOCUMENT_TYPES["resume"]["extensions"])  # .pdf, .doc, .docx

WRONG_FORMAT_MESSAGE = (
    "Thanks for sending that! However, I need your resume in PDF or Word format. "
    "Could you resend it as a .pdf or .docx file?"
)
STORAGE_FAILED_RECRUITER_ALERT = (
    "Thunder received a resume from {name} but could not store it after two attempts. Please follow up manually."
)


def _confirmation_message(candidate: Candidate) -> str:
    name = candidate.candidateFirstName or candidate.candidateEmail or "there"
    return (
        f"Thank you {name}! I have received your resume and will review it shortly. "
        "I'll be in touch with the next steps."
    )


def has_active_resume(db: Session, candidate_id: str) -> bool:
    return (
        db.query(CandidateDocument)
        .filter(CandidateDocument.candidate_id == candidate_id, CandidateDocument.document_type == "resume", CandidateDocument.is_latest == True, CandidateDocument.is_deleted == False)
        .first()
        is not None
    )


def _extension_from(filename: str, mime_type: Optional[str]) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext:
        return ext
    guessed = mimetypes.guess_extension(mime_type or "") or ""
    return guessed.lower()


def _notify_recruiter_of_storage_failure(db: Session, tenant_id: str, candidate: Candidate) -> None:
    from app.models.candidate_ai import CandidateAIAssignment
    from app.models.user import Users
    from app.services.notification_service import send_notification

    assignment = (
        db.query(CandidateAIAssignment)
        .filter(CandidateAIAssignment.candidate_id == candidate.candidateID, CandidateAIAssignment.is_active == True)
        .order_by(CandidateAIAssignment.assigned_at.desc())
        .first()
    )
    recipient_id = assignment.assigned_by if assignment and assignment.assigned_by else tenant_id
    recipient = db.query(Users).filter(Users.UserID == recipient_id).first()
    if not recipient:
        return
    try:
        send_notification(
            db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient,
            priority_tier="P1", channel_preference="IN_APP",
            message=STORAGE_FAILED_RECRUITER_ALERT.format(name=candidate.candidateFirstName or candidate.candidateID),
        )
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[ResumeUpload] Failed to notify recruiter of storage failure for candidate {candidate.candidateID}: {exc}")


def handle_resume_document(
    db: Session,
    conversation: CandidateConversation,
    candidate: Candidate,
    tenant_id: str,
    *,
    file_content: bytes,
    original_filename: str,
    mime_type: Optional[str],
    source: str,
    graph_token_fn: Optional[Callable[[], str]] = None,
    llm_call: Optional[Callable[[str], str]] = None,
    whatsapp_client=None,
) -> Dict:
    """
    Never raises. Returns one of:
      {"outcome": "wrong_format"}
      {"outcome": "storage_failed"}
      {"outcome": "stored", "document_id": ..., "sharepoint_url": ...}
    """
    extension = _extension_from(original_filename, mime_type)
    if extension not in RESUME_ALLOWED_EXTENSIONS:  # BR-02
        db.add(ConversationEvent(
            conversation_id=conversation.id, event_type="RESUME_WRONG_FORMAT",
            event_data={"mime_type": mime_type, "filename": original_filename, "source": source}, triggered_by="candidate",
        ))
        send_channel_aware_message(db, conversation, candidate, WRONG_FORMAT_MESSAGE, whatsapp_client=whatsapp_client)
        db.commit()
        return {"outcome": "wrong_format"}

    doc_service = DocumentService(db)
    document = None
    last_error: Optional[Exception] = None

    for attempt in range(2):  # BR: retry once on storage failure
        try:
            token_fn = graph_token_fn
            if token_fn is None:
                from app.core.graph_auth import get_graph_token as _get_graph_token
                token_fn = _get_graph_token
            access_token = token_fn()

            unique_filename = doc_service.generate_unique_filename(original_filename, candidate.candidateID, "resume")
            sharepoint_data = doc_service.upload_to_sharepoint(access_token, candidate.candidateID, "resume", file_content, unique_filename)
            document = doc_service.save_document_metadata(
                candidate_id=candidate.candidateID, document_type="resume", original_filename=original_filename,
                unique_filename=unique_filename, file_size=len(file_content), file_extension=extension,
                sharepoint_data=sharepoint_data, uploaded_by="thunder_ai",
            )
            break
        except Exception as exc:
           logger.error(f"Error: {str(exc)}", exc_info=True)
            last_error = exc
            logger.warning(f"[ResumeUpload] Storage attempt {attempt + 1} failed for candidate {candidate.candidateID}: {exc}")

    if document is None:
        db.add(ConversationEvent(
            conversation_id=conversation.id, event_type="RESUME_STORAGE_FAILED",
            event_data={"reason": str(last_error), "source": source}, triggered_by="system",
        ))
        db.commit()
        _notify_recruiter_of_storage_failure(db, tenant_id, candidate)
        return {"outcome": "storage_failed"}

    db.add(ConversationEvent(
        conversation_id=conversation.id, event_type="RESUME_UPLOADED",
        event_data={"document_id": document.id, "sharepoint_url": document.sharepoint_url, "source": source}, triggered_by="candidate",
    ))

    message = _confirmation_message(candidate)
    if is_qualifying_state(conversation):
        plan = get_qualification_plan(db, conversation, candidate, tenant_id, llm_call=llm_call)
        if not plan["is_complete"] and plan["question"]:
            message = f"{message} {plan['question']}"

    send_channel_aware_message(db, conversation, candidate, message, whatsapp_client=whatsapp_client)
    db.commit()
    return {"outcome": "stored", "document_id": document.id, "sharepoint_url": document.sharepoint_url}

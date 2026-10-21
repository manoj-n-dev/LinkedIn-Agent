"""Draft service managing creation, hashing, versioning, and validation (FR-004, FR-005)."""

import hashlib
import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.ai.groq_client import generate_completion
from src.ai.prompts import (
    build_comment_prompt,
    build_connection_note_prompt,
    build_post_prompt,
    build_revision_prompt,
)
from src.ai.rules import (
    ValidationResult,
    validate_comment,
    validate_connection_note,
    validate_post,
)
from src.db.models import AICall, Approval, AuditLog, Draft


def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hash of text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generate_draft_code(db: Session) -> str:
    """Generate an unused unique short code like 'd-9a8b1c'."""
    while True:
        code = f"d-{secrets.token_hex(3)}"
        existing = db.execute(select(Draft.id).where(Draft.code == code)).scalar_one_or_none()
        if not existing:
            return code


class DraftService:
    """Orchestrates AI draft generation, rule checks, and database persistence."""

    def __init__(self, db: Session, api_key: str, model: str):
        self.db = db
        self.api_key = api_key
        self.model = model

    def _log_ai_call(self, purpose: str, status: str, http_status: int | None = None) -> None:
        call_log = AICall(
            provider="groq",
            purpose=purpose,
            status=status,
            http_status=http_status,
        )
        self.db.add(call_log)

    def _log_audit(
        self,
        event: str,
        entity_id: str,
        outcome: str = "success",
        details: dict[str, Any] | None = None,
    ) -> None:
        audit = AuditLog(
            actor="ai",
            event=event,
            entity_type="draft",
            entity_id=entity_id,
            outcome=outcome,
            details=details or {},
        )
        self.db.add(audit)

    async def create_post_draft(
        self,
        idea: str,
        context: str | None = None,
        tone: str = "friendly, honest, curious, professional",
        language: str = "English",
        allowed_urls: set[str] | None = None,
    ) -> tuple[Draft, ValidationResult]:
        """Generate a new LinkedIn post draft from an idea."""
        sys_prompt, user_prompt = build_post_prompt(idea, context, tone=tone, language=language)

        try:
            raw_text = await generate_completion(
                api_key=self.api_key,
                model=self.model,
                system_prompt=sys_prompt,
                user_prompt=user_prompt,
            )
            self._log_ai_call(purpose="draft_post", status="success", http_status=200)
        except Exception:
            self._log_ai_call(purpose="draft_post", status="failed")
            raise

        validation = validate_post(raw_text, allowed_urls=allowed_urls)
        code = generate_draft_code(self.db)
        content_hash = compute_content_hash(validation.cleaned_text)

        draft = Draft(
            code=code,
            kind="post",
            version=1,
            idea=idea,
            body=validation.cleaned_text,
            content_hash=content_hash,
            context_text=context,
            status="draft",
        )
        self.db.add(draft)
        self._log_audit(
            event="draft_created",
            entity_id=code,
            details={"kind": "post", "version": 1, "warnings": validation.warnings},
        )
        self.db.commit()
        self.db.refresh(draft)
        return draft, validation

    async def create_comment_draft(
        self,
        post_text: str,
        tone: str = "friendly, honest, curious, professional",
        language: str = "English",
    ) -> tuple[Draft, ValidationResult]:
        """Generate 2-3 comment options in response to a post."""
        sys_prompt, user_prompt = build_comment_prompt(post_text, tone=tone, language=language)

        try:
            raw_text = await generate_completion(
                api_key=self.api_key,
                model=self.model,
                system_prompt=sys_prompt,
                user_prompt=user_prompt,
            )
            self._log_ai_call(purpose="draft_comment", status="success", http_status=200)
        except Exception:
            self._log_ai_call(purpose="draft_comment", status="failed")
            raise

        validation = validate_comment(raw_text)
        code = generate_draft_code(self.db)
        content_hash = compute_content_hash(validation.cleaned_text)

        draft = Draft(
            code=code,
            kind="comment",
            version=1,
            idea=None,
            body=validation.cleaned_text,
            content_hash=content_hash,
            context_text=post_text,
            status="draft",
        )
        self.db.add(draft)
        self._log_audit(
            event="draft_created",
            entity_id=code,
            details={"kind": "comment", "version": 1},
        )
        self.db.commit()
        self.db.refresh(draft)
        return draft, validation

    async def create_connection_note_draft(
        self,
        recipient_context: str,
        tone: str = "friendly, honest, curious, professional",
        language: str = "English",
    ) -> tuple[Draft, ValidationResult]:
        """Generate a connection note (< 200 chars)."""
        sys_prompt, user_prompt = build_connection_note_prompt(
            recipient_context, tone=tone, language=language
        )

        try:
            raw_text = await generate_completion(
                api_key=self.api_key,
                model=self.model,
                system_prompt=sys_prompt,
                user_prompt=user_prompt,
            )
            self._log_ai_call(purpose="draft_note", status="success", http_status=200)
        except Exception:
            self._log_ai_call(purpose="draft_note", status="failed")
            raise

        validation = validate_connection_note(raw_text)
        code = generate_draft_code(self.db)
        content_hash = compute_content_hash(validation.cleaned_text)

        draft = Draft(
            code=code,
            kind="connection_note",
            version=1,
            idea=recipient_context,
            body=validation.cleaned_text,
            content_hash=content_hash,
            context_text=recipient_context,
            status="draft",
        )
        self.db.add(draft)
        self._log_audit(
            event="draft_created",
            entity_id=code,
            details={"kind": "connection_note", "version": 1},
        )
        self.db.commit()
        self.db.refresh(draft)
        return draft, validation

    async def revise_draft(
        self,
        draft_code: str,
        instruction: str,
        tone: str = "friendly, honest, curious, professional",
        language: str = "English",
    ) -> tuple[Draft, ValidationResult]:
        """Revise an existing draft into a new version and void any pending approvals (FR-005)."""
        parent = self.db.execute(select(Draft).where(Draft.code == draft_code)).scalar_one_or_none()

        if not parent:
            raise ValueError(f"Draft '{draft_code}' not found.")

        # Determine root parent and next version number
        root_parent_id = parent.parent_id or parent.id
        latest_versions = (
            self.db.execute(
                select(Draft.version).where(
                    (Draft.id == root_parent_id) | (Draft.parent_id == root_parent_id)
                )
            )
            .scalars()
            .all()
        )
        next_version = (max(latest_versions) if latest_versions else parent.version) + 1

        sys_prompt, user_prompt = build_revision_prompt(
            current_body=parent.body,
            instruction=instruction,
            tone=tone,
            language=language,
        )

        try:
            raw_text = await generate_completion(
                api_key=self.api_key,
                model=self.model,
                system_prompt=sys_prompt,
                user_prompt=user_prompt,
            )
            self._log_ai_call(purpose="revise_draft", status="success", http_status=200)
        except Exception:
            self._log_ai_call(purpose="revise_draft", status="failed")
            raise

        validation = validate_post(raw_text)
        new_code = generate_draft_code(self.db)
        content_hash = compute_content_hash(validation.cleaned_text)

        new_draft = Draft(
            code=new_code,
            kind=parent.kind,
            parent_id=root_parent_id,
            version=next_version,
            idea=parent.idea,
            body=validation.cleaned_text,
            content_hash=content_hash,
            context_text=parent.context_text,
            status="draft",
        )
        self.db.add(new_draft)

        # Void any pending approvals for prior versions of this draft (FR-005)
        prior_draft_ids = (
            self.db.execute(
                select(Draft.id).where(
                    (Draft.id == root_parent_id) | (Draft.parent_id == root_parent_id)
                )
            )
            .scalars()
            .all()
        )

        for d_id in prior_draft_ids:
            pending_approvals = (
                self.db.execute(
                    select(Approval).where(
                        Approval.draft_id == d_id,
                        Approval.decision == "pending",
                    )
                )
                .scalars()
                .all()
            )
            for app in pending_approvals:
                app.decision = "expired"

        self._log_audit(
            event="draft_revised",
            entity_id=new_code,
            details={
                "parent_code": draft_code,
                "version": next_version,
                "voided_approvals_count": len(prior_draft_ids),
            },
        )
        self.db.commit()
        self.db.refresh(new_draft)
        return new_draft, validation

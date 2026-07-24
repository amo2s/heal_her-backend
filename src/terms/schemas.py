"""
src/terms/mutations.py

The GraphQL execution layer for Legal Document Signatures.
Connects the Next.js frontend to the OTP cache, consent lock, and Cryptographic PDF engine.
"""

import logging
import strawberry
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from graphql import GraphQLError

# -- Internal Service Imports --
from terms.auth_service import generate_and_cache_signature_otp, verify_signature_otp, OTPVerificationError
from terms.signing import lock_consent_payload, release_consent_payload, ConsentPayloadError
from terms.pdf_service import generate_and_seal_document

# Note: Adjust this import path depending on the exact name of your mailer service file
from mailers.reset_password import send_signature_otp_email

# -- Database Models --
from terms.models import DocumentSignature

logger = logging.getLogger("HEAL_LEGAL_SECURITY")


@strawberry.type
class DocumentSignatureResponse:
    """
    Standardized strict response object for the Next.js client.
    Error states are handled exclusively via the standard GraphQL 'errors' array.
    """
    status: str
    message: str
    document_hash: Optional[str] = None
    storage_url: Optional[str] = None


def _validate_minor_fields(minor_name: Optional[str], minor_age: Optional[int]) -> None:
    """Shared guard so both mutations enforce identical minor-consent input rules."""
    if minor_age is not None and not (0 < minor_age < 18):
        raise GraphQLError("If signing for a minor, age must be between 1 and 17.")
    if minor_name and minor_name.strip() and not minor_age:
        raise GraphQLError("Minor age is required if a minor's name is provided.")


@strawberry.type
class LegalMutations:

    @strawberry.mutation
    async def request_legal_signature_otp(
        self,
        info: strawberry.Info,
        email: str,
        name: str,
        minor_name: Optional[str] = None,
        minor_age: Optional[int] = None
    ) -> bool:
        """
        Step 1: Generates the OTP AND locks the exact consent payload it will later
        release only to the matching, verified request — this is what binds identity to intent.
        """
        clean_email = email.lower().strip()
        clean_name = name.strip()
        clean_minor_name = minor_name.strip() if minor_name else None

        _validate_minor_fields(clean_minor_name, minor_age)

        try:
            # 1. Cryptographic Generation & Cache Lock
            otp_code = await generate_and_cache_signature_otp(clean_email)

            # 2. Lock the consent payload NOW, tied to the same email and TTL as the OTP.
            # This is the only copy of "what was agreed to" the system will trust later.
            await lock_consent_payload(clean_email, {
                "name": clean_name,
                "minor_name": clean_minor_name,
                "minor_age": minor_age
            })

            # 3. Async Network Dispatch via Google Apps Script
            await send_signature_otp_email(
                email=clean_email,
                recipient_name=clean_name,
                otp_code=otp_code
            )

            return True

        except OTPVerificationError as e:
            logger.warning(f"[OTP REQUEST BLOCKED] {clean_email}: {e.message}")
            extensions = {"retry_after_seconds": e.retry_after_seconds} if e.retry_after_seconds else {}
            raise GraphQLError(e.message, extensions=extensions)

        except Exception as e:
            logger.error(f"[OTP REQUEST FAILED] Could not process request for {clean_email}: {str(e)}")
            raise GraphQLError("Failed to process signature request. Please try again later.")

    @strawberry.mutation
    async def execute_document_signature(
        self,
        info: strawberry.Info,
        email: str,
        otp_code: str,
        ip_address: str
    ) -> DocumentSignatureResponse:
        """
        Step 2: Verifies the OTP, then releases the payload that was locked in step 1.
        Client no longer supplies name/minor fields here — they cannot be swapped post-verification.
        """
        clean_email = email.lower().strip()

        # Extract the AsyncSession injected dynamically via FastAPI/Strawberry context dependencies
        db: AsyncSession = info.context["db"]

        try:
            # 1. Cryptographic Validation (Raises OTPVerificationError if failed, expired, or locked)
            await verify_signature_otp(clean_email, otp_code)

            # 2. Release the payload locked at request-time — this, not client input, is the source of truth.
            payload = await release_consent_payload(clean_email)

            # 3. The PDF Generation, Sealing, & Cloud Streaming Engine
            pdf_metadata = await generate_and_seal_document(
                client_name=payload["name"],
                client_email=clean_email,
                ip_address=ip_address,
                minor_name=payload["minor_name"],
                minor_age=payload["minor_age"]
            )

            # 4. Permanent Database Audit Record Generation
            new_signature = DocumentSignature(
                client_name=payload["name"],
                client_email=clean_email,
                minor_name=payload["minor_name"],
                minor_age=payload["minor_age"],
                ip_address=ip_address,
                document_hash=pdf_metadata["document_hash"],
                storage_path=pdf_metadata["storage_url"],
                signed_at=pdf_metadata["signed_at"]
            )

            db.add(new_signature)
            await db.commit()
            await db.refresh(new_signature)

            logger.info(f"Legal document successfully executed, locked, and stored for {clean_email}")

            return DocumentSignatureResponse(
                status="success",
                message="Document successfully signed and cryptographically locked.",
                document_hash=pdf_metadata["document_hash"],
                storage_url=pdf_metadata["storage_url"]
            )

        except OTPVerificationError as e:
            extensions = {"retry_after_seconds": e.retry_after_seconds} if e.retry_after_seconds else {}
            raise GraphQLError(e.message, extensions=extensions)

        except ConsentPayloadError as e:
            # OTP was valid but the locked payload was missing/expired/already consumed.
            logger.error(f"[CONSENT PAYLOAD MISSING] {clean_email}: {str(e)}")
            raise GraphQLError("Your session expired before signing completed. Please request a new code.")

        except Exception as e:
            # 5. Total Rollback Shield
            logger.critical(f"[EXECUTION FATAL] System failure executing signature for {clean_email}: {str(e)}")
            await db.rollback()
            raise GraphQLError("A critical infrastructure error occurred during document execution. No changes were saved.")
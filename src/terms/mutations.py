"""
src/terms/graphql/mutations.py

The GraphQL execution layer for Legal Document Signatures.
Connects the Next.js frontend to the OTP cache, mailer transports, and Cryptographic PDF engine.
"""

import logging
import strawberry
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

# -- Internal Service Imports --
from terms.auth_service import generate_and_cache_signature_otp, verify_signature_otp, OTPVerificationError
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
    """
    status: str
    message: str
    document_hash: Optional[str] = None
    storage_url: Optional[str] = None


@strawberry.type
class LegalMutations:
    
    @strawberry.mutation
    async def request_legal_signature_otp(self, info: strawberry.Info, email: str, name: str) -> bool:
        """
        Step 1: Frontend requests a secure OTP challenge.
        Generates the 6-digit code, caches it in Valkey, and dispatches the Google webhook email.
        """
        clean_email = email.lower().strip()
        
        try:
            # 1. Cryptographic Generation & Cache Lock
            otp_code = await generate_and_cache_signature_otp(clean_email)
            
            # 2. Async Network Dispatch via Google Apps Script
            await send_signature_otp_email(
                email=clean_email,
                recipient_name=name,
                otp_code=otp_code
            )
            
            return True
            
        except Exception as e:
            logger.error(f"[OTP REQUEST FAILED] Could not process request for {clean_email}: {str(e)}")
            # We raise a clean, non-revealing error to the frontend
            raise Exception("Failed to process signature request. Please try again later.")

    @strawberry.mutation
    async def execute_document_signature(
        self, 
        info: strawberry.Info, 
        email: str, 
        name: str, 
        otp_code: str, 
        ip_address: str
    ) -> DocumentSignatureResponse:
        """
        Step 2: Frontend submits the OTP challenge response.
        Verifies the cache, draws the PDF, applies the PKCS#7 seal, uploads to Supabase, and commits to Postgres.
        """
        clean_email = email.lower().strip()
        
        # Extract the AsyncSession injected dynamically via FastAPI/Strawberry context dependencies
        db: AsyncSession = info.context["db"]
        
        try:
            # 1. Cryptographic Validation (Raises OTPVerificationError if failed or expired)
            await verify_signature_otp(clean_email, otp_code)
            
            # 2. The PDF Generation, Sealing, & Cloud Streaming Engine
            pdf_metadata = await generate_and_seal_document(
                client_name=name,
                client_email=clean_email,
                ip_address=ip_address
            )
            
            # 3. Permanent Database Audit Record Generation
            new_signature = DocumentSignature(
                client_name=name,
                client_email=clean_email,
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
            # Safe failure state for incorrect/expired codes
            return DocumentSignatureResponse(
                status="error",
                message=str(e)
            )
        except Exception as e:
            # 4. Total Rollback Shield
            logger.critical(f"[EXECUTION FATAL] System failure executing signature for {clean_email}: {str(e)}")
            await db.rollback()
            return DocumentSignatureResponse(
                status="error",
                message="A critical infrastructure error occurred during document execution. No changes were saved."
            )
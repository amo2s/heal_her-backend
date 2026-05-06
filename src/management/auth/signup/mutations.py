import strawberry
from strawberry.types import Info
from fastapi import Request
# Changed from sqlalchemy.orm to sqlalchemy.ext.asyncio
from sqlalchemy.ext.asyncio import AsyncSession 

from core.config import settings
from .schemas import StaffSignUpInput, StaffSignUpResponse
from .services import StaffAuthService

@strawberry.type
class StaffAuthMutation:
    
    @strawberry.mutation
    async def register_staff_application(self, info: Info, input: StaffSignUpInput) -> StaffSignUpResponse:
        """
        The Sterile GraphQL Entry Point.
        - Enforces the cryptographic Handshake directly from the HTTP Context.
        - Wraps execution in a Silent Wall (Total Error Masking).
        - Delegates all database and cryptographic logic to the Air-Gapped Service Layer.
        """
        
        # =====================================================================
        # 1. THE HANDSHAKE SENTINEL (Perimeter Defense)
        # =====================================================================
        request: Request = info.context.get("request")
        if not request:
            raise Exception("Security Violation: Execution context breached.")
        
        client_handshake = request.headers.get("x-healher-handshake")
        
        if not client_handshake or client_handshake != settings.FRONTEND_HANDSHAKE_SECRET:
            raise Exception("Security Violation: Invalid Client Signature.")

        # =====================================================================
        # 2. TOTAL ERROR MASKING (The Black Hole)
        # =====================================================================
        try:
            # 3. RECURSIVE VALIDATION
            clean_input = input.validate_and_sanitize()
            
            # Updated to AsyncSession for asyncpg compatibility
            db: AsyncSession = info.context.get("db") 
            if not db:
                raise Exception("System Failure: Database Context Missing.")
                
            # 4. DELEGATION TO THE BRAIN
            # Service logic is awaited; errors are caught by the 'except' below.
            await StaffAuthService.create_pending_staff(
                db=db, 
                request=request, 
                payload=clean_input
            )
            
        except Exception:
            # THE BLACK HOLE:
            # We preserve your request for absolute silence. 
            # No errors leak, no hints given.
            pass 
        
        # =====================================================================
        # 5. THE MIRROR RESPONSE
        # =====================================================================
        # Your hard-coded False Positive logic. Every request gets a "Success" 
        # as far as the outside world is concerned.
        return StaffSignUpResponse()
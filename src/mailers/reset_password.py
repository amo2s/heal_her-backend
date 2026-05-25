import logging
import httpx

# central imports based on your heal her architecture
from core.config import settings
from core.exceptions import InfrastructureError

# strict internal import from your presentation layer
from mailers.templates.reset_otp import get_reset_otp_template

logger = logging.getLogger("HEAL_SECURITY")
logger.setLevel(logging.WARNING)

async def send_reset_otp_email(
    email: str, 
    recipient_name: str, 
    otp_code: str, 
    expiry_minutes: int = 10
) -> bool:
    """
    the independent http transport layer.
    fires the fortified html template to the google apps script engine asynchronously.
    """
    
    # 1. generate the pure html string from your presentation layer
    html_body = get_reset_otp_template(
        recipient_name=recipient_name, 
        otp_code=otp_code, 
        expiry_minutes=expiry_minutes
    )

    # 2. structure the payload exactly how the google apps script expects it
    payload = {
        "recipient": email,
        "subject": "Heal Her - Secure Authorization Code",
        "html_body": html_body
    }

    try:
        # 3. the async non-blocking network execution
        # added follow_redirects=True so google's 302 redirect doesn't crash the request
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.post(
                settings.GOOGLE_MAILER_WEBHOOK_URL, 
                json=payload,
                timeout=10.0  # strict limit bumped slightly for the redirect hop
            )
            
            # raise an exception if google returns a 4xx or 5xx status code
            response.raise_for_status()
            
            return True

    except httpx.RequestError as e:
        # 4. the absolute network fallback shield for connection drops
        logger.critical(f"[MAILER DROP] google apps script network failure: {str(e)}")
        raise InfrastructureError(
            internal_message="Email dispatch system is currently unreachable."
        )
    except httpx.HTTPStatusError as e:
        # 5. the fallback shield for when google rejects the payload
        logger.critical(f"[MAILER REJECTED] google script returned error status: {e.response.status_code}")
        raise InfrastructureError(
            internal_message="Email dispatch system rejected the payload."
        )
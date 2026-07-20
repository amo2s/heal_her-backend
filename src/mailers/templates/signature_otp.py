def get_signature_otp_template(recipient_name: str, otp_code: str, expiry_minutes: int) -> str:
    """
    Generates the strictly fortified HTML template for the digital signature OTP email.
    Uses safe inline CSS and table structures for cross-client compatibility.
    """
    # NOTE: If you have a logo URL later, you can swap it into an <img> tag below.
    # LOGO_URL = "https://your-domain.com/assets/logo.png"
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Heal Her - Secure Document Signature</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #0A051E; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
        
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #0A051E; padding: 40px 20px;">
            <tr>
                <td align="center">
                    
                    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #150D33; border-radius: 16px; overflow: hidden; border: 1px solid #2A1F55; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
                        
                        <tr>
                            <td align="center" style="padding: 30px 40px; border-bottom: 1px solid #2A1F55; background-color: #0F0926;">
                                <h1 style="margin: 0; color: #FFFFFF; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;">
                                    Heal <span style="color: #DA8CA0;">Her</span>
                                </h1>
                                <p style="margin: 8px 0 0 0; color: #8F8AA8; font-size: 11px; text-transform: uppercase; letter-spacing: 2px; font-weight: 600;">
                                    Legal Identity Verification
                                </p>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding: 40px;">
                                <p style="margin: 0 0 20px 0; color: #FFFFFF; font-size: 16px; font-weight: 600;">
                                    Hello {recipient_name},
                                </p>
                                <p style="margin: 0 0 30px 0; color: #B4AEDB; font-size: 15px; line-height: 1.6;">
                                    We received an initialization request to append your verified digital signature to the Heal Her Master Terms of Service Agreement. Please use the secure authorization code below to complete this transaction.
                                </p>

                                <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                    <tr>
                                        <td align="center" style="padding: 24px; background-color: #0A051E; border-radius: 12px; border: 1px dashed #DA8CA0;">
                                            <span style="font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 700; color: #DA8CA0; letter-spacing: 8px;">
                                                {otp_code}
                                            </span>
                                        </td>
                                    </tr>
                                </table>

                                <p style="margin: 30px 0 0 0; color: #B4AEDB; font-size: 14px; text-align: center;">
                                    This code will securely self-destruct in <strong style="color: #FFFFFF;">{expiry_minutes} minutes</strong>.
                                </p>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding: 30px 40px; background-color: #0F0926; border-top: 1px solid #2A1F55;">
                                <p style="margin: 0 0 10px 0; color: #DA8CA0; font-size: 13px; font-weight: 600; text-align: center;">
                                    Did not request this transaction?
                                </p>
                                <p style="margin: 0; color: #8F8AA8; font-size: 12px; line-height: 1.5; text-align: center;">
                                    If you did not initiate this legal agreement signature sequence, please completely ignore this transmission. No legal document will be executed or bound to your profile without this verification code challenge.
                                </p>
                            </td>
                        </tr>

                    </table>
                    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px;">
                        <tr>
                            <td align="center" style="padding: 20px 0;">
                                <p style="margin: 0; color: #5B547B; font-size: 11px;">
                                    &copy; 2026 Heal Her Platform. Automated Legal Security Transmission.
                                </p>
                            </td>
                        </tr>
                    </table>

                </td>
            </tr>
        </table>
    </body>
    </html>
    """
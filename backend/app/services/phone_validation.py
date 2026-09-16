"""Phone Number Validation - E.164 format validation for WhatsApp compliance.

Validates phone numbers for WhatsApp delivery (E.164 international format).
Uses phonenumbers library for validation and normalization.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import phonenumbers
except ImportError:
    logger.warning("[PhoneValidation] phonenumbers library not installed. Install with: pip install phonenumbers")
    phonenumbers = None


def is_valid_e164_format(phone: str) -> bool:
    """
    Check if phone is valid E.164 format: +{country}{number}.

    Args:
        phone: Phone number string to validate

    Returns:
        True if valid E.164 format, False otherwise
    """
    if not phone or not isinstance(phone, str):
        return False

    # E.164 format: starts with +, followed by 1-3 digit country code, then 4-14 digits
    if not phone.startswith("+"):
        return False

    # Remove + and check if all remaining characters are digits
    digits_only = phone[1:]
    if not digits_only.isdigit():
        return False

    # E.164 length: + (1) + country code (1-3) + number (4-14) = 6-18 chars total
    if len(phone) < 6 or len(phone) > 18:
        return False

    return True


def normalize_to_e164(phone: str, country_code: str = "US") -> str:
    """
    Convert phone to E.164 format. Raise ValueError if invalid.

    Args:
        phone: Phone number string (various formats accepted)
        country_code: ISO country code (e.g., 'US', 'UK', 'IN')

    Returns:
        Phone number in E.164 format (e.g., '+15551234567')

    Raises:
        ValueError: If phone number cannot be parsed or is invalid
    """
    if not phonenumbers:
        logger.error("[PhoneValidation] phonenumbers library not available")
        raise RuntimeError("phonenumbers library not installed")

    if not phone or not isinstance(phone, str):
        raise ValueError(f"Invalid phone: {phone}")

    try:
        # Parse phone number with country code context
        parsed = phonenumbers.parse(phone, country_code)

        # Validate the parsed number
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError(f"Invalid phone number: {phone} (parsed but validation failed)")

        # Format to E.164 standard
        e164_phone = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        logger.debug(f"[PhoneValidation] Normalized {phone} → {e164_phone}")
        return e164_phone

    except phonenumbers.NumberParseException as e:
        logger.warning(f"[PhoneValidation] Failed to parse phone {phone}: {e}")
        raise ValueError(f"Cannot parse phone number: {phone}") from e
    except Exception as e:
        logger.error(f"[PhoneValidation] Unexpected error normalizing phone: {e}")
        raise ValueError(f"Failed to normalize phone: {str(e)}") from e


def is_valid_for_whatsapp(phone: str) -> bool:
    """
    Check if phone can receive WhatsApp messages (E.164 format + valid number).

    Args:
        phone: Phone number string

    Returns:
        True if phone is valid for WhatsApp delivery, False otherwise
    """
    try:
        if not phonenumbers:
            logger.warning("[PhoneValidation] phonenumbers not available, basic validation only")
            return is_valid_e164_format(phone)

        # Validate E.164 format first
        if not is_valid_e164_format(phone):
            return False

        # Parse and validate using phonenumbers
        parsed = phonenumbers.parse(phone, None)
        is_valid = phonenumbers.is_valid_number(parsed)

        if not is_valid:
            logger.debug(f"[PhoneValidation] Phone {phone} is not valid for WhatsApp")

        return is_valid

    except Exception as e:
        logger.debug(f"[PhoneValidation] WhatsApp validation error for {phone}: {e}")
        return False

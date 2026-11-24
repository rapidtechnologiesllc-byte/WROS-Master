"""Addresses that are not a person.

A company distribution list (the all-staff list, employees@blitzenx.com) reaches everyone at
once. It is never a candidate, and the app never sends email to it: one automated message there
would go to the whole company. The list is configuration (settings.NON_PERSON_EMAILS).
"""
from typing import Iterable, Optional, Set

from app.core.config import settings


class NonPersonEmailError(ValueError):
    """Raised when an address that is not a person is used as a candidate or a recipient."""


def non_person_emails() -> Set[str]:
    return {e.strip().lower() for e in (settings.NON_PERSON_EMAILS or "").split(",") if e.strip()}


def is_non_person_email(address: Optional[str]) -> bool:
    return bool(address) and address.strip().lower() in non_person_emails()


def ensure_person_email(address: Optional[str], what: str = "This address") -> None:
    """NonPersonEmailError (a ValueError: never retried) for a distribution list."""
    if is_non_person_email(address):
        raise NonPersonEmailError(f"{what} {address} is a distribution list, not a person")


def person_recipients(addresses: Iterable[Optional[str]]) -> list:
    """The addresses that are a person (distribution lists removed), in order."""
    return [a for a in addresses if a and not is_non_person_email(a)]

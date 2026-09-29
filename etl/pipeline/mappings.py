"""Canonical value dictionaries (docs/etl_rules.md, rules A3-A4).

Raw values arrive in Spanish; the LATAM_Bank_Complete_Data_Dictionary defines the canonical English
domains. Silver stores the canonical value; a value outside key and domain is NOT silently kept: the
contract's isin check quarantines it (guard against future deliveries).

Three canonical values extend the organizer dictionary, which omits them although the data carries
them ("Muy Positivo", "Retención", video-call channel "Web"); they are marked TEAM_EXTENSIONS.
"""

from __future__ import annotations

# Null-like text treated as NULL everywhere (same set the profiling used).
NULL_TOKENS = ("none", "nan", "null", "n/a", "na", "-", "?", "undefined")

COUNTRIES = {"México": "Mexico"}

DOCUMENT_TYPES = {"Pasaporte": "Passport"}

PRODUCT_TYPES = {
    "Cuenta Corriente": "Checking Account",
    "Cuenta Ahorro": "Savings Account",
    "Tarjeta Crédito": "Credit Card",
    "Tarjeta Débito": "Debit Card",
    "Préstamo Personal": "Personal Loan",
    "Préstamo Hipotecario": "Mortgage",
    "Inversión": "Investment",
    "Seguro": "Insurance",  # dictionary truncates the list; Insurance is the evident translation
}

GEOGRAPHIC_ZONES = {"Urbana": "Urban", "Suburbana": "Suburban"}

REASON_CATEGORIES = {
    "Transaccional": "Transactional",
    "Producto": "Product",
    "Queja": "Complaint",
    "Técnico": "Technical",
    "Comercial": "Commercial",
    "Retención": "Retention",  # team extension
}

SENTIMENTS = {
    "Positivo": "Positive",
    "Negativo": "Negative",
    "Muy Negativo": "Very Negative",
    "Muy Positivo": "Very Positive",  # team extension
}

MAPPINGS: dict[str, dict[str, str]] = {
    "country": COUNTRIES,
    "document_type": DOCUMENT_TYPES,
    "product_type": PRODUCT_TYPES,
    "geographic_zone": GEOGRAPHIC_ZONES,
    "reason_category": REASON_CATEGORIES,
    "sentiment": SENTIMENTS,
}

TEAM_EXTENSIONS = ("Very Positive", "Retention", "Web")

def standardize_sql(column: str, mapping_name: str) -> str:
    """CASE expression translating a column to its canonical value (unmapped values pass through
    and are then caught by the contract's isin check)."""
    mapping = MAPPINGS[mapping_name]
    whens = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in mapping.items())
    return f"CASE {column} {whens} ELSE {column} END"


# Card brand from the BIN (same rules seed_demo.py uses); applied before product_number is dropped.
def card_brand_sql(number: str) -> str:
    return f"""CASE WHEN {number} IS NULL THEN NULL
        WHEN {number} LIKE '4%' THEN 'visa'
        WHEN regexp_matches({number}, '^(5[1-5]|222[1-9]|22[3-9]|2[3-6]|27[01]|2720)') THEN 'mastercard'
        WHEN regexp_matches({number}, '^3[47]') THEN 'amex'
        ELSE 'other' END"""

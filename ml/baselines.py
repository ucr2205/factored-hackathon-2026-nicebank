"""Frozen copy of the Phase 0 keyword stub (ml-service `keyword-stub-0`), kept as baseline B1.

ml/service/app.py no longer contains this logic once the trained model ships, so the baseline lives here to stay
reproducible in every MLflow comparison.

Library only, not run directly: ml/train.py imports `keyword_classify` (run it with `make train`).
"""

from __future__ import annotations

import re
import unicodedata

KEYWORDS: dict[str, list[str]] = {
    "unrecognized_charge": ["no reconozco", "no reconocido", "nao reconheco", "nao reconhecida",
                            "no hice", "nao fiz", "fraude", "no autorice", "nao autorizei"],
    "duplicate_charge": ["dos veces", "doble", "duplicado", "duas vezes", "cobrado dos", "cobraram duas"],
    "wrong_amount": ["monto incorrecto", "cobraron de mas", "valor errado", "cobraram a mais"],
    "not_received": ["no llego", "no recibi", "nao chegou", "nao recebi"],
    "atm_cash_not_dispensed": ["cajero", "no entrego", "caixa eletronico", "nao liberou"],
    "card_lost_stolen": ["robaron", "me robaron", "perdi mi tarjeta", "perdi la tarjeta", "roubaram",
                         "perdi meu cartao", "tarjeta robada", "cartao roubado", "extravie"],
    "out_of_scope": ["prestamo", "credito", "emprestimo", "inversion", "investimento"],
}
ABSTAIN_BELOW = 0.5


def normalize(text: str) -> str:
    """Lowercase, strip accents (NFKD combining marks) and collapse whitespace, as keyword-stub-0 did."""
    stripped = unicodedata.normalize("NFKD", text.lower())
    return re.sub(r"\s+", " ", "".join(c for c in stripped if not unicodedata.combining(c)))


def keyword_classify(text: str) -> tuple[str, float]:
    """Returns (label, confidence) exactly like keyword-stub-0."""
    norm = normalize(text)
    hits = {label: sum(kw in norm for kw in kws) for label, kws in KEYWORDS.items()}
    best, score = max(hits.items(), key=lambda kv: kv[1])
    if score == 0:
        return "other_in_scope", 0.0
    return best, min(0.5 + 0.2 * score, 0.9)

"""
Deterministic borrower-name normalization and similarity (Stage 9).

Used only to produce confirmation candidates. Never auto-assigns a loan.

Rules (offline, stdlib only):
  normalize(name)
    - strip, lowercase
    - collapse internal whitespace
    - drop punctuation (letters/digits/spaces kept)

  names_equal_normalized(a, b)
    - True when normalize(a) == normalize(b) and non-empty
    - This is a deterministic identity, not a "fuzzy" match

  names_are_similar(query, stored)
    - False if either side is empty or query normalize length < MIN_QUERY_LEN (3)
    - False if names_equal_normalized (caller should treat that as exact)
    - True when any of:
        1. Query tokens are an ordered prefix of stored tokens
           ("yash" → "yash gupta")
        2. Stored tokens are an ordered prefix of query tokens
        3. Same token multiset, 2+ tokens (safe reversal: "gupta yash")
        4. First tokens are similar (SequenceMatcher >= FIRST_TOKEN_RATIO)
           and query first token length >= MIN_QUERY_LEN
           ("pam" → "pammi", "yash" → "yash gupta")
        5. Full-string SequenceMatcher >= FULL_RATIO (0.86) AND first tokens
           share a 3-character prefix (blocks unrelated long strings)

Unrelated names (no shared first-token signal, low ratio) return False.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import List

MIN_QUERY_LEN = 3
FULL_RATIO = 0.86
FIRST_TOKEN_RATIO = 0.75
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalize_person_name(name: str) -> str:
    text = (name or "").strip().lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text


def name_tokens(name: str) -> List[str]:
    n = normalize_person_name(name)
    return n.split(" ") if n else []


def names_equal_normalized(left: str, right: str) -> bool:
    a = normalize_person_name(left)
    b = normalize_person_name(right)
    return bool(a) and a == b


def _token_prefix(shorter: List[str], longer: List[str]) -> bool:
    if not shorter or len(shorter) > len(longer):
        return False
    return all(s == l for s, l in zip(shorter, longer))


def names_are_similar(query: str, stored: str) -> bool:
    """
    Conservative similarity for assisted matching.

    Returns False for normalized-equal names so the caller can keep those
    on the deterministic path.
    """
    if names_equal_normalized(query, stored):
        return False

    nq = normalize_person_name(query)
    ns = normalize_person_name(stored)
    if len(nq) < MIN_QUERY_LEN or not ns:
        return False

    q_tokens = nq.split(" ")
    s_tokens = ns.split(" ")
    if not q_tokens or not s_tokens:
        return False

    if _token_prefix(q_tokens, s_tokens) or _token_prefix(s_tokens, q_tokens):
        return True

    if len(q_tokens) >= 2 and sorted(q_tokens) == sorted(s_tokens):
        return True

    q0, s0 = q_tokens[0], s_tokens[0]
    if len(q0) >= MIN_QUERY_LEN:
        token_ratio = SequenceMatcher(None, q0, s0).ratio()
        if token_ratio >= FIRST_TOKEN_RATIO:
            return True

    full_ratio = SequenceMatcher(None, nq, ns).ratio()
    if full_ratio >= FULL_RATIO and q0[:3] == s0[:3] and len(q0) >= MIN_QUERY_LEN:
        return True

    return False

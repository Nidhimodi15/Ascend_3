"""
Masking Utility — Sensitive Data Masking.

Masks sensitive transaction and account identifiers in audit logs and public responses
without obscuring the underlying verification results.
"""

def mask_id(identifier: str) -> str:
    """
    Mask transaction or account identifiers while preserving prefixes.
    Examples:
        "txn_48291" -> "txn_****"
        "acct_042"  -> "acct_***"
        "blk_1001"  -> "blk_****"
    """
    if not identifier:
        return identifier
    if "_" in identifier:
        parts = identifier.split("_", 1)
        prefix = parts[0]
        suffix = parts[1]
        masked_suffix = "*" * len(suffix)
        return f"{prefix}_{masked_suffix}"
    if len(identifier) <= 4:
        return "*" * len(identifier)
    return identifier[:2] + ("*" * (len(identifier) - 2))


def mask_txn_id(txn_id: str) -> str:
    return mask_id(txn_id)


def mask_key(key: str) -> str:
    return mask_id(key)

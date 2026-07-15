from __future__ import annotations

import hashlib
import re

from app.models.wallet_address import AddressFamily, NormalizedWalletAddress
from app.utils.keccak import keccak_256

_EVM_PATTERN = re.compile(r"^0x[0-9a-fA-F]{40}$")
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def detect_wallet_address(value: str) -> NormalizedWalletAddress | None:
    # Pasted whitespace is rejected: silently changing blockchain identifiers is
    # surprising and makes validation less strict.
    if value != value.strip():
        return None
    address = value
    if _EVM_PATTERN.fullmatch(address):
        body = address[2:]
        letters = [character for character in body if character.isalpha()]
        if letters and not (all(c.islower() for c in letters) or all(c.isupper() for c in letters)):
            digest = keccak_256(body.lower().encode("ascii")).hex()
            if any(character.isalpha() and character.isupper() != (int(digest[index], 16) >= 8)
                   for index, character in enumerate(body)):
                return None
        return NormalizedWalletAddress(address, address.lower(), AddressFamily.EVM)
    if _is_valid_tron(address):
        return NormalizedWalletAddress(address, address, AddressFamily.TRON)
    return None


def _is_valid_tron(address: str) -> bool:
    try:
        decoded = _base58_decode(address)
    except ValueError:
        return False
    if len(decoded) != 25 or decoded[0] != 0x41:
        return False
    payload, checksum = decoded[:-4], decoded[-4:]
    expected = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    return checksum == expected


def _base58_decode(value: str) -> bytes:
    if not value:
        raise ValueError("empty Base58 value")
    number = 0
    for character in value:
        index = _BASE58_ALPHABET.find(character)
        if index < 0:
            raise ValueError("invalid Base58 character")
        number = number * 58 + index
    body = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return b"\0" * (len(value) - len(value.lstrip("1"))) + body

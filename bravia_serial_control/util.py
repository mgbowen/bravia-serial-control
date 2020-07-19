from typing import Iterable


def dump_bytes_to_str(payload: Iterable[int]) -> str:
    return f'[{", ".join("0x{:02X}".format(b) for b in payload)}]'

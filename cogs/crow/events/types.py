from typing import NamedTuple


class Adjustment(NamedTuple):
    user_id: int
    adjustment: int
    note: str

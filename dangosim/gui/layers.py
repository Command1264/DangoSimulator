from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

BASE_PIECE_Z = 100.0
STACK_Z_STEP = 10.0
LABEL_Z_OFFSET = 1.0
SHADOW_Z_OFFSET = -1.0
HIGHLIGHT_Z_OFFSET = 2.0
STACK_OFFSET_Y = 17


@dataclass(frozen=True)
class PieceLayer:
    stack_index: int
    offset_y: int
    shadow_z: float
    piece_z: float
    label_z: float
    highlight_z: float


def build_piece_layers(
    *,
    positions: Mapping[str, int],
    stacks: Mapping[int, list[str]],
) -> dict[str, PieceLayer]:
    return {
        dango_id: _piece_layer(dango_id=dango_id, position=position, stacks=stacks)
        for dango_id, position in positions.items()
    }


def _piece_layer(
    *,
    dango_id: str,
    position: int,
    stacks: Mapping[int, list[str]],
) -> PieceLayer:
    stack = stacks.get(position, [])
    stack_index = stack.index(dango_id) if dango_id in stack else 0
    piece_z = BASE_PIECE_Z + stack_index * STACK_Z_STEP
    return PieceLayer(
        stack_index=stack_index,
        offset_y=-stack_index * STACK_OFFSET_Y,
        shadow_z=piece_z + SHADOW_Z_OFFSET,
        piece_z=piece_z,
        label_z=piece_z + LABEL_Z_OFFSET,
        highlight_z=piece_z + HIGHLIGHT_Z_OFFSET,
    )

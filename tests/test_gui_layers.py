from __future__ import annotations

from dangosim.gui.layers import build_piece_layers


def test_stacked_piece_layers_raise_top_pieces_visually_and_by_z_order() -> None:
    layers = build_piece_layers(
        positions={"bottom": 5, "middle": 5, "top": 5},
        stacks={5: ["bottom", "middle", "top"]},
    )

    assert layers["bottom"].offset_y == 0
    assert layers["middle"].offset_y < layers["bottom"].offset_y
    assert layers["top"].offset_y < layers["middle"].offset_y
    assert layers["bottom"].piece_z < layers["middle"].piece_z < layers["top"].piece_z
    assert layers["bottom"].label_z < layers["middle"].label_z < layers["top"].label_z


def test_piece_labels_and_highlights_are_above_piece_bodies() -> None:
    layers = build_piece_layers(
        positions={"bottom": 5, "top": 5},
        stacks={5: ["bottom", "top"]},
    )

    assert layers["bottom"].shadow_z < layers["bottom"].piece_z < layers["bottom"].label_z
    assert layers["top"].shadow_z < layers["top"].piece_z < layers["top"].label_z
    assert layers["top"].highlight_z > layers["top"].label_z


def test_unstacked_piece_uses_base_layer_values() -> None:
    layers = build_piece_layers(positions={"solo": 3}, stacks={3: ["solo"]})

    assert layers["solo"].stack_index == 0
    assert layers["solo"].offset_y == 0
    assert layers["solo"].piece_z == 100.0

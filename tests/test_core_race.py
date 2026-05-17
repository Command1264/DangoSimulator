from __future__ import annotations

from dangosim.core.models import DeviceType, DangoConfig, RaceConfig, TrackConfig
from dangosim.core.simulator import RaceSimulator


def make_config(*, length: int = 8, devices: dict[int, DeviceType] | None = None) -> RaceConfig:
    track = TrackConfig(length=length, finish=length, devices=devices or {})
    dangos = [
        DangoConfig(id="a", name="A", start_position=1),
        DangoConfig(id="b", name="B", start_position=1),
    ]
    return RaceConfig(track=track, dangos=dangos, seed=7)


def test_step_next_uses_one_randomized_action_order_per_round() -> None:
    config = RaceConfig(
        track=TrackConfig(length=20, finish=20),
        dangos=[
            DangoConfig(id="a", name="A", start_position=1),
            DangoConfig(id="b", name="B", start_position=2),
            DangoConfig(id="c", name="C", start_position=3),
        ],
        seed=1,
    )
    simulator = RaceSimulator(config)

    actors = [simulator.step_next().dango_id for _ in range(3)]

    assert set(actors) == {"a", "b", "c"}


def test_dangos_stack_when_they_land_on_the_same_cell_and_bottom_carries_top() -> None:
    simulator = RaceSimulator(make_config())

    simulator.step_dango("a", 2)
    simulator.step_dango("b", 2)
    simulator.step_dango("a", 1)

    snapshot = simulator.snapshot()
    assert snapshot.stacks[4] == ["a", "b"]
    assert snapshot.positions["a"] == 4
    assert snapshot.positions["b"] == 4


def test_advance_and_block_devices_trigger_only_on_landing_cell() -> None:
    simulator = RaceSimulator(
        make_config(devices={3: DeviceType.ADVANCE, 5: DeviceType.BLOCK})
    )

    first = simulator.step_dango("a", 2)
    second = simulator.step_dango("b", 4)

    assert first.to_position == 4
    assert first.device_triggered == DeviceType.ADVANCE
    assert second.to_position == 4
    assert second.device_triggered == DeviceType.BLOCK


def test_time_rift_reorders_stack_with_seeded_randomness() -> None:
    simulator = RaceSimulator(make_config(devices={3: DeviceType.TIME_RIFT}))

    simulator.step_dango("a", 2)
    simulator.step_dango("b", 2)

    snapshot = simulator.snapshot()
    assert set(snapshot.stacks[3]) == {"a", "b"}
    assert snapshot.event_log[-1].event_type == "time_rift"


def test_boss_runs_counter_clockwise_and_reverses_advance_block_devices() -> None:
    advance_as_block = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=8, finish=8, devices={7: DeviceType.ADVANCE}),
            dangos=[DangoConfig(id="boss", name="布大王", start_position=8, is_boss=True)],
            seed=3,
        )
    ).step_dango("boss", 1)
    block_as_advance = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=8, finish=8, devices={6: DeviceType.BLOCK}),
            dangos=[DangoConfig(id="boss", name="布大王", start_position=7, is_boss=True)],
            seed=3,
        )
    ).step_dango("boss", 1)

    assert advance_as_block.to_position == 8
    assert advance_as_block.device_triggered == DeviceType.ADVANCE
    assert block_as_advance.to_position == 5
    assert block_as_advance.device_triggered == DeviceType.BLOCK


def test_boss_enters_action_order_from_round_three() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=50, finish=50),
            dangos=[
                DangoConfig(id="a", name="A", start_position=1),
                DangoConfig(id="b", name="B", start_position=2),
                DangoConfig(id="boss", name="布大王", start_position=50, is_boss=True, ranked=False),
            ],
            seed=2,
        )
    )

    first_two_rounds = [simulator.step_next().dango_id for _ in range(4)]
    third_round = [simulator.step_next().dango_id for _ in range(3)]

    assert "boss" not in first_two_rounds
    assert "boss" in third_round


def test_boss_is_always_bottom_and_moves_without_carrying_regular_dangos() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=10, finish=10),
            dangos=[
                DangoConfig(id="a", name="A", start_position=5),
                DangoConfig(id="boss", name="布大王", start_position=10, is_boss=True, ranked=False),
            ],
            seed=2,
        )
    )

    simulator.step_dango("boss", 5)
    stacked = simulator.snapshot()
    assert stacked.stacks[5] == ["boss", "a"]

    simulator.step_dango("boss", 1)
    moved = simulator.snapshot()
    assert moved.positions["boss"] == 4
    assert moved.positions["a"] == 5
    assert moved.stacks[5] == ["a"]


def test_boss_returns_to_finish_after_round_when_separated_from_last_place() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=100, finish=100),
            dangos=[
                DangoConfig(id="a", name="A", start_position=1),
                DangoConfig(id="boss", name="布大王", start_position=100, is_boss=True, ranked=False),
            ],
            seed=4,
        )
    )

    for _ in range(4):
        simulator.step_next()

    snapshot = simulator.snapshot()
    assert snapshot.positions["boss"] == 100
    assert snapshot.event_log[-1].event_type == "boss_return"

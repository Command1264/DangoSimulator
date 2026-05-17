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

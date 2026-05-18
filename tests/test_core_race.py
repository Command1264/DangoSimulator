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
    assert actors == ["b", "c", "a"]


def test_round_start_event_log_uses_dango_names_not_ids() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=20, finish=20),
            dangos=[
                DangoConfig(id="lu", name="陸赫斯團子", start_position=1),
                DangoConfig(id="fei", name="菲比團子", start_position=2),
            ],
            seed=1,
        )
    )

    simulator.step_next()

    message = simulator.snapshot().event_log[0].message
    assert "陸赫斯團子" in message
    assert "菲比團子" in message
    assert "lu" not in message
    assert "fei" not in message


def test_initial_stack_order_is_randomized_with_seed() -> None:
    config = RaceConfig(
        track=TrackConfig(length=8, finish=8),
        dangos=[
            DangoConfig(id="a", name="A", start_position=1),
            DangoConfig(id="b", name="B", start_position=1),
            DangoConfig(id="c", name="C", start_position=1),
            DangoConfig(id="d", name="D", start_position=1),
        ],
        seed=0,
    )

    first = RaceSimulator(config).snapshot().stacks[1]
    second = RaceSimulator(config).snapshot().stacks[1]

    assert first == ["c", "a", "b", "d"]
    assert second == first


def test_initial_stack_shuffle_keeps_boss_at_bottom() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=8, finish=8),
            dangos=[
                DangoConfig(id="a", name="A", start_position=1),
                DangoConfig(id="boss", name="布大王", start_position=1, is_boss=True, ranked=False),
                DangoConfig(id="b", name="B", start_position=1),
            ],
            seed=0,
        )
    )

    assert simulator.snapshot().stacks[1][0] == "boss"


def test_initial_stack_order_override_arranges_same_cell_dangos_bottom_to_top() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=8, finish=8),
            dangos=[
                DangoConfig(id="a", name="A", start_position=1),
                DangoConfig(id="b", name="B", start_position=1),
                DangoConfig(id="c", name="C", start_position=1),
            ],
            seed=0,
            initial_stack_order={"a": 2, "b": 1},
        )
    )

    stack = simulator.snapshot().stacks[1]
    assert stack[:2] == ["b", "a"]
    assert set(stack) == {"a", "b", "c"}


def test_first_round_order_override_only_applies_to_first_round() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=30, finish=30),
            dangos=[
                DangoConfig(id="a", name="A", start_position=1),
                DangoConfig(id="b", name="B", start_position=2),
                DangoConfig(id="c", name="C", start_position=3),
            ],
            seed=1,
            first_round_order={"c": 1, "a": 2},
        )
    )

    first_round = [simulator.step_next().dango_id for _ in range(3)]
    second_round = [simulator.step_next().dango_id for _ in range(3)]

    assert first_round[:2] == ["c", "a"]
    assert second_round != ["c", "a", "b"]


def test_first_round_order_does_not_make_boss_act_before_round_three() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=50, finish=50),
            dangos=[
                DangoConfig(id="a", name="A", start_position=1),
                DangoConfig(id="boss", name="布大王", start_position=50, is_boss=True, ranked=False),
            ],
            seed=1,
            first_round_order={"boss": 1, "a": 2},
        )
    )

    first_two_rounds = [simulator.step_next().dango_id for _ in range(2)]
    third_round = [simulator.step_next().dango_id for _ in range(2)]

    assert first_two_rounds == ["a", "a"]
    assert "boss" in third_round


def test_snapshot_exposes_current_round_order_and_rolls_without_idle_boss() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=50, finish=50),
            dangos=[
                DangoConfig(id="a", name="A", start_position=1),
                DangoConfig(id="b", name="B", start_position=2),
                DangoConfig(id="boss", name="布大王", start_position=50, is_boss=True, ranked=False),
            ],
            seed=1,
            first_round_order={"b": 1, "a": 2, "boss": 3},
        )
    )

    simulator.step_next()
    first_round = simulator.snapshot()
    simulator.step_next()
    second_round = simulator.snapshot()
    simulator.step_next()
    simulator.step_next()
    simulator.step_next()
    third_round = simulator.snapshot()

    assert first_round.round_order == ("b", "a")
    assert set(first_round.round_rolls) == {"a", "b"}
    assert all(1 <= roll <= 3 for roll in first_round.round_rolls.values())
    assert first_round.remaining_round_order == ("a",)
    assert second_round.round_order == ("b", "a")
    assert second_round.remaining_round_order == ()
    assert "boss" in third_round.round_order
    assert 1 <= third_round.round_rolls["boss"] <= 6


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


def test_device_event_log_uses_device_names_not_values() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=8, finish=8, devices={3: DeviceType.ADVANCE, 6: DeviceType.BLOCK}),
            dangos=[DangoConfig(id="lu", name="陸赫斯團子", start_position=1)],
        )
    )

    simulator.step_dango("lu", 2)
    simulator.step_dango("lu", 2)

    messages = [event.message for event in simulator.snapshot().event_log if event.event_type == "device"]
    assert messages == ["陸赫斯團子 觸發 推進裝置", "陸赫斯團子 觸發 阻遏裝置"]


def test_time_rift_reorders_stack_with_seeded_randomness() -> None:
    simulator = RaceSimulator(make_config(devices={3: DeviceType.TIME_RIFT}))

    simulator.step_dango("a", 2)
    simulator.step_dango("b", 2)

    snapshot = simulator.snapshot()
    assert set(snapshot.stacks[3]) == {"a", "b"}
    assert snapshot.event_log[-1].event_type == "time_rift"


def test_live_rankings_use_progress_and_top_to_bottom_stack_order_before_finish() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=10, finish=10),
            dangos=[
                DangoConfig(id="a", name="A", start_position=8),
                DangoConfig(id="b", name="B", start_position=7),
                DangoConfig(id="c", name="C", start_position=7),
            ],
            seed=5,
        )
    )

    simulator.step_dango("b", 2)
    simulator.step_dango("c", 2)

    snapshot = simulator.snapshot()
    assert snapshot.finished is False
    assert snapshot.rankings == ()
    assert snapshot.live_rankings == ("c", "b", "a")


def test_first_ranked_dango_at_finish_ends_race_and_ranks_all_by_progress_then_stack_order() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=10, finish=10),
            dangos=[
                DangoConfig(id="a", name="A", start_position=8),
                DangoConfig(id="b", name="B", start_position=7),
                DangoConfig(id="c", name="C", start_position=7),
            ],
            seed=5,
        )
    )

    simulator.step_dango("b", 2)
    simulator.step_dango("c", 2)
    simulator.step_dango("a", 2)

    snapshot = simulator.snapshot()
    assert snapshot.finished is True
    assert snapshot.rankings == ("a", "c", "b")
    assert snapshot.live_rankings == snapshot.rankings


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
    round_events = [
        event for event in simulator.snapshot().event_log if event.event_type == "round_start"
    ]
    assert "boss" not in round_events[0].data["order"]
    assert "boss" not in round_events[1].data["order"]
    assert "boss" in round_events[2].data["order"]


def test_boss_picks_up_landed_regular_dango_and_keeps_carrying_it() -> None:
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
    assert moved.positions["a"] == 4
    assert moved.stacks[4] == ["boss", "a"]


def test_boss_inserts_newly_passed_dangos_between_boss_and_carried_stack() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=12, finish=12),
            dangos=[
                DangoConfig(id="carried", name="背上", start_position=10),
                DangoConfig(id="lower", name="下層", start_position=7),
                DangoConfig(id="upper", name="上層", start_position=7),
                DangoConfig(id="boss", name="布大王", start_position=12, is_boss=True, ranked=False),
            ],
            seed=2,
            initial_stack_order={"lower": 1, "upper": 2},
        )
    )

    simulator.step_dango("boss", 2)
    assert simulator.snapshot().stacks[10] == ["boss", "carried"]

    simulator.step_dango("boss", 4)
    snapshot = simulator.snapshot()
    assert snapshot.positions["boss"] == 6
    assert snapshot.positions["carried"] == 6
    assert snapshot.positions["lower"] == 6
    assert snapshot.positions["upper"] == 6
    assert snapshot.stacks[6] == ["boss", "lower", "upper", "carried"]


def test_boss_stays_after_round_when_carrying_regular_on_same_position() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=12, finish=12),
            dangos=[
                DangoConfig(id="a", name="A", start_position=9),
                DangoConfig(id="boss", name="布大王", start_position=12, is_boss=True, ranked=False),
            ],
            seed=4,
        )
    )

    simulator.step_dango("boss", 4)
    simulator._round_number = 3
    simulator._finish_round()

    snapshot = simulator.snapshot()
    assert snapshot.positions["boss"] == 8
    assert snapshot.positions["a"] == 8
    assert snapshot.stacks[8] == ["boss", "a"]
    assert all(event.event_type != "boss_return" for event in snapshot.event_log)


def test_boss_returns_to_finish_after_round_when_no_regular_remains_ahead_or_on_same_position() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=12, finish=12),
            dangos=[
                DangoConfig(id="a", name="A", start_position=9),
                DangoConfig(id="boss", name="布大王", start_position=8, is_boss=True, ranked=False),
            ],
            seed=4,
        )
    )

    simulator._round_number = 3
    simulator._finish_round()

    snapshot = simulator.snapshot()
    assert snapshot.positions["boss"] == 12
    assert snapshot.positions["a"] == 9
    assert snapshot.event_log[-1].event_type == "boss_return"


def test_boss_stays_when_regular_remains_ahead_before_finish_in_boss_direction() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=12, finish=12),
            dangos=[
                DangoConfig(id="a", name="A", start_position=6),
                DangoConfig(id="boss", name="布大王", start_position=12, is_boss=True, ranked=False),
            ],
            seed=4,
        )
    )

    simulator.step_dango("boss", 4)
    simulator._round_number = 3
    simulator._finish_round()

    snapshot = simulator.snapshot()
    assert snapshot.positions["boss"] == 8
    assert all(event.event_type != "boss_return" for event in snapshot.event_log)


def test_time_rift_keeps_boss_at_stack_bottom() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=10, finish=10, devices={5: DeviceType.TIME_RIFT}),
            dangos=[
                DangoConfig(id="a", name="A", start_position=5),
                DangoConfig(id="boss", name="布大王", start_position=10, is_boss=True, ranked=False),
            ],
            seed=1,
        )
    )

    simulator.step_dango("boss", 5)

    assert simulator.snapshot().stacks[5][0] == "boss"


def test_regular_dangos_roll_only_one_to_three() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=100, finish=100),
            dangos=[
                DangoConfig(id="a", name="A", start_position=1),
                DangoConfig(id="b", name="B", start_position=1),
                DangoConfig(id="boss", name="布大王", start_position=100, is_boss=True, ranked=False),
            ],
            seed=11,
        )
    )

    regular_rolls = [
        result.roll
        for result in (simulator.step_next() for _ in range(12))
        if result.dango_id != "boss"
    ]

    assert regular_rolls
    assert all(1 <= roll <= 3 for roll in regular_rolls)


def test_ranked_boss_is_hidden_from_live_rankings_until_round_three() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=100, finish=100),
            dangos=[
                DangoConfig(id="a", name="A", start_position=1),
                DangoConfig(id="b", name="B", start_position=1),
                DangoConfig(id="boss", name="布大王", start_position=100, is_boss=True, ranked=True),
            ],
            boss_ranked=True,
            seed=11,
        )
    )

    assert "boss" not in simulator.snapshot().live_rankings

    for _ in range(4):
        simulator.step_next()

    assert simulator.snapshot().round_number == 2
    assert "boss" not in simulator.snapshot().live_rankings

    simulator.step_next()

    assert simulator.snapshot().round_number == 3
    assert "boss" in simulator.snapshot().live_rankings


def test_ranked_boss_is_excluded_from_finish_rankings_before_round_three() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=10, finish=10),
            dangos=[
                DangoConfig(id="a", name="A", start_position=8),
                DangoConfig(id="boss", name="布大王", start_position=10, is_boss=True, ranked=True),
            ],
            boss_ranked=True,
            seed=3,
        )
    )

    simulator.step_dango("a", 2)

    assert simulator.snapshot().finished is True
    assert simulator.snapshot().rankings == ("a",)

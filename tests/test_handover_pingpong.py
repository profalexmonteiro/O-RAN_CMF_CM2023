import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import scripts.simulation as simulation


def make_user(serving_bs=0, allocated_prbs=5):
    return simulation.User(
        ue_id=1,
        x=0.0,
        y=0.0,
        speed=0.0,
        direction=0.0,
        profile_name="test",
        bitrate_bps=96e3,
        color="green",
        serving_bs=serving_bs,
        connected=True,
        allocated_prbs=allocated_prbs,
    )


def make_base_stations(count=3):
    base_stations = [
        simulation.BaseStation(bs_id=i + 1, x=float(i * 100), y=0.0)
        for i in range(count)
    ]
    return base_stations


class HandoverPingPongTest(unittest.TestCase):
    def setUp(self):
        self.sinr_patch = patch(
            "scripts.simulation.calculate_sinr_db",
            return_value=(20.0, [-60.0, -60.0, -60.0]),
        )
        self.prb_patch = patch(
            "scripts.simulation.required_prbs_for_user",
            return_value=10,
        )
        self.sinr_patch.start()
        self.prb_patch.start()

    def tearDown(self):
        self.prb_patch.stop()
        self.sinr_patch.stop()

    def test_handover_increments_once_and_moves_prbs(self):
        bs_list = make_base_stations()
        ue = make_user(serving_bs=0, allocated_prbs=5)
        bs_list[0].used_prbs = 5

        event = simulation.perform_handover(ue, bs_list, target_bs_idx=1, current_time=1.0)

        self.assertIsNotNone(event)
        self.assertEqual(ue.serving_bs, 1)
        self.assertEqual(ue.total_handovers, 1)
        self.assertEqual(ue.total_pingpongs, 0)
        self.assertEqual(bs_list[0].used_prbs, 0)
        self.assertEqual(bs_list[1].used_prbs, 10)
        self.assertEqual(list(bs_list[0].ho_events), [1.0])
        self.assertEqual(len(bs_list[0].pingpong_events), 0)

    def test_return_to_previous_bs_inside_pingpong_window_counts_pingpong(self):
        bs_list = make_base_stations()
        ue = make_user(serving_bs=0, allocated_prbs=5)
        bs_list[0].used_prbs = 5

        first = simulation.perform_handover(ue, bs_list, target_bs_idx=1, current_time=0.0)
        second = simulation.perform_handover(ue, bs_list, target_bs_idx=0, current_time=5.0)

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(ue.total_handovers, 2)
        self.assertEqual(ue.total_pingpongs, 1)
        self.assertIsNotNone(second["pingpong"])
        self.assertEqual(second["pingpong"]["current bs"], 1)
        self.assertTrue(math.isclose(second["pingpong"]["ho pp time"], 5.0))
        self.assertEqual(list(bs_list[1].ho_events), [5.0])
        self.assertEqual(list(bs_list[1].pingpong_events), [5.0])

    def test_return_to_previous_bs_after_pingpong_window_does_not_count_pingpong(self):
        bs_list = make_base_stations()
        ue = make_user(serving_bs=0, allocated_prbs=5)
        bs_list[0].used_prbs = 5

        simulation.perform_handover(ue, bs_list, target_bs_idx=1, current_time=1.0)
        event = simulation.perform_handover(
            ue,
            bs_list,
            target_bs_idx=0,
            current_time=1.0 + simulation.PINGPONG_PERIOD + 0.1,
        )

        self.assertIsNotNone(event)
        self.assertEqual(ue.total_handovers, 2)
        self.assertEqual(ue.total_pingpongs, 0)
        self.assertIsNone(event["pingpong"])
        self.assertEqual(len(bs_list[1].pingpong_events), 0)

    def test_failed_handover_does_not_increment_counters(self):
        bs_list = make_base_stations()
        ue = make_user(serving_bs=0, allocated_prbs=5)
        bs_list[0].used_prbs = 5

        with patch("scripts.simulation.required_prbs_for_user", return_value=simulation.TOTAL_PRBS_PER_BS + 1):
            event = simulation.perform_handover(ue, bs_list, target_bs_idx=1, current_time=1.0)

        self.assertIsNone(event)
        self.assertEqual(ue.serving_bs, 0)
        self.assertEqual(ue.total_handovers, 0)
        self.assertEqual(ue.total_pingpongs, 0)
        self.assertEqual(len(bs_list[0].ho_events), 0)
        self.assertEqual(len(bs_list[0].pingpong_events), 0)


if __name__ == "__main__":
    unittest.main()

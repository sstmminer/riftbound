import inspect
import unittest
from types import SimpleNamespace

from riftbound.engine import Action
from riftbound.gui import OriginsGUI


class GuiInteractionTests(unittest.TestCase):
    def _gui(self, *, phase="main", actor=0, actions=()):
        gui = object.__new__(OriginsGUI)
        gui.selected_mulligan = set()
        gui._opponent_job = None
        gui.env = SimpleNamespace(
            done=False,
            current_player=actor,
            observe=lambda _player: {
                "phase": phase,
                "hand": [{"id": "c1", "code": "OGN-001"}],
                "decision": ({"kind": "target", "targets": ["u1"]}
                              if phase == "decision" else None),
            },
            legal_actions=lambda: tuple(actions),
        )
        gui.notices = []
        gui.render_count = 0
        gui.set_notice = lambda text: gui.notices.append(text)
        gui.render = lambda: setattr(gui, "render_count", gui.render_count + 1)
        return gui

    def test_rune_click_is_blocked_during_non_accelerate_decision(self):
        gui = self._gui(phase="decision", actions=(Action.make("choose_target", target="u1"),))
        gui.rune_click("r1")
        self.assertEqual(gui.notices, [
            "当前正在选择目标，请左键点选合法目标；符文操作暂不可用。"
        ])

    def test_rune_click_is_blocked_during_other_priority_windows(self):
        gui = self._gui(phase="optional")
        gui.rune_click("r1")
        self.assertEqual(gui.notices, ["当前结算阶段不能直接操作符文。"])

    def test_stale_mulligan_click_after_turn_change_cannot_select_card(self):
        gui = self._gui(phase="main", actor=0)
        gui.mulligan_click("c1")
        self.assertEqual(gui.selected_mulligan, set())
        self.assertIn("调度阶段已经结束", gui.notices[-1])

    def test_mulligan_click_rejects_card_removed_from_hand(self):
        gui = self._gui(phase="mulligan", actor=0)
        gui.env.observe = lambda _player: {
            "phase": "mulligan", "hand": [{"id": "other", "code": "OGN-001"}],
        }
        gui.mulligan_click("c1")
        self.assertEqual(gui.selected_mulligan, set())
        self.assertIn("已经不在当前手牌", gui.notices[-1])

    def test_initial_driver_replaces_slow_stale_timer(self):
        gui = self._gui(phase="mulligan", actor=1)
        gui._opponent_job = "slow-timer"
        cancelled = []
        scheduled = []
        gui.after_cancel = lambda token: cancelled.append(token)
        gui.after = lambda delay, callback: scheduled.append((delay, callback)) or "fast-timer"
        gui._drive_initial_turn()
        self.assertEqual(cancelled, ["slow-timer"])
        self.assertEqual(gui._opponent_job, "fast-timer")
        self.assertEqual(scheduled[0][0], 1)

    def test_log_counter_is_initialized_before_first_render(self):
        source = inspect.getsource(OriginsGUI.__init__)
        self.assertLess(source.index("self._log_seq = 0"), source.index("self._build()"))


if __name__ == "__main__":
    unittest.main()

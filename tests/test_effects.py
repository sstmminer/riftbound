import unittest

from riftbound.effects import EffectRegistry, UnknownEffectError
from riftbound.origins import OriginsRules


class EffectRegistryTests(unittest.TestCase):
    def test_register_dispatch_and_sorted_names(self):
        registry = EffectRegistry()

        @registry.register("zeta")
        def zeta(state, item, rng):
            state["seen"] = item["value"]
            return True

        registry.register("alpha", lambda state, item, rng: False)
        state = {}
        self.assertEqual(registry.names(), ("alpha", "zeta"))
        self.assertTrue(registry.dispatch("zeta", state, {"value": 7}, None))
        self.assertEqual(state["seen"], 7)
        self.assertFalse(registry.dispatch("alpha", state, {}, None))

    def test_rejects_duplicates_unknown_and_non_boolean_handlers(self):
        registry = EffectRegistry()
        registry.register("draw", lambda state, item, rng: True)
        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register("draw", lambda state, item, rng: True)
        with self.assertRaisesRegex(UnknownEffectError, "unregistered effect"):
            registry.dispatch("discard", {}, {}, None)
        registry.register("bad", lambda state, item, rng: None)
        with self.assertRaisesRegex(TypeError, "must return bool"):
            registry.dispatch("bad", {}, {}, None)

    def test_origins_registers_all_current_chain_effects(self):
        rules = OriginsRules()
        self.assertEqual(
            rules.effects.names(),
            ("ahri_debuff", "buff_eight", "buff_self", "buff_self_three", "buff_target", "buff_two", "channel_one", "crackshot_target", "darius", "discard_one", "discard_two", "draw_one", "drummer", "fae_debuff", "fortified_shield", "kill_target", "leona_stun_target", "move_field_unit", "peak", "poro_herder", "ravenbloom", "ready_self", "ready_target", "reaver_recall_target", "return_field_unit", "return_unit", "return_unit_trigger", "riptide_damage", "solari_target", "spell", "sprite_mother", "stun_target", "viktor_innovator", "vision", "watcher_debuff", "yasuo_attack_target"),
        )


if __name__ == "__main__":
    unittest.main()


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
            ("adaptatron_conquer", "ahri_debuff", "albus_channel", "albus_optional", "apprentice_smith", "ava_attack", "baited_hook_finish", "blitz_move", "buff_another_on_move", "buff_eight", "buff_other_units_two", "buff_self", "buff_self_three", "buff_target", "buff_two", "channel_one", "counter", "crackshot_target", "darius", "dazzling_aurora_continue", "discard_one", "discard_one_draw_two", "discard_two", "draven_might", "draw_one", "drummer", "ember_hidden_buff", "fae_debuff", "fortified_shield", "ganking_target", "gear_armory_protect", "gear_baited_hook", "gear_buff_exhausted", "gear_buff_three", "gear_damage", "gear_debuff", "gear_draw", "gear_move", "gear_return", "harrowing_finish", "jinx_discard", "kadregrin_draw", "karma_recycle", "karthus_deathknell", "kill_small_enemy", "kill_small_unit_and_gold", "kill_target", "kinkou_buff", "legend_toggle", "leona_stun_target", "loyal_pup_defend", "lucian_attack", "mindsplitter", "move_field_unit", "optional_draw_or_buff", "optional_kill_cheap_gear", "optional_kill_gear", "optional_return_small_field_unit", "overzealous_fan_defend", "peak", "play_four_gold_gear", "play_sand_soldier", "poro_herder", "portal_rescue", "ravenbloom", "ready_another_friendly_mech", "ready_friendly_units", "ready_self", "ready_target", "reaver_recall_target", "return_field_unit", "return_friendly_enemy", "return_gear_from_trash", "return_unit", "return_unit_trigger", "riptide_damage", "sabotage", "snapvine_fight", "solari_target", "spell", "spirit_refuge", "sprite_mother", "stun_target", "teemo_defend", "tideturner_target", "twisted_fate", "vanguard_helm", "viktor_innovator", "vision", "volibear_attack", "watcher_debuff", "wildclaw_optional", "wildclaw_ready", "yasuo_attack_target", "yordle_explorer"),
        )


if __name__ == "__main__":
    unittest.main()


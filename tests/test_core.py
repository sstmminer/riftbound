from collections import Counter
from dataclasses import replace
import random
import unittest

from riftbound.core import (Card, Deck, DOMAINS, Pool, Rune, Scoreboard, Unit,
                           channel_count, damage_assignments, mulligan,
                           resolve_combat, setup_duel, validate_deck)
from riftbound.catalog import load_origins, require_supported
from riftbound.engine import RulesUnavailable
from riftbound.core import MovingUnit, draw_cards, standard_move


def fixture_deck():
    """Synthetic card metadata; no claims that this is a real playable deck."""
    body = frozenset({"body"})
    cards = {"legend": Card("legend", "Test legend", "legend", body, frozenset({"Test"})),
             "champ": Card("champ", "Test champion", "unit", body, frozenset({"Test"}), champion=True),
             "rune": Card("rune", "Test rune", "rune", body)}
    main = ["champ"]
    for i in range(13):
        key = f"u{i}"
        cards[key] = Card(key, f"Test unit {i}", "unit", body)
        main.extend([key]*3)
    for i in range(3):
        key = f"b{i}"
        cards[key] = Card(key, f"Test battlefield {i}", "battlefield")
    return Deck("legend", "champ", tuple(main), ("rune",)*12, ("b0", "b1", "b2")), cards


class ConstructionTests(unittest.TestCase):
    def test_103_valid_base_deck(self):
        deck, cards = fixture_deck()
        validate_deck(deck, cards)

    def test_103_copy_limit_counts_names_not_ids(self):
        deck, cards = fixture_deck()
        cards["alternate"] = replace(cards["u0"], id="alternate")
        with self.assertRaisesRegex(ValueError, "copy limit"):
            validate_deck(replace(deck, main=deck.main+("alternate",)), cards)

    def test_103_identity_requires_all_domains(self):
        deck, cards = fixture_deck()
        cards["u0"] = replace(cards["u0"], domains=frozenset({"body", "mind"}))
        with self.assertRaisesRegex(ValueError, "domain identity"):
            validate_deck(deck, cards)

    def test_103_champion_runes_battlefields_and_size(self):
        deck, cards = fixture_deck()
        invalid = [replace(deck, chosen_champion="u0"), replace(deck, runes=deck.runes[:11]),
                   replace(deck, main=deck.main[:39]), replace(deck, battlefields=("b0",)*3)]
        for candidate in invalid:
            with self.assertRaises(ValueError):
                validate_deck(candidate, cards)

    def test_103_signature_count_and_825_unique(self):
        deck, cards = fixture_deck()
        for key in ("u0", "u1"):
            cards[key] = replace(cards[key], signature=True, tags=frozenset({"Test"}))
        with self.assertRaisesRegex(ValueError, "signature"):
            validate_deck(deck, cards)
        _, cards = fixture_deck()
        cards["u0"] = replace(cards["u0"], unique=True)
        with self.assertRaisesRegex(ValueError, "copy limit"):
            validate_deck(deck, cards)

    def test_111_117_setup_preserves_counts_and_separate_decks(self):
        deck, cards = fixture_deck()
        state = setup_duel((deck, deck), cards, random.Random(42))
        self.assertEqual(state, setup_duel((deck, deck), cards, random.Random(42)))
        for player in state["players"]:
            self.assertEqual(len(player["hand"]), 4)
            self.assertEqual(len(player["main"]), 35)
            self.assertEqual(len(player["rune_deck"]), 12)
            self.assertEqual(Counter(player["main"]+player["hand"]+player["champion_zone"]), Counter(deck.main))
            self.assertIn(player["battlefield"], deck.battlefields)

    def test_117_replacements_before_random_bottom_recycle(self):
        hand, main = ["a", "b", "c", "d"], ["e", "f", "g", "h"]
        new_hand, new_main = mulligan(hand, main, (0, 3), random.Random(4))
        self.assertEqual(new_hand, ["b", "c", "e", "f"])
        self.assertEqual(new_main[:2], ["g", "h"])
        self.assertCountEqual(new_main[2:], ["a", "d"])
        self.assertEqual(hand, ["a", "b", "c", "d"])
        self.assertEqual(mulligan(hand, main, (), random.Random(4)), (hand, main))
        for slots in ((0, 1, 2), (0, 0), (-1,), (4,)):
            with self.assertRaises(ValueError):
                mulligan(hand, main, slots, random.Random(4))


class ResourceTests(unittest.TestCase):
    def test_164_can_exhaust_then_recycle_same_rune(self):
        rune = Rune("r", "body")
        board, deck, pool = [rune], [], Pool()
        pool.exhaust_basic(rune)
        with self.assertRaises(ValueError):
            pool.exhaust_basic(rune)
        pool.recycle_basic("r", board, deck)
        self.assertEqual((pool.energy, pool.power), (1, ["body"]))
        self.assertFalse(board)
        self.assertFalse(deck[0].exhausted)

    def test_135_445_payment_choices_are_explicit_and_atomic(self):
        pool = Pool(2, ["body", "calm", "any"])
        with self.assertRaisesRegex(ValueError, "mismatch"):
            pool.pay(1, (frozenset({"body"}),), (1,))
        self.assertEqual((pool.energy, pool.power), (2, ["body", "calm", "any"]))
        pool.pay(1, (frozenset({"body", "chaos"}), frozenset({"fury"})), (0, 2))
        self.assertEqual((pool.energy, pool.power), (1, ["calm"]))
        pool.pay(0, (DOMAINS,), (0,))
        pool.empty()
        self.assertEqual((pool.energy, pool.power), (0, []))

    def test_315_487_second_player_first_turn(self):
        self.assertEqual(channel_count(first_turn=True, second_player=True, available=12), 3)
        self.assertEqual(channel_count(first_turn=True, second_player=False, available=12), 2)
        self.assertEqual(channel_count(first_turn=False, second_player=True, available=12), 2)
        self.assertEqual(channel_count(first_turn=True, second_player=True, available=1), 1)


class ScoringTests(unittest.TestCase):
    def test_472_once_per_player_per_battlefield_per_turn(self):
        score = Scoreboard()
        self.assertEqual(score.score(0, 0, method="hold"), "point")
        self.assertEqual(score.score(0, 0, method="conquer"), "already_scored")
        self.assertEqual(score.points, [1, 0])
        score.new_turn()
        self.assertEqual(score.score(0, 0, method="hold"), "point")

    def test_473_final_conquer_draws_unless_all_fields_scored(self):
        score = Scoreboard(points=[7, 0])
        self.assertEqual(score.score(0, 0, method="conquer"), "draw")
        self.assertIsNone(score.winner_at_cleanup())
        self.assertEqual(score.score(0, 1, method="conquer"), "point")
        self.assertEqual(score.winner_at_cleanup(), 0)

    def test_473_final_hold_unrestricted_and_474_tie_not_win(self):
        score = Scoreboard(points=[7, 0])
        self.assertEqual(score.score(0, 0, method="hold"), "point")
        self.assertEqual(score.winner_at_cleanup(), 0)
        self.assertIsNone(Scoreboard(points=[8, 8]).winner_at_cleanup())


class DrawAndMovementTests(unittest.TestCase):
    def test_414_draw_exactly_deck_size_does_not_burn_out(self):
        result = draw_cards(("a", "b"), (), 2, player=0, points=(0, 0), rng=random.Random(3))
        self.assertEqual(result.drawn, ("a", "b"))
        self.assertEqual(result.burnouts, 0)

    def test_432_recycle_trash_give_opponent_point_continue_draw(self):
        result = draw_cards(("a",), ("b", "c"), 3, player=0, points=(0, 0), rng=random.Random(3))
        self.assertCountEqual(result.drawn, ("a", "b", "c"))
        self.assertEqual(result.points, (0, 1))
        self.assertEqual(result.burnouts, 1)
        self.assertIsNone(result.immediate_winner)

    def test_432_empty_deck_and_trash_repeated_burnout_ends_without_loop(self):
        result = draw_cards((), (), 1, player=0, points=(0, 0), rng=random.Random(3))
        self.assertEqual(result.points, (0, 8))
        self.assertEqual(result.immediate_winner, 1)
        self.assertEqual(result.burnouts, 8)
        self.assertEqual(result.drawn, ())

    def test_432_first_burnout_no_immediate_win_second_can_win(self):
        result = draw_cards((), (), 1, player=0, points=(0, 7), rng=random.Random(3))
        self.assertEqual(result.points, (0, 9))
        self.assertEqual(result.burnouts, 2)

    def test_144_group_move_same_destination_exhausts_simultaneously(self):
        units = (MovingUnit("a", 0, "base:0", False), MovingUnit("b", 0, "base:0", False))
        moved = standard_move(units, ("a", "b"), player=0, destination="battlefield:0", neutral_open_main=True)
        self.assertTrue(all(u.exhausted and u.location == "battlefield:0" for u in moved))
        self.assertTrue(all(u.location == "base:0" for u in units))

    def test_144_return_from_different_fields_to_same_base(self):
        units = (MovingUnit("a", 0, "battlefield:0", False), MovingUnit("b", 0, "battlefield:1", False))
        moved = standard_move(units, ("a", "b"), player=0, destination="base:0", neutral_open_main=True)
        self.assertTrue(all(u.location == "base:0" for u in moved))

    def test_144_invalid_timing_destination_controller_or_exhaustion(self):
        unit = MovingUnit("a", 0, "battlefield:0", False)
        for units, destination, timing in [((unit,), "battlefield:1", True),
                                          ((unit,), "base:0", False),
                                          ((replace(unit, exhausted=True),), "base:0", True),
                                          ((replace(unit, controller=1),), "base:0", True)]:
            with self.assertRaises(ValueError):
                standard_move(units, ("a",), player=0, destination=destination, neutral_open_main=timing)


class CombatTests(unittest.TestCase):
    def test_142_zero_might_needs_nonzero_damage(self):
        self.assertFalse(Unit("zero", 0).lethal)
        self.assertTrue(Unit("zero", 0, 1).lethal)
        self.assertFalse(Unit("negative", -3).lethal)

    def test_467_rulebook_five_damage_four_three_might_example(self):
        targets = tuple(Unit(str(i), 3) for i in range(4))
        assignments = damage_assignments(5, targets)
        self.assertEqual(len(assignments), 12)
        self.assertNotIn((2, 1, 1, 1), assignments)
        self.assertTrue(all(sorted(a) == [0, 0, 2, 3] for a in assignments))

    def test_467_existing_damage_changes_lethal_and_overkill(self):
        targets = (Unit("a", 3, 1), Unit("b", 3, 1))
        self.assertEqual(damage_assignments(3, targets), ((1, 2), (2, 1)))
        self.assertEqual(damage_assignments(5, targets), ((2, 3), (3, 2)))

    def test_467_simultaneous_damage_and_double_death(self):
        result = resolve_combat((Unit("a", 3),), (Unit("d", 3),), (3,), (3,))
        self.assertCountEqual(result.killed, ("a", "d"))
        self.assertEqual(result.result, "no_result")

    def test_468_survivors_heal_and_attackers_recall_if_defender_survives(self):
        result = resolve_combat((Unit("a", 5),), (Unit("d1", 3), Unit("d2", 3)), (3, 2), (6,))
        self.assertEqual(result.result, "defender")
        self.assertEqual(result.defender_survivors, (Unit("d2", 3),))
        # Zero Might attacker contributes no damage; both sides survive and recall.
        result = resolve_combat((Unit("a", 0),), (Unit("d", 0),), (0,), (0,))
        self.assertEqual(result.recalled, ("a",))
        self.assertEqual(result.result, "no_result")

    def test_467_illegal_split_fails(self):
        with self.assertRaisesRegex(ValueError, "allocation"):
            resolve_combat((Unit("a", 2),), (Unit("d1", 2), Unit("d2", 2)), (1, 1), (4,))


class CatalogTests(unittest.TestCase):
    def test_catalog_has_298_unique_base_cards_no_showcase_duplicates(self):
        cards = load_origins()
        self.assertEqual(len(cards), 298)
        self.assertEqual(len({c["name"] for c in cards}), 298)

    def test_catalog_does_not_imply_play_support(self):
        with self.assertRaises(RulesUnavailable):
            require_supported(("OGN-002",))
        with self.assertRaises(ValueError):
            require_supported(("invented",))

class GearZoneTests(unittest.TestCase):
    def test_gear_enters_exhausted_and_resource_ability_is_explicit(self):
        from riftbound.core import GearZone
        card = Card("seal", "Seal of Rage", "gear", frozenset({"fury"}))
        zone, pool = GearZone(), Pool()
        gear = zone.play(card, controller=0, resource_domain="fury")
        self.assertTrue(gear.exhausted)
        zone.ready("seal", controller=0)
        zone.activate_resource("seal", controller=0, pool=pool)
        self.assertEqual(pool.power, ["fury"])
        with self.assertRaisesRegex(ValueError, "already exhausted"):
            zone.activate_resource("seal", controller=0, pool=pool)

    def test_gear_kill_moves_to_trash_and_checks_controller(self):
        from riftbound.core import GearZone
        card = Card("g", "Test Gear", "gear")
        zone = GearZone()
        zone.play(card, controller=0)
        with self.assertRaises(ValueError):
            zone.kill("g", controller=1)
        self.assertEqual(zone.kill("g", controller=0), "g")
        self.assertEqual(zone.trash, ["g"])

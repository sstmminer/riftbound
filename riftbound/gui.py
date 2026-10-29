"""Local card-table client for the executable Origins subset.

The table is deliberately a thin view over :class:`OriginsRules`: every
button, drag, and context-menu entry is created from a legal engine action.
Card art is bundled at a small display resolution so the client works offline.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .engine import Environment, InvalidAction
from .origins import OriginsRules
from .policies import GreedyPolicy
from .support import (complex_test_deck, cost_abilities_deck, daughter_deck,
                      repeat_targets_deck, replay_windows_deck, resource_and_gear_deck,
                      reveal_targets_deck, starter_deck, vision_deck)


IMAGE_ROOT = Path(__file__).with_name("data") / "images"
BACK_CODE = "__back__"


class OriginsGUI(tk.Tk):
    """A compact dark card table with private hand information for player 0."""

    def __init__(self, *, seed=42, opponent="greedy", variant="starter", extra_fields=()):
        super().__init__()
        self.title("Riftbound Origins · 自动对战与结算")
        self.geometry("1600x1300")
        self.minsize(1200, 900)
        self.configure(bg="#0e1725")
        self.variant = variant
        # extra_fields is an engine/testing hook. There is intentionally no
        # manual "add battlefield" control: effects and rules own the board.
        self.extra_fields = list(extra_fields)
        self.rules = OriginsRules(self._decks(), extra_fields=self.extra_fields)
        self.env = Environment(self.rules, max_steps=3000)
        self.env.reset(seed=seed)
        self.seed = seed
        self.opponent = GreedyPolicy() if opponent == "greedy" else None
        self.drag_card = None
        self._mulligan_press_uid = None
        self.selected_units = set()
        self.selected_mulligan = set()
        # Ordered target clicks are kept locally until the player confirms.
        # A list is required for effects such as Falling Star and Icathian
        # Rain where the same unit may be chosen more than once.
        self.selected_decision_targets = []
        self.labels = {}
        self._photo_cache = {}
        self._high_photo_cache = {}
        self._hover_job = None
        self._preview = None
        self._decision_signature = None
        self._reveal_window = None
        self._target_window = None
        self._opponent_job = None
        self._winner_announced = False
        self._build()
        self.render()
        # Drive an opponent-first opening mulligan immediately.  Without an
        # idle callback Tk can leave the first private setup decision dormant
        # until another UI event (which made Restart appear to fix it).
        self.after_idle(self._drive_initial_turn)

    def _drive_initial_turn(self):
        if (self._opponent_job is None and not self.env.done
                and self.env.current_player != 0):
            self._opponent_job = self.after(1, self.opponent_step)

    # ---------- window and layout ----------

    def _build(self):
        toolbar = tk.Frame(self, bg="#101b2b", padx=10, pady=7)
        toolbar.pack(fill="x")
        self.status = tk.Label(toolbar, text="", anchor="w", bg="#101b2b", fg="#edf4ff",
                               font=("TkDefaultFont", 13, "bold"))
        self.status.pack(side="left", fill="x", expand=True)
        self.hint = tk.Label(toolbar, text="", anchor="e", bg="#101b2b", fg="#9fb4ce")
        self.hint.pack(side="left", padx=12)
        ttk.Button(toolbar, text="规则/范围", command=self.show_scope).pack(side="right", padx=3)
        ttk.Button(toolbar, text="重新开始", command=self.restart).pack(side="right", padx=3)
        self.variant_box = ttk.Combobox(toolbar, state="readonly", width=10,
                                        values=("starter", "vision", "daughter", "complex", "repeat", "replay", "cost", "resources", "reveal"))
        self.variant_box.set(self.variant)
        self.variant_box.pack(side="right", padx=5)

        self.board = tk.Frame(self, bg="#0e1725")
        self.board.pack(fill="both", expand=True, padx=8, pady=4)
        self.board.grid_propagate(False)
        self.board.grid_columnconfigure(0, weight=1)
        self.board.grid_columnconfigure(1, weight=0, minsize=220)
        # Keep the three table bands compact and predictable.  In particular,
        # the battlefield must not absorb every spare pixel on a tall window;
        # that made the two player areas look detached from the table.  The
        # top and bottom rows share any modest extra height, while the middle
        # row stays at the intended battlefield size.
        self.board.grid_rowconfigure(0, weight=1, minsize=345)
        self.board.grid_rowconfigure(1, weight=0, minsize=390)
        self.board.grid_rowconfigure(2, weight=1, minsize=330)
        self._panel("opponent", "对手区域 / Opponent", 0, height=345)
        self._panel("battlefields", "战场区 / Battlefields", 1, height=390)
        self._panel("player", "我方区域 / Player", 2, height=330)
        self._panel("chain", "结算链 / Chain", 0, column=1, height=360)
        self._panel("banishment", "放逐区 / Banishment", 1, column=1, rowspan=2, height=900)

        bottom = tk.Frame(self, bg="#101b2b", padx=8, pady=5)
        bottom.pack(fill="x")
        self.state_bar = tk.Label(bottom, text="", anchor="w", justify="left",
                                  bg="#17263a", fg="#dbe8f7", padx=8, pady=4)
        self.state_bar.pack(fill="x")
        self.actions = tk.Frame(bottom, bg="#101b2b")
        self.actions.pack(fill="x")
        self.log = tk.Text(bottom, height=7, state="disabled", wrap="word",
                           bg="#111d2d", fg="#d6e3f5", insertbackground="white")
        self.log.pack(fill="x", pady=(5, 0))

    def _panel(self, key, title, row, *, column=0, rowspan=1, height):
        frame = tk.LabelFrame(self.board, text=title, fg="#dce9fb", bg="#1b2a3e",
                              padx=6, pady=5, height=height)
        frame.grid(row=row, column=column, rowspan=rowspan, sticky="nsew", padx=3, pady=3)
        frame.grid_propagate(False)
        frame.pack_propagate(False)
        body = tk.Frame(frame, bg="#1b2a3e")
        body.pack(fill="both", expand=True)
        frame._body = body
        self.labels[key] = frame
        return frame

    def _clear(self, key):
        body = self.labels[key]._body
        for child in body.winfo_children():
            child.destroy()
        return body

    def _subzone(self, parent, title, *, width=None, height=None):
        frame = tk.LabelFrame(parent, text=title, fg="#c9d8ed", bg="#24364d",
                              padx=4, pady=3)
        if width is not None:
            frame.configure(width=width)
        if height is not None:
            frame.configure(height=height)
        if width is not None or height is not None:
            frame.pack_propagate(False)
        return frame

    # ---------- card art ----------

    def _photo(self, code, factor=3, *, horizontal=False):
        key = (code, factor, horizontal)
        if key in self._photo_cache:
            return self._photo_cache[key]
        suffix = "-horizontal" if horizontal and code != BACK_CODE else ""
        path = IMAGE_ROOT / "card-back.png" if code == BACK_CODE else IMAGE_ROOT / "OGN" / f"{code}{suffix}.png"
        try:
            image = tk.PhotoImage(file=str(path))
        except tk.TclError:
            fallback = IMAGE_ROOT / "OGN" / f"{code}.png" if code != BACK_CODE else IMAGE_ROOT / "card-back.png"
            image = tk.PhotoImage(file=str(fallback))
        if factor > 1:
            image = image.subsample(factor, factor)
        self._photo_cache[key] = image
        return image

    def _high_photo(self, code):
        if code in self._high_photo_cache:
            return self._high_photo_cache[code]
        path = IMAGE_ROOT / "high" / f"{code}.png"
        try:
            image = tk.PhotoImage(file=str(path))
        except tk.TclError:
            image = self._photo(code, 2)
        else:
            # Keep the original source ratio while fitting a desktop preview.
            image = image.subsample(2, 2)
        self._high_photo_cache[code] = image
        return image

    def _card_name(self, code):
        return self.rules.cards.get(code, {}).get("name", code)

    def _unit_status_label(self, unit, *, pending=0):
        """Return a compact, explicit status readout for a unit card.

        The card art remains the source of truth for identity.  These markers
        expose transient rules state that is otherwise easy to miss when the
        card is exhausted or displayed in a compact battlefield row.
        """
        markers = ["横置" if unit.get("exhausted") else "就绪"]
        temporary = unit.get("temporary", 0)
        if temporary:
            markers.append(f"临时战力 {'+' if temporary > 0 else ''}{temporary}")
        if unit.get("damage", 0):
            markers.append(f"伤害 {unit['damage']}")
        if pending:
            markers.append(f"待分配 {pending}")
        if unit.get("buff", 0):
            markers.append(f"增益 {unit['buff']}")
        if unit.get("assault", 0):
            markers.append(f"强攻 {unit['assault']}")
        if unit.get("combat_shield", 0):
            markers.append(f"护盾 {unit['combat_shield']}")
        if unit.get("stunned"):
            markers.append("眩晕")
        if unit.get("temporary_ganking"):
            markers.append("Ganking")
        if unit.get("temporary_unit"):
            markers.append("临时单位")
        head = f"P{unit['owner']} · 战力 {unit.get('might', '?')}"
        return head + ("\n" + " · ".join(markers) if markers else "")

    def _image_card(self, parent, code, *, uid=None, zone=None, owner=None, factor=3,
                    private=False, compact_label=None, click=True, exhausted=False,
                    selected=False, pack=True, show_label=True, field=None):
        if uid is not None and uid in self.selected_decision_targets:
            selected = True
        wrapper = tk.Frame(parent, bg="#f4c542" if selected else "#24364d",
                           padx=4 if selected else 2, pady=4 if selected else 2)
        if pack:
            wrapper.pack(side="left", padx=2, pady=2, anchor="n")
        image = self._photo(BACK_CODE if private else code, factor, horizontal=exhausted)
        # Card frames stay black like the physical cards; gold is reserved for
        # the selected-unit highlight.
        color = "#111111"
        button = tk.Button(wrapper, image=image, relief="raised", bd=2,
                           bg=color, activebackground="#f6d78b", cursor="hand2",
                           highlightthickness=3 if selected else 1,
                           highlightbackground="#f4c542" if selected else color,
                           highlightcolor="#f4c542" if selected else color)
        button.pack()
        label = compact_label or (self._card_name(code) if code != BACK_CODE else "牌背")
        if show_label and label:
            tk.Label(wrapper, text=label, bg="#24364d", fg="#e9f1fc",
                     font=("TkDefaultFont", 8), wraplength=110).pack(fill="x")
        button.bind("<Enter>", lambda _event, c=code: self._arm_preview(button, c))
        button.bind("<Leave>", lambda _event: self._cancel_preview())
        if click:
            decision = self.env.observe(0).get("decision") if self.env.current_player == 0 else None
            if decision and decision.get("kind") == "field" and field is not None:
                def select_decision_field(event, index=field):
                    self._decision_field_click(index)
                    return "break"
                button.bind("<Button-1>", select_decision_field)
                wrapper.bind("<Button-1>", select_decision_field)
            elif uid is not None and decision and self.env.observe(0)["phase"] == "decision":
                # Stop the image-button event before it can bubble into the
                # wrapper handler.  Both bindings are kept so clicking the
                # card label or its image uses the same target path, but one
                # physical click is always processed exactly once.
                def select_decision_target(event, u=uid):
                    self._decision_target_click(u)
                    return "break"
                button.bind("<Button-1>", select_decision_target)
                wrapper.bind("<Button-1>", select_decision_target)
            elif uid is not None and (zone == "hand" and self.env.current_player == 0
                  and self.env.observe(0)["phase"] == "mulligan"):
                # Use the button command for the opening hand. Rebuilding the
                # fan during a ButtonPress binding can destroy the widget
                # before Tk delivers ButtonRelease, which made the first
                # launch appear unresponsive until Restart.
                button.configure(command=lambda u=uid: self.mulligan_click(u))
            elif uid is not None:
                if zone == "gear":
                    button.bind("<Button-1>", lambda event, u=uid: self.card_menu(event, u))
                else:
                    button.bind("<ButtonPress-1>", lambda event, u=uid: self.start_drag(event, u, zone))
                    button.bind("<ButtonRelease-1>", lambda event, u=uid: self.end_drag(event, u, zone))
                button.bind("<Button-3>", lambda event, u=uid: self.card_menu(event, u))
                if zone == "hand":
                    # The wrapper catches the opening hand click as well as the
                    # image button, which avoids losing the first mulligan click
                    # when the fan is rebuilt during initial rendering.
                    wrapper.bind("<Button-1>", lambda event, u=uid: self.start_drag(event, u, zone))
        return wrapper

    def _stack(self, parent, cards, *, owner=None, title="", limit=4, factor=4,
               count=None, collapse=False):
        frame = self._subzone(parent, title)
        frame.pack(side="left", fill="y", padx=3)
        cards = list(cards)
        if not cards:
            self._image_card(frame, BACK_CODE, factor=factor, compact_label="空")
        elif collapse:
            # Keep the pile compact on the table.  The exposed top card and
            # its wrapper both receive the click binding because the image
            # button consumes mouse events before they bubble to the frame.
            wrapper = self._image_card(
                frame, cards[-1]["code"], owner=owner, factor=factor,
                compact_label=self._card_name(cards[-1]["code"]), click=False)
            callback = lambda _event, p=owner: self._show_trash_popup(p)
            wrapper.bind("<Button-1>", callback)
            for child in wrapper.winfo_children():
                child.bind("<Button-1>", callback, add="+")
        else:
            for card in cards[-limit:]:
                self._image_card(frame, card["code"], owner=owner, factor=factor,
                                 compact_label=self._card_name(card["code"]), click=False)
        shown_count = len(cards) if count is None else count
        tk.Label(frame, text=f"{shown_count} 张", bg="#24364d", fg="#d6e3f5").pack()
        return frame

    def _show_trash_popup(self, owner):
        """Show the complete public discard pile in a scrollable window."""
        obs = self.env.observe(0)
        cards = list(obs["players"][owner]["trash"])
        popup = tk.Toplevel(self)
        popup.title(f"P{owner} 弃牌堆 / Trash · {len(cards)} 张")
        popup.geometry("980x700")
        popup.transient(self)
        header = tk.Label(popup, text=f"P{owner} 弃牌堆（顶部在最前）· 共 {len(cards)} 张",
                          anchor="w", padx=8, pady=5)
        header.pack(fill="x")
        body = ttk.Frame(popup)
        body.pack(fill="both", expand=True)
        canvas = tk.Canvas(body, bg="#101b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg="#101b2b")
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        if not cards:
            tk.Label(inner, text="弃牌堆为空", bg="#101b2b", fg="#dbe8f7").grid(
                row=0, column=0, padx=20, pady=20)
        else:
            for index, card in enumerate(reversed(cards)):
                wrapper = self._image_card(
                    inner, card["code"], factor=3,
                    compact_label=("顶部 · " if index == 0 else "") + self._card_name(card["code"]),
                    click=False, pack=False)
                wrapper.grid(row=index // 7, column=index % 7, padx=6, pady=6, sticky="n")
        canvas.bind("<MouseWheel>", lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"))

    def _flow(self, parent, items, render_item, *, per_row=6):
        """Pack image cards in rows so a full rune zone/hand stays visible."""
        row = None
        for index, item in enumerate(items):
            if index % per_row == 0:
                row = tk.Frame(parent, bg="#24364d")
                row.pack(fill="x", anchor="nw")
            render_item(row, item)

    def _fan(self, parent, items, render_item, *, per_row=10, row_height=132):
        """Lay cards over each other inside a fixed-size region.

        The step is calculated from the actual parent width, so every card keeps
        a clickable exposed strip even when the hand or rune pool grows.
        """
        parent.update_idletasks()
        available = max(parent.winfo_width(), parent.winfo_reqwidth(), 1)
        items = list(items)
        for start in range(0, len(items), per_row):
            row_items = items[start:start + per_row]
            wrappers = [render_item(parent, item) for item in row_items]
            if not wrappers:
                continue
            self.update_idletasks()
            card_width = max(wrapper.winfo_reqwidth() for wrapper in wrappers)
            count = len(wrappers)
            step = card_width if count == 1 else min(card_width, max(18, (available - card_width) / (count - 1)))
            for index, wrapper in enumerate(wrappers):
                wrapper.place(x=int(index * step), y=(start // per_row) * row_height)

    def set_hint(self, text):
        self.hint.configure(text=text, fg="#9fb4ce")

    def set_notice(self, text):
        self.hint.configure(text=text, fg="#ffb39f")
        self.log_add(text)

    def _arm_preview(self, widget, code):
        self.set_hint(self._card_name(code))
        self._cancel_preview()
        if code == BACK_CODE:
            return
        self._hover_job = self.after(1000, lambda w=widget, c=code: self._show_preview(w, c))

    def _cancel_preview(self):
        if self._hover_job is not None:
            try:
                self.after_cancel(self._hover_job)
            except tk.TclError:
                pass
            self._hover_job = None
        if self._preview is not None:
            try:
                self._preview.destroy()
            except tk.TclError:
                pass
            self._preview = None

    def _show_preview(self, widget, code):
        if not widget.winfo_exists() or self._preview is not None:
            return
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        image = self._high_photo(code)
        label = tk.Label(popup, image=image, bd=3, relief="solid", bg="black")
        label.pack()
        popup.update_idletasks()
        x = self.winfo_pointerx() + 18
        y = self.winfo_pointery() + 18
        x = min(x, self.winfo_screenwidth() - popup.winfo_width() - 8)
        y = min(y, self.winfo_screenheight() - popup.winfo_height() - 8)
        popup.geometry(f"+{max(4, x)}+{max(4, y)}")
        self._preview = popup
        self._hover_job = None

    # ---------- interactions ----------

    def restart(self):
        if self._opponent_job is not None:
            try:
                self.after_cancel(self._opponent_job)
            except tk.TclError:
                pass
            self._opponent_job = None
        selected = self.variant_box.get() or self.variant
        self.variant = selected if selected in {"starter", "vision", "daughter", "complex", "repeat", "replay", "cost", "resources", "reveal"} else "starter"
        self.rules = OriginsRules(self._decks(), extra_fields=self.extra_fields)
        self.env = Environment(self.rules, max_steps=3000)
        self.env.reset(seed=self.seed)
        self.selected_units.clear()
        self.selected_mulligan.clear()
        self.selected_decision_targets.clear()
        self._close_target_window()
        self._decision_signature = None
        self._winner_announced = False
        self._log_seq = 0
        self.log_clear()
        self.log_add(f"已用种子 {self.seed} 重新开始。")
        self.render()

    def _decks(self):
        deck = (vision_deck() if self.variant == "vision" else
                daughter_deck() if self.variant == "daughter" else
                complex_test_deck() if self.variant == "complex" else
                repeat_targets_deck() if self.variant == "repeat" else
                replay_windows_deck() if self.variant == "replay" else
                cost_abilities_deck() if self.variant == "cost" else
                resource_and_gear_deck() if self.variant == "resources" else
                reveal_targets_deck() if self.variant == "reveal" else starter_deck())
        return [deck, deck]

    def show_scope(self):
        messagebox.showinfo(
            "当前范围",
            "RUP5 2026-10-09\n双人 Duel；158 张显式实现的 Origins 卡牌。\n\n"
            "战场数量由规则状态和卡牌效果决定，界面不会手动添加战场。\n"
            "未支持的牌和效果会在开局前拒绝，不会静默当作白板。",
        )

    def log_clear(self):
        self._log_seq = 0
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def log_add(self, text):
        self._log_seq += 1
        self.log.configure(state="normal")
        self.log.insert("end", f"{self._log_seq:04d}  {text}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start_drag(self, event, uid, zone):
        if (zone == "hand" and self.env.current_player == 0
                and self.env.observe(0)["phase"] == "mulligan"):
            # Mulligan is a direct card selection.  Handle it on press so the
            # first opening render cannot lose the release event while the
            # hand fan is being rebuilt.
            self.mulligan_click(uid)
            self._mulligan_press_uid = uid
            self.drag_card = None
            return "break"
        self.drag_card = (uid, zone, event.x_root, event.y_root)

    def end_drag(self, event, uid, zone):
        if not self.drag_card or self.drag_card[0] != uid:
            if (zone == "hand" and self.env.current_player == 0
                    and self.env.observe(0)["phase"] == "mulligan"
                    and self._mulligan_press_uid != uid):
                # Fallback for the first Tk event delivered to the card's
                # release binding before the press binding has been installed.
                self.mulligan_click(uid)
            self._mulligan_press_uid = None
            return
        started = self.drag_card
        self.drag_card = None
        self._mulligan_press_uid = None
        if abs(event.x_root - started[2]) < 6 and abs(event.y_root - started[3]) < 6:
            if zone == "hand" and self.env.current_player == 0 and self.env.observe(0)["phase"] == "mulligan":
                self.mulligan_click(uid)
                return
            if zone == "hand" and self.env.current_player == 0:
                direct = next((a for a in self.env.legal_actions()
                               if a.kind in {"play_spell_targeted", "play_field_targeted", "play_counter", "play_unit_targeted"}
                               and json.loads(a.arguments).get("card") == uid), None)
                if direct is not None:
                    self.perform(direct)
                    return
            if zone in {"field", "base"} and self.env.current_player == 0 and self.env.observe(0)["phase"] == "main":
                self.unit_click(uid)
            else:
                self.card_menu(event, uid)
            return
        widget = self.winfo_containing(event.x_root, event.y_root)
        target = None
        while widget is not None:
            if hasattr(widget, "_field_index"):
                target = widget._field_index
                break
            if hasattr(widget, "_base_player"):
                target = f"base:{widget._base_player}"
                break
            widget = widget.master
        if target is None:
            self.set_notice("请把已选单位拖到基地或战场区域。")
            return
        if zone not in {"field", "base"}:
            self.card_menu(event, uid)
            return
        if self.env.observe(0)["phase"] != "main" or self.env.current_player != 0:
            self.set_notice("单位只能在自己的主要阶段拖动移动。")
            return
        if uid not in self.selected_units:
            if not self._try_select_unit(uid):
                return
        self._move_selected_units(target)

    def _movement_options(self):
        """Return destination -> units that can be selected after beginning it."""
        if self.env.done or self.env.current_player != 0 or self.env.observe(0)["phase"] != "main":
            return {}
        options = {}
        for action in self.env.legal_actions():
            if action.kind != "begin_move":
                continue
            destination = json.loads(action.arguments)["destination"]
            clone = self.env.clone()
            clone.step(action)
            options[destination] = {
                json.loads(select.arguments)["unit"]
                for select in clone.legal_actions() if select.kind == "select_unit"
            }
        return options

    def _unit_by_id(self, uid):
        return next((u for u in self.env.observe(0)["units"] if u["id"] == uid), None)

    def _try_select_unit(self, uid):
        unit = self._unit_by_id(uid)
        if unit is None or unit["owner"] != 0:
            self.set_notice("只能选择自己的单位。")
            return False
        if unit["exhausted"]:
            self.set_notice(f"不能选择休眠单位：{self._card_name(unit['code'])}。")
            return False
        options = self._movement_options()
        common = {destination for destination, units in options.items() if uid in units}
        common &= {destination for destination, units in options.items()
                   if self.selected_units | {uid} <= units}
        if not common:
            self.set_notice("该单位与当前已选单位没有共同的合法移动目的地。")
            return False
        self.selected_units.add(uid)
        self.set_notice(f"已选择 {self._card_name(unit['code'])}；可继续多选。")
        self.render()
        return True

    def unit_click(self, uid):
        if self.env.current_player != 0 or self.env.observe(0)["phase"] != "main":
            self.card_menu(type("Event", (), {"x_root": self.winfo_pointerx(), "y_root": self.winfo_pointery()})(), uid)
            return
        if uid in self.selected_units:
            self.selected_units.remove(uid)
            self.set_notice("已取消选择该单位。")
            self.render()
            return
        self._try_select_unit(uid)

    def _move_selected_units(self, destination):
        selected = set(self.selected_units)
        options = self._movement_options()
        units = options.get(destination, set())
        if not selected or not selected <= units:
            self.set_notice("所选单位不能一起移动到这个目的地。")
            return
        begin = next((a for a in self.env.legal_actions()
                      if a.kind == "begin_move" and json.loads(a.arguments)["destination"] == destination), None)
        if begin is None:
            self.set_notice("这个目的地当前没有合法移动。")
            return
        try:
            self.env.step(begin)
            for uid in selected:
                select = next(a for a in self.env.legal_actions()
                              if a.kind == "select_unit" and json.loads(a.arguments)["unit"] == uid)
                self.env.step(select)
            commit = next(a for a in self.env.legal_actions() if a.kind == "commit_move")
            self.env.step(commit)
            self.selected_units.clear()
            self.log_add(f"玩家 0：移动 {len(selected)} 个单位到 {destination}（自动横置）")
            self.set_notice("移动完成，单位已横置。")
            self.render()
        except (InvalidAction, ValueError, StopIteration) as error:
            self.set_notice(f"移动未完成：{error}")
            self.selected_units.clear()
            self.render()

    def mulligan_click(self, uid):
        if uid in self.selected_mulligan:
            self.selected_mulligan.remove(uid)
            self.set_notice("已取消调度这张牌。")
        elif len(self.selected_mulligan) >= 2:
            self.set_notice("调度最多选择两张牌。")
            return
        else:
            self.selected_mulligan.add(uid)
            self.set_notice(f"已选择调度 {len(self.selected_mulligan)} 张牌。")
        self.render()

    def commit_mulligan(self):
        if self.env.current_player != 0 or self.env.observe(0)["phase"] != "mulligan":
            return
        hand = self.env.observe(0)["hand"]
        slots = sorted(index for index, card in enumerate(hand) if card["id"] in self.selected_mulligan)
        action = next((a for a in self.env.legal_actions()
                       if a.kind == "mulligan" and json.loads(a.arguments)["slots"] == slots), None)
        if action is None:
            self.set_notice("当前调度选择无效。")
            return
        self.selected_mulligan.clear()
        self.perform(action)

    def card_menu(self, event, uid):
        if self._decision_target_click(uid):
            return
        menu = tk.Menu(self, tearoff=False)
        actions = []
        for action in self.env.legal_actions():
            args = json.loads(action.arguments)
            if uid in {args.get("card"), args.get("unit"), args.get("target"), args.get("gear")}:
                actions.append(action)
        targeted = [action for action in actions if action.kind in {
            "play_spell_targeted", "play_field_targeted", "gear_targeted",
            "unit_ability_targeted", "legend_targeted", "legend_move_targeted"}]
        if targeted:
            legacy = {
                "play_spell", "gear_target", "unit_caitlyn", "unit_malzahar",
                "legend_buff", "legend_ganking", "legend_teemo", "legend_move",
            }
            actions = [action for action in actions if action.kind not in legacy]
        if not actions:
            menu.add_command(label="当前没有合法操作", state="disabled")
        else:
            for action in actions:
                menu.add_command(label=self.action_text(action),
                                 command=lambda a=action: self.perform(a))
        menu.tk_popup(event.x_root, event.y_root)

    def _decision_target_click(self, uid):
        """Handle a card click while the rules engine exposes a choice window."""
        obs = self.env.observe(0)
        decision = obs.get("decision")
        if self.env.current_player != 0 or obs["phase"] != "decision" or not decision:
            return False
        actions = self.env.legal_actions()
        matching = [a for a in actions if json.loads(a.arguments).get("target") == uid
                    or json.loads(a.arguments).get("card") == uid]
        if not matching:
            self.set_notice("这张牌不是当前效果的合法目标。")
            return True
        if decision.get("multi"):
            maximum = decision.get("max", decision.get("count", 1))
            if decision.get("allow_repeat"):
                if len(self.selected_decision_targets) >= maximum:
                    self.set_notice(f"最多选择 {maximum} 次目标。")
                    return True
                # Keep every click, including repeated clicks on one unit.
                self.selected_decision_targets.append(uid)
            elif uid in self.selected_decision_targets:
                self.selected_decision_targets.remove(uid)
            else:
                if len(self.selected_decision_targets) >= maximum:
                    self.set_notice(f"最多选择 {maximum} 个目标。")
                    return True
                self.selected_decision_targets.append(uid)
            self.render()
            return True
        self.selected_decision_targets.clear()
        self.perform(matching[0])
        return True

    def _decision_field_click(self, field):
        """Handle a battlefield click for effects that choose a battlefield."""
        obs = self.env.observe(0)
        decision = obs.get("decision")
        if (self.env.current_player != 0 or obs["phase"] != "decision"
                or not decision or decision.get("kind") != "field"):
            return False
        action = next((action for action in self.env.legal_actions()
                       if action.kind == "choose_field"
                       and json.loads(action.arguments).get("field") == field), None)
        if action is None:
            self.set_notice("这个战场不是当前效果的合法目标。")
            return True
        self.perform(action)
        return True

    def _decision_chain_click(self, chain_target):
        """Choose a spell/ability currently visible on the live Chain."""
        obs = self.env.observe(0)
        decision = obs.get("decision")
        if (self.env.current_player != 0 or obs["phase"] != "decision"
                or not decision or decision.get("kind") != "chain_target"):
            return False
        action = next((action for action in self.env.legal_actions()
                       if action.kind == "choose_chain_target"
                       and json.loads(action.arguments).get("target") == chain_target), None)
        if action is None:
            self.set_notice("这张牌不是当前可无效化的结算链目标。")
            return True
        self.perform(action)
        return True

    def _decision_chain_event(self, event, chain_target):
        self._decision_chain_click(chain_target)
        return "break"

    def commit_decision_targets(self):
        """Commit a multi-target choice after the player explicitly confirms."""
        obs = self.env.observe(0)
        decision = obs.get("decision")
        if not decision or not decision.get("multi"):
            return
        chosen = list(self.selected_decision_targets)
        minimum = decision.get("min", decision.get("count", 1))
        if len(chosen) < minimum:
            self.set_notice(f"至少选择 {minimum} 个目标后才能确认。")
            return
        # The engine keeps the selected ids in the private decision state and
        # exposes a dedicated confirmation action. Apply the clicked ids only
        # when the player presses Confirm, so a click never resolves the effect.
        try:
            for uid in chosen:
                choose = next(a for a in self.env.legal_actions()
                              if a.kind == "choose_target"
                              and json.loads(a.arguments).get("target") == uid)
                self.env.step(choose)
            confirm = next((a for a in self.env.legal_actions()
                            if a.kind == "confirm_targets"), None)
            if confirm is None:
                raise InvalidAction("目标确认动作不可用")
            self.env.step(confirm)
            self.selected_decision_targets.clear()
            self.log_add("玩家 0：按顺序确认目标 " + "、".join(self._target_label(uid) for uid in chosen))
            self.render()
        except (InvalidAction, ValueError, StopIteration) as error:
            self.set_notice(f"目标确认失败：{error}")
            self.selected_decision_targets.clear()
            self.render()
        return

    def cancel_decision_targets(self):
        self.selected_decision_targets.clear()
        self.set_notice("已取消当前目标选择。")
        self.render()

    def _target_label(self, uid):
        """Return a readable label for a selected target UID."""
        obs = self.env.observe(0)
        unit = next((unit for unit in obs.get("units", []) if unit["id"] == uid), None)
        if unit is not None:
            return self._card_name(unit["code"])
        for row in obs.get("players", []):
            gear = next((gear for gear in row.get("gear", []) if gear.get("id") == uid), None)
            if gear is not None:
                return self._card_name(gear["code"])
        return str(uid)

    def _target_code(self, uid):
        obs = self.env.observe(0)
        unit = next((unit for unit in obs.get("units", []) if unit["id"] == uid), None)
        if unit is not None:
            return unit["code"]
        for row in obs.get("players", []):
            gear = next((gear for gear in row.get("gear", []) if gear.get("id") == uid), None)
            if gear is not None:
                return gear["code"]
        return BACK_CODE

    def _close_target_window(self):
        if self._target_window is not None:
            try:
                if self._target_window.winfo_exists():
                    self._target_window.destroy()
            except tk.TclError:
                pass
        self._target_window = None

    def _remove_decision_target(self, index):
        if 0 <= index < len(self.selected_decision_targets):
            self.selected_decision_targets.pop(index)
            self.render()

    def _remove_decision_target_event(self, event, index):
        """Remove one entry from the temporary target sequence window."""
        self._remove_decision_target(index)
        return "break"

    def _render_target_window(self, decision):
        """Show the ordered, not-yet-committed target sequence."""
        if not decision.get("multi") or self.env.current_player != 0:
            self._close_target_window()
            return
        if self._target_window is None or not self._target_window.winfo_exists():
            popup = tk.Toplevel(self)
            popup.title("目标分配 / Target sequence")
            popup.transient(self)
            popup.protocol("WM_DELETE_WINDOW", self._close_target_window)
            self._target_window = popup
        else:
            popup = self._target_window
            for child in popup.winfo_children():
                child.destroy()
        popup.configure(bg="#101b2b")
        tk.Label(popup, text=("按顺序点击目标；重复点击代表重复分配。"
                              if decision.get("allow_repeat") else "点击目标加入分配序列。"),
                 bg="#101b2b", fg="#f3d58b", padx=8, pady=6).pack(fill="x")
        body = tk.Frame(popup, bg="#101b2b")
        body.pack(fill="both", expand=True, padx=6, pady=4)
        for index, uid in enumerate(self.selected_decision_targets):
            item = tk.Frame(body, bg="#24364d", padx=3, pady=3)
            item.pack(side="left", padx=3, anchor="n")
            wrapper = self._image_card(item, self._target_code(uid), factor=5,
                                       compact_label=f"{index + 1}. {self._target_label(uid)}",
                                       click=False, pack=True)
            wrapper.bind("<Button-1>", lambda event, i=index: self._remove_decision_target_event(event, i))
            for child in wrapper.winfo_children():
                child.bind("<Button-1>", lambda event, i=index: self._remove_decision_target_event(event, i), add="+")
        if not self.selected_decision_targets:
            tk.Label(body, text="尚未选择目标", bg="#101b2b", fg="#9fb4ce",
                     padx=12, pady=16).pack()
        controls = tk.Frame(popup, bg="#101b2b")
        controls.pack(fill="x", padx=6, pady=(2, 6))
        ttk.Button(controls, text="清空重选 / Clear",
                   command=self.cancel_decision_targets).pack(side="left")
        tk.Label(controls, text=f"已选 {len(self.selected_decision_targets)}/{decision.get('max', 0)}",
                 bg="#101b2b", fg="#dbe8f7").pack(side="right", padx=6)
        popup.update_idletasks()
        width = max(420, min(1200, 180 * max(2, len(self.selected_decision_targets))))
        popup.geometry(f"{width}x260")

    def _rune_name(self, uid):
        for row in self.env.observe(0)["players"]:
            for rune in row["runes"]:
                if rune["id"] == uid:
                    return self._card_name(rune["code"])
        return uid

    def _rune_card(self, parent, rune, *, player, pack=True, show_label=True):
        wrapper = tk.Frame(parent, bg="#24364d", padx=1, pady=1)
        if pack:
            wrapper.pack(side="left", padx=2, pady=2)
        button = tk.Button(wrapper, image=self._photo(rune["code"], 5, horizontal=rune["exhausted"]), relief="raised", bd=2,
                           bg="#111111", cursor="hand2")
        button.pack()
        button.bind("<Enter>", lambda _event, c=rune["code"]: self._arm_preview(button, c))
        button.bind("<Leave>", lambda _event: self._cancel_preview())
        if rune["exhausted"]:
            tk.Label(wrapper, text="横置", bg="#8e2930", fg="white",
                     font=("TkDefaultFont", 8, "bold")).place(relx=.5, rely=.5, anchor="center")
        if show_label:
            tk.Label(wrapper, text=self._card_name(rune["code"]), bg="#24364d", fg="#e9f1fc",
                     font=("TkDefaultFont", 7)).pack()
        if player == 0:
            button.bind("<Button-1>", lambda _event, u=rune["id"]: self.rune_click(u))
            button.bind("<Button-3>", lambda event, u=rune["id"]: self.rune_menu(event, u))
        return wrapper

    def rune_click(self, uid):
        for action in self.env.legal_actions():
            args = json.loads(action.arguments)
            if action.kind == "exhaust_rune" and args.get("rune") == uid:
                self.perform(action)
                return
        self.log_add("这枚符文当前不能横置。右键可查看回收操作。")

    def undo_rune(self):
        action = next((a for a in self.env.legal_actions() if a.kind == "undo_rune"), None)
        if action is None:
            self.set_notice("当前没有可回撤的连续符文操作。")
            return
        self.perform(action)

    def rune_menu(self, event, uid):
        menu = tk.Menu(self, tearoff=False)
        actions = [a for a in self.env.legal_actions()
                   if json.loads(a.arguments).get("rune") == uid]
        if not actions:
            menu.add_command(label="当前没有合法符文操作", state="disabled")
        else:
            for action in actions:
                menu.add_command(label=self.action_text(action),
                                 command=lambda a=action: self.perform(a))
        menu.tk_popup(event.x_root, event.y_root)

    def action_text(self, action):
        args = json.loads(action.arguments)
        names = {
            "play_unit": "打出单位 / Play unit", "play_spell": "施放法术 / Play spell",
            "begin_move": "移动到目标 / Move", "exhaust_rune": "横置符文 / Exhaust rune",
            "recycle_rune": "回收符文 / Recycle rune", "legend_energy": "传奇能力 / Legend energy",
            "undo_rune": "回撤上一步符文操作 / Undo rune action",
            "hide_card": "Hidden：放置到战场 / Hide",
            "end_reveal": "结束展示 / End reveal",
            "choose_revealed": "选择展示牌 / Select revealed card",
            "confirm_revealed": "确认展示牌选择 / Confirm revealed cards",
            "choose_option": "确认选项 / Choose option",
            "play_hidden": "打出 Hidden / Play Hidden",
            "play_hidden_targeted": "打出 Hidden 并选择目标 / Play Hidden",
            "play_gear": "放置装备 / Play gear",
            "gear_resource": "装备资源能力 / Gear resource",
            "gear_target": "装备目标能力 / Gear target",
            "gear_ready_next": "装备能力 / Ready next unit",
            "gear_tome": "装备能力 / Bonus spell damage",
            "gear_kill": "装备能力 / Kill gear",
            "gear_grab": "装备能力 / Recycle and draw",
            "gear_forge_recycle": "Forge：回收弃牌 / Recycle trash",
            "unit_recycle_buff": "单位能力 / Recycle for Might",
            "legend_spell_power": "传奇能力 / Spell rainbow power",
            "legend_recruit": "传奇能力 / Recruit token",
            "legend_channel": "传奇能力 / Channel exhausted rune",
            "unit_buff": "单位能力 / Buff self",
            "legend_buff": "传奇能力 / Buff unit",
            "legend_move": "传奇能力 / Move unit",
            "legend_ganking": "传奇能力 / Grant Ganking",
            "legend_teemo": "Swift Scout：回收 Teemo / Return Teemo",
            "end_turn": "结束回合 / End turn", "pass": "让过 / Pass", "commit_move": "确认移动 / Commit",
            "cancel_move": "取消移动 / Cancel", "select_unit": "选择单位 / Select unit",
            "assign_damage": "分配伤害 / Assign damage",
            "optional_effect": "可选效果 / Optional effect",
            "order_optional": "选择可选效果顺序 / Order optional effects",
            "play_spell_targeted": "施放法术并选择目标 / Cast and choose targets",
            "play_counter": "施放反制法术并选择结算链目标 / Cast counter and choose chain target",
            "play_field_targeted": "施放法术并选择战场 / Cast and choose battlefield",
            "play_unit_targeted": "打出单位并选择技能目标 / Play and choose ability target",
            "gear_targeted": "装备能力并选择目标 / Gear ability and choose target",
            "unit_ability_targeted": "单位技能并选择目标 / Unit ability and choose target",
            "legend_targeted": "传奇能力并选择目标 / Legend ability and choose target",
            "legend_move_targeted": "传奇能力并选择移动目标 / Legend move and choose target",
            "choose_target": "选择目标 / Choose target",
            "choose_chain_target": "选择结算链目标 / Choose chain target",
            "choose_field": "选择战场 / Choose battlefield",
            "confirm_targets": "确认目标 / Confirm targets",
            "cancel_play": "取消打出 / Cancel play",
            "predict": "洞察 / Vision：" + ("回收牌顶" if args.get("recycle") else "保留牌顶"),
            "discard_card": "弃置此牌 / Discard",
            "mulligan": "调度 / Mulligan：" + ("、".join(str(i + 1) for i in args.get("slots", [])) or "不换牌"),
        }
        text = names.get(action.kind, action.kind)
        if action.kind == "choose_option":
            text = {"draw": "抽一张牌 / Draw 1", "channel": "横置引导一枚符文 / Channel rune",
                    "accelerate": "加速：支付额外费用并活跃 / Accelerate: pay and enter ready",
                    "skip": "跳过加速：横置入场 / Skip Accelerate: enter exhausted"}.get(
                args.get("option"), text)
            option = args.get("option")
            if isinstance(option, int):
                text = f"选择战场 {option + 1} / Choose battlefield {option + 1}"
            elif isinstance(option, str) and option.startswith("base:"):
                text = f"移动到基地 {option.split(':', 1)[1]} / Move to base"
        if action.kind in {"exhaust_rune", "recycle_rune"}:
            text += " · " + self._rune_name(args.get("rune"))
        if action.kind == "play_unit":
            text += " → " + str(args.get("location"))
        if action.kind == "play_spell":
            text += " → " + ",".join(args.get("targets", []))
        if action.kind == "play_spell_targeted":
            text += f"（选择 {args.get('target_min', 0)}–{args.get('target_max', 0)} 个目标）"
        if action.kind == "order_triggers":
            text = "触发顺序：" + " → ".join(str(i + 1) for i in args.get("order", []))
        if action.kind == "order_optional":
            text = "可选效果顺序：" + " → ".join(args.get("order", []))
        if action.kind == "optional_effect":
            text = ("确认触发 / Confirm optional" if args.get("accept")
                    else "跳过 / Skip optional")
        return text

    def choose_action(self, actions, title):
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.grab_set()
        ttk.Label(dialog, text=title, padding=8).pack()
        for action in actions:
            ttk.Button(dialog, text=self.action_text(action),
                       command=lambda a=action, d=dialog: (d.destroy(), self.perform(a))).pack(
                           fill="x", padx=12, pady=3)

    def _log_transition(self, before, after):
        """Write meaningful rules-state changes alongside the clicked action."""
        if before["phase"] != after["phase"]:
            self.log_add(f"阶段：{before['phase']} → {after['phase']}")
        def chain_signature(items):
            return [json.dumps({key: item.get(key) for key in
                                ("effect", "code", "source", "owner", "target", "targets")},
                               ensure_ascii=False, sort_keys=True)
                    for item in items]
        old_chain, new_chain = chain_signature(before.get("chain", [])), chain_signature(after.get("chain", []))
        if old_chain != new_chain:
            if after.get("chain"):
                self.log_add("结算链：" + " → ".join(self._chain_item_text(item)
                                                   for item in reversed(after["chain"])))
            else:
                self.log_add("结算链已清空。")
        old_pending, new_pending = chain_signature(before.get("pending", [])), chain_signature(after.get("pending", []))
        if old_pending != new_pending and after.get("pending"):
            self.log_add("待排序触发：" + " → ".join(self._chain_item_text(item)
                                                  for item in after["pending"]))
        if before.get("decision") != after.get("decision") and after.get("decision"):
            decision = after["decision"]
            targets = decision.get("targets", [])
            self.log_add(f"等待 P{decision.get('player')} 选择 {decision.get('kind')}"
                         + (f"（{len(targets)} 个合法目标）" if targets else ""))
        if before.get("reveal") != after.get("reveal"):
            reveal = after.get("reveal") or before.get("reveal")
            if reveal:
                shown = "、".join(card.get("code", "") for card in reveal.get("cards", []))
                selected = "、".join(card.get("code", "") for card in reveal.get("selected", []))
                self.log_add(f"公开展示：{shown}" + (f"；已选：{selected}" if selected else ""))
        for index, (old_row, new_row) in enumerate(zip(before.get("players", []), after.get("players", []))):
            if (old_row.get("energy"), old_row.get("power")) != (new_row.get("energy"), new_row.get("power")):
                self.log_add(f"P{index} 资源：法力 {old_row.get('energy')}→{new_row.get('energy')}；"
                             f"符能 {len(old_row.get('power', []))}→{len(new_row.get('power', []))}")
        old_units = {unit["id"]: unit for unit in before.get("units", [])}
        new_units = {unit["id"]: unit for unit in after.get("units", [])}
        for uid, unit in new_units.items():
            old = old_units.get(uid)
            if old is None:
                self.log_add(f"单位进入：P{unit['owner']} {self._card_name(unit['code'])}（{unit['location']}）")
                continue
            keys = ("location", "might", "damage", "temporary", "buff", "assault",
                    "combat_shield", "stunned", "exhausted")
            if any(old.get(key) != unit.get(key) for key in keys):
                flags = []
                if old.get("temporary") != unit.get("temporary"):
                    flags.append(f"临时战力 {old.get('temporary', 0)}→{unit.get('temporary', 0)}")
                if old.get("damage") != unit.get("damage"):
                    flags.append(f"伤害 {old.get('damage', 0)}→{unit.get('damage', 0)}")
                if old.get("buff") != unit.get("buff"):
                    flags.append(f"增益 {old.get('buff', 0)}→{unit.get('buff', 0)}")
                if old.get("stunned") != unit.get("stunned"):
                    flags.append("眩晕" if unit.get("stunned") else "解除眩晕")
                if old.get("location") != unit.get("location"):
                    flags.append(f"位置 {old.get('location')}→{unit.get('location')}")
                if old.get("exhausted") != unit.get("exhausted"):
                    flags.append("横置" if unit.get("exhausted") else "就绪")
                self.log_add(f"单位状态：{self._card_name(unit['code'])}（{'; '.join(flags)}）")
        for uid, old in old_units.items():
            if uid not in new_units:
                self.log_add(f"单位离场：P{old['owner']} {self._card_name(old['code'])}")

    def perform(self, action):
        try:
            before = self.env.current_player
            before_obs = self.env.observe(0)
            self.env.step(action)
            self.log_add(f"玩家 {before}：{self.action_text(action)}")
            self._log_transition(before_obs, self.env.observe(0))
            self.render()
        except (InvalidAction, ValueError) as error:
            messagebox.showerror("操作无效", str(error))

    # ---------- rendering ----------

    def _chain_item_text(self, item):
        effect = item.get("effect", "effect")
        if effect == "spell":
            code = item.get("code", item.get("card", "spell"))
            name = self._card_name(self.rules.cards.get(code, {}).get("code", code))
            return f"P{item.get('owner')} {name}"
        names = {
            "vision": "Vision / 洞察", "discard_two": "弃牌触发",
            "darius": "Darius 触发", "buff_self": "自身增益",
            "peak": "Peak Guardian 触发", "drummer": "Drummer 触发",
            "kill_target": "击杀目标", "stun_target": "Stun 目标",
            "buff_eight": "+8 增益",
            "ahri_debuff": "Ahri：目标 -2 战力",
        }
        return f"P{item.get('owner')} {names.get(effect, effect)}"

    def _chain_source_code(self, obs, item):
        source = item.get("source")
        unit = next((u for u in obs.get("units", []) if u.get("id") == source), None)
        return unit["code"] if unit else None

    def render_chain(self, obs):
        """Show the full live chain in a compact two-column card stack."""
        body = self._clear("chain")
        body.configure(width=205, height=390)
        body.pack_propagate(False)
        chain = list(obs.get("chain") or [])
        items = [(f"chain:{chain_index}", item, False)
                 for chain_index, item in reversed(list(enumerate(chain)))]
        items += [(None, {**item, "pending": True}, True)
                  for item in (obs.get("pending") or [])]
        if not items:
            tk.Label(body, text="当前没有待结算项目", bg="#1b2a3e", fg="#9fb4ce",
                     justify="left", wraplength=180).pack(pady=10)
            return
        decision = obs.get("decision") or {}
        chain_targets = set(decision.get("targets", [])) if decision.get("kind") == "chain_target" else set()
        for index, (chain_target, item, pending) in enumerate(items):
            effect = item.get("effect")
            code = item.get("code") if effect == "spell" else self._chain_source_code(obs, item)
            if not code:
                code = BACK_CODE
            selectable = chain_target in chain_targets
            card = tk.Frame(body, bg="#f4c542" if selectable else "#31445f", padx=2, pady=2)
            x = 4 + (index % 2) * 98
            y = 4 + (index // 2) * 88
            card.place(x=x, y=y, width=92, height=84)
            self._image_card(card, code, factor=7, compact_label="", click=False,
                             pack=True, show_label=False)
            label = "法术" if effect == "spell" else "技能虚影"
            if pending:
                label += " · 待排序"
            if chain_target is not None:
                label = f"#{len(chain) - 1 - int(chain_target.split(':', 1)[1]) + 1} · " + label
            tk.Label(card, text=label, bg="#31445f", fg="#dbe8f7",
                     font=("TkDefaultFont", 7, "bold")).place(relx=.5, rely=.9, anchor="center")
            if selectable:
                def bind_chain_click(widget, target=chain_target):
                    widget.bind("<Button-1>", lambda event, t=target:
                                self._decision_chain_event(event, t), add="+")
                    for child in widget.winfo_children():
                        bind_chain_click(child, target)
                bind_chain_click(card)

    def _state_summary(self, obs):
        phases = {
            "mulligan": "调度阶段", "main": "主要阶段",
            "chain": "结算链", "trigger_order": "触发顺序",
            "showdown": "对决结算", "damage": "战斗伤害分配",
            "move_select": "移动选择", "decision": "效果选择", "optional": "可选效果确认",
        }
        parts = [f"回合 {obs['turn']} · 回合玩家 P{obs['turn_player']} · 当前行动 P{obs['to_act']} · {phases.get(obs['phase'], obs['phase'])}"]
        chain = obs.get("chain") or []
        if chain:
            parts.append("结算链（顶→底）：" + " | ".join(self._chain_item_text(item) for item in reversed(chain)))
        pending = obs.get("pending") or []
        if pending:
            parts.append("待排序触发：" + " | ".join(self._chain_item_text(item) for item in pending))
        battle = obs.get("battle")
        if battle:
            text = f"战场 {battle['field'] + 1} · 攻击者 P{battle['attacker']}"
            if battle.get("combat"):
                text += " · 有战斗"
            parts.append(text)
        decision = obs.get("decision")
        if decision:
            parts.append(f"等待 P{decision['player']} 完成 {decision['kind']} 选择")
        optional = obs.get("optional") or []
        if optional:
            parts.append("可选效果队列：" + " → ".join(
                f"P{item.get('player')} {item.get('effect', 'effect')}" for item in optional
            ))
        reveal = obs.get("reveal")
        if reveal:
            parts.append("公开展示：" + "、".join(self._card_name(card["code"]) for card in reveal.get("cards", [])))
        return "\n".join(parts)

    def render(self):
        obs = self.env.observe(0)
        if obs["phase"] != "main" or obs["to_act"] != 0:
            self.selected_units.clear()
        if obs["phase"] != "mulligan" or obs["to_act"] != 0:
            self.selected_mulligan.clear()
        if obs["phase"] != "decision" or obs["to_act"] != 0:
            self.selected_decision_targets.clear()
            self._close_target_window()
        turn_text = "玩家 0 行动" if obs["to_act"] == 0 else "对手行动"
        self.status.configure(text=f"回合 {obs['turn']} · {turn_text} · 比分 {obs['points'][0]}–{obs['points'][1]} / {obs['victory']}")
        self.state_bar.configure(text=self._state_summary(obs))
        self.render_opponent(obs)
        self.render_battlefields(obs)
        self.render_player(obs)
        self.render_chain(obs)
        self.render_banishment(obs)
        self.render_actions()
        self._render_reveal_window(obs)
        if obs["phase"] == "decision" and obs["to_act"] == 0:
            signature = json.dumps(obs["decision"], sort_keys=True)
            if signature != self._decision_signature:
                self._decision_signature = signature
        else:
            self._decision_signature = None
        if obs["winner"] is not None and not self._winner_announced:
            self._winner_announced = True
            messagebox.showinfo("对局结束", f"玩家 {obs['winner']} 获胜。")

    def render_opponent(self, obs):
        body = self._clear("opponent")
        body.grid_rowconfigure(0, weight=1, minsize=165)
        body.grid_rowconfigure(1, weight=0, minsize=165)
        # Match the player's left-to-right arrangement: identity, runes,
        # hand, piles, status.  Keeping the rune pool beside the hand also
        # gives it the same usable height and width as the player's pool.
        body.grid_columnconfigure(1, weight=1, minsize=280)
        body.grid_columnconfigure(2, weight=2, minsize=420)
        body.grid_columnconfigure(3, weight=0, minsize=250)
        body.grid_columnconfigure(4, weight=0, minsize=150)
        identity = tk.Frame(body, bg="#1b2a3e")
        identity.grid(row=0, column=0, sticky="nsw")
        self._identity(identity, obs, 1, compact=True)
        rune_zone = self._subzone(body, "对手符文区", width=280)
        rune_zone.grid(row=0, column=1, sticky="nsew", padx=4)
        self._fan(rune_zone, obs["players"][1]["runes"],
                  lambda parent, rune: self._rune_card(parent, rune, player=1,
                                                        pack=False, show_label=False),
                  per_row=10, row_height=130)
        hand = self._subzone(body, f"对手手牌 · {obs['players'][1]['hand_count']} 张", width=500, height=165)
        hand.grid(row=0, column=2, sticky="nsew", padx=4)
        self._fan(hand, range(min(10, obs["players"][1]["hand_count"])),
                  lambda parent, _item: self._image_card(parent, BACK_CODE, factor=4,
                                                         compact_label="", pack=False, show_label=False),
                  per_row=10, row_height=165)
        piles = self._subzone(body, "对手牌堆 / Opponent Piles", width=250)
        piles.grid(row=0, column=3, sticky="nsew", padx=4)
        self._stack(piles, obs["players"][1]["trash"], owner=1,
                    title="P1 弃牌 / Trash", factor=5, collapse=True)
        self._stack(piles, [], title="牌库 / Deck", factor=5,
                    count=obs["players"][1]["main_count"])
        self._status_box(body, obs, 1, column=4)
        base_zone = self._subzone(body, "对手基地 / Opponent Base", height=165)
        base_zone.grid(row=1, column=0, columnspan=5, sticky="ew", padx=4, pady=(3, 0))
        base = tk.Frame(base_zone, bg="#263a54")
        base.pack(fill="both", expand=True)
        for unit in [u for u in obs["units"] if u["location"] == "base:1"]:
            self._image_card(base, unit["code"], uid=unit["id"], owner=unit["owner"],
                             zone="base", factor=4,
                             compact_label=self._unit_status_label(unit),
                             exhausted=unit["exhausted"], selected=unit["id"] in self.selected_units)
        for gear in obs["players"][1].get("gear", []):
            self._image_card(base, gear["code"], uid=gear["id"], owner=1, zone="gear", factor=4,
                             compact_label="装备 · " + ("横置" if gear["exhausted"] else "就绪"),
                             exhausted=gear["exhausted"])

    def _identity(self, parent, obs, player, *, compact=False):
        row = obs["players"][player]
        legend = self._subzone(parent, "传奇区 / Legend")
        legend.pack(side="left", fill="y", padx=2)
        self._image_card(legend, row["legend"], factor=4,
                         compact_label=("横置" if row["legend_exhausted"] else "就绪"),
                         click=False, exhausted=row["legend_exhausted"])
        champion = self._subzone(parent, "英雄区 / Champion")
        champion.pack(side="left", fill="y", padx=2)
        for card in row["champion"]:
            self._image_card(champion, card["code"], uid=card["id"] if player == 0 else None,
                             owner=player, zone="champion", factor=4)

    def _status_box(self, parent, obs, player, *, column=None, row=0):
        frame = self._subzone(parent, f"P{player} 状态", width=150)
        if column is None:
            frame.pack(side="left", fill="y", padx=3)
        else:
            frame.grid(row=row, column=column, sticky="nse", padx=4)
        row = obs["players"][player]
        power_names = {"fury": "Fury", "calm": "Calm", "mind": "Mind",
                       "body": "Body", "chaos": "Chaos", "order": "Order",
                       "spell_any": "万能"}
        power_counts = Counter(row["power"])
        power_text = "、".join(
            f"{power_names.get(domain, domain)}×{count}"
            for domain, count in power_counts.items()
        ) or "—"
        text = (f"法力/能量 {row['energy']}\n"
                f"符能/力量 {row.get('power_count', len(row['power']))}\n"
                f"{power_text}\n"
                f"牌库 {row['main_count']}\n符文 {len(row['runes'])}\n阶段 {obs['phase']}")
        tk.Label(frame, text=text, justify="left", anchor="nw", bg="#24364d", fg="#e6eef9",
                 padx=8, pady=6).pack(fill="both", expand=True)

    def render_battlefields(self, obs):
        body = self._clear("battlefields")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)
        fields = tk.Frame(body, bg="#1b2a3e")
        fields.grid(row=0, column=0, sticky="nsew")
        fields.grid_rowconfigure(0, weight=1)
        for index in range(len(obs["fields"])):
            fields.grid_columnconfigure(index, weight=1)
        for index, field in enumerate(obs["fields"]):
            frame = tk.LabelFrame(fields,
                                  text=f"战场 {index + 1} · {self._card_name(field['code'])}\n控制：{field['controller']}",
                                  bg="#263a54", fg="#e9f1fc", padx=4, pady=3)
            frame.grid(row=0, column=index, sticky="nsew", padx=3, pady=2)
            frame._field_index = index
            if obs["phase"] == "decision" and obs["to_act"] == 0 and obs.get("decision", {}).get("kind") == "field":
                frame.bind("<Button-1>", lambda _event, i=index: self._decision_field_click(i))
            field_card_zone = tk.Frame(frame, bg="#263a54", width=82)
            field_card_zone.pack(side="left", fill="y", padx=(0, 4))
            field_card_center = tk.Frame(field_card_zone, bg="#263a54")
            field_card_center.pack(expand=True)
            self._image_card(field_card_center, field["code"], factor=4,
                             compact_label="战场卡", click=True, field=index)
            units = tk.Frame(frame, bg="#263a54")
            units.pack(side="left", fill="both", expand=True)
            units.grid_rowconfigure(0, weight=1)
            units.grid_rowconfigure(1, weight=1)
            opponent_row = tk.Frame(units, bg="#263a54")
            opponent_row.grid(row=0, column=0, sticky="new")
            player_row = tk.Frame(units, bg="#263a54")
            player_row.grid(row=1, column=0, sticky="sew")
            for unit in [u for u in obs["units"] if u["location"] == index]:
                pending = 0
                if obs["battle"] and obs["battle"].get("damage"):
                    pending = sum(assignment.get(unit["id"], 0)
                                  for assignment in obs["battle"]["damage"]["assignments"])
                row = player_row if unit["owner"] == 0 else opponent_row
                self._image_card(row, unit["code"], uid=unit["id"], owner=unit["owner"],
                                 zone="field", factor=5,
                                 compact_label=self._unit_status_label(unit, pending=pending),
                                 exhausted=unit["exhausted"], selected=unit["id"] in self.selected_units,
                                 field=index)
            for owner, hidden_row in enumerate(obs["players"]):
                hidden_cards = [h for h in hidden_row.get("hidden", []) if h["field"] == index]
                target_row = player_row if owner == 0 else opponent_row
                for hidden in hidden_cards:
                    self._image_card(target_row, hidden["code"], uid=hidden["id"], owner=owner,
                                     zone="hidden", factor=5, compact_label="Hidden · 背面",
                                     click=True, field=index)
    def render_player(self, obs):
        body = self._clear("player")
        body.grid_rowconfigure(0, weight=0, minsize=165)
        body.grid_rowconfigure(1, weight=1, minsize=165)
        body.grid_columnconfigure(1, weight=1, minsize=300)
        body.grid_columnconfigure(2, weight=2, minsize=500)
        body.grid_columnconfigure(3, weight=0, minsize=150)
        body.grid_columnconfigure(4, weight=0, minsize=250)
        identity = tk.Frame(body, bg="#1b2a3e")
        identity.grid(row=1, column=0, sticky="nsw")
        self._identity(identity, obs, 0)

        rune_zone = self._subzone(body, "符文区 / Runes · 左键横置 · 右键回收", width=280)
        rune_zone.grid(row=1, column=1, sticky="nsew", padx=4)
        self._fan(rune_zone, obs["players"][0]["runes"],
                  lambda parent, rune: self._rune_card(parent, rune, player=0,
                                                        pack=False, show_label=False),
                  per_row=10, row_height=130)
        undo_count = obs.get("rune_undo_count", 0)
        if undo_count:
            controls = tk.Frame(rune_zone, bg="#24364d")
            controls.place(relx=0.99, rely=0.98, anchor="se")
            ttk.Button(controls, text=f"回撤符文操作 ({undo_count})",
                       command=self.undo_rune).pack(side="left", padx=2)

        hand_zone = self._subzone(body, f"手牌 / Hand · {len(obs['hand'])} 张", width=500, height=165)
        hand_zone.grid(row=1, column=2, sticky="nsew", padx=4)
        self._fan(hand_zone, obs["hand"],
                  lambda parent, card: self._image_card(parent, card["code"], uid=card["id"],
                                                        owner=0, zone="hand", factor=4,
                                                        selected=card["id"] in self.selected_mulligan,
                                                        pack=False, show_label=False),
                  per_row=10, row_height=132)

        self._status_box(body, obs, 0, column=3, row=1)
        # The player's base is above the hand row, matching the physical table
        # orientation and keeping it outside the battlefield panel.
        bases = self._subzone(body, "我方基地 / Player Base", height=165)
        bases.grid(row=0, column=0, columnspan=5, sticky="nsew", padx=3, pady=(2, 0))
        # The outer player-base zone already provides the label and border;
        # use it directly so there is no redundant nested "P0 基地" panel.
        base = bases
        base._base_player = 0
        for unit in [u for u in obs["units"] if u["location"] == "base:0"]:
            self._image_card(base, unit["code"], uid=unit["id"], owner=unit["owner"],
                             zone="base", factor=4,
                             compact_label=self._unit_status_label(unit),
                             exhausted=unit["exhausted"], selected=unit["id"] in self.selected_units)
        for gear in obs["players"][0].get("gear", []):
            self._image_card(base, gear["code"], uid=gear["id"], owner=0, zone="gear", factor=4,
                             compact_label="装备 · " + ("横置" if gear["exhausted"] else "就绪"),
                             exhausted=gear["exhausted"])
        piles = self._subzone(body, "牌堆 / Player Piles", width=250)
        piles.grid(row=1, column=4, sticky="nsew", padx=4)
        self._stack(piles, obs["players"][0]["trash"], owner=0,
                    title="P0 弃牌 / Trash", factor=5, collapse=True)
        self._stack(piles, [], title="牌库 / Deck", factor=5,
                    count=obs["players"][0]["main_count"])


    def render_banishment(self, obs):
        body = self._clear("banishment")
        tk.Label(body, text="公开放逐牌", bg="#1b2a3e", fg="#dce9fb").pack(anchor="w", padx=4)
        self._stack(body, obs["players"][0]["banishment"], owner=0,
                    title="P0 放逐 / Banishment", factor=4)
        self._stack(body, obs["players"][1]["banishment"], owner=1,
                    title="P1 放逐 / Banishment", factor=4)

    def render_actions(self):
        for child in self.actions.winfo_children():
            child.destroy()
        if self.env.done:
            tk.Label(self.actions, text="对局已结束", bg="#101b2b", fg="#f2d38b").pack(side="left")
            return
        legal = self.env.legal_actions()
        obs = self.env.observe(0)
        reveal = obs.get("reveal")
        if reveal:
            self._render_reveal_bar(reveal, legal)
            return
        optional = obs.get("optional") or []
        if optional and self.env.current_player == 0:
            self._render_optional_bar(optional[0], legal)
            return
        decision = obs.get("decision")
        if decision and self.env.current_player == 0:
            self._render_decision_bar(decision, legal)
            return
        if self.env.current_player != 0:
            tk.Label(self.actions, text="对手正在自动决策…", bg="#101b2b", fg="#c7d7eb").pack(side="left")
            if self._opponent_job is None:
                self._opponent_job = self.after(300, self.opponent_step)
            return
        targeted_kinds = {"gear_targeted", "unit_ability_targeted", "legend_targeted"}
        targeted_present = {
            (action.kind, json.loads(action.arguments).get("unit"),
             json.loads(action.arguments).get("gear"),
             json.loads(action.arguments).get("ability"))
            for action in legal if action.kind in targeted_kinds
        }
        mulligans = [a for a in legal if a.kind == "mulligan"]
        if mulligans:
            ttk.Button(self.actions, text=f"调度 / Mulligan ({len(self.selected_mulligan)})",
                       command=self.commit_mulligan).pack(side="left", padx=2)
        for action in legal:
            args = json.loads(action.arguments)
            if action.kind in {"unit_caitlyn", "unit_malzahar"}:
                marker = ("unit_ability_targeted", args.get("unit"), None,
                          "caitlyn" if action.kind == "unit_caitlyn" else "malzahar")
                if marker in targeted_present:
                    continue
            if action.kind in {"legend_buff", "legend_ganking", "legend_teemo"}:
                ability = {"legend_buff": "buff", "legend_ganking": "ganking", "legend_teemo": "teemo"}[action.kind]
                if any(entry[0] == "legend_targeted" and entry[3] == ability for entry in targeted_present):
                    continue
            if action.kind == "legend_move" and any(entry[0] == "legend_move_targeted" for entry in targeted_present):
                continue
            if action.kind in {"end_turn", "pass", "legend_energy", "legend_spell_power",
                               "legend_recruit", "legend_channel", "unit_buff", "legend_buff",
                               "legend_move", "legend_ganking",
                               "legend_targeted", "legend_move_targeted", "commit_move", "cancel_move", "order_triggers",
                               "play_spell_targeted", "play_field_targeted", "play_counter", "play_unit_targeted"}:
                ttk.Button(self.actions, text=self.action_text(action),
                           command=lambda a=action: self.perform(a)).pack(side="left", padx=2)
        prompt = "左键选择/多选单位，再拖到基地/战场移动；右键查看其他操作"
        if self.env.observe(0)["phase"] == "damage":
            prompt = "点击或右键对手单位分配伤害"
        tk.Label(self.actions, text=prompt, bg="#101b2b", fg="#9fb4ce").pack(side="right")

    def _render_reveal_bar(self, reveal, legal):
        kind = reveal.get("kind")
        text = "公开展示：" + "、".join(self._card_name(card["code"]) for card in reveal.get("cards", []))
        if kind == "select":
            text += f"；已选 {len(reveal.get('selected', []))}/{reveal.get('max', 0)}"
        elif kind == "display":
            # The public-display branch is closed by the player who caused the
            # reveal (the displayed player's opponent).  Keep this wording
            # explicit because ``owner`` is the player whose cards are shown,
            # while older state snapshots called the closer merely ``opponent``.
            text += "；由展示对象的对手结束展示 / Displayed player's opponent ends reveal"
        tk.Label(self.actions, text=text, bg="#101b2b", fg="#f3d58b").pack(side="left", padx=4)
        closer = reveal.get("end_player", reveal.get("closer", reveal.get("opponent")))
        can_close = closer is None or closer == self.env.current_player
        for action in legal:
            if action.kind in {"end_reveal", "confirm_revealed"} and (action.kind != "end_reveal" or can_close):
                label = ("施放者结束展示 / Caster ends reveal"
                         if action.kind == "end_reveal" else self.action_text(action))
                ttk.Button(self.actions, text=label,
                           command=lambda a=action: self.perform(a)).pack(side="left", padx=2)

    def _render_reveal_window(self, obs):
        reveal = obs.get("reveal")
        if not reveal:
            if self._reveal_window is not None and self._reveal_window.winfo_exists():
                self._reveal_window.destroy()
            self._reveal_window = None
            return
        if self._reveal_window is not None and self._reveal_window.winfo_exists():
            self._reveal_window.destroy()
        popup = tk.Toplevel(self)
        self._reveal_window = popup
        popup.title("公开展示 / Reveal")
        popup.geometry("1100x760")
        popup.transient(self)
        tk.Label(popup, text="双方可见的临时展示区", bg="#101b2b", fg="#f3d58b",
                 padx=8, pady=6).pack(fill="x")
        body = tk.Frame(popup, bg="#101b2b")
        body.pack(fill="both", expand=True)
        selected = {card["id"] for card in reveal.get("selected", [])}
        legal = self.env.legal_actions()
        actions = {json.loads(a.arguments).get("card"): a for a in legal if a.kind == "choose_revealed"}
        for card in reveal.get("cards", []):
            wrapper = self._image_card(body, card["code"], uid=None, factor=3,
                                       selected=card["id"] in selected, click=False,
                                       compact_label=self._card_name(card["code"]))
            if card["id"] in actions:
                action = actions[card["id"]]
                for child in wrapper.winfo_children():
                    child.bind("<Button-1>", lambda _event, a=action: self.perform(a), add="+")
                wrapper.bind("<Button-1>", lambda _event, a=action: self.perform(a), add="+")
        closer = reveal.get("end_player", reveal.get("closer", reveal.get("opponent")))
        can_close = closer is None or closer == self.env.current_player
        if reveal.get("kind") == "display":
            end = next((a for a in legal if a.kind == "end_reveal"), None)
            if end is not None and can_close:
                ttk.Button(popup, text="施放者结束展示 / Caster ends reveal",
                           command=lambda a=end: self.perform(a)).pack(pady=6)
        else:
            confirm = next((a for a in legal if a.kind == "confirm_revealed"), None)
            if confirm is not None:
                ttk.Button(popup, text=self.action_text(confirm),
                           command=lambda a=confirm: self.perform(a)).pack(pady=6)

    def _render_decision_bar(self, decision, legal):
        """Render target/choice instructions in the persistent bottom bar."""
        kind = decision.get("kind", "choice")
        if kind == "target":
            prompt = "选择目标：点击场上或基地中的合法卡牌"
        elif kind == "discard":
            prompt = "选择要弃置的牌：点击手牌中的目标"
        elif kind == "predict":
            prompt = "洞察：选择保留或回收牌库顶牌"
        elif kind == "unit_target":
            prompt = "选择技能目标：点击场上或基地中的合法单位"
        elif kind == "field":
            prompt = "选择战场：点击战场区域"
        elif kind == "chain_target":
            prompt = "选择要无效化的结算链项目：点击右侧结算链中的卡牌"
        elif decision.get("accelerate"):
            domains = "/".join(decision["accelerate"].get("domains", []))
            prompt = (f"加速：可先横置/回收符文支付 1 法力 + {domains} 符能，"
                      "然后确认单位活跃入场；也可跳过")
        else:
            prompt = f"等待选择：{kind}"
        tk.Label(self.actions, text=prompt, bg="#101b2b", fg="#f3d58b").pack(side="left", padx=4)
        if kind == "predict":
            for action in legal:
                ttk.Button(self.actions, text=self.action_text(action),
                           command=lambda a=action: self.perform(a)).pack(side="left", padx=2)
            return
        if decision.get("multi"):
            count = len(self.selected_decision_targets)
            maximum = decision.get("max", decision.get("count", 1))
            sequence = "；重复点击按顺序分配" if decision.get("allow_repeat") else ""
            tk.Label(self.actions, text=f"已选 {count}/{maximum}{sequence}",
                     bg="#101b2b", fg="#dbe8f7").pack(side="left", padx=4)
            ttk.Button(self.actions, text="确认目标 / Confirm",
                       command=self.commit_decision_targets).pack(side="left", padx=2)
            ttk.Button(self.actions, text="取消 / Cancel",
                       command=self.cancel_decision_targets).pack(side="left", padx=2)
            self._render_target_window(decision)
        else:
            self._close_target_window()
            # Keep a text fallback for targets whose card is not visible in the
            # current private view; normal interaction remains card clicking.
            for action in legal:
                ttk.Button(self.actions, text=self.action_text(action),
                           command=lambda a=action: self.perform(a)).pack(side="left", padx=2)

    def _render_optional_bar(self, optional, legal):
        """Keep optional trigger confirmation in the persistent bottom bar.

        Optional triggers are queued by the rules engine.  Showing both choices
        here avoids an extra modal dialog and makes the order visible when more
        than one optional effect is waiting.
        """
        effect_names = {
            "channel_rune": "横置一枚符文",
            "return_champion": "将指定英雄移回英雄区",
            "spend_buff_draw": "移除增益并抽一张牌",
            "ready_runes": "重置至多两枚符文",
            "recycle_top_two": "将牌库顶两张牌循环至底部",
            "reaver_recall": "选择一个友军移回基地",
            "recall_defender": "将目标单位移回基地",
            "qiyana_conquer": "Qiyana：抽牌或横置引导符文",
            "play_flame_chompers": "Flame Chompers：支付 Fury 从弃牌区打出",
        }
        name = effect_names.get(optional.get("effect"), optional.get("effect", "可选效果"))
        tk.Label(self.actions, text=f"可选效果（P{optional.get('player')}）：{name}",
                 bg="#101b2b", fg="#f3d58b").pack(side="left", padx=4)
        options = [a for a in legal if a.kind == "optional_effect"
                   and json.loads(a.arguments).get("optional") == optional.get("id")]
        order_options = [a for a in legal if a.kind == "order_optional"]
        if order_options:
            tk.Label(self.actions, text="请先确认同时触发的顺序：",
                     bg="#101b2b", fg="#dbe8f7").pack(side="left", padx=4)
            for action in order_options:
                ttk.Button(self.actions, text=self.action_text(action),
                           command=lambda a=action: self.perform(a)).pack(side="left", padx=2)
            return
        for action in options:
            ttk.Button(self.actions, text=self.action_text(action),
                       command=lambda a=action: self.perform(a)).pack(side="left", padx=2)
        tk.Label(self.actions, text="可选效果按队列顺序逐项确认；同时触发时可依次选择。",
                 bg="#101b2b", fg="#9fb4ce").pack(side="right", padx=4)

    def opponent_step(self):
        self._opponent_job = None
        if self.env.done or self.env.current_player == 0:
            return
        legal = self.env.legal_actions()
        if not legal:
            return
        action = self.opponent.choose(self.env.observe(1), legal) if self.opponent else legal[0]
        try:
            before_obs = self.env.observe(0)
            self.env.step(action)
            self.log_add(f"对手：{self.action_text(action)}")
            self._log_transition(before_obs, self.env.observe(0))
            self.render()
        except Exception as error:
            self.log_add(f"对手操作错误：{error}")

    def show_decision_dialog(self):
        if self.env.done or self.env.current_player != 0 or self.env.observe(0)["phase"] != "decision":
            return
        actions = self.env.legal_actions()
        if not actions:
            return
        first = json.loads(actions[0].arguments)
        title = "洞察 / Vision" if first.get("recycle") is not None else "弃牌选择"
        self.choose_action(actions, title)


def main(*, variant="starter", extra_fields=()):
    OriginsGUI(variant=variant, extra_fields=extra_fields).mainloop()


if __name__ == "__main__":
    main()

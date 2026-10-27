"""Local card-table client for the executable Origins subset.

The table is deliberately a thin view over :class:`OriginsRules`: every
button, drag, and context-menu entry is created from a legal engine action.
Card art is bundled at a small display resolution so the client works offline.
"""
from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .engine import Environment, InvalidAction
from .origins import OriginsRules
from .policies import GreedyPolicy
from .support import daughter_deck, starter_deck, vision_deck


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
        self.labels = {}
        self._photo_cache = {}
        self._high_photo_cache = {}
        self._hover_job = None
        self._preview = None
        self._decision_signature = None
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
                                        values=("starter", "vision", "daughter"))
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
        self.board.grid_rowconfigure(2, weight=1, minsize=300)
        self._panel("opponent", "对手区域 / Opponent", 0, height=345)
        self._panel("battlefields", "战场区 / Battlefields", 1, height=390)
        self._panel("player", "我方区域 / Player", 2, height=300)
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

    def _image_card(self, parent, code, *, uid=None, zone=None, owner=None, factor=3,
                    private=False, compact_label=None, click=True, exhausted=False,
                    selected=False, pack=True, show_label=True):
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
        if uid is not None and click:
            button.bind("<ButtonPress-1>", lambda event, u=uid: self.start_drag(event, u, zone))
            button.bind("<ButtonRelease-1>", lambda event, u=uid: self.end_drag(event, u, zone))
            button.bind("<Button-3>", lambda event, u=uid: self.card_menu(event, u))
            if zone == "hand":
                # The wrapper catches the opening hand click as well as the
                # image button, which avoids losing the first mulligan click
                # when the fan is rebuilt during initial rendering.
                wrapper.bind("<Button-1>", lambda event, u=uid: self.start_drag(event, u, zone))
        return wrapper

    def _stack(self, parent, cards, *, owner=None, title="", limit=4, factor=4, count=None):
        frame = self._subzone(parent, title)
        frame.pack(side="left", fill="y", padx=3)
        cards = list(cards)
        if not cards:
            self._image_card(frame, BACK_CODE, factor=factor, compact_label="空")
        else:
            for card in cards[-limit:]:
                self._image_card(frame, card["code"], owner=owner, factor=factor,
                                 compact_label=self._card_name(card["code"]), click=False)
        shown_count = len(cards) if count is None else count
        tk.Label(frame, text=f"{shown_count} 张", bg="#24364d", fg="#d6e3f5").pack()
        return frame

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
        self.variant = selected if selected in {"starter", "vision", "daughter"} else "starter"
        self.rules = OriginsRules(self._decks(), extra_fields=self.extra_fields)
        self.env = Environment(self.rules, max_steps=3000)
        self.env.reset(seed=self.seed)
        self.selected_units.clear()
        self.selected_mulligan.clear()
        self._decision_signature = None
        self._winner_announced = False
        self._log_seq = 0
        self.log_clear()
        self.log_add(f"已用种子 {self.seed} 重新开始。")
        self.render()

    def _decks(self):
        deck = (vision_deck() if self.variant == "vision" else
                daughter_deck() if self.variant == "daughter" else starter_deck())
        return [deck, deck]

    def show_scope(self):
        messagebox.showinfo(
            "当前范围",
            "RUP5 2026-10-09\n双人 Duel；96 张显式实现的 Origins 卡牌。\n\n"
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
        menu = tk.Menu(self, tearoff=False)
        actions = []
        for action in self.env.legal_actions():
            args = json.loads(action.arguments)
            if uid in {args.get("card"), args.get("unit"), args.get("target")}:
                actions.append(action)
        if not actions:
            menu.add_command(label="当前没有合法操作", state="disabled")
        else:
            for action in actions:
                menu.add_command(label=self.action_text(action),
                                 command=lambda a=action: self.perform(a))
        menu.tk_popup(event.x_root, event.y_root)

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
            "legend_spell_power": "传奇能力 / Spell rainbow power",
            "legend_recruit": "传奇能力 / Recruit token",
            "legend_channel": "传奇能力 / Channel exhausted rune",
            "end_turn": "结束回合 / End turn", "pass": "让过 / Pass", "commit_move": "确认移动 / Commit",
            "cancel_move": "取消移动 / Cancel", "select_unit": "选择单位 / Select unit",
            "assign_damage": "分配伤害 / Assign damage",
            "predict": "洞察 / Vision：" + ("回收牌顶" if args.get("recycle") else "保留牌顶"),
            "discard_card": "弃置此牌 / Discard",
            "mulligan": "调度 / Mulligan：" + ("、".join(str(i + 1) for i in args.get("slots", [])) or "不换牌"),
        }
        text = names.get(action.kind, action.kind)
        if action.kind in {"exhaust_rune", "recycle_rune"}:
            text += " · " + self._rune_name(args.get("rune"))
        if action.kind == "play_unit":
            text += " → " + str(args.get("location"))
        if action.kind == "play_spell":
            text += " → " + ",".join(args.get("targets", []))
        if action.kind == "order_triggers":
            text = "触发顺序：" + " → ".join(str(i + 1) for i in args.get("order", []))
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

    def perform(self, action):
        try:
            before = self.env.current_player
            self.env.step(action)
            self.log_add(f"玩家 {before}：{self.action_text(action)}")
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
        items = list(reversed(obs.get("chain") or []))
        items += [{**item, "pending": True} for item in (obs.get("pending") or [])]
        if not items:
            tk.Label(body, text="当前没有待结算项目", bg="#1b2a3e", fg="#9fb4ce",
                     justify="left", wraplength=180).pack(pady=10)
            return
        for index, item in enumerate(items):
            effect = item.get("effect")
            code = item.get("code") if effect == "spell" else self._chain_source_code(obs, item)
            if not code:
                code = BACK_CODE
            card = tk.Frame(body, bg="#31445f", padx=2, pady=2)
            x = 4 + (index % 2) * 98
            y = 4 + (index // 2) * 88
            card.place(x=x, y=y, width=92, height=84)
            self._image_card(card, code, factor=7, compact_label="", click=False,
                             pack=True, show_label=False)
            label = "法术" if effect == "spell" else "技能虚影"
            if item.get("pending"):
                label += " · 待排序"
            tk.Label(card, text=label, bg="#31445f", fg="#dbe8f7",
                     font=("TkDefaultFont", 7, "bold")).place(relx=.5, rely=.9, anchor="center")

    def _state_summary(self, obs):
        phases = {
            "mulligan": "调度阶段", "main": "主要阶段",
            "chain": "结算链", "trigger_order": "触发顺序",
            "showdown": "对决结算", "damage": "战斗伤害分配",
            "move_select": "移动选择", "decision": "效果选择",
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
        return "\n".join(parts)

    def render(self):
        obs = self.env.observe(0)
        if obs["phase"] != "main" or obs["to_act"] != 0:
            self.selected_units.clear()
        if obs["phase"] != "mulligan" or obs["to_act"] != 0:
            self.selected_mulligan.clear()
        turn_text = "玩家 0 行动" if obs["to_act"] == 0 else "对手行动"
        self.status.configure(text=f"回合 {obs['turn']} · {turn_text} · 比分 {obs['points'][0]}–{obs['points'][1]} / {obs['victory']}")
        self.state_bar.configure(text=self._state_summary(obs))
        self.render_opponent(obs)
        self.render_battlefields(obs)
        self.render_player(obs)
        self.render_chain(obs)
        self.render_banishment(obs)
        self.render_actions()
        if obs["phase"] == "decision" and obs["to_act"] == 0:
            signature = json.dumps(obs["decision"], sort_keys=True)
            if signature != self._decision_signature:
                self._decision_signature = signature
                self.after_idle(self.show_decision_dialog)
        else:
            self._decision_signature = None
        if obs["winner"] is not None and not self._winner_announced:
            self._winner_announced = True
            messagebox.showinfo("对局结束", f"玩家 {obs['winner']} 获胜。")

    def render_opponent(self, obs):
        body = self._clear("opponent")
        body.grid_rowconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=0, minsize=120)
        # Match the player's left-to-right arrangement: identity, runes,
        # hand, piles, status.  Keeping the rune pool beside the hand also
        # gives it the same usable height and width as the player's pool.
        body.grid_columnconfigure(1, weight=1, minsize=280)
        body.grid_columnconfigure(2, weight=2, minsize=420)
        body.grid_columnconfigure(3, weight=0, minsize=250)
        body.grid_columnconfigure(4, weight=0, minsize=100)
        identity = tk.Frame(body, bg="#1b2a3e")
        identity.grid(row=0, column=0, sticky="nsw")
        self._identity(identity, obs, 1, compact=True)
        rune_zone = self._subzone(body, "对手符文区", width=280)
        rune_zone.grid(row=0, column=1, sticky="nsew", padx=4)
        self._fan(rune_zone, obs["players"][1]["runes"],
                  lambda parent, rune: self._rune_card(parent, rune, player=1,
                                                        pack=False, show_label=False),
                  per_row=10, row_height=130)
        hand = self._subzone(body, f"对手手牌 · {obs['players'][1]['hand_count']} 张", width=500)
        hand.grid(row=0, column=2, sticky="nsew", padx=4)
        self._fan(hand, range(min(10, obs["players"][1]["hand_count"])),
                  lambda parent, _item: self._image_card(parent, BACK_CODE, factor=4,
                                                         compact_label="", pack=False, show_label=False),
                  per_row=10, row_height=135)
        piles = self._subzone(body, "对手牌堆 / Opponent Piles", width=250)
        piles.grid(row=0, column=3, sticky="nsew", padx=4)
        self._stack(piles, obs["players"][1]["trash"], owner=1,
                    title="P1 弃牌 / Trash", factor=5)
        self._stack(piles, [], title="牌库 / Deck", factor=5,
                    count=obs["players"][1]["main_count"])
        self._status_box(body, obs, 1, column=4)
        base_zone = self._subzone(body, "对手基地 / Opponent Base", height=120)
        base_zone.grid(row=1, column=0, columnspan=5, sticky="ew", padx=4, pady=(3, 0))
        base = tk.Frame(base_zone, bg="#263a54")
        base.pack(fill="both", expand=True)
        for unit in [u for u in obs["units"] if u["location"] == "base:1"]:
            self._image_card(base, unit["code"], uid=unit["id"], owner=unit["owner"],
                             zone="base", factor=4,
                             compact_label=f"P{unit['owner']} · M{unit['might']}",
                             exhausted=unit["exhausted"], selected=unit["id"] in self.selected_units)

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
        frame = self._subzone(parent, f"P{player} 状态", width=110)
        if column is None:
            frame.pack(side="left", fill="y", padx=3)
        else:
            frame.grid(row=row, column=column, sticky="nse", padx=4)
        row = obs["players"][player]
        text = (f"能量 {row['energy']}\n力量 {' '.join(row['power']) or '—'}\n"
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
            field_card_zone = tk.Frame(frame, bg="#263a54", width=82)
            field_card_zone.pack(side="left", fill="y", padx=(0, 4))
            field_card_center = tk.Frame(field_card_zone, bg="#263a54")
            field_card_center.pack(expand=True)
            self._image_card(field_card_center, field["code"], factor=4,
                             compact_label="战场卡", click=False)
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
                damage_label = f"{unit['damage']}伤" + (f" / 待{pending}" if pending else "")
                row = player_row if unit["owner"] == 0 else opponent_row
                self._image_card(row, unit["code"], uid=unit["id"], owner=unit["owner"],
                                 zone="field", factor=5,
                                 compact_label=f"P{unit['owner']} · M{unit['might']} · {damage_label}",
                                 exhausted=unit["exhausted"], selected=unit["id"] in self.selected_units)
    def render_player(self, obs):
        body = self._clear("player")
        body.grid_rowconfigure(0, weight=0, minsize=120)
        body.grid_rowconfigure(1, weight=1, minsize=170)
        body.grid_columnconfigure(1, weight=1, minsize=300)
        body.grid_columnconfigure(2, weight=2, minsize=500)
        body.grid_columnconfigure(3, weight=0, minsize=100)
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

        hand_zone = self._subzone(body, f"手牌 / Hand · {len(obs['hand'])} 张", width=500)
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
        bases = self._subzone(body, "我方基地 / Player Base", height=120)
        bases.grid(row=0, column=0, columnspan=5, sticky="nsew", padx=3, pady=(2, 0))
        # The outer player-base zone already provides the label and border;
        # use it directly so there is no redundant nested "P0 基地" panel.
        base = bases
        base._base_player = 0
        for unit in [u for u in obs["units"] if u["location"] == "base:0"]:
            self._image_card(base, unit["code"], uid=unit["id"], owner=unit["owner"],
                             zone="base", factor=4,
                             compact_label=f"P{unit['owner']} · M{unit['might']}",
                             exhausted=unit["exhausted"], selected=unit["id"] in self.selected_units)
        piles = self._subzone(body, "牌堆 / Player Piles", width=250)
        piles.grid(row=1, column=4, sticky="nsew", padx=4)
        self._stack(piles, obs["players"][0]["trash"], owner=0,
                    title="P0 弃牌 / Trash", factor=5)
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
        if self.env.current_player != 0:
            tk.Label(self.actions, text="对手正在自动决策…", bg="#101b2b", fg="#c7d7eb").pack(side="left")
            if self._opponent_job is None:
                self._opponent_job = self.after(300, self.opponent_step)
            return
        mulligans = [a for a in legal if a.kind == "mulligan"]
        if mulligans:
            ttk.Button(self.actions, text=f"调度 / Mulligan ({len(self.selected_mulligan)})",
                       command=self.commit_mulligan).pack(side="left", padx=2)
        for action in legal:
            if action.kind in {"end_turn", "pass", "legend_energy", "legend_spell_power",
                               "legend_recruit", "legend_channel",
                               "commit_move", "cancel_move", "order_triggers"}:
                ttk.Button(self.actions, text=self.action_text(action),
                           command=lambda a=action: self.perform(a)).pack(side="left", padx=2)
        prompt = "左键选择/多选单位，再拖到基地/战场移动；右键查看其他操作"
        if self.env.observe(0)["phase"] == "damage":
            prompt = "点击或右键对手单位分配伤害"
        tk.Label(self.actions, text=prompt, bg="#101b2b", fg="#9fb4ce").pack(side="right")

    def opponent_step(self):
        self._opponent_job = None
        if self.env.done or self.env.current_player == 0:
            return
        legal = self.env.legal_actions()
        if not legal:
            return
        action = self.opponent.choose(self.env.observe(1), legal) if self.opponent else legal[0]
        try:
            self.env.step(action)
            self.log_add(f"对手：{self.action_text(action)}")
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

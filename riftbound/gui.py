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
from .support import starter_deck, vision_deck


IMAGE_ROOT = Path(__file__).with_name("data") / "images"
BACK_CODE = "__back__"


class OriginsGUI(tk.Tk):
    """A compact dark card table with private hand information for player 0."""

    def __init__(self, *, seed=42, opponent="greedy", variant="starter", extra_fields=()):
        super().__init__()
        self.title("Riftbound Origins · 自动对战与结算")
        self.geometry("1400x900")
        self.minsize(1100, 760)
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
        self.labels = {}
        self._photo_cache = {}
        self._decision_signature = None
        self._opponent_job = None
        self._winner_announced = False
        self._build()
        self.render()

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
                                        values=("starter", "vision"))
        self.variant_box.set(self.variant)
        self.variant_box.pack(side="right", padx=5)

        self.board = tk.Frame(self, bg="#0e1725")
        self.board.pack(fill="both", expand=True, padx=8, pady=4)
        self.board.grid_columnconfigure(0, weight=1)
        self.board.grid_columnconfigure(1, weight=0, minsize=170)
        self.board.grid_rowconfigure(1, weight=1)
        self._panel("opponent", "对手区域 / Opponent", 0, height=150)
        self._panel("battlefields", "战场区 / Battlefields", 1, height=380)
        self._panel("player", "我方区域 / Player", 2, height=245)
        self._panel("banishment", "放逐区 / Banishment", 0, column=1, rowspan=3, height=675)

        bottom = tk.Frame(self, bg="#101b2b", padx=8, pady=5)
        bottom.pack(fill="x")
        self.actions = tk.Frame(bottom, bg="#101b2b")
        self.actions.pack(fill="x")
        self.log = tk.Text(bottom, height=4, state="disabled", wrap="word",
                           bg="#111d2d", fg="#d6e3f5", insertbackground="white")
        self.log.pack(fill="x", pady=(5, 0))

    def _panel(self, key, title, row, *, column=0, rowspan=1, height):
        frame = tk.LabelFrame(self.board, text=title, fg="#dce9fb", bg="#1b2a3e",
                              padx=6, pady=5, height=height)
        frame.grid(row=row, column=column, rowspan=rowspan, sticky="nsew", padx=3, pady=3)
        frame.grid_propagate(False)
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

    def _card_name(self, code):
        return self.rules.cards.get(code, {}).get("name", code)

    def _image_card(self, parent, code, *, uid=None, zone=None, owner=None, factor=3,
                    private=False, compact_label=None, click=True, exhausted=False):
        wrapper = tk.Frame(parent, bg="#24364d", padx=2, pady=2)
        wrapper.pack(side="left", padx=2, pady=2, anchor="n")
        image = self._photo(BACK_CODE if private else code, factor, horizontal=exhausted)
        color = "#d9a441" if owner == 0 else "#6885a6"
        button = tk.Button(wrapper, image=image, relief="raised", bd=2,
                           bg=color, activebackground="#f6d78b", cursor="hand2")
        button.pack()
        label = compact_label or (self._card_name(code) if code != BACK_CODE else "牌背")
        if label:
            tk.Label(wrapper, text=label, bg="#24364d", fg="#e9f1fc",
                     font=("TkDefaultFont", 8), wraplength=110).pack(fill="x")
        if uid is not None and click:
            button.bind("<ButtonPress-1>", lambda event, u=uid: self.start_drag(event, u, zone))
            button.bind("<ButtonRelease-1>", lambda event, u=uid: self.end_drag(event, u, zone))
            button.bind("<Button-3>", lambda event, u=uid: self.card_menu(event, u))
            button.bind("<Enter>", lambda _event, c=code: self.set_hint(self._card_name(c)))
            button.bind("<Leave>", lambda _event: self.set_hint(""))
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

    def set_hint(self, text):
        self.hint.configure(text=text)

    # ---------- interactions ----------

    def restart(self):
        if self._opponent_job is not None:
            try:
                self.after_cancel(self._opponent_job)
            except tk.TclError:
                pass
            self._opponent_job = None
        selected = self.variant_box.get() or self.variant
        self.variant = selected if selected in {"starter", "vision"} else "starter"
        self.rules = OriginsRules(self._decks(), extra_fields=self.extra_fields)
        self.env = Environment(self.rules, max_steps=3000)
        self.env.reset(seed=self.seed)
        self._decision_signature = None
        self._winner_announced = False
        self.log_clear()
        self.log_add(f"已用种子 {self.seed} 重新开始。")
        self.render()

    def _decks(self):
        deck = vision_deck() if self.variant == "vision" else starter_deck()
        return [deck, deck]

    def show_scope(self):
        messagebox.showinfo(
            "当前范围",
            "RUP5 2026-10-09\n双人 Duel；32 张显式实现的 Origins 卡牌。\n\n"
            "战场数量由规则状态和卡牌效果决定，界面不会手动添加战场。\n"
            "未支持的牌和效果会在开局前拒绝，不会静默当作白板。",
        )

    def log_clear(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def log_add(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start_drag(self, event, uid, zone):
        self.drag_card = (uid, zone, event.x_root, event.y_root)

    def end_drag(self, event, uid, zone):
        if not self.drag_card or self.drag_card[0] != uid:
            return
        started = self.drag_card
        self.drag_card = None
        if abs(event.x_root - started[2]) < 6 and abs(event.y_root - started[3]) < 6:
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
            self.card_menu(event, uid)
            return
        candidates = []
        for action in self.env.legal_actions():
            args = json.loads(action.arguments)
            if action.kind == "play_unit" and args.get("card") == uid and args.get("location") == target:
                candidates.append(action)
            if action.kind == "begin_move" and args.get("destination") == target:
                candidates.append(action)
        if len(candidates) == 1:
            action = candidates[0]
            if action.kind == "begin_move" and zone in {"field", "base"}:
                self.perform(action)
                self.after(20, lambda u=uid: self._select_dragged_unit(u))
            else:
                self.perform(action)
        elif candidates:
            self.choose_action(candidates, "选择拖拽操作")
        else:
            self.log_add("该拖拽位置没有合法操作。")

    def _select_dragged_unit(self, uid):
        if self.env.done or self.env.current_player != 0:
            return
        for action in self.env.legal_actions():
            if action.kind == "select_unit" and json.loads(action.arguments).get("unit") == uid:
                self.perform(action)
                return

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

    def _rune_card(self, parent, rune, *, player):
        wrapper = tk.Frame(parent, bg="#24364d", padx=1, pady=1)
        wrapper.pack(side="left", padx=2, pady=2)
        button = tk.Button(wrapper, image=self._photo(rune["code"], 5, horizontal=rune["exhausted"]), relief="raised", bd=2,
                           bg="#d9a441" if player == 0 else "#6885a6", cursor="hand2")
        button.pack()
        if rune["exhausted"]:
            tk.Label(wrapper, text="横置", bg="#8e2930", fg="white",
                     font=("TkDefaultFont", 8, "bold")).place(relx=.5, rely=.5, anchor="center")
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

    def render(self):
        obs = self.env.observe(0)
        turn_text = "玩家 0 行动" if obs["to_act"] == 0 else "对手行动"
        self.status.configure(text=f"回合 {obs['turn']} · {turn_text} · 比分 {obs['points'][0]}–{obs['points'][1]} / {obs['victory']}")
        self.render_opponent(obs)
        self.render_battlefields(obs)
        self.render_player(obs)
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
        body.grid_columnconfigure(1, weight=2, minsize=320)
        body.grid_columnconfigure(2, weight=1, minsize=260)
        body.grid_columnconfigure(3, weight=0, minsize=90)
        body.grid_columnconfigure(4, weight=0, minsize=100)
        identity = tk.Frame(body, bg="#1b2a3e")
        identity.grid(row=0, column=0, sticky="nsw")
        self._identity(identity, obs, 1, compact=True)
        hand = self._subzone(body, f"对手手牌 · {obs['players'][1]['hand_count']} 张", width=500)
        hand.grid(row=0, column=1, sticky="nsew", padx=4)
        self._flow(hand, range(min(10, obs["players"][1]["hand_count"])),
                   lambda row, _item: self._image_card(row, BACK_CODE, factor=5, compact_label=""),
                   per_row=8)
        rune_zone = self._subzone(body, "对手符文区", width=280)
        rune_zone.grid(row=0, column=2, sticky="nse", padx=4)
        self._flow(rune_zone, obs["players"][1]["runes"],
                   lambda row, rune: self._rune_card(row, rune, player=1), per_row=6)
        discard = tk.Frame(body, bg="#1b2a3e")
        discard.grid(row=0, column=3, sticky="nse", padx=4)
        self._stack(discard, obs["players"][1]["trash"], owner=1,
                    title="P1 弃牌区 / Trash", factor=5)
        self._status_box(body, obs, 1, column=4)

    def _identity(self, parent, obs, player, *, compact=False):
        row = obs["players"][player]
        legend = self._subzone(parent, "传奇区 / Legend")
        legend.pack(side="left", fill="y", padx=2)
        self._image_card(legend, row["legend"], factor=5 if compact else 4,
                         compact_label=("横置" if row["legend_exhausted"] else "就绪"),
                         click=False, exhausted=row["legend_exhausted"])
        champion = self._subzone(parent, "英雄区 / Champion")
        champion.pack(side="left", fill="y", padx=2)
        for card in row["champion"]:
            self._image_card(champion, card["code"], uid=card["id"] if player == 0 else None,
                             owner=player, zone="champion", factor=5 if compact else 4)

    def _status_box(self, parent, obs, player, *, column=None):
        frame = self._subzone(parent, f"P{player} 状态", width=110)
        if column is None:
            frame.pack(side="left", fill="y", padx=3)
        else:
            frame.grid(row=0, column=column, sticky="nse", padx=4)
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
        for index in range(len(obs["fields"])):
            fields.grid_columnconfigure(index, weight=1)
        for index, field in enumerate(obs["fields"]):
            frame = tk.LabelFrame(fields,
                                  text=f"战场 {index + 1} · {self._card_name(field['code'])}\n控制：{field['controller']}",
                                  bg="#263a54", fg="#e9f1fc", padx=4, pady=3)
            frame.grid(row=0, column=index, sticky="nsew", padx=3, pady=2)
            frame._field_index = index
            units = tk.Frame(frame, bg="#263a54")
            units.pack(fill="both", expand=True)
            for unit in [u for u in obs["units"] if u["location"] == index]:
                self._image_card(units, unit["code"], uid=unit["id"], owner=unit["owner"],
                                 zone="field", factor=4,
                                 compact_label=f"P{unit['owner']} · M{unit['might']} · {unit['damage']}伤",
                                 exhausted=unit["exhausted"])
            self._image_card(frame, field["code"], factor=4, compact_label="战场卡", click=False)
        bases = self._subzone(body, "基地区 / Bases")
        bases.grid(row=1, column=0, sticky="ew", padx=2, pady=(2, 0))
        for player in (0, 1):
            base = tk.LabelFrame(bases, text=f"P{player} 基地", bg="#263a54", fg="#e9f1fc", padx=4)
            base.pack(side="left", fill="both", expand=True, padx=3)
            base._base_player = player
            for unit in [u for u in obs["units"] if u["location"] == f"base:{player}"]:
                self._image_card(base, unit["code"], uid=unit["id"], owner=unit["owner"],
                                 zone="base", factor=5,
                                 compact_label=f"P{unit['owner']} · M{unit['might']}",
                                 exhausted=unit["exhausted"])

    def render_player(self, obs):
        body = self._clear("player")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1, minsize=300)
        body.grid_columnconfigure(2, weight=2, minsize=500)
        body.grid_columnconfigure(3, weight=0, minsize=100)
        identity = tk.Frame(body, bg="#1b2a3e")
        identity.grid(row=0, column=0, sticky="nsw")
        self._identity(identity, obs, 0)

        rune_zone = self._subzone(body, "符文区 / Runes · 左键横置 · 右键回收", width=300)
        rune_zone.grid(row=0, column=1, sticky="nsew", padx=4)
        self._flow(rune_zone, obs["players"][0]["runes"],
                   lambda row, rune: self._rune_card(row, rune, player=0), per_row=6)

        hand_zone = self._subzone(body, f"手牌 / Hand · {len(obs['hand'])} 张", width=500)
        hand_zone.grid(row=0, column=2, sticky="nsew", padx=4)
        self._flow(hand_zone, obs["hand"],
                   lambda row, card: self._image_card(row, card["code"], uid=card["id"],
                                                     owner=0, zone="hand", factor=4),
                   per_row=6)

        self._status_box(body, obs, 0, column=3)
        piles = self._subzone(body, "公开牌堆 / Public Piles")
        piles.grid(row=1, column=0, columnspan=4, sticky="ew", padx=3, pady=(2, 0))
        self._stack(piles, obs["players"][0]["trash"], owner=0, title="P0 弃牌区 / Trash", factor=5)
        self._stack(piles, [], title="牌库 / Deck", factor=5, count=obs["players"][0]["main_count"])

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
            ttk.Button(self.actions, text="调度初始手牌…",
                       command=lambda actions=mulligans: self.choose_action(actions, "调度初始手牌")).pack(side="left", padx=2)
        for action in legal:
            if action.kind in {"end_turn", "pass", "legend_energy", "commit_move", "cancel_move", "order_triggers"}:
                ttk.Button(self.actions, text=self.action_text(action),
                           command=lambda a=action: self.perform(a)).pack(side="left", padx=2)
        prompt = "手牌/单位点击或右键；拖到基地/战场执行操作"
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

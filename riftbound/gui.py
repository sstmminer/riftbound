"""Tk graphical client for the explicit Origins subset.

The UI never invents actions: every button/menu/drag resolves to an action from
Rules. It is intentionally local and dependency-free. Right-click a card for
context actions; Vision and discard choices appear as modal dialogs.
"""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk

from .engine import Action, Environment, InvalidAction
from .origins import OriginsRules
from .policies import GreedyPolicy
from .support import FIELD_CODES, starter_deck, vision_deck


class OriginsGUI(tk.Tk):
    def __init__(self, *, seed=42, opponent="greedy", variant="starter", extra_fields=()):
        super().__init__()
        self.title("Riftbound Origins · 自动对战与结算")
        self.geometry("1440x920")
        self.minsize(1040, 700)
        self.variant = variant
        self.extra_fields = list(extra_fields)
        self.rules = OriginsRules(self._decks(), extra_fields=self.extra_fields)
        self.env = Environment(self.rules, max_steps=3000)
        self.env.reset(seed=seed)
        self.seed = seed
        self.opponent = GreedyPolicy() if opponent == "greedy" else None
        self.selected_card = None
        self.drag_card = None
        self.labels = {}
        self._decision_signature = None
        self._build()
        self.render()

    def _build(self):
        top = ttk.Frame(self, padding=8); top.pack(fill="x")
        self.status = ttk.Label(top, text="", font=("TkDefaultFont", 13, "bold")); self.status.pack(side="left")
        self.variant_box = ttk.Combobox(top, state="readonly", width=10,
                                        values=("starter", "vision"))
        self.variant_box.set(self.variant)
        self.variant_box.pack(side="right", padx=4)
        ttk.Button(top, text="增加特殊战场", command=self.add_extra_field).pack(side="right", padx=4)
        ttk.Button(top, text="重新开始", command=self.restart).pack(side="right", padx=4)
        ttk.Button(top, text="规则/范围", command=self.show_scope).pack(side="right", padx=4)
        self.board = tk.Frame(self, bg="#182333"); self.board.pack(fill="both", expand=True, padx=8, pady=4)
        self.board.grid_columnconfigure(1, weight=1); self.board.grid_rowconfigure(2, weight=1)
        self._zone("传奇区 / Legend", 0, 0, rowspan=1)
        self._zone("英雄区 / Champion", 0, 1, rowspan=1)
        self._zone("战场区 / Battlefields（可扩展）", 1, 0, columnspan=3, height=205)
        self._zone("基地与手牌 / Base + Hand", 2, 0, columnspan=3, height=210)
        self._zone("弃牌区 / Trash", 3, 0)
        self._zone("放逐区 / Banishment", 3, 1)
        self._zone("公开状态 / Public", 3, 2)
        bottom = ttk.Frame(self, padding=8); bottom.pack(fill="x")
        self.actions = ttk.Frame(bottom); self.actions.pack(fill="x")
        self.log = tk.Text(bottom, height=6, state="disabled", wrap="word")
        self.log.pack(fill="x", pady=(6, 0))

    def _zone(self, title, row, column, *, rowspan=1, columnspan=1, height=120):
        frame = tk.LabelFrame(self.board, text=title, fg="#e8f0ff", bg="#25344b", height=height,
                              padx=6, pady=5)
        frame.grid(row=row, column=column, rowspan=rowspan, columnspan=columnspan,
                   sticky="nsew", padx=4, pady=4)
        frame.grid_propagate(False)
        frame.pack_propagate(False)
        frame._title = title
        frame._body = tk.Frame(frame, bg="#25344b")
        frame._body.pack(fill="both", expand=True)
        self.labels[title] = frame
        return frame

    def restart(self):
        selected = self.variant_box.get() or self.variant
        if selected not in {"starter", "vision"}:
            selected = "starter"
        self.variant = selected
        self.rules = OriginsRules(self._decks(), extra_fields=self.extra_fields)
        self.env = Environment(self.rules, max_steps=3000)
        self.env.reset(seed=self.seed)
        self._decision_signature = None
        self.log_clear(); self.log_add(f"已用种子 {self.seed} 重新开始。")
        self.render()

    def add_extra_field(self):
        available = [code for code in sorted(FIELD_CODES) if code not in self.extra_fields]
        if not available:
            self.log_add("已达到最多 4 个特殊战场。")
            return
        self.extra_fields.append(available[0])
        self.restart()
        self.log_add(f"新增特殊战场 {available[0]}，正在重新开始对局。")

    def _decks(self):
        deck = vision_deck() if self.variant == "vision" else starter_deck()
        return [deck, deck]

    def show_scope(self):
        messagebox.showinfo("当前范围", "RUP5 2026-10-09\n双人 Duel；32 张显式实现的 Origins 卡牌。\n\n未支持的牌和效果会在开局前拒绝，不会静默当作白板。")

    def log_clear(self):
        self.log.configure(state="normal"); self.log.delete("1.0", "end"); self.log.configure(state="disabled")

    def log_add(self, text):
        self.log.configure(state="normal"); self.log.insert("end", text + "\n"); self.log.see("end"); self.log.configure(state="disabled")

    def _clear(self, title):
        body = self.labels[title]._body
        for widget in body.winfo_children(): widget.destroy()
        return body

    def _card(self, parent, text, *, uid=None, action=None, zone=None, private=False):
        shown = text if not private else "未知手牌"
        button = tk.Button(parent, text=shown, width=17, height=3, bg="#f0c674" if uid else "#b9c7dc",
                           relief="raised", wraplength=125)
        button.pack(side="left", padx=3, pady=3)
        if uid:
            button.bind("<ButtonPress-1>", lambda event, u=uid: self.start_drag(event, u, zone))
            button.bind("<ButtonRelease-1>", lambda event, u=uid: self.end_drag(event, u, zone))
            button.bind("<Button-3>", lambda event, u=uid: self.card_menu(event, u))
            button.bind("<Button-1>", lambda event, u=uid: self.select_card(u), add="+")
        if action:
            button.configure(command=lambda a=action: self.perform(a))
        return button

    def _card_name(self, code):
        return self.rules.cards.get(code, {}).get("name", code)

    def select_card(self, uid):
        self.selected_card = uid
        self.render_actions()

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
        # A drop on a battle/base zone is translated into the matching legal
        # play/move action. The rules engine remains the authority.
        widget = self.winfo_containing(event.x_root, event.y_root)
        target = None
        while widget is not None:
            title = getattr(widget, "_title", "")
            if title.startswith("战场区"):
                try: target = int(getattr(widget, "_field_index", -1))
                except (TypeError, ValueError): target = None
                break
            if title.startswith("基地与手牌"):
                target = "base:0"; break
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
            args = json.loads(action.arguments)
            if action.kind == "select_unit" and args.get("unit") == uid:
                self.perform(action)
                return

    def card_menu(self, event, uid):
        menu = tk.Menu(self, tearoff=False)
        actions = []
        for action in self.env.legal_actions():
            args = json.loads(action.arguments)
            if args.get("card") == uid or args.get("unit") == uid or args.get("target") == uid:
                actions.append(action)
        if not actions:
            menu.add_command(label="当前没有合法操作", state="disabled")
        else:
            for action in actions:
                menu.add_command(label=self.action_text(action), command=lambda a=action: self.perform(a))
        menu.tk_popup(event.x_root, event.y_root)

    def action_text(self, action):
        args = json.loads(action.arguments)
        names = {"play_unit": "打出单位", "play_spell": "施放法术", "begin_move": "移动到目标",
                 "exhaust_rune": "横置符文获得能量", "recycle_rune": "回收符文获得力量",
                 "legend_energy": "传奇能力：获得能量", "end_turn": "结束回合", "pass": "让过",
                 "commit_move": "确认移动", "cancel_move": "取消移动", "select_unit": "选择单位",
                 "assign_damage": "分配伤害", "predict": "洞察：" + ("回收牌顶" if args.get("recycle") else "保留牌顶"),
                 "discard_card": "弃置此牌", "mulligan": "调度 " + ("、".join(str(i + 1) for i in args.get("slots", [])) or "不换牌")}
        text = names.get(action.kind, action.kind)
        if action.kind == "play_unit":
            text += " → " + str(args.get("location"))
        if action.kind == "play_spell":
            text += " → " + ",".join(args.get("targets", []))
        return text

    def choose_action(self, actions, title):
        dialog = tk.Toplevel(self); dialog.title(title); dialog.transient(self); dialog.grab_set()
        ttk.Label(dialog, text=title, padding=8).pack()
        for action in actions:
            ttk.Button(dialog, text=self.action_text(action), command=lambda a=action, d=dialog: (d.destroy(), self.perform(a))).pack(fill="x", padx=12, pady=3)

    def perform(self, action):
        try:
            before = self.env.current_player
            self.env.step(action)
            self.log_add(f"玩家 {before}：{self.action_text(action)}")
            self.render()
        except (InvalidAction, ValueError) as error:
            messagebox.showerror("操作无效", str(error))

    def render(self):
        obs = self.env.observe(0)
        self.status.configure(text=f"回合 {obs['turn']} · {'玩家 0 的行动' if obs['to_act'] == 0 else '等待对手'} · 比分 {obs['points'][0]}–{obs['points'][1]} / {obs['victory']}")
        self.render_zones(obs); self.render_actions()
        if obs["phase"] == "decision" and obs["to_act"] == 0:
            signature = json.dumps(obs["decision"], sort_keys=True)
            if signature != self._decision_signature:
                self._decision_signature = signature
                self.after_idle(self.show_decision_dialog)
        else:
            self._decision_signature = None
        if obs["winner"] is not None:
            messagebox.showinfo("对局结束", f"玩家 {obs['winner']} 获胜。")

    def show_decision_dialog(self):
        if self.env.done or self.env.current_player != 0 or self.env.observe(0)["phase"] != "decision":
            return
        actions = self.env.legal_actions()
        if not actions:
            return
        title = "洞察 / Vision" if json.loads(actions[0].arguments).get("recycle") is not None else "弃牌选择"
        self.choose_action(actions, title)

    def render_zones(self, obs):
        body = self._clear("传奇区 / Legend")
        for player in (0, 1):
            row = obs["players"][player]
            self._card(body, f"P{player} {self._card_name(row['legend'])}\n{'横置' if row['legend_exhausted'] else '就绪'}")
        body = self._clear("英雄区 / Champion")
        for player in (0, 1):
            for card in obs["players"][player]["champion"]:
                self._card(body, f"P{player} {self._card_name(card['code'])}", uid=card["id"] if player == 0 else None, zone="champion")
        body = self._clear("战场区 / Battlefields（可扩展）")
        for index, field in enumerate(obs["fields"]):
            frame = tk.LabelFrame(body, text=f"战场 {index+1} · {self._card_name(field['code'])}\n控制：{field['controller']}", bg="#30445e", fg="white", padx=4)
            frame._field_index = index; frame._title = "战场区"; frame.pack(side="left", fill="both", expand=True, padx=4)
            for unit in [u for u in obs["units"] if u["location"] == index]:
                self._card(frame, f"P{unit['owner']} {self._card_name(unit['code'])}\nM {unit['might']} · 伤害 {unit['damage']}", uid=unit["id"], zone="field")
        body = self._clear("基地与手牌 / Base + Hand")
        for player in (0, 1):
            frame = tk.LabelFrame(body, text=f"P{player} 基地 · 手牌 {obs['players'][player]['hand_count']}", bg="#30445e", fg="white")
            frame.pack(side="left", fill="both", expand=True, padx=4)
            for unit in [u for u in obs["units"] if u["location"] == f"base:{player}"]:
                self._card(frame, f"{self._card_name(unit['code'])}\nM {unit['might']}", uid=unit["id"], zone="base")
            if player == 0:
                for card in obs["hand"]:
                    self._card(frame, self._card_name(card["code"]), uid=card["id"], zone="hand", private=False)
        for title, key in (("弃牌区 / Trash", "trash"), ("放逐区 / Banishment", "banishment")):
            body = self._clear(title)
            for player in (0, 1):
                for card in obs["players"][player][key]:
                    self._card(body, f"P{player} {self._card_name(card['code'])}")
        body = self._clear("公开状态 / Public")
        ttk.Label(body, text=f"阶段：{obs['phase']}\n行动权：玩家 {obs['to_act']}\n牌库：{obs['players'][0]['main_count']} / {obs['players'][1]['main_count']}\n符文：{len(obs['players'][0]['runes'])} / {len(obs['players'][1]['runes'])}", background="#25344b", foreground="white").pack(anchor="nw")

    def render_actions(self):
        for child in self.actions.winfo_children(): child.destroy()
        if self.env.done:
            ttk.Label(self.actions, text="对局已结束").pack(side="left")
            return
        legal = self.env.legal_actions()
        if self.env.current_player != 0:
            ttk.Label(self.actions, text="对手正在自动决策…").pack(side="left")
            self.after(300, self.opponent_step)
            return
        mulligans = [action for action in legal if action.kind == "mulligan"]
        if mulligans:
            ttk.Button(self.actions, text="调度初始手牌…",
                       command=lambda actions=mulligans: self.choose_action(actions, "调度初始手牌")).pack(side="left", padx=2)
        for action in legal:
            if action.kind in {"end_turn", "pass", "legend_energy", "exhaust_rune", "recycle_rune", "commit_move", "cancel_move", "order_triggers"}:
                ttk.Button(self.actions, text=self.action_text(action), command=lambda a=action: self.perform(a)).pack(side="left", padx=2)
        ttk.Label(self.actions, text="手牌/单位可点击或右键；可拖拽到基地或任意战场").pack(side="right")

    def opponent_step(self):
        if self.env.done or self.env.current_player == 0: return
        legal = self.env.legal_actions()
        if not legal: return
        action = self.opponent.choose(self.env.observe(1), legal) if self.opponent else legal[0]
        try:
            self.env.step(action); self.log_add(f"对手：{self.action_text(action)}"); self.render()
        except Exception as error:
            self.log_add(f"对手操作错误：{error}")


def main(*, variant="starter", extra_fields=()):
    OriginsGUI(variant=variant, extra_fields=extra_fields).mainloop()


if __name__ == "__main__":
    main()

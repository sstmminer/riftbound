# 第二至第五弹卡库

`riftbound/data/expansions.json` 是从固定的公开卡牌快照导入的目录数据。当前包含：

| 代码 | 卡组 | 记录数 |
| --- | --- | ---: |
| OGS | Proving Grounds | 24 |
| SFD | Spiritforged | 288 |
| UNL | Unleashed | 288 |
| VEN | Vendetta | 237 |
| RAD | Radiance | 219 |
| 合计 |  | 1056 |

每条记录保留官方 print ID、公开编号、类型、领域、费用、战力、规则文本、勘误状态和图片 URL。包含 promo、star/alternate print 等公开记录时，目录 ID 使用规范化后的官方 print ID，例如 `SFD-227-STAR-221`，不会与普通印刷版本冲突。

导入来源和哈希记录在 `riftbound/data/expansions-source.json`。可用以下命令重新生成：

```bash
python tools/import_expansion_catalog.py \
  --git-ref origin/archive-download
```

查看一个扩展卡组：

```bash
python -m riftbound catalog --set SFD
```

这些记录目前是 **catalog-only**。它们已经可以供卡牌浏览器、构筑器、图片懒加载和后续规则适配器使用，但不会被现有 `OriginsRules` 当作可执行卡牌接受。每张牌需要先注册统一的能力/效果实现，并补充目标窗口、资源支付、替代效果和回归场景后，才能加入可执行集合；不会从规则文本自动猜测效果。

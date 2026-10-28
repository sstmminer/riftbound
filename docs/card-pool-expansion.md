# 第一弹卡池扩展清点

来源：`riftbound/data/origins.json`，共 298 张第一弹基础编号。当前显式执行集为 215 张。

| 机制关键词 | 目录中出现次数 | 当前状态 |
| --- | ---: | --- |
| Reaction | 30 | 仅支持封闭卡池中的部分 Reaction |
| Action | 69 | 仅支持封闭卡池中的部分 Action |
| Hidden / reveal | 20 | 未实现 |
| Deathknell | 8 | 部分实现（OGN-096） |
| Ganking | 13 | 部分实现 |
| Shield | 11 | 部分实现（OGN-054/052/232） |
| Deflect | 7 | 部分实现 |
| Tank | 10 | 部分实现（OGN-054/087/137） |
| Vision | 5 | 部分实现 |
| Discard | 16 | 部分实现 |
| Banish | 8 | 牌区基础设施存在，卡牌效果未完整实现 |
| Recall | 5 | 部分实现 |
| Stun | 12 | 基础状态与分配限制已实现 |
| Mighty | 3 | 部分实现 |
| Assault | 10 | 部分实现 |
| Accelerate | 10 | 部分实现 |
| Legion | 9 | 部分实现 |
| Draw | 42 | 基础抽牌/Burn Out 已实现，卡牌触发未完整实现 |
| Damage | 35 | 基础战斗和有限法术已实现 |
| Heal | 3 | 战斗清理基础治疗已实现 |
| Ready / exhaust | 40 / 48 | 基础状态已实现 |
| Control | 19 | 基础战场控制已实现，控制权效果未完整实现 |
| Rune | 69 | 基础符文资源已实现 |
| Token | 11 | 当前仅支持 Recruit |
| Add / create | 215 | 当前仅支持封闭卡池效果 |

高影响未支持样例包括 OGN-005、OGN-008、OGN-014、OGN-022、OGN-025、OGN-043、OGN-045、OGN-050、OGN-053、OGN-057、OGN-062、OGN-064、多个传奇、符文和战场。

这些统计用于排期，不代表文本关键词可以直接决定结算。卡牌实现必须绑定到明确的时机、事件、替代窗口和选择动作，并通过真实卡牌测试。

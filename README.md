# Riftbound 官方来源离线卡牌资料库

这是实际采集所得的归档，附可持续更新的 Python 项目。**收录范围为本次英文官方图鉴公开的 1,408 条唯一印刷记录；不是已证明涵盖所有发行卡牌的全集。**

## 快照与范围

采集于 2026-10-25 UTC（北京时间 2026-10-26）。精确时间见 manifest、sources 和 runs。

| 系列 | 印刷记录 | 不同完整卡名数（非官方逻辑 ID 数） |
|---|---:|---:|
| OGN / Origins | 352 | 298 |
| OGS / Proving Grounds | 24 | 24 |
| RAD / Radiance | 219 | 178 |
| SFD / Spiritforged | 288 | 235 |
| UNL / Unleashed | 288 | 233 |
| VEN / Vendetta | 237 | 189 |
| 合计 | 1,408 | 跨系列按完整卡名去重为 1,103 |

本次实际原图下载成功 **1,408 / 1,408**，图片总字节数 **1,319,293,613**；全部通过 SHA-256、PNG CRC 和官方尺寸校验。87 条逐印刷已关联勘误、1 条未关联勘误和 5 篇公告级原文共组成 93 条 errata 记录。3 次最初的图片网络失败保留在历史日志中，重试后已全部成功，当前图片失败为 0。

每系列统计和文件校验见 `data/validation.json`、`data/report.json`。本次没有从第三方卡牌数据库取得数据。卡名不作为主键，不同官方印刷 ID 都保留。

**覆盖率必须分清分母：**

- 英文图鉴 HTML 的 `__NEXT_DATA__` → `props.pageProps.page.blades[type=riftboundCardGallery].cards.items` 公开嵌入 1,408 条，已全部提取；具体 blade 类型字符串以原始响应为准。
- 同一个 cards.async.metadata 却给出 `totalItems=1416`、`totalPages=8`、`prefetchAll=true`。1,408 / 1,416 = 99.44%，这是元数据数量比率，不是已经证实的全球发行覆盖率。
- 页面明确提供的相对分页 URL（from=0、200 等）在官网主机返回 404。官方 SDK 静态资源中的发布服务主机也已检查，但云端访问该主机的 robots 被代理拒绝。详细证据保存在 sources。没有猜测缺少的八条 ID 或原因。
- 页面列出六个系列筛选项和 All Sets。公开数组含异画、特殊收藏编号和 SP 编号等印刷记录，但官网是否有未列入本图鉴的其他促销卡无法确认。
- 官网未提供经确认的跨印刷逻辑卡 ID，故 `unique_logical_cards` 为 null；不同卡名数仅为辅助统计，不能当作官方独立卡数。
- 五篇指定勘误均已读取。规则中心出现 Vendetta/Radiance 公告的无尾斜杠链接，归一后与已知公告相同，没有发现额外独立勘误公告。
- **尚有 `Leblanc, Deceiver` 勘误无法准确匹配当前图鉴记录。** 修订前后文本和官方来源已保存，其关联卡牌 ID 为 null；未凭相近名称关联到 LeBlanc 的其他版本。这不证明它就是上述八条差额之一。

因此 `completeness_verified=false`。不要把数据库文件结构通过校验误解为官方全卡完整性已经核实。

## 离线查看

解压后双击 `index.html`，无需安装软件或启动服务器。可按系列、卡名、印刷 ID、规则文本搜索，查看本地原图、图鉴文本及已关联勘误。页面不请求外部脚本、字体或图片。点击官方公告链接才需要联网。

程序查询可直接使用 `data/riftbound.sqlite`。JSON/CSV 文件也可离线读取。CSV 为 UTF-8 BOM，复杂列表字段为 JSON 字符串；用电子表格打开时建议将外部文本按纯文本导入。

## Windows PowerShell 更新

需要 Python 3.10+，以及正常访问官网及官方图片主机的网络。**核心采集器只使用 Python 标准库，无 API 密钥、无第三方 Python 依赖。**

在解压后的 `riftbound-archive` 目录打开 PowerShell：

```powershell
py -3 -m venv .venv
& .\.venv\Scripts\python.exe .\scripts\sync.py
$LASTEXITCODE
Get-Content .\data\report.json -Raw
& .\.venv\Scripts\python.exe .\scripts\audit_sources.py
& .\.venv\Scripts\python.exe .\scripts\validate.py
& .\.venv\Scripts\python.exe .\scripts\build_viewer.py
& .\.venv\Scripts\python.exe .\scripts\package.py
```

也可以运行 `powershell -File .\sync.ps1`，自动执行同步、验证、更新离线查看页和打包，不需激活虚拟环境或修改执行策略。若 `py` 不存在，安装官方 Python Launcher 或把命令换成实际 Python 解释器路径。

macOS/Linux 用 `python3 -m venv .venv`，解释器路径改成 `.venv/bin/python`。

**退出码 2** 表示存在来源错误、缺失或待解析项目；目前分页 404 与未关联勘误会导致此状态。有效的部分数据仍会保存并可离线使用。退出码 0 也不自动证明官方全覆盖；查看范围报告。

更新会重新读取来源，以官方印刷 ID 更新记录，不删除旧卡牌；已经存在且有效的图片跳过，缺失图片重试。原始观察保存在 observations，运行记录保存在 runs。本次发现数和历史累计数分开报告。建议定期执行上述命令，并保留历史 ZIP。

## 离线重建、测试与校验

```powershell
# 不访问网络：对保存的官方响应校验哈希、重新提取和导出，整理图片目录。
& .\.venv\Scripts\python.exe .\scripts\sync.py --offline-rebuild
& .\.venv\Scripts\python.exe .\scripts\audit_sources.py
& .\.venv\Scripts\python.exe .\scripts\validate.py
& .\.venv\Scripts\python.exe -m unittest discover -s .\tests -v
# 简单 SQLite 查询：
& .\.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('data/riftbound.sqlite'); print(c.execute('SELECT set_code,COUNT(*) FROM cards GROUP BY set_code').fetchall())"
```

验证器检查 SQLite integrity/foreign keys、重复 ID、JSON/CSV 每字段往返一致、所有本地图片是否存在、SHA-256 是否与下载日志一致。PNG 校验全部 chunk CRC、结束标记、尺寸是否与官方元数据一致；其他格式做相应结构检查。验证不代表对勘误语义的人工审核或全卡覆盖认证。

`package.py` 在归档目录旁生成 `riftbound-archive.zip` 并刷新 SHA256SUMS.txt，排除 .venv、缓存、临时文件。ZIP 内保持完整目录层次。更新数据后需要重新打包，旧校验和不再适用。

## 公开数据结构与采集约束

本次主要数据来自官方 HTML 内嵌 JSON，不需要浏览器。实际字段包括 id、name、subtitle、publicCode、collectorNumber、set.value、rarity.value、domain.values、energy.value、power.value、might.value、tags.tags、text.richText.body、cardImage。

`cards.cost` 表示能量费用，`power_cost` 为另一种 Power 费用；`cards.power` 按用户要求存储力量值，即官方 Might，不与 Power 费用混淆。未适用于某卡型的字段保持 null，字段缺失统计不自动意味着采集错误。原始完整记录保存在 raw_record，费用、图标等源字段不会遗失。

使用官方 id 作为印刷主键；没有 ID 时只允许源中明确的 set_code + collector_number，不按卡名去重。同 ID 对应冲突图像时不静默合并，会写入错误清单。图鉴完整卡名将源 name/subtitle 组合展示，原始字段仍保留。

图片使用 cardImage.url 原样下载，不改缩略图参数、不猜测高清路径。按官方系列分目录，文件名由印刷 ID 哈希生成，映射在数据库；官方 URL 永久保留。实际源中有不同原生分辨率，以 validation.json 为准。

默认串行，至少间隔 1.5 秒；本次批量图片使用 `--delay 0.5`（每秒最多约 2 个请求），服从更长 Crawl-delay。robots 不可访问或禁止时停止相应主机；robots 404 按无规则处理。429/临时服务错误有限重试，长 Retry-After 不会触发频繁重试。TLS 验证保持启用。没有绕过登录、挑战、访问控制或反爬机制。

先验证前三张图片；若样本全失败，暂停批量。其他错误逐项记录，修复网络后可直接重跑。`--sample-size`、`--delay`、`--max-pages` 可配置，达到分页上限会报告错误。

## 原始文本、生效文本与勘误

- `printed_rules_text` 保存图鉴公开的文本快照；不被勘误覆盖。**官网字段可能已更新，因此仅凭图鉴不能证明这是所有历史印刷版本的实际印字；需要时对照随包原图。** 源 HTML 与 raw_record 保留证据。不能获取的历史文本不反推。
- `errata.original_text` / `revised_text` 从官方公告明确的 `[OLD TEXT]` / `[NEW TEXT]` 标签提取，保留原文，不自动翻译或改写。
- 卡牌关联采用完整名称的规范化精确匹配（忽略大小写和标点）。无完整名匹配时，只在源短名对应唯一完整规则名称时使用短名；不会用模糊匹配。
- 同名规则身份的多个印刷 ID 分别建立勘误记录，避免只关联其中一张异画。最新文本按已核实公告日期选择；日期缺失/冲突则标记待核对。
- `effective_rules_text` 保存最新已关联勘误。若公告仍有未解析/未关联项，无已知勘误的卡牌也保留不确定标记；不能把它们称为“确认无勘误”。已全部核对且无勘误时才使用 `no_official_errata_found`。
- 公告日期仅使用官方结构化 datePublished，不以访问时间或 URL 猜测。每项保留公告 URL、核对时间和原文证据。
- errata 表还包含五条公告级记录（关联 ID 为空），用于保存完整公告及解析状态。查询“逐卡已关联修订数”应筛选 `official_card_id IS NOT NULL`，不要把公告行算作卡牌勘误。

为解决未关联项，可提供经人工核实的 `--errata-reviewed reviewed-errata.json` 数组。每项需 official_card_id、announcement_url、revised_text、evidence，可选 original_text。导入时检查卡牌存在、公告已成功保存、证据及修订文本实际存在于公告正文；人工仍需确认对应卡牌与适用印刷范围。

## 未来官网结构变化

若字段变化，`--mapping mapping.json` 接受规范字段到真实点路径/点路径数组的映射，例如已确认源采用相应结构时：

```json
{"set_code":"set.value.id","set_name":"set.value.label","image_url":"cardImage.url"}
```

额外来源只接受已从正常官方页面发现的公开 URL：

```powershell
& .\.venv\Scripts\python.exe .\scripts\sync.py --extra-gallery-url '官方页面提供的完整HTTPS地址'
```

必要时可用可选普通浏览器模式捕获公开 JSON，不解决挑战、不绕过 403。此模式未在本次归档中使用/验证，需安装：

```powershell
& .\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
& .\.venv\Scripts\python.exe -m playwright install chromium
& .\.venv\Scripts\python.exe .\scripts\sync.py --browser
```

浏览器对选择器/分页的支持有边界，检测到筛选控件会保存 browser_controls.json 并要求范围核对，不能默认为全系列已遍历。

## 目录和官方来源

- data/riftbound.sqlite：cards、errata、sources、download_log、observations、runs。
- data/cards.*、data/errata.*：主要导出；sources.*、download_log.*：访问/下载证据。
- data/raw/：最近成功取得的官方 HTML/JSON/静态脚本原文；sources 含时间、哈希及发现来源。
- data/report.json、data/errors.json、data/validation.json、data/coverage.json、manifest.json：范围、失败与文件完整性。
- images/<系列>/：官方原图；index.html：离线检索；scripts/：采集、验证、浏览页生成与打包。

指定来源均已尝试/读取，最终 HTTP 状态见 sources：

1. https://playriftbound.com/en-us/card-gallery/
2. https://playriftbound.com/en-us/rules-hub/
3. https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
4. https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
5. https://playriftbound.com/en-us/news/rules-and-releases/unleashed-errata-updates/
6. https://playriftbound.com/en-us/news/announcements/vendetta-errata-updates/
7. https://playriftbound.com/en-us/news/announcements/radiance-errata-updates/

官方图片主机：cmsassets.rgpub.io（由官方图鉴直接提供）。content.publishing.riotgames.com 是官网公开静态 SDK 出现的发布服务主机，访问失败已保留；不以其他数据库替代。

卡图、游戏文本和商标权利归 Riot 及其权利人。本项目不授予再发布或商业使用权；使用和更新时遵守官方访问规则。

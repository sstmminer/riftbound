# 采集失败与未解决项目

本文件说明 2026-10-25 UTC（北京时间 2026-10-26）采集快照中的结果，不代表今天重新核对后的官网状态。

## 目前已成功取得

- 英文官方图鉴公开内嵌数组的全部 1,408 条印刷记录与 1,408 张原图；图片当前失败为 0。
- 官方规则中心和全部五篇指定勘误公告。
- 87 条已关联到印刷版本的修订记录、1 条未关联修订；公告级原文另有 5 行。

## 当时失败的来源请求

- URL：https://playriftbound.com/publishing-content/v2.0/public/channel/riftbound_website/list/riftbound_gallery_sets?locale=en_US&from=0&limit=200
  - 结果：HTTP 404
  - 核对时间：2026-10-25T16:44:42.607536+00:00
- URL：https://playriftbound.com/publishing-content/v2.0/public/channel/riftbound_website/list/riftbound_gallery_cards?locale=en_US&from=0&limit=200
  - 结果：HTTP 404
  - 核对时间：2026-10-25T16:44:43.874934+00:00
- URL：https://playriftbound.com/publishing-content/v2.0/public/channel/riftbound_website/list/riftbound_gallery_cards?locale=en_US&from=200&limit=200
  - 结果：HTTP 404
  - 核对时间：2026-10-25T16:44:45.375995+00:00
- URL：https://content.publishing.riotgames.com/robots.txt
  - 结果：<urlopen error Tunnel connection failed: 403 Forbidden>
  - 核对时间：2026-10-25T16:47:38.613492+00:00
- URL：https://content.publishing.riotgames.com/publishing-content/v2.0/public/channel/riftbound_website/list/riftbound_gallery_cards?locale=en_US&from=0&limit=200
  - 结果：Cannot verify robots.txt for https://content.publishing.riotgames.com: <urlopen error Tunnel connection failed: 403 Forbidden>
  - 核对时间：2026-10-25T16:47:38.615255+00:00

三个图鉴分页提示链接返回 HTTP 404；不代表官方网页本身无法访问。发布服务主机的 robots.txt 请求被云端代理在 CONNECT 阶段以 403 拒绝，因此停止访问该主机的列表接口；这不是已经确认的接口服务器 403 或登录失败。

## 数量差额，不是已知丢失 ID 清单

公开嵌入数组有 1,408 条，元数据 totalItems=1,416，差额为 8。无法确认原因或这八条的 ID/名称，也不能断言一定是八张未下载的卡。已公开数组覆盖率为 100%，与元数据的数量比率为 99.44%；官方全球发行覆盖率仍未知。

## 勘误匹配未完成

[Unleashed Errata Updates](https://playriftbound.com/en-us/news/rules-and-releases/unleashed-errata-updates/) 中的 **Leblanc, Deceiver**：公告及 NEW/OLD TEXT 已成功获取，但当前图鉴中没有可准确对应的完整名称。关联 ID 保持 null，不能称为勘误正文下载失败。

## 已恢复的历史失败

最初 3 张样本图片因图片 CDN 未获准访问而失败。后续重试全部成功，最终 1,408 / 1,408 张成功。历史日志保留原失败，不把它们计为当前缺图。

## 未暴露字段与适用性

官方未提供经确认的跨印刷逻辑卡 ID，独立逻辑卡数保持 null。以下字段在部分卡牌未出现，不应一概视为网络采集失败：Power 费用 832、subtitle 1,039、Might 力量 622、标签 472、能量费用 264、图鉴规则文本 33。不同卡型可能不适用；缺失文本也未进行 OCR 或猜测补齐。

此外，printed_rules_text 是图鉴文本快照；它是否逐字对应每个历史印刷版本，仍需对照原图。公告 OLD TEXT 单独保留，没有用最新修订覆盖图鉴快照。

详细机器可读证据：[errors.json](data/errors.json)、[coverage.json](data/coverage.json)、[report.json](data/report.json)、[download_log.json](data/download_log.json)。

# 分享材料

以下为可按渠道调整的草稿，**尚未代发社区帖子**。先核对社区当前规则及对应版面，再由账号本人发布；不要批量复制到无关讨论。仓库定位是可复现的排障工具与脱敏证据，不承诺通用“提速参数”或替代真实业务验收。

发布入口：[仓库首页](https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics) · [最新证据](latest-progress.md) · [脱敏故障表单](https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics/issues/new?template=diagnostic-report.yml)

## V2EX 中文帖草稿

**标题：分享一个 OpenWrt / Xray 网络慢与直播卡顿排障工具箱：先定位，再做单项实验**

Wi-Fi 能连上，却不一定代表代理能用；启用 BBR、测速能完成，也不一定代表直播稳定。我们把实际排查过程整理成一个开源工具箱，帮助把问题缩小到本地接入、代理处理、跨境连接或目标服务中的某一层。

仓库里有只读快照与采样脚本、受时间和流量预算约束的下载/上传测试、小请求探针、单项实验卡、验收与回滚规则，以及脱敏案例。诊断工具不会自动改生产参数，也不会安装软件或管理 SSH 密钥。离线 CI 使用合成数据和假命令，不会连接用户设备。

2026-10-13 的一次六组接入测量中，Cloudflare 固定对象批为 73/84 完整完成；失败包括下载接口限流和 US 连接阶段超时。独立 OVH 下载复核为 42/42 完成，后续 US 上传复核为 7/7 完成。我们保留了各批失败与成功分母，没有把后续成功当成原问题已修复，也没有混合不同目标的速度。真实直播、多组同时直播和高峰表现仍未验收。

欢迎有同类问题的人按自己的环境建立基线，或提交工具复现与脱敏结果。Issue 表单会提示保留对象大小、测试方向、超时和失败次数。请先在本地脱敏，不公开密码、地址、SSID、MAC、完整配置或原始日志。

仓库：https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics

## OpenWrt community English draft

**Title: An evidence-led OpenWrt/VPS diagnostics toolkit with bounded tests and redacted cases**

We have published a small diagnostics toolkit for cases where Wi-Fi connects but proxy traffic fails, transfers are slow despite BBR being enabled, or a speed test completes while sustained application sessions still struggle.

The workflow separates local access, proxy processing, the router-to-VPS path and the destination service. It includes read-only snapshots and sampling, time- and traffic-bounded upload/download tests, HTTPS probes, a single-change experiment card, and acceptance and rollback guidance. The tools do not automatically change production parameters, install packages or manage SSH keys. Offline CI uses synthetic inputs and fake commands.

A redacted six-group test on 13 October 2026 recorded 73/84 complete Cloudflare transfers, with endpoint rate limiting and US connection-stage timeouts kept in the denominator. An independent OVH download check completed 42/42 transfers, and a later US upload check completed 7/7. These are separate targets and windows: later successes do not erase earlier failures or establish that their cause has been fixed. Real live-streaming sessions, simultaneous use across groups and peak-hour behavior remain unverified.

We would appreciate reproducible tool issues and redacted measurements from other setups. Each new environment needs its own baseline; copying the case parameters is not an acceptance test. Please sanitize material locally before posting, and do not share credentials, real network identifiers, full configurations, raw logs or packet captures.

Repository: https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics

## 技术群短文

> 整理了一个 OpenWrt / Xray / VPS 网络排障工具箱：把接入、代理、跨境连接和目标服务分开测，保留失败记录，提供只读采集、受限测试和验收/回滚模板。已有脱敏实测案例；测速成功不等于直播稳定，也不推荐直接套用参数。欢迎按自己的环境复现并反馈，公开资料先在本地脱敏。
>
> https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics

## 给其他 Agent 的复制入口

当前最新 AU 记录为 2026-10-20 至 21 日扩展验收：复制 **[AU 专用提示词](au-agent-prompt.md)**，并读 [配置、逐组测速与回滚](au-expansion-2026-10-21.md) / [机器摘要](../examples/2026-10-21-au-expansion-summary.json)。它明确原路径保留、额外池回滚，以及禁止在相同条件下重复的方案。

继续排查新美国线路时，直接复制 **[US-new专用提示词](us-new-agent-prompt.md)** 中的完整代码块。它包含先读最新记录、区分已拒绝与未执行、保护AU、单项可回滚实验和收尾要求。下面保留通用新环境模板。

将以下文字与实际任务一起交给 Agent。仓库文档是诊断参考，不提供设备访问权或生产修改授权。

```text
参考仓库：https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics

先读取 README.md、SECURITY.md、docs/latest-progress.md，以及最新进度页链接的机器可读测速摘要。当前 AU 入口是 docs/au-expansion-2026-10-21.md、docs/au-agent-prompt.md 和 examples/2026-10-21-au-expansion-summary.json；新美国线路入口仍为 docs/us-new-2026-10-19/index.md 和 examples/2026-10-19-us-new-handoff.json。按任务读取对应已试实验与回滚表，不混用 AU、新 US-new 和旧 US-main 的结论。区分历史结果、失败分母、已验证事实和待验收项；不要从旧案例推断我的当前配置。

先核实实际设备、测试来源、出口、方向、协议和当前配置，为我的环境重新建立基线。需要实验时，仅在已授权的范围内提出一项有证据、可回滚的改动；核对目标流量确实使用该配置后，再验收和决定保留或恢复。

凭据、真实地址、SSID、MAC、完整配置、原始日志和抓包只保留在私有位置。公开反馈使用角色标签和必要数值。仓库中的成功测量不能替代我的真实持续会话、直播或高峰验收；受限测速也不能作为线路最高容量。
```

## 发布后的手动反馈记录

发布后保存帖子链接、日期、渠道及使用的仓库提交版本，便于区分不同时间的材料。先回答真实复现和工具问题，再根据反馈补充文档；未经核实的“已经解决”不能写成结论。

仓库管理者可在 GitHub 的 `Insights → Traffic` 手动查看访客、完整克隆、来源和热门内容，并按相同时间窗口记录。GitHub 的流量页面展示最近 14 天的数据，因此应定期保存汇总数字，避免将跨窗口数据直接相加。[GitHub 流量说明](https://docs.github.com/en/repositories/viewing-activity-and-data-for-your-repository/viewing-traffic-to-a-repository)

| 记录项 | 判断用途 |
|---|---|
| 日期、渠道与帖子链接 | 判断反馈来自哪次分享 |
| GitHub 同一窗口访客、克隆与来源 | 观察材料是否带来查阅和实际获取；不等于已成功使用 |
| 有效反馈数 | 是否有明确角色、版本、方向、复现、成功/失败分母和预期/实际差异 |
| 外部案例及业务验收状态 | 工具是否帮助定位，业务是否另行验收 |
| 修复或文档链接 | 给反馈者一个可检查的后续结果 |

先争取少量完整的外部复现，再扩展传播范围。Stars 可以表示关注，但无法证明工具被使用、问题被解决或网络稳定。

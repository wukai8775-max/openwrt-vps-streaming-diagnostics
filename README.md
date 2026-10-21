<p align="center">
  <img src="assets/banner.svg" alt="OpenWrt / VPS 网络诊断：先测量，再定位和验收" width="100%">
</p>

<p align="center">
  <strong>简体中文</strong> · <a href="README.en.md">English</a> ·
  <a href="docs/beginner-check.md">新手入口</a> ·
  <a href="docs/result-examples.md">结果示例</a> ·
  <a href="docs/cases.md">案例与历史</a>
</p>

<p align="center">
  <a href="https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics/actions/workflows/ci.yml"><img src="https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics/actions/workflows/ci.yml/badge.svg" alt="Offline verification"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB.svg" alt="Python 3.10 or newer">
</p>

# OpenWrt / VPS 网络诊断工具箱

**先从自己的电脑得到一份能读懂的检查结果，再决定查哪一层。** 不需要服务器账号或路由器密码；不会自动修改网络配置。适用于 OpenWrt/Kwrt、PassWall/Xray、VPS 网络的分步排查。

| 你的问题 | 先得到什么 |
|---|---|
| Wi-Fi 能连，网站打不开 | 小请求成功/失败，以及解析、连接、TLS 等阶段线索 |
| 显示下载很快，却总是中断 | 完整对象与部分下载分别计数，避免误读速度 |
| 测速通过，通话或直播仍卡 | 先建立基线，再按进阶指南验证负载与真实业务 |

## 第一次运行：先看报告，不联网

需要 **Python 3.10+**，不用安装 pip 依赖：

```sh
git clone https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics.git
cd openwrt-vps-streaming-diagnostics
python3 tools/quick-check.py
```

默认是**离线合成演示，不能当成你的网络实测**。示例展示：小请求 3/3 成功，固定对象下载 1/2 完整、1 次部分超时；部分下载没有成功吞吐。完整输出与解释见 [结果示例](docs/result-examples.md)。

## 检查自己的网络：只加一个参数

真实检查另需 **curl 8.4+**：

```sh
python3 tools/quick-check.py --execute
```

最多发出 **3 次 IPv4 HTTPS 小请求**，每次最多 5 秒、响应体预算 64 KiB；默认不下载测速文件，不需要手填源地址或 SSH 信息。结果提供下一步检查方向，不会自动调参。目标、预算和使用范围见 [新手诊断入口](docs/beginner-check.md)。

`--plan` 只看预算；`--json` 输出同一份脱敏结构化结果。可选固定对象测试必须另给 `--download-url` 和精确 `--bytes`，详见入门页。

## 怎样理解结果

- **小请求通过：** 说明本次目标请求完成；线路容量、指定节点和直播稳定性仍需单独验证。
- **收到部分数据后超时：** 保留失败，不把未完成下载当成成功测速。
- **HTTP 429：** 停止该目标分支并尊重等待要求；先检查目标服务响应，不盲目修改 TCP 参数。

检查使用系统当前 IPv4 路由，禁用 curl 显式代理；透明代理或 VPN 仍可能影响路径。它不会自动确认你连到哪组 Wi-Fi、哪个代理节点。见 [结果判读与边界](docs/result-examples.md)。

## 下一步去哪

| 需要 | 入口 |
|---|---|
| 第一次诊断、保存与读懂结果 | [新手指南](docs/beginner-check.md) · [结果示例](docs/result-examples.md) |
| 绑定指定来源、准备路由器/VPS 快照 | [进阶准备](docs/advanced-start.md) · [采集与测量](docs/measurement-guide.md) |
| 区分接入、代理、TCP、目标服务 | [排障路径](docs/decision-tree.md) · [单项实验卡](docs/experiment-card.md) |
| 核对稳定性或恢复改动 | [验收与回滚](docs/acceptance-and-rollback.md) |
| 阅读实测与已拒绝方案 | [案例与历史索引](docs/cases.md) · [最新进度](docs/latest-progress.md) |
| 让其他 Agent 接手 | [AU 提示词](docs/au-agent-prompt.md) · [US-new 提示词](docs/us-new-agent-prompt.md) |

## 工具与反馈

`tools/` 提供客户端入门检查、固定对象上下行、HTTPS/STUN 探针、两端只读采样和离线汇总。历史 AU、US 报告及机器摘要全部保留在 [案例索引](docs/cases.md)，不同节点、批次、失败与回滚继续分别记录。

提交问题请带上条件、完整/尝试次数和已经做过的改动：[故障表单](https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics/issues/new?template=diagnostic-report.yml)。原始日志、真实地址、网络标识、凭据、完整配置与分享链接留在私有位置；入门报告已排除这些标识，发布前仍需人工检查。[公开边界](SECURITY.md)

[贡献指南](CONTRIBUTING.md) · [环境记录](docs/environment.md) · [分享材料](docs/share-kit.md) · [更新日志](CHANGELOG.md) · [MIT License](LICENSE)

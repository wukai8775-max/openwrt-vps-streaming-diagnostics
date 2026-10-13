# 首页排版与视觉参考

本次参考日期为 **2026-10-13**。Star 数是 GitHub 官方 API 的当日观察，数字会变化；关注度不能证明某种排版带来增长。

| 官方项目 | 当日观察 | 借鉴的结构 |
|---|---:|---|
| [Uptime Kuma](https://github.com/louislam/uptime-kuma) | 92,405 Stars | 简短定位、状态徽章、视觉预览，随后给最短上手入口 |
| [Netdata](https://github.com/netdata/netdata) | 80,922 Stars | 首屏短导航，把长篇内容分层，引导到上手、文档、社区和贡献 |
| [AdGuard Home](https://github.com/AdguardTeam/AdGuardHome) | 37,393 Stars | 清楚的用途、预览、快速开始与已知限制，完整的贡献和隐私入口 |

数值来源：[Uptime Kuma API](https://api.github.com/repos/louislam/uptime-kuma)、[Netdata API](https://api.github.com/repos/netdata/netdata)、[AdGuard Home API](https://api.github.com/repos/AdguardTeam/AdGuardHome)。

## 本仓库的具体选择

首页顺序为：原创诊断路径横幅 → 中英文与短导航 → 真实离线 CI / MIT / Python 徽章 → 三种症状 → 离线示例与 dry-run → 调查路径 → 简短最新状态 → 工具与反馈。完整测量成绩继续保存在最新进度页。

图形使用深绿背景、浅色文字和浅绿强调，展示接入、路由器、代理/TCP、目标服务的流程示意。它不是实时仪表盘，不显示虚构的在线设备、带宽或通过率。原始真实数据、失败、长尾及直播待验收状态仍由文档与机器可读摘要承载。

`assets/banner.svg`、`assets/social-preview.svg` 与导出的 PNG 均为本仓库原创。没有复制参考项目的 Logo、界面截图、源代码或产品宣传措辞，也不表示与参考项目有合作或认可关系。SVG 为静态图形，不加载脚本、外部字体或用户数据；PNG 分享图的推荐尺寸为 1280 × 640。

已知限制保持在首页可见：US 原间歇超时没有被后续成功覆盖，AU 多组共享出口，完整文件测试不能代替手机持续直播验收。保留能够帮助访客判断使用范围的信息。

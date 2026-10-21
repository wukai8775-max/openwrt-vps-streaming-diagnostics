# 本案例的路由器与固件环境

[中文首页](../README.md) · [English](../README.en.md) · [最新测速记录](latest-progress.md)

**核验时间：2026-10-14T09:01:57+08:00（Asia/Shanghai）。** 通过已授权 SSH 只读执行 `ubus call system board`，下表只发布产品型号和系统版本等白名单字段。它记录核验时正在运行的系统；不包含设备名称、序列号、地址、SSID、MAC、管理入口或凭据。

| 项目 | 当前设备报告值 | 字段来源 |
|---|---|---|
| 路由器型号 / Model | `Ruijie RG-X60 Pro` | `model` |
| 固件发行版 / Distribution | `Kwrt` | `release.distribution` |
| 固件版本 / Version | `25.12-SNAPSHOT` | `release.version` |
| 构建标识 / Build revision | `10.08.2026` | `release.revision` |
| 完整系统描述 / Description | `Kwrt 25.12-SNAPSHOT 10.08.2026 by Kiddin'` | `release.description` |
| Linux 内核 / Kernel | `6.12.112` | `kernel` |
| 编译目标 / Target | `mediatek/filogic` | `release.target` |
| 设备板型 / Board name | `ruijie,rg-x60-pro` | `board_name` |
| 处理器标识 / Reported CPU system | `ARMv8 Processor rev 4` | `system` |
| 根文件系统 / Root filesystem | `squashfs` | `rootfs_type` |

`10.08.2026` 按设备的 revision 字段原样保留，没有将其推断为刷写日期。固件发行版由设备自报为 **Kwrt**，版本为 **25.12-SNAPSHOT**；本记录不将它替换成官方 OpenWrt 发行版名称。

## 与案例结果的关系

这是 **2026-10-14 的当前环境读回**，不是新一轮测速，也不会把 2026-10-13 的历史测量日期改成今天。此前各批完整成功、失败、响应长尾和真实直播待验收项继续分别保留在 [最新进度](latest-progress.md) 中。其他型号、固件或硬件版本需要重建自己的基线。

本次未核验当时刷入的镜像文件名、下载来源、文件 hash 或刷写日期；设备当前运行字段不能单独证明这些信息。本页也不提供刷写步骤或固件下载建议。

## English summary

Read back on **2026-10-14**: **Ruijie RG-X60 Pro**, running **Kwrt 25.12-SNAPSHOT**, with reported build revision **10.08.2026** and Linux kernel **6.12.112**. Target: `mediatek/filogic`; board: `ruijie,rg-x60-pro`. Values above are the router's reported fields from a read-only `ubus call system board`, not a verified firmware image filename, provenance or flashing date. This current environment check does not change the historical test windows or establish compatibility with another device revision. Device-instance identifiers and credentials remain private; see [public boundaries](../SECURITY.md).

## 后续无线容量快照 · 2026-10-20 至 21 日

AU 扩展后读回：本机 5 GHz 无线电共 **16 个 AP**，为十五个 AU 组和 US-new，达到该驱动报告的 **16 AP** 上限。2.4 GHz 管理无线电独立计数。此处只新增本轮容量观察，不改变上表 10 月 14 日系统版本的核验日期，也没有重新验证镜像来源或刷写时间。

独立子网与 SSID 不增加上游出口、带宽或并发无线容量；继续增加分组前应重新评估接入组织方式与资源，而非直接追加此无线电 BSS。验收范围及短时重关联历史见 [AU 扩展阶段报告](au-expansion-2026-10-21.md)。

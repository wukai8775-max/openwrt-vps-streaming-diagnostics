# RG-X60 PRO 刷机准备：下载、校验与分区区别

[中文首页](../README.md) · [English](../README.en.md) · [历史设备环境](environment.md)

**资料核对日期：2026-11-01（Asia/Shanghai）。本页处于文件准备与静态核验阶段，尚未完成新机刷入、启动或业务验收。** 实际刷机步骤将在这台新机成功刷入并完成验收后补充，届时注明硬件版本、原厂版本、所用文件与恢复条件。

本轮新机铭牌为 **RG-X60 PRO / 硬件 V2.00**，用户确认仍运行锐捷原厂系统；原厂固件版本、实机分区及启动入口尚未读取。铭牌上的硬件版本不能代替固件版本，也不能证明某个镜像或 U-Boot 已适配。以前的设备读回仍保留在[环境记录](environment.md)，不能用来认证新机。

## 1. 先辨认文件用途

| 文件类型 | 本次用途 | 使用前仍需确认 |
|---|---|---|
| Kwrt `squashfs-sysupgrade.bin` | 延续 Kwrt 功能方案的系统候选 | 板型、107 MiB 布局、首次安装入口及启动链 |
| OpenWrt `initramfs-kernel.bin` | 临时内存启动与恢复候选 | 当前启动链能否加载；启动后设备树如何描述闪存 |
| OpenWrt `squashfs-sysupgrade.bin` | 匹配目标与布局的系统升级候选 | 板型及 stock 63 MiB 布局 |
| U-Boot/FIP `.bin` | 引导程序参考文件 | 新机硬件与引导链兼容性，以及是否需要改写引导 |
| 锐捷原厂软件包或原机分区备份 | 回退资料 | 包的实际用途、完整性及是否足以恢复原机 |

`sysupgrade` 文件不能直接当作锐捷原厂网页升级包；U-Boot/FIP 也不能当作系统固件上传。文件名中出现相同型号，仍不足以证明分区和引导方式相同。本仓库提供上游下载链接及核验记录，固件二进制从对应发布者下载。

## 2. 下载来源与固定核验记录

以下是本轮核对的具体版本，不代表永久的最新版本，也不是已验证可刷入新机的组合。字节数与 SHA256 见[机器可读记录](firmware/x60-pro-2026-11-01.json)；四个下载文件的预期值见[下载校验清单](firmware/x60-pro-2026-11-01-downloads.sha256)。

### Kwrt 系统候选

- 发布者入口：[kiddin9/Kwrt](https://github.com/kiddin9/Kwrt) → [RG-X60 Pro 下载目录](https://dl.openwrt.ai/firmware/mediatek-filogic/ruijie_rg-x60-pro/)。Kwrt 是独立发行版，不能标为 OpenWrt 官方镜像。
- 本轮文件：[kwrt-10.28.2026-mediatek-filogic-ruijie_rg-x60-pro-squashfs-sysupgrade.bin](https://dl.openwrt.ai/firmware/mediatek-filogic/ruijie_rg-x60-pro/kwrt-10.28.2026-mediatek-filogic-ruijie_rg-x60-pro-squashfs-sysupgrade.bin)，**45,947,151 bytes**。
- 静态元数据：`Kwrt 25.12-SNAPSHOT`，revision `10.28.2026`，target `mediatek/filogic`，supported device `ruijie,rg-x60-pro`；tar 中 `CONTROL`、`kernel`、`root` 齐全。
- SHA256：`f67cbe51c08ffb72a74e41178612457a913c320f882cba9855425b7e64a0103b`。
- 本轮未找到对应的发布者独立签名或校验清单。这里的 hash 固定本次从作者 HTTPS 来源取得的内容，不等同于独立验签。滚动下载站可能替换同名文件；若下载结果不同，保留差异并重新核对，不能直接改成新 hash 后宣称验证通过。

### OpenWrt 官方系统与恢复候选

来源为 [OpenWrt 25.12.6 官方目录](https://downloads.openwrt.org/releases/25.12.6/targets/mediatek/filogic/)。

| 文件 | 精确大小 | SHA256 |
|---|---:|---|
| [openwrt-25.12.6-mediatek-filogic-ruijie_rg-x60-pro-initramfs-kernel.bin](https://downloads.openwrt.org/releases/25.12.6/targets/mediatek/filogic/openwrt-25.12.6-mediatek-filogic-ruijie_rg-x60-pro-initramfs-kernel.bin) | 9,166,140 bytes | `0ea258afd298a01ac8c2fb7df142400f5dbf899f459291325062e0226b50f73b` |
| [openwrt-25.12.6-mediatek-filogic-ruijie_rg-x60-pro-squashfs-sysupgrade.bin](https://downloads.openwrt.org/releases/25.12.6/targets/mediatek/filogic/openwrt-25.12.6-mediatek-filogic-ruijie_rg-x60-pro-squashfs-sysupgrade.bin) | 9,892,114 bytes | `a7c4e3fba0d59040e6b2b62eeabc7af015644499426ded9d72418cb6a7f63cf3` |

两份文件均与官方 `sha256sums` 一致；该清单的 usign/Ed25519 签名已使用 OpenWrt keyring 中的公钥验证通过。本轮实际使用 Node.js 内置 `crypto.verify` 验证标准 Ed25519 签名，未运行 `usign` CLI；下节另给具备 `usign` 环境时的官方格式命令。签名认证的是校验清单来源，不认证新机的兼容性。

### U-Boot/FIP 参考文件

- 发布页：[hanwckf/bl-mt798x · 20241115](https://github.com/hanwckf/bl-mt798x/releases/tag/20241115)。
- 下载：[bl-mt798x-release-20241115.7z](https://github.com/hanwckf/bl-mt798x/releases/download/20241115/bl-mt798x-release-20241115.7z)，**1,522,540 bytes**；SHA256 `33d17572634ead49c98302cc12797f3ec629eb767306c41791411300349143a7`。
- archive 顶层目标文件：`mt7986_ruijie_rg-x60-pro-fip-fixed-parts-multi-layout.bin`，**834,121 bytes**；SHA256 `8552cbeeb395f59c5f522a021557117f7aa8a08fe52e6ccc33c168bac4e54e02`。
- 7z 内包含多个设备的文件，整理时只提取上述完整文件名。不要直接上传 7z，不要按相似名称选择其他板型。本轮未找到该发布物的独立签名或发布者 checksum；hash 是本次下载与提取的记录。
- 此处提供来源和核对信息，不表示 RG-X60 PRO V2.00 已通过适配，也不表示首次安装必须刷写 U-Boot。是否需要修改引导，等待原厂版本和实机证据。

## 3. 在电脑上下载与校验

从仓库根目录执行下面的下载准备；文件放在已被 Git 忽略的 `results/` 内。这里只访问公开下载源，不连接路由器。需要 `curl`；目录已存在时先检查已有文件，保留不同批次，不覆盖需要留存的下载。

```sh
mkdir -p results/x60-pro-prep-2026-11-01
cd results/x60-pro-prep-2026-11-01

OPENWRT_BASE='https://downloads.openwrt.org/releases/25.12.6/targets/mediatek/filogic'
KWRT_BASE='https://dl.openwrt.ai/firmware/mediatek-filogic/ruijie_rg-x60-pro'

curl --fail --location --proto '=https' --tlsv1.2 --remote-name \
  "$KWRT_BASE/kwrt-10.28.2026-mediatek-filogic-ruijie_rg-x60-pro-squashfs-sysupgrade.bin"
curl --fail --location --proto '=https' --tlsv1.2 --remote-name \
  "$OPENWRT_BASE/openwrt-25.12.6-mediatek-filogic-ruijie_rg-x60-pro-initramfs-kernel.bin"
curl --fail --location --proto '=https' --tlsv1.2 --remote-name \
  "$OPENWRT_BASE/openwrt-25.12.6-mediatek-filogic-ruijie_rg-x60-pro-squashfs-sysupgrade.bin"
curl --fail --location --proto '=https' --tlsv1.2 --remote-name \
  'https://github.com/hanwckf/bl-mt798x/releases/download/20241115/bl-mt798x-release-20241115.7z'
```

每条下载命令都应成功结束，再校验本轮四个文件。下载失败留下的部分文件、下载器的临时文件，以及扩展名为 `.bin` 的 HTML 错误页，都不能当成固件。文件大小只作初筛，以完整 hash 比较为准。

Linux / GNU coreutils：

```sh
sha256sum -c ../../docs/firmware/x60-pro-2026-11-01-downloads.sha256
```

macOS：

```sh
shasum -a 256 -c ../../docs/firmware/x60-pro-2026-11-01-downloads.sha256
```

四项应全部显示 `OK` 且退出码为 `0`。如果只下载了其中一个文件，先运行 `sha256sum '完整文件名'` 或 `shasum -a 256 '完整文件名'`，与上表或 JSON 中同一文件的完整 64 位预期 hash 比较；不要把缺少其他文件的全量检查称为通过。提取 FIP 后同样单独核对它的大小和 hash。

### 进一步认证 OpenWrt 官方清单

本仓库的 hash 是有日期的核对记录；OpenWrt 文件还可以与经过签名的上游清单比较。在刚才的下载目录中保存清单、签名和公钥：

```sh
curl --fail --location --proto '=https' --tlsv1.2 --output openwrt-sha256sums \
  "$OPENWRT_BASE/sha256sums"
curl --fail --location --proto '=https' --tlsv1.2 --output openwrt-sha256sums.sig \
  "$OPENWRT_BASE/sha256sums.sig"
curl --fail --location --proto '=https' --tlsv1.2 --output openwrt-usign.pub \
  'https://raw.githubusercontent.com/openwrt/keyring/master/usign/b5043e70f9a75cde'
```

先通过 [OpenWrt 签名说明](https://openwrt.org/docs/guide-user/security/signatures)与[官方 keyring](https://github.com/openwrt/keyring/blob/master/usign/b5043e70f9a75cde)核对公钥身份；本轮 key ID 为 `b5043e70f9a75cde`。有 `usign` 时运行：

```sh
usign -V -p openwrt-usign.pub -m openwrt-sha256sums -x openwrt-sha256sums.sig
```

签名命令成功后，再在该清单中按完整文件名找到两份 OpenWrt 镜像的 hash，与下载文件计算结果逐一比较。官方清单包含整个目录的其他机型，直接全量运行 `-c` 会报告未下载文件缺失。缺少验签工具或验签失败时，不能宣称已验签；不要跳过失败继续操作。**hash 一致、签名通过和实机兼容是三个不同的结论。**

## 4. 63 MiB 与 107 MiB 的区别

这里的数值描述 **UBI 分区容量**，不是镜像下载大小、内存大小或整块闪存容量。`1 MiB = 1,048,576 bytes`。

| 本轮具体系统镜像 | 设备树中的 UBI 起点 | UBI 长度 | 适配含义 |
|---|---|---|---|
| OpenWrt 25.12.6 RG-X60 Pro sysupgrade | `0x680000` | `0x3f00000` = 63 MiB | 面向此目标的 stock 布局 |
| Kwrt 10.28.2026 RG-X60 Pro sysupgrade | `0x680000` | `0x6b00000` = 107 MiB | 需要匹配扩展布局；hanwckf multi-layout 中对应 `ubi-107m` |

OpenWrt 分区定义可查 [v25.12.6 的设备树](https://github.com/openwrt/openwrt/blob/v25.12.6/target/linux/mediatek/dts/mt7986a-ruijie-rg-x60-pro.dts)。Kwrt 值来自本轮镜像内嵌设备树的静态解析，摘录见[核验记录](firmware/x60-pro-2026-11-01.json)，不能推广到所有 Kwrt 版本。

两者起点相同不代表布局兼容。不要因为文件能上传或小于分区容量，就认定能正常刷入或启动；不能把 63 MiB 与 107 MiB 固件当作同布局的普通升级互换。U-Boot 有某个布局选项，也不证明该选项已在新机启用，更不证明硬件兼容。**本页不提供切换布局、格式化 UBI 或写入引导的命令。**

OpenWrt initramfs 内嵌设备树同样描述 63 MiB UBI，但它是临时内存启动候选。不能由此推断“必须先把闪存改为 63 MiB 才能从内存启动”；其加载方式和启动后如何识别、访问闪存需要分别核验。仅启动该镜像不会自动恢复原机无线校准、产品信息或引导分区，也不能替代原机备份和经核验的恢复路径。

## 5. 实际刷机前要补齐的条件

- 核对新机型号、硬件版本、原厂固件版本及可用的管理/恢复入口；不要把其他硬件版本的成功案例当成本机验证。
- 确认读取途径后，将新机自己的实际引导、环境、Factory/校准及产品信息等必要分区备份到私密位置，核对内容可读性和完整性。配置导出不能替代这些分区备份，其他设备的备份也不能直接覆盖新机。
- 保存下载日期、来源 URL、精确文件名、字节数与 SHA256；如来源同名内容变化，重新核对来源及元数据。
- 确认恢复条件、电脑有线连接和供电条件；先确定实际分区和启动链，再决定系统镜像与是否需要改写引导。
- 锐捷[官方 X60 PRO 软件下载页](https://www.ruijie.com.cn/fw/rj-cp-x60pro/)当前需要官网账号登录，本轮尚未取得原厂恢复镜像；路由器管理凭据不用于官网登录。官方升级包也不能自动视为全闪存恢复备份。

分区备份、原始配置、密码、密钥、节点信息及设备标识只留在私密管理位置，按[公开边界](../SECURITY.md)处理，不能作为仓库附件。

## 6. 等待实机成功后再补的内容

原厂管理入口的取得、备份与恢复的具体操作、U-Boot/FIP 是否需要改写、布局选择、系统写入、首次启动和失败恢复步骤，均等待本机实际验证后再写。不能把本页的静态检查结果表述为刷机成功。

成功后的记录应包含适用的硬件和原厂固件版本、精确镜像 hash、最终分区及启动方式、重启恢复、网口和 Wi-Fi 功能验收，以及仍未验证的恢复场景。新宽带直连正常后，再配置所需扩展和一组分流网络，并使用[诊断入口](beginner-check.md)建立新环境基线。

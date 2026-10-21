# 快速开始：选择你的第一步

[首页](../README.md) · [结果示例](result-examples.md) · [案例与历史](cases.md)

**第一次使用，从客户端检查开始；不用先准备路由器/VPS 的 SSH。**

```sh
python3 tools/quick-check.py
```

这是离线合成演示，无网络请求。准备检查自己当前网络时，再运行：

```sh
python3 tools/quick-check.py --execute
```

最多三次轻量 HTTPS 请求，未指定固定对象就不做下载测速。完整安装要求、目标、预算与输出解释见 [新手诊断指南](beginner-check.md)。

| 你现在需要什么 | 继续阅读 |
|---|---|
| 看默认报告、执行首次轻量检查 | [新手诊断入口](beginner-check.md) |
| 分清成功、部分下载、429 和超时 | [结果怎么读](result-examples.md) |
| 已会基本检查，要核对指定来源和两端服务 | [原 15 分钟进阶准备流程](advanced-start.md) |
| 需要完整分层诊断或单项实验 | [决策树](decision-tree.md) · [测量指南](measurement-guide.md) |
| 接手维护者现有 AU / US 排查 | [最新进度](latest-progress.md) · [案例索引](cases.md) |

新手小请求不证明节点归属、最高带宽或手机直播稳定性。各历史批次仍单独保存，入口调整没有改变原失败记录和保留/回滚决定。

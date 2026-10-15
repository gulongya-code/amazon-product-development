# 新市场研究任务接收 V1

2026-10-14，北京时间。本版配合 PDS 的版本化市场工具选择，解决“尚未有研究成功回执，也能先提交新任务”。原 `market_pds_workflow` 和历史结果复用入口保持原样。

新增 `market_research_intake.py` 和 `scripts/receive_pds_market_research.py`。调用通常由 PDS 路由程序完成：

```powershell
python -B -X utf8 scripts/receive_pds_market_research.py --task <PDS新研究任务JSON> --output <新接收回执JSON>
```

接收程序核对版本、身份、源问题/上下文/选择的文件 SHA 与 record_ref、问题 OPEN 状态、业务日期、问题/目标与 Expected Answer、研究类型、选择来源和固定非执行策略，并再次逐字段匹配原问题记录。CLOSED 不能通过重新封装的 OPEN 投影进入接收。

真实项目选择必须有自身成功模型回执，不能将 Codex 会话、未知来源或旧问题的选择当成当前选择。`SYNTHETIC_TEST` 默认拒绝；显式 `--allow-synthetic` 只用于离线合同验证，回执保留合成性质。

成功接收返回 `ACCEPTED_PENDING_ANALYSIS`，明确 `research_completed=false`、`business_value_accepted=false`、`new_provider_calls=0`。接收不表示取证、模型分析、经营复盘、业务验收或执行已完成。相同任务已有合格回执时返回原回执；错配或损坏不能覆盖旧回执。

本程序不采集、调用模型、执行经营操作或注册定时任务。新研究须另行核定输入和分析授权。SP-043B 继续 `BUSINESS VALUE HUMAN REVIEW PENDING`。

PDS 完整选择/路由说明：`C:/Users/Administrator/daily_data_auto_entry/docs/pds/PDS_MARKET_SELECTION_ROUTING_V1.md`。本轮离线证据：`C:/amazon_private/pds_market_selection_v1_20261014/offline_verification.json`；源文件保留和 SHA/whitespace 检查见 `validation.json`。

验证：市场新接收及原工作流/回读 42 项测试通过，PDS 相关 100 项通过。正例为显式合成任务，通过实际本地进程完成接收及反馈，但保持待分析；真实负例为 PDS 已关闭/资料不足事项，均不派发。新真实模型选择的验证未执行。

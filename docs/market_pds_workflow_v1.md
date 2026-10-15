# PDS 市场研究统一入口 V1

2026-10-14，北京时间。当前实现为留存证据与已有项目模型分析的自动交接、消费和回读。新付费调用、定时采集及经营操作均不在本版执行路径中；SP-043B 继续 `BUSINESS VALUE HUMAN REVIEW PENDING`。

## 已实现的流程

任务文件 → 核对身份、研究类型、原 PDS 输入与全部来源 SHA → 准备交接包 → 启动 PDS 本地消费程序 → 核对 PDS 响应 → 输出回读和短报告。

首次运行后，同一有效任务再次运行会直接复用完整结果，且不再次启动 PDS 消费程序。复用前仍检查原证据、结果文件及运行方法。证据或身份不匹配会拒绝；缺少本地证据返回 `INSUFFICIENT_EVIDENCE`；处理中失败保存断点，后续返回 `NEEDS_REVIEW`，不自动重试。修改运行方法也需要审核，不能静默使用旧工作流结果。

执行步骤已经由程序串联，不需要 Codex 逐步选择命令、搬运结果或代写 PDS 分析。任务选择仍需由调用方明确提出；本版没有全 SKU 自主发现问题或生成新市场研究判断的能力。

## 复用与适用范围

市场侧复用原 `pds_market_readback.read_verified`、`yps_competitive_difference.ref/save` 和原证据包。PDS 侧复用 strict JSON、seal/verify、不可变写入、来源校验及三个既有响应验证器。两项目仍通过版本化文件和独立子进程交接，市场项目不导入 PDS 业务模块，不共享数据库或运行时状态。

三种研究类型：

| 类型 | 继承的证据格式 | 对应消费范围 |
|---|---|---|
| `native_offer_review` | `amazon-buyer-context-probe/v1` | 已完成的买家条件与报价复核 |
| `offer_comparison` | `08-market-offer-evidence/v1` | 已完成的报价、包装及优惠投入复核 |
| `competitive_difference` | `yps-competitive-difference/v1` | 已完成的规格、页面与变体评论竞争差异复核 |

历史 schema 名保持兼容；新入口不按 SKU 分支，也不硬编码 YPS/08 身份或私有目录。其他商品只有具备对应格式、相同身份、匹配的原输入和成功项目模型回执时才可复用。新增任意问题、目标、约束或不同证据不能挂接旧回执；本版要求继承 `pds_context_ref` 中原有问题与经营上下文。

## 使用

无需安装新依赖，可从本仓库运行 `python scripts/run_pds_market_research.py`。如果项目已安装，等价入口为 `amazon-market-pds`（已有环境需更新安装才能取得新 console script）。

一次性准备任务：

```powershell
python scripts/run_pds_market_research.py init --task-id <任务ID> --research-type <类型> --packet <原市场证据JSON> --receipt <成功PDS回执JSON> --task-file <新任务JSON路径>
```

也可由上游程序调用 `make_task()` 创建任务文件；任务包含身份、研究类型、原市场证据引用、模型回执引用、原 PDS 上下文引用和本版固定策略。策略不接受付费、定时采集或经营执行开关。

之后仅一条命令完成交接与回读：

```powershell
python scripts/run_pds_market_research.py run --task-file <任务JSON> --output-root <工作流结果根目录> --pds-root <PDS仓库目录>
```

`--pds-python` 可指定 PDS 已有 Python 环境；默认使用当前解释器。PDS 仓库须具备新入口 `tools/run_market_research_handoff.py`。这个入口仅消费现有成功回执，没有模型调用、采集或失败转模型的分支。

新结果目录保存 `task.json`、原证据字节副本、`handoff.json`、`pds_response.json`、`readback.json`、`REPORT.md`、带指纹和文件 SHA 的 `result.json`；失败时保存 `failure.json`。原证据、原模型回执、历史验收和已消耗调用槽位不改写。

## 真实验证结果

真实任务及运行记录：`C:/amazon_private/market_pds_workflow_v1_20261014`。任务文件为 `yps.task.json` 和 `08.task.json`，最终产物位于 `verified_runs`。两款首次运行均为 `WORKFLOW_COMPLETED`，重复运行均为 `REUSED_COMPLETED_WORKFLOW`，重复运行后所有产物字节保持一致。

- YPS 使用证据链完整的原报价复核：`yps_market_offer_review_002/run_3/review.json`。
- 08 使用原报价及优惠投入复核：`08_market_review_001/run_1/review.json`。
- YPS 竞争差异旧回执引用的 ADS `application/pds_traffic_semantics.py` 已变更，因此该份回执被入口拒绝。没有恢复 ADS 旧代码、修改原引用、重新调用模型或把它升级为完整可复用；该限制保留在 `live_replay_verification.json`。

本轮新市场采集与付费模型调用均为 0，未启用定时采集。报告明确标注历史原分析时间、未刷新证据和 `business_value_accepted=false`。历史分析完成不等于本次新增经营判断或业务验收。

验证：市场相关测试 87 项通过，PDS 相关测试 43 项通过。覆盖两个真实案例的自动交接与重复复用，及合成的其他 SKU、错误回执、不同证据、付费策略扩张、重复 JSON 键、失败不重试、响应错配、产物损坏和方法变更。合成案例只证明合同适用性，不作为商品实证。

## 本版边界

这是一版可独立运行的自动交接与历史结果复用能力。新证据取数、新的项目模型判断、PDS 自主派发任务及定时运行尚未由本版实现或授权。没有适用成功回执时不会以 Codex 聊天判断填补，也不会自动调用模型。

实现、调用与完整性证据见 `baseline.json`、`live_replay_verification.json`、`validation.json`。没有提交、推送或更新任何人工业务验收状态。

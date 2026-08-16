# v3.3.1 Pilot重新准入冻结提案

## 1. 文件性质

状态：`PROPOSED_FOR_USER_FREEZE; ZERO_API; PILOT_NOT_AUTHORIZED`

本文件把P001—P006恢复执行所需的调用、时间、费用、模型版本和代码版本条件整理为一次性决策单。除`N_max=10`外，下列数值在用户明确接受前均只是提案。创建本文件、运行`--plan-only`或执行历史结果清点都不构成真实LLM Pilot授权。

## 2. 已有事实与可推导范围

已完成的Real-LLM稳健性suite包含5个完整九条件blocks，共743次底层语义调用，故历史均值为：

```text
743 / 5 = 148.6 provider calls per block
148.6 × 6 = 891.6 calls for P001—P006（点估算）
```

该点估算不能被当作确定调用数。新simulation seed、requested LLM seed及其引起的发帖/观察路径变化都可能改变后续需要评价的信息数量。程序中的provider-call ceiling是预算性停止规则，不是科学样本量，也不能因超限而追加replacement seed。

历史记录只保存了五个blocks的总调用量，没有在仓库证据中保存逐block运行时长或输入/输出token。因此：

- 不能从743次调用精确推出费用；
- 不能把run ID之间的时间间隔冒充经审计的单block wall time；
- 不能宣称提案上限保证六个blocks一定完成。

## 3. 建议冻结值

| 条件 | 建议值 | 依据 | 是否程序硬执行 |
|---|---:|---|---|
| 正式block预算上限 | `N_max=10` | 已在Pilot结果前由用户冻结 | 是，既有门禁 |
| Pilot provider-call ceiling | `1200` | 相对六block点估算891.6保留308.4次、约34.6%余量 | 是，调用底层router前停止 |
| Pilot wall-clock ceiling | `2.0 hours` | 覆盖历史suite表现之外的provider重试和本地I/O，不把历史时间间隔当精确耗时 | 是，新门禁；到时取消当前block并停止suite |
| 可接受费用上限 | `CNY 20` | 远高于按当前官方单价和常见短JSON响应得到的工作估算 | 否；须由账户侧额度/预警或用户承担 |
| Pilot seed grid | `P001—P006` | 原3×2认知Pilot设计 | 是，不允许replacement |
| 离线需求重放 | 每block `D1—D3` | 原协议 | 不产生provider call |

`1200`不是对743的事后统计优化，而是执行前预算边界。若在完成P001—P006前触及1200次调用或2小时，整个suite状态应为失败停止，已完成的部分blocks不得进入方差或OC分析；随后只能在新的预登记决策下处理，不能临时提高上限继续原suite。

## 4. 费用估算的边界

阿里云百炼官方模型价格页在2026-08-16显示，华北2（北京）`qwen-plus`在单次输入不超过128K时，非思考模式输入单价为0.8元/百万Token、输出单价为2元/百万Token，思考模式输出单价为8元/百万Token。来源：

```text
https://help.aliyun.com/zh/model-studio/model-pricing
访问日期：2026-08-16
```

当前项目记录语义调用次数，但AgentKernel的`ModelRouter.chat`接口只向本项目返回文本，没有把provider usage对象写入运行账本，也没有程序化token费用停止器。因此`CNY 20`只能作为用户可接受费用或账户侧额度，不能伪称代码强制的精确费用上限。正式执行前至少满足以下二者之一：

1. 用户确认账户余额/预算足以覆盖20元，并接受代码只能强制1200次调用与2小时时间；
2. 用户在阿里云账户侧设置可用的费用预警或额度控制，并保留设置截图/账单作为执行记录。

## 5. 模型版本复现性门禁

当前`configs/models_config.yaml`使用滚动别名`qwen-plus`。同一官方价格页在2026-08-16说明，该别名当前能力等同于`qwen-plus-2025-12-01`。滚动别名未来可能迁移，因此仅冻结字符串`qwen-plus`不足以保证长期复现。

执行前必须二选一：

| 方案 | 处置 | 科学后果 |
|---|---|---|
| A（推荐） | 在Pilot结果前把模型固定为`qwen-plus-2025-12-01`，同步合同、测试和执行SHA | 提高复现性；需要承认此前稳健性suite使用的是当时指向同版本的滚动别名 |
| B | 保持`qwen-plus`滚动别名，并记录执行日期、官方当日映射及provider响应元数据 | 与既有工程run字面配置连续，但未来复现性较弱 |

不得在看到Pilot结果后根据结果方向选择模型版本。

## 6. 已补充的程序化时间门禁

真实执行入口现在额外要求：

```text
--max-wall-clock-hours <positive finite number>
```

runner在每次真实provider调用前检查调用数和墙钟时间，并用剩余时间包裹当前完整block执行。达到时间上限时，当前block记为失败、suite停止、不使用replacement seed。该门禁不能控制阿里云对一次已经接收请求最终如何计费，但能防止客户端无限继续新的科学语义调用。

零API检查命令：

```powershell
D:\Python\Anaconda\envs\Kernel\python.exe -X utf8 .\run_v33_pilot_variance.py `
  --plan-only `
  --n-max 10 `
  --provider-call-ceiling 1200 `
  --max-wall-clock-hours 2
```

预期必须同时显示：`status=PLAN_ONLY`、`real_llm_calls_started=false`、`execution_authorized=false`、`provider_call_ceiling=1200`及`max_wall_clock_hours=2.0`。

## 7. 历史逐block调用量清点

冻结1200前，建议在用户本地只读清点五个历史Real-LLM blocks的逐block调用量，以确认没有由单个极端block支配743这一总数：

```powershell
$root = ".\results\v33_llm_robustness\llmrob_20260814_230111\profiles"

$rows = Get-ChildItem $root -Filter "run_summary.json" -File -Recurse |
ForEach-Object {
    $s = Get-Content $_.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    [PSCustomObject]@{
        Profile = Split-Path (Split-Path $_.Directory.FullName -Parent) -Leaf
        RunId = $s.run_id
        ProviderCalls = [int](($s.condition_meta | Measure-Object -Property provider_calls -Sum).Sum)
        ReplayMisses = [int](($s.condition_meta | Measure-Object -Property replay_misses -Sum).Sum)
        Status = $s.status
    }
}

$rows | Sort-Object Profile | Format-Table -AutoSize
"TOTAL_PROVIDER_CALLS=$((($rows | Measure-Object ProviderCalls -Sum).Sum))"
"MAX_BLOCK_CALLS=$((($rows | Measure-Object ProviderCalls -Maximum).Maximum))"
```

总数应为743，所有`ReplayMisses`应为0。若不一致，停止冻结并先审计结果目录；不得选择性排除调用量较高的有效历史block。

## 8. 尚需用户一次确认的项目

在任何真实调用前，用户需明确回复是否同时接受：

1. `provider-call ceiling=1200`；
2. `wall-clock ceiling=2.0 hours`；
3. `可接受费用上限=CNY 20`及其非程序化边界；
4. 模型版本方案A或B；
5. 在新代码通过Windows全量测试后，再以当时clean HEAD单独冻结执行SHA；
6. SHA冻结之后仍需另行说出“授权执行P001—P006”，冻结参数本身不自动启动Pilot。

## 9. 当前零结果声明

本提案新增GABM run=0、provider call=0、有效Pilot observation=0、formal inference=0。P001—P006仍未执行，正式N仍未由v3.3.1 Pilot证明。

# TASK_005 Stage I.5B-1 工程 pilot 扩展决策 1.0

## 1. 审查结论

选择**方案 B：建立独立扩展批次**。禁止在
`task005-real-pilot-v1`中直接把`num_replicates`从3改为5。

冻结runner在读取既有批次时要求：

1. seed ledger行数必须等于本次请求的`num_replicates`；
2. `replication_metadata.json`中的`num_replicates`必须与请求一致；
3. 既有批次加载逻辑只有读取与一致性验证，没有追加ledger、manifest或metadata的分支。

因此，对原批次传入`--num-replicates 5`会在启动校验阶段失败。手工追加ledger、
manifest或修改metadata会破坏已经冻结的Stage H证据，禁止采用。

## 2. 独立扩展批次

- replication_id：`task005-real-pilot-extension-v1`
- num_replicates：2
- llm_mode：`real`
- llm_seed_supported：`unknown`
- provider_model：`qwen-plus`
- max_parallel：1
- 首次启动不得使用`--retry-failed`

扩展master seed按冻结函数计算：

`derive_seed(20260802, 1, "pilot-extension-master-v1") = 188668086`

不能继续使用原master seed `20260802`，因为新批次的物理R001、R002将重复原pilot
R001、R002的seed。

## 3. 扩展seed ledger

| 物理ID | 规范分析ID | simulation seed | requested LLM seed | Python hash seed |
|---|---|---:|---:|---:|
| R001 | P004 | 4187293815 | 836958817 | 227373458 |
| R002 | P005 | 4272437146 | 3270415158 | 1090171497 |

物理ID由现有runner固定生成。跨批次分析时必须使用规范ID，避免把两个批次中的
R001、R002误当作同一block。

## 4. 五block工程诊断映射

- 原pilot：R001→P001，R002→P002，R003→P003
- 扩展批次：R001→P004，R002→P005

扩展完成后，只使用各block最终成功attempt，按`exp_id`在block内配对，形成5个独立
工程诊断block。用途仅限重新估计SD和精度可行性。

## 5. 中断恢复

首次启动后若发生外部中断，只能对
`task005-real-pilot-extension-v1`使用完全相同参数并追加`--retry-failed`恢复。
不得对原pilot批次执行恢复，不得删除失败ledger或attempt目录。

## 6. 门禁

- Stage I.5B-2前不得启动扩展；
- 扩展不属于formal样本；
- 不并入smoke；
- 不执行策略或因子显著性推断；
- formal target N仍未冻结；
- formal真实LLM启动仍禁止。

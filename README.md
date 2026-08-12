# GreenConsumer — TASK_005 FMCG v3.2 GABM

当前 canonical scenario：完全虚构的植物奶品牌危机场景 **VerdantCo Oat**。

## 正式版本身份
- Scenario: `fmcg-scenario-3.2`
- Formal source HEAD: `ef6567adaafcafcf3b9f6884295f509a05ed727e`
- Cognitive agents: 20 个平衡 engineering personas
- Horizon: 30 Ticks
- Crisis: Tick 5
- Communication: Content × Channel × Timing = 2 × 2 × 2
- Common control: `NoClarification-Control`
- Conversion support: offline PBC-only cross
- Formal valid replication blocks: F001-F010, 10/10

## Canonical architecture

```text
ExperimentConfig
  → FMCG scenario/personas/stimuli
  → AgentKernel social network + observations
  → LLM semantic appraisal
  → Trust + Att + peer-only SN + PBC
  → social posting/diffusion
  → offline category opportunity
  → repeated focal-brand choice + loyalty
  → block-level estimands / formal analysis
```

## 核心构念边界
- LLM 只做语义评估，不直接决定购买。
- SN 只由实际 social-feed observation 中的 perceived peer approval 更新。
- 企业澄清和 global news 不直接更新 SN。
- Hub/Random 操作 reach，不自动等于 persuasion 或 purchase。
- conversion support 只通过 PBC 通道进入 demand layer。
- category-purchase opportunity 与 treatment identity 分离。
- 行为端是 repeated focal-brand choice，不是 absorbing first purchase。
- 20 cognitive agents 不是人口代表样本。
- micro-buyers 不是独立 formal replications。

## 文档入口
- `docs/architecture/CODEBASE_MAP_V32.md`
- `docs/thesis/MODEL_DESIGN_CHAPTER_V32.md`
- `docs/reproducibility/TASK005_V32_FORMAL_CLOSEOUT.md`
- `docs/legacy/LEGACY_BOUNDARY.md`

仓库包含早期 scenario、旧 purchase construct、旧 formal launcher 与历史调试材料。它们是开发证据，不是当前 v3.2 canonical execution authority。

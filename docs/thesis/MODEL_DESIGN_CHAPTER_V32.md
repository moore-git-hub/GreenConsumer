# GABM模型设计与实现

## 1 研究目标与模型边界

本文构建一个面向绿色消费危机传播情境的生成式智能体仿真模型（Generative Agent-Based Model, GABM），用于刻画企业澄清信息、消费者认知、社会网络扩散与快速消费品重复选择之间的动态耦合关系。模型研究对象限定为短期声誉危机中的绿色消费品牌选择，而非一般意义上的耐用品扩散或真实市场份额预测。为避免现实品牌历史信息、既有声誉与外部事件对实验处理产生不可控混杂，模型采用完全虚构的植物奶品牌 VerdantCo Oat，并将目标群体限定为具有植物奶品类购买经验的消费者。

模型遵循“语义—认知—网络—行为”分层原则。大型语言模型并不直接输出购买决策，而仅承担对 Agent 实际观察信息的语义评估；结构化语义输出随后进入显式、可审计的心理状态转移函数，再通过社会网络传播和独立 FMCG 购买机会机制形成宏观结果。该设计在利用大型语言模型处理自然语言语义异质性的同时，避免将完整行为生成过程交由不可解释的端到端模型决定，以增强机制可识别性、实验可重复性和因果解释边界的清晰度。

从方法规范看，本研究参照 ODD（Overview, Design concepts, Details）协议的基本思想，对模型目的、实体、状态变量、过程调度、初始化、随机性、输入与子模型进行明确说明，并将主要理论构念与可定位的代码模块对应。模型的核心目标不是拟合某一真实品牌的销量轨迹，而是检验一组冻结机制在竞争信息与社会网络条件下能否生成内部一致的信任恢复、传播触达与重复品牌选择模式。

## 2 模型总体架构

模型由五个相互连接但职责分离的模块构成：情境与实验配置模块、LLM语义评估模块、消费者认知状态转移模块、社会网络传播模块以及 FMCG 购买需求模块。

第一，情境与实验配置模块规定危机事件、企业澄清内容、澄清时机、传播渠道与转化支持条件。第二，LLM 语义评估模块将 Agent 实际观察到的新闻、企业澄清或社会信息转化为效价、唤醒度、可信度、证据强度、主题相关性、共情感知以及同伴认可等结构化变量。第三，消费者认知状态转移模块依据固定函数更新信任、态度、主观规范、感知行为控制、危机记忆和修复记忆。第四，社会网络模块决定消息能够到达哪些 Agent，并允许 Agent 生成的社会信息沿有向关系传播。第五，购买需求模块在与处理条件无关的品类购买机会出现时，根据认知状态、个体偏好、可得性、价格敏感度和品牌忠诚状态计算焦点品牌的重复选择概率。

模型的基本因果顺序为：

企业/社会信息 → 语义评估 → 心理状态更新 → 社会传播与认知累积 → 品类购买机会 → 焦点品牌条件选择。

这一顺序的核心在于：企业传播不能跳过心理机制直接写入购买结果；Hub 节点不能直接产生购买；价格与可得性支持不能直接改变信任；LLM 也不能直接返回“购买/不购买”。因此，不同理论构念在代码层面具有明确的排除限制。

## 3 情境、Agent与初始化设计

### 3.1 虚构品牌与危机事件

模型采用 VerdantCo Oat 作为完全虚构的植物奶品牌。危机发生于 Tick 5：品牌接受一家在情境中被批评持有环境争议资产的虚构投资集团少数股权投资，由此引发消费者对价值一致性、漂绿和使命偏移的质疑。投资方不拥有多数股权，也不控制品牌可持续政策。该设置的目的不是复现现实公司事件，而是构造一个能够同时触发“环境价值一致性判断”和“品牌信任修复需求”的标准化声誉危机。

采用虚构品牌具有三点方法优势。其一，可减少真实品牌熟悉度、历史舆情与现实政治经济信息对语言模型和 Agent 判断的污染；其二，可以保证 Rational 与 Empathy 两种澄清材料共享相同事实集合，只改变框架与强调重点；其三，可避免将仿真结果误解为对某一现实品牌的事实判断或市场预测。

### 3.2 消费者 Agent

认知层包含 20 个消费者 Agent。20 个 Agent 并非人口抽样意义上的代表性样本，而是用于覆盖不同机制状态的平衡 engineering panel。每个 Agent 具有六类固定或缓慢变化的画像属性：绿色取向、植物奶购买频率、既有品牌关系、价格敏感度、零售可得性摩擦以及社会发帖角色。

绿色取向包括 Non_Greens、Convenient_Greens、Active_Greens 与 Dormant_Greens；品类购买频率划分为 5–7 天、7–10 天、10–14 天与 14–28 天；既有品牌关系包括 loyal、repertoire 与 non-user。该设计将价值取向、购买频率、品牌关系与购买约束分开，避免用单一“绿色偏好”标签承担过多行为解释。

### 3.3 微观购买者

行为需求层在每个认知 Agent 下构造若干确定性的 micro-buyers。其作用是提高 30 Tick 短期窗口中品类购买机会与重复选择事件的分辨率，而不是增加正式独立样本量。正式统计推断的独立单位始终是 replication block，而非 cognitive Agent 或 micro-buyer。

这种双层 Agent 设计解决了一个关键矛盾：认知层需要控制 LLM 调用规模，以保证审计和实验成本可控；行为层又需要足够多的购买机会，才能避免重复购买结果因事件过少而呈现过度离散。因此，认知 Agent 负责语义与心理过程，micro-buyers 负责需求机会和选择分辨率。

## 4 实验处理设计

### 4.1 企业澄清的三因素矩阵

企业沟通采用 2×2×2 因子设计：

1. 内容框架：Rational-Evidence 与 Emotional-Empathy；
2. 传播渠道：Hub 与 Random；
3. 澄清时机：Immediate 与 Delayed。

八个策略条件之外另设一个 NoClarification-Control，共形成 9 个认知条件。

危机固定发生于 Tick 5。Immediate 条件在 Tick 6 澄清，Delayed 条件在 Tick 10 澄清。该设置使 Tick 6–9 构成天然的 pre-delay 窗口：即时组已经接受企业澄清，而延迟组尚未接受澄清，因此可用于观察“及时性”机制在危机早期阶段的差异。

### 4.2 Rational 与 Empathy 的内容控制

两种企业澄清包含完全相同的七项事实，包括少数股权、无董事会控制、承认既往沟通不足、公开治理信息、发布独立可持续评估、设置未来投资审查机制以及“信任需通过可观察行动重建”等内容。Rational-Evidence 强调验证、审计、程序透明和可检查证据；Emotional-Empathy 强调责任承担、消费者情绪、关系修复与价值认同。

这种“事实恒定、框架变化”的设计旨在降低内容信息量差异造成的混杂，使内容因子更接近“证据框架—共情框架”的机制比较，而不是两组完全不同信息的比较。

### 4.3 Hub 与 Random 的渠道处理

传播预算固定为 K=3 个 paid seed nodes。Hub 条件选择网络中出度最高的节点，Random 条件使用独立随机种子从同一网络随机选择三个节点。企业澄清的最终触达由 public organic exposure、paid seed 与真实网络上的 one-hop amplification 共同形成。

渠道变量只决定信息能否被看到以及被哪些节点看到，不直接改变信任、态度或购买。换言之，Hub 的理论作用是结构性 reach，而不是“意见领袖天然更有说服力”。这一排除限制使网络位置效应与心理说服效应在模型中保持概念区分。

### 4.4 转化支持

模型另设 conversion support：在 Tick 6–19 提供一次价格保护券与门店可得性核验服务。该处理与 9 个认知条件离线交叉，形成 18 个 demand conditions。

conversion support 只允许改变 PBC 通道，不直接改变 Trust、Att 或 SN，也不改变 LLM 调用与认知轨迹。这样可以区分“企业解释是否修复信任”和“消费者是否具备完成购买的现实条件”两个机制。该排除限制是模型假设，需要在稳健性分析中检验，而不能被解释为已经由真实市场数据证实。

## 5 LLM语义评估模块

### 5.1 LLM在模型中的角色

GABM 中的大型语言模型被限制为结构化语义评估器。Agent 每一 Tick 只对其实际观察到的文本进行评价，并输出固定 JSON schema。核心字段包括：

- valence ∈ [-1,1]；
- arousal ∈ [0,1]；
- credibility ∈ [0,1]；
- evidence_strength ∈ [0,1]；
- topic_relevance ∈ [0,1]；
- perceived_empathy ∈ [0,1]；
- perceived_peer_approval；
- hypocrisy_perceived；
- importance；
- reasoning。

这一设计将语言模型擅长的自然语言语境理解与研究者需要控制的行为机制分离。语义输出必须通过 schema validator 后才能进入认知转移函数；正式运行同时记录 prompt 与 response 的 SHA256、条件、Tick、请求种子、模型、温度、解析状态和错误类型，以便事后审计。

### 5.2 主观规范的特殊约束

计划行为理论中的主观规范（SN）表示个体感知到的重要他人或社会群体对行为的认可，而不等同于信息本身的正负情绪。因此，模型为 SN 单独设置 perceived_peer_approval 字段。

当 Agent 未观察到任何 social-feed message 时，该字段必须为 null；只有实际观察到同伴消息时才允许生成 [0,1] 数值。全球新闻或企业澄清即使具有很强正面效价，也不能直接改变 SN。此设计避免将“企业说自己值得购买”错误解释为“消费者感知到其他人支持购买”。

## 6 消费者心理状态转移

### 6.1 信任与双记忆结构

每个 Agent 具有 baseline trust、crisis memory 和 repair memory。危机或负向信息增加 crisis memory，正向信息与企业修复信号增加 repair memory；两类记忆均按固定 retention factor 衰减。

令 \(C_t\) 和 \(R_t\) 分别表示危机记忆与修复记忆，核心衰减形式为：

\[
C_t^- = 0.97 C_{t-1}, \qquad R_t^- = 0.97 R_{t-1}.
\]

在观察到信息后，负向情绪信号进入 \(C_t\)，正向信号与关系修复信号进入 \(R_t\)。信任由基线与两类记忆的净效应得到：

\[
Trust_t = \operatorname{clip}(Trust_{base}+R_t-C_t,0,10).
\]

因此，即使没有新的企业澄清，危机记忆也可能随时间衰减，使信任逐步向 baseline 回归。本文将这种过程解释为“自然恢复”，而不是企业澄清效果；澄清效应必须相对于同一 Tick 的 NoClarification-Control 识别。

### 6.2 情绪评估的不对称性

语义效价、唤醒度与可信度共同形成 affective magnitude：

\[
m_t=|v_t|(0.5+0.5a_t)(0.5+0.5c_t).
\]

当 \(v_t<0\) 时，模型使用较大的负向权重；当 \(v_t\ge0\) 时使用相对较小的正向权重：

\[
Affect_t=
\begin{cases}
-2.0m_t,& v_t<0,\\
1.5m_t,& v_t\ge0.
\end{cases}
\]

该设置体现对负面信息更强的危机冲击假设，但数值大小属于模型参数假设，应通过敏感性分析而非统计显著性反向校准。

### 6.3 态度更新

模型首先将 valence 转换为 \(v_{01}=(v+1)/2\)，并构造综合语义信号：

\[
S_t=0.45v_{01}+0.25Credibility_t+0.20Evidence_t+0.10Relevance_t.
\]

态度按照固定学习率 0.25 更新：

\[
Att_t=0.75Att_{t-1}+0.25S_t.
\]

因此，态度同时受信息情绪方向、可信度、证据与主题相关性影响，而不是直接读取 treatment label。

### 6.4 主观规范更新

若当前没有实际社会信息，主观规范保持不变：

\[
SN_t=SN_{t-1}.
\]

若观察到 \(n\) 条同伴信息，模型采用边际递减的有效更新率：

\[
\rho_n=1-(1-0.20)^{\min(n,3)},
\]

并依据感知同伴认可度 \(PA_t\) 更新：

\[
SN_t=(1-\rho_n)SN_{t-1}+\rho_n PA_t.
\]

这一结构使 SN 成为真正的社会互动变量，而非企业传播的直接函数。

### 6.5 PBC与购买意向

认知层的基础 PBC 不由企业沟通内容直接改变。extended-TPB purchase intention 使用：

\[
z_t=-0.50+1.40(Att_t-0.5)+0.80(SN_t-0.5)
+0.60(PBC_t-0.5)+1.20(Trust_t/10-0.5),
\]

\[
I_t=\sigma(z_t).
\]

信任被作为绿色品牌危机条件下的扩展认知变量加入 TPB，而购买本身仍不在 AgentKernel Plan 中发生。Plan 层只计算意向与发帖倾向，然后将购买选择交给独立 demand layer。

## 7 社会网络与信息扩散

### 7.1 网络拓扑

20 个认知 Agent 构建于 Barabási–Albert（BA）无标度网络底图，参数为 \(m=2\)。为了表达广播方向，模型随后将每条无向边定向为“高度节点 → 低度节点”，形成有向网络。由此，高出度节点具有更大的直接下游触达能力。

BA 网络用于构造具有明显度异质性的机制实验环境，而不是声称真实社交媒体网络严格服从该拓扑。网络随机种子在 replication block 层独立冻结，使不同 block 能反映网络 realization 的随机不确定性。

### 7.2 社会信息传播

当 Agent 发生发帖行为时，内容沿其出向邻居广播。接收者在后续认知循环中将这些消息作为 Social observations 处理，并由 LLM 单独评估 peer approval。因而，社会网络既影响企业澄清的结构性 reach，也影响消费者生成内容对 SN 的后续更新。

## 8 FMCG购买机会与重复品牌选择

### 8.1 为什么废弃“首次购买”端点

植物奶属于重复购买型 FMCG。若在每个 Tick 都尝试一次“是否购买”，并将首次购买设置为 absorbing state，会把品类购买频率、品牌替代和重复购买行为混为一体，同时使结果快速达到 ceiling。为保持行为构念与研究对象一致，最终模型将购买过程拆分为“品类购买机会”与“条件品牌选择”。

### 8.2 品类购买机会

每个 micro-buyer 根据其 category_purchase_frequency 获得一个 treatment-invariant opportunity interval 与 phase。机会时间表只由 persona 与冻结随机种子决定，不由沟通条件、语义分数、信任或此前选择改变。

因此，各实验条件首先共享相同的“什么时候需要购买植物奶”，然后才比较“在这一购买机会中是否选择 VerdantCo Oat”。这种设计避免将企业澄清错误解释为制造额外品类需求。

### 8.3 个体异质性映射

v3.2 将 persona 属性映射到 demand layer：

- purchase frequency → 可行 opportunity intervals；
- prior brand relationship → preference centre 与 initial loyalty centre；
- price sensitivity → baseline PBC latent adjustment；
- availability friction → baseline PBC latent adjustment。

例如 loyal buyer 的 preference centre 为 +0.65，non-user 为 −0.65；相应 loyalty latent centres 为 +1.10 与 −1.10。低/中/高价格敏感度和可得性摩擦分别对应 +0.25/0/−0.25 的 PBC logit effect。上述取值均是透明的工程假设，而不是从 20 个 Agent 或正式结果中估计得到的真实市场参数。

### 8.4 条件品牌选择与忠诚状态

在购买机会发生时，模型首先由 Att、SN、PBC 与 Trust 得到 TPB intention，再将个体 preference offset、PBC facilitation 与 loyalty 加入条件品牌效用：

\[
U_{it}=\operatorname{logit}(I_{it})+\theta_i+
\beta_{PBC}(PBC_{it}-PBC_{i0})+\beta_L L_{i,t-1},
\]

\[
P(Choice_{it}=1)=\sigma(U_{it}).
\]

随后使用固定 seed、buyer id 与 Tick 生成可重复 choice draw。品牌选择不是 absorbing state，因此同一消费者在不同品类购买机会中可以选择或放弃焦点品牌。

忠诚度按：

\[
L_{it}=\operatorname{clip}(0.85L_{i,t-1}+0.20Y_{it},-1,1),
\]

其中选择 VerdantCo Oat 时 \(Y=1\)，选择其他品牌时 \(Y=-1\)。这样，品牌关系可以在重复选择中缓慢演化，而不是在第一次购买后永久锁定。

## 9 仿真调度与实验单位

每个 cognitive condition 运行 30 Ticks。单 Tick 的核心逻辑依次为环境事件与消息进入、Agent 感知、LLM 语义反思、认知状态更新、发帖决策和社会广播。购买 demand layer 在认知轨迹完成后离线计算，因此 conversion support 的 present/absent 两个条件共享完全相同的 LLM 认知轨迹。

正式统计的独立单位为 replication block。每个 block 使用独立 simulation seed、requested LLM seed、demand seed 与 Python hash seed，并在同一 block 内保持不同实验条件之间的可比随机结构。engineering personas 与 micro-buyers 均不被视为独立统计样本。

## 10 正式估计量与推断边界

最终正式设计在执行前冻结为 10 个独立 formal replication blocks（F001–F010），且不允许 replacement、optional stopping 或追加 F011+。

确认性 family 包含三个 estimands：

1. P1：总体企业澄清相对于 contemporaneous control 的危机后信任效应；
2. P2：Rational 相对于 Empathy 的危机后信任差异；
3. P5：总体企业澄清对 expected repeat focal-brand choice 的影响。

三者采用 block-level 双侧 one-sample t-test 对 0 检验，并在 P1/P2/P5 family 内采用 Holm procedure 控制 FWER=0.05。

P3（Immediate−Delayed 的 T6–T9 early trust）和 P4（Hub−Random clarification reach）在正式执行前被划为 exploratory/mechanistic，不进入确认性 Holm family，也不用于正式样本量驱动。该划分使时机机制和网络触达机制可以被完整报告，但避免在统计功效不足时进行过度确认性宣称。

## 11 可重复性、验证与审计

模型采用多层验证，而不是单一依赖“结果看起来合理”。

第一，构念验证通过代码排除限制实现。例如 SN 更新函数的输入中不存在 global news 或 enterprise message；conversion support 与认知轨迹离线交叉；purchase opportunity schedule 不读取 treatment identity。

第二，结构验证通过 unit tests、fake semantic router、AgentKernel lifecycle smoke、pre-treatment alignment、zero replay miss 和 opportunity/draw invariance 等 gate 完成。

第三，LLM 调用通过 audited router 留存 prompt/response hash、解析与 schema 状态、条件、Tick、requested seed、模型和温度等元数据。

第四，正式 replication block 使用固定 seed ledger，且 engineering blocks 与 formal blocks 相互隔离。正式统计只反映冻结 GABM 内部的 stochastic replication uncertainty。

按照这一边界，模型中的 p 值与置信区间不能直接解释为真实消费者总体抽样推断，也不能单独证明现实市场中的因果效应。模型外部有效性仍需依赖调查、实验、平台数据或真实销售数据进行交叉验证。

## 12 设计选择的科研理由与局限

本文的核心设计选择可以概括为“用语言模型处理语义，用显式机制处理因果链，用网络处理触达，用独立需求层处理行为机会”。

其优势在于：第一，能够处理传统 ABM 难以预先枚举的自然语言语义差异；第二，心理变量更新具有清晰数学形式，避免 LLM 直接替代行为理论；第三，企业信息、社会规范、网络触达与购买可行性被分别建模，从而降低构念混淆；第四，重复购买场景通过 opportunity-choice-loyalty 链条得到比一次性 adoption 更符合 FMCG 的行为表示；第五，代码中大量 audit fields、schema validators 与 frozen contracts 为结果复现与机制核查提供基础。

同时，模型仍存在明确局限。20 个认知 Agent 是机制覆盖面板而非代表性样本；persona-to-demand 数值映射没有经过真实消费者数据校准；BA 网络是理论化结构而不是社交平台拓扑估计；LLM 的语义判断可能存在模型特定偏差；部分心理参数与记忆衰减率属于工程假设；PBC-only conversion support 是识别性排除限制而非已经得到经验验证的规律。因此，本文将模型定位为机制解释与策略比较工具，而不是现实市场份额预测模型。

## 13 本章小结

本章构建了一个面向绿色 FMCG 声誉危机的 GABM。模型以虚构品牌 VerdantCo Oat 为统一情境，以 20 个认知 Agent 表达语义与心理异质性，以有向 BA 网络表达结构性传播，以 LLM 处理自然语言语义评估，并通过显式 Trust–Att–SN–PBC 状态转移连接至独立的重复品牌选择 demand layer。实验上，通过 Content×Channel×Timing 与 NoClarification-Control 形成 9 个认知条件，并将 conversion support 作为独立 PBC 通道离线交叉。整个设计强调 treatment、semantic appraisal、psychological state、network reach 和 purchase opportunity 的分离，从而为后续机制检验、正式 replication inference 与科研复现提供结构化基础。

## 参考文献建议

Ajzen, I. (1991). The theory of planned behavior. *Organizational Behavior and Human Decision Processes*, 50(2), 179–211.

Aher, G. V., Arriaga, R. I., & Kalai, A. T. (2023). Using Large Language Models to Simulate Multiple Humans and Replicate Human Subject Studies. *Proceedings of the 40th International Conference on Machine Learning*, 202, 337–371.

Barabási, A.-L., & Albert, R. (1999). Emergence of scaling in random networks. *Science*, 286(5439), 509–512.

Epstein, J. M. (1999). Agent-based computational models and generative social science. *Complexity*, 4(5), 41–60.

Grimm, V., et al. (2020). The ODD protocol for describing agent-based and other simulation models: A second update to improve clarity, replication, and structural realism. *Journal of Artificial Societies and Social Simulation*, 23(2).

Tversky, A., & Kahneman, D. (1991). Loss aversion in riskless choice: A reference-dependent model. *The Quarterly Journal of Economics*, 106(4), 1039–1061.

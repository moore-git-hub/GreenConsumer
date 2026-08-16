# 附录A v3.3.1模型ODD＋D复现说明

## A.1 文档身份

本附录依据ODD的Overview、Design concepts和Details结构报告v3.3.1模型，并使用ODD＋D补充人类决策子模型。ODD用于提高Agent-based model描述的透明度与复现性（Grimm等，2020，《The ODD protocol for describing agent-based and other simulation models: A second update to improve clarity, replication, and structural realism》）；ODD＋D要求进一步说明决策主体、目标、信息、适应、社会影响及理论/经验基础（Müller等，2013，《Describing human decisions in agent-based models: ODD + D, an extension of the ODD protocol》）。

本附录描述代码版本TASK_005_FMCG_V3.3.1。它是复现规范，不是模型有效性证明，也不授权Pilot或正式实验。

## A.2 Overview

### A.2.1 Purpose and patterns

模型目的为：在虚构绿色植物奶品牌发生绿色信任危机后，比较澄清内容、paid-seed渠道和回应时机如何通过自然语言语义评价、心理状态更新和固定社会网络传播，改变模型内品牌信任恢复、企业直接触达和预期重复品牌选择。

模型预期产生而非预先硬编码的宏观模式包括：不同条件下的Trust轨迹、企业直接触达差异、UGC传播流、Agent异质性以及expected repeat-choice差异。处理标签不直接给Trust或购买结果加分；结果由文本暴露、语义评价、状态转移、网络结构和冻结随机过程共同形成。

### A.2.2 Entities, state variables and scales

| 实体/对象 | 数量或尺度 | 主要状态 | 代码位置 |
|---|---:|---|---|
| Cognitive Agent | 基线20 | Persona、Trust、Attitude、Subjective norm、PBC、危机/修复记忆、购买/发帖意向、消息收件箱 | `fmcg_scenario_v32.py`；Agent plugins |
| Micro-buyer | 每Agent 25 | 购买机会相位、PBC、loyalty、purchase index、next opportunity Tick | `purchase_mechanism_v33.py`；`greenconsumer_v33/demand.py` |
| 信息对象 | 事件产生 | source、type、content、sender、创建/投递Tick | crisis/clarification injector；network plugin |
| 社会网络节点 | 与Cognitive Agents一一对应 | in-degree、out-degree、targeting role | `SocialNetworkPlugin.py` |
| 社会网络边 | 固定有向边 | source、target | 同上 |
| 实验条件 | 9 | Content、Channel、Timing、K、clarification Tick | `experiment_config.py` |
| Replication block | Pilot/正式阶段确定 | 三类seeds、九条件输出、estimands、validity状态 | runner与formal protocol |

时间单位为1 simulation day。基线运行T1—T35；T1—T4为共同历史，T5发生危机，T6为Immediate澄清，T10为Delayed澄清，T35为endpoint。模型空间不是地理空间，而是固定有向社会关系网络。

### A.2.3 Process overview and scheduling

单个完整block的调度为：

1. 读取冻结配置、Persona、文本、seeds和参数；
2. 生成或读取固定社会网络，并为九条件保持相同topology hash；
3. 按固定顺序运行九个实验条件；
4. 每个Tick投递到达信息；
5. 仅对Agent实际观察到的文本执行schema约束的LLM语义评价；规则触发发帖后，显式评价理由作为UGC正文；
6. 更新危机/修复记忆、Trust和Attitude；
7. 根据实际同伴观察更新Subjective norm；
8. 计算purchase intention和posting intention；
9. 按冻结随机规则形成UGC并沿有向边投递；
10. 保存Agent、认知、文本、网络和事件审计记录；
11. 九个认知条件完成后，离线执行support-absent需求重放；
12. 在block内部计算P1—P5并执行validity gate。

条件间不共享处理后的心理状态。T1—T4通过common-history replay保持一致，T5危机事件保持相同。未来horizon不能反向改变已发生的认知轨迹。

## A.3 Design concepts

### A.3.1 Basic principles

模型采用四类理论或方法原则：TPB式Attitude—Subjective norm—PBC到意向的转换；动态信任破坏与修复；社会网络中的结构性暴露与UGC传播；绿色FMCG重复品牌选择。理论只约束构念关系，不为参数提供数值校准。

### A.3.2 Emergence

条件层Trust AUC、直接触达、UGC传播量、expected repeat choice和Agent异质性由微观暴露与状态转移聚合产生。P4部分受企业targeting规则直接约束，但具体recipient union仍取决于网络与概率性一跳投递。模型不预设哪一种内容、渠道或时机最终获胜。

### A.3.3 Adaptation

Agent依据新观察更新Trust、Attitude、Subjective norm、危机记忆和修复记忆；micro-buyer依据选择结果更新bounded-EWMA loyalty和下一次购买机会状态。网络拓扑、Persona身份和PBC基线不适应性变化。

### A.3.4 Objectives

Cognitive Agents没有显式效用最大化或长期规划目标。购买意向和发帖意向由冻结函数计算，随后由确定性伪随机抽样形成行为。企业也不在运行中优化策略；Content、Channel和Timing由实验配置外生赋值。因此，本模型是受控机制实验，不是企业与消费者共同求解的博弈模型。

### A.3.5 Learning

模型没有参数学习、强化学习或跨block学习。Agent的“学习”仅指状态随观察更新和记忆存量变化；LLM不根据运行结果训练。禁止把这种状态更新描述为机器学习意义上的在线学习。

### A.3.6 Prediction

Agent不形成显式未来预测。purchase intention反映当期心理状态，购买机会按预设renewal过程出现。企业不预测网络级联并调整投放。

### A.3.7 Sensing

Agent只能感知当前Tick实际投递到其收件箱的危机新闻、企业澄清或UGC，以及自身当前状态。Agent不掌握全网结构、其他Agent的隐性心理状态或未来事件。Hub选择器可读取网络出度，但该信息属于企业targeting规则，不属于消费者认知。

### A.3.8 Interaction

企业通过public exposure、K=3 paid seeds及概率性一跳放大投递澄清。消费者UGC沿固定有向边单向广播。接收者重新评价文本，不直接复制发送者的Trust、Attitude或选择结果。Subjective norm仅由实际同伴观察更新。

### A.3.9 Stochasticity

随机性包括：网络/仿真seed、requested LLM seed与provider/runtime波动、public/paid recipient selection、发帖抽样、购买机会与品牌选择、离线demand seed。所有可控seeds均落盘。requested LLM seed不被视为provider完全确定性的保证。

### A.3.10 Collectives

模型没有内生形成或演化的正式群体实体。Persona segment用于描述性分层；网络community只在拓扑稳健性中作为外生结构。不得把分组均值解释为估计出的现实消费者群体。

### A.3.11 Observation

模型记录Agent×Tick状态、显式语义评价、企业澄清暴露、UGC投递、网络节点/边、target nodes、需求机会、选择概率、realized choice、loyalty、运行配置和文件哈希。正式estimand在完整block内部计算；Agent行不用于正式标准误。

## A.4 Details

### A.4.1 Initialization

初始化输入包括：

- 20个冻结engineering personas；
- 虚构品牌VerdantCo Oat与植物奶品类；
- 一条危机刺激和两套共享事实但框架不同的澄清文本；
- 2×2×2＋共同控制处理矩阵；
- 基线有向BA网络，m=2；
- Trust、clarification、demand与LLM参数快照；
- simulation/network、requested LLM和demand seeds。

Persona面板通过确定性规则覆盖green orientation、category purchase frequency、prior brand relationship、price sensitivity、availability friction和social posting role。该面板是机制覆盖设计，不是样本抽样。

### A.4.2 Input data

基线模型不读取现实品牌、消费者面板、平台网络或销量数据。自然语言输入由虚构危机和澄清材料构成。既有selected Real-LLM工程运行按历史元数据调用`qwen-plus`，temperature=0.3，prompt profile为baseline_exact；后续v3.3.1 Pilot固定为`qwen-plus-2025-12-01`。Fake-LLM仅用于结构和敏感性测试。

缺少现实输入数据是当前外部有效性的主要限制。任何未来现实数据校准必须形成新版本和新协议，不能静默覆盖v3.3.1。

### A.4.3 Submodels

#### A.4.3.1 Semantic appraisal

当且仅当Agent观察到文本时，LLM返回valence、arousal、credibility、evidence strength、topic relevance、perceived empathy、peer approval、hypocrisy perceived及一条显式审计理由。输出必须满足schema和边界；fallback或解析错误会使正式block失效。LLM不直接决定行为；若规则随后触发发帖，显式审计理由会被复用为UGC正文并由接收者重新评价。

#### A.4.3.2 Trust and memory

危机记忆与修复记忆先按不同保留率衰减，再依据观察信号增加。负向信号可被伪善感知放大；正向及关系修复信号受到修复饱和约束。Trust以事件期或安静期调整率部分靠近由baseline、危机记忆和修复记忆形成的目标。

#### A.4.3.3 Attitude and subjective norm

Attitude由效价、可信度、证据强度和相关性形成的有界信号更新。Subjective norm只根据实际同伴认可观察更新；企业澄清不能通过隐藏捷径直接改变SN。PBC在基线中不动态更新。

#### A.4.3.4 Purchase and posting intention

purchase intention为Attitude、Subjective norm、PBC和Trust的Logit函数。posting intention只在有观察时产生，由arousal和效价绝对值进入Logit函数。系数为冻结工程参数。

#### A.4.3.5 Network generation and targeting

N≥5时生成无向BA底图，再将高无向度节点指向低度节点；等度边按legacy first-endpoint规则定向。Hub选择高出度节点，Random选择相同数量随机节点。单次运行内拓扑固定。拓扑和方向稳健性已显示P4依赖网络与等度边方向，因此该规则不能视为现实真值。

#### A.4.3.6 Clarification diffusion

企业澄清在t0形成public exposure和paid-seed exposure，并以baseline probability 0.55沿paid seeds的一跳出边放大，在t0+1投递。控制组不投递企业澄清。direct-enterprise reach为t0至t0+lag内观察到澄清的Agent并集比例，不包含UGC。

#### A.4.3.7 UGC diffusion

Agent根据posting intention与冻结随机抽样决定是否发帖。文本沿全部出向邻居投递，接收者在下一处理环节重新评价。当前模型没有算法推荐、边权、信息容量竞争或网络rewiring。

#### A.4.3.8 Renewal demand

认知历史完成后，每个Agent下的micro-buyers按购买频率允许区间形成renewal opportunities。机会出现时，模型以当期TPB式purchase intention及loyalty/PBC状态形成焦点品牌选择概率，再以demand seed产生realized choice并更新loyalty。正式P5使用support absent下的expected choice share。

## A.5 ODD＋D决策补充

| 决策问题 | v3.3.1回答 | 证据身份 |
|---|---|---|
| 谁决策 | Cognitive Agents形成发帖和购买意向；micro-buyers执行条件品牌选择；企业策略由实验外生设定 | 代码事实 |
| 决策对象 | 是否发布UGC、购买机会下是否选择焦点品牌 | 代码事实 |
| 决策目标 | 无显式跨期效用最大化；当期概率函数驱动 | 工程设计 |
| 信息基础 | 实际观察文本、自身状态、Persona；消费者看不到全网 | 代码事实 |
| 社会影响 | UGC暴露与peer approval更新SN | 理论约束＋代码实现 |
| 适应与记忆 | Trust、Attitude、SN、危机/修复记忆和loyalty更新 | 代码事实 |
| 异质性 | Persona属性、基线心理、购买频率、网络位置 | 机制覆盖设计 |
| 不确定性 | 多类seed与provider/runtime波动 | 可审计随机性 |
| 理论基础 | TPB、动态信任修复、信息加工、网络扩散、重复品牌选择 | 构念依据，不是数值校准 |
| 经验基础 | 当前没有现实参数校准或平台网络拟合 | 结构性限制 |

ODD＋D强调人类决策模型的选择理由和经验基础（Müller等，2013，《Describing human decisions in agent-based models: ODD + D, an extension of the ODD protocol》）。本模型在理论理由上较完整，但经验基础仍弱：Persona比例、心理系数、时间窗口和需求过程均未由现实纵向数据估计。

## A.6 复现清单

每个可复现run至少保存：

1. code release、Git HEAD、branch及dirty state；
2. 模型、temperature、prompt profile和requested LLM seed；
3. simulation/network及demand seeds；
4. 处理矩阵、时间范围和全部参数快照；
5. `run_summary.json`；
6. `cognitive_records.csv`、`agent_records.csv`和`agent_thoughts.csv`；
7. `network_meta.json`、`network_nodes.csv`、`network_edges.csv`和`target_nodes.csv`；
8. `clarification_exposure_plan.csv`和`effective_event_timeline.json`；
9. `demand_opportunities.csv`和`choice_curves.csv`；
10. analysis outputs、validity reports和SHA-256 manifest。

正式block还必须进入attempt ledger和seed ledger。只有源文件、代码身份、哈希和validity gate全部闭合后，表图才能进入论文。

## A.7 模型范围与不可复现对象

本附录能够支持他人在相同代码、配置、provider条件和seeds下重建模型流程；不能保证第三方LLM provider跨时间完全返回相同文本，也不能重建现实消费者心理。模型没有保存或推断隐性chain-of-thought；显式reasoning字段只是schema约束的简短审计输出。

当前未建模机制包括真实平台推荐算法、多平台迁移、网络rewiring、竞争品牌主动策略、企业内生预算优化、现实库存/价格变化以及消费者退出品类。后续若加入这些机制，应创建新模型版本，不得把扩展结果与v3.3.1正式样本合并。

# 第三章 GABM模型构建（v3.3.1正文底稿）

## 3.1 研究情境、模型目的与适用范围

本研究设置虚构绿色快消品品牌VerdantCo Oat及其植物奶产品。T1—T4为共同历史期，T5出现针对企业绿色主张的虚构信任危机，企业可在T6或T10发布澄清，并通过不同节点投放规则形成直接触达。选择虚构品牌的目的，是避免把实验刺激误写为现实企业事件，并使内容、时机与渠道能够在相同背景下受控比较。

模型目的不是复制某一真实社交平台，也不是预测某品牌销量。其直接用途是：在冻结的Agent属性、社会网络、自然语言刺激、心理状态转移和重复购买机制下，比较企业澄清内容、投放渠道与回应时机如何改变模型内的直接触达、品牌信任恢复和预期重复品牌选择。所有结论都以该适用范围为前提。

绿色消费与社会扩散研究支持考察消费者之间的信息关注、分享和异质性互动（王建明、冯雨，2023，《绿色消费会传染吗？——绿色消费的社会扩散效应及其形成机制》；Janssen、Jager，2002，《Stimulating diffusion of green products: Co-evolution between firms and consumers》），但不为本模型的Agent数量、网络类型、时点和系数提供直接校准。上述设置均在本章作为研究设计披露。

## 3.2 总体架构与混合建模原则

v3.3.1采用“生成式语义评价＋规则化状态转移”的混合GABM。模型分为五层：信息环境层生成危机新闻、企业澄清与消费者UGC；语义评价层把Agent实际观察到的文本转换为结构化指标；心理状态层更新信任、态度、主观规范和购买意向；社会网络层记录信息投递与消费者传播；需求层在认知仿真结束后重放购买机会、条件品牌选择和忠诚更新。

LLM的主要权限被限制在语义评价接口。其输出包括valence、arousal、credibility、evidence strength、topic relevance、perceived empathy、peer approval和hypocrisy perceived，并附一条用于审计的显式简短理由。LLM不直接生成信任分数，不决定是否发帖、是否购买或选择哪个品牌，也不生成正式统计结果；上述状态与行为均由冻结规则和随机种子决定。但当前实现存在一个必须披露的文本接口：当规则判定Agent发帖时，该显式评价理由会被复用为UGC正文并进入后续网络传播。因此，LLM不控制发帖事件，却会影响被传播文本的内容。该设计保留了状态转移与行为触发的可复算性，但UGC语义仍可能继承模型输出偏差。生成式Agent研究支持这种自然语言Agent架构的可行性，同时要求防止把“表现可信”误当作现实行为有效（Park等，2023，《Generative Agents: Interactive Simulacra of Human Behavior》；Adornetto等，2025，《Generative agents in agent-based modeling: Overview, validation, and emerging challenges》）。

## 3.3 实体、状态变量与尺度

### 3.3.1 认知Agent（Cognitive Agents）

模型包含20个认知Agent。每个Agent具有稳定身份和一组Persona属性，用于覆盖绿色涉入、品牌信任基线、态度、主观规范、感知行为控制、信息加工倾向、购买频率及网络位置等机制差异。选择20个Agent是计算预算与机制覆盖之间的工程折中，不是现实消费者样本量。绿色消费者分层文献支持引入心理和态度异质性，但不能证明当前Persona配额具有总体代表性（Straughan、Roberts，1999，《Environmental segmentation alternatives: A look at green consumer behavior in the new millennium》）。

Agent i在Tick t的核心心理状态写为：

$$S_{i,t}=\{Trust_{i,t},Att_{i,t},SN_{i,t},PBC_i,CrisisMemory_{i,t},RepairMemory_{i,t}\}.$$

其中Trust取0—10，Att、SN和PBC取0—1。PBC在当前基线中作为Persona/state输入，不发生动态更新；因此，本研究没有检验动态感知行为控制机制。

### 3.3.2 信息对象与观察记录

信息对象分为危机新闻、企业澄清和消费者UGC。每条信息保留来源、创建Tick、投递Tick、目标Agent和文本内容。只有Agent在当前Tick实际观察到信息时，才调用语义评价并更新相应状态；没有观察时不生成虚构语义记录。该规则用于保持“暴露—评价—状态变化”的时间一致性。

### 3.3.3 Micro-buyers与统计单位

每个认知Agent下设置25个微型购买者（micro-buyers），用于离线需求重放中的数值分辨率。微型购买者共享上层Agent的认知历史，并通过冻结随机种子形成购买机会与选择结果。M=25不是新增的消费者样本，更不增加正式统计自由度。正式推断单位是包含全部九个条件的一次完整replication block。

## 3.4 时间、事件和处理结构

单次认知运行包括35个Tick，每个Tick定义为一个simulation day。T1—T4为共同历史，T5发生危机，Immediate条件在T6澄清，Delayed条件在T10澄清，终点为T35。时间映射是模型时钟，不代表现实最优响应小时或天数。危机时机固定后，T6—T9构成延迟澄清尚未启动的早期窗口。

处理结构为2种内容×2种渠道×2种时机加共同不澄清组。内容包括Rational-evidence和Emotional-empathy；渠道包括Hub与Random；时机包括Immediate与Delayed。八个处理单元完全交叉，另设NoClarification-Control。Rational与Empathy都是复合文本框架，因而后续内容对比只能识别两套完整刺激的总体差异。

## 3.5 自然语言刺激与结构化语义评价

Agent接收文本后，LLM按照冻结schema返回八项语义变量。效价取−1至1，其余连续变量取0至1，伪善感知为布尔值。各变量承担不同功能：效价和唤醒表示情绪方向与激活程度；可信度、证据强度和主题相关性表示信息加工线索；感知共情表示关系修复线索；同伴认同用于主观规范更新；伪善感知用于放大负面危机增量。

启发式—系统加工研究支持保留来源和论据线索，但本模型没有直接测量加工路径潜变量（Chaiken，1980，《Heuristic versus systematic information processing and the use of source versus message cues in persuasion》）。在线传播研究支持将唤醒与效价分开，但不意味着高唤醒内容必然在本情境中占优（Berger、Milkman，2012，《What makes online content viral?》）。所以，语义变量是具有理论依据的模型接口，不是已校准心理量表。

为了控制LLM不稳定性，运行记录模型、temperature、prompt profile、请求种子、原始响应、schema状态、fallback状态和哈希。显式简短理由只是可审计输出，不是隐藏思维链；它在规则触发发帖后被复用为UGC，因而还应作为后续信息输入保存和追踪。正式有效block要求schema错误、解析错误和semantic fallback均为零。selected Real-LLM robustness只能作为工程稳定性证据，不能替代现实被试效度或UGC内容效度。

## 3.6 心理状态更新

### 3.6.1 危机记忆与修复记忆

模型首先对上一Tick的危机记忆和修复记忆进行不对称保留：

$$C^-_{i,t}=\rho_c C_{i,t-1},\qquad R^-_{i,t}=\rho_r R_{i,t-1}.$$

若Agent观察到负向信息，则由情绪效价、唤醒、可信度、主题相关性和伪善感知形成危机增量；若观察到正向信息，则由情绪、可信度、相关性与证据强度形成修复增量。修复增量受到既有修复记忆的饱和约束，以避免同类澄清无限线性累积。Agent实际观察到企业澄清时，感知共情还形成关系修复增量。

信任目标写为：

$$TrustTarget_{i,t}=clip(BaselineTrust_i+w_rR_{i,t}-w_cC_{i,t},0,10).$$

最终信任并不直接跳到目标，而是按事件期或安静期调整率部分靠近目标：

$$Trust_{i,t}=clip[Trust_{i,t-1}+\lambda_t(TrustTarget_{i,t}-Trust_{i,t-1}),0,10].$$

动态信任修复文献支持保留历史状态、关系互动和恢复过程（Kim、Dirks、Cooper，2009，《The repair of trust: A dynamic bilateral perspective and multilevel conceptualization》；Lewicki、Brinsfield，2017，《Trust repair》），但ρ、w和λ的具体值均为工程参数，尚未经验校准。

### 3.6.2 Attitude与Subjective norm

观察发生时，模型将效价映射到0—1区间，并与可信度、证据强度和主题相关性形成综合信号；Attitude以有界部分调整方式更新。Subjective norm不从企业信息直接更新，而只根据Agent实际观察到的同伴认可信息变化。该区分避免把企业说服和社会规范混为同一通道。

TPB支持Attitude、Subjective norm和PBC共同进入意向，但不规定本研究的更新函数和权重（Ajzen，1991，《The theory of planned behavior》）。中国绿色购买研究支持把个人相关性和社会规范纳入绿色意向解释，但同样不能替代本模型参数校准（盛光华、龚思羽、解芳，2019，《中国消费者绿色购买意愿形成的理论依据与实证检验——基于生态价值观、个人感知相关性的TPB拓展模型》）。

### 3.6.3 购买意向与发帖意向

购买意向采用有界Logit形式：

$$PI_{i,t}=\sigma[\beta_0+\beta_A(Att_{i,t}-0.5)+\beta_S(SN_{i,t}-0.5)+\beta_P(PBC_i-0.5)+\beta_T(Trust_{i,t}/10-0.5)].$$

当前实现冻结为β0=−0.50、βA=1.40、βS=0.80、βP=0.60、βT=1.20。Trust是漂绿危机情境下的扩展状态，并非Ajzen原始TPB的组成变量。因此，论文应称其为“TPB式购买意向桥接”，不能声称完整检验TPB。这里记录的是认知Agent层的购买意向轨迹；需求层会使用同一函数结构，以微型购买者自身的PBC重新计算机会发生时的购买意向，两者不能当作两项独立心理测量。

发帖意向只在观察发生时生成，并由唤醒与效价绝对值进入Logit函数。该结构反映“激活程度可能与传播相关”的理论方向，但系数仍是工程假设（Berger、Milkman，2012，《What makes online content viral?》）。

## 3.7 社会网络与澄清扩散

### 3.7.1 固定有向BA网络

基线采用固定有向BA网络，以形成连接异质性和可辨识的高出度节点。BA模型能够生成尺度异质结构，为Hub操作化提供受控基准（Barabási、Albert，1999，《Emergence of scaling in random networks》）。但本研究网络不是由真实平台关系数据拟合得到，且单次运行内拓扑不变化；变化的是信息状态和传播流量。因此，论文不得把模型结果称为“网络拓扑演化”。

网络在同一replication block的九个条件间保持一致，以减少处理比较中的拓扑混杂。现有BA、Watts–Strogatz、community、方向规则及N=20/40/80实验只用于工程稳健性，不构成现实平台结构效度。

### 3.7.2 Hub与Random投放

企业付费种子节点数量固定为K=3。Hub规则选择高出度节点，Random规则从符合条件的节点中随机选择相同数量的种子。K表示种子数量预算，不是货币预算。企业澄清还包括公共暴露、概率0.55的一跳放大和一个Tick的投递滞后；这些均为冻结工程设置。

有限种子选择与网络影响最大化研究说明节点结构会影响潜在覆盖（Kempe、Kleinberg、Tardos，2003，《Maximizing the Spread of Influence through a Social Network》），但复杂传染研究提示连接优势取决于重复确认与网络桥宽度（Centola、Macy，2007，《Complex Contagions and the Weakness of Long Ties》）。因此，本研究的Hub—Random对比首先以企业直接触达比例衡量；任何下游信任和选择变化都必须另行测量，不能由reach替代。

### 3.7.3 消费者UGC

Agent在观察信息后依据发帖意向和冻结随机种子决定是否发布UGC。发帖事件由规则决定；若发帖，当前实现将LLM在该次观察中生成的显式简短评价理由作为UGC正文，无理由时使用冻结回退文本。UGC随后沿有向网络边传递，接收者重新进行语义评价，而不是继承发送者的信任或态度。该设计使社会影响通过“观察到同伴文本—形成语义评价—更新主观规范或其他心理状态”的路径发生，但也形成LLM文本在网络中的内生反馈；这种反馈属于模型机制，不得表述为真实消费者自发内容生成。

## 3.8 绿色快消品重复品牌选择

认知仿真完成后，需求层读取完整的Trust、Attitude和Subjective norm历史并进行离线重放。每个微型购买者具有由所属Persona购买频率区间确定的首次机会相位；每次机会后，再从该Persona冻结的5—7、7—10、10—14或14—28 Tick允许区间中确定性重抽下一间隔。机会调度不读取处理标签、心理状态或既往品牌选择，因此在相同demand seed下不受处理影响。

机会发生时，需求层先以微型购买者PBC和当期上层心理状态重新计算TPB式购买意向，再在其Logit上叠加微型购买者偏好偏移和上一期忠诚状态，形成焦点品牌条件选择概率。冻结随机数只用于生成已实现品牌选择，选择结果再通过有界EWMA更新忠诚。因此，焦点品牌选择概率不等于认知Agent层购买意向，且其后续路径会受到已经实现的历史选择影响。

品牌选择模型的概念分解受到重复购买和品牌忠诚研究启发（Guadagni、Little，1983，《A Logit Model of Brand Choice Calibrated on Scanner Data》，包外引用），但机会区间、偏好偏移、微型购买者数量和忠诚更新均未经扫描面板数据校准。正式P5使用各次品类购买机会上的条件选择概率均值；该均值条件于模型生成的既往忠诚路径，因此称为“焦点品牌预期选择份额”时必须保留这一条件性。已实现选择只作描述性一致性检查。

## 3.9 过程调度与共同历史

每个Tick按固定顺序执行：读取本Tick到达的信息；对实际观察文本进行语义评价；更新危机/修复记忆、Trust与Attitude；依据同伴观察更新Subjective norm；计算购买意向和发帖意向；记录并投递UGC；保存状态与审计字段。认知运行完成后才执行离线需求重放。

九个条件在T1—T4共享共同历史，危机事件在T5保持一致。条件差异只能从预定澄清时点和渠道开始出现。正式有效block要求处理前状态相等、控制组无企业澄清污染、九条件共享topology hash，并能从原始记录重建全部estimand。

## 3.10 初始化、输入与参数身份

初始化包括20个Persona、固定网络、共同历史、危机文本、两套澄清文本、处理矩阵和随机种子。模型没有把现实人口分布、真实品牌销量、真实社交平台边或消费者面板作为输入。因此，当前研究属于机制探索与受控计算实验，而非数据驱动的市场预测。

所有参数必须按三类披露：一是文献支持的构念关系，例如TPB变量进入意向、信息论据与来源线索需要区分；二是研究设计，例如T5/T6/T10/T35、K=3、N=20和M=25；三是工程参数，例如信任记忆率、传播概率和Logit系数。第二、三类均不得写成文献估计值。ABM校准研究表明，参数估计需要明确经验目标和不确定性方法（Platt，2020，《A comparison of economic agent-based model calibration methods》；Grazzini、Richiardi、Tsionas，2017，《Bayesian estimation of agent-based models》），而本研究当前尚未完成现实数据校准。

## 3.11 复现、验证与证据边界

模型按ODD思路记录目的、实体、状态、过程、调度、初始化、输入和子模型（Grimm等，2020，《The ODD protocol for describing agent-based and other simulation models: A second update to improve clarity, replication, and structural realism》）。代码层建立模型—实现—输出追踪表，运行层记录Git HEAD、工作树状态、参数快照、模型与prompt、种子、schema及文件哈希。

证据分为五层。第一层为实现验证，检查单元测试、边界、schema、共同历史和处理污染；第二层为工程稳健性，检查时间范围、信任参数、澄清概率与滞后、网络拓扑/方向/规模及微型购买者分辨率；第三层为单次Real-LLM描述，只用于展示固定run中的轨迹与Agent异质性；第四层为Pilot方差规划；第五层才是以独立replication blocks为单位的正式推断。当前前三层已有不同程度证据，Pilot与正式推断均尚未形成结果。

用户在查看任何有效Pilot结果前取消正式replication-block上限。Pilot现固定为P001—P024共24个独立cognitive blocks，只用于估计规划方差；每个block的24次离线demand replay不是额外独立重复。正式`N_required`将在Pilot后从N=10向上搜索，取四个预设相关结构场景中同时满足P1、P2、P5各自single-MDE Holm检出概率≥.90的最保守首个通过N。资源不足只能形成执行可行性问题，不能事后放宽标准。Pilot及正式实验均未在本章写作过程中执行。

## 3.12 本章小结

本章把第二章的理论关系转化为可执行的五层GABM：自然语言信息先形成受约束语义评价，再进入可审计的心理状态更新、固定社会网络传播和快消品重复选择。模型通过限制LLM权限、区分触达与说服、区分意向与购买机会、区分Agent与replication block，降低了常见的构念混淆。与此同时，现实参数校准、平台网络拟合和消费者外部有效性仍未完成，这些限制决定了后续实验结果只能首先解释为冻结模型内部的机制证据。

# v3.3.1论文框架图登记

## FIG-MECH-01：语义—心理—网络—行为机制架构

- 可编辑源：`FIG-MECH-01_v331_mechanism_architecture.svg`
- 论文预览：`FIG-MECH-01_v331_mechanism_architecture.png`
- 建议图题：图3-X 绿色快消品信任危机下的GABM机制架构
- 允许用途：模型设计/研究方法章节；说明处理、语义评价、心理状态、网络传播、重复选择和估计量之间的实现关系。
- 必须保留：LLM只负责语义评价；心理、传播和行为结果由可审计规则生成；Agent轨迹不是正式重复推断。
- 替代旧图内容：删除KOL/Bridge正式因素、任意内容配比、T30 endpoint、LLM直接生成购买决策和泛化ROI表述。

## FIG-ROUTE-01：论文研究与技术路线

- 可编辑源：`FIG-ROUTE-01_v331_thesis_technical_route.svg`
- 论文预览：`FIG-ROUTE-01_v331_thesis_technical_route.png`
- 建议图题：图1-X 研究与技术路线
- 状态语义：绿色为已完成/可用基础，黄色为部分固定但禁止执行，灰色为尚未开始。
- Pilot口径：`N_max=10`是查看Pilot结果前固定的正式replication-block预算上限；P001–P006仍是6个Pilot cognitive blocks；正式N尚未由方差证据证明。
- 当前执行门禁：provider-call ceiling、时间预算、clean execution SHA和真实Pilot授权仍缺失。

## 渲染与版本规则

SVG保留可编辑文本；PNG按1600×1000和1400×1720生成并完成视觉检查。由于Linux验收容器没有CJK字体，PNG生成时只在临时QA目录中使用用户提供论文PDF已嵌入的字形轮廓，仓库未保存、分发或依赖任何字体文件。Windows论文排版时可直接用Microsoft YaHei等本机中文字体打开SVG；若只调整字体、论文图号或画布尺寸，不改变机制内容，则不需要重新运行模型。

两图均属于概念/方法artifact，不是实验结果。任何处理、时间点、状态变量、证据等级或执行状态变化，都必须先更新协议和Decision Log，再同步图源与PNG。

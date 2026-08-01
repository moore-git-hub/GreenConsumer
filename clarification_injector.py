"""
clarification_injector.py — 企业澄清信息注入器

根据实验配置，在指定 Tick 向指定节点投放企业澄清内容。
澄清消息通过 incoming_messages 注入，与现有消息机制一致，
目标节点会在同一 Tick 通过 Perceive→Reflect→Plan 管线处理该消息。
"""
from typing import List

# ══════════════════════════════════════════════════════════════════════
# 澄清内容模板
# ══════════════════════════════════════════════════════════════════════

CONTENT_TEMPLATES = {
    "rational-evidence": (
        "[Hypothetical experimental stimulus — not a factual company statement] "
        "Oatly Official Statement — Verified Evidence on Our Sustainability Work: "
        "We have heard the questions raised about our investment partnership and want to respond with facts you can check. "
        "(1) Our investor holds a 10% minority stake with zero board seats and zero governance rights over our sustainability decisions — "
        "confirmed in our SEC filing (Form F-1, July 2020, p.114). "
        "(2) Since 2020, our total oat cultivation area certified under the Rainforest Alliance standard has grown from 12,000 to 31,000 hectares — "
        "a verified 158% increase, audited by an independent third party. "
        "(3) Our carbon footprint per liter has been independently verified by Bureau Veritas: "
        "0.44 kg CO₂e (2019) to 0.38 kg CO₂e (2021), a confirmed 14% reduction. "
        "(4) Our supply chain sourcing in regions of environmental sensitivity has been reviewed quarterly by our Sustainability Council "
        "with no supply chain exposure identified in high-deforestation-risk areas. "
        "We are publishing the full investor agreement and third-party audit reports at oatly.com/transparency today. "
        "We will not ask you to trust us without proof."
    ),
    "emotional-empathy": (
        "[Hypothetical experimental stimulus — not a factual company statement] "
        "A personal message from Oatly's CEO, Toni Petersson: "
        "I have spent the past week reading your messages, and I want to say clearly: your frustration is valid. "
        "When you chose Oatly, you were making a statement about the kind of world you want. "
        "We did not communicate clearly enough about the terms and safeguards around our investment partnership, "
        "and that failure is on us. "
        "Here is what we are committing to — not as a PR move, but because we owe it to the community that built this brand: "
        "We are establishing an independent Community Trust Board — with three seats appointed by Oatly consumers through a public vote — "
        "that has binding review rights over any future investment partnership before it is signed. "
        "We are also opening our quarterly sustainability audit for public comment. "
        "We know words are cheap right now. We are asking for the chance to earn back what was broken — "
        "not by asking you to forget, but by showing you, quarter by quarter, that the values you believed in were never just marketing."
    ),
}


class ClarificationInjector:
    """
    企业澄清信息注入器。

    职责：
      - 根据 ExperimentConfig 的 timing_factor 判断何时注入
      - 根据 content_factor 选择消息模板
      - 向 target_nodes 列表中的 Agent 信箱投放消息
    """

    def __init__(self, config):
        """
        Args:
            config: ExperimentConfig 实例
        """
        self.content_factor = config.content_factor
        self.clarification_tick = config.clarification_tick  # None = 不澄清
        self.target_nodes: List[str] = []  # 由外部在网络构建后设置
        # ── TASK_002 审计回执：最近一次 inject() 实际成功写入 inbox 的 Agent ID ──
        # 只写不读，不参与任何投放判定；供 agent_records 的
        # clarification_injected（阶段②）取真实来源。
        self.last_injected_ids: List[str] = []

    def set_target_nodes(self, nodes: List[str]):
        """设置目标投放节点（由 NodeSelector 选出后调用）"""
        self.target_nodes = nodes

    def should_inject(self, current_tick: int) -> bool:
        """当前 Tick 是否需要注入澄清"""
        if self.clarification_tick is None:
            return False
        return current_tick == self.clarification_tick

    def get_message(self) -> dict:
        """获取澄清消息包

        TASK_002 审计增强：消息包内显式携带 content_factor，
        使下游 Reflect / Plan 层能从**实际被观察到的消息**读取澄清内容类型，
        不再需要从 ExperimentConfig 反推（避免「配置声称注入」与「实际被观察」不一致）。
        """
        content = CONTENT_TEMPLATES[self.content_factor]
        return {
            "source": "Enterprise_Clarification",
            "content": content,
            "type": "clarification",
            "content_factor": self.content_factor,
        }

    async def inject(self, agents, current_tick: int) -> int:
        """
        向目标节点注入澄清消息。

        Args:
            agents: Agent 实例列表
            current_tick: 当前仿真 Tick

        Returns:
            实际注入的节点数

        副作用（TASK_002 审计）：
            self.last_injected_ids 被本次调用**覆盖写**，等于本 Tick 实际成功写入
            inbox 的 Agent ID 列表；未注入时为空列表。
            返回值恒等于 len(self.last_injected_ids)。
        """
        # 无条件重置：避免上一 Tick 的回执泄漏到本 Tick（阶段②误判为 True）
        self.last_injected_ids = []

        if not self.should_inject(current_tick):
            return 0

        msg = self.get_message()
        injected_ids = []

        for ag in agents:
            if ag.agent_id in self.target_nodes:
                state_plugin = ag.get_component("state")._plugin
                s_data = getattr(state_plugin, "state_data",
                                 getattr(state_plugin, "_state_data", {}))
                inbox = s_data.get("incoming_messages", [])
                await state_plugin.set_state("incoming_messages", list(inbox) + [msg])
                # 只有 set_state 成功返回后才登记，确保回执 == 实际写入
                injected_ids.append(ag.agent_id)

        self.last_injected_ids = injected_ids
        injected_count = len(injected_ids)

        if injected_count > 0:
            content_short = "Rational" if self.content_factor == "rational-evidence" else "Empathy"
            print(f"💊 [Clarification] Tick {current_tick} | "
                  f"Content={content_short} | "
                  f"Injected to {injected_count}/{len(self.target_nodes)} nodes")

        return injected_count


if __name__ == "__main__":
    # 快速验证模板长度（150-300词为有效范围：内容丰富但不超出Prompt预算）
    for name, template in CONTENT_TEMPLATES.items():
        word_count = len(template.split())
        print(f"  {name}: {word_count} words ({'✅' if 150 <= word_count <= 300 else '❌'})")

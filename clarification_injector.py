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
        "Oatly Official Statement on the Blackstone Investment — Facts and Evidence: "
        "We are aware that our $200M partnership with Blackstone has raised serious concerns, and we owe you a transparent, factual response. "
        "Here is what the data shows: "
        "(1) Blackstone's 10% minority stake gives them zero seats on our board and zero veto rights over our sustainability decisions — confirmed in our SEC filing (Form F-1, July 2020, p.114). "
        "(2) Since this investment closed, our total oat cultivation area certified under the Rainforest Alliance standard has grown from 12,000 to 31,000 hectares — an increase of 158% over 18 months. "
        "(3) Our carbon footprint per liter of product has been independently audited by Bureau Veritas and fell from 0.44 kg CO₂e (2019) to 0.38 kg CO₂e (2021), a verified 14% reduction. "
        "(4) We acknowledge that Blackstone has investments linked to land use change in Brazil. We cannot control their broader portfolio. What we can document is that no Blackstone capital has been directed to Oatly's supply chain in regions with deforestation risk — a commitment monitored quarterly by our Sustainability Council. "
        "We are publishing the full investor agreement and third-party audit reports at oatly.com/transparency today. If the evidence does not satisfy you, we accept that judgment. We will not ask you to trust us without proof."
    ),
    "emotional-empathy": (
        "[Hypothetical experimental stimulus — not a factual company statement] "
        "A personal message from Oatly's CEO, Toni Petersson: "
        "I have spent the past week reading your messages, your posts, and your anger — and I want to say clearly: your frustration is completely valid. "
        "When you chose Oatly, you weren't just buying a drink. You were making a statement about the kind of world you want. The news about our Blackstone investment felt like a betrayal of that statement, and I understand why. "
        "I want to be honest with you about something I wish we had said sooner: we needed growth capital to build the factories that would let oat milk reach people beyond specialty cafés. We chose a financial partner whose other investments conflict with values we share with you. That was a tension we underestimated, and we got that wrong. "
        "Here is what we are committing to, not as a PR move, but because we genuinely believe we owe it to the community that built this brand: "
        "We are establishing an independent Community Trust Board — with three seats appointed by Oatly consumers through a public vote — that has the right to review any future investment partnership before it is signed. "
        "We know words are cheap right now. We are asking for the chance to earn back what was broken — not by asking you to forget, but by showing you, quarter by quarter, that the values you believed in were never just marketing."
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

    def set_target_nodes(self, nodes: List[str]):
        """设置目标投放节点（由 NodeSelector 选出后调用）"""
        self.target_nodes = nodes

    def should_inject(self, current_tick: int) -> bool:
        """当前 Tick 是否需要注入澄清"""
        if self.clarification_tick is None:
            return False
        return current_tick == self.clarification_tick

    def get_message(self) -> dict:
        """获取澄清消息包"""
        content = CONTENT_TEMPLATES[self.content_factor]
        return {
            "source": "Enterprise_Clarification",
            "content": content,
            "type": "clarification"
        }

    async def inject(self, agents, current_tick: int) -> int:
        """
        向目标节点注入澄清消息。

        Args:
            agents: Agent 实例列表
            current_tick: 当前仿真 Tick

        Returns:
            实际注入的节点数
        """
        if not self.should_inject(current_tick):
            return 0

        msg = self.get_message()
        injected_count = 0

        for ag in agents:
            if ag.agent_id in self.target_nodes:
                state_plugin = ag.get_component("state")._plugin
                s_data = getattr(state_plugin, "state_data",
                                 getattr(state_plugin, "_state_data", {}))
                inbox = s_data.get("incoming_messages", [])
                await state_plugin.set_state("incoming_messages", list(inbox) + [msg])
                injected_count += 1

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

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
        "Official Statement from Oatly: We acknowledge the concerns raised about our investment partners. "
        "Here are the verified facts: (1) Our carbon footprint has been independently audited by Bureau Veritas, "
        "showing a 73% reduction compared to dairy milk per liter. (2) We have committed $50M to a new "
        "Sustainability Accountability Fund with quarterly public reporting. (3) Our supply chain is now "
        "100% certified by the Rainforest Alliance. We invite scrutiny — all audit reports are publicly "
        "available at oatly.com/transparency. Numbers don't lie. We believe in accountability through data."
    ),
    "emotional-empathy": (
        "A message from Oatly's team: We hear you. We understand the anger and the feeling of betrayal. "
        "You trusted us to be different, and we let you down. We are deeply sorry. The truth is, we made "
        "a difficult choice under financial pressure, and we should have been transparent from day one. "
        "We are not perfect, but we are committed to earning back your trust — not with words, but with "
        "actions. Starting today, we are restructuring our investor relationships and publishing monthly "
        "impact reports. We owe you that honesty. Thank you for holding us accountable."
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
    # 快速验证模板长度
    for name, template in CONTENT_TEMPLATES.items():
        word_count = len(template.split())
        print(f"  {name}: {word_count} words ({'✅' if 50 <= word_count <= 200 else '❌'})")

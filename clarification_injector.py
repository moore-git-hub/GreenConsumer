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
        "[Hypothetical experimental stimulus; Fictional scenario; not a factual company statement] "
        "VerdantCo Structured Evidence Summary: "
        "VerdantCo is a fictional sustainability-oriented consumer brand created solely for this experiment. "
        "We are responding with a structured explanation, document disclosure, and checkable evidence about the stipulated investment controversy. "
        "Fact 1: the fictional investor holds only a minority stake. "
        "Fact 2: the investor has no board control over VerdantCo's sustainability policy. "
        "Fact 3: our prior communication about the partnership was insufficient. "
        "Fact 4: we will publish partnership governance information. "
        "Fact 5: we will publish an independent sustainability review. "
        "Fact 6: we will establish a future-investment review safeguard before any similar partnership. "
        "Fact 7: trust must be rebuilt through observable actions, not slogans. "
        "Our emphasis here is verification, audit, procedural transparency, and facts consumers can inspect."
    ),
    "emotional-empathy": (
        "[Hypothetical experimental stimulus; Fictional scenario; not a factual company statement] "
        "VerdantCo Responsibility and Relationship Message: "
        "VerdantCo is a fictional sustainability-oriented consumer brand created solely for this experiment. "
        "We hear why this controversy feels like a breach of the values consumers associated with the brand. "
        "We acknowledge the frustration and concern created by the stipulated investment controversy. "
        "Fact 1: the fictional investor holds only a minority stake. "
        "Fact 2: the investor has no board control over VerdantCo's sustainability policy. "
        "Fact 3: our prior communication about the partnership was insufficient. "
        "Fact 4: we will publish partnership governance information. "
        "Fact 5: we will publish an independent sustainability review. "
        "Fact 6: we will establish a future-investment review safeguard before any similar partnership. "
        "Fact 7: trust must be rebuilt through observable actions, not slogans. "
        "Our emphasis here is responsibility, consumer frustration, value identification, relationship repair, and community concern."
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
        self.target_nodes: List[str] = []  # K paid-amplification seeds
        self.public_exposure_nodes: List[str] = []
        self.amplified_nodes: List[str] = []
        self.last_exposure_modes = {}
        # ── TASK_002 审计回执：最近一次 inject() 实际成功写入 inbox 的 Agent ID ──
        # 只写不读，不参与任何投放判定；供 agent_records 的
        # clarification_injected（阶段②）取真实来源。
        self.last_injected_ids: List[str] = []

    def set_target_nodes(self, nodes: List[str]):
        """设置 K 个 paid-amplification seed 节点。"""
        self.target_nodes = list(nodes)

    def set_public_exposure_nodes(self, nodes: List[str]):
        """设置公共企业声明的有机基础曝光节点。"""
        self.public_exposure_nodes = list(nodes)

    def set_amplified_nodes(self, nodes: List[str]):
        """设置 paid seeds 经真实网络拓扑产生的一跳放大触达。"""
        self.amplified_nodes = list(nodes)

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
        # 无条件重置：避免上一 Tick 的回执泄漏到本 Tick。
        self.last_injected_ids = []
        self.last_exposure_modes = {}

        if not self.should_inject(current_tick):
            return 0

        base_msg = self.get_message()
        injected_ids = []
        recipients = (
            set(self.public_exposure_nodes)
            | set(self.target_nodes)
            | set(self.amplified_nodes)
        )

        for ag in agents:
            if ag.agent_id in recipients:
                modes = []
                if ag.agent_id in self.public_exposure_nodes:
                    modes.append("public_organic")
                if ag.agent_id in self.target_nodes:
                    modes.append("paid_seed")
                if ag.agent_id in self.amplified_nodes:
                    modes.append("paid_one_hop")

                msg = dict(base_msg)
                msg["exposure_modes"] = list(modes)

                state_plugin = ag.get_component("state")._plugin
                s_data = getattr(state_plugin, "state_data",
                                 getattr(state_plugin, "_state_data", {}))
                inbox = s_data.get("incoming_messages", [])
                await state_plugin.set_state("incoming_messages", list(inbox) + [msg])
                injected_ids.append(ag.agent_id)
                self.last_exposure_modes[ag.agent_id] = list(modes)

        self.last_injected_ids = injected_ids
        injected_count = len(injected_ids)

        if injected_count > 0:
            content_short = "Rational" if self.content_factor == "rational-evidence" else "Empathy"
            print(f"💊 [Clarification-v2] Tick {current_tick} | "
                  f"Content={content_short} | "
                  f"Public={len(self.public_exposure_nodes)} | "
                  f"PaidSeeds={len(self.target_nodes)} | "
                  f"OneHop={len(self.amplified_nodes)} | "
                  f"Reached={injected_count}")

        return injected_count


if __name__ == "__main__":
    # 快速验证模板长度（150-300词为有效范围：内容丰富但不超出Prompt预算）
    for name, template in CONTENT_TEMPLATES.items():
        word_count = len(template.split())
        print(f"  {name}: {word_count} words ({'✅' if 150 <= word_count <= 300 else '❌'})")

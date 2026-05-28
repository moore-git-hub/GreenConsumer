"""
ConsumerPlanPlugin — Plan 层（System 2：慢速理性决策）

信任更新架构（双过程理论 + shock_anchor 机制）：
  ┌─────────────────────────────────────────────────────────────────┐
  │  Step 1  遗忘曲线（从 shock_anchor 向 baseline 回归）            │
  │          trust = anchor + (1-exp(-λ*quiet)) * (base - anchor)   │
  │                                                                 │
  │  Step 2  叠加 System 1 的情绪冲击（来自 Reflect 层）              │
  │          final_trust = trust_after_decay + Δ_affective          │
  │                                                                 │
  │  Step 3  更新 shock_anchor（事件当天锚定新的最低点）              │
  │                                                                 │
  │  Step 4  LLM 只做行为决策（is_buying / is_posting）               │
  └─────────────────────────────────────────────────────────────────┘

关键设计：
  - shock_anchor 记录最近一次事件冲击后的信任值，作为遗忘曲线的固定起点
  - 避免"复利式加速回弹"：回归量由 quiet_ticks 绝对值决定，而非上一 Tick 的已回弹值
  - 事件当天（quiet_ticks=0）：遗忘曲线不执行，情绪冲击直接叠加，然后更新 shock_anchor
"""
import json
import re
import math
from agentkernel_standalone.mas.agent.base.plugin_base import PlanPlugin

# 各消费者类型的遗忘曲线衰减速率 λ
DECAY_LAMBDA = {
    "Active_Greens":     0.05,   # 记仇，恢复极慢
    "Convenient_Greens": 0.12,   # 适中偏慢
    "Dormant_Greens":    0.18,   # 遗忘较快
    "Non_Greens":        0.25,   # 快速回归（本来就不在乎）
}
DEFAULT_LAMBDA = 0.12

# 各消费者类型的初始信任基线（心理锚点）
INITIAL_BASELINE_TRUST = {
    "Active_Greens":     8.0,    # 对绿色品牌高度信任
    "Convenient_Greens": 6.5,    # 中等偏好
    "Dormant_Greens":    5.5,    # 无所谓
    "Non_Greens":        5.0,    # 纯看价格
}
DEFAULT_BASELINE = 5.5


class ConsumerPlanPlugin(PlanPlugin):
    async def init(self):
        pass

    def _get_agent(self):
        if hasattr(self, "agent") and self.agent: return self.agent
        if self.component and hasattr(self.component, "agent"): return self.component.agent
        if hasattr(self, "_component") and self._component: return self._component.agent
        return None

    def _get_plugin(self, name):
        agent = self._get_agent()
        if not agent: return None
        comp = agent.get_component(name)
        if not comp: return None
        p = getattr(comp, "_plugin", None)
        if p: return p
        return getattr(comp, "plugin", None)

    @staticmethod
    def _forgetting_curve(shock_anchor: float, baseline_trust: float,
                          quiet_ticks: int, lam: float) -> float:
        """
        Ebbinghaus 遗忘曲线 + 均值回归（从冲击锚定点回归）。

        公式：
            trust = shock_anchor + (1 - exp(-λ * quiet_ticks)) * (baseline - shock_anchor)

        性质：
          - quiet_ticks=0 → trust = shock_anchor（事件当天不回弹）
          - quiet_ticks→∞ → trust → baseline（完全回归）
          - 回归速度由 λ 和 quiet_ticks 的绝对值决定，不受中间 Tick 的影响

        示例（Active_Greens, λ=0.05, anchor=3.0, baseline=8.0）：
          quiet=1:  3.0 + 0.049*(8-3) = 3.24   （+0.24/天）
          quiet=5:  3.0 + 0.221*(8-3) = 4.11   （+0.22/天 平均）
          quiet=10: 3.0 + 0.393*(8-3) = 4.97
          quiet=20: 3.0 + 0.632*(8-3) = 6.16
          quiet=40: 3.0 + 0.865*(8-3) = 7.32
        """
        if quiet_ticks <= 0:
            return shock_anchor
        decay_rate = 1.0 - math.exp(-lam * quiet_ticks)
        return shock_anchor + decay_rate * (baseline_trust - shock_anchor)

    async def execute(self, current_tick: int) -> None:
        agent = self._get_agent()
        if not agent: return

        state_plugin = self._get_plugin("state")
        profile_plugin = self._get_plugin("profile")
        if not state_plugin or not profile_plugin: return

        s_data = getattr(state_plugin, "state_data", getattr(state_plugin, "_state_data", {}))
        p_data = getattr(profile_plugin, "profile_data",
                         getattr(profile_plugin, "_profile_data", {}))

        product_price = 4.0
        product_name = "Oatly Barista"

        # ── 1. 读取新闻 ──────────────────────────────────────────────────
        current_news = s_data.get("current_news", "")
        news_text = current_news.strip() if current_news.strip() else "Normal peaceful day. No major news."
        is_quiet_day = not current_news.strip()

        # ── 2. 平静期计数 ────────────────────────────────────────────────
        quiet_ticks = int(s_data.get("quiet_ticks", 0))
        quiet_ticks = quiet_ticks + 1 if is_quiet_day else 0
        await state_plugin.set_state("quiet_ticks", quiet_ticks)

        # ── 3. 读取信任状态与消费者类型 ──────────────────────────────────
        previous_trust = float(s_data.get("trust_score", 5.0))
        cluster_type = p_data.get("psychology", {}).get("cluster_type", "")
        baseline_trust = float(s_data.get("baseline_trust",
                                          INITIAL_BASELINE_TRUST.get(cluster_type, DEFAULT_BASELINE)))
        lam = DECAY_LAMBDA.get(cluster_type, DEFAULT_LAMBDA)

        # ── 4. 读取 shock_anchor（冲击锚定点） ──────────────────────────
        # shock_anchor = 最近一次事件冲击后的信任值，遗忘曲线从这里开始回归
        # 初始值 = baseline_trust（无冲击时，遗忘曲线不产生任何变化）
        shock_anchor = float(s_data.get("shock_anchor", baseline_trust))

        # ── 5. Step 1：遗忘曲线（从 shock_anchor 向 baseline 回归） ──────
        trust_after_decay = self._forgetting_curve(shock_anchor, baseline_trust, quiet_ticks, lam)

        # ── 6. Step 2：叠加 System 1 的情绪冲击 ──────────────────────────
        affective_change = float(s_data.get("trust_change_affective", 0.0))
        trust_after_shock = trust_after_decay + affective_change
        final_trust = round(max(0.0, min(10.0, trust_after_shock)), 3)

        # ── 7. Step 3：更新 shock_anchor ─────────────────────────────────
        # 事件当天（quiet_ticks=0）：用 final_trust 作为新的冲击锚定点
        # 平静期：shock_anchor 保持不变（遗忘曲线从固定点回归）
        if not is_quiet_day:
            await state_plugin.set_state("shock_anchor", final_trust)
        # 如果是平静期但有社交消息导致的情绪冲击（affective_change != 0），
        # 也需要更新 anchor（社交传播也是一种"事件"）
        elif abs(affective_change) > 0.5:
            await state_plugin.set_state("shock_anchor", final_trust)

        # 写入最终信任分
        await state_plugin.set_state("trust_score", final_trust)

        # ── 8. Step 4：LLM 只做行为决策 ──────────────────────────────────
        latest_thought = s_data.get("latest_thought", {})
        thought_str = json.dumps(latest_thought) if latest_thought else "Just my usual daily routine."
        persona = profile_plugin.get_prompt()

        prompt = f"""
        {persona}

        [Environment Context]
        Current Global News: {news_text}
        Product available: '{product_name}' (Price: ${product_price}).

        [Your Current Mental State]
        Your Trust Score RIGHT NOW: {final_trust:.1f}/10.0
        (This score already reflects today's news impact and memory decay — do NOT recalculate it.)
        Your Latest Inner Thought: {thought_str}

        [Task — Behavioral Decision]
        Based on your trust score and persona, decide your actions:

        1. **Purchase Decision (is_buying)**:
           - True if trust >= 5.0 AND price is acceptable for your income level.
           - False if trust < 4.0 OR you are actively boycotting.

        2. **Social Media Decision (is_posting)**:
           - True ONLY if: (a) there is fresh news TODAY, AND (b) your emotional reaction
             is strong (trust dropped sharply or you feel betrayed/excited), AND
             (c) your social role allows posting (Lurkers NEVER post).
           - False during quiet periods — people rarely post about old news.

        Output JSON ONLY:
        {{
            "is_buying": <boolean true or false>,
            "is_posting": <boolean true or false>,
            "post_content": "Your social media post IN ENGLISH (only if is_posting, else empty)",
            "reason": "One sentence explaining your decision. (IN ENGLISH)"
        }}
        """
        try:
            model = getattr(agent, "model", getattr(agent, "_model", None))
            if not model: return

            response = await model.chat(prompt)

            plan = {}
            if isinstance(response, str):
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    plan = json.loads(match.group(0))
                else:
                    raise ValueError(f"No JSON in response: {response[:80]}...")
            elif isinstance(response, list):
                plan = response[0]
            else:
                plan = response

            is_buying  = bool(plan.get("is_buying", False))
            is_posting = bool(plan.get("is_posting", False))

            plan["current_trust"]     = final_trust
            plan["is_buying"]         = is_buying
            plan["is_posting"]        = is_posting
            plan["trust_after_decay"] = round(trust_after_decay, 3)
            plan["affective_change"]  = round(affective_change, 3)
            plan["shock_anchor"]      = round(shock_anchor, 3)
            plan["decay_lambda"]      = lam
            plan["quiet_ticks"]       = quiet_ticks

            await state_plugin.set_state("plan_result", plan)

            # 控制台日志
            actions_str = []
            if is_buying:  actions_str.append("BUY")
            if is_posting: actions_str.append("POST")
            if not actions_str: actions_str.append("IGNORE")

            trust_delta = final_trust - previous_trust
            sign = "+" if trust_delta >= 0 else ""

            print(f"🧠 [Plan] {agent.agent_id} | "
                  f"Trust: {previous_trust:.1f}→{final_trust:.1f} ({sign}{trust_delta:.2f}) | "
                  f"Anchor:{shock_anchor:.1f} Decay→{trust_after_decay:.1f} Affect:{affective_change:+.1f} | "
                  f"λ={lam} Quiet:{quiet_ticks}d | {'+'.join(actions_str)}")

        except Exception as e:
            print(f"⚠️ [Plan Error] {agent.agent_id}: {e}")
            fallback_plan = {
                "current_trust":      final_trust,
                "is_buying":          False,
                "is_posting":         False,
                "trust_after_decay":  round(trust_after_decay, 3),
                "affective_change":   round(affective_change, 3),
                "shock_anchor":       round(shock_anchor, 3),
                "decay_lambda":       lam,
                "quiet_ticks":        quiet_ticks,
                "reason": "System parsing error, fell back to silent mode."
            }
            await state_plugin.set_state("plan_result", fallback_plan)

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass

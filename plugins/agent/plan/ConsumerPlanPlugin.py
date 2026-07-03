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
# 注意：遗忘曲线现在只在收到正面信息时才触发回升
# λ 控制的是"正面信息到来后的恢复速度"，而非"自动回升速度"
DECAY_LAMBDA = {
    "Active_Greens":     0.03,   # 即使有正面信息也恢复极慢（记仇）
    "Convenient_Greens": 0.08,   # 正面信息能缓慢修复
    "Dormant_Greens":    0.12,   # 正面信息能较快修复
    "Non_Greens":        0.20,   # 正面信息能快速修复（本来就不在乎）
}
DEFAULT_LAMBDA = 0.08

# 各消费者类型的初始信任基线（心理锚点）
INITIAL_BASELINE_TRUST = {
    "Active_Greens":     8.0,    # 对绿色品牌高度信任
    "Convenient_Greens": 6.5,    # 中等偏好
    "Dormant_Greens":    5.5,    # 无所谓
    "Non_Greens":        5.0,    # 纯看价格
}
DEFAULT_BASELINE = 5.5

# 各消费者类型的情绪冲击敏感度系数
# LLM 输出的 affective_change 会乘以此系数，控制不同人群的反应幅度
SENSITIVITY_MULTIPLIER = {
    "Active_Greens":     1.0,    # 全额感受冲击（对漂绿极度敏感）
    "Convenient_Greens": 0.6,    # 中等敏感
    "Dormant_Greens":    0.4,    # 低敏感（被动，需要强刺激）
    "Non_Greens":        0.15,   # 几乎不受环保相关新闻影响
}
DEFAULT_SENSITIVITY = 0.5


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
        Ebbinghaus 遗忘曲线 + 均值回归（从冲击锚定点回归）。情绪适应/均值回归函数（Hedonic Adaptation）

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

        # ── 1. 读取新闻与澄清状态 ────────────────────────────────────────
        current_news = s_data.get("current_news", "")
        news_text = current_news.strip() if current_news.strip() else "Normal peaceful day. No major news."
        is_quiet_day = not current_news.strip()

        # 澄清检测：读 last_observations（Reflect 处理后保存的只读快照）
        # 执行顺序：perceive → observations; reflect → 消费 observations → 清空 → 保存 last_observations
        # Plan 执行时 observations 已为空，必须从 last_observations 检测当天的澄清事件
        last_observations = s_data.get("last_observations", [])
        has_clarification = any(
            o.get("source") == "Enterprise_Clarification" or o.get("type") == "clarification"
            for o in last_observations
        )
        # 澄清当天不算平静日
        if has_clarification:
            is_quiet_day = False

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
        shock_anchor = float(s_data.get("shock_anchor", baseline_trust))

        # ── 5. Step 1：遗忘曲线逻辑 ─────────────────────────────────────
        # 规则：
        #   - 有事件当天（quiet_ticks=0）：遗忘曲线不执行，保持 previous_trust
        #   - 平静期 OR 正面信息：从 shock_anchor 向 baseline 缓慢回归
        trust_after_decay = previous_trust  # 默认：有事件当天不回弹

        if quiet_ticks > 0:
            # 平静期或正面信息日：遗忘曲线生效，从 shock_anchor 向 baseline 回归
            trust_after_decay = self._forgetting_curve(shock_anchor, baseline_trust, quiet_ticks, lam)

        # ── 6. Step 2：叠加 System 1 的情绪冲击（带敏感度系数） ──────────
        raw_affective = float(s_data.get("trust_change_affective", 0.0))
        sensitivity = SENSITIVITY_MULTIPLIER.get(cluster_type, DEFAULT_SENSITIVITY)
        affective_change = round(raw_affective * sensitivity, 3)

        trust_after_shock = trust_after_decay + affective_change
        final_trust = round(max(0.0, min(10.0, trust_after_shock)), 3)

        # ── 7. Step 3：更新 shock_anchor ─────────────────────────────────
        # 核心规则：只有全局事件当天（quiet_ticks=0 且有 current_news）才更新 anchor
        # 社交传播的负面冲击直接影响当前信任，但不改变遗忘曲线的回归起点
        # 这防止了"级联下探"：多个邻居的帖子不会把 anchor 无限往下拉
        if not is_quiet_day:
            # 全局事件或澄清当天：锚定新的冲击/恢复点
            await state_plugin.set_state("shock_anchor", final_trust)
        # 正面信息导致信任回升时，也更新 anchor（防止下次遗忘曲线从旧的低点开始）
        elif affective_change > 0 and final_trust > shock_anchor:
            await state_plugin.set_state("shock_anchor", final_trust)

        # 写入最终信任分
        await state_plugin.set_state("trust_score", final_trust)

        # ── 8. Step 4：LLM 只做行为决策 ──────────────────────────────────
        latest_thought = s_data.get("latest_thought", {})
        thought_str = json.dumps(latest_thought) if latest_thought else "Just my usual daily routine."
        persona = profile_plugin.get_prompt()

        prompt = f"""
        {persona}

        [Current Situation]
        Today's News: {news_text}
        Product you are considering: '{product_name}' (Price: ${product_price}).
        For reference: regular dairy milk costs $2.5, other plant-based milks cost $3.5–4.5.
        Brand facts you know: Oatly holds B Corp certification (score 93.4) and discloses
        a carbon footprint of 0.44 kg CO₂e per liter — significantly lower than dairy.
        It is currently rated the #1 barista plant milk by independent coffee professionals.

        [Your Current Mental State]
        Your Trust Score RIGHT NOW: {final_trust:.1f}/10.0
        Your Latest Inner Thought: {thought_str}
        Days since last major news event: {quiet_ticks}

        [Task — Make Your Decision as This Character]
        You are living your daily life as this consumer. Based on who you are, how you feel
        right now, and what you just read, naturally decide:

        1. **Would you buy this product today?**
           Consider your trust level, the price, and whether it aligns with your values.
           There is no fixed threshold — it is YOUR personal judgment.

        2. **Would you post something on social media today?**
           Only post if there is genuinely something worth saying right now.
           Posting frequency varies greatly by persona — most people post rarely.

        Stay fully in character. Output JSON ONLY:
        {{
            "is_buying": <boolean>,
            "is_posting": <boolean>,
            "post_content": "Your post IN ENGLISH (empty string if not posting)",
            "reason": "Brief first-person explanation of your decision (IN ENGLISH)"
        }}
        """
        try:
            model = getattr(agent, "model", getattr(agent, "_model", None))
            if not model: return

            response = await model.chat(prompt)

            plan = {}
            if isinstance(response, str):
                clean = re.sub(r"```(?:json)?", "", response).replace("```", "").strip()
                # 规范化 Python 字面量 → JSON 合法值
                clean = re.sub(r'\bNone\b',  'null',  clean)
                clean = re.sub(r'\bTrue\b',  'true',  clean)
                clean = re.sub(r'\bFalse\b', 'false', clean)
                match = re.search(r'\{.*\}', clean, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    try:
                        plan = json.loads(json_str)
                    except json.JSONDecodeError:
                        import ast
                        try:
                            plan = ast.literal_eval(json_str)
                        except Exception:
                            # 逐字段正则抽取兜底
                            plan = {
                                "is_buying":  bool(re.search(r'"is_buying"\s*:\s*true',  json_str, re.I)),
                                "is_posting": bool(re.search(r'"is_posting"\s*:\s*true', json_str, re.I)),
                                "post_content": m.group(1) if (m := re.search(r'"post_content"\s*:\s*"([^"]*)"', json_str)) else "",
                                "reason":      m.group(1) if (m := re.search(r'"reason"\s*:\s*"([^"]*)"',       json_str)) else "",
                            }
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

            print(f" [Plan] {agent.agent_id} | "
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

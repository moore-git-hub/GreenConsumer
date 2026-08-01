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
    # 值的校准原则：在 25 平静 tick 内，各人群的自然恢复比例应有明显差异，
    # 且恢复不应在观察窗口内完全完成（否则澄清效果被遗忘曲线覆盖）
    # Active_Greens: 25 ticks → ~70% 恢复（λ=0.05）
    # Convenient:    25 ticks → ~83% 恢复（λ=0.07）
    # Dormant:       25 ticks → ~91% 恢复（λ=0.10）
    # Non_Greens:    25 ticks → ~96% 恢复（λ=0.14）
    "Active_Greens":     0.05,
    "Convenient_Greens": 0.07,
    "Dormant_Greens":    0.10,
    "Non_Greens":        0.14,
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
# 理论依据：Dual Process Theory 框架中，不同消费者人群对环境相关信息的
# 态度强度（Attitude Strength）存在系统性差异。此系数属于 System 2 的
# 参数化假设，不是对 LLM 输出的截断——LLM 的 System 1 原始冲击值保持
# 完整传递，敏感度系数在 System 2 层面对其进行人群差异化缩放。
# 注意：若希望完全依赖 LLM Persona 产生差异，可将所有系数设为 1.0。
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

        # ── TASK_002 审计：澄清内容类型只从**实际观察到的消息**读取 ──
        # 禁止从 ExperimentConfig.content_factor 反推：那只代表"配置声称注入了什么"，
        # 不代表"这个 Agent 这一 Tick 实际观察到了什么"。
        clarification_content_type = ""
        if has_clarification:
            for _o in last_observations:
                if _o.get("source") == "Enterprise_Clarification" or _o.get("type") == "clarification":
                    clarification_content_type = str(_o.get("content_factor", "unknown"))
                    break

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
        trust_after_decay = previous_trust
        decay_rate_raw = 0.0    # 纯审计：本 Tick 实际生效的遗忘曲线回归比例

        if has_clarification:
            # 澄清当天：affective_change 直接叠加，quiet_ticks 重置为 1
            # quiet_ticks 重置确保后续遗忘曲线从澄清后的新起点（shock_anchor）重新计算，
            # 而不是沿用丑闻前积累的 quiet_ticks（否则遗忘曲线起点偏移，两组轨迹无差异）
            trust_after_decay = previous_trust
            quiet_ticks = 0  # 澄清当天视为事件日，遗忘曲线不执行
        elif quiet_ticks > 0:
            # 普通平静期：遗忘曲线生效，从 shock_anchor 向 baseline 回归
            trust_after_decay = self._forgetting_curve(shock_anchor, baseline_trust, quiet_ticks, lam)
            decay_rate_raw = 1.0 - math.exp(-lam * quiet_ticks)

        # ── 6. Step 2：叠加 System 1 的情绪冲击（带敏感度系数） ──────────
        raw_affective = float(s_data.get("trust_change_affective", 0.0))
        sensitivity = SENSITIVITY_MULTIPLIER.get(cluster_type, DEFAULT_SENSITIVITY)
        # 审计用未舍入原值；下游信任计算继续使用 round(...,3) 的 affective_change（行为不变）
        affective_change_raw = raw_affective * sensitivity
        affective_change = round(raw_affective * sensitivity, 3)

        trust_after_shock = trust_after_decay + affective_change
        final_trust = round(max(0.0, min(10.0, trust_after_shock)), 3)
        # 审计：未舍入的裁剪后信任值 + 是否触及 [0, 10] 边界
        trust_score_raw = max(0.0, min(10.0, trust_after_shock))
        trust_clipped_at_bound = (trust_after_shock < 0.0) or (trust_after_shock > 10.0)

        # ── 7. Step 3：更新 shock_anchor ─────────────────────────────────
        # 纯审计变量：记录实际走了哪个 anchor 更新分支及其参数（分支条件本身未改）
        anchor_update_branch = "none"
        clr_anchor_lift_ratio = ""
        clr_lift_raw = ""
        shock_anchor_after = shock_anchor
        if has_clarification:
            # 澄清当天：将 shock_anchor 向 baseline 方向移动固定比例
            # 使用固定的人群差异化参数（而非 affective_change 的倍数），
            # 避免澄清时机（即时 vs 延迟）通过情绪强度差异影响 anchor 提升量，
            # 确保时机效应只体现在「丑闻积累了多少quiet_ticks后才注入澄清」上
            # Active_Greens：最难被说服，anchor提升最少（20%）
            # Non_Greens：本来不关心，anchor几乎全恢复（60%）
            CLR_ANCHOR_LIFT_RATIO = {
                "Active_Greens":     0.20,
                "Convenient_Greens": 0.35,
                "Dormant_Greens":    0.45,
                "Non_Greens":        0.60,
            }
            lift_ratio = CLR_ANCHOR_LIFT_RATIO.get(cluster_type, 0.35)
            gap = baseline_trust - shock_anchor          # 丑闻造成的总损害
            clr_lift = gap * lift_ratio                  # 澄清修复其中的固定比例
            new_anchor = max(final_trust, shock_anchor + clr_lift)
            await state_plugin.set_state("shock_anchor", new_anchor)
            anchor_update_branch = "clarification"
            clr_anchor_lift_ratio = lift_ratio
            clr_lift_raw = clr_lift
            shock_anchor_after = new_anchor
        elif not is_quiet_day:
            # 普通全局事件当天（丑闻等）：锚定新的冲击点
            await state_plugin.set_state("shock_anchor", final_trust)
            anchor_update_branch = "global_event"
            shock_anchor_after = final_trust
        elif affective_change > 0 and final_trust > shock_anchor:
            # 社交正面反馈：信任超过 anchor 时也更新（防止遗忘曲线从过低起点恢复）
            await state_plugin.set_state("shock_anchor", final_trust)
            anchor_update_branch = "social_positive"
            shock_anchor_after = final_trust

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
        Product you are considering: '{product_name}'.

        [Your Current Mental State]
        How you feel right now: {thought_str}
        Days since last major news event: {quiet_ticks}
        (Internal reference only — your emotional state above reflects your current attitude)

        [Task — Make Your Decision as This Character]
        You are living your daily life as this consumer. Based on who you are, how you feel
        right now, and what you just read, naturally decide:

        1. **Would you buy this product today?**
           Consider your trust level, the price, and whether it aligns with your values.
           IMPORTANT: Most consumers do NOT buy every single day. People typically buy
           oat milk once every 1-2 weeks. Only decide to buy if you genuinely feel
           ready to make a purchase TODAY specifically.

        2. **Would you post something on social media today?**
           Only post if there is genuinely something NEW worth saying right now.
           Most people post about a brand controversy only once or twice, not every day.
           If you already expressed your opinion recently, you would probably stay quiet today.

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
            # ── TASK_002 审计字段：保存**未舍入**原始 float ──
            # 上面 8 个旧兼容字段的精度（round(…,3)）保持不变，供既有分析脚本使用。
            plan["previous_trust_raw"]         = previous_trust
            plan["baseline_trust_raw"]         = baseline_trust
            plan["trust_after_decay_raw"]      = trust_after_decay
            plan["affective_change_raw"]       = affective_change_raw
            plan["trust_score_raw"]            = trust_score_raw
            plan["shock_anchor_before_raw"]    = shock_anchor
            plan["shock_anchor_after_raw"]     = shock_anchor_after
            plan["decay_rate_raw"]             = decay_rate_raw
            plan["sensitivity_multiplier"]     = sensitivity
            plan["trust_clipped_at_bound"]     = trust_clipped_at_bound
            plan["anchor_update_branch"]       = anchor_update_branch
            plan["clr_anchor_lift_ratio"]      = clr_anchor_lift_ratio
            plan["clr_lift_raw"]               = clr_lift_raw
            plan["is_quiet_day"]                   = is_quiet_day
            # 阶段④：Plan 层**自己**识别到的澄清，也就是实际驱动了行为分支的那个布尔量。
            # 与记录器独立计算的阶段③ clarification_received 分列落盘，便于交叉核对。
            plan["clarification_detected_by_plan"] = has_clarification
            plan["clarification_content_type"]     = clarification_content_type
            plan["plan_fallback_used"]             = False

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
                "reason": "System parsing error, fell back to silent mode.",
                # ── TASK_002 审计字段（fallback 路径必须同样完整填充）──
                # 注意：上一行 "reason" 末尾的逗号是必需的，缺失会导致
                # 字符串隐式拼接 → 字典构造语法/语义错误。
                "previous_trust_raw":         previous_trust,
                "baseline_trust_raw":         baseline_trust,
                "trust_after_decay_raw":      trust_after_decay,
                "affective_change_raw":       affective_change_raw,
                "trust_score_raw":            trust_score_raw,
                "shock_anchor_before_raw":    shock_anchor,
                "shock_anchor_after_raw":     shock_anchor_after,
                "decay_rate_raw":             decay_rate_raw,
                "sensitivity_multiplier":     sensitivity,
                "trust_clipped_at_bound":     trust_clipped_at_bound,
                "anchor_update_branch":       anchor_update_branch,
                "clr_anchor_lift_ratio":      clr_anchor_lift_ratio,
                "clr_lift_raw":               clr_lift_raw,
                "is_quiet_day":                   is_quiet_day,
                "clarification_detected_by_plan": has_clarification,
                "clarification_content_type":     clarification_content_type,
                "plan_fallback_used":             True,
            }
            await state_plugin.set_state("plan_result", fallback_plan)

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass

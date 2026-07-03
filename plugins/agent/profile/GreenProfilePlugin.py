from typing import Any, Dict, Optional
from agentkernel_standalone.mas.agent.base.plugin_base import ProfilePlugin


class GreenProfilePlugin(ProfilePlugin):
    def __init__(self, profile_data: Optional[Dict[str, Any]] = None):
        # 1. 必须调用父类初始化，建立组件关联的基础
        super().__init__()
        self._profile_data = profile_data if profile_data is not None else {}

    async def init(self):
        """插件初始化逻辑"""
        pass

    # 3. 【参数修复】必须接受 current_tick 参数，否则运行时会报错
    async def execute(self, current_tick: int) -> None:
        """Profile 组件通常是静态的，不需要每 Tick 执行逻辑"""
        pass

    async def set_profile(self, key: str, value: Any):
        """支持动态修改 Profile"""
        self._profile_data[key] = value

    def get_prompt(self) -> str:
        """
        返回 Agent 的 Persona Prompt。

        优先使用 profiles.jsonl 中预生成的完整 `persona` 字段（由 generate_data.py 写入）。
        若该字段不存在（旧格式数据），则回退到从结构化字段动态拼接。
        """
        if not self._profile_data:
            return "You are a consumer agent."

        p = self._profile_data

        # 优先路径：直接使用预生成的完整 Persona Prompt
        if p.get("persona"):
            return p["persona"]

        # 回退路径：从结构化字段动态拼接（兼容旧格式数据，新数据不走此分支）
        # 注意：此路径使用了已废弃的人口统计字段和 if-then 规则文本，
        # 仅在 profiles.jsonl 缺少 persona 字段时生效（正常运行不应触发）
        demos = p.get('demographics', {})
        psych = p.get('psychology', {})
        cluster_type = psych.get('cluster_type', psych.get('environmental_involvement', 'Unknown'))
        big_five = psych.get('big_five', {})
        social_role = psych.get('social_role', 'Regular User')

        prompt = (
            f"You are {p.get('name', 'Unknown')}, a {demos.get('age', 'N/A')}-year-old consumer.\n"
            f"Income Level: {demos.get('income', 'N/A')}.\n"
            f"Personality (Big Five): {big_five}.\n"
            f"Consumer Segment: '{cluster_type}'.\n"
            f"Social Role: {social_role}.\n"
        )

        # 根据消费者类型注入行为指导规则
        guidelines = {
            'Active_Greens': (
                "You actively seek information about greener products and are willing to choose them "
                "even when doing so is less convenient."
            ),
            'Convenient_Greens': (
                "You are interested in greener choices, but price and convenience usually take priority."
            ),
            'Dormant_Greens': (
                "You do not actively seek green information, but you may be open to persuasion when relevant information is made salient."
            ),
            'Non_Greens': (
                "Environmental considerations are secondary to price, convenience, and functional value in your purchasing decisions."
            ),
            # 旧字段兼容
            'Deep Green': (
                "You are extremely sensitive to greenwashing. If you detect hypocrisy, you will lose trust immediately."
            ),
        }
        guideline = guidelines.get(cluster_type, "You care about price and convenience more than strict environmental claims.")
        prompt += f"Guideline: {guideline}\n"

        return prompt

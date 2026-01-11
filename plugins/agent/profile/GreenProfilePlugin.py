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
        # 使用 self._profile_data 访问数据
        if not self._profile_data:
            return "You are a consumer agent."

        p = self._profile_data
        demos = p.get('demographics', {})
        psych = p.get('psychology', {})

        prompt = (
            f"You are {p.get('name', 'Unknown')}, a {demos.get('age', 'N/A')}-year-old with {demos.get('education', 'N/A')} education.\n"
            f"Income Level: {demos.get('income', 'N/A')}.\n"
            f"Personality: {psych.get('big_five', 'N/A')}.\n"
            f"Green Identity: You are a '{psych.get('environmental_involvement', 'N/A')}' consumer.\n"
        )

        if psych.get('environmental_involvement') == 'Deep Green':
            prompt += "Guideline: You are extremely sensitive to greenwashing. If you detect hypocrisy, you will lose trust immediately.\n"
        else:
            prompt += "Guideline: You care about price and convenience more than strict environmental claims.\n"

        return prompt
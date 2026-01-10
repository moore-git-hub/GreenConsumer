import json
import textwrap
import asyncio
from typing import List, Dict, Any
import json_repair
from agentkernel_standalone.mas.agent.base.plugin_base import PlanPlugin
from agentkernel_standalone.mas.agent.components import *
from agentkernel_standalone.toolkit.logger import get_logger

logger = get_logger(__name__)


class EasyPlanPlugin(PlanPlugin):
    """
    一个简单的计划插件，用于生成下一时间步的计划。
    1. 选择是否移动到另一个位置或留在当前位置
    2. 选择是否与另一个智能体聊天
    """

    def __init__(self):
        super().__init__()
        self.plan = []  # 存储计划的列表
        logger.info("EasyPlanPlugin initialized")

    async def init(self):
        # 初始化插件，获取必要的组件和资源
        self.agent_id = self._component.agent.agent_id  # 获取当前智能体ID
        self.model = self._component.agent.model  # 获取AI模型实例
        self.perceive_comp: PerceiveComponent = self._component.agent.get_component("perceive")  # 获取感知组件
        self.perceive_plug = self.perceive_comp._plugin  # 获取感知组件的插件实例

    async def execute(self, current_tick: int) -> Dict[str, Any]:
        # 执行计划生成逻辑
        self.plan.clear()  # 清空之前的计划
        could_see_agents = self.perceive_plug.surrounding_agents  # 获取周围可看见的智能体列表
        current_position = self.perceive_plug.current_position  # 获取当前智能体位置
        chat_history = self.perceive_plug.last_tick_messages  # 获取上一个时间步的消息历史

        # 构建提示词，用于指导AI模型生成下一步行动
        prompt = f'''
                You are a goal planner, help me plan what to do next. Currently, you are on a 300x300 2D map. You can choose to move to any position on the map, or talk to someone nearby.
                Agents you can see around you: {json.dumps(could_see_agents)}
                Your current position: {json.dumps(current_position)}
                Chat history from previous conversations: {json.dumps(chat_history)}
                Response examples:
                    {{ "action":"move", "target":[50,60]}}
                    or
                    {{"action":"chat", "target": "agent_id", "content": "Hello"}}
                Please ensure the response is in JSON format.
                Please choose your next action:
                '''

        # 调用AI模型生成计划响应
        model_response = await self.model.chat(prompt)
        print(model_response)
        logger.info(f"Agent {self.agent_id} has planned its next step: {model_response}.")
        # 解析并修复JSON响应，将其添加到计划列表中
        self.plan.append(json_repair.loads(model_response))

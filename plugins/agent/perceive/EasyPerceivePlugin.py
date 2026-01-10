from typing import Dict, Any, Optional, List, Tuple

import heapq
import itertools
import math

from agentkernel_standalone.types.schemas.message import Message
from agentkernel_standalone.mas.agent.base.plugin_base import PerceivePlugin
from agentkernel_standalone.mas.environment.components import *
from agentkernel_standalone.toolkit.logger import get_logger

logger = get_logger(__name__)


class EasyPerceivePlugin(PerceivePlugin):
    def __init__(self):
        """
        智能体的简易感知插件初始化
        功能包括：
        1. 获取周围信息，如其他智能体、对象等
        2. 接收系统消息
        """
        super().__init__()
        self.global_tick = 0  # 全局时钟计数器
        self.received_messages = []  # 存储接收到的消息列表
        self.last_tick_messages = []  # 存储上一时钟周期的消息列表
        self.surrounding_agents = []  # 存储周围智能体列表
        logger.info(f"EasyPerceivePlugin initialized.")

    async def init(self):
        # 初始化插件，获取控制器、智能体ID和规划组件
        self.controller = self._component.agent.controller  # 获取控制器引用
        self.agent_id = self._component.agent.agent_id  # 获取当前智能体ID
        self.plan_comp = self._component.agent.get_component("plan")  # 获取规划组件

    async def execute(self, current_tick: int):
        # 执行感知逻辑，获取当前智能体位置信息
        agent_info = await self.controller.run_environment("space", "get_agent", self.agent_id)
        self.current_position = agent_info["position"]  # 更新当前智能体位置
        self.last_tick_messages = self.received_messages  # 将当前消息列表转移到上一时钟周期消息列表
        self.received_messages = []  # 清空当前接收消息列表
        logger.info(
            f"Agent {self.agent_id} is at position {self.current_position}, at last tick, there are {len(self.last_tick_messages)} messages."
        )
        # 获取当前位置

        # 设置可视距离，初始化周围智能体列表
        could_see_distance = 10  # 感知距离，单位为10
        self.surrounding_agents = []  # 清空周围智能体列表
        self.all_agents = []  # 初始化所有智能体列表

        # 从环境中获取所有智能体信息
        self.all_agents = await self.controller.run_environment("space", "get_all_agents")
        for agent in self.all_agents:
            if agent["id"] != self.agent_id:  # 排除自身
                # 计算当前智能体与环境中其他智能体的距离
                if (
                    math.sqrt(
                        (agent["position"][0] - self.current_position[0]) ** 2 + (agent["position"][1] - self.current_position[1]) ** 2
                    )
                    <= could_see_distance  # 如果距离小于等于感知距离
                ):
                    self.surrounding_agents.append(agent)  # 将该智能体添加到周围智能体列表

        logger.info(f"Agent {self.agent_id} looked around, and found {len(self.surrounding_agents)} agents.")

    async def add_message(self, message: Message):
        """
        被系统调度函数调用，将消息添加到received_messages列表中
        """

        logger.info(f"Agent {self.agent_id} received message from {message.from_id}: {message.content}")
        copyed_message = {"from_id": message.from_id, "kind": message.kind, "content": message.content}
        self.received_messages.append(copyed_message)
        logger.info(f"Agent {self.agent_id} stored message: {copyed_message}")

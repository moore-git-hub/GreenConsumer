from typing import Dict, Any, Optional, List
import json
import textwrap
from enum import Enum

from agentkernel_standalone.mas.agent.base.plugin_base import ReflectPlugin
from agentkernel_standalone.toolkit.logger import get_logger
from agentkernel_standalone.toolkit.utils import clean_json_response

logger = get_logger(__name__)


class EasyReflectPlugin(ReflectPlugin):
    def __init__(self):
        """
        初始化简单反思插件
        """
        super().__init__()
        self.agent_id = None  # 存储智能体ID的属性

    async def init(self):
        """
        异步初始化方法，获取并设置当前智能体的ID
        """
        self.agent_id = self._component.agent.agent_id

    async def execute(self, current_tick: int) -> Dict[str, Any]:
        """
        执行反思逻辑
        :param current_tick: 当前时间步
        :return: 包含反思结果的字典
        """
        logger.info(f'Agent {self.agent_id} reflect his whole day, and get nothing.')

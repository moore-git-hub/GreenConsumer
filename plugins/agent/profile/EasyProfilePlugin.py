from typing import Dict, Any, Optional, Callable
from agentkernel_standalone.mas.agent.base.plugin_base import ProfilePlugin
from agentkernel_standalone.toolkit.logger import get_logger

logger = get_logger(__name__)


class EasyProfilePlugin(ProfilePlugin):
    def __init__(self, profile_data: Optional[Dict[str, Any]] = None):
        """
        初始化简单档案插件
        :param profile_data: 可选的档案数据字典，如果未提供则创建空字典
        """
        self._profile_data = profile_data if profile_data is not None else {}

    async def init(self):
        """
        异步初始化方法，当前为空实现
        """
        pass

    async def execute(self):
        """
        执行档案插件的主要逻辑，当前为空实现
        """
        pass

    async def set_profile(self, key: str, value: Any):
        """
        设置档案中的键值对，当前为空实现
        :param key: 档案项的键名
        :param value: 档案项的值
        """
        pass

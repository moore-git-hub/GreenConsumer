from typing import Any, Dict
from agentkernel_standalone.mas.agent.components.state import StatePlugin
from plugins.agent.reflect.MemoryManager import MemoryManager


class GreenStatePlugin(StatePlugin):
    def __init__(self, *args, **kwargs):
        """强制在对象实例化时挂载记忆管理器"""
        super().__init__(*args, **kwargs)
        self.memory_manager = MemoryManager()

    async def init(self):
        # 兼容 Agent-Kernel 异步生命周期，做二次防错
        if not hasattr(self, 'memory_manager'):
            self.memory_manager = MemoryManager()

    async def execute(self, current_tick: int) -> None:
        pass

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass

    async def set_state(self, key: str, value: Any) -> None:
        self._state_data[key] = value

    def get_state_sync(self, key: str) -> Any:
        return self._state_data.get(key)

    def add_to_memory(self, tick: int, content: str, importance: float = 5.0):
        # 三次防错：懒加载机制
        if not hasattr(self, 'memory_manager'):
            self.memory_manager = MemoryManager()
        self.memory_manager.add_memory(tick, content, importance)

    def retrieve_memory(self, current_tick: int, query: str, top_k: int = 3) -> list:
        # 三次防错：懒加载机制
        if not hasattr(self, 'memory_manager'):
            self.memory_manager = MemoryManager()
        return self.memory_manager.retrieve(current_tick, query, top_k)
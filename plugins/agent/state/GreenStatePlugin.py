from typing import Any, Dict
from agentkernel_standalone.mas.agent.components.state import StatePlugin


class GreenStatePlugin(StatePlugin):
    async def init(self):
        pass

    async def execute(self, current_tick: int) -> None:
        pass

    async def save_to_db(self):
        pass

    async def load_from_db(self):
        pass

    # === 核心修复 ===
    # 1. 必须是 async，且更新基类的 self._state_data
    async def set_state(self, key: str, value: Any) -> None:
        self._state_data[key] = value

    # 2. 增加同步获取方法 (方便其他插件调用)
    def get_state_sync(self, key: str) -> Any:
        return self._state_data.get(key)
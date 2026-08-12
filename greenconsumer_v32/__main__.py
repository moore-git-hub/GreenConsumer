"""允许使用 ``python -m greenconsumer_v32 ...`` 启动统一工作流。"""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())

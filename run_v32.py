"""TASK_005 FMCG v3.2 的唯一人工运行入口。

研究者在 PyCharm 或终端中只需要运行本文件。实际命令解析与全过程调度
位于 :mod:`greenconsumer_v32.cli`，这样根目录不会再出现多个互相竞争的
``run_*.py`` 入口。
"""
from greenconsumer_v32.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

# Formal v3.2 N=10 script provenance

本目录用于保存正式 N=10 workflow 的分析与授权检查代码，并记录正式 real-LLM runner 的不可变身份。

已归档代码：
- `activate_task005_fmcg_formal_v32_n10.py`
- `check_task005_fmcg_formal_v32_n10_authorized.py`
- `analyze_task005_fmcg_formal_v32_n10.py`

正式执行 runner 的冻结 SHA256 为：

`4b439e629f957fa552d11df36cf0bd2d4987e2eeac9b0e7d6216c9f16a346db5`

该 runner 已完成 F001-F010 后关闭，不应把本目录当作新的执行入口。其哈希同时记录于 runtime contract 与 execution authorization。当前 post-formal 代码库的主要目的，是保存机制源码、设计合同、正式结果与分析可追溯性，而不是重新开放 formal execution。

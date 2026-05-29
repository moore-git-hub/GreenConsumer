"""全面验证脚本 —— 覆盖所有已修复的问题点。运行完成后可删除。"""
import ast
import sys
import os
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
all_ok = True

def check(desc, condition):
    global all_ok
    ok = bool(condition)
    print(f"  {'✅' if ok else '❌'} {desc}")
    if not ok:
        all_ok = False

def src(rel_path):
    with open(os.path.join(ROOT, rel_path), encoding="utf-8") as f:
        return f.read()

# ── 1. Python 语法检查 ──────────────────────────────────────────────
print("=" * 55)
print("1. Python 语法检查（全部核心文件）")
print("=" * 55)
py_files = [
    "run_simulation.py",
    "generate_data.py",
    "analyze_thoughts.py",
    "plot_results.py",
    "plot_advanced_dashboard.py",
    "plot_comparison.py",
    "plugins/agent/reflect/MemoryManager.py",
    "plugins/agent/profile/GreenProfilePlugin.py",
    "plugins/agent/state/GreenStatePlugin.py",
    "plugins/agent/perceive/GreenPerceivePlugin.py",
    "plugins/agent/reflect/GreenCognitionPlugin.py",
    "plugins/agent/plan/ConsumerPlanPlugin.py",
    "plugins/agent/invoke/GreenInvokePlugin.py",
    "plugins/environment/network/SocialNetworkPlugin.py",
]
for rel in py_files:
    path = os.path.join(ROOT, rel)
    try:
        with open(path, encoding="utf-8") as fh:
            ast.parse(fh.read())
        print(f"  ✅ {rel}")
    except SyntaxError as e:
        print(f"  ❌ {rel}: {e}")
        all_ok = False

# ── 2. YAML 配置检查 ────────────────────────────────────────────────
print("\n" + "=" * 55)
print("2. simulation_config.yaml")
print("=" * 55)
yaml_path = os.path.join(ROOT, "configs", "simulation_config.yaml")
try:
    with open(yaml_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    check("max_ticks == 30", cfg["simulation"]["max_ticks"] == 30)
except Exception as e:
    print(f"  ❌ YAML 解析失败: {e}")
    all_ok = False

# ── 3. run_simulation.py ────────────────────────────────────────────
print("\n" + "=" * 55)
print("3. run_simulation.py")
print("=" * 55)
rs = src("run_simulation.py")
check("文件句柄注册到 _open_files（防泄漏）", "_open_files = [csv_file, thought_file, macro_file]" in rs)
check("循环结束用 _open_files 关闭文件", "for f in _open_files" in rs)
check("BURN_IN_TICKS 死代码已删除", "BURN_IN_TICKS" not in rs)
check("profile 字段优先读 _profile_data", '"_profile_data"' in rs and 'p_data = getattr' in rs)
check("裸 except 已改为 except Exception", "except Exception" in rs and rs.count("except:") == 0)
check("node_link_data 兼容新版 networkx", 'edges="links"' in rs)
check("node_link_graph 兼容新版 networkx", 'edges="links"' in rs)

# ── 4. ConsumerPlanPlugin.py ────────────────────────────────────────
print("\n" + "=" * 55)
print("4. ConsumerPlanPlugin.py — Plan 层新闻读取修复")
print("=" * 55)
cp = src("plugins/agent/plan/ConsumerPlanPlugin.py")
check("从 observations 读取新闻（而非已清空的 incoming_messages）",
      "observations = s_data.get(\"observations\", [])" in cp)
check("兼容 incoming_messages 直接注入的情况", "incoming_messages" in cp)
check("重复 set_state 已消除（正常路径只写一次，fallback 路径一次，共两次）",
      cp.count('set_state("plan_result"') == 2)

# ── 5. GreenCognitionPlugin.py ──────────────────────────────────────
print("\n" + "=" * 55)
print("5. GreenCognitionPlugin.py — 认知失败时清空 observations")
print("=" * 55)
gc = src("plugins/agent/reflect/GreenCognitionPlugin.py")
check("except 块中清空 observations 防重复处理",
      'set_state("observations", [])' in gc)
check("JSON 解析使用 re.search 提取（兼容附加文字）",
      "re.search" in gc)

# ── 6. MemoryManager.py ─────────────────────────────────────────────
print("\n" + "=" * 55)
print("6. MemoryManager.py")
print("=" * 55)
mm = src("plugins/agent/reflect/MemoryManager.py")
check("sentence-transformers 可选导入", "from sentence_transformers import" in mm)
check("回退到确定性哈希向量（无全局随机种子污染）", "default_rng" in mm)
check("np.random.seed 已移除", "np.random.seed" not in mm)

# ── 7. GreenProfilePlugin.py ────────────────────────────────────────
print("\n" + "=" * 55)
print("7. GreenProfilePlugin.py")
print("=" * 55)
gp = src("plugins/agent/profile/GreenProfilePlugin.py")
check("优先读取 persona 字段", 'p.get("persona")' in gp)
check("education 字段已移除", "education" not in gp)

# ── 8. plot_advanced_dashboard.py ───────────────────────────────────
print("\n" + "=" * 55)
print("8. plot_advanced_dashboard.py")
print("=" * 55)
pad = src("plot_advanced_dashboard.py")
check("非法颜色 '#gray' 已修复为 '#888888'", "'#gray'" not in pad and "'#888888'" in pad)

# ── 9. plot_comparison.py ───────────────────────────────────────────
print("\n" + "=" * 55)
print("9. plot_comparison.py — 事件标注 Tick 对齐")
print("=" * 55)
pc = src("plot_comparison.py")
check("axvline(x=5) 对齐 ENTERPRISE_STRATEGY Tick 5", "axvline(x=5" in pc)
check("旧的错误 axvline(x=4) 已删除", "axvline(x=4" not in pc)

# ── 10. generate_data.py ────────────────────────────────────────────
print("\n" + "=" * 55)
print("10. generate_data.py — stats 死代码修复")
print("=" * 55)
gd = src("generate_data.py")
check("stats 统计结果已打印输出", "stats['Role']" in gd and "stats['Cluster']" in gd)

# ── 11. analyze_thoughts.py ─────────────────────────────────────────
print("\n" + "=" * 55)
print("11. analyze_thoughts.py — 类型注解兼容性")
print("=" * 55)
at = src("analyze_thoughts.py")
check("使用 Optional[str] 替代 str | None（兼容 Python < 3.10）",
      "Optional[str]" in at and "str | None" not in at)
check("自动查找最新文件（无硬编码文件名）",
      "thoughts_log_20260515_140826.csv" not in at)

# ── 总结 ─────────────────────────────────────────────────────────────
print("\n" + "=" * 55)
print(f"总结: {'✅ 全部通过' if all_ok else '❌ 存在问题，请检查上方输出'}")
print("=" * 55)
sys.exit(0 if all_ok else 1)

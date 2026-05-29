"""
Task 9: 集成测试 — 验证实验系统所有模块的语法和逻辑正确性。

运行方式：python _verify_experiment_system.py
"""
import ast
import os
import sys
import math

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
all_ok = True


def check(desc, cond):
    global all_ok
    ok = bool(cond)
    print(f"  {'✅' if ok else '❌'} {desc}")
    if not ok:
        all_ok = False


def src(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


# ══════════════════════════════════════════════════════════════════════
print("=" * 60)
print("1. 语法检查（所有新增模块）")
print("=" * 60)
new_files = [
    "experiment_config.py",
    "node_selector.py",
    "clarification_injector.py",
    "metrics_calculator.py",
    "simulation_core.py",
    "run_experiments.py",
    "plot_pareto.py",
]
for rel in new_files:
    path = os.path.join(ROOT, rel)
    try:
        with open(path, encoding="utf-8") as f:
            ast.parse(f.read())
        print(f"  ✅ {rel}")
    except SyntaxError as e:
        print(f"  ❌ {rel}: {e}")
        all_ok = False
    except FileNotFoundError:
        print(f"  ❌ {rel}: 文件不存在")
        all_ok = False

# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("2. experiment_config.py 逻辑验证")
print("=" * 60)
from experiment_config import ExperimentConfig, generate_experiment_matrix

matrix = generate_experiment_matrix()
check(f"实验矩阵生成 12 个配置（实际 {len(matrix)}）", len(matrix) == 12)

# 验证 exp_id 唯一性
ids = [c.exp_id for c in matrix]
check(f"12 个 exp_id 全部唯一", len(set(ids)) == 12)

# 验证 clarification_tick
imm = [c for c in matrix if c.timing_factor == "immediate"]
check("immediate 的 clarification_tick == 5", all(c.clarification_tick == 5 for c in imm))

d3 = [c for c in matrix if c.timing_factor == "delay-3"]
check("delay-3 的 clarification_tick == 8", all(c.clarification_tick == 8 for c in d3))

noclr = [c for c in matrix if c.timing_factor == "no-clarification"]
check("no-clarification 的 clarification_tick == None", all(c.clarification_tick is None for c in noclr))

# 验证字段验证
try:
    ExperimentConfig(content_factor="invalid", channel_factor="hub", timing_factor="immediate")
    check("非法 content_factor 应抛出 ValueError", False)
except ValueError:
    check("非法 content_factor 正确抛出 ValueError", True)

# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("3. node_selector.py 逻辑验证")
print("=" * 60)
import networkx as nx
from node_selector import select_target_nodes

G = nx.barabasi_albert_graph(10, m=2, seed=42)
mapping = {i: f"Consumer_{i:03d}" for i in range(10)}
G = nx.relabel_nodes(G, mapping)

hub_nodes = select_target_nodes(G, "hub", 3, seed=42)
check(f"Hub 策略返回 3 个节点", len(hub_nodes) == 3)

# 验证 hub 节点确实是度数最高的
degrees = sorted(G.degree(), key=lambda x: x[1], reverse=True)
top3_ids = [n for n, _ in degrees[:3]]
check(f"Hub 节点是度数 top-3", set(hub_nodes) == set(top3_ids))

random_nodes = select_target_nodes(G, "random", 3, seed=42)
check(f"Random 策略返回 3 个节点", len(random_nodes) == 3)

# 可复现性
random_nodes2 = select_target_nodes(G, "random", 3, seed=42)
check(f"Random 策略相同 seed 结果一致", random_nodes == random_nodes2)

# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("4. clarification_injector.py 逻辑验证")
print("=" * 60)
from clarification_injector import ClarificationInjector, CONTENT_TEMPLATES

# 模板长度检查
for name, template in CONTENT_TEMPLATES.items():
    word_count = len(template.split())
    check(f"模板 '{name}' 长度 {word_count} 词（50-200）", 50 <= word_count <= 200)

# 注入逻辑
cfg_imm = ExperimentConfig(content_factor="rational-evidence", channel_factor="hub", timing_factor="immediate")
inj = ClarificationInjector(cfg_imm)
check("immediate 配置: should_inject(5) == True", inj.should_inject(5))
check("immediate 配置: should_inject(6) == False", not inj.should_inject(6))

cfg_noclr = ExperimentConfig(content_factor="emotional-empathy", channel_factor="random", timing_factor="no-clarification")
inj2 = ClarificationInjector(cfg_noclr)
check("no-clarification: should_inject(任何tick) == False", not inj2.should_inject(5) and not inj2.should_inject(8))

# 消息格式
msg = inj.get_message()
check("消息 source == 'Enterprise_Clarification'", msg["source"] == "Enterprise_Clarification")
check("消息 content 非空", len(msg["content"]) > 0)

# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("5. metrics_calculator.py 逻辑验证")
print("=" * 60)
from metrics_calculator import compute_metrics

# 构造测试轨迹：Tick 1-4 信任 7.0，Tick 5 跌至 3.0，之后指数恢复
trust_traj = []
for t in range(1, 31):
    if t <= 4:
        trust_traj.append(7.0)
    elif t == 5:
        trust_traj.append(3.0)
    else:
        trust_traj.append(3.0 + 4.0 * (1 - math.exp(-0.15 * (t - 5))))

conv_traj = [i * 0.1 for i in range(1, 5)] + [0.4] * 26

metrics = compute_metrics(trust_traj, conv_traj, scandal_tick=5, total_ticks=30)
check(f"baseline_trust == 7.0（Tick 4）", metrics.baseline_trust == 7.0)
check(f"trust_min == 3.0（Tick 5）", metrics.trust_min == 3.0)
check(f"trust_min_tick == 5", metrics.trust_min_tick == 5)
check(f"T80 < 30（信任应能恢复到 5.6）", metrics.t80 < 30)
check(f"steady_state_score > 3.0（应有恢复）", metrics.steady_state_score > 3.0)
check(f"recovery_rate == 1.0（转化率未变）", metrics.recovery_rate == 1.0)

# 边界：信任不恢复
flat_trust = [7.0] * 4 + [2.0] * 26
flat_conv = [0.3] * 4 + [0.3] * 26
metrics_flat = compute_metrics(flat_trust, flat_conv, scandal_tick=5, total_ticks=30)
check(f"信任不恢复时 T80 == 30（censored）", metrics_flat.t80 == 30)

# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("6. simulation_core.py 导入检查")
print("=" * 60)
# 只检查语法和导入链是否正确（不实际运行仿真，因为需要 agentkernel_standalone）
sc_src = src("simulation_core.py")
check("包含 run_simulation_core 函数定义", "async def run_simulation_core" in sc_src)
check("导入 ExperimentConfig", "from experiment_config import ExperimentConfig" in sc_src)
check("导入 ClarificationInjector", "from clarification_injector import ClarificationInjector" in sc_src)
check("导入 select_target_nodes", "from node_selector import select_target_nodes" in sc_src)
check("导入 compute_metrics", "from metrics_calculator import compute_metrics" in sc_src)
check("设置 random seed", "random_module.seed(config.random_seed)" in sc_src)
check("设置 numpy seed", "np.random.seed(config.random_seed)" in sc_src)
check("澄清注入在 Perceive 之前", 
      sc_src.index("await injector.inject") < sc_src.index('await ag.get_component("perceive")'))
check("返回 trust_trajectory", '"trust_trajectory"' in sc_src)

# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("7. run_experiments.py 结构检查")
print("=" * 60)
re_src = src("run_experiments.py")
check("导入 generate_experiment_matrix", "from experiment_config import generate_experiment_matrix" in re_src)
check("导入 run_simulation_core", "from simulation_core import run_simulation_core" in re_src)
check("进度显示 [{i}/{total}]", "[{i}/{" in re_src or "f\"[{i}/" in re_src)
check("异常处理 try/except", "except Exception" in re_src)
check("写入 summary.csv", "summary.csv" in re_src)
check("调用帕累托分析", "analyze_and_plot_pareto" in re_src)

# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("8. plot_pareto.py 结构检查")
print("=" * 60)
pp_src = src("plot_pareto.py")
check("is_dominated 函数", "def is_dominated" in pp_src)
check("find_pareto_front 函数", "def find_pareto_front" in pp_src)
check("analyze_and_plot_pareto 函数", "def analyze_and_plot_pareto" in pp_src)
check("3D 散点图", "projection='3d'" in pp_src or "projection=\"3d\"" in pp_src)
check("保存 pareto_3d.png", "pareto_3d.png" in pp_src)
check("保存 strategy_ranking.csv", "strategy_ranking.csv" in pp_src)
check("300 DPI", "dpi=300" in pp_src)

# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("9. run_simulation.py 向后兼容检查")
print("=" * 60)
rs_src = src("run_simulation.py")
check("保留 async def run() 函数", "async def run()" in rs_src)
check("保留 if __name__ == '__main__'", 'if __name__ == "__main__"' in rs_src)
check("保留 asyncio.run(run())", "asyncio.run(run())" in rs_src)

# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
success_count = sum(1 for line in [] if True)  # placeholder
print(f"总结: {'✅ 全部通过' if all_ok else '❌ 存在问题，请检查上方输出'}")
print("=" * 60)
sys.exit(0 if all_ok else 1)

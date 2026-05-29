"""验证信任更新机制重构。"""
import ast, os, sys, math

ROOT = os.path.dirname(os.path.abspath(__file__))
all_ok = True

def check(desc, cond):
    global all_ok
    ok = bool(cond)
    print(f"  {'OK' if ok else 'FAIL'} {desc}")
    if not ok: all_ok = False

def src(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()

print("=" * 60)
print("1. 语法检查")
print("=" * 60)
for rel in [
    "plugins/agent/reflect/GreenCognitionPlugin.py",
    "plugins/agent/plan/ConsumerPlanPlugin.py",
    "run_simulation.py",
    "analyze_thoughts.py",
]:
    try:
        ast.parse(src(rel))
        print(f"  OK  {rel}")
    except SyntaxError as e:
        print(f"  FAIL {rel}: {e}")
        all_ok = False

print("\n" + "=" * 60)
print("2. GreenCognitionPlugin — System 1 职责检查")
print("=" * 60)
gc = src("plugins/agent/reflect/GreenCognitionPlugin.py")
check("输出 trust_change_affective（不修改 trust_score）",
      'set_state("trust_change_affective"' in gc)
check("不再直接修改 trust_score",
      'set_state("trust_score"' not in gc)
check("多条 observations 聚合（全局新闻 + 社交帖子）",
      'global_news' in gc and 'social_posts' in gc)
check("失败时情绪冲击归零（不崩溃）",
      'set_state("trust_change_affective", 0.0)' in gc)

print("\n" + "=" * 60)
print("3. ConsumerPlanPlugin — System 2 职责检查")
print("=" * 60)
cp = src("plugins/agent/plan/ConsumerPlanPlugin.py")
check("包含 _forgetting_curve 静态方法",
      'def _forgetting_curve' in cp)
check("遗忘曲线使用 math.exp",
      'math.exp' in cp)
check("差异化 λ 参数（DECAY_LAMBDA 字典）",
      'DECAY_LAMBDA' in cp and 'Active_Greens' in cp)
check("Step1: 遗忘曲线计算 trust_after_decay",
      'trust_after_decay' in cp)
check("Step2: 叠加情绪冲击 affective_change",
      'trust_change_affective' in cp and 'affective_change' in cp)
check("Step3: LLM 只输出 is_buying / is_posting（不输出 current_trust）",
      '"current_trust"' not in cp.split('Output JSON')[1].split('}}')[0]
      if 'Output JSON' in cp else True)
check("plan_result 包含 trust_after_decay 和 affective_change",
      'plan["trust_after_decay"]' in cp and 'plan["affective_change"]' in cp)
check("trust_score 由公式写入（在 LLM 调用之前）",
      cp.index('set_state("trust_score"') < cp.index('await model.chat'))

print("\n" + "=" * 60)
print("4. 遗忘曲线数学验证")
print("=" * 60)

def forgetting_curve(prev, base, quiet, lam):
    if quiet <= 0: return prev
    decay_rate = 1.0 - math.exp(-lam * quiet)
    return prev + decay_rate * (base - prev)

# Active_Greens λ=0.05：恢复慢
trust_ag = 3.0  # 丑闻后信任跌至 3.0
base_ag  = 7.0  # 基线 7.0
after_5  = forgetting_curve(trust_ag, base_ag, 5,  0.05)
after_20 = forgetting_curve(trust_ag, base_ag, 20, 0.05)
check(f"Active_Greens λ=0.05: 5天后 {after_5:.2f}（应在3~7之间）",
      3.0 < after_5 < 7.0)
check(f"Active_Greens λ=0.05: 20天后 {after_20:.2f}（应比5天更接近基线）",
      after_20 > after_5)

# Non_Greens λ=0.25：恢复快
after_5_ng  = forgetting_curve(trust_ag, base_ag, 5,  0.25)
after_20_ng = forgetting_curve(trust_ag, base_ag, 20, 0.25)
check(f"Non_Greens λ=0.25: 5天后 {after_5_ng:.2f}（应比 Active_Greens 更接近基线）",
      after_5_ng > after_5)
check(f"Non_Greens λ=0.25: 20天后 {after_20_ng:.2f}（应接近基线 7.0）",
      after_20_ng > 6.0)

# 边界：quiet_ticks=0 时不变
check("quiet_ticks=0 时信任不变",
      forgetting_curve(3.0, 7.0, 0, 0.15) == 3.0)

print("\n" + "=" * 60)
print("5. run_simulation.py CSV 表头检查")
print("=" * 60)
rs = src("run_simulation.py")
check("simulation_log 新增 TrustAfterDecay 列",
      '"TrustAfterDecay"' in rs)
check("simulation_log 新增 AffectiveChange 列",
      '"AffectiveChange"' in rs)
check("simulation_log 新增 DecayLambda 列",
      '"DecayLambda"' in rs)
check("thoughts_log 使用 AffectiveChange 替代 TrustChange",
      '"AffectiveChange"' in rs and rs.count('"TrustChange"') == 0)

print("\n" + "=" * 60)
print(f"总结: {'全部通过' if all_ok else '存在问题'}")
print("=" * 60)
sys.exit(0 if all_ok else 1)

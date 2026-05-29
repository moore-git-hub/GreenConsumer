"""验证发帖数为0的修复。"""
import ast, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
all_ok = True

def check(desc, cond):
    global all_ok
    ok = bool(cond)
    print(f"  {'OK' if ok else 'FAIL'} {desc}")
    if not ok:
        all_ok = False

def src(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()

print("=" * 55)
print("语法检查")
print("=" * 55)
for rel in ["plugins/agent/plan/ConsumerPlanPlugin.py", "run_simulation.py"]:
    try:
        ast.parse(src(rel))
        print(f"  OK  {rel}")
    except SyntaxError as e:
        print(f"  FAIL {rel}: {e}")
        all_ok = False

print("\n" + "=" * 55)
print("发帖数为0 根因修复验证")
print("=" * 55)

cp = src("plugins/agent/plan/ConsumerPlanPlugin.py")
check("Plan 层从 current_news 读取新闻", 'current_news' in cp)
check("is_quiet_day 用 current_news 空值判断", 'is_quiet_day = not current_news.strip()' in cp)
check("旧的 Normal peaceful day 字符串匹配已删除", '"Normal peaceful day" in news_text' not in cp)
check("JSON 正则使用 re.DOTALL", 're.DOTALL' in cp)

rs = src("run_simulation.py")
check("主循环事件注入时写 current_news", 'set_state("current_news", event_text)' in rs)
check("无事件 Tick 重置 current_news 为空", 'set_state("current_news", "")' in rs)

print("\n" + "=" * 55)
print("总结:", "全部通过" if all_ok else "存在问题")
print("=" * 55)
sys.exit(0 if all_ok else 1)

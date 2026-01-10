import os
import time
import shutil
import glob
from generate_data import generate_profiles
from run_simulation import run as run_simulation
import asyncio


async def run_batch():
    # 实验配置
    experiments = [
        # ("deep_only", "Exp1_DeepGreen"),
        # ("light_only", "Exp2_LightGreen"),
        ("mixed", "Exp3_Mixed")
    ]

    results_dir = os.path.join(os.path.dirname(__file__), "results")
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)

    for mode, label in experiments:
        print(f"\n\n========================================")
        print(f"🧪 开始实验: {label} (Mode: {mode})")
        print(f"========================================")

        # 1. 生成特定分布的数据
        # 注意：run_simulation 读取的是默认路径 data/agents/profiles.jsonl
        generate_profiles(mode=mode, filename="profiles.jsonl")

        # 2. 运行仿真
        # 由于 run_simulation 是 async 的，我们需要在这里 await 它
        # 注意：需要确保 run_simulation.py 里的 run() 函数没有 sys.exit()
        await run_simulation()

        # 3. 找到刚刚生成的 CSV 并重命名
        # run_simulation 会生成类似 simulation_log_2023xxxx.csv
        list_of_files = glob.glob(os.path.join(results_dir, 'simulation_log_*.csv'))
        if list_of_files:
            latest_file = max(list_of_files, key=os.path.getctime)
            new_name = os.path.join(results_dir, f"{label}.csv")

            # 如果目标文件存在先删除，防止报错
            if os.path.exists(new_name):
                os.remove(new_name)

            os.rename(latest_file, new_name)
            print(f"📦 实验结果已归档: {label}.csv")
        else:
            print("❌ 未找到结果文件！")

        # 休息一下，防止文件读写冲突
        time.sleep(2)

    print("\n✅ 所有对比实验已完成！")


if __name__ == "__main__":
    asyncio.run(run_batch())
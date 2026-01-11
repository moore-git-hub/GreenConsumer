import json
import os
import random
import sys

# 默认配置
DEFAULT_NUM_AGENTS = 20

def generate_profiles(mode="mixed", filename="profiles.jsonl"):
    """
    mode: 'mixed' (30% Deep), 'deep_only' (100% Deep), 'light_only' (100% Light)
    """
    os.makedirs("data/agents", exist_ok=True)

    profiles = []
    print(f"⚙️ 正在生成数据... 模式: {mode}, 数量: {DEFAULT_NUM_AGENTS}")

    for i in range(DEFAULT_NUM_AGENTS):
        agent_id = f"Consumer_{i:03d}"

        # 1. 人口统计学
        age = random.randint(20, 60)
        income = random.choice(["Low", "Medium", "High"])
        education = random.choice(["High School", "Bachelor", "Master", "PhD"])

        # 2. 核心变量控制：环境卷入度
        if mode == "deep_only":
            involvement = "Deep Green"
        elif mode == "light_only":
            involvement = "Light Green"
        else:  # mixed
            involvement = "Deep Green" if random.random() < 0.3 else "Light Green"

        # 3. 大五人格 (配合调整)
        big_five = {
            "Openness": "High" if involvement == "Deep Green" else random.choice(["High", "Medium"]),
            "Conscientiousness": "High",
            "Extraversion": random.choice(["High", "Low"]),
            "Agreeableness": "High" if involvement == "Deep Green" else random.choice(["High", "Low"]),
            "Neuroticism": "Low"
        }

        profile_data = {
            "id": agent_id,
            "name": agent_id,
            "demographics": {
                "age": age,
                "income": income,
                "education": education
            },
            "psychology": {
                "environmental_involvement": involvement,
                "big_five": big_five
            },
            # 初始信任值 (0-10)
            "trust_score": round(random.uniform(5.0, 9.0), 1),
            "budget": random.randint(50, 200)
        }
        profiles.append(profile_data)

    # 写入文件
    file_path = f"data/agents/{filename}"
    with open(file_path, "w", encoding="utf-8") as f:
        for p in profiles:
            f.write(json.dumps(p) + "\n")

    print(f"✅ 数据已保存至 {file_path}")


if __name__ == "__main__":
    # 支持命令行参数: python generate_data.py deep_only
    mode = sys.argv[1] if len(sys.argv) > 1 else "mixed"
    generate_profiles(mode)
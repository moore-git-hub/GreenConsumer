import json
import os
import random
import sys

DEFAULT_NUM_AGENTS = 20

# 理论界定字典：将抽象特质转化为具体的行为范例 (Few-shot)
BEHAVIORAL_RULES = {
    "Deep Green": (
        "【核心价值观】你是一名深绿消费者（高环境卷入度）。\n"
        "1. 决策逻辑：环保认证与真实碳足迹是你消费的最高优先级，你极度厌恶并会主动抵制任何'漂绿 (Greenwashing)'行为。\n"
        "2. 行为特征：在社交网络中，你会积极揭露虚假环保宣传，并且绝不轻易原谅有过劣迹的品牌。"
    ),
    "Light Green": (
        "【核心价值观】你是一名浅绿消费者（低环境卷入度）。\n"
        "1. 决策逻辑：你支持环保，但前提是产品价格合理且质量过关。你不愿意承担过高的环保溢价。\n"
        "2. 行为特征：你容易被包装上的绿色标识打动，对深度的认证数据不感兴趣，容易遗忘品牌的负面新闻。"
    )
}

BIG_FIVE_MAPPING = {
    "Conscientiousness": {
        "High": "【高尽责性】：你知行合一，购买前必查证产品的环保资质，绝不冲动消费。",
        "Low": "【低尽责性】：你容易受情绪引导，环保态度与实际购买行为经常脱节。"
    },
    "Agreeableness": {
        "High": "【高宜人性】：你极易受邻居和KOL推荐影响，会为了'社会合许性 (Social Desirability)'而盲目从众购买。",
        "Low": "【低宜人性】：你坚持己见，不受外界舆论和他人评价干扰。"
    }
}


def generate_profiles(mode="mixed", filename="profiles.jsonl"):
    os.makedirs("data/agents", exist_ok=True)
    profiles = []
    print(f"⚙️ 正在生成数据... 模式: {mode}, 数量: {DEFAULT_NUM_AGENTS}")

    for i in range(DEFAULT_NUM_AGENTS):
        agent_id = f"Consumer_{i:03d}"

        # 核心变量控制：环境卷入度 (Environmental Involvement)
        if mode == "deep_only":
            involvement = "Deep Green"
        elif mode == "light_only":
            involvement = "Light Green"
        else:
            involvement = "Deep Green" if random.random() < 0.3 else "Light Green"

        conscientiousness = "High" if involvement == "Deep Green" else random.choice(["High", "Low"])
        agreeableness = "Low" if involvement == "Deep Green" else random.choice(["High", "Low"])

        # 组装最终的 Persona Prompt
        persona = f"{BEHAVIORAL_RULES[involvement]}\n{BIG_FIVE_MAPPING['Conscientiousness'][conscientiousness]}\n{BIG_FIVE_MAPPING['Agreeableness'][agreeableness]}"

        profile_data = {
            "id": agent_id,
            "name": agent_id,
            "psychology": {
                "environmental_involvement": involvement,
                "big_five": {
                    "Conscientiousness": conscientiousness,
                    "Agreeableness": agreeableness
                }
            },
            "persona": persona,  # 直接供认知层提取的完整画像
            "initial_trust": round(random.uniform(4.0, 6.0), 1),
            "budget": random.randint(50, 300)
        }
        profiles.append(profile_data)

    file_path = f"data/agents/{filename}"
    with open(file_path, "w",  encoding="utf-8") as f:
        for p in profiles:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print(f"✅ 数据已保存至 {file_path}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "mixed"
    generate_profiles(mode)
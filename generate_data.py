import json
import os
import random
import sys
import numpy as np

# 建议在仿真中将数量调高以体现统计学规律 (如 100)
DEFAULT_NUM_AGENTS = 50

# ==========================================
# 🧠 学术级画像库：ELM + Big Five + 90-9-1 社交媒体法则
# ==========================================

INVOLVEMENT_RULES = {
    "Deep Green": (
        "【认知模式：中心路径加工】你是一名'深绿消费者'，具备极高的环境卷入度与环保知识。\n"
        "- 决策核心：对'漂绿 (Greenwashing)'行为容忍度很低。\n"
        "- 信息处理：对企业官方的华丽宣传天然脱敏且持高度怀疑态度，倾向于独立查证事实。"
    ),
    "Light Green": (
        "【认知模式：边缘路径加工】你是一名'浅绿消费者'，环保只是你消费的加分项而非决定项。\n"
        "- 决策核心：支持环保，但前提是产品必须具备性价比且质量过关，不愿承担过高溢价。\n"
        "- 信息处理：容易被包装上的绿色标识、KOL的推荐或企业的情感营销打动，很少深究科学数据。"
    )
}

# 社交媒体角色设定表
SOCIAL_MEDIA_ROLES = {
    "KOL": (
        "【社交媒体角色：意见领袖 】你是拥有大量粉丝的环保/消费领域大V。\n"
        "- 行为特征：你表达欲旺盛。你发布的每一条内容都带有个人观点，并且会用煽动性或严谨专业的语气质问企业。"
    ),
    "Active User": (
        "【社交媒体角色：活跃网民】你是社交网络上的活跃分子。\n"
        "- 行为特征：你喜欢冲浪、吃瓜、点赞和转发。遇到有争议的品牌事件，你非常乐于在评论区发表自己的看法。"
    ),
    "Lurker": (
        "【社交媒体角色：潜水者】你是互联网上'沉默的大多数'。\n"
        "- 行为特征：你很少不主动发帖或评论。你习惯于观看网上的舆论战，这些信息会改变你对品牌的信任度，你除非对某事有发声欲，否则绝不参与网络骂战。"
    )
}

BIG_FIVE_MAPPING = {
    "Openness": {"High": "[高开放性] 乐于尝试前沿新材料。", "Low": "[低开放性] 思想保守，只信任传统成熟品牌。"},
    "Conscientiousness": {"High": "[高尽责性] 知行合一，消费极具计划性，不盲目冲动。",
                          "Low": "[低尽责性] 容易冲动消费，环保态度与购买行为常脱节。"},
    "Agreeableness": {"High": "[高宜人性] 在意他人眼光，极易受网络舆论、邻居或KOL推荐影响，会为了合群而跟风。",
                      "Low": "[低宜人性] 坚持独立思考，不受社交网络舆论的干扰。"},
    "Neuroticism": {"High": "[高神经质] 情绪极易波动。一旦看到负面曝光，信任值会断崖式崩塌。",
                    "Low": "[低神经质] 情绪稳定理智。面对负面舆情倾向于让子弹飞一会儿。"}
}


def generate_profiles(mode="mixed", filename="profiles.jsonl"):
    os.makedirs("data/agents", exist_ok=True)
    profiles = []
    print(f"生成数据... 数量: {DEFAULT_NUM_AGENTS}")

    # 统计验证字典
    stats = {"Role": {"KOL": 0, "Active User": 0, "Lurker": 0}, "Involvement": {"Deep Green": 0, "Light Green": 0}}

    for i in range(DEFAULT_NUM_AGENTS):
        agent_id = f"Consumer_{i:03d}"

        # --- 1. 社交媒体角色分配  ---
        # 概率分布：1% KOL, 9% Active, 90% Lurker
        role = np.random.choice(["KOL", "Active User", "Lurker"], p=[0.05, 0.20, 0.75])
        stats["Role"][role] += 1

        # --- 2. 人口统计学与预算 ---
        age = random.randint(18, 65)
        # KOL 通常具有较高社会资本 (高预算)
        if role == "KOL":
            income_level = "High";
            budget = random.randint(300, 800);
            education = random.choice(["Master", "PhD"])
        else:
            income_level = np.random.choice(["Low", "Medium", "High"], p=[0.4, 0.4, 0.2])
            budget = random.randint(30, 200) if income_level != "High" else random.randint(200, 500)
            education = random.choice(["High School", "Bachelor", "Master"])

        # --- 3. 环境卷入度 ---
        if mode == "deep_only":
            involvement = "Deep Green"
        elif mode == "light_only":
            involvement = "Light Green"
        else:
            # KOL 中深绿的比例更高 (环保大V通常是深绿)
            p_deep = 0.6 if role == "KOL" else 0.25
            involvement = "Deep Green" if random.random() < p_deep else "Light Green"
        stats["Involvement"][involvement] += 1

        # --- 4. 科学分配大五人格 ---
        traits = {
            "Openness": "High" if involvement == "Deep Green" else random.choice(["High", "Low"]),
            "Conscientiousness": "High" if involvement == "Deep Green" else random.choice(["High", "Low"]),
            "Agreeableness": "Low" if involvement == "Deep Green" else random.choice(["High", "Low"]),
            "Neuroticism": random.choice(["High", "Low"])
        }

        # 强制绑定外向性与社交角色
        if role == "KOL":
            traits["Extraversion"] = "Extreme High"
        elif role == "Active User":
            traits["Extraversion"] = "High"
        else:
            traits["Extraversion"] = "Low"

        # --- 5. 组装结构化 System Prompt (Persona) ---
        persona_blocks = [
            f"【基础身份】你是一名 {age}岁的消费者，学历为 {education}，收入水平 {income_level}。预算受限。",
            INVOLVEMENT_RULES[involvement],
            SOCIAL_MEDIA_ROLES[role],
            "【心理特质】"
        ]
        for trait_name, trait_val in traits.items():
            if trait_name != "Extraversion":  # 外向性已在角色中体现
                persona_blocks.append(BIG_FIVE_MAPPING[trait_name][trait_val])

        persona_prompt = "\n".join(persona_blocks)

        # --- 6. 初始状态赋值 ---
        init_trust = round(random.uniform(3.0, 5.0), 1) if involvement == "Deep Green" else round(
            random.uniform(5.0, 7.0), 1)

        profile_data = {
            "id": agent_id, "name": agent_id,
            "demographics": {"age": age, "income": income_level, "education": education},
            "psychology": {"environmental_involvement": involvement, "big_five": traits, "social_role": role},
            "persona": persona_prompt,
            "initial_trust": init_trust,
            "budget": budget
        }
        profiles.append(profile_data)

    file_path = f"data/agents/{filename}"
    with open(file_path, "w", encoding="utf-8") as f:
        for p in profiles:
            f.write(json.dumps(p) + "\n")

    # === 自带验证系统 (Validation) ===
    print("\n=== 数据分布有效性验证 (Validation) ===")
    total = sum(stats["Role"].values())
    print(f"1. 社交角色分布:")
    for r, count in stats["Role"].items():
        print(f"   - {r}: {count} 人 ({count / total * 100:.1f}%)")

    print(f"\n2. 价值观分布 (深绿 vs 浅绿):")
    for inv, count in stats["Involvement"].items():
        print(f"   - {inv}: {count} 人 ({count / total * 100:.1f}%)")
    print("==============================================\n")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "mixed"
    generate_profiles(mode)
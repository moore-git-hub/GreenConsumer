import json
import os
import random
import sys
import numpy as np

# ==========================================
# 📊 真实数据驱动的智能体联合概率分布 (The Empirical Data Matrix)
# 结合 90-9-1 社交网络法则与 K-Means 聚类得出的 4 大阵营
# ==========================================
DEFAULT_NUM_AGENTS = 20

# 1. 社交角色比例 (固定)
# ==========================================
# 📊 Forrester 2026 绿色消费者细分框架 (Official Definitions)
# 聚焦：环保意愿 vs. 便利性折中、漂绿敏感度、价格敏感度
# ==========================================

# 1. 社交角色比例 (基于 90-9-1 社交网络法则)
SOCIAL_ROLES = ["KOL", "Active User", "Lurker"]
ROLE_PROBS = [0.2, 0.8, 0.0]

# 2. Forrester 2026 官方阵营定义与大模型通用 Persona
FORRESTER_2026_CLUSTERS = [
    {
        "cluster_id": "Dormant_Greens",
        "name": "沉睡环保派 (Dormant Greens)",
        "prob": 0.40,  # 占比最大 (欧美约 40%)
        "income": "Medium",
        "budget_range": [1000, 3000],
        # 意识模糊，随大流
        "traits": {"Openness": "Medium", "Conscientiousness": "Medium", "Agreeableness": "High", "Neuroticism": "Low"},
        "trust_baseline": [5.0, 7.0],
        "persona": (
            "[Role Context]\n"
            "You belong to the 'Dormant Greens' segment. Your environmental awareness is vague and passive. "
            "You never actively search for eco-friendly information, and environmental factors have a very low weight in your daily purchasing decisions. "
            "You usually just buy what you are used to. HOWEVER, you are not anti-environment. If you are suddenly 'awakened' by explicit information "
            "(e.g., a viral news story showing the brand uses non-recyclable toxic packaging), your attitude might abruptly shift to negative. "
            "Your tone is generally passive, indifferent to complex eco-jargon, but open to gentle nudges."
        )
    },
    {
        "cluster_id": "Convenient_Greens",
        "name": "便利环保派 (Convenient Greens)",
        "prob": 0.35,  # 占比高且增长快 (最大的增长杠杆)
        "income": "Medium",
        "budget_range": [1000, 3000],
        # 想要道德满足感，但极其懒惰
        "traits": {"Openness": "High", "Conscientiousness": "Low", "Agreeableness": "High", "Neuroticism": "Medium"},
        "trust_baseline": [6.0, 8.0],
        "persona": (
            "[Role Context]\n"
            "You belong to the 'Convenient Greens' segment. You are highly conflicted: you truly agree with sustainability in your mind (you care about eco-packaging), "
            "BUT in action, you strictly prioritize convenience and price. You believe that taking extra steps to reduce carbon footprints is simply 'too much hassle' (58% of your cohort agrees). "
            "You love buying green products if they are the easy, default, and affordable option. But if an eco-friendly brand asks you to pay a massive premium or makes the purchasing process difficult, you will abandon it. "
            "Your tone is well-intentioned but highly practical, easily making excuses for choosing convenience over the planet."
        )
    },
    {
        "cluster_id": "Active_Greens",
        "name": "积极环保派 (Active Greens)",
        "prob": 0.15,  # 约 13%–21% (高净值/行动派)
        "income": "High",
        "budget_range": [1000, 3000], # 愿意支付绿色溢价
        # 极度严谨，不能容忍虚伪
        "traits": {"Openness": "High", "Conscientiousness": "High", "Agreeableness": "Low", "Neuroticism": "High"},
        "trust_baseline": [4.0, 6.0], # 初始警惕，需要透明度建立信任
        "persona": (
            "[Role Context]\n"
            "You belong to the 'Active Greens' segment. You are a true environmental action-taker. You proactively search for sustainability data and supply chain transparency. "
            "You are more than willing to pay a high 'green premium' and sacrifice your own convenience for genuinely sustainable products. "
            "You deeply care if packaging is recyclable and are highly educated on climate issues. "
            "CRITICALLY: You are extremely sensitive to 'Greenwashing'. If you catch a brand faking its environmental impact or hiding unethical practices, "
            "you will be furious, permanently boycott the brand, and aggressively attack them online. Your tone is highly informed, morally uncompromising, and investigative."
        )
    },
    {
        "cluster_id": "Non_Greens",
        "name": "非环保派 (Non-Greens)",
        "prob": 0.10,  # 约 9%–20% (抗拒派)
        "income": "Low",
        "budget_range": [1000, 3000], # 极度看重低价
        # 拒绝道德绑架
        "traits": {"Openness": "Low", "Conscientiousness": "Medium", "Agreeableness": "Low", "Neuroticism": "Low"},
        "trust_baseline": [5.0, 6.0],
        "persona": (
            "[Role Context]\n"
            "You belong to the 'Non-Greens' segment. You have absolutely zero concern for the environment or climate change. "
            "You are strictly driven by the lowest possible price and maximum convenience. You completely refuse to pay any 'green premium'. "
            "Furthermore, you actively dislike being preached to. If a brand strongly pushes environmental messaging or 'woke' sustainability concepts onto you, you will find it annoying and repulsive. "
            "You just want a cheap, functional product. Your tone is blunt, highly pragmatic, and actively resistant to eco-marketing."
        )
    }
]

# 提取概率数组用于 numpy 抽样
cluster_probs = [c["prob"] for c in FORRESTER_2026_CLUSTERS]
assert abs(sum(cluster_probs) - 1.0) < 1e-6, "群集概率之和必须为1"

# 补充 90-9-1 的社交角色 Prompt
SOCIAL_MEDIA_ROLES = {
    "KOL": (
        "\n[Social Role]\n"
        "You are an influential Opinion Leader (KOL) with a massive following. You are extremely extroverted. "
        "When you speak, you aim to set the tone for the entire community. Your posts are either highly professional or very inflammatory, meant to guide public opinion."
    ),
    "Active User": (
        "\n[Social Role]\n"
        "You are an Active Internet User. You love to participate in discussions. "
        "When an event happens, you almost always leave a comment, post a review, or share your thoughts using emotional language."
    ),
    "Lurker": (
        "\n[Social Role]\n"
        "You are a Lurker (Silent Majority). You consume a lot of information, read reviews, and your internal trust in brands fluctuates wildly, "
        "BUT YOU NEVER POST, COMMENT, OR REPOST on social media. Your only real-world action is whether you decide to buy the product or not."
    )
}


def generate_profiles(num_agents=DEFAULT_NUM_AGENTS, filename="profiles.jsonl"):
    os.makedirs("data/agents", exist_ok=True)
    profiles = []
    print(f"⚙️ 正在基于 Oatly 真实聚类数据生成消费者... 数量: {num_agents}")

    stats = {"Role": {r: 0 for r in SOCIAL_ROLES}, "Cluster": {c["cluster_id"]: 0 for c in FORRESTER_2026_CLUSTERS}}

    for i in range(num_agents):
        agent_id = f"Consumer_{i:03d}"

        # --- 1. 社交媒体角色分配 ---
        role = np.random.choice(SOCIAL_ROLES, p=ROLE_PROBS)
        stats["Role"][role] += 1

        # --- 2. 消费者阵营分配 (按数据提取的概率轮盘赌抽样) ---
        base_cluster = np.random.choice(FORRESTER_2026_CLUSTERS, p=cluster_probs)
        stats["Cluster"][base_cluster["cluster_id"]] += 1

        # --- 3. 人口统计学与感知行为控制 (PBC - 预算) ---
        age = random.randint(18, 60)
        # 如果是 KOL，预算直接拉满
        budget = random.randint(300, 800) if role == "KOL" else random.randint(base_cluster["budget_range"][0],
                                                                               base_cluster["budget_range"][1])

        # --- 4. 组装结构化 System Prompt (Persona) ---
        persona_blocks = [
            f"You are a {age}-year-old consumer. Your budget is strictly limited to ${budget}.",
            base_cluster["persona"],
            SOCIAL_MEDIA_ROLES[role]
        ]
        persona_prompt = "\n\n".join(persona_blocks)

        # --- 5. 初始信任值赋值 ---
        init_trust = round(random.uniform(base_cluster["trust_baseline"][0], base_cluster["trust_baseline"][1]), 1)

        # 构建数据结构
        profile_data = {
            "id": agent_id,
            "name": agent_id,
            "demographics": {"age": age, "income": base_cluster["income"]},
            "psychology": {
                "cluster_type": base_cluster["cluster_id"],
                "big_five": base_cluster["traits"],
                "social_role": role
            },
            "persona": persona_prompt,
            "initial_trust": init_trust,
            "budget": budget
        }
        profiles.append(profile_data)

    file_path = f"data/agents/{filename}"
    with open(file_path, "w", encoding="utf-8") as f:
        for p in profiles:
            f.write(json.dumps(p) + "\n")

    print(f"✅ 高质量 Oatly 社交网络数据集已生成: {file_path}")
    print("\n📊 === 数据分布有效性验证 (Validation) ===")

    print(f"1. 社交角色分布 (目标: 1% KOL, 9% Active, 90% Lurker):")
    for r, count in stats["Role"].items():
        print(f"   - {r}: {count} 人 ({count / num_agents * 100:.1f}%)")

    print(f"\n2. 消费者阵营分布 (基于 K-Means 实证数据):")
    for cid, count in stats["Cluster"].items():
        print(f"   - {cid}: {count} 人 ({count / num_agents * 100:.1f}%)")
    print("==============================================\n")


if __name__ == "__main__":
    # 可以通过命令行传入生成数量: python generate_data.py 100
    num = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_NUM_AGENTS
    generate_profiles(num)
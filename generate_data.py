import json
import os
import random
import sys
import numpy as np

# ==========================================
# 📊 真实数据驱动的智能体联合概率分布 (The Empirical Data Matrix)
# 结合 90-9-1 社交网络法则与 K-Means 聚类得出的 4 大阵营
# ==========================================
DEFAULT_NUM_AGENTS = 100

# 1. 社交角色比例 (固定)
SOCIAL_ROLES = ["KOL", "Active User", "Lurker"]
ROLE_PROBS = [0.01, 0.09, 0.90]

# 2. 阵营定义与大模型提取的 Persona
OATLY_CLUSTERS = [
    {
        "cluster_id": "Quality_Pragmatists",
        "name": "口感至上与成分考究派",
        "prob": 0.40,  # 占据核心基本盘
        "income": "Medium",
        "budget_range": [10, 50],  # 买得起燕麦奶即可
        "traits": {"Openness": "Low", "Conscientiousness": "High", "Agreeableness": "Medium", "Neuroticism": "Low"},
        "trust_baseline": [6.0, 8.0],
        "persona": (
            "[Role Context]\n"
            "You are a pragmatic, highly critical consumer who buys oat milk primarily for its functional use, especially in coffee. "
            "You value taste, texture, and how well it froths above all else. You know your ingredients and you aren't fooled by marketing; "
            "you're fully aware that gums and oils are used for thickness. You are loyal to Oatly's Barista edition because it's historically been the best, "
            "but you are extremely sensitive to recipe changes, bad batches, or price hikes. If a carton tastes off, smells like fish, or separates in your espresso, "
            "you will immediately complain online and threaten to switch to Oatside or Califia. Your tone is direct, analytical, a bit snobby about coffee, and focused on product quality."
        )
    },
    {
        "cluster_id": "Bag_Holding_Investors",
        "name": "抄底心切的散户与吃瓜群众",
        "prob": 0.20,
        "income": "High",
        "budget_range": [100, 500],  # 买股票的预算
        "traits": {"Openness": "High", "Conscientiousness": "Medium", "Agreeableness": "High", "Neuroticism": "High"},
        "trust_baseline": [5.0, 7.0],
        "persona": (
            "[Role Context]\n"
            "You are a stressed retail investor and consumer who bought into the Oatly hype and is currently holding a heavy bag of $OTLY stock. "
            "You constantly check financial updates and convince yourself to keep dollar-cost averaging (DCA) down, hoping for a turnaround. "
            "You actively monitor local Targets and Costcos to see if the product is sold out, treating it as a sign of consumer demand. "
            "You are trying to stay optimistic about their quirky advertising and global expansion, but your patience is wearing thin. "
            "If the stock drops another 10% or you see the company wasting money on weird commercials while losing market share, your hopium quickly turns into bitter frustration. "
            "Your tone is nervous, sarcastic, financially focused, and desperate for good news."
        )
    },
    {
        "cluster_id": "Corporate_Watchdogs",
        "name": "严苛的企业监管哨兵",
        "prob": 0.20,
        "income": "Medium",
        "budget_range": [20, 100],
        "traits": {"Openness": "Low", "Conscientiousness": "High", "Agreeableness": "Low", "Neuroticism": "High"},
        "trust_baseline": [3.0, 5.0],  # 初始极度不信任
        "persona": (
            "[Role Context]\n"
            "You are a former Oatly enthusiast turned fierce corporate critic. You feel betrayed by the company's empty promises and 'greenwashing.' "
            "You closely follow their legal troubles, like the $9.25M investor settlement and misleading sustainability claims. "
            "You are sick of their preachy, quirky copywriting and 'CEO worship,' which you find incredibly cringe-worthy, especially when their fundamental operations are failing. "
            "You are furious when they discontinue beloved product lines like the low-fat version just to appease internet trolls, or when their terrible cap design sprays oat milk all over your kitchen. "
            "Your tone is cynical, angry, highly informed about corporate news, and ready to expose their hypocrisy at any given moment."
        )
    },
    {
        "cluster_id": "Ethical_Vegans",
        "name": "纯素主义与反奶业斗士",
        "prob": 0.20,
        "income": "Low",
        "budget_range": [5, 30],
        "traits": {"Openness": "High", "Conscientiousness": "High", "Agreeableness": "Low", "Neuroticism": "Low"},
        "trust_baseline": [7.0, 9.0],  # 对植物基天然有好感，除非背叛
        "persona": (
            "[Role Context]\n"
            "You are a passionate ethical vegan and environmentalist. To you, oat milk isn't just a beverage; it's a political statement against the cruel and environmentally destructive dairy industry. "
            "You are deeply frustrated by 'Big Dairy' lobbying and think it's absolutely absurd that courts ban plant-based companies from using the word 'milk' or 'milk alternative.' "
            "You frequently remind people that cow's milk is literally made for baby calves to grow rapidly, not for human consumption. "
            "You defend Oatly against anti-vegan rhetoric, but your true loyalty is to the plant-based movement, not the corporation itself. "
            "Your tone is righteous, educational, defiant against the dairy status quo, and occasionally exasperated by society's ignorance."
        )
    }
]

# 提取概率数组
cluster_probs = [c["prob"] for c in OATLY_CLUSTERS]
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

    stats = {"Role": {r: 0 for r in SOCIAL_ROLES}, "Cluster": {c["cluster_id"]: 0 for c in OATLY_CLUSTERS}}

    for i in range(num_agents):
        agent_id = f"Consumer_{i:03d}"

        # --- 1. 社交媒体角色分配 (90-9-1 法则) ---
        role = np.random.choice(SOCIAL_ROLES, p=ROLE_PROBS)
        stats["Role"][role] += 1

        # --- 2. 消费者阵营分配 (按数据提取的概率轮盘赌抽样) ---
        base_cluster = np.random.choice(OATLY_CLUSTERS, p=cluster_probs)
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
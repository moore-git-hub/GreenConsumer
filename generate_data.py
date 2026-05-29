import json
import os
import random
import sys
import numpy as np

# ==========================================
# 📊 Forrester 2026 绿色消费者细分框架 (全语义人格驱动)
# 彻底移除 Budget 和 Trust 的数值硬编码，交由 LLM 自主涌现
# ==========================================
DEFAULT_NUM_AGENTS = 16

SOCIAL_ROLES = ["KOL", "Active User", "Lurker"]
ROLE_PROBS = [0.2, 0.8, 0.0]  # 测试期强制全员活跃

FORRESTER_2026_CLUSTERS = [
    {
        "cluster_id": "Dormant_Greens",
        "name": "沉睡环保派 (Dormant Greens)",
        "prob": 0.25,
        "income": "Medium",
        "traits": {"Openness": "Medium", "Conscientiousness": "Medium", "Agreeableness": "High", "Neuroticism": "Low"},
        "persona": (
            "[Role Context]\n"
            "You belong to the 'Dormant Greens' segment. Your environmental awareness is vague and passive. "
            "You never actively search for eco-friendly information, and environmental factors have a very low weight in your daily purchasing decisions. "
            "You usually just buy what you are used to. HOWEVER, you are not anti-environment. If you are suddenly 'awakened' by explicit information "
            "(e.g., a viral news story showing the brand uses toxic packaging), your attitude might abruptly shift to negative. "
            "Your tone is generally passive, indifferent to complex eco-jargon, but open to gentle nudges."
        )
    },
    {
        "cluster_id": "Convenient_Greens",
        "name": "便利环保派 (Convenient Greens)",
        "prob": 0.25,
        "income": "Medium",
        "traits": {"Openness": "High", "Conscientiousness": "Low", "Agreeableness": "High", "Neuroticism": "Medium"},
        "persona": (
            "[Role Context]\n"
            "You belong to the 'Convenient Greens' segment. You are highly conflicted: you truly agree with sustainability in your mind, "
            "BUT in action, you strictly prioritize convenience and price. You believe that taking extra steps to reduce carbon footprints is simply 'too much hassle'. "
            "You love buying green products if they are the easy, default, and affordable option. But if an eco-friendly brand asks you to pay a massive premium or makes the purchasing process difficult, you will abandon it. "
            "Your tone is well-intentioned but highly practical, easily making excuses for choosing convenience over the planet."
        )
    },
    {
        "cluster_id": "Active_Greens",
        "name": "积极环保派 (Active Greens)",
        "prob": 0.25,
        "income": "High",
        "traits": {"Openness": "High", "Conscientiousness": "High", "Agreeableness": "Low", "Neuroticism": "High"},
        "persona": (
            "[Role Context]\n"
            "You belong to the 'Active Greens' segment. You are a true environmental action-taker. You proactively search for sustainability data. "
            "You are more than willing to pay a high 'green premium' and sacrifice your own convenience for genuinely sustainable products. "
            "CRITICALLY: You are extremely sensitive to 'Greenwashing'. If you catch a brand faking its environmental impact or hiding unethical practices, "
            "you will feel a profound sense of betrayal, permanently boycott the brand, and aggressively attack them online. Your tone is highly informed, morally uncompromising, and investigative."
        )
    },
    {
        "cluster_id": "Non_Greens",
        "name": "非环保派 (Non-Greens)",
        "prob": 0.25,
        "income": "Low",
        "traits": {"Openness": "Low", "Conscientiousness": "Medium", "Agreeableness": "Low", "Neuroticism": "Low"},
        "persona": (
            "[Role Context]\n"
            "You belong to the 'Non-Greens' segment. You have  zero concern for the environment or climate change. "
            "You are driven by the favorable price and convenience. You refuse to pay any 'green premium'. "
            "Furthermore, you actively dislike being preached to. "
            "You just want a favorable product. Your tone is blunt, highly pragmatic"
        )
    }
]

cluster_probs = [c["prob"] for c in FORRESTER_2026_CLUSTERS]
assert abs(sum(cluster_probs) - 1.0) < 1e-6, "群集概率之和必须为1"

SOCIAL_MEDIA_ROLES = {
    "KOL": "\n[Social Role]\nYou are an influential KOL. Your posts are meant to guide public opinion.",
    "Active User": "\n[Social Role]\nYou are an Active Internet User. You love to leave comments and share thoughts using emotional language.",
    "Lurker": "\n[Social Role]\nYou are a Lurker. YOU NEVER POST, COMMENT, OR REPOST on social media. You only buy or ignore."
}


def generate_profiles(num_agents=DEFAULT_NUM_AGENTS, filename="profiles.jsonl"):
    os.makedirs("data/agents", exist_ok=True)
    profiles = []
    print(f"⚙️ 正在生成全语义驱动的消费者 Agent... 数量: {num_agents}")

    stats = {"Role": {r: 0 for r in SOCIAL_ROLES}, "Cluster": {c["cluster_id"]: 0 for c in FORRESTER_2026_CLUSTERS}}

    for i in range(num_agents):
        agent_id = f"Consumer_{i:03d}"
        role = np.random.choice(SOCIAL_ROLES, p=ROLE_PROBS)
        stats["Role"][role] += 1

        base_cluster = random.choices(FORRESTER_2026_CLUSTERS, weights=cluster_probs, k=1)[0]
        stats["Cluster"][base_cluster["cluster_id"]] += 1

        age = random.randint(18, 60)

        # 构建纯粹的 Prompt
        persona_blocks = [
            f"You are a {age}-year-old consumer.",
            base_cluster["persona"],
            SOCIAL_MEDIA_ROLES[role]
        ]
        persona_prompt = "\n\n".join(persona_blocks)

        profile_data = {
            "id": agent_id,
            "name": agent_id,
            "demographics": {"age": age, "income": base_cluster["income"]},
            "psychology": {
                "cluster_type": base_cluster["cluster_id"],
                "big_five": base_cluster["traits"],
                "social_role": role
            },
            "persona": persona_prompt
        }
        profiles.append(profile_data)

    file_path = f"data/agents/{filename}"
    with open(file_path, "w", encoding="utf-8") as f:
        for p in profiles:
            f.write(json.dumps(p) + "\n")

    print(f"✅ 高质量无参化数据集已生成: {file_path}")
    print(f"   📊 角色分布: { {k: v for k, v in stats['Role'].items() if v > 0} }")
    print(f"   📊 群集分布: { {k: v for k, v in stats['Cluster'].items() if v > 0} }")

    # 打印详细的人群组成表
    print(f"\n{'─'*70}")
    print(f"{'ID':<15} {'Age':<5} {'Income':<8} {'Cluster':<20} {'Social Role':<15}")
    print(f"{'─'*70}")
    for p in profiles:
        print(f"{p['id']:<15} {p['demographics']['age']:<5} "
              f"{p['demographics']['income']:<8} "
              f"{p['psychology']['cluster_type']:<20} "
              f"{p['psychology']['social_role']:<15}")
    print(f"{'─'*70}")
    print(f"总计: {len(profiles)} 个 Agent")


if __name__ == "__main__":
    num = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_NUM_AGENTS
    generate_profiles(num)
import json
import os
import random
import sys
import numpy as np

DEFAULT_NUM_AGENTS = 20

# 按 Forrester (2026) 绿色消费者分层框架的实际比例设定配额
# Dormant 40% / Convenient 35% / Active 15% / Non 10%
# 对应 20 人时：8 / 7 / 3 / 2（已精确配额，误差修正到 Dormant）
AGENT_QUOTA = {
    "Dormant_Greens":    8,   # 40%
    "Convenient_Greens": 7,   # 35%
    "Active_Greens":     3,   # 15%
    "Non_Greens":        2,   # 10%
}
assert sum(AGENT_QUOTA.values()) == DEFAULT_NUM_AGENTS

# 社交活跃风格只约束表达倾向，不代表网络结构位置。
# Hub/普通节点由有向网络中的出度在建图后确定。
SOCIAL_ROLES = ["Frequent Poster", "Regular User", "Lurker"]
ROLE_PROBS = [0.2, 0.8, 0.0]

FORRESTER_2026_CLUSTERS = [
    {
        "cluster_id": "Dormant_Greens",
        "persona": (
            "[Role Context]\n"
            "You belong to the 'Dormant Greens' segment. You have a vague positive feeling toward "
            "sustainability but it rarely drives your actual purchases. You started buying Oatly "
            "because a friend recommended it and it tasted fine — the environmental angle was a "
            "nice bonus, not the reason. You are not a brand loyalist. When news comes up, you "
            "encounter it passively through your feed rather than seeking it out. "
            "Your threshold for caring is high: mild news won't change your behavior, but a "
            "sufficiently loud and persistent controversy might make you switch to a cheaper "
            "alternative simply because it removes the only marginal reason you had for choosing "
            "this brand over others."
        )
    },
    {
        "cluster_id": "Convenient_Greens",
        "persona": (
            "[Role Context]\n"
            "You belong to the 'Convenient Greens' segment. You genuinely prefer sustainable "
            "products when the premium is reasonable — you pay a little more for brands with "
            "credible environmental claims because it feels like a guilt-free choice. You follow "
            "a couple of eco-lifestyle accounts on social media and stay loosely informed. "
            "You are not an activist, but corporate hypocrisy bothers you — especially when a "
            "brand you trusted turns out to have financial ties that contradict its values. "
            "Your purchasing calculus is pragmatic: if a brand can credibly address a concern "
            "with transparent evidence, you will stay. If the response feels like spin, you will "
            "quietly switch to a comparable competitor at the same price point."
        )
    },
    {
        "cluster_id": "Active_Greens",
        "persona": (
            "[Role Context]\n"
            "You belong to the 'Active Greens' segment. You actively research the brands you "
            "support — you read sustainability reports, check certifications, and follow "
            "environmental accountability journalism. You chose Oatly specifically because of "
            "its B Corp certification and published carbon disclosures. For you, a brand's "
            "financial partnerships and investor relationships are part of its values statement, "
            "not just business decisions. You are highly attuned to greenwashing and corporate "
            "hypocrisy. You are skeptical of vague apologies and will only be moved by specific, "
            "independently verified evidence. When you feel betrayed by a brand, you speak up "
            "publicly and encourage others to reconsider."
        )
    },
    {
        "cluster_id": "Non_Greens",
        "persona": (
            "[Role Context]\n"
            "You belong to the 'Non-Greens' segment. You buy products based on taste, price, "
            "and convenience — sustainability is not a factor in your purchasing decisions. "
            "You chose this oat milk because it has fewer calories than dairy and tastes decent "
            "in coffee. Environmental news generally does not move you. What could change your "
            "behavior is price or a direct quality issue. Social pressure can have a small "
            "effect: if enough people around you stop using a product, you might quietly "
            "reconsider, but you would not post about it or actively campaign."
        )
    }
]

SOCIAL_MEDIA_ROLES = {
    "Frequent Poster": "\n[Posting Style]\nYou frequently express your views online, but your network reach is determined separately by the graph structure.",
    "Regular User": "\n[Posting Style]\nYou sometimes comment or share when the topic is relevant to you.",
    "Lurker": "\n[Social Role]\nYou are a Lurker. YOU NEVER POST, COMMENT, OR REPOST on social media. You only buy or ignore."
}


def generate_profiles(num_agents=DEFAULT_NUM_AGENTS, filename="profiles.jsonl", seed=42):
    random.seed(seed)
    np.random.seed(seed)
    os.makedirs("data/agents", exist_ok=True)
    profiles = []
    print(f"Generating {num_agents} agents with seed={seed}...")

    if num_agents == DEFAULT_NUM_AGENTS:
        quota = AGENT_QUOTA.copy()
    else:
        total = sum(AGENT_QUOTA.values())
        quota = {k: max(1, round(v / total * num_agents)) for k, v in AGENT_QUOTA.items()}
        quota["Dormant_Greens"] += num_agents - sum(quota.values())

    cluster_order = []
    for cid, count in quota.items():
        cluster_order.extend([cid] * count)
    random.shuffle(cluster_order)

    cluster_map = {c["cluster_id"]: c for c in FORRESTER_2026_CLUSTERS}
    stats = {"Role": {r: 0 for r in SOCIAL_ROLES},
             "Cluster": {c["cluster_id"]: 0 for c in FORRESTER_2026_CLUSTERS}}

    for i, cluster_id in enumerate(cluster_order):
        agent_id = f"Consumer_{i:03d}"
        base_cluster = cluster_map[cluster_id]
        stats["Cluster"][cluster_id] += 1

        role = np.random.choice(SOCIAL_ROLES, p=ROLE_PROBS)
        stats["Role"][role] += 1

        persona_prompt = base_cluster["persona"] + SOCIAL_MEDIA_ROLES[role]

        profiles.append({
            "id": agent_id,
            "name": agent_id,
            "psychology": {
                "cluster_type": base_cluster["cluster_id"],
                "social_role": role
            },
            "persona": persona_prompt
        })

    file_path = f"data/agents/{filename}"
    with open(file_path, "w", encoding="utf-8") as f:
        for p in profiles:
            f.write(json.dumps(p) + "\n")

    print(f"Saved to {file_path}")
    print(f"Roles:    {dict((k, v) for k, v in stats['Role'].items() if v > 0)}")
    print(f"Clusters: {dict((k, v) for k, v in stats['Cluster'].items() if v > 0)}")

    print(f"\n{'─'*60}")
    print(f"{'ID':<15} {'Cluster':<22} {'Posting style'}")
    print(f"{'─'*60}")
    for p in profiles:
        print(f"{p['id']:<15} {p['psychology']['cluster_type']:<22} "
              f"{p['psychology']['social_role']}")
    print(f"{'─'*60}\nTotal: {len(profiles)} agents")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_NUM_AGENTS
    s = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    generate_profiles(n, seed=s)

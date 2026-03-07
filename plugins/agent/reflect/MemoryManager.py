import numpy as np

class MemoryManager:
    """
    基于有限理性 (Bounded Rationality) 假设的联想记忆模型。
    """
    def __init__(self, alpha=1.0, beta=1.0, gamma=1.5):
        self.memory_stream = []
        self.weights = {'alpha': alpha, 'beta': beta, 'gamma': gamma}

    def _get_embedding(self, text: str) -> np.ndarray:
        # 占位：生产环境需替换为 sentence-transformers
        np.random.seed(sum(ord(c) for c in text) % (2**32))
        return np.random.rand(384)

    def add_memory(self, tick: int, content: str, importance: float):
        self.memory_stream.append({
            "tick": tick,
            "content": content,
            "importance": importance,
            "embedding": self._get_embedding(content)
        })

    def retrieve(self, current_tick: int, query: str, top_k: int = 3) -> list:
        if not self.memory_stream: return []
        query_emb = self._get_embedding(query)
        scored_memories = []

        for mem in self.memory_stream:
            # 新近性衰减 (Recency)
            recency = np.exp(-0.1 * (current_tick - mem['tick']))
            # 重要性 (Importance)
            importance = mem['importance'] / 10.0
            # 相关性 (Relevance)
            relevance = np.dot(query_emb, mem['embedding']) / (np.linalg.norm(query_emb) * np.linalg.norm(mem['embedding']) + 1e-9)

            score = (self.weights['alpha'] * recency + self.weights['beta'] * importance + self.weights['gamma'] * relevance)
            scored_memories.append((score, f"Tick {mem['tick']}: {mem['content']}"))

        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [mem[1] for mem in scored_memories[:top_k]]
import numpy as np

# 尝试加载 sentence-transformers，失败时回退到确定性哈希向量
try:
    from sentence_transformers import SentenceTransformer as _ST
    _SBERT_MODEL = _ST("paraphrase-multilingual-MiniLM-L12-v2")
    _USE_SBERT = True
    print("✅ [MemoryManager] sentence-transformers 已加载，使用真实语义 Embedding。")
except ImportError:
    _SBERT_MODEL = None
    _USE_SBERT = False
    print("⚠️ [MemoryManager] sentence-transformers 未安装，回退到确定性哈希向量（相关性计算为近似值）。")


class MemoryManager:
    """
    基于有限理性 (Bounded Rationality) 假设的联想记忆模型。

    Embedding 策略（按优先级）：
      1. sentence-transformers paraphrase-multilingual-MiniLM-L12-v2（真实语义，支持中英文）
      2. 确定性哈希向量（无需额外依赖，相关性为近似值，但保证同文本同向量）

    安装真实 Embedding：
        pip install sentence-transformers
    """

    def __init__(self, alpha=1.0, beta=1.0, gamma=1.5):
        self.memory_stream = []
        self.weights = {'alpha': alpha, 'beta': beta, 'gamma': gamma}

    def _get_embedding(self, text: str) -> np.ndarray:
        """获取文本的向量表示。优先使用 sentence-transformers，否则用确定性哈希向量。"""
        if _USE_SBERT and _SBERT_MODEL is not None:
            # encode() 返回 numpy array，shape=(384,)
            return _SBERT_MODEL.encode(text, normalize_embeddings=True)
        else:
            # 确定性哈希向量：同一文本始终返回相同向量，避免随机种子污染全局状态
            h = hash(text) & 0xFFFFFFFF  # 32-bit 无符号哈希
            rng = np.random.default_rng(seed=h)
            vec = rng.random(384).astype(np.float32)
            norm = np.linalg.norm(vec)
            return vec / (norm + 1e-9)  # 归一化，使余弦相似度有意义

    def add_memory(self, tick: int, content: str, importance: float):
        self.memory_stream.append({
            "tick": tick,
            "content": content,
            "importance": importance,
            "embedding": self._get_embedding(content)
        })

    def retrieve(self, current_tick: int, query: str, top_k: int = 3) -> list:
        if not self.memory_stream:
            return []

        query_emb = self._get_embedding(query)
        scored_memories = []

        for mem in self.memory_stream:
            # 新近性衰减 (Recency)
            recency = np.exp(-0.1 * (current_tick - mem['tick']))
            # 重要性 (Importance)
            importance = mem['importance'] / 10.0
            # 相关性 (Relevance)：余弦相似度（向量已归一化，直接点积即可）
            relevance = float(np.dot(query_emb, mem['embedding']))

            score = (self.weights['alpha'] * recency
                     + self.weights['beta'] * importance
                     + self.weights['gamma'] * relevance)
            scored_memories.append((score, f"Tick {mem['tick']}: {mem['content']}"))

        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [mem[1] for mem in scored_memories[:top_k]]
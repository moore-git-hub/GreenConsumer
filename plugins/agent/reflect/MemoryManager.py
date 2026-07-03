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
    真实 Embedding：
        pip install sentence-transformers
    """

    MAX_MEMORY_SIZE = 50   # 最多保留 50 条记忆（超出时淘汰重要性最低且最旧的）

    def __init__(self, alpha=1.0, beta=1.0, gamma=1.5):
        self.memory_stream = []
        self.weights = {'alpha': alpha, 'beta': beta, 'gamma': gamma}

    def _get_embedding(self, text: str) -> np.ndarray:
        """获取文本的向量表示。优先使用 sentence-transformers，回退到 n-gram 哈希向量。"""
        if _USE_SBERT and _SBERT_MODEL is not None:
            return _SBERT_MODEL.encode(text, normalize_embeddings=True)
        # 回退：bigram 计数向量（512 维），比单字符累加有更好的语义区分度
        # 相同主题的文本（如两条关于 Blackstone 的新闻）会产生更高的余弦相似度
        dim = 512
        vec = np.zeros(dim, dtype=np.float32)
        words = text.lower().split()
        # unigram
        for w in words:
            h = hash(w) % dim
            vec[abs(h)] += 1.0
        # bigram
        for i in range(len(words) - 1):
            bg = words[i] + "_" + words[i+1]
            h = hash(bg) % dim
            vec[abs(h)] += 1.5   # bigram 权重略高
        norm = np.linalg.norm(vec)
        return vec / (norm + 1e-9)


    def add_memory(self, tick: int, content: str, importance: float):
        self.memory_stream.append({
            "tick": tick,
            "content": content,
            "importance": importance,
            "embedding": self._get_embedding(content)
        })
        # 超出容量时淘汰：按 importance 升序 + tick 升序，删除最旧且最不重要的
        if len(self.memory_stream) > self.MAX_MEMORY_SIZE:
            self.memory_stream.sort(key=lambda m: (m["importance"], m["tick"]))
            self.memory_stream = self.memory_stream[-(self.MAX_MEMORY_SIZE):]

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
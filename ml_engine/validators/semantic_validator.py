"""Semantic Validator"""
import numpy as np
import logging

logger = logging.getLogger(__name__)

class SemanticValidator:
    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.available = True
        except ImportError:
            self.available = False

    def calculate_similarity(self, text1: str, text2: str) -> float:
        if not self.available:
            return 0.0
        try:
            emb1 = self.model.encode(text1, convert_to_tensor=True)
            emb2 = self.model.encode(text2, convert_to_tensor=True)
            from sentence_transformers import util
            return float(util.pytorch_cos_sim(emb1, emb2).item())
        except:
            return 0.0

    def validate_open_ended(self, synthetic_responses, real_responses):
        if not self.available or not real_responses:
            return {"test": "semantic_similarity", "status": "skipped"}
        
        similarities = []
        for syn in synthetic_responses[:5]:
            max_sim = max([self.calculate_similarity(str(syn), str(real)) 
                          for real in real_responses[:10]], default=0)
            similarities.append(max_sim)
        
        avg_similarity = np.mean(similarities) if similarities else 0.0
        tier = "TIER_1" if avg_similarity > 0.85 else "TIER_2" if avg_similarity > 0.70 else "TIER_3"
        return {"test": "semantic_similarity", "average_similarity": float(avg_similarity),
               "tier": tier, "match_score": float(avg_similarity)}


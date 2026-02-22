"""
AI 模型集成
支持：FinBERT、Isolation Forest、Gemini
"""
import os
from typing import Optional, Dict, Any, List
from loguru import logger

# 尝试导入 Transformers（情感分析）
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("Transformers 未安装，情感分析功能受限")

# 尝试导入 Scikit-learn（异常检测）
try:
    from sklearn.ensemble import IsolationForest
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("Scikit-learn 未安装，异常检测功能受限")

# 尝试导入 Google AI (使用新版API)
try:
    from google import genai
    GENAI_AVAILABLE = True
    logger.info("✅ Google GenerativeAI 已加载")
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("Google AI 未安装")


class AIModels:
    """AI 模型管理器"""
    
    def __init__(self):
        self.finbert_available = TRANSFORMERS_AVAILABLE
        self.isolation_forest_available = SKLEARN_AVAILABLE
        self.genai_available = GENAI_AVAILABLE
        
        logger.info(f"AI 模型状态:")
        logger.info(f"  FinBERT: {'✅' if self.finbert_available else '❌'}")
        logger.info(f"  Isolation Forest: {'✅' if self.isolation_forest_available else '❌'}")
        logger.info(f"  GenAI: {'✅' if self.genai_available else '❌'}")
    
    def get_status(self) -> Dict[str, bool]:
        """获取所有模型状态"""
        return {
            'finbert': self.finbert_available,
            'isolation_forest': self.isolation_forest_available,
            'genai': self.genai_available,
        }


if __name__ == '__main__':
    models = AIModels()
    print("AI 模型状态:", models.get_status())

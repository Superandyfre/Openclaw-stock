#!/usr/bin/env python3
"""
Gemini 模型智能管理器 (2026版)
根据任务类型自动选择最合适的模型，配额耗尽时自动降级
降级链：gemini-2.0-flash → gemini-1.5-flash → gemini-2.0-flash-lite → DeepSeek
"""
import os
import asyncio
from typing import Optional, Literal
from loguru import logger

try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("Google AI 未安装")

try:
    from openai import OpenAI as OpenAIClient
    OPENAI_SDK_AVAILABLE = True
except ImportError:
    OPENAI_SDK_AVAILABLE = False

try:
    from groq import Groq as GroqClient
    GROQ_SDK_AVAILABLE = True
except ImportError:
    GROQ_SDK_AVAILABLE = False


TaskType = Literal[
    'lightweight',      # 轻量任务：公告标题初筛、简单问答
    'standard',         # 标准任务：日常监控、一般推荐
    'complex',          # 复杂任务：深度分析、策略研判
    'experimental'      # 实验任务：前沿功能测试
]


class GeminiModelManager:
    """Gemini模型智能管理器（含自动降级链）"""

    # 免费tier实际每日配额（2026年2月）：
    #   gemini-2.5-flash: 20次/天
    #   gemini-2.0-flash: 1500次/天（但每个API key共享，今天已耗尽则0）
    #   gemini-2.0-flash-lite: 1500次/天
    #   gemini-1.5-flash: 1500次/天（单独配额，不与2.0共享）

    # 降级链：配额/不可用时按顺序尝试，直到有一个成功
    FALLBACK_CHAIN = [
        'gemini-2.0-flash',
        'gemini-2.0-flash-lite',
    ]

    MODEL_CONFIG = {
        'lightweight': {
            'name': 'gemini-2.0-flash-lite',
            'description': '轻量级模型，配额充足',
            'use_cases': ['公告标题筛选', '简单问答', '关键词提取'],
            'quota': '免费: 1500次/天'
        },
        'standard': {
            'name': 'gemini-2.0-flash',
            'description': 'Gemini 2.0 Flash，日常对话主力模型',
            'use_cases': ['日常盯盘', '一般推荐', '情感分析', '自然语言理解'],
            'quota': '免费: 1500次/天'
        },
        'complex': {
            'name': 'gemini-2.5-flash',
            'description': 'Gemini 2.5 Flash，深度分析（配额有限）',
            'use_cases': ['深度市场分析', '交易策略判断', '风险评估', '长文本研报分析'],
            'quota': '免费: 20次/天'
        },
        'experimental': {
            'name': 'gemini-2.0-flash',
            'description': '实验性功能，使用2.0 Flash',
            'use_cases': ['前沿功能测试', '极长上下文处理'],
            'quota': '免费: 1500次/天'
        }
    }
    
    def __init__(self, api_key: Optional[str] = None, default_task_type: TaskType = 'standard'):
        """
        初始化模型管理器

        Args:
            api_key: Google AI API密钥
            default_task_type: 默认任务类型
        """
        self.api_key = api_key or os.getenv('GOOGLE_AI_API_KEY')
        self.default_task_type = default_task_type
        self.genai_client = None
        self.current_model_name = None
        self.deepseek_client = None
        self.groq_client = None

        if not GENAI_AVAILABLE:
            logger.error("Google AI SDK 未安装")
            return

        if not self.api_key:
            logger.error("GOOGLE_AI_API_KEY 未设置")
            return

        # 创建 Gemini Client (新API)
        try:
            self.genai_client = genai.Client(api_key=self.api_key)
            logger.info("✅ Gemini Client 初始化成功")
        except Exception as e:
            logger.error(f"创建Gemini Client失败: {e}")
            return

        # 初始化 Groq 客户端（lightweight 首选，~0.5s 延迟）
        groq_key = os.getenv('GROQ_API_KEY')
        if groq_key and GROQ_SDK_AVAILABLE:
            try:
                self.groq_client = GroqClient(api_key=groq_key)
                logger.info("✅ Groq 客户端初始化成功（lightweight 路由首选）")
            except Exception as e:
                logger.warning(f"Groq 初始化失败: {e}")
        elif groq_key and not GROQ_SDK_AVAILABLE:
            logger.warning("⚠️ groq 包未安装（pip install groq），跳过 Groq")
        else:
            logger.info("ℹ️ GROQ_API_KEY 未设置，跳过 Groq")

        # 初始化 DeepSeek 备用客户端
        deepseek_key = os.getenv('DEEPSEEK_API_KEY')
        if deepseek_key and OPENAI_SDK_AVAILABLE:
            try:
                self.deepseek_client = OpenAIClient(
                    api_key=deepseek_key,
                    base_url='https://api.deepseek.com'
                )
                logger.info("✅ DeepSeek 备用客户端初始化成功")
            except Exception as e:
                logger.warning(f"DeepSeek 初始化失败: {e}")
        elif not deepseek_key:
            logger.info("ℹ️ DEEPSEEK_API_KEY 未设置，跳过DeepSeek备用")
        elif not OPENAI_SDK_AVAILABLE:
            logger.warning("⚠️ openai 包未安装，无法使用DeepSeek备用（pip install openai）")

        # 设置当前默认模型名称
        self.current_model_name = self.MODEL_CONFIG[default_task_type]['name']
    
    def get_model(self, task_type: TaskType = None):
        """
        获取指定任务类型的模型名称
        
        Args:
            task_type: 任务类型，如果为None则使用默认类型
        
        Returns:
            模型名称字符串
        """
        task_type = task_type or self.default_task_type
        config = self.MODEL_CONFIG.get(task_type)
        if config:
            self.current_model_name = config['name']
            logger.info(f"✅ 选择Gemini模型: {self.current_model_name} ({config['description']})")
            return self.current_model_name
        return None
    
    def _call_gemini_model(self, model_name: str, prompt: str) -> str:
        """调用指定的Gemini模型 (同步)"""
        if not self.genai_client:
            raise RuntimeError("Gemini Client 未初始化")
        
        response = self.genai_client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        return response.text.strip()

    async def _call_groq(self, prompt: str, model: str = 'llama-3.3-70b-versatile') -> Optional[str]:
        """调用 Groq LPU 推理（极低延迟，~0.5s）"""
        if not self.groq_client:
            return None
        def _sync():
            resp = self.groq_client.chat.completions.create(
                model=model,
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=512,
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()
        try:
            text = await asyncio.to_thread(_sync)
            logger.info(f"✅ Groq ({model}) 响应成功")
            return text
        except Exception as e:
            logger.warning(f"⚠️ Groq 调用失败: {e}")
            return None

    async def generate_with_fallback(self, prompt: str, task_type: TaskType = 'standard') -> Optional[str]:
        """
        调用LLM，按优先级顺序尝试：
        【临时策略：DeepSeek 最高优先】
          1. DeepSeek（中国直连，最稳定）
          2. Groq（lightweight 任务备用：最低延迟）
          3. Gemini 降级链（gemini-2.0-flash → gemini-2.0-flash-lite）
        恢复原策略：恢复 .bak 备份覆盖此文件即可。
        """
        # ── 1. DeepSeek 最高优先（中国直连稳定）──
        if self.deepseek_client:
            try:
                def _call_deepseek():
                    resp = self.deepseek_client.chat.completions.create(
                        model='deepseek-chat',
                        messages=[{'role': 'user', 'content': prompt}],
                        max_tokens=1024,
                        temperature=0.3,
                    )
                    return resp.choices[0].message.content.strip()
                text = await asyncio.to_thread(_call_deepseek)
                if text:
                    logger.info("✅ DeepSeek 响应成功（最高优先）")
                    return text
            except Exception as e:
                err = str(e)
                if '402' in err or 'Insufficient Balance' in err:
                    logger.error("❌ DeepSeek 余额不足，降级到 Groq/Gemini")
                elif '401' in err:
                    logger.error("❌ DeepSeek API Key 无效，降级到 Groq/Gemini")
                else:
                    logger.warning(f"⚠️ DeepSeek 调用失败: {err[:80]}，降级...")

        # ── 2. Groq 备用（lightweight 优先，延迟极低）──
        if task_type == 'lightweight' and self.groq_client:
            text = await self._call_groq(prompt)
            if text:
                return text
            logger.warning("⚠️ Groq 失败，降级到 Gemini...")

        # ── 3. Gemini 降级链 (使用新API) ──
        if not self.genai_client:
            logger.error("❌ Gemini Client 未初始化")
            return None
            
        primary = self.MODEL_CONFIG.get(task_type, {}).get('name', 'gemini-2.0-flash')
        chain = [primary] + [m for m in self.FALLBACK_CHAIN if m != primary]

        for model_name in chain:
            try:
                text = await asyncio.to_thread(self._call_gemini_model, model_name, prompt)
                if model_name != primary:
                    logger.warning(f"⚠️ 已降级使用: {model_name}")
                else:
                    logger.info(f"✅ 使用模型: {model_name}")
                return text
            except Exception as e:
                err = str(e)
                if '429' in err or '404' in err or 'quota' in err.lower() or 'RESOURCE_EXHAUSTED' in err or 'not found' in err.lower():
                    logger.warning(f"⚠️ {model_name} 不可用（{err[:60]}），尝试下一个...")
                    continue
                else:
                    logger.error(f"模型 {model_name} 调用失败（非配额问题）: {e}")
                    raise

        # ── 4. Groq 最后兜底（standard/complex）──
        if task_type != 'lightweight' and self.groq_client:
            logger.warning("⚠️ 所有Gemini耗尽，切换到 Groq 最终兜底...")
            text = await self._call_groq(prompt)
            if text:
                return text

        logger.error("❌ 所有AI模型均不可用")
        return None

    def switch_to(self, task_type: TaskType):
        """
        切换到指定任务类型的模型

        Args:
            task_type: 任务类型

        Returns:
            模型名称
        """
        return self.get_model(task_type)
    
    def get_model_info(self, task_type: TaskType = None) -> dict:
        """获取模型信息"""
        task_type = task_type or self.default_task_type
        return self.MODEL_CONFIG.get(task_type, {})
    
    def list_available_models(self):
        """列出所有可用的模型配置"""
        logger.info("\n📋 可用的Gemini模型配置：\n")
        
        for task_type, config in self.MODEL_CONFIG.items():
            logger.info(f"🔹 {task_type.upper()}")
            logger.info(f"   模型: {config['name']}")
            logger.info(f"   描述: {config['description']}")
            logger.info(f"   用途: {', '.join(config['use_cases'])}")
            logger.info("")


# 便捷函数
def get_lightweight_model(api_key: Optional[str] = None):
    """获取轻量级模型管理器（最省钱）"""
    manager = GeminiModelManager(api_key, default_task_type='lightweight')
    return manager


def get_standard_model(api_key: Optional[str] = None):
    """获取标准模型管理器（日常使用）"""
    manager = GeminiModelManager(api_key, default_task_type='standard')
    return manager


def get_complex_model(api_key: Optional[str] = None):
    """获取复杂分析模型管理器（深度推理）"""
    manager = GeminiModelManager(api_key, default_task_type='complex')
    return manager


def get_experimental_model(api_key: Optional[str] = None):
    """获取实验模型管理器（最新技术）"""
    manager = GeminiModelManager(api_key, default_task_type='experimental')
    return manager


if __name__ == '__main__':
    # 测试
    manager = GeminiModelManager()
    manager.list_available_models()
    
    # 测试模型切换
    print("\n测试模型切换：")
    
    for task_type in ['lightweight', 'standard', 'complex']:
        model_name = manager.get_model(task_type)
        if model_name:
            print(f"✅ {task_type}: {model_name}")
        else:
            print(f"❌ {task_type}: 加载失败")

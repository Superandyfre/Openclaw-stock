#!/usr/bin/env python3
"""
列出所有可用的Gemini模型
"""
import os
from dotenv import load_dotenv

load_dotenv()

try:
    import google.generativeai as genai
    
    api_key = os.getenv('GOOGLE_AI_API_KEY')
    if not api_key:
        print("❌ GOOGLE_AI_API_KEY 未设置")
        exit(1)
    
    genai.configure(api_key=api_key)
    
    print("📋 可用的Gemini模型列表：\n")
    
    models = genai.list_models()
    
    for model in models:
        # 只显示支持 generateContent 的模型
        if 'generateContent' in model.supported_generation_methods:
            print(f"✅ {model.name}")
            print(f"   版本: {model.version if hasattr(model, 'version') else 'N/A'}")
            print(f"   描述: {model.display_name if hasattr(model, 'display_name') else 'N/A'}")
            print()
    
except Exception as e:
    print(f"❌ 列举模型失败: {e}")
    import traceback
    traceback.print_exc()

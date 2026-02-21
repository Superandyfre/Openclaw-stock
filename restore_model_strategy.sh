#!/bin/bash
# 恢复 LLM 路由原策略（Gemini 优先）
# 当前备份：gemini_model_manager.py.bak_20260220_141003

BAK="/home/andy/projects/Openclaw-stock/openclaw/skills/analysis/gemini_model_manager.py.bak_20260220_141003"
TARGET="/home/andy/projects/Openclaw-stock/openclaw/skills/analysis/gemini_model_manager.py"

if [ ! -f "$BAK" ]; then
    echo "❌ 备份文件不存在: $BAK"
    exit 1
fi

cp "$BAK" "$TARGET"
echo "✅ 已恢复原策略（Gemini 优先 → Groq 备用 → DeepSeek 兜底）"
killbot 2>/dev/null
sleep 2
OPCLSTART
echo "✅ Bot 已重启"

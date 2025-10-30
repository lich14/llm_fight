#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""AI战场分析模块"""

import json
import os
from openai import OpenAI

class AIAnalyzer:
    """AI战场分析器"""
    
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
        self.analysis_file = "ai_analysis.json"
        
    def analyze_situation(self):
        """分析战场情况"""
        print("=== AI分析战场情况 ===")
        
        # 读取用户意图
        user_intent = self._load_user_intent()
        # 读取战场状态
        battlefield_state = self._load_battlefield_state()
        
        if not user_intent or not battlefield_state:
            print("❌ 无法读取必要数据")
            return None
            
        # 进行AI分析
        analysis = self._perform_ai_analysis(user_intent, battlefield_state)
        
        # 保存分析结果
        with open(self.analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
            
        print("✅ AI分析完成并保存")
        return analysis
    
    def _load_user_intent(self):
        """加载用户意图"""
        try:
            with open("user_intent.json", 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            print("❌ 无法读取用户意图文件")
            return None
    
    def _load_battlefield_state(self):
        """加载战场状态"""
        try:
            with open("battlefield_state.json", 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            print("❌ 无法读取战场状态文件")
            return None
    
    def _perform_ai_analysis(self, user_intent, battlefield_state):
        """执行AI分析"""
        economy = battlefield_state.get('economy', {})
        production = battlefield_state.get('production', {})
        
        prompt = f"""你是红警游戏战略AI。请分析当前情况并制定策略。

用户指令: "{user_intent['raw_input']}"
用户意图类型: {user_intent['intent_type']}
用户偏好单位: {user_intent['priority_units']}
用户战略: {user_intent['strategy']}

当前战场状况:
💰 经济状况:
- 现金: ${economy.get('cash', 0)}
- 电力: {economy.get('power', 0)}/{economy.get('power_provided', 0)}

🏭 生产队列:
- 步兵队列: {production.get('infantry', {}).get('items', 0)}项目
- 载具队列: {production.get('vehicle', {}).get('items', 0)}项目  
- 建筑队列: {production.get('building', {}).get('items', 0)}项目

请返回JSON格式的分析和决策:
{{
  "situation_assessment": "战况评估",
  "user_intent_interpretation": "用户意图理解",
  "recommended_strategy": "推荐策略",
  "priority_actions": ["行动1", "行动2"],
  "production_recommendations": {{
    "infantry_units": ["单位代码"],
    "vehicle_units": ["单位代码"],
    "building_units": ["单位代码"]
  }},
  "reasoning": "详细推理过程"
}}

可用单位类型（推测）:
- 步兵: e1(步兵), e6(工程师)
- 载具: jeep(吉普车), tank(坦克), bike(摩托) 
- 建筑: barr(兵营), weap(战车工厂)"""

        try:
            print("🧠 GPT分析中...")
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            decision_text = response.choices[0].message.content
            
            # 提取JSON
            start = decision_text.find('{')
            end = decision_text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = decision_text[start:end]
                analysis = json.loads(json_str)
                
                print(f"📋 AI评估: {analysis.get('situation_assessment', '未知')}")
                print(f"🎯 推荐策略: {analysis.get('recommended_strategy', '未知')}")
                
                return analysis
                
        except Exception as e:
            print(f"❌ AI分析失败: {e}")
            
        # 失败时返回默认分析
        return {
            "situation_assessment": "无法进行AI分析",
            "user_intent_interpretation": user_intent['raw_input'],
            "recommended_strategy": "保守发展",
            "priority_actions": ["生产基础单位"],
            "production_recommendations": {
                "infantry_units": ["e1"],
                "vehicle_units": [],
                "building_units": []
            },
            "reasoning": "AI分析不可用，使用默认策略"
        }

def main():
    """主函数"""
    API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
    
    analyzer = AIAnalyzer(API_KEY)
    analysis = analyzer.analyze_situation()
    
    if analysis:
        print(f"\n🎯 AI建议:")
        for action in analysis.get('priority_actions', []):
            print(f"   - {action}")
    
if __name__ == "__main__":
    main()
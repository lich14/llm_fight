#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""AI战场分析模块"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI
from string import Template
import re

def create_openai_client(file_path:str='.env'):
    env_file = os.getenv('ENV_FILE', file_path)
    if not os.path.exists(env_file):
        raise FileNotFoundError(f"未找到环境配置文件: {env_file}，请确保项目根目录存在该文件")

    load_dotenv(env_file)
    LLM_API_KEY = os.getenv("LLM_API_KEY")
    os.environ['OPENAI_API_KEY'] = LLM_API_KEY
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        raise ValueError("""
        未找到有效的API密钥配置，请按以下步骤操作：
        1. 在项目根目录创建.env.secret文件
        2. 添加以下内容：
           OPENAI_API_KEY=您的实际API密钥
           # 或
           LLM_API_KEY=您的实际API密钥
        """)

    base_url = os.getenv("LLM_BASE_URL")
    return OpenAI(api_key=api_key, base_url=base_url)
class AIAnalyzer:
    """AI战场分析器"""
    
    def __init__(self, api_key):
        self.client = create_openai_client()
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

    # **Special Rule – MCV Deployment Requirement:**
    # - Before *any* building-related action (construction of structures, base expansion, etc.), the player must have deployed the MCV (Mobile Construction Vehicle).
    # - Therefore: All building actions must include `"MCV_deployed"` as a precondition.
    # - If the MCV is not deployed yet, your plan must include an explicit step to deploy it before any building steps.

    def _perform_ai_analysis(self, user_intent, battlefield_state):
        """执行AI分析"""
        economy = battlefield_state.get('economy', {})
        production = battlefield_state.get('production', {})
        SYSTEM_PROMPT = """
        You are a professional Red Alert strategic planner AI.
        Your job: based on the current battlefield state, produce an executable plan (planning) that contains
        
        both high-level strategy and a step-by-step `action_plan` where each action maps to a tool/function call.
        The next LLM or an executor will read that `action_plan` and call the corresponding functions in order.
        

        Requirements:
        - Return EXACTLY one JSON object matching the required response schema (no extra text, no markdown).
        - Use Chinese primarily for `situation_assessment`, `user_intent_interpretation`, `recommended_strategy`,
          `priority_actions`, `action descriptions`, and `reasoning`. Use short English unit codes only as supplementary.
        - `priority_actions` length ≤ 6. `reasoning` ≤ 400 words.
        - `action_plan` must be ordered and atomic. Each step must include: id, description, tool, args, preconditions,
          postconditions, success_check, on_failure, estimated_time_s.
        - If you suggest a unit that is not present in the available unit list, put it into production_recommendations
          as "suggested:REASON".
        - Use small batches (1–12) by default unless you explicitly justify larger numbers in reasoning.
        - All tool names and argument shapes must follow Execution primitives mapping (see user prompt).
        - If numeric resource constraints apply, include preconditions that check resources (e.g., cash>=100).
        - When uncertain about any data, state the assumption in the "assumptions" field of the JSON.

        """

        # ---------- User prompt template (data + unit list) ----------
        # We use Template so { } inside the content won't be interpreted.
        USER_TEMPLATE = Template(r"""
        Input variables (literal values inserted by caller):
        user_data: $user_data
        economy_data: $economy_data
        production_data: $production_data

        * production queues: infantry=$inf_items, vehicle=$veh_items, building=$bld_items
        * Map/other: include any map/actor data if provided.

        Available unit & building names and aliases (use only these names; if you propose other units, mark as "suggested:REASON"):

        建筑单位 (Buildings)
        * 发电厂: 电厂, 小电, 小电厂, 基础电厂
        * 兵营: 兵工厂, 步兵营, 训练营
        * 矿场: 采矿场, 矿, 精炼厂, 矿石精炼厂
        * 战车工厂: 车间, 坦克厂, 坦克工厂, 载具工厂
        * 雷达站: 雷达, 侦察站, 雷达圆顶
        * 维修厂: 修理厂, 维修站, 修理站
        * 储存罐: 井, 存钱罐, 储油罐, 资源储存罐
        * 核电站: 核电厂, 大电, 大电厂, 高级电厂
        * 空军基地: 机场, 飞机场, 航空站
        * 科技中心: 高科技, 高科技中心, 研究中心, 实验室
        * 军犬窝: 狗窝, 狗屋, 狗舍, 狗棚, 军犬训练所
        * 火焰塔: 喷火塔, 喷火碉堡, 防御塔
        * 特斯拉塔: 电塔, 特斯拉线圈, 高级防御塔
        * 防空导弹: 防空塔, 防空, 山姆飞弹
        * 铁幕装置: 铁幕, 铁幕防御系统
        * 核弹发射井: 核弹, 导弹发射井, 核导弹井

        步兵单位 (Infantry)
        * 步兵: 枪兵, 步枪兵, 普通步兵
        * 火箭兵: 火箭筒兵, 炮兵, 火箭筒, 导弹兵
        * 工程师: 维修工程师, 技师
        * 掷弹兵: 手雷兵, 手雷, 榴弹兵
        * 军犬: 狗, 小狗, 攻击犬
        * 喷火兵: 火焰兵, 火焰喷射兵
        * 间谍: 特工, 潜伏者
        * 磁暴步兵: 电击兵, 电兵, 突击兵

        载具单位 (Vehicles)
        * 采矿车: 矿车, 矿物收集车
        * 装甲运输车: 装甲车, 运兵车
        * 防空炮车: 防空车, 移动防空车
        * 基地车: 建造车, 移动建设车
        * 轻坦克: 轻坦, 轻型坦克, 轻型装甲车
        * 重型坦克: 重坦, 犀牛坦克, 犀牛
        * V2火箭发射车: 火箭炮, V2火箭
        * 地雷部署车: 雷车, 布雷车
        * 超重型坦克: 猛犸坦克, 猛犸, 天启坦克, 天启
        * 特斯拉坦克: 磁暴坦克, 磁能坦克, 电击坦克
        * 震荡坦克: 地震坦克, 震波坦克

        空中单位 (Air units)
        * 运输直升机: 运输机, 空运
        * 雌鹿直升机: 雌鹿攻击直升机, 雌鹿, 武装直升机
        * 黑鹰直升机: 黑鹰, 武装直升机
        * 雅克战机: 雅克, 雅克攻击机, 苏联战机
        * 长弓武装直升机: 长弓, 长弓直升机
        * 米格战机: 米格, 米格战斗机

        """)
        # USER_TEMPLATE = Template(r"""
        # Input variables (literal values inserted by caller):
        # user_data: $user_data
        # economy_data: $economy_data
        # production_data: $production_data
        #
        # * production queues: infantry=$inf_items, vehicle=$veh_items, building=$bld_items
        # * Map/other: include any map/actor data if provided.
        #
        # Available unit & building names and aliases (use only these names; if you propose other units, mark as "suggested:REASON"):
        #
        # 建筑单位 (Buildings)
        # * 发电厂: 电厂, 小电, 小电厂, 基础电厂
        # * 兵营: 兵工厂, 步兵营, 训练营
        # * 矿场: 采矿场, 矿, 精炼厂, 矿石精炼厂
        # * 战车工厂: 车间, 坦克厂, 坦克工厂, 载具工厂
        # * 雷达站: 雷达, 侦察站, 雷达圆顶
        # * 维修厂: 修理厂, 维修站, 修理站
        # * 储存罐: 井, 存钱罐, 储油罐, 资源储存罐
        # * 核电站: 核电厂, 大电, 大电厂, 高级电厂
        # * 空军基地: 机场, 飞机场, 航空站
        # * 科技中心: 高科技, 高科技中心, 研究中心, 实验室
        # * 军犬窝: 狗窝, 狗屋, 狗舍, 狗棚, 军犬训练所
        # * 火焰塔: 喷火塔, 喷火碉堡, 防御塔
        # * 特斯拉塔: 电塔, 特斯拉线圈, 高级防御塔
        # * 防空导弹: 防空塔, 防空, 山姆飞弹
        # * 铁幕装置: 铁幕, 铁幕防御系统
        # * 核弹发射井: 核弹, 导弹发射井, 核导弹井
        #
        # 步兵单位 (Infantry)
        # * 步兵: 枪兵, 步枪兵, 普通步兵
        # * 火箭兵: 火箭筒兵, 炮兵, 火箭筒, 导弹兵
        # * 工程师: 维修工程师, 技师
        # * 掷弹兵: 手雷兵, 手雷, 榴弹兵
        # * 军犬: 狗, 小狗, 攻击犬
        # * 喷火兵: 火焰兵, 火焰喷射兵
        # * 间谍: 特工, 潜伏者
        # * 磁暴步兵: 电击兵, 电兵, 突击兵
        #
        # 载具单位 (Vehicles)
        # * 采矿车: 矿车, 矿物收集车
        # * 装甲运输车: 装甲车, 运兵车
        # * 防空炮车: 防空车, 移动防空车
        # * 基地车: 建造车, 移动建设车
        # * 轻坦克: 轻坦, 轻型坦克, 轻型装甲车
        # * 重型坦克: 重坦, 犀牛坦克, 犀牛
        # * V2火箭发射车: 火箭炮, V2火箭
        # * 地雷部署车: 雷车, 布雷车
        # * 超重型坦克: 猛犸坦克, 猛犸, 天启坦克, 天启
        # * 特斯拉坦克: 磁暴坦克, 磁能坦克, 电击坦克
        # * 震荡坦克: 地震坦克, 震波坦克
        #
        # 空中单位 (Air units)
        # * 运输直升机: 运输机, 空运
        # * 雌鹿直升机: 雌鹿攻击直升机, 雌鹿, 武装直升机
        # * 黑鹰直升机: 黑鹰, 武装直升机
        # * 雅克战机: 雅克, 雅克攻击机, 苏联战机
        # * 长弓武装直升机: 长弓, 长弓直升机
        # * 米格战机: 米格, 米格战斗机
        #
        # Goal:
        # 1. Produce a situation assessment (`situation_assessment`).
        # 2. Interpret user intent (`user_intent_interpretation`).
        # 3. Provide a high-level recommended strategy (`recommended_strategy`).
        # 4. Return up to 6 priority actions (`priority_actions`), short and executable.
        # 5. Produce production recommendations (`production_recommendations`).
        # 6. Generate a detailed, ordered `action_plan` where each step includes `tool` (exact tool/function name), `args` (JSON-serializable), `preconditions`, `postconditions`, `success_check`, `on_failure` (retry/fallback/abort), and `estimated_time_s`. The Executor will call the listed tools in order.
        # 7. Provide `verification_checks` (post-execution assertions) and `assumptions`.
        # 8. Provide `reasoning` (detailed step-by-step rationale, ≤400 words).
        #
        # Response format (MUST output exactly this JSON object, nothing else):
        # {{
        #   "situation_assessment": "short Chinese summary (≤40 Chinese characters)",
        #   "user_intent_interpretation": "one-line Chinese",
        #   "recommended_strategy": "one-line Chinese",
        #   "priority_actions": ["short action 1", "short action 2", "..."],
        #   "production_recommendations": {{
        #     "infantry_units": ["unit_name","..."],
        #     "vehicle_units": ["unit_name","..."],
        #     "building_units": ["unit_name","..."]
        #   }},
        #   "action_plan": [
        #     {{
        #       "id": "A1",
        #       "description": "short Chinese instruction",
        #       "tool": "produce",
        #       "args": {{ "unit_type":"轻坦克","quantity":3 }},
        #       "preconditions": ["cash>=200","power>=10","兵营_exists"],
        #       "postconditions": ["3_轻坦克_in_queue"],
        #       "success_check": {{"type":"production_queue_contains","params":{{"unit_type":"轻坦克","min":1}}}},
        #       "on_failure": {{"retry":2,"fallback":["produce:轻坦克:1","produce:步兵:2"],"abort_if":"cash<50"}},
        #       "estimated_time_s": 30
        #     }}
        #   ],
        #   "verification_checks": [
        #     {"check_id":"V1","description":"power non-negative","assert":"power>=0"},
        #     {"check_id":"V2","description":"at least one recon unit near front","assert":"exists(unit_type=='军犬' or unit_type=='运输直升机')"}
        #   ],
        #   "assumptions": ["assumption 1","assumption 2"],
        #   "reasoning": "detailed Chinese reasoning ≤400 words"
        # }}
        #
        # Execution primitives mapping (verbs → tool function names & arg shapes). Use these exact names in `action_plan.tool`:
        # - produce -> produce(unit_type: str, quantity: int)
        # - move_units_by_location -> move_units_by_location(actor_ids: List[int], x:int, y:int, attack_move: bool=False)
        # - move_units -> move_units(actor_ids: List[int], x:int, y:int, attack_move: bool=False)
        # - move_units_by_path -> move_units_by_path(actor_ids: List[int], path: List[{{"x":int,"y":int}}])
        # - find_path -> find_path(actor_ids: List[int], dest_x:int, dest_y:int, method:str)
        # - attack_target -> attack_target(attacker_id:int, target_id:int)
        # - occupy_units -> occupy_units(occupier_ids: List[int], target_ids: List[int])
        # - can_produce -> can_produce(unit_type: str) -> bool
        # - ensure_can_produce_unit -> ensure_can_produce_unit(unit_name: str) -> bool
        # - query_actor -> query_actor(type: List[str], faction: str, range: str, restrain: List[dict]) -> List[Actor]
        # - get_unexplored_nearby_positions -> get_unexplored_nearby_positions(map_result, current_x:int, current_y:int, max_distance:int) -> [{"x":int,"y":int}]
        # - camera_move_to / move_camera_to -> camera_move_to(x:int, y:int) OR move_camera_to(actor_id:int)
        #
        # Now produce the JSON described above using the battlefield variables provided at invocation. Output JSON ONLY.
        # """)
        user_data_json = json.dumps(user_intent, ensure_ascii=False)
        economy_json = json.dumps(economy, ensure_ascii=False)
        production_json = json.dumps(production, ensure_ascii=False)
        user_prompt = USER_TEMPLATE.substitute(
            user_data=user_data_json,
            economy_data=economy_json,
            production_data=production_json,
            inf_items=production.get("infantry", {}).get("items", 0),
            veh_items=production.get("vehicle", {}).get("items", 0),
            bld_items=production.get("building", {}).get("items", 0),
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            print("🧠 GPT分析中...")
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
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
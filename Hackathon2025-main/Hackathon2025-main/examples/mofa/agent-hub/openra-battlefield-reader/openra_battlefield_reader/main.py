import json
import os
import sys
sys.path.append(os.getenv('OPENRA_PATH','.'))
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
from mofa.agent_build.base.base_agent import MofaAgent, run_agent
from OpenRA_Copilot_Library import GameAPI, Location, TargetsQueryParam
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
from battlefield_reader import BattlefieldReader


def _analyze_intent_type( text):
    """分析意图类型"""
    text_lower = text.lower()

    if any(word in text_lower for word in ['战车', '载具', '坦克', '吉普']):
        return "vehicle_focus"
    elif any(word in text_lower for word in ['步兵', '士兵', '人员']):
        return "infantry_focus"
    elif any(word in text_lower for word in ['建筑', '基地', '防御']):
        return "building_focus"
    elif any(word in text_lower for word in ['攻击', '进攻', '战斗']):
        return "attack_focus"
    elif any(word in text_lower for word in ['防守', '防御', '守护']):
        return "defense_focus"
    else:
        return "balanced_development"

def _extract_unit_preferences( text):
    """提取单位偏好"""
    preferences = []
    text_lower = text.lower()

    if any(word in text_lower for word in ['步兵', '士兵']):
        preferences.append("infantry")
    if any(word in text_lower for word in ['战车', '载具', '坦克']):
        preferences.append("vehicle")
    if any(word in text_lower for word in ['建筑', '基地']):
        preferences.append("building")

    return preferences

def _extract_strategy( text):
    """提取战略倾向"""
    text_lower = text.lower()

    if any(word in text_lower for word in ['多多', '大量', '疯狂', '拼命']):
        return "aggressive_production"
    elif any(word in text_lower for word in ['稳定', '正常', '保持']):
        return "stable_development"
    elif any(word in text_lower for word in ['快速', '速度', '急']):
        return "rapid_expansion"
    else:
        return "standard"


@run_agent
def run(agent: MofaAgent):
    # 0. 等待遥控器发送使能信号
    start_signal = agent.receive_parameter('battlefield-reader-signal')
    intent_data = {
        "raw_input": start_signal,
        "intent_type": _analyze_intent_type(start_signal),
        "priority_units": _extract_unit_preferences(start_signal),
        "strategy": _extract_strategy(start_signal)
    }

    with open("user_intent.json", 'w', encoding='utf-8') as f:
        json.dump(intent_data, f, ensure_ascii=False, indent=2)

    battlefield_reader = BattlefieldReader()
    battlefield_state = battlefield_reader.read_battlefield()
    if not battlefield_state:
        agent.send_output(agent_output_name='battlefield_reader_result', agent_result='❌ 战场读取失败，请检查游戏连接')
    else:
        agent.send_output(agent_output_name='battlefield_reader_result', agent_result=battlefield_state)



def main():
    # 创建 agent 实例
    agent = MofaAgent(agent_name='openra-battlefield-reader')

    run(agent=agent)

if __name__ == "__main__":
    main()

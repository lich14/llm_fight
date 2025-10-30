import os
import sys
sys.path.append(os.getenv('OPENRA_PATH','.'))
from mofa.agent_build.base.base_agent import MofaAgent, run_agent
from OpenRA_Copilot_Library import GameAPI, Location, TargetsQueryParam
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
from ai_analyzer import AIAnalyzer
from dotenv import load_dotenv

@run_agent
def run(agent: MofaAgent):
    # 0. 等待遥控器发送使能信号
    start_signal = agent.receive_parameter('battlefield-analyze-signal')
    load_dotenv('.env')
    if os.getenv('LLM_API_KEY',None) is not None:
        os.environ['OPENAI_API_KEY'] = os.getenv('LLM_API_KEY')
    API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")

    ai_analyzer = AIAnalyzer(API_KEY)
    file_path = 'battlefield_state.json'
    ai_analysis = ai_analyzer.analyze_situation()
    if not ai_analysis:
        agent.send_output(agent_output_name='battlefield_analyze_result', agent_result='❌ AI分析失败')
    else:
        strategy = ai_analysis.get('recommended_strategy', '未知策略')
        print('Ai 策略',strategy)
        agent.send_output(agent_output_name='battlefield_analyze_result', agent_result=ai_analysis)



def main():
    # 创建 agent 实例
    agent = MofaAgent(agent_name='openra-battlefield-analyze')

    run(agent=agent)

if __name__ == "__main__":
    main()

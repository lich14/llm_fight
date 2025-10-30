import os
import sys

from openra_execute.game_llm_executor import run_executor_with_plan

sys.path.append(os.getenv('OPENRA_PATH','.'))
from mofa.agent_build.base.base_agent import MofaAgent, run_agent
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
from dotenv import load_dotenv
from game_executor import GameExecutor
@run_agent
def run(agent: MofaAgent):
    execute_plan = agent.receive_parameter('battlefield-execute-signal')
    load_dotenv('.env')
    if os.getenv('LLM_API_KEY',None) is not None:
        os.environ['OPENAI_API_KEY'] = os.getenv('LLM_API_KEY')

    result = run_executor_with_plan(execute_plan)

    agent.send_output(agent_output_name='battlefield_execute_result', agent_result=result)



def main():
    # 创建 agent 实例
    agent = MofaAgent(agent_name='openra-execute-execute')
    run(agent=agent)

if __name__ == "__main__":
    main()

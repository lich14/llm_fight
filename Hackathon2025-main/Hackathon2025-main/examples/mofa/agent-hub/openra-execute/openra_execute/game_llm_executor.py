# run_executor_llm.py
import os
import json
import importlib
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

from openra_execute import game_tool
tools_schema_mod = game_tool  # schema 定义所在模块
tools_impl_mod = game_tool    # 工具实现所在模块

available_tools = game_tool.available_tools # 同一文件里既有 schema 也有实现

# EXECUTOR_SYSTEM_PROMPT = """You are the **Execution Orchestrator LLM** for an RTS game (Red Alert-like).
# You are given a single JSON `plan` that contains an ordered `action_plan` plus optional `verification_checks`.
# Your job is to **execute** the plan step by step by calling tools (function calling).
# You must not invent results—only decide which tool to call next and with what arguments.
# You will receive each tool’s result as a tool message; then decide the next tool call or finish.
#
# Execution algorithm (strict):
# # 1) Maintain a lightweight scratch state internally. Before each step, if needed, call `player_base_info_query` and/or `get_game_state` to refresh cash/power/visible units/queues.
# 2) For the current step:
#    a) Evaluate `preconditions`:
#       - Numeric forms like `cash>=100` use values from `player_base_info_query()`.
#       - `XYZ_exists` means at least one actor of type `XYZ` exists (use `query_actor([XYZ], "任意", "all", [])`).
#       - `visible(x,y)` use `visible_query(x,y)`.
#       If preconditions fail and the step is a production/build action, you MAY call `ensure_can_produce_unit` or `ensure_can_build_wait` to satisfy dependencies; then re-check once.
#    b) Call the specified `tool` with the given `args`.
#    c) Run `success_check`:
#       - `{"type":"production_queue_contains","params":{"unit_type":"步兵","min":1}}`:
#         Check production queues via `query_production_queue` over relevant queues. True if found ≥ min.
#       - `{"type":"exists_unit","params":{"unit_type":"步兵"}}`:
#         Use `query_actor`/`get_game_state` and return true if any visible unit matches.
#       If no `success_check`, treat as success when the tool returned OK.
#    d) If failed: obey `on_failure` strictly:
#       - `retry`: re-call the same tool up to N times.
#       - `fallback`: each entry can be a string like `produce:轻坦克:1` (map to tool name + positional args), or an inline action object `{ "tool":"produce","args":{"unit_type":"轻坦克","quantity":1} }`. Execute first successful fallback and then re-run the same `success_check`.
#       - `abort_if`: numeric condition (e.g., `cash<50`). If true, stop executing remaining steps and finish with failure.
# 3) After the last step (or abort), evaluate `verification_checks` if provided:
#    - For numeric assertions like `power>=0`, use `player_base_info_query()`.
#    - For `X_in_queue`, search all queues from `query_production_queue` and pass if any item name contains `X`.
#    - For `exists(unit_type=='军犬' or unit_type=='运输直升机')`, pass if any visible unit matches any listed type.
# 4) **Output** a final assistant message containing a single JSON object `execution_report` with:
#    - `step_results`: array of `{id, called_tool, args, success, result_summary, error}` in order.
#    - `verification_results`: array of `{check_id, ok, detail}`.
#    - `status`: `"success"` if all required steps succeeded and verifications passed, else `"partial"` or `"failed"`.
#    - `notes`: short text on assumptions/fallbacks taken.
#
# Hard rules:
# - Only use available tools; never fabricate tool outputs.
# - Treat `estimated_time_s` as metadata; do not wait.
# - Keep tool args JSON-serializable and match the tool schema.
# - If actor IDs are unknown, first call `query_actor(...)` to obtain them before movement/attack.
# - Be concise in `result_summary`; include key fields returned by the tool (IDs, counts, booleans).
# """
EXECUTOR_SYSTEM_PROMPT = """You are the **Execution Orchestrator LLM** for an RTS game (Red Alert-like).
You are given a single JSON `plan` that contains an ordered `action_plan` plus optional `verification_checks`.
Your job is to **execute** the plan step by step by calling tools (function calling).
You must not invent results—only decide which tool to call next and with what arguments.
You will receive each tool’s result as a tool message; then decide the next tool call or finish.

Hard rules:
- Only use available tools; never fabricate tool outputs.
- Treat `estimated_time_s` as metadata; do not wait.
- Keep tool args JSON-serializable and match the tool schema.
- If actor IDs are unknown, first call `query_actor(...)` to obtain them before movement/attack.
- Be concise in `result_summary`; include key fields returned by the tool (IDs, counts, booleans).
"""

def dispatch_tool_call(name: str, arguments_json: str) -> str:
    """把 LLM 的 tool call 路由到真实函数，并把结果序列化为字符串返回给模型。"""
    fn = getattr(tools_impl_mod, name, None)
    if not fn:
        return json.dumps({"error": f"tool `{name}` not found"})
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except Exception as e:
        return json.dumps({"error": f"invalid arguments json: {e}", "raw": arguments_json})
    try:
        # 支持 dict / list / 空参三种形态
        if isinstance(args, dict):
            result = fn(**args)
        elif isinstance(args, list):
            result = fn(*args)
        else:
            result = fn(args)
        # 统一包装
        return json.dumps({"ok": True, "data": result}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

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

def run_executor_with_plan(plan: Dict[str, Any], model: str = "gpt-4.1") -> Dict[str, Any]:
    game_tool.deploy_mcv_and_wait()
    client = create_openai_client()

    messages = [
        {"role": "system", "content": EXECUTOR_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps({"plan": plan}, ensure_ascii=False)
        }
    ]

    # 使用你在 mcp_server/tools.py 中声明的工具 schema
    tools = available_tools

    # 防御式循环：允许多轮 tool calls，直到模型输出最终报告（无 tool_calls）
    for _ in range(64):  # 上限，防止死循环
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.5
        )
        msg = resp.choices[0].message

        # 如果有 tool calls，就全部执行并把结果逐个回填
        if msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls})

            for tc in msg.tool_calls:
                tool_name = tc.function.name
                tool_args = tc.function.arguments
                tool_result = dispatch_tool_call(tool_name, tool_args)

                # 回填工具结果
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tool_name,
                    "content": tool_result
                })
                print({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tool_name,
                    "content": tool_result
                })
            # 继续下一轮
            continue

        # 没有 tool_calls，则认为模型给出了最终文本（应为 execution_report JSON）
        final_text = msg.content or ""
        try:
            report = json.loads(final_text)
        except Exception:
            # 如果模型没按约定输出 JSON，也返回原文方便调试
            report = {"raw_output": final_text}
        return report

    # 超过循环上限还没结束
    return {"error": "executor exceeded max rounds"}

if __name__ == "__main__":
    # 这里放你提供的示例 plan（可直接替换）
    plan ={
  "situation_assessment": "现金充足，电力正常，未部署MCV。",
  "user_intent_interpretation": "用户希望建造战争工厂。",
  "recommended_strategy": "优先部署MCV以扩展基地。",
  "priority_actions": [
    "部署MCV",
    "建造战争工厂"
  ],
  "production_recommendations": {
    "infantry_units": [],
    "vehicle_units": [],
    "building_units": [
      "战争工厂"
    ]
  },
  "action_plan": [
    {
      "id": "A1",
      "description": "部署移动建设车以扩展基地。",
      "tool": "produce",
      "args": {
        "unit_type": "基地车",
        "quantity": 1
      },
      "preconditions": [
        "cash>=1000"
      ],
      "postconditions": [
        "基地车_in_queue"
      ],
      "success_check": {
        "type": "production_queue_contains",
        "params": {
          "unit_type": "基地车",
          "min": 1
        }
      },
      "on_failure": {
        "retry": 2,
        "fallback": [],
        "abort_if": "cash<1000"
      },
      "estimated_time_s": 30
    },
    {
      "id": "A2",
      "description": "部署MCV以便建造建筑。",
      "tool": "move_units",
      "args": {
        "actor_ids": [
          1
        ],
        "x": 0,
        "y": 0
      },
      "preconditions": [
        "基地车_in_queue"
      ],
      "postconditions": [
        "MCV_deployed"
      ],
      "success_check": {
        "type": "unit_deployed",
        "params": {
          "unit_type": "基地车"
        }
      },
      "on_failure": {
        "retry": 1,
        "fallback": [],
        "abort_if": "true"
      },
      "estimated_time_s": 20
    },
    {
      "id": "A3",
      "description": "建造战争工厂以增强生产能力。",
      "tool": "produce",
      "args": {
        "unit_type": "战车工厂",
        "quantity": 1
      },
      "preconditions": [
        "MCV_deployed",
        "cash>=5000",
        "power>=10"
      ],
      "postconditions": [
        "战车工厂_in_queue"
      ],
      "success_check": {
        "type": "production_queue_contains",
        "params": {
          "unit_type": "战车工厂",
          "min": 1
        }
      },
      "on_failure": {
        "retry": 1,
        "fallback": [],
        "abort_if": "cash<5000"
      },
      "estimated_time_s": 60
    }
  ],
  "verification_checks": [
    {
      "check_id": "V1",
      "description": "确保电力正常",
      "assert": "power>=0"
    }
  ],
  "assumptions": [
    "MCV的初始位置在(0,0)",
    "现金和电力足够进行所有操作"
  ],
  "reasoning": "当前经济状况良好，现金和电力充足。用户希望建造战争工厂，但必须首先部署MCV。计划首先生产基地车，然后移动MCV到适当位置，最后建造战争工厂。每个步骤都考虑了资源和前置条件，以确保顺利执行。"
}

    out = run_executor_with_plan(plan)
    print(json.dumps(out, ensure_ascii=False, indent=2))

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Central Brain for OpenRA
- LLM 决策中枢：所有“建造/生产/移动/攻击”均由大模型输出的动作列表决定。
- 目标：资金>=100000 & 尽可能探索全图（由 LLM 自主决定探索方式）。
- 游戏控制层仅负责：编码观测 -> 请求LLM -> 解析JSON动作 -> 逐条执行 -> 回传反馈。

准备：
  - 你已有的 OpenRA_Copilot_Library / GameAPI (中文)
  - 你提供的 StreamingAgent（已内嵌于本文件，可替换API KEY/模型）
"""

import sys
import time
import json
import math
from typing import List, Dict, Any, Tuple, Optional

# === 引入 OpenRA 控制库 ===
sys.path.append('examples/mofa/examples/openra-controller')
from OpenRA_Copilot_Library.game_api import GameAPI
from OpenRA_Copilot_Library.models import TargetsQueryParam

# === 你给的 StreamingAgent（原样复用，略微精简） ===
import requests
from tenacity import retry, wait_random_exponential, stop_after_attempt


class StreamingAgent:

    def __init__(
            self,
            role: str,
            api_key: str = "f61ov1gbo76awnl3z4rz1a8ltiykrg6c",
            model: str = "llama-3.1-405b-instruct",
            api_base: str = "https://autobak.zaiwen.top/api/v1/chat/completions"
    ):
        self.role = role
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    @retry(wait=wait_random_exponential(min=1, max=30),
           stop=stop_after_attempt(5),
           reraise=True)
    def chat(self, user_message: str) -> str:
        payload = {
            "messages": [{
                "role": "system",
                "content": self.role
            }, {
                "role": "user",
                "content": user_message
            }],
            "model":
            self.model,
            "stream":
            True
        }
        full = ""
        while True:
            try:
                with requests.post(self.api_base,
                                   headers=self.headers,
                                   json=payload,
                                   stream=True) as r:
                    r.raise_for_status()
                    for line in r.iter_lines(decode_unicode=True):
                        if not line: continue
                        if not line.startswith("data: "): continue
                        data = line[6:]
                        if data == "[DONE]": break
                        try:
                            chunk = json.loads(data)
                            if "choices" in chunk and chunk["choices"]:
                                full += chunk["choices"][0].get(
                                    "delta", {}).get("content", "")
                        except Exception:
                            continue
            except requests.exceptions.RequestException:
                continue
            if full == "null": full = ""
            if full: break
        return full


# ======= 行为空间定义（唯一真理 = LLM 输出） =======
"""
LLM 必须输出严格 JSON（无前后解释文字），形如：

{
  "build": [  // 建筑或单位生产队列（由LLM判断）
    {"name_or_code": "电厂", "count": 1, "is_building": true, "why": "电力不足"},
    {"name_or_code": "harv", "count": 1, "is_building": false, "why": "加快采集"}
  ],
  "unit_commands": [  // 对每个我方单位发命令
    {"actor_id": 123, "action": "move", "target": {"x": 80, "y": 120}},
    {"actor_id": 124, "action": "attack", "target_id": 999},
    {"actor_id": 125, "action": "hold"}  // 不动也可省略
  ],
  "notes": "简短策略思路或后续规划（可选）"
}

- name_or_code: 建筑可用中文名(电厂/矿场/战车工厂/雷达/建造厂...)；单位用代号/中文（harv/jeep/apc/ftrk/mcv/采矿车/吉普车...）
- is_building: true=建造建筑；false=生产单位
- action: "move" | "attack" | "hold" | "stop"（如你的 GameAPI 还支持"attack_move"/"patrol"等，可由LLM使用，见执行器里兼容）
- target: {"x": int, "y": int}   # 地图坐标
- target_id: 敌方或中立单位/建筑 id
"""

SYSTEM_PROMPT = """
你是 OpenRA 的唯一决策中枢。你的行为只有一种：依据观测 state 生成一次性动作列表（JSON）。
你的目标：
1) 尽量提高资金获得的效率，同时快速花掉资金建造战斗兵种打击敌方部队和区域；
2) 覆盖性探索整张地图，逐步扩大可见区域；
3) 避免电力赤字（Power 使用量不超过提供量），保持生产节奏。
4) 如果发现敌军，集中火力进行打击

硬性规则（重要，逐条遵守）：
- 只输出 **有效 JSON**，键必须包含：build, unit_commands, notes。
- 绝不能复述或抄袭我给的示例内容；示例仅说明**格式**，不是建议。
- 只根据“state”决策。如果某单位/建筑不在可生产列表或不可生产，你可以选择不生产或先建前置科技。
- 每次循环最多下达 64 条 unit_commands，避免过载。
- unit_commands 只允许操作我方单位（state.my_units 里出现的 actor_id）。
- 攻击与锁定目标仅限可见敌方（state.enemies 里的 id）。
- 若无必要动作，可返回空列表（例如：[]）。

允许动作（动作空间）：
- 建造/生产：name_or_code(中文建筑名或单位代号)、count、is_building(True=建筑, False=单位)
- 单位指令：
  - move: 移动单位到某一个目标坐标 target{x,y}
  - attack: 设定单位需要攻击的可见敌方目标的列表 [target_id]
  - attack_move: 移动单位到某一个目标坐标 target{x,y}，同时单位在行进的途中可以攻击

策略提醒（可选采纳）：
- 若采集偏弱：优先补“矿场/采矿车”，一个矿场可以配多个采矿车。
- 若电力将不足：优先“电厂”。
- 若需要解锁车辆生产：补“战车工厂/车间”。
- 高级的车辆生产需要建造更高级的建筑物，如雷达，维修厂，核电站，科技中心
- 探索建议：把 jeeps/apc/ftrk 分派到不同扇区或网格点，逐步扫图。
- 战斗建议：遇到威胁时，支援单位可 attack_move 到威胁附近或 attack 全部的敌方单位列表。

输出格式（schema，仅作**字段定义**，不要复制任何示例值）：
{
  "build": [
    {"name_or_code":"<string>", "count":<int>, "is_building":<bool>, "why":"<string-optional>"}
  ],
  "unit_commands": [
    {"actor_id":<int>, "action":"move|attack|attack_move",
     "target":{"x":<int>,"y":<int>}?, "target_id":[<int>]?}
  ],
  "notes":"<string-optional>"
}

绝不要输出 JSON 之外的文字。
注意参考reflection里面的内容。
"""


# ======= 观测编码 =======
def encode_state(api: GameAPI, cycle: int) -> Dict[str, Any]:
    info = api.player_base_info_query()

    # 我方全部
    mine = api.query_actor(TargetsQueryParam(faction='自己')) or []
    my_buildings, my_units = [], []
    for a in mine:
        item = {
            "id": getattr(a, "actor_id", None),
            "type": getattr(a, "type", ""),
            "hp": getattr(a, "hppercent", None),
            "pos": {
                "x": getattr(getattr(a, "position", None), "x", None),
                "y": getattr(getattr(a, "position", None), "y", None)
            }
        }
        # 粗分
        if item["type"] in ['电厂', '矿场', '战车工厂', '雷达', '维修厂', '核电站', '科技中心']:
            my_buildings.append(item)
        else:
            my_units.append(item)

    # 敌方（视野内）
    enemies = api.query_actor(TargetsQueryParam(faction='敌人')) or []
    enemy_list = [{
        "id": getattr(e, "actor_id", None),
        "type": getattr(e, "type", ""),
        "hp": getattr(e, "hppercent", None),
        "pos": {
            "x": getattr(getattr(e, "position", None), "x", None),
            "y": getattr(getattr(e, "position", None), "y", None)
        }
    } for e in enemies]

    # 可生产性（常用单位）
    def safe_can(code: str) -> bool:
        try:
            return api.can_produce(code)
        except Exception:
            return False

    tech = {
        c: safe_can(c)
        for c in [
            "apc", "ftrk", "3tnk", "4tnk", "v2rl", "采矿车", '电厂', '矿场', '战车工厂',
            '雷达', '维修厂', '核电站', '科技中心'
        ]
    }

    # 粗略探索率（若有更准API可替换）
    explored_ratio = 0.2  # 占位；可按你实际API替换

    return {
        "cycle": cycle,
        "money": info.Cash + info.Resources,
        "power": {
            "unused": info.Power,
            "provided": info.PowerProvided
        },
        "my_buildings": my_buildings,
        "my_units": my_units,
        "enemies": enemy_list,
        "can_produce": tech,
        "goals": {
            "target_money": 100000,
            "explore_map": True
        },
        "hints": {
            "map_size": {
                "w": 100,
                "h": 100
            },
            "fast_units": [
                "jeep", "apc", "ftrk", "吉普车", "装甲运输车", "防空车", "3tnk", "4tnk",
                "v2rl"
            ]
        }
    }


# ======= 动作执行器（严格执行 LLM 指令） =======
def exec_build_plan(api: GameAPI, build_list: List[Dict[str, Any]]):
    for item in build_list or []:
        name = item.get("name_or_code")
        cnt = max(1, int(item.get("count", 1)))
        is_building = bool(item.get("is_building", True))
        why = item.get("why", "")
        if not name:
            print("[BUILD] 跳过：无 name_or_code")
            continue
        print(f"[BUILD] {name} x{cnt} | is_building={is_building} | why={why}")
        for i in range(cnt):
            try:
                wait_id = api.produce(name, 1, is_building)
                if wait_id: api.wait(wait_id, 10 if is_building else 6)
            except Exception as e:
                print(f"[BUILD] 执行失败: {e}")


def _try_calls(calls: list):
    for f in calls:
        try:
            f()
            return True
        except Exception as e:
            print(f"函数 {f.__name__} 出错：{e}")
            continue
    return False


def exec_unit_commands(api: GameAPI,
                       cmds: List[Dict[str, Any]],
                       max_per_tick=64):
    n = 0
    for c in cmds or []:
        if n >= max_per_tick:
            print(f"[UNIT] 超过每轮上限 {max_per_tick}，剩余忽略")
            break
        actor_id = c.get("actor_id")
        action = (c.get("action") or "").lower()
        if not actor_id or not action:
            continue

        if action == "move":
            t = c.get("target") or {}
            x, y = t.get("x"), t.get("y")
            if x is None or y is None: continue
            ok = _try_calls([
                lambda: api.move_units_by_location_and_id(
                    [actor_id], location={
                        'x': x,
                        'y': y
                    }, attack_move=True)
            ])
            print(f"[UNIT] move {actor_id} -> ({x},{y}) | ok={ok}")
            n += 1

        elif action == "attack":
            tid = c.get("target_id")
            if not tid: continue
            ok = _try_calls([
                lambda: api.attack_target_id(actor_id, tid),
            ])
            print(f"[UNIT] attack {actor_id} -> target_id={tid} | ok={ok}")
            n += 1

        elif action == "attack_move":
            t = c.get("target") or {}
            x, y = t.get("x"), t.get("y")
            if x is None or y is None: continue
            ok = _try_calls([
                lambda: api.move_units_by_location_and_id(
                    [actor_id], location={
                        'x': x,
                        'y': y
                    }, attack_move=True)
            ])
            print(f"[UNIT] attack_move {actor_id} -> ({x},{y}) | ok={ok}")
            n += 1

        elif action in ["hold", "stop"]:
            ok = _try_calls([
                lambda: api.stop(actor_id),
                lambda: api.hold_position(actor_id),
            ])
            print(f"[UNIT] {action} {actor_id} | ok={ok}")
            n += 1

        else:
            print(f"[UNIT] 未识别动作: {action}（忽略）")


# ======= LLM 调度循环 =======
class LLMCentralBrain:

    def __init__(self,
                 api: GameAPI,
                 agent: StreamingAgent,
                 target_money: int = 100000,
                 max_cycles: int = 200,
                 seconds_per_tick: float = 2.5):
        self.api = api
        self.agent = agent
        self.target_money = target_money
        self.max_cycles = max_cycles
        self.seconds_per_tick = seconds_per_tick
        api.deploy_mcv_and_wait(5)

    def loop(self):
        print("=" * 68)
        print("[*] LLM Central Brain 启动（LLM 全权决策）")
        print("=" * 68)

        # 如果未部署 MCV，交给 LLM 决策；我们不强制部署
        for cycle in range(1, self.max_cycles + 1):
            # 1) 观测编码
            state = encode_state(self.api, cycle)
            money = state["money"]
            print(
                f"\n--- Cycle {cycle}/{self.max_cycles} | Money ${money} | Power {state['power']['unused']}/{state['power']['provided']} ---"
            )

            if money >= self.target_money:
                print(f"✓ 达成资金目标：${money} ≥ ${self.target_money}")
                break

            def build_llm_prompt(state: dict) -> str:
                # 行为“可做什么”的目录（帮助模型理解边界，不是要它照抄）
                catalog = {
                    "buildings": [
                        "电厂", "矿场", "战车工厂", "车间", "雷达", "建造厂", "维修厂", "核电站",
                        "科技中心"
                    ],
                    "vehicle_codes": [
                        "harv", "jeep", "apc", "ftrk", "mcv", "truk", "mvly",
                        "3tnk", "4tnk", "v2rl", "采矿车"
                    ],
                    "unit_actions": ["move", "attack", "attack_move"]
                }

                # 多样化 few-shot 输出（只示格式，用完全不同的值，且明确禁止抄）
                examples = [{
                    "build": [{
                        "name_or_code": "矿场",
                        "count": 1,
                        "is_building": True
                    }, {
                        "name_or_code": "采矿车",
                        "count": 2,
                        "is_building": False
                    }],
                    "unit_commands": [{
                        "actor_id": 201,
                        "action": "move",
                        "target": {
                            "x": 40,
                            "y": 20
                        }
                    }, {
                        "actor_id": 205,
                        "action": "attack_move",
                        "target": {
                            "x": 20,
                            "y": 80
                        }
                    }],
                    "notes":
                    "补经济并推进右下角探索"
                }, {
                    "build": [{
                        "name_or_code": "战车工厂",
                        "count": 1,
                        "is_building": True
                    }, {
                        "name_or_code": "ftrk",
                        "count": 1,
                        "is_building": False
                    }],
                    "unit_commands": [{
                        "actor_id": 310,
                        "action": "attack",
                        "target_id": [911]
                    }],
                    "notes":
                    "解锁车辆生产，同时在上方扇区巡逻"
                }, {
                    "build": [],
                    "unit_commands": [{
                        "actor_id": 401,
                        "action": "attack",
                        "target_id": [911]
                    }, {
                        "actor_id": 402,
                        "action": "move",
                        "target": {
                            "x": 16,
                            "y": 16
                        }
                    }],
                    "notes":
                    "局部火力压制+补一处盲区"
                }]

                # 输出要求：必须生成“新内容”，禁止抄 examples 值
                output_instruction = (
                    "Return ONLY a JSON object that follows 'schema'. "
                    "Do NOT copy values from 'examples'. "
                    "Choose names, counts, coordinates, and ids based solely on the given 'state'."
                )

                payload = {
                    "state":
                    state,  # ← 真实观测
                    "schema": {  # ← 只是字段定义，不带具体值
                        "build": [{
                            "name_or_code": "<string>",
                            "count": "<int>",
                            "is_building": "<bool>",
                            "why": "<string-optional>"
                        }],
                        "unit_commands": [{
                            "actor_id": "<int>",
                            "action": "move|attack|attack_move",
                            "target": {
                                "x": "<int>",
                                "y": "<int>"
                            },
                            "target_id": "[<int>]"
                        }],
                        "notes":
                        "<string-optional>"
                    },
                    "catalog":
                    catalog,
                    "constraints": {
                        "max_unit_commands_per_tick": 64,
                        "must_not_target_allies": True,
                        "attack_targets_must_be_visible_enemies": True,
                        "avoid_power_deficit": True,
                        "primary_goal_money": 100000,
                        "explore_whole_map": True
                    },
                    "examples":
                    examples,  # ← 多样化、非电厂-only
                    "reflection": [
                        "注意整个地图的范围是(0,0)到(100,100)", "探索地图前要先建雷达",
                        "升级科技需要建造维修厂，核电站，科技中心", "攻击单位推荐升级科技后建造4tnk",
                        "探索地图发现敌方位置后要集中火力消灭敌方的攻击单位，之后消灭敌方的建造单位",
                        "要布置兵力保护我方重要建筑物", "进攻路线可以有很多，注意使用包夹策略"
                    ],
                    "output_instruction":
                    output_instruction
                }
                return json.dumps(payload, ensure_ascii=False)

            # 2) 向 LLM 提供观测，索取动作
            prompt = build_llm_prompt(state)

            print(prompt)
            raw = self.agent.chat(prompt)
            print(raw)

            # 3) 解析 & 执行动作（严格执行）
            plan = self._parse_llm_json(raw)
            print(plan)
            print('=' * 30)
            if not plan:
                print("[LLM] JSON 解析失败，本轮跳过执行。")
            else:
                build_list = plan.get("build", [])
                unit_cmds = plan.get("unit_commands", [])
                exec_build_plan(self.api, build_list)
                exec_unit_commands(self.api, unit_cmds, max_per_tick=64)

                # 4) 简要反馈（非强制）
                try:
                    new_money = self.api.player_base_info_query(
                    ).Cash + self.api.player_base_info_query().Resources
                    feedback = {
                        "prev_money": money,
                        "new_money": new_money,
                        "delta_money": new_money - money,
                        "cycle": cycle
                    }
                    print(f"[FEEDBACK] {feedback}")
                except Exception:
                    pass

            time.sleep(self.seconds_per_tick)

        print("\n[*] 循环结束。")

    @staticmethod
    def _parse_llm_json(raw: str) -> Optional[Dict[str, Any]]:
        try:
            s, e = raw.find("{"), raw.rfind("}")
            if s >= 0 and e >= s:
                obj = json.loads(raw[s:e + 1])
                # 基本字段容错
                if "build" not in obj: obj["build"] = []
                if "unit_commands" not in obj: obj["unit_commands"] = []
                return obj
        except Exception as ex:
            print("[PARSE] 失败：", ex)
        return None


# ======= 运行入口 =======
def main():
    # 你可以按需替换 KEY/模型
    agent = StreamingAgent(role=SYSTEM_PROMPT,
                           api_key="f61ov1gbo76awnl3z4rz1a8ltiykrg6c",
                           model="gemini-1.5-flash")

    api = GameAPI('localhost', 7445, 'zh')

    print("准备在 Skirmish 局内运行。按回车开始（建议 Tech Level=Unrestricted，初始现金充足）。")
    input()

    brain = LLMCentralBrain(api,
                            agent,
                            target_money=100000,
                            max_cycles=240,
                            seconds_per_tick=2.5)
    brain.loop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"[错误] 程序异常: {e}")
        import traceback
        traceback.print_exc()

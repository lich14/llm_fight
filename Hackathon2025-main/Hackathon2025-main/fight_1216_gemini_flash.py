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

import sys,os
import time
import json
import math
import datetime
from typing import List, Dict, Any, Tuple, Optional, Set

# === 引入 OpenRA 控制库 ===
current_dir = os.path.dirname(os.path.abspath(__file__))
library_path = os.path.join(current_dir, 'examples', 'mofa', 'examples', 'openra-controller')
sys.path.insert(0, library_path)

from OpenRA_Copilot_Library.game_api import GameAPI
from OpenRA_Copilot_Library.models import TargetsQueryParam

# === 单位/建筑价格表 ===
UNIT_PRICES = {
    # 建筑
    "电厂": 150, "powr": 150,
    "核电站": 250, "apwr": 250,
    "矿场": 700, "proc": 700,
    "战车工厂": 1000, "weap": 1000,
    "兵营": 250, "barr": 250,
    "雷达": 250, "dome": 250, "雷达站": 250,
    "维修厂": 600, "fix": 600,
    "科技中心": 750, "stek": 750,
    "机场": 200, "afld": 200,
    "建造厂": 2500, "fact": 2500,
    # 防御建筑
    "火焰塔": 300, "ftur": 300,
    "特斯拉塔": 600, "tsla": 600,
    "防空导弹": 350, "sam": 350,
    # 车辆
    "采矿车": 1400, "harv": 1400,
    "防空车": 300, "ftrk": 300,
    "重型坦克": 575, "3tnk": 575,
    "猛犸坦克": 500, "4tnk": 500,
    "V2火箭发射车": 450, "v2rl": 450,
    "吉普车": 400, "jeep": 400,
    "装甲运输车": 700, "apc": 700,
    "建造车": 2500, "mcv": 2500,
    "运输卡车": 500, "truk": 500,
    # 步兵
    "步兵": 50, "e1": 50,
    "火箭兵": 5, "e3": 5,
    # 飞机
    "雅克战机": 675, "yak": 675,
    "米格战机": 800, "mig": 800,
}

# === 你给的 StreamingAgent（原样复用，略微精简） ===
import requests
from tenacity import retry, wait_random_exponential, stop_after_attempt


class StreamingAgent:

    def __init__(
        self,
        role: str,
        api_key: str = "f61ov1gbo76awnl3z4rz1a8ltiykrg6c",
        model: str = "llama-3.1-405b-instruct",
        api_base: str = "https://back.zaiwenai.com/api/v1/ai/chat/completions"
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
                # 设置timeout: (连接超时30秒, 读取超时120秒)
                with requests.post(self.api_base,
                                   headers=self.headers,
                                   json=payload,
                                   stream=True,
                                   timeout=(30, 120)) as r:
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

【状态说明】
每轮观测包含：
- cycle（回合数）、money（资金）、power（电力使用/提供）
- my_buildings（我方重要建筑：矿场、工厂、科技建筑等）
- combat_units（我方战斗单位：坦克、防空车、建造厂等，包含id/type/hp/pos）
- harvesters（采矿车统计：总数count、平均血量avg_hp、受损列表damaged[]）
- power_buildings（电厂统计：总数count、总发电量total_power、受损列表damaged[]）
- enemies（可见敌军，包含id/type/hp/pos）
- can_produce（当前可生产列表）

注意：为优化性能，采矿车和电厂已汇总统计，只有受损单位会列出详细信息（id/hp/pos）。

【目标】
1) 尽量提高资金获得的效率，同时快速花掉资金建造战斗兵种打击敌方部队和区域；
2) 覆盖性探索整张地图，逐步扩大可见区域；
3) 避免电力赤字（Power 使用量不超过提供量），保持生产节奏。
4) 如果发现敌军，集中火力进行打击
5) 歼灭所有的敌方目标

硬性规则（重要，逐条遵守）：
- 只输出 **有效 JSON**，键必须包含：build, unit_commands, notes。
- 绝不能复述或抄袭我给的示例内容；示例仅说明**格式**，不是建议。
- 只根据"state"决策。如果某单位/建筑不在可生产列表或不可生产，你可以选择不生产或先建前置科技。
- 每次循环最多下达 40 条 unit_commands，避免过载和JSON截断。
- unit_commands 只允许操作我方战斗单位（state.combat_units 里的 actor_id）。
- 攻击与锁定目标仅限可见敌方（state.enemies 里的 id）。
- 若无必要动作，可返回空列表（例如：[]）。

允许动作（动作空间）：
- 建造/生产：name_or_code(中文建筑名或单位代号)、count、is_building(True=建筑, False=单位)
- 单位指令：
  - move: 移动单位到某一个目标坐标 target{x,y}
  - attack: 设定单位需要攻击的可见敌方目标，注意只能设定一个攻击目标 [target_id]
  - attack_move: 移动单位到某一个目标坐标 target{x,y}，同时单位在行进的途中可以攻击

策略提醒（可选采纳）：
- 若采集偏弱：优先补“矿场/采矿车”，一个矿场可以配多个采矿车，但是数量最好在三以下。
- 若电力将不足：优先“电厂”。
- 若需要解锁车辆生产：补“战车工厂/车间”。
- 高级的车辆生产需要建造更高级的建筑物，如雷达，维修厂，核电站，科技中心
- 探索建议：把 jeeps/apc/ftrk 分派到不同扇区或网格点，逐步扫图。
- 战斗建议：遇到威胁时，支援单位可 attack_move 到威胁附近。

输出格式（schema，仅作**字段定义**，不要复制任何示例值）：

#####Action#####
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


# ======= 观测编码（优化版：减少冗余信息） =======
def encode_state(api: GameAPI, cycle: int) -> Dict[str, Any]:
    info = api.player_base_info_query()

    # 我方全部
    mine = api.query_actor(TargetsQueryParam(faction='自己')) or []
    my_buildings = []
    combat_units = []  # 战斗单位
    harvesters_summary = {"count": 0, "avg_hp": 0, "damaged": []}  # 采矿车汇总
    power_buildings = {"count": 0, "total_power": 0, "damaged": []}  # 电厂汇总
    
    harv_count = 0
    harv_total_hp = 0
    power_count = 0
    
    for a in mine:
        actor_id = getattr(a, "actor_id", None)
        atype = getattr(a, "type", "")
        hp = getattr(a, "hppercent", None)
        pos = {
            "x": getattr(getattr(a, "position", None), "x", None),
            "y": getattr(getattr(a, "position", None), "y", None)
        }
        
        # 电厂：只统计数量和总发电量，受损的单独列出
        if atype == '发电厂':
            power_count += 1
            if hp and hp < 80:
                power_buildings["damaged"].append({"id": actor_id, "hp": hp, "pos": pos})
            continue
        
        # 采矿车：只统计数量和平均血量，受损的单独列出
        if atype == '采矿车':
            harv_count += 1
            if hp:
                harv_total_hp += hp
            if hp and hp < 80:
                harvesters_summary["damaged"].append({"id": actor_id, "hp": hp, "pos": pos})
            continue
        
        # 其他建筑：保留完整信息
        if atype in ['矿场', '战车工厂', '雷达', '维修厂', '核电站', '科技中心', '建造厂', '雷达站']:
            my_buildings.append({
                "id": actor_id,
                "type": atype,
                "hp": hp,
                "pos": pos
            })
        # 战斗单位：保留完整信息
        else:
            combat_units.append({
                "id": actor_id,
                "type": atype,
                "hp": hp,
                "pos": pos
            })
    
    # 计算采矿车平均血量
    harvesters_summary["count"] = harv_count
    harvesters_summary["avg_hp"] = int(harv_total_hp / harv_count) if harv_count > 0 else 0
    
    # 电厂统计
    power_buildings["count"] = power_count
    power_buildings["total_power"] = info.PowerProvided

    # 敌方（视野内）- 保留完整信息
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

    return {
        "cycle": cycle,
        "money": info.Cash + info.Resources,  # 总资金 = 现金 + 资源
        "power": {
            "unused": info.Power,
            "provided": info.PowerProvided
        },
        "my_buildings": my_buildings,
        "combat_units": combat_units,  # 只包含战斗单位
        "harvesters": harvesters_summary,  # 采矿车汇总统计
        "power_buildings": power_buildings,  # 电厂汇总统计
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
def exec_build_plan(api: GameAPI, build_list: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    执行建造计划
    返回：(连接错误次数, 总建造成本)
    """
    connection_errors = 0
    total_cost = 0
    for item in build_list or []:
        name = item.get("name_or_code")
        cnt = max(1, int(item.get("count", 1)))
        is_building = bool(item.get("is_building", True))
        why = item.get("why", "")
        if not name:
            print("[BUILD] 跳过：无 name_or_code")
            continue
        
        # 查询单价
        unit_price = UNIT_PRICES.get(name, 0)
        if unit_price == 0:
            print(f"[BUILD] 警告：未找到 {name} 的价格，使用默认值0")
        
        item_cost = unit_price * cnt
        total_cost += item_cost
        
        print(f"[BUILD] {name} x{cnt} | is_building={is_building} | 单价=${unit_price} | 小计=${item_cost} | why={why}")
        for i in range(cnt):
            try:
                wait_id = api.produce(name, 1, is_building)
                if wait_id: api.wait(wait_id, 10 if is_building else 6)
            except Exception as e:
                error_msg = str(e)
                print(f"[BUILD] 执行失败: {error_msg}")
                # 检测是否是连接错误
                if "CONNECTION_ERROR" in error_msg or "10061" in error_msg or "连接" in error_msg:
                    connection_errors += 1
                    # 如果连续多次连接失败，提前返回
                    if connection_errors >= 3:
                        print(f"[BUILD] 检测到连续{connection_errors}次连接错误，停止执行建造")
                        return (connection_errors, total_cost)
    return (connection_errors, total_cost)


def _try_calls(calls: list) -> tuple:
    """
    尝试执行调用列表
    返回：(是否成功, 是否是连接错误)
    """
    for f in calls:
        try:
            f()
            return (True, False)
        except Exception as e:
            error_msg = str(e)
            print(f"函数 {f.__name__} 出错：{error_msg}")
            # 检测连接错误
            is_connection_error = "CONNECTION_ERROR" in error_msg or "10061" in error_msg or "连接" in error_msg
            if is_connection_error:
                return (False, True)
            continue
    return (False, False)


def exec_unit_commands(api: GameAPI,
                       cmds: List[Dict[str, Any]],
                       max_per_tick=64) -> int:
    """
    执行单位命令
    返回：连接错误次数
    """
    n = 0
    connection_errors = 0
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
            ok, is_conn_err = _try_calls([
                lambda: api.move_units_by_location_and_id(
                    [actor_id], location={
                        'x': x,
                        'y': y
                    }, attack_move=True)
            ])
            if is_conn_err: connection_errors += 1
            print(f"[UNIT] move {actor_id} -> ({x},{y}) | ok={ok}")
            n += 1
            if connection_errors >= 3:
                print(f"[UNIT] 检测到{connection_errors}次连接错误，停止执行命令")
                return connection_errors

        elif action == "attack":
            tid = c.get("target_id")
            if not tid: continue
            ok, is_conn_err = _try_calls([
                lambda: api.attack_target_id(actor_id, tid),
            ])
            if is_conn_err: connection_errors += 1
            print(f"[UNIT] attack {actor_id} -> target_id={tid} | ok={ok}")
            n += 1
            if connection_errors >= 3:
                print(f"[UNIT] 检测到{connection_errors}次连接错误，停止执行命令")
                return connection_errors

        elif action == "attack_move":
            t = c.get("target") or {}
            x, y = t.get("x"), t.get("y")
            if x is None or y is None: continue
            ok, is_conn_err = _try_calls([
                lambda: api.move_units_by_location_and_id(
                    [actor_id], location={
                        'x': x,
                        'y': y
                    }, attack_move=True)
            ])
            if is_conn_err: connection_errors += 1
            print(f"[UNIT] attack_move {actor_id} -> ({x},{y}) | ok={ok}")
            n += 1
            if connection_errors >= 3:
                print(f"[UNIT] 检测到{connection_errors}次连接错误，停止执行命令")
                return connection_errors

        elif action in ["hold", "stop"]:
            ok, is_conn_err = _try_calls([
                lambda: api.stop(actor_id),
                lambda: api.hold_position(actor_id),
            ])
            if is_conn_err: connection_errors += 1
            print(f"[UNIT] {action} {actor_id} | ok={ok}")
            n += 1
            if connection_errors >= 3:
                print(f"[UNIT] 检测到{connection_errors}次连接错误，停止执行命令")
                return connection_errors

        else:
            print(f"[UNIT] 未识别动作: {action}（忽略）")
    
    return connection_errors


# ======= LLM 调度循环 =======
class LLMCentralBrain:

    def __init__(self,
                 api: GameAPI,
                 agent: StreamingAgent,
                 target_money: int = 100000,
                 max_cycles: int = 200,
                 seconds_per_tick: float = 2.5,
                 timeout_minutes: int = 30):
        self.api = api
        self.agent = agent
        self.target_money = target_money
        self.max_cycles = max_cycles
        self.seconds_per_tick = seconds_per_tick
        self.timeout_minutes = timeout_minutes
        self.start_time = datetime.datetime.now()
        
        # 探索区域追踪
        self.explored_cells: Set[Tuple[int, int]] = set()
        
        # 资金统计
        self.initial_money = 0
        self.total_money_spent = 0
        self.total_money_earned = 0
        self.money_history = []
        
        # 日志记录
        self.log_data = {
            "start_time": self.start_time.isoformat(),
            "timestamp": self.start_time.strftime("%Y%m%d_%H%M%S"),
            "model": agent.model,
            "cycles": [],
            "initialization_errors": []
        }
        
        # 连接失败检测
        self.connection_fail_count = 0
        self.max_connection_fails = 3  # 连续3次失败则认为游戏已结束
        
        api.deploy_mcv_and_wait(5)

    def loop(self):
        print("=" * 68)
        print("[*] LLM Central Brain 启动（LLM 全权决策）")
        print(f"[*] 超时时间：{self.timeout_minutes} 分钟")
        print("=" * 68)

        # 如果未部署 MCV，交给 LLM 决策；我们不强制部署
        for cycle in range(1, self.max_cycles + 1):
            # 检查超时
            elapsed_time = (datetime.datetime.now() - self.start_time).total_seconds()
            if elapsed_time > self.timeout_minutes * 60:
                print(f"\n[!] 已达到超时限制 {self.timeout_minutes} 分钟，程序结束")
                break
            
            # 检查连接状态
            try:
                # 尝试查询状态以检测连接
                test_info = self.api.player_base_info_query()
                self.connection_fail_count = 0  # 连接成功，重置计数器
            except Exception as e:
                self.connection_fail_count += 1
                error_msg = str(e)
                print(f"\n[!] 连接检测失败 ({self.connection_fail_count}/{self.max_connection_fails}): {error_msg}")
                
                if self.connection_fail_count >= self.max_connection_fails:
                    print(f"\n[!] 连续{self.max_connection_fails}次连接失败，游戏可能已结束，保存结果并退出")
                    self.log_data["end_reason"] = f"连接失败: {error_msg}"
                    break
                else:
                    # 还未达到失败上限，跳过本轮并重试
                    time.sleep(2)
                    continue
            
            # 1) 观测编码
            cycle_start = datetime.datetime.now()
            try:
                state = encode_state(self.api, cycle)
            except Exception as e:
                print(f"\n[!] 观测编码失败: {e}")
                self.connection_fail_count += 1
                if self.connection_fail_count >= self.max_connection_fails:
                    print(f"\n[!] 游戏可能已结束，保存结果并退出")
                    self.log_data["end_reason"] = f"观测失败: {str(e)}"
                    break
                time.sleep(2)
                continue
            money = state["money"]
            
            # 记录初始资金（第一次循环）
            if cycle == 1:
                self.initial_money = money
            
            # 更新探索区域（只追踪战斗单位和建筑，不追踪采矿车）
            for unit in state.get("combat_units", []):
                pos = unit.get("pos", {})
                x, y = pos.get("x"), pos.get("y")
                if x is not None and y is not None:
                    self.explored_cells.add((x, y))
            
            for building in state.get("my_buildings", []):
                pos = building.get("pos", {})
                x, y = pos.get("x"), pos.get("y")
                if x is not None and y is not None:
                    self.explored_cells.add((x, y))
            
            # 追踪受损采矿车位置
            for harv in state.get("harvesters", {}).get("damaged", []):
                pos = harv.get("pos", {})
                x, y = pos.get("x"), pos.get("y")
                if x is not None and y is not None:
                    self.explored_cells.add((x, y))
            
            print(
                f"\n--- Cycle {cycle}/{self.max_cycles} | Money ${money} | Power {state['power']['unused']}/{state['power']['provided']} | 探索区域: {len(self.explored_cells)} ---"
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
                        "max_unit_commands_per_tick": 40,
                        "must_not_target_allies": True,
                        "attack_targets_must_be_visible_enemies": True,
                        "avoid_power_deficit": True,
                        "primary_goal_money": 100000,
                        "explore_whole_map": True,
                        "critical": "严格限制unit_commands数量在40条以内，防止输出被截断导致JSON解析失败"
                    },
                    "examples":
                    examples,  # ← 多样化、非电厂-only
                    "reflection": [
                        "注意整个地图的范围是(0,0)到(100,100)",
                        "探索地图前要先建雷达",
                        "升级科技需要建造维修厂，核电站，科技中心",
                        "攻击单位推荐升级科技后建造4tnk",
                        "探索地图发现敌方位置后要集中火力消灭敌方的攻击单位，之后消灭敌方的建造单位，最后敌方的生产建筑可以分兵力快速消灭",
                        "要布置兵力保护我方重要建筑物",
                        "进攻路线可以有很多，注意使用包夹策略",
                        "矿场和矿车数量比要在1：2左右",
                        "避开或者优先进攻敌方的防御塔",
                        "每轮unit_commands数量不要超过40条，优先指挥关键战斗单位，避免JSON输出过长被截断",
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
            
            # 记录当前循环日志
            cycle_log = {
                "cycle": cycle,
                "datetime": cycle_start.isoformat(),
                "prompt": prompt,
                "response": raw,
                "prompt_length": len(prompt),
                "response_length": len(raw)
            }
            self.log_data["cycles"].append(cycle_log)
            
            if not plan:
                print("[LLM] JSON 解析失败，本轮跳过执行。")
            else:
                build_list = plan.get("build", [])
                unit_cmds = plan.get("unit_commands", [])
                
                # 执行建造和命令（获取建造成本）
                build_errors, build_cost = exec_build_plan(self.api, build_list)
                unit_errors = exec_unit_commands(self.api, unit_cmds, max_per_tick=64)
                
                # 累加建造成本
                self.total_money_spent += build_cost
                
                # 检查连接错误
                total_errors = build_errors + unit_errors
                if total_errors >= 3:
                    self.connection_fail_count += 1
                    print(f"\n[!] 执行操作时发生{total_errors}次连接错误")
                    if self.connection_fail_count >= self.max_connection_fails:
                        print(f"\n[!] 连续多次连接失败，游戏可能已结束，保存结果并退出")
                        self.log_data["end_reason"] = "执行操作时连接失败"
                        break

                # 4) 记录资金变化（用于统计收入）
                try:
                    # 等待一小段时间后查询最终资金
                    time.sleep(0.5)
                    info_final = self.api.player_base_info_query()
                    money_final = info_final.Cash + info_final.Resources
                    
                    # 本轮净收入（实际资金变化）
                    cycle_net_change = money_final - money
                    
                    # 本轮采集收入 = 净变化 + 建造成本
                    cycle_income = cycle_net_change + build_cost
                    if cycle_income > 0:
                        self.total_money_earned += cycle_income
                    
                    # 记录资金历史（包含详细信息）
                    money_record = {
                        "cycle": cycle,
                        "money_start": money,
                        "money_final": money_final,
                        "cash_final": info_final.Cash,
                        "resources_final": info_final.Resources,
                        "build_cost": build_cost,  # 本轮建造成本（价格表）
                        "cycle_income": cycle_income,  # 本轮采集收入
                        "cycle_net_change": cycle_net_change  # 本轮净变化
                    }
                    self.money_history.append(money_record)
                    
                    feedback = {
                        "money_before": money,
                        "money_after": money_final,
                        "build_cost": build_cost,
                        "income": cycle_income,
                        "net_change": cycle_net_change,
                        "cycle": cycle
                    }
                    print(f"[FEEDBACK] {feedback}")
                except Exception as e:
                    print(f"[FEEDBACK] 资金统计异常: {e}")

            time.sleep(self.seconds_per_tick)

        # 循环结束后保存日志和输出探索区域
        self._save_log_and_report()

    @staticmethod
    def _parse_llm_json(raw: str) -> Optional[Dict[str, Any]]:
        from typing import Optional
        import re

        def extract_after_action(s: str,
                                 marker: str = "#####Action#####",
                                 strip: bool = True) -> str:
            """
            返回字符串中第一次出现 marker 之后的所有文本。
            - 若 marker 不存在，返回原始字符串。
            - strip=True 时，会对结果做 .strip() 去除前后空白。
            """
            idx = s.find(marker)
            if idx == -1:
                return s
            out = s[idx + len(marker):]
            return out.strip() if strip else out
        
        def try_fix_incomplete_json(text: str) -> str:
            """
            尝试修复不完整的JSON（如缺少闭合括号）
            """
            # 统计括号数量
            open_braces = text.count('{')
            close_braces = text.count('}')
            open_brackets = text.count('[')
            close_brackets = text.count(']')
            
            # 补全缺失的闭合符号
            fixed = text
            if open_brackets > close_brackets:
                fixed += ']' * (open_brackets - close_brackets)
            if open_braces > close_braces:
                fixed += '}' * (open_braces - close_braces)
            
            return fixed

        try:
            raw = extract_after_action(raw)
            s, e = raw.find("{"), raw.rfind("}")
            print(f"[DEBUG] JSON位置: start={s}, end={e}")
            
            if s < 0:
                print("[PARSE] 未找到JSON起始标记")
                return None
            
            # 提取JSON文本
            json_text = raw[s:e + 1] if e >= s else raw[s:]
            
            # 尝试直接解析
            try:
                obj = json.loads(json_text)
            except json.JSONDecodeError as je:
                print(f"[PARSE] JSON解析失败: {je}, 尝试修复...")
                # 尝试修复不完整的JSON
                fixed_json = try_fix_incomplete_json(json_text)
                try:
                    obj = json.loads(fixed_json)
                    print("[PARSE] JSON修复成功")
                except:
                    print("[PARSE] JSON修复失败，返回空结果")
                    return {"build": [], "unit_commands": [], "notes": "JSON解析失败"}
            
            # 基本字段容错
            if "build" not in obj: 
                obj["build"] = []
            if "unit_commands" not in obj: 
                obj["unit_commands"] = []
            
            # 限制unit_commands数量，防止过长
            if len(obj["unit_commands"]) > 50:
                print(f"[PARSE] 警告: unit_commands数量过多({len(obj['unit_commands'])}), 截取前50条")
                obj["unit_commands"] = obj["unit_commands"][:50]
            
            return obj
            
        except Exception as ex:
            print(f"[PARSE] 解析异常: {ex}")
            import traceback
            traceback.print_exc()
            return None

    def _save_log_and_report(self):
        """保存日志文件并输出探索区域统计"""
        # 计算最大可见区域范围
        if self.explored_cells:
            xs = [x for x, y in self.explored_cells]
            ys = [y for x, y in self.explored_cells]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            exploration_area = {
                "min_x": min_x,
                "max_x": max_x,
                "min_y": min_y,
                "max_y": max_y,
                "width": max_x - min_x + 1,
                "height": max_y - min_y + 1,
                "total_cells": len(self.explored_cells),
                "bounding_box_area": (max_x - min_x + 1) * (max_y - min_y + 1)
            }
        else:
            exploration_area = {
                "min_x": 0, "max_x": 0, "min_y": 0, "max_y": 0,
                "width": 0, "height": 0, "total_cells": 0, "bounding_box_area": 0
            }
        
        # 添加结束信息到日志
        self.log_data["end_time"] = datetime.datetime.now().isoformat()
        self.log_data["total_cycles"] = len(self.log_data["cycles"])
        self.log_data["exploration_area"] = exploration_area
        
        # 添加资金统计信息（修正算法）
        final_money = self.money_history[-1]["money_final"] if self.money_history else self.initial_money
        net_change = final_money - self.initial_money
        actual_total_earned = self.total_money_spent + net_change  # 总收入 = 总支出 + 净变化
        
        self.log_data["money_statistics"] = {
            "initial_money": self.initial_money,
            "final_money": final_money,
            "total_money_spent": self.total_money_spent,
            "total_money_earned": actual_total_earned,
            "net_money_change": net_change,
            "money_history": self.money_history,
            "note": "total_money_spent根据价格表统计建造成本，total_money_earned根据资金变化计算采集收入，验证公式: 最终资金 = 初始资金 + 总收入 - 总支出"
        }
        
        # 构建日志文件名（包含模型名称）
        model_name = self.agent.model.replace("/", "_").replace(".", "_")
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        log_dir = os.path.join(os.path.dirname(__file__), "llm_logs")
        os.makedirs(log_dir, exist_ok=True)
        ai_name = "Naval AI"
        log_filename = f"game_log_{model_name}_{ai_name}_{timestamp}.json"
        log_filepath = os.path.join(log_dir, log_filename)
        
        # 保存日志
        try:
            with open(log_filepath, 'w', encoding='utf-8') as f:
                json.dump(self.log_data, f, ensure_ascii=False, indent=2)
            print(f"\n[LOG] 日志已保存到: {log_filepath}")
        except Exception as e:
            print(f"\n[LOG] 日志保存失败: {e}")
        
        # 输出探索区域统计
        print("\n" + "=" * 68)
        print("[*] 探索区域统计")
        print("=" * 68)
        print(f"探索的总格子数: {exploration_area['total_cells']}")
        print(f"最大可见区域范围:")
        print(f"  X轴: {exploration_area['min_x']} ~ {exploration_area['max_x']} (宽度: {exploration_area['width']})")
        print(f"  Y轴: {exploration_area['min_y']} ~ {exploration_area['max_y']} (高度: {exploration_area['height']})")
        print(f"  边界框面积: {exploration_area['bounding_box_area']} 格子")
        print("=" * 68)
        
        # 输出资金消耗统计（修正算法）
        final_money = self.money_history[-1]["money_final"] if self.money_history else self.initial_money
        net_change = final_money - self.initial_money
        
        # 修正：总收入 = 总支出 + 净变化（因为：净变化 = 收入 - 支出）
        actual_total_earned = self.total_money_spent + net_change
        
        print("\n" + "=" * 68)
        print("[*] 资金统计")
        print("=" * 68)
        print(f"初始资金: ${self.initial_money:,}")
        print(f"最终资金: ${final_money:,}")
        print(f"净资金变化: ${net_change:,}")
        print(f"总消耗资金: ${self.total_money_spent:,} (建造/生产成本)")
        print(f"总获得资金: ${actual_total_earned:,} (采集收入)")
        print(f"\n验证: ${self.initial_money:,} + ${actual_total_earned:,} - ${self.total_money_spent:,} = ${self.initial_money + actual_total_earned - self.total_money_spent:,}")
        if self.total_money_spent > 0:
            print(f"收入/支出比: {(actual_total_earned / self.total_money_spent):.2f}")
            print(f"投资回报率: {((actual_total_earned - self.total_money_spent) / self.total_money_spent * 100):.2f}%")
        print("=" * 68)


# ======= 运行入口 =======
def main():
    # 你可以按需替换 KEY/模型
    agent = StreamingAgent(
        role=SYSTEM_PROMPT,
        api_key=
        "sk-1ceae40f665683d838eecb22bddbf710af8e20900d139b45f57de52a9ac3e663",
        model="DeepSeek-V3.2")

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

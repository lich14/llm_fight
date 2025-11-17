#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 指挥官模式
阶段1: 建造所有建筑（固定流程）
阶段2: 由大模型决策如何生产战斗单位和指挥作战

结合了 defense_simple.py 的建筑建造 + fight.py 的 LLM 决策
"""

import sys
import os
import time
import json
import requests
from typing import List, Dict, Any
from datetime import datetime
from tenacity import retry, wait_random_exponential, stop_after_attempt

# 添加库路径
current_dir = os.path.dirname(os.path.abspath(__file__))
library_path = os.path.join(current_dir, 'examples', 'mofa', 'examples', 'openra-controller')
sys.path.insert(0, library_path)

from OpenRA_Copilot_Library.game_api import GameAPI
from OpenRA_Copilot_Library.models import TargetsQueryParam, Location, Actor


# ===== StreamingAgent (复用自 fight.py) =====
class StreamingAgent:
    def __init__(
            self,
            role: str,
            api_key: str = "f61ov1gbo76awnl3z4rz1a8ltiykrg6c",
            model: str = "gemini-1.5-flash",
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
            "model": self.model,
            "stream": True
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


# ===== 系统提示词 =====
SYSTEM_PROMPT = """
你是 OpenRA 的战术指挥官 AI。

你的目标是：主动探索地图，找到并消灭所有敌人（包括视野外的敌人）和建筑。

## 重要提示

敌人可能不在你的视野范围内，你必须：
1. 持续派遣侦察单位探索未知区域
2. 即使看不到敌人，也要主动向地图各个方向推进
3. 地图大小约 99x99，需要全面扫描

## 当前阶段

基地建设已完成，你现在需要：
1. 根据当前战场情况决定生产哪些战斗单位
2. 指挥已有单位进行移动、攻击、防守等操作
3. **持续派遣部队探索地图各个角落**

## 你可以生产的单位

步兵类：
- "步兵" - 便宜的基础步兵，可用于侦察
- "火箭兵" - 反坦克、反空

坦克类：
- "3tnk" - 重型坦克，性价比高
- "4tnk" - 猛犸坦克，最强坦克
- "ftrk" - 防空车，对空单位
- "v2rl" - V2火箭发射车，远程轰炸

空军：
- "yak" - 雅克战斗机，适合空中支援
- "mig" - 米格战斗机，速度快，适合侦察

## 输出格式

你必须输出严格的 JSON 格式（不要有任何其他文字）：

{
  "build": [
    {"name_or_code": "3tnk", "count": 5, "is_building": false, "why": "生产重型坦克进攻"}
  ],
  "unit_commands": [
    {"actor_id": 123, "action": "attack_move", "target": {"x": 80, "y": 120}},
    {"actor_id": 124, "action": "attack", "target_id": 999}
  ],
  "notes": "当前策略：集结坦克部队向敌方基地推进"
}

说明：
- build: 生产队列，is_building 必须为 false（单位）
- unit_commands: 对每个单位的指令
  - action: "move" 移动到坐标
  - action: "attack" 攻击指定敌人
  - action: "attack_move" 攻击性移动（边走边打）- **推荐用于探索**
  - action: "hold" 原地待命
- notes: 可选的策略说明

## 战术建议（重要）

1. **主动探索**: 即使看不到敌人，也要派单位去地图四个角落（0,0）（99,0）（0,99）（99,99）
2. **侦察优先**: 先派步兵或米格战斗机快速侦察，发现敌人后再派主力
3. **攻击性移动**: 使用 attack_move 让单位在移动过程中自动攻击遇到的敌人
4. **持续推进**: 不要守在基地，要主动向外扩展视野
5. **分散搜索**: 让不同单位去不同方向，加快搜索速度
6. **目标明确**: 一旦发现敌人，立即集结部队前往

只输出 JSON，不要其他文字。
"""


# ===== 建筑建造函数 (从 defense_simple.py 复用) =====
def build_structure(api: GameAPI, name: str, code: str, count: int) -> int:
    """建造建筑"""
    print(f"\n[建造] {name} x{count}")
    
    success = 0
    for i in range(count):
        try:
            api.produce(code, 1, True)
            print(f"  [{i+1}/{count}] 已下单")
            time.sleep(2)
            success += 1
        except Exception as e:
            print(f"  [{i+1}/{count}] 失败: {e}")
    
    # 等待建造完成
    if success > 0:
        print(f"  等待建造完成...")
        time.sleep(10)
    
    return success


def check_and_build_power(api: GameAPI):
    """检查电力，如果不足则建造核电站"""
    info = api.player_base_info_query()
    
    # 如果电力低于100或电力为负
    if info.Power < 100:
        print(f"\n电力不足！(当前: {info.Power}/{info.PowerProvided})")
        
        # 检查是否有足够资金
        if info.Cash >= 250:
            print("  自动建造核电站...")
            try:
                api.produce("核电站", 1, True)
                print("  核电站已下单")
                time.sleep(10)
                
                # 再次检查电力
                new_info = api.player_base_info_query()
                print(f"  电力状态: {new_info.Power}/{new_info.PowerProvided}")
            except Exception as e:
                print(f"  建造核电站失败: {e}")
        else:
            print(f"  资金不足，无法建造核电站 (需要$250，当前${info.Cash})")
    else:
        print(f"电力充足: {info.Power}/{info.PowerProvided}")


def build_all_structures(api: GameAPI):
    """建造所有建筑（不生产战斗单位）"""
    print("\n" + "=" * 60)
    print("阶段1: 建造完整基地")
    print("=" * 60)
    
    # 步骤1: 基础电力和资源
    print("\n[步骤1] 基础电力和资源")
    build_structure(api, "电厂", "电厂", 2)
    check_and_build_power(api)
    
    build_structure(api, "矿场", "矿场", 2)
    check_and_build_power(api)
    
    # 步骤2: 基础生产建筑
    print("\n[步骤2] 基础生产建筑")
    build_structure(api, "兵营", "兵营", 1)
    check_and_build_power(api)
    
    build_structure(api, "战车工厂", "战车工厂", 1)
    check_and_build_power(api)
    
    # 步骤3: 雷达和科技
    print("\n[步骤3] 雷达和科技")
    build_structure(api, "雷达", "雷达", 1)
    check_and_build_power(api)
    
    build_structure(api, "维修厂", "维修厂", 1)
    check_and_build_power(api)
    
    build_structure(api, "科技中心", "科技中心", 1)
    check_and_build_power(api)
    
    # 步骤4: 高级建筑（科技中心之后才能建）
    print("\n[步骤4] 高级生产建筑")
    build_structure(api, "战车工厂", "战车工厂", 1)  # 第二个战车工厂
    check_and_build_power(api)
    
    build_structure(api, "机场", "机场", 1)  # 机场需要科技中心前置
    check_and_build_power(api)
    
    # 步骤5: 补充资源建筑
    print("\n[步骤5] 补充资源设施")
    build_structure(api, "矿场", "矿场", 3)  # 再建3个矿场，总共5个
    check_and_build_power(api)
    
    build_structure(api, "核电站", "核电站", 1)
    check_and_build_power(api)
    
    # 步骤6: 防御建筑
    print("\n[步骤6] 防御设施")
    build_structure(api, "火焰塔", "火焰塔", 2)
    check_and_build_power(api)
    
    build_structure(api, "特斯拉线圈", "特斯拉线圈", 2)
    check_and_build_power(api)
    
    build_structure(api, "防空导弹", "防空导弹", 2)
    check_and_build_power(api)
    
    print("\n" + "=" * 60)
    print("基地建设完成！现在交给 AI 指挥官接管")
    print("=" * 60)


# ===== 观测编码 (从 fight.py 简化) =====
def encode_state(api: GameAPI, cycle: int) -> Dict[str, Any]:
    """编码当前游戏状态"""
    info = api.player_base_info_query()
    
    # 我方单位（排除建筑）
    mine = api.query_actor(TargetsQueryParam(faction='自己')) or []
    my_units = []
    my_buildings = []
    
    building_types = {'建造厂', '电厂', '核电站', '矿场', '兵营', '战车工厂', 
                     '雷达', '维修厂', '科技中心', '机场', '采矿车',
                     '火焰塔', '特斯拉线圈', '防空导弹', '储存罐'}
    
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
        
        if item["type"] in building_types:
            my_buildings.append(item)
        else:
            my_units.append(item)
    
    # 敌方单位
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
    
    return {
        "cycle": cycle,
        "money": info.Cash + info.Resources,
        "power": {
            "unused": info.Power,
            "provided": info.PowerProvided
        },
        "my_buildings_count": len(my_buildings),
        "my_units": my_units,
        "enemies": enemy_list,
        "hints": {
            "map_size": {"w": 128, "h": 128},
            "available_units": ["步兵", "火箭兵", "3tnk", "4tnk", "ftrk", "v2rl", "mig"]
        }
    }


# ===== 动作执行器 (从 fight.py 简化) =====
def exec_build_plan(api: GameAPI, build_list: List[Dict[str, Any]]):
    """执行生产计划"""
    for item in build_list or []:
        name = item.get("name_or_code")
        cnt = max(1, int(item.get("count", 1)))
        is_building = bool(item.get("is_building", False))
        why = item.get("why", "")
        
        if not name:
            continue
            
        print(f"[生产] {name} x{cnt} | {why}")
        
        for i in range(cnt):
            try:
                api.produce(name, 1, is_building)
                print(f"  [{i+1}/{cnt}] 已下单")
                time.sleep(1)
            except Exception as e:
                print(f"  [{i+1}/{cnt}] 失败: {e}")


def exec_unit_commands(api: GameAPI, cmds: List[Dict[str, Any]]):
    """执行单位指令"""
    executed = 0
    
    for c in cmds or []:
        actor_id = c.get("actor_id")
        action = (c.get("action") or "").lower()
        
        if not actor_id or not action:
            continue
        
        try:
            if action == "move":
                t = c.get("target") or {}
                x, y = t.get("x"), t.get("y")
                if x is None or y is None:
                    continue
                # 直接传字典，避免Location对象序列化问题
                api.move_units_by_location_and_id([actor_id], location={"x": int(x), "y": int(y)})
                print(f"  [指令] 单位 {actor_id} 移动到 ({x}, {y})")
                executed += 1
                
            elif action == "attack":
                tid = c.get("target_id")
                if not tid:
                    continue
                api.attack_target_id(actor_id, tid)
                print(f"  [指令] 单位 {actor_id} 攻击目标 {tid}")
                executed += 1
                
            elif action == "attack_move":
                t = c.get("target") or {}
                x, y = t.get("x"), t.get("y")
                if x is None or y is None:
                    continue
                # 直接传字典，避免Location对象序列化问题
                api.move_units_by_location_and_id([actor_id], location={"x": int(x), "y": int(y)}, attack_move=True)
                print(f"  [指令] 单位 {actor_id} 攻击性移动到 ({x}, {y})")
                executed += 1
                
            elif action in ["hold", "stop"]:
                api.stop(actor_id)
                print(f"  [指令] 单位 {actor_id} 停止")
                executed += 1
                
        except Exception as e:
            print(f"  [指令失败] {e}")
    
    if executed > 0:
        print(f"执行了 {executed} 条指令")


# ===== AI 决策循环 =====
class AICommander:
    # 优先攻击的敌方建筑类型
    TARGET_BUILDINGS = [
        "fact",   # 建造厂
        "powr",   # 电厂
        "weap",   # 战车工厂
        "afld",   # 空军基地
        "proc",   # 矿场
        "stek",   # 科技中心
        "apwr",   # 核电站
        "barr",   # 兵营
        "fix",    # 维修厂   
    ]
    
    # 战斗单位类型（用于执行攻击任务）
    COMBAT_UNIT_TYPES = [
        # 坦克类
        "3tnk", "4tnk",  # 重坦、猛犸
        # 步兵类
        "e1", "e3",  # 步兵、火箭兵
        # 空军类
        "mig", "yak",  # 米格、雅克战机
        # 其他战斗载具
        "v2rl", "ftrk",  # V2火箭、火焰车
    ]
    
    def __init__(self, api: GameAPI, agent: StreamingAgent, max_cycles: int = 300):
        self.api = api
        self.agent = agent
        self.max_cycles = max_cycles
        self.assigned_targets = {}  # unit_id -> target_building_id
        self.destroyed_buildings = set()  # 已摧毁的建筑ID
    
    def auto_attack_enemy_buildings(self):
        """自动指挥战斗单位攻击敌方关键建筑"""
        try:
            # 1. 获取我方战斗单位
            my_units = self.api.query_actor(TargetsQueryParam(
                faction="己方",
                type=self.COMBAT_UNIT_TYPES
            )) or []
            
            if not my_units:
                return
            
            # 2. 获取敌方建筑
            enemy_buildings = self.api.query_actor(TargetsQueryParam(
                faction="敌方",
                type=self.TARGET_BUILDINGS
            )) or []
            
            if not enemy_buildings:
                return
            
            # 3. 更新已摧毁建筑列表
            existing_ids = {b.actor_id for b in enemy_buildings}
            for target_id in list(self.assigned_targets.values()):
                if target_id not in existing_ids and target_id not in self.destroyed_buildings:
                    self.destroyed_buildings.add(target_id)
                    print(f"  建筑 {target_id} 已被摧毁！")
            
            # 4. 找出空闲单位
            idle_units = []
            for unit in my_units:
                if unit.actor_id not in self.assigned_targets:
                    idle_units.append(unit)
                else:
                    # 检查目标是否还存在
                    target_id = self.assigned_targets[unit.actor_id]
                    if target_id in self.destroyed_buildings:
                        idle_units.append(unit)
                        del self.assigned_targets[unit.actor_id]
            
            if not idle_units:
                return
            
            # 5. 为空闲单位分配攻击目标
            assigned_count = 0
            for unit in idle_units:
                # 找到最优先的建筑
                target = None
                for building_type in self.TARGET_BUILDINGS:
                    for building in enemy_buildings:
                        if building.actor_id in self.destroyed_buildings:
                            continue
                        if building.type == building_type:
                            target = building
                            break
                    if target:
                        break
                
                # 如果没有找到，就攻击最近的建筑
                if not target:
                    min_dist = float('inf')
                    for building in enemy_buildings:
                        if building.actor_id in self.destroyed_buildings:
                            continue
                        if unit.position and building.position:
                            dx = building.position.x - unit.position.x
                            dy = building.position.y - unit.position.y
                            dist = (dx * dx + dy * dy) ** 0.5
                            if dist < min_dist:
                                min_dist = dist
                                target = building
                
                # 发起攻击
                if target:
                    try:
                        success = self.api.attack_target_id(unit.actor_id, [target.actor_id])
                        if success:
                            self.assigned_targets[unit.actor_id] = target.actor_id
                            assigned_count += 1
                    except Exception:
                        pass
            
            if assigned_count > 0:
                print(f"  自动攻击: {assigned_count} 个单位分配攻击敌方建筑")
                print(f"  已摧毁建筑: {len(self.destroyed_buildings)} 个")
                
        except Exception as e:
            # 静默失败，不影响主流程
            pass
    
    def run(self):
        """AI 指挥循环"""
        print("\n" + "=" * 60)
        print("阶段2: AI 指挥官接管")
        print("=" * 60)
        
        for cycle in range(1, self.max_cycles + 1):
            print(f"\n{'='*60}")
            print(f"回合 {cycle}/{self.max_cycles}")
            print(f"{'='*60}")
            
            # 1. 自动攻击敌方建筑
            self.auto_attack_enemy_buildings()
            
            # 2. 获取当前状态
            state = encode_state(self.api, cycle)
            print(f"资金: ${state['money']} | 电力: {state['power']['unused']}/{state['power']['provided']}")
            print(f"我方单位: {len(state['my_units'])} | 敌方可见单位: {len(state['enemies'])}")
            
            # 提示探索重要性
            if len(state['enemies']) == 0:
                print("视野内无敌人 - 需要主动探索地图寻找敌人！")
            
            # 注意：不再因为看不到敌人就判定胜利，需要真正全部消灭
            
            # 3. 构建提示词
            instruction = "根据当前状态，决定生产哪些单位以及如何指挥现有单位作战。"
            if len(state['enemies']) == 0:
                instruction += " ⚠️ 当前视野内无敌人，必须派遣单位主动探索地图（地图大小99x99），使用attack_move向不同方向推进！"
            
            prompt = json.dumps({
                "state": state,
                "instruction": instruction
            }, ensure_ascii=False)
            
            # 4. 获取 AI 决策
            try:
                raw_response = self.agent.chat(prompt)
                
                # 尝试提取 JSON
                response = None
                if "```json" in raw_response:
                    json_start = raw_response.find("```json") + 7
                    json_end = raw_response.find("```", json_start)
                    json_str = raw_response[json_start:json_end].strip()
                    response = json.loads(json_str)
                elif "```" in raw_response:
                    json_start = raw_response.find("```") + 3
                    json_end = raw_response.find("```", json_start)
                    json_str = raw_response[json_start:json_end].strip()
                    response = json.loads(json_str)
                else:
                    response = json.loads(raw_response)
                
                # 5. 执行决策
                if response:
                    notes = response.get("notes", "")
                    if notes:
                        print(f"\n[AI 策略] {notes}")
                    
                    # 执行生产
                    build_list = response.get("build", [])
                    if build_list:
                        print(f"\n[生产计划] {len(build_list)} 项")
                        exec_build_plan(self.api, build_list)
                    
                    # 执行指令
                    commands = response.get("unit_commands", [])
                    if commands:
                        print(f"\n[单位指令] {len(commands)} 条")
                        exec_unit_commands(self.api, commands)
                
            except json.JSONDecodeError as e:
                print(f"JSON 解析失败: {e}")
                print(f"原始响应: {raw_response[:200]}...")
            except Exception as e:
                print(f"决策执行失败: {e}")
            
            # 6. 等待下一回合
            time.sleep(3)
        
        print("\n" + "=" * 60)
        print("游戏结束")
        print("=" * 60)


# ===== 主程序 =====
def main():
    print("=" * 60)
    print("AI 指挥官模式")
    print("阶段1: 建造完整基地")
    print("阶段2: AI 全权指挥作战")
    print("=" * 60)
    
    # 初始化 API
    api = GameAPI(host="localhost", port=7445, language="zh")
    
    # 部署 MCV
    print("\n[初始化] 部署建造厂...")
    try:
        api.deploy_mcv_and_wait(5)
        print("建造厂就绪")
    except Exception as e:
        print(f"提示: {e}")
    
    time.sleep(3)
    
    # 阶段1: 建造所有建筑
    build_all_structures(api)
    
    # 阶段2: AI 接管
    agent = StreamingAgent(
        role=SYSTEM_PROMPT,
        model="gemini-1.5-flash"
    )
    
    commander = AICommander(api, agent, max_cycles=300)
    commander.run()


if __name__ == "__main__":
    main()

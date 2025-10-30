#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""OpenRA 游戏工具集 - 移植自 MCP 版本"""

import sys
import os
sys.path.append(os.getenv('OPENRA_PATH', '/Users/liyao/Code/mofa/OpenCodeAlert/Copilot/openra_ai'))

from OpenRA_Copilot_Library import GameAPI
from OpenRA_Copilot_Library.models import Location, TargetsQueryParam, Actor, MapQueryResult
from typing import List, Dict, Any, Optional
import json

class OpenRATools:
    """OpenRA 游戏工具类，包含与 MCP 版本完全相同的功能"""
    
    def __init__(self, host="localhost", port=7445):
        self.api = GameAPI(host=host, port=port, language="zh")
    
    def get_game_state(self) -> Dict[str, Any]:
        """返回玩家资源、电力和可见单位列表"""
        # 1) 玩家基础信息
        info = self.api.player_base_info_query()
        
        # 2) 由于 query_actor API 在当前游戏版本中似乎有问题，我们采用间接方法
        visible = []
        
        # 方法1: 先选择所有单位，然后尝试查询（虽然查询会失败，但能确认有单位存在）
        game_status = "游戏正在运行"
        try:
            # 尝试选择屏幕中的所有单位
            select_response = self.api._send_request('select_unit', {
                'targets': {},
                'isCombine': 0
            })
            if "Selected" in select_response.get('response', ''):
                game_status += "，检测到可选择的单位存在"
            else:
                game_status += "，未检测到可选择的单位"
        except:
            game_status += "，选择操作失败"
        
        # 方法2: 尝试通过ID暴力查找（这个方法有时能工作）
        for actor_id in range(1, 30):  # 扩大搜索范围
            try:
                actor = self.api.get_actor_by_id(actor_id)
                if actor:
                    visible.append({
                        "actor_id": actor.actor_id,
                        "type": actor.type,
                        "faction": actor.faction,
                        "position": {"x": actor.position.x, "y": actor.position.y},
                    })
            except:
                pass

        return {
            "cash": info.Cash,
            "resources": info.Resources,
            "power": info.Power,
            "visible_units": visible,
            "game_status": game_status  # 添加游戏状态信息
        }

    def visible_units(self, type: List[str], faction: str, range: str, restrain: List[dict]) -> List[Dict[str, Any]]:
        """根据条件查询可见单位"""
        # 修复单值传入错误
        if isinstance(type, str):
            type = [type]
        if isinstance(restrain, dict):  # 有时也会传成一个字典
            restrain = [restrain]
        elif isinstance(restrain, bool):  # LLM 有时会给布尔值
            restrain = []

        params = TargetsQueryParam(type=type, faction=faction, range=range, restrain=restrain)
        units = self.api.query_actor(params)
        return [
            {
                "actor_id": u.actor_id,
                "type": u.type,
                "faction": u.faction,
                "position": {"x": u.position.x, "y": u.position.y},
                "hpPercent": getattr(u, "hp_percent", None)
            }
            for u in units
        ]

    def produce(self, unit_type: str, quantity: int) -> int:
        """生产指定类型和数量的单位，返回生产任务 ID"""
        wait_id = self.api.produce(unit_type, quantity, auto_place_building=True)
        return wait_id or -1

    def move_units(self, actor_ids: List[int], x: int, y: int, attack_move: bool = False) -> str:
        """移动一批单位到指定坐标"""
        actors = [Actor(i) for i in actor_ids]
        loc = Location(x, y)
        self.api.move_units_by_location(actors, loc, attack_move=attack_move)
        return "ok"

    def camera_move_to(self, x: int, y: int) -> str:
        """将镜头移动到指定坐标"""
        self.api.move_camera_by_location(Location(x, y))
        return "ok"

    def camera_move_dir(self, direction: str, distance: int) -> str:
        """按方向移动镜头"""
        self.api.move_camera_by_direction(direction, distance)
        return "ok"

    def can_produce(self, unit_type: str) -> bool:
        """检查是否可生产某类型单位"""
        return self.api.can_produce(unit_type)

    def move_units_by_location(self, actor_ids: List[int], x: int, y: int, attack_move: bool = False) -> str:
        """把一批单位移动到指定坐标"""
        actors = [Actor(i) for i in actor_ids]
        self.api.move_units_by_location(actors, Location(x, y), attack_move)
        return "ok"

    def move_units_by_direction(self, actor_ids: List[int], direction: str, distance: int) -> str:
        """按方向移动一批单位"""
        actors = [Actor(i) for i in actor_ids]
        self.api.move_units_by_direction(actors, direction, distance)
        return "ok"

    def move_units_by_path(self, actor_ids: List[int], path: List[Dict[str, int]]) -> str:
        """沿指定路径移动一批单位"""
        actors = [Actor(i) for i in actor_ids]
        locs = [Location(p["x"], p["y"]) for p in path]
        self.api.move_units_by_path(actors, locs)
        return "ok"

    def select_units(self, type: List[str], faction: str, range: str, restrain: List[dict]) -> str:
        """选中符合条件的单位"""
        self.api.select_units(TargetsQueryParam(type=type, faction=faction, range=range, restrain=restrain))
        return "ok"

    def form_group(self, actor_ids: List[int], group_id: int) -> str:
        """为一批单位编组"""
        actors = [Actor(i) for i in actor_ids]
        self.api.form_group(actors, group_id)
        return "ok"

    def query_actor(self, type: List[str], faction: str, range: str, restrain: List[dict]) -> List[Dict[str, Any]]:
        """查询单位列表"""
        params = TargetsQueryParam(type=type, faction=faction, range=range, restrain=restrain)
        actors = self.api.query_actor(params)
        return [
            {
                "actor_id": u.actor_id,
                "type": u.type,
                "faction": u.faction,
                "position": {"x": u.position.x, "y": u.position.y},
                "hpPercent": getattr(u, "hp_percent", None)
            }
            for u in actors
        ]

    def attack(self, attacker_id: int, target_id: int) -> bool:
        """发起一次攻击"""
        atk = Actor(attacker_id)
        tgt = Actor(target_id)
        return self.api.attack_target(atk, tgt)

    def occupy(self, occupiers: List[int], targets: List[int]) -> str:
        """占领目标"""
        occ = [Actor(i) for i in occupiers]
        tgt = [Actor(i) for i in targets]
        self.api.occupy_units(occ, tgt)
        return "ok"

    def find_path(self, actor_ids: List[int], dest_x: int, dest_y: int, method: str) -> List[Dict[str,int]]:
        """为单位寻找路径"""
        actors = [Actor(i) for i in actor_ids]
        path = self.api.find_path(actors, Location(dest_x, dest_y), method)
        return [{"x": p.x, "y": p.y} for p in path]

    def get_actor_by_id(self, actor_id: int) -> Optional[Dict[str, Any]]:
        """根据 Actor ID 获取单个单位的信息，如果不存在则返回 None"""
        actor = self.api.get_actor_by_id(actor_id)
        if actor is None:
            return None

        return {
            "actor_id": actor.actor_id,
            "type": actor.type,
            "faction": actor.faction,
            "position": {"x": actor.position.x, "y": actor.position.y},
            "hpPercent": getattr(actor, "hp_percent", None)
        }

    def update_actor(self, actor_id: int) -> Optional[Dict[str, Any]]:
        """根据 actor_id 更新该单位的信息，并返回其最新状态"""
        actor = Actor(actor_id)
        success = self.api.update_actor(actor)
        if not success:
            return None

        return {
            "actor_id": actor.actor_id,
            "type": actor.type,
            "faction": actor.faction,
            "position": {"x": actor.position.x, "y": actor.position.y},
            "hpPercent": getattr(actor, "hp_percent", None)
        }

    def deploy_units(self, actor_ids: List[int] = None) -> str:
        """展开或部署指定单位列表，如果没有指定ID则尝试寻找和部署基地车"""
        if actor_ids:
            # 指定了ID，正常部署
            actors = [Actor(i) for i in actor_ids]
            self.api.deploy_units(actors)
            return "ok"
        else:
            # 没有指定ID，尝试直接使用 API 调用部署基地车
            # 1. 先尝试使用内置的 deploy_mcv_and_wait 方法
            try:
                self.api.deploy_mcv_and_wait(1.0)
                return "成功部署基地车 (使用内置方法)"
            except Exception as e:
                print(f"内置方法失败: {e}")
                
            # 2. 尝试直接调用 deploy API
            deploy_attempts = [
                {'targets': {'type': ['基地车'], 'faction': '己方'}},
                {'targets': {'type': ['mcv'], 'faction': '己方'}},  
                {'targets': {'type': ['基地车']}},
                {'targets': {'type': ['mcv']}},
                {'targets': {'faction': '己方'}},  # 部署所有己方可部署单位
            ]
            
            for i, params in enumerate(deploy_attempts):
                try:
                    response = self.api._send_request('deploy', params)
                    return f"成功部署 (尝试{i+1}): {response.get('response', '')}"
                except Exception as e:
                    continue
                    
            # 3. 最后尝试通过ID暴力查找MCV
            for actor_id in range(1, 50):
                try:
                    actor = self.api.get_actor_by_id(actor_id)
                    if actor and ('mcv' in actor.type.lower() or 'construction' in actor.type.lower() or '基地车' in actor.type):
                        self.api.deploy_units([actor])
                        return f"找到并部署基地车 ID: {actor_id}"
                except:
                    continue
                    
            return "未找到基地车可以部署，所有尝试都失败了"

    def move_camera_to_actor(self, actor_id: int) -> str:
        """将镜头移动到指定 Actor 的位置"""
        self.api.move_camera_to(Actor(actor_id))
        return "ok"

    def occupy_units(self, occupier_ids: List[int], target_ids: List[int]) -> str:
        """占领指定目标单位"""
        occupiers = [Actor(i) for i in occupier_ids]
        targets = [Actor(i) for i in target_ids]
        self.api.occupy_units(occupiers, targets)
        return "ok"

    def attack_target(self, attacker_id: int, target_id: int) -> bool:
        """由指定单位发起对目标单位的攻击"""
        attacker = Actor(attacker_id)
        target = Actor(target_id)
        return self.api.attack_target(attacker, target)

    def can_attack_target(self, attacker_id: int, target_id: int) -> bool:
        """检查指定单位是否可以攻击目标单位"""
        attacker = Actor(attacker_id)
        target = Actor(target_id)
        return self.api.can_attack_target(attacker, target)

    def repair_units(self, actor_ids: List[int]) -> str:
        """修复一批单位"""
        actors = [Actor(i) for i in actor_ids]
        self.api.repair_units(actors)
        return "ok"

    def stop_units(self, actor_ids: List[int]) -> str:
        """停止一批单位当前行动"""
        actors = [Actor(i) for i in actor_ids]
        self.api.stop(actors)
        return "ok"

    def visible_query(self, x: int, y: int) -> bool:
        """查询指定坐标是否在视野中"""
        return self.api.visible_query(Location(x, y))

    def explorer_query(self, x: int, y: int) -> bool:
        """查询指定坐标是否已探索"""
        return self.api.explorer_query(Location(x, y))

    def query_production_queue(self, queue_type: str) -> Dict[str, Any]:
        """查询指定类型的生产队列"""
        return self.api.query_production_queue(queue_type)

    def manage_production(self, queue_type: str, action: str) -> str:
        """管理生产队列中的项目（暂停、取消或继续）"""
        self.api.manage_production(queue_type, action)
        return "ok"

    def ensure_can_build_wait(self, building_name: str) -> bool:
        """确保指定建筑已存在，若不存在则递归建造其所有依赖并等待完成"""
        return self.api.ensure_can_build_wait(building_name)

    def ensure_can_produce_unit(self, unit_name: str) -> bool:
        """确保能生产指定单位（会自动补齐依赖建筑并等待完成）"""
        return self.api.ensure_can_produce_unit(unit_name)

    def move_units_and_wait(self, actor_ids: List[int], x: int, y: int, max_wait_time: float = 10.0, tolerance_dis: int = 1) -> bool:
        """移动一批单位到指定位置并等待到达或超时"""
        actors = [Actor(i) for i in actor_ids]
        return self.api.move_units_by_location_and_wait(actors, Location(x, y), max_wait_time, tolerance_dis)

    def unit_attribute_query(self, actor_ids: List[int]) -> Dict[str, Any]:
        """查询指定单位的属性及其攻击范围内的目标"""
        actors = [Actor(i) for i in actor_ids]
        return self.api.unit_attribute_query(actors)

    def map_query(self) -> Dict[str, Any]:
        """查询地图信息并返回序列化数据"""
        result = self.api.map_query()
        return {
            "width": result.MapWidth,
            "height": result.MapHeight,
            "heightMap": result.Height,
            "visible": result.IsVisible,
            "explored": result.IsExplored,
            "terrain": result.Terrain,
            "resourcesType": result.ResourcesType,
            "resources": result.Resources
        }

    def player_base_info_query(self) -> Dict[str, Any]:
        """查询玩家基地的资源、电力等基础信息"""
        info = self.api.player_base_info_query()
        return {
            "cash": info.Cash,
            "resources": info.Resources,
            "power": info.Power,
            "powerDrained": info.PowerDrained,
            "powerProvided": info.PowerProvided
        }

    def screen_info_query(self) -> Dict[str, Any]:
        """查询当前屏幕信息"""
        info = self.api.screen_info_query()
        return {
            "screenMin": {"x": info.ScreenMin.x, "y": info.ScreenMin.y},
            "screenMax": {"x": info.ScreenMax.x, "y": info.ScreenMax.y},
            "isMouseOnScreen": info.IsMouseOnScreen,
            "mousePosition": {"x": info.MousePosition.x, "y": info.MousePosition.y}
        }

    def set_rally_point(self, actor_ids: List[int], x: int, y: int) -> str:
        """为指定建筑设置集结点"""
        actors = [Actor(i) for i in actor_ids]
        self.api.set_rally_point(actors, Location(x, y))
        return "ok"

    def start_production(self, unit_type: str, quantity: int = 1, auto_place_building: bool = True) -> int:
        """开始生产单位或建筑，返回等待ID"""
        try:
            # 直接调用 API
            response = self.api._send_request('start_production', {
                'units': [{'unit_type': unit_type, 'quantity': quantity}],
                'autoPlaceBuilding': auto_place_building
            })
            result = response.get('data', {})
            return result.get('waitId', -1)
        except Exception as e:
            print(f"生产失败: {e}")
            return -1

    def place_building(self, queue_type: str, x: int = None, y: int = None) -> str:
        """放置已生产完成的建筑"""
        try:
            params = {'queueType': queue_type}
            if x is not None and y is not None:
                params['location'] = {'x': x, 'y': y}
            
            response = self.api._send_request('place_building', params)
            return response.get('response', '建筑放置完成')
        except Exception as e:
            return f"放置建筑失败: {e}"
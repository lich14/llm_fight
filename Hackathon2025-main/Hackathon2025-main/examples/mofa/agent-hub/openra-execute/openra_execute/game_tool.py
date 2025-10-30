"""
OpenRA Game API Tools
完整的游戏操作工具集，用于AI控制游戏单位和执行战略战术
"""

import os
import sys
import time
from typing import List, Dict, Any, Optional, Tuple

sys.path.append(os.getenv('OPENRA_PATH', '.'))

from OpenRA_Copilot_Library import GameAPI
from OpenRA_Copilot_Library.models import Location, TargetsQueryParam, Actor, MapQueryResult

# 单例 GameAPI 客户端
api = GameAPI(host="localhost", port=7445, language="zh")


# ==================== 基础查询工具 ====================

def get_game_state() -> Dict[str, Any]:
    """返回玩家资源、电力和可见单位列表"""
    info = api.player_base_info_query()
    units = api.query_actor(
        TargetsQueryParam(
            type=[], faction=["任意"], range="screen", restrain=[{"visible": True}]
        )
    )
    visible = [
        {
            "actor_id": u.actor_id,
            "type": u.type,
            "faction": u.faction,
            "position": {"x": u.position.x, "y": u.position.y},
        }
        for u in units if u.faction != "中立"
    ]

    return {
        "cash": info.Cash,
        "resources": info.Resources,
        "power": info.Power,
        "visible_units": visible
    }


def visible_units(type: List[str], faction: str, range: str, restrain: List[dict]) -> List[Dict[str, Any]]:
    """根据条件查询可见单位"""
    if isinstance(type, str):
        type = [type]
    if isinstance(restrain, dict):
        restrain = [restrain]
    elif isinstance(restrain, bool):
        restrain = []

    params = TargetsQueryParam(type=type, faction=faction, range=range, restrain=restrain)
    units = api.query_actor(params)
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


def query_actor(type: List[str], faction: str, range: str, restrain: List[dict]) -> List[Dict[str, Any]]:
    """查询单位列表"""
    params = TargetsQueryParam(type=type, faction=faction, range=range, restrain=restrain)
    actors = api.query_actor(params)
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


def get_actor_by_id(actor_id: int) -> Optional[Dict[str, Any]]:
    """根据 Actor ID 获取单个单位的信息，如果不存在则返回 None"""
    actor = api.get_actor_by_id(actor_id)
    if actor is None:
        return None
    return {
        "actor_id": actor.actor_id,
        "type": actor.type,
        "faction": actor.faction,
        "position": {"x": actor.position.x, "y": actor.position.y},
        "hpPercent": getattr(actor, "hp_percent", None)
    }


def update_actor(actor_id: int) -> Optional[Dict[str, Any]]:
    """根据 actor_id 更新该单位的信息，并返回其最新状态"""
    actor = Actor(actor_id)
    success = api.update_actor(actor)
    if not success:
        return None
    return {
        "actor_id": actor.actor_id,
        "type": actor.type,
        "faction": actor.faction,
        "position": {"x": actor.position.x, "y": actor.position.y},
        "hpPercent": getattr(actor, "hp_percent", None)
    }


# ==================== 生产相关工具 ====================

def produce(unit_type: str, quantity: int) -> int:
    """生产指定类型和数量的单位，返回生产任务 ID"""
    wait_id = api.produce(unit_type, quantity, auto_place_building=True)
    return wait_id or -1


def can_produce(unit_type: str) -> bool:
    """检查是否可生产某类型单位"""
    return api.can_produce(unit_type)


def query_production_queue(queue_type: str) -> Dict[str, Any]:
    """查询指定类型的生产队列"""
    return api.query_production_queue(queue_type)


def manage_production(queue_type: str, action: str) -> str:
    """管理生产队列中的项目（暂停、取消或继续）"""
    api.manage_production(queue_type, action)
    return "ok"


def ensure_can_build_wait(building_name: str) -> bool:
    """确保指定建筑已存在，若不存在则递归建造其所有依赖并等待完成"""
    return api.ensure_can_build_wait(building_name)


def ensure_can_produce_unit(unit_name: str) -> bool:
    """确保能生产指定单位（会自动补齐依赖建筑并等待完成）"""
    return api.ensure_can_produce_unit(unit_name)


# ==================== 单位移动工具 ====================

def move_units(actor_ids: List[int], x: int, y: int, attack_move: bool = False) -> str:
    """移动一批单位到指定坐标"""
    actors = [Actor(i) for i in actor_ids]
    loc = Location(x, y)
    api.move_units_by_location(actors, loc, attack_move=attack_move)
    return "ok"


def move_units_by_location(actor_ids: List[int], x: int, y: int, attack_move: bool = False) -> str:
    """把一批单位移动到指定坐标"""
    actors = [Actor(i) for i in actor_ids]
    api.move_units_by_location(actors, Location(x, y), attack_move)
    return "ok"


def move_units_by_direction(actor_ids: List[int], direction: str, distance: int) -> str:
    """按方向移动一批单位"""
    actors = [Actor(i) for i in actor_ids]
    api.move_units_by_direction(actors, direction, distance)
    return "ok"


def move_units_by_path(actor_ids: List[int], path: List[Dict[str, int]]) -> str:
    """沿指定路径移动一批单位"""
    actors = [Actor(i) for i in actor_ids]
    locs = [Location(p["x"], p["y"]) for p in path]
    api.move_units_by_path(actors, locs)
    return "ok"


def move_units_and_wait(
        actor_ids: List[int],
        x: int,
        y: int,
        max_wait_time: float = 10.0,
        tolerance_dis: int = 1
) -> bool:
    """移动一批单位到指定位置并等待到达或超时"""
    actors = [Actor(i) for i in actor_ids]
    return api.move_units_by_location_and_wait(actors, Location(x, y), max_wait_time, tolerance_dis)


# ==================== 相机控制工具 ====================

def camera_move_to(x: int, y: int) -> str:
    """将镜头移动到指定坐标"""
    api.move_camera_by_location(Location(x, y))
    return "ok"


def camera_move_dir(direction: str, distance: int) -> str:
    """按方向移动镜头"""
    api.move_camera_by_direction(direction, distance)
    return "ok"


def move_camera_to(actor_id: int) -> str:
    """将镜头移动到指定 Actor 的位置"""
    api.move_camera_to(Actor(actor_id))
    return "ok"


# ==================== 战斗相关工具 ====================

def attack(attacker_id: int, target_id: int) -> bool:
    """发起一次攻击"""
    atk = Actor(attacker_id)
    tgt = Actor(target_id)
    return api.attack_target(atk, tgt)


def attack_target(attacker_id: int, target_id: int) -> bool:
    """由指定单位发起对目标单位的攻击"""
    attacker = Actor(attacker_id)
    target = Actor(target_id)
    return api.attack_target(attacker, target)


def can_attack_target(attacker_id: int, target_id: int) -> bool:
    """检查指定单位是否可以攻击目标单位"""
    attacker = Actor(attacker_id)
    target = Actor(target_id)
    return api.can_attack_target(attacker, target)


def stop_units(actor_ids: List[int]) -> str:
    """停止一批单位当前行动"""
    actors = [Actor(i) for i in actor_ids]
    api.stop(actors)
    return "ok"


# ==================== 特殊操作工具 ====================

def select_units(type: List[str], faction: str, range: str, restrain: List[dict]) -> str:
    """选中符合条件的单位"""
    api.select_units(TargetsQueryParam(type=type, faction=faction, range=range, restrain=restrain))
    return "ok"


def form_group(actor_ids: List[int], group_id: int) -> str:
    """为一批单位编组"""
    actors = [Actor(i) for i in actor_ids]
    api.form_group(actors, group_id)
    return "ok"


def deploy_units(actor_ids: List[int]) -> str:
    """展开或部署指定单位列表"""
    actors = [Actor(i) for i in actor_ids]
    api.deploy_units(actors)
    return "ok"


def deploy_mcv_and_wait(wait_time: float = 1.0) -> str:
    """展开自己的基地车并等待指定时间"""
    api.deploy_mcv_and_wait(wait_time)
    return "ok"


def occupy(occupiers: List[int], targets: List[int]) -> str:
    """占领目标"""
    occ = [Actor(i) for i in occupiers]
    tgt = [Actor(i) for i in targets]
    api.occupy_units(occ, tgt)
    return "ok"


def occupy_units(occupier_ids: List[int], target_ids: List[int]) -> str:
    """占领指定目标单位"""
    occupiers = [Actor(i) for i in occupier_ids]
    targets = [Actor(i) for i in target_ids]
    api.occupy_units(occupiers, targets)
    return "ok"


def repair_units(actor_ids: List[int]) -> str:
    """修复一批单位"""
    actors = [Actor(i) for i in actor_ids]
    api.repair_units(actors)
    return "ok"


def set_rally_point(actor_ids: List[int], x: int, y: int) -> str:
    """为指定建筑设置集结点"""
    actors = [Actor(i) for i in actor_ids]
    api.set_rally_point(actors, Location(x, y))
    return "ok"


# ==================== 地图与路径工具 ====================

def find_path(actor_ids: List[int], dest_x: int, dest_y: int, method: str) -> List[Dict[str, int]]:
    """为单位寻找路径"""
    actors = [Actor(i) for i in actor_ids]
    path = api.find_path(actors, Location(dest_x, dest_y), method)
    return [{"x": p.x, "y": p.y} for p in path]


def visible_query(x: int, y: int) -> bool:
    """查询指定坐标是否在视野中"""
    return api.visible_query(Location(x, y))


def explorer_query(x: int, y: int) -> bool:
    """查询指定坐标是否已探索"""
    return api.explorer_query(Location(x, y))


def get_unexplored_nearby_positions(
        map_result: Dict[str, Any],
        current_x: int,
        current_y: int,
        max_distance: int
) -> List[Dict[str, int]]:
    """获取当前位置附近尚未探索的坐标列表"""
    mq = MapQueryResult(
        MapWidth=map_result["width"],
        MapHeight=map_result["height"],
        Height=map_result["heightMap"],
        IsVisible=map_result["visible"],
        IsExplored=map_result["explored"],
        Terrain=map_result["terrain"],
        ResourcesType=map_result["resourcesType"],
        Resources=map_result["resources"]
    )
    locs = api.get_unexplored_nearby_positions(
        mq,
        Location(current_x, current_y),
        max_distance
    )
    return [{"x": loc.x, "y": loc.y} for loc in locs]


def map_query() -> Dict[str, Any]:
    """查询地图信息并返回序列化数据"""
    result = api.map_query()
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


# ==================== 玩家信息工具 ====================

def player_base_info_query() -> Dict[str, Any]:
    """查询玩家基地的资源、电力等基础信息"""
    info = api.player_base_info_query()
    return {
        "cash": info.Cash,
        "resources": info.Resources,
        "power": info.Power,
        "powerDrained": info.PowerDrained,
        "powerProvided": info.PowerProvided
    }


def screen_info_query() -> Dict[str, Any]:
    """查询当前屏幕信息"""
    info = api.screen_info_query()
    return {
        "screenMin": {"x": info.ScreenMin.x, "y": info.ScreenMin.y},
        "screenMax": {"x": info.ScreenMax.x, "y": info.ScreenMax.y},
        "isMouseOnScreen": info.IsMouseOnScreen,
        "mousePosition": {"x": info.MousePosition.x, "y": info.MousePosition.y}
    }


def unit_attribute_query(actor_ids: List[int]) -> Dict[str, Any]:
    """查询指定单位的属性及其攻击范围内的目标"""
    actors = [Actor(i) for i in actor_ids]
    return api.unit_attribute_query(actors)


# ==================== 工具描述列表 ====================

available_tools = [
    # 基础查询工具
    {
        "type": "function",
        "function": {
            "name": "get_game_state",
            "description": "获取当前游戏的整体状态，包括玩家的现金、资源储备、电力状况以及当前屏幕内所有可见的单位列表。这是了解游戏全局状况的主要接口。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "visible_units",
            "description": "根据指定条件查询当前可见的所有单位。可以按单位类型、所属阵营、范围和其他约束条件进行精确筛选。返回符合条件的单位详细信息列表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要查询的单位类型列表，如['步兵', '坦克']，空列表表示所有类型"
                    },
                    "faction": {
                        "type": "string",
                        "description": "单位所属阵营：'自己'、'敌人'、'中立'或'任意'"
                    },
                    "range": {
                        "type": "string",
                        "description": "查询范围：'screen'(屏幕内)、'all'(全地图)或'area'(指定区域)"
                    },
                    "restrain": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "额外的约束条件列表，如[{'visible': True}]表示只查询可见单位"
                    }
                },
                "required": ["type", "faction", "range", "restrain"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_actor",
            "description": "查询符合指定条件的所有Actor单位。这是一个通用的单位查询接口，可以获取单位的ID、类型、阵营、位置和血量等详细信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "单位类型列表"
                    },
                    "faction": {
                        "type": "string",
                        "description": "阵营筛选"
                    },
                    "range": {
                        "type": "string",
                        "description": "查询范围"
                    },
                    "restrain": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "约束条件"
                    }
                },
                "required": ["type", "faction", "range", "restrain"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_actor_by_id",
            "description": "根据指定的Actor ID获取单个单位的详细信息。如果单位不存在或已被摧毁，返回None。适用于追踪特定单位的状态。",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_id": {
                        "type": "integer",
                        "description": "要查询的单位ID"
                    }
                },
                "required": ["actor_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_actor",
            "description": "更新指定单位的信息并返回其最新状态。用于刷新单位的位置、血量等动态属性。如果单位已死亡则返回None。",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_id": {
                        "type": "integer",
                        "description": "要更新的单位ID"
                    }
                },
                "required": ["actor_id"]
            }
        }
    },

    # 生产相关工具
    {
        "type": "function",
        "function": {
            "name": "produce",
            "description": "生产指定类型和数量的单位或建筑。对于建筑会自动放置。返回生产任务ID，可用于后续跟踪生产进度。如果无法生产返回-1。",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_type": {
                        "type": "string",
                        "description": "要生产的单位类型，如'步兵'、'坦克'、'电厂'等"
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "生产数量"
                    }
                },
                "required": ["unit_type", "quantity"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "can_produce",
            "description": "检查当前是否满足生产指定类型单位的条件，包括科技要求、建筑依赖和资源是否充足。",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_type": {
                        "type": "string",
                        "description": "要检查的单位类型"
                    }
                },
                "required": ["unit_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_production_queue",
            "description": "查询指定类型生产队列的详细状态，包括正在生产的项目、进度、剩余时间和队列中等待的项目。",
            "parameters": {
                "type": "object",
                "properties": {
                    "queue_type": {
                        "type": "string",
                        "description": "队列类型：'Building'(建筑)、'Defense'(防御)、'Infantry'(步兵)、'Vehicle'(载具)、'Aircraft'(飞机)或'Naval'(海军)"
                    }
                },
                "required": ["queue_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_production",
            "description": "管理生产队列中的项目，可以暂停、取消或恢复生产。操作会影响队列中的第一个项目。",
            "parameters": {
                "type": "object",
                "properties": {
                    "queue_type": {
                        "type": "string",
                        "description": "队列类型"
                    },
                    "action": {
                        "type": "string",
                        "description": "操作类型：'pause'(暂停)、'cancel'(取消)或'resume'(恢复)"
                    }
                },
                "required": ["queue_type", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ensure_can_build_wait",
            "description": "确保能够建造指定的建筑。如果缺少前置建筑，会自动递归建造所有依赖并等待完成。这是一个智能建造函数，会处理完整的科技树。",
            "parameters": {
                "type": "object",
                "properties": {
                    "building_name": {
                        "type": "string",
                        "description": "要建造的建筑名称，如'科技中心'、'雷达'等"
                    }
                },
                "required": ["building_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ensure_can_produce_unit",
            "description": "确保能够生产指定的单位。会自动检查并建造所需的生产建筑和科技建筑，等待全部完成后返回。",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_name": {
                        "type": "string",
                        "description": "要生产的单位名称，如'猛犸坦克'、'V2火箭'等"
                    }
                },
                "required": ["unit_name"]
            }
        }
    },

    # 单位移动工具
    {
        "type": "function",
        "function": {
            "name": "move_units",
            "description": "移动一批单位到指定的地图坐标。可以选择是否使用攻击移动模式（边移动边攻击遇到的敌人）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "要移动的单位ID列表"
                    },
                    "x": {
                        "type": "integer",
                        "description": "目标位置的X坐标"
                    },
                    "y": {
                        "type": "integer",
                        "description": "目标位置的Y坐标"
                    },
                    "attack_move": {
                        "type": "boolean",
                        "description": "是否使用攻击移动模式，默认为False"
                    }
                },
                "required": ["actor_ids", "x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_units_by_direction",
            "description": "按指定方向移动一批单位。方向可以是八个基本方向之一，距离以地图格子为单位。",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "要移动的单位ID列表"
                    },
                    "direction": {
                        "type": "string",
                        "description": "移动方向：'上'、'下'、'左'、'右'、'左上'、'左下'、'右上'或'右下'"
                    },
                    "distance": {
                        "type": "integer",
                        "description": "移动距离（格子数）"
                    }
                },
                "required": ["actor_ids", "direction", "distance"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_units_by_path",
            "description": "让一批单位沿着指定的路径点序列移动。单位会依次经过每个路径点，适用于巡逻或复杂路线移动。",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "要移动的单位ID列表"
                    },
                    "path": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "integer"},
                                "y": {"type": "integer"}
                            }
                        },
                        "description": "路径点列表，每个点包含x和y坐标"
                    }
                },
                "required": ["actor_ids", "path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_units_and_wait",
            "description": "移动单位到指定位置并等待其到达。会阻塞执行直到单位到达目标位置附近或超时。返回是否成功到达。",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "要移动的单位ID列表"
                    },
                    "x": {
                        "type": "integer",
                        "description": "目标X坐标"
                    },
                    "y": {
                        "type": "integer",
                        "description": "目标Y坐标"
                    },
                    "max_wait_time": {
                        "type": "number",
                        "description": "最大等待时间（秒），默认10秒"
                    },
                    "tolerance_dis": {
                        "type": "integer",
                        "description": "容忍的距离误差（格子数），默认1"
                    }
                },
                "required": ["actor_ids", "x", "y"]
            }
        }
    },

    # 相机控制工具
    {
        "type": "function",
        "function": {
            "name": "camera_move_to",
            "description": "将游戏视角（镜头）移动到指定的地图坐标位置。用于观察地图上的特定区域。",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "integer",
                        "description": "目标位置X坐标"
                    },
                    "y": {
                        "type": "integer",
                        "description": "目标位置Y坐标"
                    }
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "camera_move_dir",
            "description": "按指定方向移动游戏镜头。可以用于探索地图或调整视角。",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "移动方向：'上'、'下'、'左'、'右'等八个方向"
                    },
                    "distance": {
                        "type": "integer",
                        "description": "移动距离（格子数）"
                    }
                },
                "required": ["direction", "distance"]
            }
        }
    },
    {
        "type": "function","function": {
           "name": "move_camera_to",
           "description": "将游戏镜头快速定位到指定单位的当前位置。用于快速查看特定单位的状况。",
           "parameters": {
               "type": "object",
               "properties": {
                   "actor_id": {
                       "type": "integer",
                       "description": "要定位的单位ID"
                   }
               },
               "required": ["actor_id"]
           }
       }
   },

   # 战斗相关工具
   {
       "type": "function",
       "function": {
           "name": "attack",
           "description": "命令一个单位攻击指定的目标单位。攻击会持续进行直到目标被摧毁或收到新的命令。",
           "parameters": {
               "type": "object",
               "properties": {
                   "attacker_id": {
                       "type": "integer",
                       "description": "攻击单位的ID"
                   },
                   "target_id": {
                       "type": "integer",
                       "description": "目标单位的ID"
                   }
               },
               "required": ["attacker_id", "target_id"]
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "attack_target",
           "description": "命令指定单位攻击目标。与attack功能相同，提供备选接口。返回是否成功发起攻击。",
           "parameters": {
               "type": "object",
               "properties": {
                   "attacker_id": {
                       "type": "integer",
                       "description": "攻击单位的ID"
                   },
                   "target_id": {
                       "type": "integer",
                       "description": "目标单位的ID"
                   }
               },
               "required": ["attacker_id", "target_id"]
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "can_attack_target",
           "description": "检查一个单位是否能够攻击指定目标。会考虑射程、视野、单位类型等因素。",
           "parameters": {
               "type": "object",
               "properties": {
                   "attacker_id": {
                       "type": "integer",
                       "description": "攻击单位的ID"
                   },
                   "target_id": {
                       "type": "integer",
                       "description": "目标单位的ID"
                   }
               },
               "required": ["attacker_id", "target_id"]
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "stop_units",
           "description": "立即停止一批单位的当前行动，包括移动、攻击等。单位会在原地待命。",
           "parameters": {
               "type": "object",
               "properties": {
                   "actor_ids": {
                       "type": "array",
                       "items": {"type": "integer"},
                       "description": "要停止的单位ID列表"
                   }
               },
               "required": ["actor_ids"]
           }
       }
   },

   # 特殊操作工具
   {
       "type": "function",
       "function": {
           "name": "select_units",
           "description": "在游戏中选中符合条件的单位，相当于框选操作。选中后可以对这些单位统一下达命令。",
           "parameters": {
               "type": "object",
               "properties": {
                   "type": {
                       "type": "array",
                       "items": {"type": "string"},
                       "description": "要选中的单位类型"
                   },
                   "faction": {
                       "type": "string",
                       "description": "单位阵营"
                   },
                   "range": {
                       "type": "string",
                       "description": "选择范围"
                   },
                   "restrain": {
                       "type": "array",
                       "items": {"type": "object"},
                       "description": "额外约束条件"
                   }
               },
               "required": ["type", "faction", "range", "restrain"]
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "form_group",
           "description": "将一批单位编为一个控制组，方便后续快速选择和指挥。类似于RTS游戏中的Ctrl+数字键编组。",
           "parameters": {
               "type": "object",
               "properties": {
                   "actor_ids": {
                       "type": "array",
                       "items": {"type": "integer"},
                       "description": "要编组的单位ID列表"
                   },
                   "group_id": {
                       "type": "integer",
                       "description": "组号（通常为1-9）"
                   }
               },
               "required": ["actor_ids", "group_id"]
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "deploy_units",
           "description": "部署或展开指定的单位。主要用于展开基地车成为建造厂，或部署特殊单位进入防御模式。",
           "parameters": {
               "type": "object",
               "properties": {
                   "actor_ids": {
                       "type": "array",
                       "items": {"type": "integer"},
                       "description": "要部署的单位ID列表"
                   }
               },
               "required": ["actor_ids"]
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "deploy_mcv_and_wait",
           "description": "自动查找并展开己方的基地车（MCV），展开后等待指定时间确保部署完成。这是游戏开局的常用操作。",
           "parameters": {
               "type": "object",
               "properties": {
                   "wait_time": {
                       "type": "number",
                       "description": "展开后的等待时间（秒），默认1秒"
                   }
               },
               "required": []
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "occupy",
           "description": "命令工程师或特定单位占领中立建筑或敌方建筑。可用于占领油井增加收入或占领敌方建筑。",
           "parameters": {
               "type": "object",
               "properties": {
                   "occupiers": {
                       "type": "array",
                       "items": {"type": "integer"},
                       "description": "执行占领的单位ID列表（通常是工程师）"
                   },
                   "targets": {
                       "type": "array",
                       "items": {"type": "integer"},
                       "description": "要占领的目标建筑ID列表"
                   }
               },
               "required": ["occupiers", "targets"]
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "occupy_units",
           "description": "占领指定的目标单位或建筑。功能与occupy相同，提供备选接口。",
           "parameters": {
               "type": "object",
               "properties": {
                   "occupier_ids": {
                       "type": "array",
                       "items": {"type": "integer"},
                       "description": "占领单位ID列表"
                   },
                   "target_ids": {
                       "type": "array",
                       "items": {"type": "integer"},
                       "description": "目标ID列表"
                   }
               },
               "required": ["occupier_ids", "target_ids"]
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "repair_units",
           "description": "修复受损的单位或建筑。对于载具需要有维修中心，建筑会自动修复。消耗资金。",
           "parameters": {
               "type": "object",
               "properties": {
                   "actor_ids": {
                       "type": "array",
                       "items": {"type": "integer"},
                       "description": "要修复的单位ID列表"
                   }
               },
               "required": ["actor_ids"]
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "set_rally_point",
           "description": "为生产建筑设置集结点。新生产的单位会自动移动到集结点位置，便于部队集结。",
           "parameters": {
               "type": "object",
               "properties": {
                   "actor_ids": {
                       "type": "array",
                       "items": {"type": "integer"},
                       "description": "生产建筑的ID列表"
                   },
                   "x": {
                       "type": "integer",
                       "description": "集结点X坐标"
                   },
                   "y": {
                       "type": "integer",
                       "description": "集结点Y坐标"
                   }
               },
               "required": ["actor_ids", "x", "y"]
           }
       }
   },

   # 地图与路径工具
   {
       "type": "function",
       "function": {
           "name": "find_path",
           "description": "为单位计算到目标位置的移动路径。支持不同的寻路策略，返回路径点序列。",
           "parameters": {
               "type": "object",
               "properties": {
                   "actor_ids": {
                       "type": "array",
                       "items": {"type": "integer"},
                       "description": "需要寻路的单位ID列表"
                   },
                   "dest_x": {
                       "type": "integer",
                       "description": "目标位置X坐标"
                   },
                   "dest_y": {
                       "type": "integer",
                       "description": "目标位置Y坐标"
                   },
                   "method": {
                       "type": "string",
                       "description": "寻路方法：'最短路'、'左路'或'右路'"
                   }
               },
               "required": ["actor_ids", "dest_x", "dest_y", "method"]
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "visible_query",
           "description": "查询地图上指定坐标点当前是否在视野范围内（战争迷雾中的可见区域）。",
           "parameters": {
               "type": "object",
               "properties": {
                   "x": {
                       "type": "integer",
                       "description": "查询位置的X坐标"
                   },
                   "y": {
                       "type": "integer",
                       "description": "查询位置的Y坐标"
                   }
               },
               "required": ["x", "y"]
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "explorer_query",
           "description": "查询地图上指定坐标是否已经被探索过（曾经被侦察过的区域）。",
           "parameters": {
               "type": "object",
               "properties": {
                   "x": {
                       "type": "integer",
                       "description": "查询位置的X坐标"
                   },
                   "y": {
                       "type": "integer",
                       "description": "查询位置的Y坐标"
                   }
               },
               "required": ["x", "y"]
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "get_unexplored_nearby_positions",
           "description": "获取指定位置附近所有未探索的地图坐标，用于指导侦察单位探索地图。",
           "parameters": {
               "type": "object",
               "properties": {
                   "map_result": {
                       "type": "object",
                       "description": "地图查询结果对象（从map_query获取）"
                   },
                   "current_x": {
                       "type": "integer",
                       "description": "当前位置X坐标"
                   },
                   "current_y": {
                       "type": "integer",
                       "description": "当前位置Y坐标"
                   },
                   "max_distance": {
                       "type": "integer",
                       "description": "搜索的最大距离（曼哈顿距离）"
                   }
               },
               "required": ["map_result", "current_x", "current_y", "max_distance"]
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "map_query",
           "description": "获取完整的地图信息，包括地图大小、地形、高度、资源分布、可见性和探索状态等详细数据。",
           "parameters": {
               "type": "object",
               "properties": {},
               "required": []
           }
       }
   },

   # 玩家信息工具
   {
       "type": "function",
       "function": {
           "name": "player_base_info_query",
           "description": "查询玩家的基地信息，包括当前现金、资源储备、电力供应、电力消耗等经济状态数据。",
           "parameters": {
               "type": "object",
               "properties": {},
               "required": []
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "screen_info_query",
           "description": "获取当前游戏屏幕的视野信息，包括屏幕边界坐标、鼠标位置等界面相关数据。",
           "parameters": {
               "type": "object",
               "properties": {},
               "required": []
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "unit_attribute_query",
           "description": "查询指定单位的详细属性信息，包括攻击力、防御力、射程，以及当前攻击范围内的所有目标。",
           "parameters": {
               "type": "object",
               "properties": {
                   "actor_ids": {
                       "type": "array",
                       "items": {"type": "integer"},
                       "description": "要查询属性的单位ID列表"
                   }
               },
               "required": ["actor_ids"]
           }
       }
   },
   {
       "type": "function",
       "function": {
           "name": "move_units_by_location",
           "description": "移动单位到指定坐标位置。与move_units功能相同，提供备选接口名称。",
           "parameters": {
               "type": "object",
               "properties": {
                   "actor_ids": {
                       "type": "array",
                       "items": {"type": "integer"},
                       "description": "要移动的单位ID列表"
                   },
                   "x": {
                       "type": "integer",
                       "description": "目标X坐标"
                   },
                   "y": {
                       "type": "integer",
                       "description": "目标Y坐标"
                   },
                   "attack_move": {
                       "type": "boolean",
                       "description": "是否使用攻击移动"
                   }
               },
               "required": ["actor_ids", "x", "y"]
           }
       }
   }
]

# 工具函数总数统计
def count_tools():
   """统计可用工具数量"""
   unique_names = set()
   for tool in available_tools:
       unique_names.add(tool["function"]["name"])
   return len(unique_names)

# 打印工具列表
def list_all_tools():
   """列出所有可用工具"""
   print(f"总共有 {count_tools()} 个可用工具：\n")
   categories = {
       "基础查询": ["get_game_state", "visible_units", "query_actor", "get_actor_by_id", "update_actor"],
       "生产管理": ["produce", "can_produce", "query_production_queue", "manage_production",
                  "ensure_can_build_wait", "ensure_can_produce_unit"],
       "单位移动": ["move_units", "move_units_by_location", "move_units_by_direction",
                  "move_units_by_path", "move_units_and_wait"],
       "相机控制": ["camera_move_to", "camera_move_dir", "move_camera_to"],
       "战斗操作": ["attack", "attack_target", "can_attack_target", "stop_units"],
       "特殊操作": ["select_units", "form_group", "deploy_units", "deploy_mcv_and_wait",
                  "occupy", "occupy_units", "repair_units", "set_rally_point"],
       "地图路径": ["find_path", "visible_query", "explorer_query",
                  "get_unexplored_nearby_positions", "map_query"],
       "玩家信息": ["player_base_info_query", "screen_info_query", "unit_attribute_query"]
   }

   for category, tools in categories.items():
       print(f"\n{category}类 ({len(tools)}个):")
       for tool in tools:
           tool_info = next((t for t in available_tools if t["function"]["name"] == tool), None)
           if tool_info:
               desc = tool_info["function"]["description"][:60] + "..." if len(tool_info["function"]["description"]) > 60 else tool_info["function"]["description"]
               print(f"  - {tool}: {desc}")

if __name__ == "__main__":
   # 测试统计
   print(f"工具文件已加载")
   print(f"总共定义了 {count_tools()} 个工具函数")
   print(f"工具描述列表包含 {len(available_tools)} 个工具定义")

   # 可选：列出所有工具
   # list_all_tools()
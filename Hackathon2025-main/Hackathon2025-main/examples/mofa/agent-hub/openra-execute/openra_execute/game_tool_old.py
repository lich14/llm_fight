# mcp_server/tools.py
# 这个脚本不依赖于 mcp 框架，只包含可调用的函数
import os
import sys

sys.path.append(os.getenv('OPENRA_PATH','.'))

from OpenRA_Copilot_Library import GameAPI
from OpenRA_Copilot_Library.models import Location, TargetsQueryParam, Actor, MapQueryResult
from typing import List, Dict, Any, Optional

# 单例 GameAPI 客户端
api = GameAPI(host="localhost", port=7445, language="zh")

# 所有函数都已移除 @mcp.tool 装饰器

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

def produce(unit_type: str, quantity: int) -> int:
    """生产指定类型和数量的单位，返回生产任务 ID"""
    wait_id = api.produce(unit_type, quantity, auto_place_building=True)
    return wait_id or -1

def move_units(actor_ids: List[int], x: int, y: int, attack_move: bool = False) -> str:
    """移动一批单位到指定坐标"""
    actors = [Actor(i) for i in actor_ids]
    loc = Location(x, y)
    api.move_units_by_location(actors, loc, attack_move=attack_move)
    return "ok"

def camera_move_to(x: int, y: int) -> str:
    """将镜头移动到指定坐标"""
    api.move_camera_by_location(Location(x, y))
    return "ok"

def camera_move_dir(direction: str, distance: int) -> str:
    """按方向移动镜头"""
    api.move_camera_by_direction(direction, distance)
    return "ok"

def can_produce(unit_type: str) -> bool:
    """检查是否可生产某类型单位"""
    return api.can_produce(unit_type)

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

def select_units(type: List[str], faction: str, range: str, restrain: List[dict]) -> str:
    """选中符合条件的单位"""
    api.select_units(TargetsQueryParam(type=type, faction=faction, range=range, restrain=restrain))
    return "ok"

def form_group(actor_ids: List[int], group_id: int) -> str:
    """为一批单位编组"""
    actors = [Actor(i) for i in actor_ids]
    api.form_group(actors, group_id)
    return "ok"

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

def attack(attacker_id: int, target_id: int) -> bool:
    """发起一次攻击"""
    atk = Actor(attacker_id); tgt = Actor(target_id)
    return api.attack_target(atk, tgt)

def occupy(occupiers: List[int], targets: List[int]) -> str:
    """占领目标"""
    occ = [Actor(i) for i in occupiers]
    tgt = [Actor(i) for i in targets]
    api.occupy_units(occ, tgt)
    return "ok"

def find_path(actor_ids: List[int], dest_x: int, dest_y: int, method: str) -> List[Dict[str,int]]:
    """为单位寻找路径"""
    actors = [Actor(i) for i in actor_ids]
    path = api.find_path(actors, Location(dest_x, dest_y), method)
    return [{"x": p.x, "y": p.y} for p in path]

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

def deploy_units(actor_ids: List[int]) -> str:
    """展开或部署指定单位列表"""
    actors = [Actor(i) for i in actor_ids]
    api.deploy_units(actors)
    return "ok"

def move_camera_to(actor_id: int) -> str:
    """将镜头移动到指定 Actor 的位置"""
    api.move_camera_to(Actor(actor_id))
    return "ok"

def occupy_units(occupier_ids: List[int], target_ids: List[int]) -> str:
    """占领指定目标单位"""
    occupiers = [Actor(i) for i in occupier_ids]
    targets = [Actor(i) for i in target_ids]
    api.occupy_units(occupiers, targets)
    return "ok"

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

def repair_units(actor_ids: List[int]) -> str:
    """修复一批单位"""
    actors = [Actor(i) for i in actor_ids]
    api.repair_units(actors)
    return "ok"

def stop_units(actor_ids: List[int]) -> str:
    """停止一批单位当前行动"""
    actors = [Actor(i) for i in actor_ids]
    api.stop(actors)
    return "ok"

def visible_query(x: int, y: int) -> bool:
    """查询指定坐标是否在视野中"""
    return api.visible_query(Location(x, y))

def explorer_query(x: int, y: int) -> bool:
    """查询指定坐标是否已探索"""
    return api.explorer_query(Location(x, y))

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

def unit_attribute_query(actor_ids: List[int]) -> Dict[str, Any]:
    """查询指定单位的属性及其攻击范围内的目标"""
    actors = [Actor(i) for i in actor_ids]
    return api.unit_attribute_query(actors)

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
# @RAMCP.tool(name="deploy_mcv_and_wait",description="展开自己的基地车并等待指定时间")
def deploy_mcv_and_wait(wait_time: float = 1.0) -> str:
    """
    Args:
        wait_time (float): 展开后的等待时间（秒），默认 1.0
    """
    api.deploy_mcv_and_wait(wait_time)
    return "ok"
def screen_info_query() -> Dict[str, Any]:
    """查询当前屏幕信息"""
    info = api.screen_info_query()
    return {
        "screenMin": {"x": info.ScreenMin.x, "y": info.ScreenMin.y},
        "screenMax": {"x": info.ScreenMax.x, "y": info.ScreenMax.y},
        "isMouseOnScreen": info.IsMouseOnScreen,
        "mousePosition": {"x": info.MousePosition.x, "y": info.MousePosition.y}
    }

def set_rally_point(actor_ids: List[int], x: int, y: int) -> str:
    """为指定建筑设置集结点"""
    actors = [Actor(i) for i in actor_ids]
    api.set_rally_point(actors, Location(x, y))
    return "ok"

# 创建一个字典来映射函数名称和函数对象
# 这对于通过字符串名称动态调用函数非常有用
available_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_game_state",
            "description": "返回玩家资源、电力和可见单位列表",
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
            "description": "根据条件查询可见单位",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "单位类型列表，例如 ['步兵', '坦克']"
                    },
                    "faction": {
                        "type": "string",
                        "description": "阵营，例如 '盟军', '苏军', '中立'"
                    },
                    "range": {
                        "type": "string",
                        "description": "查询范围，例如 'screen'（屏幕内）, 'all'（所有）"
                    },
                    "restrain": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "附加限制条件，例如 [{'hp_percent_min': 50}]"
                    }
                },
                "required": ["type", "faction", "range", "restrain"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "produce",
            "description": "生产指定类型和数量的单位，返回生产任务 ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_type": {
                        "type": "string",
                        "description": "要生产的单位类型"
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
            "name": "move_units",
            "description": "移动一批单位到指定坐标",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "要移动的单位 ID 列表"
                    },
                    "x": {
                        "type": "integer",
                        "description": "目标位置的 X 坐标"
                    },
                    "y": {
                        "type": "integer",
                        "description": "目标位置的 Y 坐标"
                    },
                    "attack_move": {
                        "type": "boolean",
                        "description": "是否为攻击性移动"
                    }
                },
                "required": ["actor_ids", "x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "camera_move_to",
            "description": "将镜头移动到指定坐标",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"}
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "camera_move_dir",
            "description": "按方向移动镜头",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "移动方向，例如 '上', '下', '左', '右'"
                    },
                    "distance": {
                        "type": "integer",
                        "description": "移动距离"
                    }
                },
                "required": ["direction", "distance"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "can_produce",
            "description": "检查是否可生产某类型单位",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_type": {
                        "type": "string",
                        "description": "单位类型"
                    }
                },
                "required": ["unit_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_units_by_location",
            "description": "把一批单位移动到指定坐标",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "要移动的单位 ID 列表"
                    },
                    "x": {"type": "integer", "description": "目标位置的 X 坐标"},
                    "y": {"type": "integer", "description": "目标位置的 Y 坐标"},
                    "attack_move": {"type": "boolean", "description": "是否为攻击性移动，默认为 False"}
                },
                "required": ["actor_ids", "x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_units_by_direction",
            "description": "按方向移动一批单位",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "要移动的单位 ID 列表"
                    },
                    "direction": {
                        "type": "string",
                        "description": "移动方向，例如 '上', '下', '左', '右'"
                    },
                    "distance": {
                        "type": "integer",
                        "description": "移动距离"
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
            "description": "沿指定路径移动一批单位",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "要移动的单位 ID 列表"
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
                        "description": "路径点列表，每个点为 {'x': int, 'y': int}"
                    }
                },
                "required": ["actor_ids", "path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_units",
            "description": "选中符合条件的单位",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "faction": {"type": "string"},
                    "range": {"type": "string"},
                    "restrain": {
                        "type": "array",
                        "items": {"type": "object"}
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
            "description": "为一批单位编组",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "要分组的单位 ID 列表"
                    },
                    "group_id": {
                        "type": "integer",
                        "description": "群组 ID"
                    }
                },
                "required": ["actor_ids", "group_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_actor",
            "description": "查询单位列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "faction": {"type": "string"},
                    "range": {"type": "string"},
                    "restrain": {
                        "type": "array",
                        "items": {"type": "object"}
                    }
                },
                "required": ["type", "faction", "range", "restrain"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "attack",
            "description": "发起一次攻击",
            "parameters": {
                "type": "object",
                "properties": {
                    "attacker_id": {"type": "integer"},
                    "target_id": {"type": "integer"}
                },
                "required": ["attacker_id", "target_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "occupy",
            "description": "占领目标",
            "parameters": {
                "type": "object",
                "properties": {
                    "occupiers": {
                        "type": "array",
                        "items": {"type": "integer"}
                    },
                    "targets": {
                        "type": "array",
                        "items": {"type": "integer"}
                    }
                },
                "required": ["occupiers", "targets"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_path",
            "description": "为单位寻找路径",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_ids": {
                        "type": "array",
                        "items": {"type": "integer"}
                    },
                    "dest_x": {"type": "integer"},
                    "dest_y": {"type": "integer"},
                    "method": {
                        "type": "string",
                        "description": "寻路方法，必须在 {'最短路', '左路', '右路'} 中"
                    }
                },
                "required": ["actor_ids", "dest_x", "dest_y", "method"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_actor_by_id",
            "description": "根据 Actor ID 获取单个单位的信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_id": {"type": "integer"}
                },
                "required": ["actor_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_actor",
            "description": "根据 actor_id 更新该单位的信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_id": {"type": "integer"}
                },
                "required": ["actor_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deploy_units",
            "description": "展开或部署指定单位列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_ids": {
                        "type": "array",
                        "items": {"type": "integer"}
                    }
                },
                "required": ["actor_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_camera_to",
            "description": "将镜头移动到指定 Actor 的位置",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_id": {"type": "integer"}
                },
                "required": ["actor_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "occupy_units",
            "description": "占领指定目标单位",
            "parameters": {
                "type": "object",
                "properties": {
                    "occupier_ids": {
                        "type": "array",
                        "items": {"type": "integer"}
                    },
                    "target_ids": {
                        "type": "array",
                        "items": {"type": "integer"}
                    }
                },
                "required": ["occupier_ids", "target_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "attack_target",
            "description": "由指定单位发起对目标单位的攻击",
            "parameters": {
                "type": "object",
                "properties": {
                    "attacker_id": {"type": "integer"},
                    "target_id": {"type": "integer"}
                },
                "required": ["attacker_id", "target_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "can_attack_target",
            "description": "检查指定单位是否可以攻击目标单位",
            "parameters": {
                "type": "object",
                "properties": {
                    "attacker_id": {"type": "integer"},
                    "target_id": {"type": "integer"}
                },
                "required": ["attacker_id", "target_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "repair_units",
            "description": "修复一批单位",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_ids": {
                        "type": "array",
                        "items": {"type": "integer"}
                    }
                },
                "required": ["actor_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stop_units",
            "description": "停止一批单位当前行动",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_ids": {
                        "type": "array",
                        "items": {"type": "integer"}
                    }
                },
                "required": ["actor_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "visible_query",
            "description": "查询指定坐标是否在视野中",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"}
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explorer_query",
            "description": "查询指定坐标是否已探索",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"}
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_production_queue",
            "description": "查询指定类型的生产队列",
            "parameters": {
                "type": "object",
                "properties": {
                    "queue_type": {
                        "type": "string",
                        "description": "队列类型，必须是 'Building', 'Defense', 'Infantry', 'Vehicle', 'Aircraft' 或 'Naval'"
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
            "description": "管理生产队列中的项目（暂停、取消或继续）",
            "parameters": {
                "type": "object",
                "properties": {
                    "queue_type": {
                        "type": "string",
                        "description": "队列类型，必须是 'Building', 'Defense', 'Infantry', 'Vehicle', 'Aircraft' 或 'Naval'"
                    },
                    "action": {
                        "type": "string",
                        "description": "操作类型，必须是 'pause', 'cancel' 或 'resume'"
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
            "description": "确保指定建筑已存在，若不存在则递归建造其所有依赖并等待完成",
            "parameters": {
                "type": "object",
                "properties": {
                    "building_name": {
                        "type": "string",
                        "description": "建筑名称（中文）"
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
            "description": "确保能生产指定单位（会自动补齐依赖建筑并等待完成）",
            "parameters": {
                "type": "object",
                "properties": {
                    "unit_name": {
                        "type": "string",
                        "description": "要生产的单位名称（中文）"
                    }
                },
                "required": ["unit_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_unexplored_nearby_positions",
            "description": "获取当前位置附近尚未探索的坐标列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "map_result": {
                        "type": "object",
                        "description": "map_query 返回的地图信息字典"
                    },
                    "current_x": {"type": "integer"},
                    "current_y": {"type": "integer"},
                    "max_distance": {"type": "integer"}
                },
                "required": ["map_result", "current_x", "current_y", "max_distance"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_units_and_wait",
            "description": "移动一批单位到指定位置并等待到达或超时",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_ids": {
                        "type": "array",
                        "items": {"type": "integer"}
                    },
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "max_wait_time": {"type": "number"},
                    "tolerance_dis": {"type": "integer"}
                },
                "required": ["actor_ids", "x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "unit_attribute_query",
            "description": "查询指定单位的属性及其攻击范围内的目标",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_ids": {
                        "type": "array",
                        "items": {"type": "integer"}
                    }
                },
                "required": ["actor_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "map_query",
            "description": "查询地图信息并返回序列化数据",
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
            "name": "player_base_info_query",
            "description": "查询玩家基地的资源、电力等基础信息",
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
            "description": "查询当前屏幕信息",
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
            "name": "set_rally_point",
            "description": "为指定建筑设置集结点",
            "parameters": {
                "type": "object",
                "properties": {
                    "actor_ids": {
                        "type": "array",
                        "items": {"type": "integer"}
                    },
                    "x": {"type": "integer"},
                    "y": {"type": "integer"}
                },
                "required": ["actor_ids", "x", "y"]
            }
        }
    },
{
    "type": "function",
    "function": {
        "name": "deploy_mcv_and_wait",
        "description": "部署或者展开基地车并在指定时间后返回",
        "parameters": {
            "type": "object",
            "properties": {
                "wait_time": {
                    "type": "number",
                    "description": "展开后的等待时间（秒），默认 1.0"
                }
            },
            "required": []
        }
    }
}
]







# 你可以通过这个字典来调用函数
# 例如:
# result = available_functions["produce"]("矿车", 1)
# print(f"生产任务 ID: {result}")
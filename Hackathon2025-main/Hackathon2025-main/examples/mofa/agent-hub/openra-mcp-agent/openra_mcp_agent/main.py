#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import sys
from typing import Any, Dict, List
from dotenv import load_dotenv
from mofa.agent_build.base.base_agent import run_agent, MofaAgent
from openai import OpenAI

# 加载环境变量
load_dotenv()
from OpenRA_Copilot_Library import GameAPI
from OpenRA_Copilot_Library.models import Location, TargetsQueryParam, Actor,MapQueryResult
from typing import List, Dict, Any
from mcp.server.fastmcp import FastMCP
from typing import Optional

# 单例 GameAPI 客户端
api = GameAPI(host="localhost", port=7445, language="zh")
#mcp实例
mcp = FastMCP()


@mcp.tool(name="get_game_state", description="返回玩家资源、电力和可见单位列表")
def get_game_state() -> Dict[str, Any]:
    # 1) 玩家基础信息
    info = api.player_base_info_query()
    # 2) 屏幕内可见单位
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



@mcp.tool(name="visible_units", description="根据条件查询可见单位")
def visible_units(type: List[str],faction: str,range: str,restrain: List[dict]) -> List[Dict[str, Any]]:
    # 修复单值传入错误
    if isinstance(type, str):
        type = [type]
    if isinstance(restrain, dict):  # 有时也会传成一个字典
        restrain = [restrain]
    elif isinstance(restrain, bool):  # LLM 有时会给布尔值
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

@mcp.tool(name="produce",description="生产指定类型和数量的单位，返回生产任务 ID")
def produce(unit_type: str, quantity: int) -> int:
    '''生产指定数量的Actor

    Args:
        unit_type (str): Actor类型
        quantity (int): 生产数量
        auto_place_building (bool, optional): 是否在生产完成后使用随机位置自动放置建筑，仅对建筑类型有效

    Returns:
        int: 生产任务的 waitId
        None: 如果任务创建失败
    '''
    wait_id = api.produce(unit_type, quantity, auto_place_building=True)
    return wait_id or -1

@mcp.tool(name="move_units",description="移动一批单位到指定坐标")
def move_units(actor_ids: List[int], x: int, y: int, attack_move: bool = False) -> str:
    #     Args:
    #     actors(List[Actor]): 要移动的Actor列表
    #     location(Location): 目标位置
    #     attack_move(bool): 是否为攻击性移动
    actors = [Actor(i) for i in actor_ids]
    loc = Location(x, y)
    api.move_units_by_location(actors, loc, attack_move=attack_move)
    return "ok"

# —— 相机控制 ——
@mcp.tool(name="camera_move_to", description="将镜头移动到指定坐标")
def camera_move_to(x: int, y: int) -> str:
    api.move_camera_by_location(Location(x, y))
    return "ok"

@mcp.tool(name="camera_move_dir", description="按方向移动镜头")
def camera_move_dir(direction: str, distance: int) -> str:
    api.move_camera_by_direction(direction, distance)
    return "ok"


# —— 生产相关 ——
@mcp.tool(name="can_produce", description="检查是否可生产某类型单位")
def can_produce(unit_type: str) -> bool:
    '''检查是否可以生产指定类型的Actor

    Args:
        unit_type (str): Actor类型，必须在 {ALL_UNITS} 中

    Returns:
        bool: 是否可以生产

    '''
    return api.can_produce(unit_type)


# @RAMCP.tool(name="produce_wait", description="发起并等待生产完成")
# def produce_wait(unit_type: str, quantity: int, auto_place: bool = True) -> bool:
#     '''生产指定数量的Actor并等待生产完成
#
#     Args:
#         unit_type (str): Actor类型
#         quantity (int): 生产数量
#         auto_place_building (bool, optional): 是否在生产完成后使用随机位置自动放置建筑，仅对建筑类型有效
#
#     Raises:
#         GameAPIError: 当生产或等待过程中发生错误时
#     '''
#     try:
#         api.produce_wait(unit_type, quantity, auto_place)
#         return True
#     except Exception:
#         return False

# @RAMCP.tool(name="is_ready",description="检查指定生产任务是否已完成")
# def is_ready(wait_id: int) -> bool:
#     """
#     Args:
#         wait_id (int): 生产任务的 ID
#     Returns:
#         bool: 生产任务是否已完成
#     """
#     return api.is_ready(wait_id)

# @RAMCP.tool(name="wait",description="等待指定生产任务完成，或超时返回 False")
# def wait(wait_id: int, max_wait_time: float = 20.0) -> bool:
#     """
#     Args:
#         wait_id (int): 生产任务的 ID
#         max_wait_time (float): 最大等待时间（秒），默认 20.0
#     Returns:
#         bool: 是否在指定时间内完成（False 表示超时）
#     """
#     return api.wait(wait_id, max_wait_time)


# —— 单位移动 ——
@mcp.tool(name="move_units_by_location", description="把一批单位移动到指定坐标")
def move_units_by_location(actor_ids: List[int], x: int, y: int, attack_move: bool = False) -> str:
    '''移动单位到指定位置

    Args:
        actors (List[Actor]): 要移动的Actor列表
        location (Location): 目标位置
        attack_move (bool): 是否为攻击性移动

    Raises:
        GameAPIError: 当移动命令执行失败时
    '''
    actors = [Actor(i) for i in actor_ids]
    api.move_units_by_location(actors, Location(x, y), attack_move)
    return "ok"

@mcp.tool(name="move_units_by_direction", description="按方向移动一批单位")
def move_units_by_direction(actor_ids: List[int], direction: str, distance: int) -> str:
    actors = [Actor(i) for i in actor_ids]
    api.move_units_by_direction(actors, direction, distance)
    return "ok"

@mcp.tool(name="move_units_by_path", description="沿指定路径移动一批单位")
def move_units_by_path(actor_ids: List[int], path: List[Dict[str, int]]) -> str:
    '''
    沿指定路径移动一批单位。

    Args:
        actor_ids (List[int]): 要移动的单位 ID 列表。
        path (List[Dict[str, int]]): 路径点列表，每个点为 {"x": int, "y": int} 形式。

    Returns:
        str: "ok" 表示移动命令已发送成功。

    Raises:
        GameAPIError: 当移动命令执行失败时。
    '''
    actors = [Actor(i) for i in actor_ids]
    locs = [Location(p["x"], p["y"]) for p in path]
    api.move_units_by_path(actors, locs)
    return "ok"


# —— 查询与选择 ——
@mcp.tool(name="select_units", description="选中符合条件的单位")
def select_units(type: List[str], faction: str, range: str, restrain: List[dict]) -> str:
    '''选中符合条件的Actor，指的是游戏中的选中操作

    Args:
        query_params (TargetsQueryParam): 查询参数

    Raises:
        GameAPIError: 当选择单位失败时
    '''
    api.select_units(TargetsQueryParam(type=type, faction=faction, range=range, restrain=restrain))
    return "ok"

@mcp.tool(name="form_group", description="为一批单位编组")
def form_group(actor_ids: List[int], group_id: int) -> str:
    '''将Actor编成编组

            Args:
                actors (List[Actor]): 要分组的Actor列表
                group_id (int): 群组 ID

            Raises:
                GameAPIError: 当编组失败时
            '''
    actors = [Actor(i) for i in actor_ids]
    api.form_group(actors, group_id)
    return "ok"

@mcp.tool(name="query_actor", description="查询单位列表")
def query_actor(type: List[str], faction: str, range: str, restrain: List[dict]) -> List[Dict[str, Any]]:
    '''查询符合条件的Actor，获取Actor应该使用的接口

    Args:
        query_params (TargetsQueryParam): 查询参数

    Returns:
        List[Actor]: 符合条件的Actor列表

    Raises:
        GameAPIError: 当查询Actor失败时
    '''
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


# —— 攻击与占领 ——
@mcp.tool(name="attack", description="发起一次攻击")
def attack(attacker_id: int, target_id: int) -> bool:
    '''攻击指定目标

    Args:
        attacker (Actor): 发起攻击的Actor
        target (Actor): 被攻击的目标

    Returns:
        bool: 是否成功发起攻击(如果目标不可见，或者不可达，或者攻击者已经死亡，都会返回false)

    Raises:
        GameAPIError: 当攻击命令执行失败时
    '''
    atk = Actor(attacker_id); tgt = Actor(target_id)
    return api.attack_target(atk, tgt)

@mcp.tool(name="occupy", description="占领目标")
def occupy(occupiers: List[int], targets: List[int]) -> str:
    '''占领目标

    Args:
        occupiers (List[Actor]): 执行占领的Actor列表
        targets (List[Actor]): 被占领的目标列表

    Raises:
        GameAPIError: 当占领行动失败时
    '''
    occ = [Actor(i) for i in occupiers]
    tgt = [Actor(i) for i in targets]
    api.occupy_units(occ, tgt)
    return "ok"


# —— 路径寻路 ——
@mcp.tool(name="find_path", description="为单位寻找路径")
def find_path(actor_ids: List[int], dest_x: int, dest_y: int, method: str) -> List[Dict[str,int]]:
    '''为Actor找到到目标的路径
    Args:
        actors (List[Actor]): 要移动的Actor列表
        destination (Location): 目标位置
        method (str): 寻路方法，必须在 {"最短路"，"左路"，"右路"} 中

    Returns:
        List[Location]: 路径点列表，第0个是目标点，最后一个是Actor当前位置，相邻的点都是八方向相连的点

    Raises:
        GameAPIError: 当寻路失败时
    '''
    actors = [Actor(i) for i in actor_ids]
    path = api.find_path(actors, Location(dest_x, dest_y), method)
    return [{"x": p.x, "y": p.y} for p in path]

@mcp.tool(name="get_actor_by_id",description="根据 Actor ID 获取单个单位的信息，如果不存在则返回 None"
)
def get_actor_by_id(actor_id: int) -> Optional[Dict[str, Any]]:
    """
    Args:
        actor_id (int): 要查询的 Actor ID
    Returns:
        Dict: 包含 actor_id, type, faction, position, hpPercent 的字典
        None: 如果该 ID 对应的 Actor 不存在
    """
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

@mcp.tool(name="update_actor",description="根据 actor_id 更新该单位的信息，并返回其最新状态")
def update_actor(actor_id: int) -> Optional[Dict[str, Any]]:
    """
    Args:
        actor_id (int): 要更新的 Actor ID
    Returns:
        Dict: 最新的 Actor 信息（如果成功），否则 None
    """
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


@mcp.tool(name="deploy_units",description="展开或部署指定单位列表")
def deploy_units(actor_ids: List[int]) -> str:
    """
    Args:
        actor_ids (List[int]): 要展开的单位 ID 列表
    Returns:
        str: 操作完成返回 "ok"
    """
    actors = [Actor(i) for i in actor_ids]
    api.deploy_units(actors)
    return "ok"



@mcp.tool(name="move_camera_to",description="将镜头移动到指定 Actor 的位置"
)
def move_camera_to(actor_id: int) -> str:
    """
    Args:
        actor_id (int): 目标 Actor 的 ID
    Returns:
        str: 操作完成返回 "ok"
    """
    api.move_camera_to(Actor(actor_id))
    return "ok"


@mcp.tool(name="occupy_units",description="占领指定目标单位")
def occupy_units(occupier_ids: List[int], target_ids: List[int]) -> str:
    """
    Args:
        occupier_ids (List[int]): 发起占领的单位 ID 列表
        target_ids (List[int]): 被占领的目标单位 ID 列表
    Returns:
        str: 操作完成返回 "ok"
    """
    occupiers = [Actor(i) for i in occupier_ids]
    targets = [Actor(i) for i in target_ids]
    api.occupy_units(occupiers, targets)
    return "ok"



@mcp.tool(name="attack_target",description="由指定单位发起对目标单位的攻击")
def attack_target(attacker_id: int, target_id: int) -> bool:
    """
    Args:
        attacker_id (int): 发起攻击的单位 ID
        target_id (int): 被攻击的目标单位 ID
    Returns:
        bool: 是否成功发起攻击
    """
    attacker = Actor(attacker_id)
    target = Actor(target_id)
    return api.attack_target(attacker, target)


@mcp.tool(name="can_attack_target",description="检查指定单位是否可以攻击目标单位")
def can_attack_target(attacker_id: int, target_id: int) -> bool:
    """
    Args:
        attacker_id (int): 攻击者的单位 ID
        target_id (int): 目标单位的 ID
    Returns:
        bool: 如果攻击者可以攻击目标（目标可见），返回 True，否则 False
    """
    attacker = Actor(attacker_id)
    target = Actor(target_id)
    return api.can_attack_target(attacker, target)


@mcp.tool(name="repair_units",description="修复一批单位")
def repair_units(actor_ids: List[int]) -> str:
    """
    Args:
        actor_ids (List[int]): 要修复的单位 ID 列表
    Returns:
        str: 操作完成返回 "ok"
    """
    actors = [Actor(i) for i in actor_ids]
    api.repair_units(actors)
    return "ok"


@mcp.tool(name="stop_units",description="停止一批单位当前行动")
def stop_units(actor_ids: List[int]) -> str:
    """
    Args:
        actor_ids (List[int]): 要停止的单位 ID 列表
    Returns:
        str: 操作完成返回 "ok"
    """
    actors = [Actor(i) for i in actor_ids]
    api.stop(actors)
    return "ok"


@mcp.tool(name="visible_query",description="查询指定坐标是否在视野中")
def visible_query(x: int, y: int) -> bool:
    """
    Args:
        x (int): 地图坐标 X
        y (int): 地图坐标 Y
    Returns:
        bool: 如果该点可见返回 True，否则 False
    """
    return api.visible_query(Location(x, y))



@mcp.tool(name="explorer_query",description="查询指定坐标是否已探索")
def explorer_query(x: int, y: int) -> bool:
    """
    Args:
        x (int): 地图坐标 X
        y (int): 地图坐标 Y
    Returns:
        bool: 如果该点已探索返回 True，否则 False
    """
    return api.explorer_query(Location(x, y))


@mcp.tool(name="query_production_queue",description="查询指定类型的生产队列")
def query_production_queue(queue_type: str) -> Dict[str, Any]:
    '''查询指定类型的生产队列

    Args:
        queue_type (str): 队列类型，必须是以下值之一：
            'Building'
            'Defense'
            'Infantry'
            'Vehicle'
            'Aircraft'
            'Naval'

    Returns:
        dict: 包含队列信息的字典，格式如下：
            {
                "queue_type": "队列类型",
                "queue_items": [
                    {
                        "name": "项目内部名称",
                        "chineseName": "项目中文名称",
                        "remaining_time": 剩余时间,
                        "total_time": 总时间,
                        "remaining_cost": 剩余花费,
                        "total_cost": 总花费,
                        "paused": 是否暂停,
                        "done": 是否完成,
                        "progress_percent": 完成百分比,
                        "owner_actor_id": 所属建筑的ActorID,
                        "status": "项目状态，可能的值：
                            'completed' - 已完成
                            'paused' - 已暂停
                            'in_progress' - 正在建造（队列中第一个项目）
                            'waiting' - 等待中（队列中其他项目）"
                    },
                    ...
                ],
                "has_ready_item": 是否有已就绪的项目
            }

    Raises:
        GameAPIError: 当查询生产队列失败时
    '''
    return api.query_production_queue(queue_type)


# @RAMCP.tool(name="place_building",description="放置生产队列中已就绪的建筑")
# def place_building(queue_type: str, x: Optional[int] = None, y: Optional[int] = None) -> str:
#     """
#     Args:
#         queue_type (str): 队列类型，必须是 'Building', 'Defense', 'Infantry', 'Vehicle', 'Aircraft', 或 'Naval'
#         x (Optional[int]): 建筑放置 X 坐标（如不提供则自动选址）
#         y (Optional[int]): 建筑放置 Y 坐标（如不提供则自动选址）
#     Returns:
#         str: 操作完成时返回 "ok"
#     """
#     loc = Location(x, y) if x is not None and y is not None else None
#     api.place_building(queue_type, loc)
#     return "ok"

@mcp.tool(name="manage_production",description="管理生产队列中的项目（暂停、取消或继续）")
def manage_production(queue_type: str, action: str) -> str:
    """
    Args:
        queue_type (str): 队列类型，必须是 'Building', 'Defense', 'Infantry', 'Vehicle', 'Aircraft' 或 'Naval'
        action (str): 操作类型，必须是 'pause', 'cancel' 或 'resume'
    Returns:
        str: 操作完成时返回 "ok"
    """
    api.manage_production(queue_type, action)
    return "ok"


# @RAMCP.tool(name="deploy_mcv_and_wait",description="展开自己的基地车并等待指定时间")
# def deploy_mcv_and_wait(wait_time: float = 1.0) -> str:
#     """
#     Args:
#         wait_time (float): 展开后的等待时间（秒），默认 1.0
#     """
#     api.deploy_mcv_and_wait(wait_time)
#     return "ok"

@mcp.tool(name="ensure_can_build_wait",description="确保指定建筑已存在，若不存在则递归建造其所有依赖并等待完成")
def ensure_can_build_wait(building_name: str) -> bool:
    """
    Args:
        building_name (str): 建筑名称（中文）
    Returns:
        bool: 是否已拥有该建筑或成功建造完成
    """
    return api.ensure_can_build_wait(building_name)


# @RAMCP.tool(name="ensure_building_wait",description="内部接口：确保指定建筑及其依赖已建造并等待完成")
# def ensure_building_wait(building_name: str) -> bool:
#     """
#     Args:
#         building_name (str): 建筑名称（中文）
#     Returns:
#         bool: 是否成功建造并等待完成
#     """
#     return api.ensure_building_wait_buildself(building_name)


@mcp.tool(name="ensure_can_produce_unit",description="确保能生产指定单位（会自动补齐依赖建筑并等待完成）")
def ensure_can_produce_unit(unit_name: str) -> bool:
    """
    Args:
        unit_name (str): 要生产的单位名称（中文）
    Returns:
        bool: 是否已准备好生产该单位
    """
    return api.ensure_can_produce_unit(unit_name)


@mcp.tool(name="get_unexplored_nearby_positions",description="获取当前位置附近尚未探索的坐标列表")
def get_unexplored_nearby_positions(
    map_result: Dict[str, Any],
    current_x: int,
    current_y: int,
    max_distance: int
) -> List[Dict[str, int]]:
    """
    Args:
        map_result (dict): map_query 返回的地图信息字典
        current_x (int): 当前 X 坐标
        current_y (int): 当前 Y 坐标
        max_distance (int): 曼哈顿距离范围
    Returns:
        List[dict]: 未探索位置的列表，每项包含 'x' 和 'y'
    """
    # 将 dict 转回 MapQueryResult
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
    # 调用底层方法
    locs = api.get_unexplored_nearby_positions(
        mq,
        Location(current_x, current_y),
        max_distance
    )
    # 序列化为 JSON-friendly 格式
    return [{"x": loc.x, "y": loc.y} for loc in locs]


@mcp.tool(name="move_units_and_wait",description="移动一批单位到指定位置并等待到达或超时")
def move_units_and_wait(
    actor_ids: List[int],
    x: int,
    y: int,
    max_wait_time: float = 10.0,
    tolerance_dis: int = 1
) -> bool:
    """
    Args:
        actor_ids (List[int]): 要移动的单位 ID 列表
        x (int): 目标 X 坐标
        y (int): 目标 Y 坐标
        max_wait_time (float): 最大等待时间（秒），默认 10.0
        tolerance_dis (int): 到达判定的曼哈顿距离容差，默认 1
    Returns:
        bool: 是否在 max_wait_time 内全部到达（False 表示超时或卡住）
    """
    actors = [Actor(i) for i in actor_ids]
    return api.move_units_by_location_and_wait(actors, Location(x, y), max_wait_time, tolerance_dis)


@mcp.tool(name="unit_attribute_query",description="查询指定单位的属性及其攻击范围内的目标")
def unit_attribute_query(actor_ids: List[int]) -> Dict[str, Any]:
    """
    Args:
        actor_ids (List[int]): 要查询的单位 ID 列表
    Returns:
        dict: 每个单位的属性信息，包括其攻击范围内的目标列表
    """
    actors = [Actor(i) for i in actor_ids]
    return api.unit_attribute_query(actors)


@mcp.tool(name="map_query",description="查询地图信息并返回序列化数据")
def map_query() -> Dict[str, Any]:
    """
    Returns:
        dict: 包含地图宽度、高度、高程、可见性、探索状态、地形、资源类型和资源量的字典
    """
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

@mcp.tool(name="player_base_info_query",description="查询玩家基地的资源、电力等基础信息")
def player_base_info_query() -> Dict[str, Any]:
    """
    Returns:
        dict: 包含以下字段的玩家基地信息
            - cash: 当前金钱
            - resources: 资源数量
            - power: 总供电量
            - powerDrained: 已用电量
            - powerProvided: 可用电量
    """
    info = api.player_base_info_query()
    return {
        "cash": info.Cash,
        "resources": info.Resources,
        "power": info.Power,
        "powerDrained": info.PowerDrained,
        "powerProvided": info.PowerProvided
    }

@mcp.tool(name="screen_info_query",description="查询当前屏幕信息")
def screen_info_query() -> Dict[str, Any]:
    """
    Returns:
        dict: 包含以下字段的屏幕信息
            - screenMin: {x, y}
            - screenMax: {x, y}
            - isMouseOnScreen: bool
            - mousePosition: {x, y}
    """
    info = api.screen_info_query()
    return {
        "screenMin": {"x": info.ScreenMin.x, "y": info.ScreenMin.y},
        "screenMax": {"x": info.ScreenMax.x, "y": info.ScreenMax.y},
        "isMouseOnScreen": info.IsMouseOnScreen,
        "mousePosition": {"x": info.MousePosition.x, "y": info.MousePosition.y}
    }


@mcp.tool(name="set_rally_point",description="为指定建筑设置集结点")
def set_rally_point(actor_ids: List[int], x: int, y: int) -> str:
    """
    Args:
        actor_ids (List[int]): 要设置集结点的建筑 ID 列表
        x (int): 集结点 X 坐标
        y (int): 集结点 Y 坐标
    Returns:
        str: 操作完成返回 "ok"
    """
    actors = [Actor(i) for i in actor_ids]
    api.set_rally_point(actors, Location(x, y))
    return "ok"

@run_agent
def run(agent: MofaAgent):
    """Agent 主运行函数"""

    # 接收用户命令
    user_input = agent.receive_parameter('start_input')

    print(f"🎮 收到用户指令: {user_input}")

    mcp.settings.log_level = "critical"
    mcp.run(transport="sse")

    # 发送输出
    # agent.send_output(agent_output_name='openra-mcp-start', agent_result='start openra mcp ')


def main():
    """主函数"""
    agent = MofaAgent(agent_name='openra-mcp-agent')
    run(agent=agent)


if __name__ == "__main__":
    main()
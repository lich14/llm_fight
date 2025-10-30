import sys
import time
import json
import math
from typing import List, Dict, Any, Tuple, Optional

# === 引入 OpenRA 控制库 ===
sys.path.append('examples/mofa/examples/openra-controller')
from OpenRA_Copilot_Library.game_api import GameAPI
from OpenRA_Copilot_Library.models import TargetsQueryParam, Actor

# === 你给的 StreamingAgent（原样复用，略微精简） ===
import requests
from tenacity import retry, wait_random_exponential, stop_after_attempt

api = GameAPI('localhost', 7445, 'zh')


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
        if item["type"] in ['建造厂', '电厂', '矿场', '战车工厂', '车间', '雷达']:
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

    tech = {c: safe_can(c) for c in ["harv", "jeep", "apc", "ftrk", "mcv"]}

    # 粗略探索率（若有更准API可替换）
    explored_ratio = 0.2  # 占位；可按你实际API替换

    return {
        "cycle": cycle,
        "money": info.Cash,
        "power": {
            "used": info.Power,
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
            "map_size_guess": {
                "w": 256,
                "h": 256
            },
            "fast_units": ["jeep", "apc", "ftrk", "吉普车", "装甲运输车", "防空车"]
        }
    }


state = encode_state(api, 0)
print(state)

print(api.attack_target_id(491, [397, 451, 464]))

# api.move_units_by_location_and_id([341], location={'x': 100, 'y': 100})

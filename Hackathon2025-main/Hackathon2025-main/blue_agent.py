#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手动坦克生产模式
1. 先建造完整基地（参考 defense_simple.py）
2. 由用户在终端手动选择生产哪种坦克
3. 预算限制：总花费不能超过 $10,000
"""

import sys
import os
import time
import json
import socket
import threading
from datetime import datetime
from queue import Queue

# 添加库路径
current_dir = os.path.dirname(os.path.abspath(__file__))
library_path = os.path.join(current_dir, 'examples', 'mofa', 'examples', 'openra-controller')
sys.path.insert(0, library_path)

from OpenRA_Copilot_Library.game_api import GameAPI
from OpenRA_Copilot_Library.models import TargetsQueryParam, Location


# ===== 工具函数：将对象转换为可JSON序列化 =====
def to_jsonable(obj):
    """递归将对象转换为可JSON序列化的类型，特别处理datetime。"""
    import datetime as _dt
    if isinstance(obj, _dt.datetime):
        return obj.isoformat()
    if isinstance(obj, _dt.date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    # 其他非常见类型统一转字符串，避免JSON错误
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)

# ===== 发送战损统计到红方 =====
def send_battle_stats_to_red(combat_stats, red_host=None, red_port=8899, max_retries=3):
    """将蓝方战损统计发送给红方，带强化重试机制和动态IP识别"""
    global red_actual_ip
    
    # 优先使用动态获取的红方IP地址
    if red_actual_ip:
        red_host = red_actual_ip
        print(f"\n[战损发送] 使用动态获取的红方IP: {red_host}")
    elif red_host is None:
        red_host = '172.22.63.34'  # 默认fallback
        print(f"\n[战损发送] 使用默认红方IP: {red_host}")
    else:
        print(f"\n[战损发送] 使用指定红方IP: {red_host}")
    
    print(f"[战损发送] 目标地址: {red_host}:{red_port}")
    print(f"[战损发送] 战损数据大小: {len(str(combat_stats))} 字符")
    
    for attempt in range(max_retries):
        print(f"\n[战损发送] === 第{attempt+1}/{max_retries}次发送尝试 ===")
        sock = None
        try:
            # 创建Socket连接，使用较短的超时时间
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # 缩短超时时间到5秒
            
            print(f"[战损发送] 正在连接 {red_host}:{red_port}...")
            start_time = time.time()
            sock.connect((red_host, red_port))
            connect_time = time.time() - start_time
            print(f"[战损发送] ✓ 连接成功，耗时 {connect_time:.2f}秒")
            
            # 准备发送数据
            # 在发送前，对战损统计做JSON友好化转换（处理datetime等）
            safe_stats = to_jsonable(combat_stats)
            message = {
                'action': 'report_battle_stats',
                'timestamp': datetime.now().isoformat(),
                'blue_stats': safe_stats,
                'attempt': attempt + 1,
                'blue_ip': '172.22.63.66'  # 标识蓝方IP
            }
            data = json.dumps(message, ensure_ascii=False).encode('utf-8')
            print(f"[战损发送] 准备发送数据: {len(data)} 字节")
            
            # 发送数据
            send_start = time.time()
            bytes_sent = sock.send(data)
            send_time = time.time() - send_start
            print(f"[战损发送] ✓ 数据发送完成: {bytes_sent}/{len(data)} 字节，耗时 {send_time:.2f}秒")
            
            # 等待红方确认
            print(f"[战损发送] 等待红方确认响应...")
            recv_start = time.time()
            sock.settimeout(3)  # 接收响应时使用更短的超时
            response = sock.recv(4096)
            recv_time = time.time() - recv_start
            
            if response:
                print(f"[战损发送] ✓ 收到响应: {len(response)} 字节，耗时 {recv_time:.2f}秒")
                try:
                    response_data = json.loads(response.decode('utf-8'))
                    print(f"[战损发送] 响应内容: {response_data}")
                    
                    if response_data.get('status') == 'success':
                        print(f"[战损发送] ✓ 战损统计发送成功，红方已确认接收！")
                        return True
                    else:
                        print(f"[战损发送] ✗ 红方响应状态异常: {response_data.get('status')}")
                        print(f"[战损发送] 响应消息: {response_data.get('message', '无消息')}")
                except json.JSONDecodeError as e:
                    print(f"[战损发送] ✗ 响应JSON解析失败: {e}")
                    print(f"[战损发送] 原始响应: {response.decode('utf-8', errors='ignore')}")
            else:
                print(f"[战损发送] ✗ 红方无响应 (接收到空数据)")
                
        except socket.timeout as e:
            print(f"[战损发送] ✗ 连接超时: {e}")
        except ConnectionRefusedError as e:
            print(f"[战损发送] ✗ 连接被拒绝: {e} (红方可能未监听端口{red_port})")
        except ConnectionResetError as e:
            print(f"[战损发送] ✗ 连接被重置: {e} (红方可能已关闭连接)")
        except OSError as e:
            if "Network is unreachable" in str(e) or "No route to host" in str(e):
                print(f"[战损发送] ✗ 网络不可达: {e} (请检查红方IP {red_host} 是否正确)")
            else:
                print(f"[战损发送] ✗ 网络错误: {e}")
        except Exception as e:
            print(f"[战损发送] ✗ 发送失败: {type(e).__name__}: {e}")
            import traceback
            error_lines = traceback.format_exc().split('\n')
            print(f"[战损发送] 错误详情: {error_lines[-3]}")
        finally:
            if sock:
                sock.close()
        
        # 重试前等待
        if attempt < max_retries - 1:
            wait_time = 2 + attempt  # 递增等待时间: 2, 3, 4秒
            print(f"[战损发送] 等待{wait_time}秒后重试...")
            time.sleep(wait_time)
        else:
            print(f"[战损发送] ✗ 所有{max_retries}次发送尝试均失败")
    
    print(f"[战损发送] ✗ 战损统计发送最终失败")
    return False


# ===== 坦克配置（从 units_config.json 获取） =====
TANKS = {
    "A": {
        "name": "防空车",
        "code": "ftrk",
        "cost": 300,
        "description": "防空车，对空中单位有效"
    },
    "B": {
        "name": "重型坦克",
        "code": "3tnk",
        "cost": 575,
        "description": "主力坦克，攻防平衡"
    },
    "C": {
        "name": "猛犸坦克",
        "code": "4tnk",
        "cost": 1000,
        "description": "最强坦克，双炮管高伤害"
    },
    "D": {
        "name": "V2火箭发射车",
        "code": "v2rl",
        "cost": 450,
        "description": "远程火箭，射程12"
    },
    "E": {
        "name": "采矿车",
        "code": "harv",
        "cost": 550,
        "description": "采集矿石，运回矿场"
    }
}

BUDGET_LIMIT = 10000  # 总预算限制

# 创建反向映射（代码 -> 名称）用于统计
CODE_TO_NAME = {tank["code"]: tank["name"] for tank in TANKS.values()}
NAME_TO_LETTER = {v["name"]: k for k, v in TANKS.items()}

# 游戏API返回的单位类型到配置名称的映射
API_TYPE_TO_CONFIG_NAME = {
    "防空车": "防空车",
    "重型坦克": "重型坦克", 
    "超重型坦克": "猛犸坦克",  # 游戏API返回"超重型坦克"，但配置中是"猛犸坦克"
    "猛犸坦克": "猛犸坦克",
    "V2火箭发射车": "V2火箭发射车",
    "采矿车": "采矿车"
}

# 配置名称到字母的映射（用于unit_type_details）
CONFIG_NAME_TO_LETTER = NAME_TO_LETTER

# 与红方一致的建筑类型排除列表
NON_COMBAT_TYPES = {
    '建造厂', '电厂', '核电站', '矿场', '兵营', '战车工厂',
    '雷达', '维修厂', '科技中心', '机场', '火焰塔',
    '特斯拉线圈', '防空导弹', '储存罐', '发电厂', '雷达站',
    '空军基地', '特斯拉塔'
}

# 是否启用“手动生产”交互（默认关闭，走Socket指令）
ENABLE_MANUAL_PRODUCTION = False

# 全局标志：控制后台防御线程
defense_running = False
defense_thread = None

# 全局生产队列（Socket通信用）
production_queue = Queue()

# 矿场自带的采矿车ID列表（不移动这些采矿车）
initial_harvester_ids = []

# 游戏结束信号（用于Socket通信）
game_over_signal = None

# 线程事件 - 用于通知主循环游戏结束
game_over_event = threading.Event()

# 红方真实IP地址（动态获取）
red_actual_ip = None

# 战损统计
combat_stats = {
    "side": "blue",
    "game_start_time": None,
    "game_end_time": None,
    "produced_units": {},  # {"重型坦克": 10, "猛犸坦克": 5}
    "total_produced": 0,
    "total_cost": 0,
    "final_surviving": 0,
    "final_units_detail": {},  # {"重型坦克": 3, "猛犸坦克": 2}
    "loss_count": 0,
    "loss_rate": 0.0,
    "battle_start_time": None
}


# ===== Socket 服务器功能 =====
def socket_server_thread(host='0.0.0.0', port=8888):
    """本地Socket服务器线程，接收ai_builder_v3.py的坦克生产指令"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)
    
    print(f"\n[Socket服务器] 已启动，监听 {host}:{port}")
    print(f"[Socket服务器] 等待红方连接...\n")
    
    while True:
        try:
            client_socket, address = server_socket.accept()
            print(f"\n[Socket服务器] 收到连接: {address}")
            
            # 处理客户端请求
            threading.Thread(target=handle_client, args=(client_socket, address), daemon=True).start()
        except Exception as e:
            print(f"[Socket服务器] 错误: {e}")
            time.sleep(1)


def handle_client(client_socket, address):
    """处理单个客户端连接"""
    global red_actual_ip
    
    # 记录客户端IP地址（可能是红方）
    client_ip = address[0]
    print(f"\n[Socket服务器] 客户端IP: {client_ip}")
    
    try:
        while True:
            data = client_socket.recv(4096)
            if not data:
                break
            
            try:
                message = json.loads(data.decode('utf-8'))
                print(f"\n[Socket服务器] 收到来自 {address} 的指令: {message}")
                print(f"[Socket服务器] 指令类型: {message.get('action', 'unknown')}")
                
                # 解析生产指令
                if message.get('action') == 'produce_tank':
                    tank_type = message.get('tank_type')
                    
                    # 查找对应的坦克 - 支持字母代号(A-E)和中文名称
                    tank_found = None
                    # 首先检查是否是字母代号 A、B、C、D、E
                    if tank_type in TANKS:
                        tank_found = TANKS[tank_type]
                        print(f"[Socket服务器] 通过字母代号找到坦克: {tank_type} -> {tank_found['name']}")
                    else:
                        # 如果不是字母代号，尝试通过中文名称查找
                        for tank_id, tank_info in TANKS.items():
                            if tank_info['name'] == tank_type:
                                tank_found = tank_info
                                print(f"[Socket服务器] 通过中文名称找到坦克: {tank_type} -> {tank_id}")
                                break
                    
                    if tank_found:
                        # 计算能建造多少辆（用完$10,000预算）
                        max_count = BUDGET_LIMIT // tank_found['cost']
                        
                        # 加入生产队列
                        production_queue.put({
                            'tank_info': tank_found,
                            'count': max_count
                        })
                        
                        response = {
                            'status': 'success',
                            'message': f'已加入生产队列: {tank_type} x{max_count} (花费${max_count * tank_found["cost"]})'
                        }
                        print(f"[Socket服务器] {response['message']}")
                    else:
                        response = {
                            'status': 'error',
                            'message': f'未知坦克类型: {tank_type}'
                        }
                        print(f"[Socket服务器] {response['message']}")
                    
                    # 发送响应
                    client_socket.send(json.dumps(response).encode('utf-8'))
                
                elif message.get('action') == 'produce_multi_tanks':
                    # 处理多种坦克类型组合生产指令
                    tank_distribution = message.get('tank_distribution', {})
                    print(f"[Socket服务器] 收到多坦克生产指令: {tank_distribution}")
                    
                    total_cost = 0
                    valid_orders = []
                    error_messages = []
                    
                    # 验证每种坦克类型和计算总成本
                    for tank_id, count in tank_distribution.items():
                        print(f"[生产队列] 处理坦克类型 {tank_id}: 数量={count}")
                        
                        if tank_id not in TANKS:
                            error_messages.append(f"未知坦克类型: {tank_id}")
                            continue
                        
                        if not isinstance(count, int) or count <= 0:
                            print(f"[生产队列] 跳过坦克{tank_id}，数量无效或为0: {count}")
                            continue
                            
                        tank_info = TANKS[tank_id]
                        cost = count * tank_info['cost']
                        total_cost += cost
                        valid_orders.append((tank_id, tank_info, count, cost))
                        print(f"[生产队列] 有效订单: {tank_id}({tank_info['name']}) x{count} (${cost})")
                    
                    if error_messages:
                        response = {
                            'status': 'error',
                            'message': '; '.join(error_messages)
                        }
                    elif total_cost > BUDGET_LIMIT:
                        response = {
                            'status': 'error', 
                            'message': f'总花费${total_cost}超出预算限制${BUDGET_LIMIT}'
                        }
                    else:
                        # 将所有有效订单加入生产队列
                        for tank_id, tank_info, count, cost in valid_orders:
                            production_queue.put({
                                'tank_info': tank_info,
                                'count': count
                            })
                            print(f"[生产队列] 已添加: {tank_id}({tank_info['name']}) x{count} (${cost})")
                        
                        tank_summary = ', '.join([f"{tid}x{cnt}" for tid, _, cnt, _ in valid_orders])
                        response = {
                            'status': 'success',
                            'message': f'已加入多坦克生产队列: {tank_summary} (总花费${total_cost})'
                        }
                    
                    print(f"[Socket服务器] {response['message']}")
                    client_socket.send(json.dumps(response).encode('utf-8'))
                
                elif message.get('action') == 'query_status':
                    # 查询当前队列状态
                    response = {
                        'status': 'success',
                        'queue_size': production_queue.qsize(),
                        'available_tanks': [f"{tank_id}({tank_info['name']})" for tank_id, tank_info in TANKS.items()],
                        'tank_types': list(TANKS.keys())  # 返回可用的字母代号 A, B, C, D, E
                    }
                    client_socket.send(json.dumps(response).encode('utf-8'))
                
                elif message.get('action') == 'report_game_over':
                    # 红方通知战局结束
                    side = message.get('side', '')
                    status = message.get('status', '')
                    reason = message.get('reason', '')
                    
                    print(f"\n[Socket服务器] 收到战局通知:")
                    print(f"  - 一方: {side}")
                    print(f"  - 状态: {status}")
                    print(f"  - 原因: {reason}")
                    
                    if side == 'red' and status == 'defeated':
                        print(f"\n[Socket服务器] 红方已战败，蓝方获胜！")
                        print(f"[Socket服务器] 正在准备战损统计...")
                        
                        # 记录红方真实IP地址
                        red_actual_ip = client_ip
                        print(f"[Socket服务器] 记录红方IP: {red_actual_ip}")
                        
                        # 不在这里停止防御线程，让主循环处理
                        # 主循环会在处理完战损统计后自动停止防御
                        
                        # 发送确认响应，但不退出程序
                        response = {
                            'status': 'success',
                            'message': '蓝方已收到红方战败通知，正在准备战损统计'
                        }
                        client_socket.send(json.dumps(response).encode('utf-8'))
                        
                        # 设置全局标志，让主线程处理战损统计但不退出
                        global game_over_signal, game_over_event
                        print(f"[Socket服务器] 设置game_over_signal之前: {game_over_signal}")
                        game_over_signal = {
                            'red_defeated': True,
                            'blue_victory': True,
                            'reason': reason,
                            'stats_sent': False  # 标记战损统计是否已发送
                        }
                        # 设置事件通知主循环
                        game_over_event.set()
                        print(f"[Socket服务器] 设置game_over_signal之后: {game_over_signal}")
                        print(f"[Socket服务器] *** 红方败北信号已设置，事件已触发 ***")
                        print(f"[Socket服务器] 强制刷新输出...")
                        import sys
                        sys.stdout.flush()
                        
                    else:
                        # 其他战局状态
                        response = {
                            'status': 'success',
                            'message': f'已收到战局通知: {side} {status}'
                        }
                        client_socket.send(json.dumps(response).encode('utf-8'))
            
            except json.JSONDecodeError as e:
                print(f"[Socket服务器] JSON解析错误: {e}")
                error_response = {'status': 'error', 'message': 'Invalid JSON'}
                client_socket.send(json.dumps(error_response).encode('utf-8'))
    
    except Exception as e:
        print(f"[Socket服务器] 处理客户端错误: {e}")
    finally:
        client_socket.close()
        print(f"[Socket服务器] 连接关闭: {address}")


# ===== 建筑建造函数 =====
def move_combat_units_to_center(api: GameAPI, center_x=80, center_y=20):
    """将战斗单位移动到战斗集结点（右上角），使用与红方一致的统计方式"""
    print(f"\n[集结] 将战斗单位移动到战斗集结点({center_x}, {center_y})...")
    
    try:
        # 获取所有我方单位
        mine = api.query_actor(TargetsQueryParam(faction='自己'))
        combat_units = []
        
        print(f"  [调试] 生产记录: {combat_stats['produced_units']}")
        print(f"  [调试] 总计生产: {combat_stats['total_produced']} 辆")
        print(f"  [调试] 初始采矿车ID: {initial_harvester_ids}")
        print(f"  [调试] 开始扫描所有单位，使用红方统计逻辑...")
        
        for unit in mine:
            original_type = getattr(unit, "type", "")
            print(f"  [扫描] 单位: {original_type} (ID: {unit.actor_id})")
            
            # 排除建筑类型（与红方一致）
            if original_type in NON_COMBAT_TYPES:
                print(f"    -> [排除] 建筑类型: {original_type}")
                continue
                
            # 排除初始采矿车（与红方一致）
            if original_type == "采矿车" and unit.actor_id in initial_harvester_ids:
                print(f"    -> [排除] 初始采矿车: {original_type} (ID: {unit.actor_id})")
                continue
                
            # 其他所有单位都算作战斗单位（包括主动生产的采矿车）
            combat_units.append(unit)
            print(f"    -> [统计] 战斗单位: {original_type} (ID: {unit.actor_id})")
        
        print(f"  当前统计: produced_units={combat_stats['produced_units']}, total={combat_stats['total_produced']}")
        print(f"  地图上找到 {len(combat_units)} 个战斗单位（按红方统计方式）")
        
        if len(combat_units) > 0:
            print(combat_units)
            print(f"  找到 {len(combat_units)} 个战斗单位")
            
            # 收集所有战斗单位的ID，使用与红方一致的攻击移动策略
            target_ids = [unit.actor_id for unit in combat_units]
            
            try:
                # 使用与红方一致的攻击移动策略
                api.move_units_by_location_and_id(
                    target_ids,
                    location={"x": center_x, "y": center_y},
                    attack_move=True
                )
                print(f"  ✓ {len(target_ids)} 个单位已下达 attack_move 指令到({center_x}, {center_y})")
                
                # 等待移动完成并验证位置
                print(f"  等待10秒让单位移动到目标位置...")
                time.sleep(10)
                
                # 验证移动结果
                moved_units = 0
                for unit in combat_units:
                    try:
                        # 重新查询该单位的位置
                        all_units = api.query_actor(TargetsQueryParam(faction='自己'))
                        updated_unit = [u for u in all_units if u.actor_id == unit.actor_id]
                        if updated_unit:
                            current_pos = updated_unit[0].position
                            distance = abs(current_pos.x - center_x) + abs(current_pos.y - center_y)
                            if distance < 5:  # 允许5格误差
                                moved_units += 1
                            print(f"    单位{unit.actor_id}: ({current_pos.x}, {current_pos.y}) [距离目标: {distance}格]")
                    except:
                        pass
                        
                print(f"  ✓ 移动验证: {moved_units}/{len(combat_units)} 个单位已到达目标附近")
                
            except Exception as e:
                print(f"  批量 attack_move 失败: {e}")
                # 备用方案：逐个 attack_move
                moved_count = 0
                for unit in combat_units:
                    try:
                        api.move_units_by_location_and_id(
                            [unit.actor_id],
                            location={"x": center_x, "y": center_y},
                            attack_move=True
                        )
                        moved_count += 1
                    except:
                        pass
                print(f"  ✓ 单个 attack_move 成功: {moved_count}/{len(combat_units)}")
                
                # 逐个移动后也等待和验证
                if moved_count > 0:
                    print(f"  等待5秒让单位移动...")
                    time.sleep(5)
        else:
            print(f"  ⚠️  未找到战斗单位")
    
    except Exception as e:
        print(f"  移动失败: {e}")


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
        print(f"\n⚠️  电力不足！(当前: {info.Power}/{info.PowerProvided})")
        
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
        print(f"✓ 电力充足: {info.Power}/{info.PowerProvided}")


def record_initial_harvesters(api: GameAPI):
    """记录矿场自带的采矿车ID"""
    global initial_harvester_ids
    try:
        mine = api.query_actor(TargetsQueryParam(faction='自己'))
        for unit in mine:
            if unit.type in ['采矿车', 'harv']:
                if unit.actor_id not in initial_harvester_ids:
                    initial_harvester_ids.append(unit.actor_id)
        
        if initial_harvester_ids:
            print(f"\n[记录] 已记录 {len(initial_harvester_ids)} 个矿场自带的采矿车ID: {initial_harvester_ids}")
    except Exception as e:
        print(f"[记录] 记录采矿车ID失败: {e}")


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
    
    # 等待矿场生成采矿车（矿场建造完成后需要时间生成采矿车）
    print("\n[等待] 等待矿场生成采矿车...")
    time.sleep(15)  # 等待15秒确保采矿车完全生成
    
    # 记录矿场自带的采矿车ID
    record_initial_harvesters(api)
    
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
    
    # 步骤5: 补充电力
    print("\n[步骤5] 补充电力设施")
    build_structure(api, "核电站", "核电站", 2)
    check_and_build_power(api)
    
    print("\n" + "=" * 60)
    print("✓ 基地建设完成！")
    print("=" * 60)


# ===== 坦克生产函数 =====
def show_tank_menu(remaining_budget: int):
    """显示坦克选择菜单"""
    print("\n" + "=" * 60)
    print("可生产的坦克类型：")
    print("=" * 60)
    for key, tank in TANKS.items():
        max_count = remaining_budget // tank["cost"]
        affordable = "✓" if tank["cost"] <= remaining_budget else "✗"
        print(f"{key}. {tank['name']} - ${tank['cost']} {affordable} (最多可生产: {max_count}辆)")
        print(f"   {tank['description']}")
    print("-" * 60)
    print(f"剩余预算: ${remaining_budget} / ${BUDGET_LIMIT}")
    print("=" * 60)


def produce_tank(api: GameAPI, tank_info: dict, count: int) -> int:
    """生产指定数量的坦克"""
    name = tank_info["name"]
    code = tank_info["code"]
    cost = tank_info["cost"]
    
    print(f"\n[生产] {name}({code}) x{count} | 单价: ${cost}")
    print(f"[调试] 开始记录生产统计...")
    
    success = 0
    for i in range(count):
        try:
            api.produce(name, 1, False)  # False 表示生产单位，不是建筑
            print(f"  [{i+1}/{count}] 已下单 - 花费 ${cost}")
            time.sleep(1)
            success += 1
        except Exception as e:
            print(f"  [{i+1}/{count}] 失败: {e}")
            break
    
    total_cost = success * cost
    print(f"✓ 成功生产 {success} 辆 {name}，总花费 ${total_cost}")
    
    # 记录生产统计
    if success > 0:
        print(f"[调试] 记录到统计: {name} x {success}")
        if name not in combat_stats["produced_units"]:
            combat_stats["produced_units"][name] = 0
        combat_stats["produced_units"][name] += success
        combat_stats["total_produced"] += success
        combat_stats["total_cost"] += total_cost
        print(f"[调试] 当前统计: produced_units={combat_stats['produced_units']}, total={combat_stats['total_produced']}")
        
        # 生产完成后，等待所有单位建造完成然后移动到中心
        # 估算等待时间：每辆坦克约需要10-15秒建造时间
        wait_time = min(success * 12, 100)  # 每辆12秒，最多等待3分钟
        print(f"  等待所有单位生产完成（预计{wait_time}秒）...")
        
        # 分段等待并显示进度
        for i in range(wait_time // 10):
            time.sleep(10)
            print(f"  [{(i+1)*10}/{wait_time}秒] 等待中...")
        
        # 最后等待剩余时间
        remaining = wait_time % 10
        if remaining > 0:
            time.sleep(remaining)
        
        print(f"  开始移动所有单位到战斗集结点...")
        
        # 查询地图战斗集结位置（右上角）
        try:
            map_info = api.map_query()
            # battle_x = int(map_info.MapWidth * 0.90)  # 地图宽度的85%位置（右侧）
            # battle_y = int(map_info.MapHeight * 0.10)  # 地图高度的15%位置（上方）
            battle_x = 90  
            battle_y = 10  
            print(f"  动态战斗集结点（右上角）: ({battle_x}, {battle_y})")
        except:
            # 使用默认值 - 右上角位置
            battle_x, battle_y = 90, 10
            print(f"  使用默认战斗集结点（右上角）: ({battle_x}, {battle_y})")
        
        move_combat_units_to_center(api, battle_x, battle_y)
    else:
        print(f"[调试] 未成功生产任何单位，不记录统计")
    
    return total_cost


def safe_attack_target(api: GameAPI, attacker, target, max_retries=3):
    """安全的攻击目标函数，使用attack_move替代直接攻击"""
    try:
        # 获取目标位置
        target_pos = getattr(target, 'position', None)
        if not target_pos:
            print(f"    无法获取目标位置")
            return False
        
        # 使用attack_move到目标位置，这比直接attack_target更可靠
        result = api.move_units_by_location_and_id(
            [attacker.actor_id],
            location={"x": target_pos.x, "y": target_pos.y},
            attack_move=True
        )
        
        return bool(result)
            
    except Exception as e:
        print(f"    attack_move异常: {e}")
        return False


def auto_defense(api: GameAPI):
    """自动防御模式（后台运行） + 处理Socket生产队列"""
    global defense_running
    
    print("\n[后台防御] 自动防御已启动...")
    print("[后台防御] Socket生产队列处理已启动...")
    
    check_count = 0
    last_enemy_count = 0
    
    while defense_running:
        try:
            # 处理Socket生产队列
            if not production_queue.empty():
                order = production_queue.get()
                tank_info = order['tank_info']
                count = order['count']
                
                print(f"\n[队列处理] 开始生产: {tank_info['name']} x{count}")
                produce_tank(api, tank_info, count)
            
            # 每10次循环检查一次电力
            check_count += 1
            if check_count >= 10:
                try:
                    check_and_build_power(api)
                except:
                    pass
                check_count = 0
            
            # 查询敌人
            enemies = api.query_actor(TargetsQueryParam(faction='敌人'))
            
            # 检查战败条件：蓝方所有战斗单位被消灭
            # 使用与红方一致的统计方式
            if combat_stats["total_produced"] > 0:  # 确保已经开始生产
                mine = api.query_actor(TargetsQueryParam(faction='自己'))
                combat_units = []
                
                for unit in mine:
                    original_type = getattr(unit, "type", "")
                    
                    # 排除建筑类型（与红方一致）
                    if original_type in NON_COMBAT_TYPES:
                        continue
                    
                    # 排除初始采矿车（与红方一致）
                    if original_type == "采矿车" and unit.actor_id in initial_harvester_ids:
                        continue
                    
                    # 其他所有单位都算作战斗单位（包括主动生产的采矿车）
                    combat_units.append(unit)
                
                total_combat_units = len(combat_units)
                
                # 检查战斗单位数量
                if total_combat_units == 0:
                    print("\n" + "=" * 60)
                    print("战败检测")
                    print("=" * 60)
                    print("❌ 蓝方所有战斗单位已被消灭")
                    print(f"   已生产单位: {combat_stats['total_produced']} 辆")
                    print(f"   剩余战斗单位: 0")
                    print(f"   总花费: ${combat_stats['total_cost']}")
                    print("\n游戏结束 - 蓝方失败")
                    print("=" * 60)
                    
                    # 计算并保存最终统计
                    calculate_final_stats(api)
                    save_combat_log()
                    print_combat_summary()
                    
                    # 发送战损统计给红方
                    print('3333333333333333333333333333333333')
                    print(combat_stats)
                    send_battle_stats_to_red(combat_stats)
                    
                    # 停止防御线程
                    defense_running = False
                    return  # 退出函数，结束防御循环
            
            if enemies and len(enemies) > 0:
                if len(enemies) != last_enemy_count:
                    print(f"\n[防御] ⚠️  发现 {len(enemies)} 个敌人！正在反击...")
                    last_enemy_count = len(enemies)
                
                # 获取我方战斗单位进行攻击（按红方逻辑）
                mine = api.query_actor(TargetsQueryParam(faction='自己'))
                combat_units = []
                
                for unit in mine:
                    original_type = getattr(unit, "type", "")
                    
                    # 排除建筑类型（与红方一致）
                    if original_type in NON_COMBAT_TYPES:
                        continue
                    
                    # 排除初始采矿车（与红方一致）
                    if original_type == "采矿车" and unit.actor_id in initial_harvester_ids:
                        continue
                    
                    # 其他所有单位都算作战斗单位（包括主动生产的采矿车）
                    combat_units.append(unit)
                
                if len(combat_units) > 0:
                    # 智能攻击策略：确保每个单位都有攻击目标
                    attack_success = 0
                    attack_failed = 0
                    total_attempts = len(combat_units)
                    
                    # 每次都显示当前状态
                    print(f"[攻击状态] 蓝方{len(combat_units)}个战斗单位 vs 红方{len(enemies)}个敌人")
                    
                    if len(enemies) == 1:
                        # 只有一个敌人，所有单位集火攻击
                        target_enemy = enemies[0]
                        target_pos = getattr(target_enemy, 'position', None)
                        target_info = f"位置({target_pos.x},{target_pos.y})" if target_pos else "位置未知"
                        
                        print(f"[集火模式] 所有单位攻击单一目标: {target_enemy.type} {target_info}")
                        
                        for i, unit in enumerate(combat_units):
                            result = safe_attack_target(api, unit, target_enemy)
                            if result:
                                attack_success += 1
                                if i < 3:  # 只显示前3个单位的详细信息
                                    print(f"  单位{i+1}({unit.type}): ✓ 攻击成功")
                            else:
                                attack_failed += 1
                                if i < 3:
                                    print(f"  单位{i+1}({unit.type}): ✗ 攻击失败")
                        
                        print(f"[集火结果] ✓成功:{attack_success} ✗失败:{attack_failed} 总计:{total_attempts}")
                    
                    elif len(enemies) > 1:
                        # 多个敌人，智能分配攻击目标
                        units_per_enemy = max(1, len(combat_units) // len(enemies))
                        
                        print(f"[分配模式] 平均每个敌人分配{units_per_enemy}个攻击单位")
                        
                        # 预先计算分配方案
                        attack_plan = {}
                        for i, unit in enumerate(combat_units):
                            target_index = min(i // units_per_enemy, len(enemies) - 1)
                            if target_index not in attack_plan:
                                attack_plan[target_index] = []
                            attack_plan[target_index].append((i, unit))
                        
                        # 显示攻击计划
                        for target_index, assigned_units in attack_plan.items():
                            enemy = enemies[target_index]
                            enemy_pos = getattr(enemy, 'position', None)
                            enemy_info = f"位置({enemy_pos.x},{enemy_pos.y})" if enemy_pos else "位置未知"
                            print(f"  目标{target_index+1}({enemy.type} {enemy_info}): 分配{len(assigned_units)}个单位")
                        
                        # 执行攻击
                        for target_index, assigned_units in attack_plan.items():
                            target_enemy = enemies[target_index]
                            target_success = 0
                            target_failed = 0
                            
                            for unit_index, unit in assigned_units:
                                result = safe_attack_target(api, unit, target_enemy)
                                if result:
                                    attack_success += 1
                                    target_success += 1
                                else:
                                    attack_failed += 1
                                    target_failed += 1
                            
                            print(f"    -> 目标{target_index+1}: ✓{target_success} ✗{target_failed}")
                        
                        print(f"[分配结果] ✓成功:{attack_success} ✗失败:{attack_failed} 总计:{total_attempts}")
                    
                    # 备用策略：如果上述都失败，使用轮询攻击
                    if attack_success == 0 and len(enemies) > 0:
                        print(f"[备用模式] 主攻击失败，启用轮询攻击模式")
                        backup_success = 0
                        
                        for i, unit in enumerate(combat_units):
                            enemy = enemies[i % len(enemies)]
                            result = safe_attack_target(api, unit, enemy)
                            if result:
                                backup_success += 1
                                attack_success += 1
                        
                        print(f"[备用结果] ✓成功:{backup_success} 个单位")
                    
                    # 如果仍然没有成功攻击，尝试强制攻击
                    if attack_success == 0 and len(enemies) > 0:
                        print(f"[强制攻击] 所有攻击都失败，尝试强制攻击最近的敌人")
                        force_success = 0
                        nearest_enemy = enemies[0]  # 简单选择第一个敌人
                        
                        for unit in combat_units[:5]:  # 只尝试前5个单位，避免过多日志
                            # 强制重新获取单位信息
                            all_fresh_units = api.query_actor(TargetsQueryParam(faction='自己'))
                            fresh_units = [u for u in all_fresh_units if u.actor_id == unit.actor_id]
                            if fresh_units:
                                result = safe_attack_target(api, fresh_units[0], nearest_enemy)
                                if result:
                                    force_success += 1
                                    attack_success += 1
                        
                        if force_success > 0:
                            print(f"[强制结果] ✓成功:{force_success} 个单位强制攻击")
                    
                    # 最终状态总结
                    if attack_success > 0:
                        efficiency = (attack_success / total_attempts) * 100
                        print(f"[攻击效率] {attack_success}/{total_attempts} 单位参与攻击 ({efficiency:.1f}%)")
                    else:
                        print(f"[警告] 没有单位成功攻击！需要检查游戏状态")
            else:
                if last_enemy_count > 0:
                    print("\n[防御] ✓ 敌人已清除")
                    last_enemy_count = 0
            
            time.sleep(1)  # 减少睡眠时间，提高攻击响应速度
            
        except Exception as e:
            # 静默处理错误，避免中断防御线程
            time.sleep(1)  # 减少睡眠时间，提高攻击响应速度
    
    print("\n[后台防御] 已停止")


def start_background_defense(api: GameAPI):
    """启动后台防御线程"""
    global defense_running, defense_thread
    
    if not defense_running:
        defense_running = True
        defense_thread = threading.Thread(target=auto_defense, args=(api,), daemon=True)
        defense_thread.start()
        print("\n" + "=" * 60)
        print("✓ 后台自动防御已启动")
        print("=" * 60)


def stop_background_defense():
    """停止后台防御线程"""
    global defense_running
    defense_running = False
    if defense_thread:
        try:
            defense_thread.join(timeout=2)  # 减少超时时间
        except KeyboardInterrupt:
            # 如果再次中断，直接跳过等待
            pass


def calculate_final_stats(api: GameAPI):
    """计算最终战损统计（使用与红方一致的统计方式）"""
    try:
        # 检查combat_stats是否已经转换为最终格式
        if "army_distribution" in combat_stats:
            print(f"[调试] combat_stats已经是最终格式，直接返回")
            return
        
        # 先保存原始数据，避免在clear()后丢失
        original_produced_units = combat_stats.get("produced_units", {}).copy()
        original_total_produced = combat_stats.get("total_produced", 0)
        original_total_cost = combat_stats.get("total_cost", 0)
        
        print(f"[调试] 原始数据检查:")
        print(f"  original_produced_units: {original_produced_units}")
        print(f"  original_total_produced: {original_total_produced}")
        print(f"  original_total_cost: {original_total_cost}")
        
        # 如果生产记录为空但total_produced不为0，说明数据已丢失
        if not original_produced_units and original_total_produced > 0:
            print(f"[警告] 生产记录为空但total_produced={original_total_produced}，数据可能已丢失")
        
        # 获取蓝方（自己）剩余战斗单位
        mine = api.query_actor(TargetsQueryParam(faction='自己'))
        
        blue_combat_units = []
        unit_counts = {}
        
        print(f"\n[统计] 开始计算最终战损统计...")
        print(f"[统计] 生产记录: {original_produced_units}")
        print(f"[统计] 初始采矿车ID: {initial_harvester_ids}")
        
        # 统计当前地图上的战斗单位（按红方逻辑）
        print(f"[统计] 开始扫描所有单位，使用红方统计逻辑...")
        for unit in mine:
            original_type = getattr(unit, "type", "")
            print(f"[扫描] 单位: {original_type} (ID: {unit.actor_id})")
            
            # 排除建筑类型（与红方一致）
            if original_type in NON_COMBAT_TYPES:
                print(f"  -> [排除] 建筑类型: {original_type}")
                continue
                
            # 排除初始采矿车（与红方一致）
            if original_type == "采矿车" and unit.actor_id in initial_harvester_ids:
                print(f"  -> [排除] 初始采矿车: {original_type} (ID: {unit.actor_id})")
                continue
                
            # 其他所有单位都算作战斗单位（包括主动生产的采矿车）
            blue_combat_units.append(unit)
            print(f"  -> [统计] 战斗单位: {original_type} (ID: {unit.actor_id})")
            
            # 统计各类型单位数量
            if original_type not in unit_counts:
                unit_counts[original_type] = 0
            unit_counts[original_type] += 1
        
        print(f"[统计] 地图上找到 {len(blue_combat_units)} 个战斗单位（按红方统计方式）")
        print(f"[统计] 单位分类计数: {unit_counts}")
        
        # 幸存单位详情（使用字母映射A-E）
        unit_type_details = {}
        for api_type, count in unit_counts.items():
            # 将游戏API类型转换为配置名称，再转换为字母
            config_name = API_TYPE_TO_CONFIG_NAME.get(api_type, api_type)
            letter = CONFIG_NAME_TO_LETTER.get(config_name)
            if letter:
                unit_type_details[letter] = unit_type_details.get(letter, 0) + count
            else:
                print(f"[警告] 未知单位类型映射: {api_type} -> {config_name}")
        
        print(f"[统计] 最终单位详情(字母): {unit_type_details}")
        
        # 获取红方剩余战斗单位（使用相同的统计逻辑）
        enemies = api.query_actor(TargetsQueryParam(faction='敌人')) or []
        red_combat_units = []
        
        for unit in enemies:
            original_type = getattr(unit, "type", "")
            
            # 排除建筑类型（与统计蓝方时一致）
            if original_type in NON_COMBAT_TYPES:
                continue
                
            # 红方没有初始采矿车需要特殊处理，所有非建筑单位都算战斗单位
            red_combat_units.append(unit)
        
        # 判定胜负（优先使用Socket信号）
        global game_over_signal
        print(f"[胜负判定] 调试信息:")
        print(f"  game_over_signal: {game_over_signal}")
        print(f"  蓝方剩余战斗单位: {len(blue_combat_units)}")
        print(f"  红方剩余战斗单位: {len(red_combat_units)}")
        
        if game_over_signal and game_over_signal.get('red_defeated'):
            result = "win"  # 红方已战败，蓝方胜利
            print(f"[胜负判定] *** 基于Socket信号: 红方已败，蓝方胜利 ***")
        elif len(blue_combat_units) == 0:
            result = "loss"  # 蓝方全部阵亡，蓝方失败
            print(f"[胜负判定] 基于自身单位: 蓝方全部阵亡，蓝方失败")
        else:
            result = "ongoing"  # 战斗继续
            print(f"[胜负判定] 基于自身单位: 蓝方仍有{len(blue_combat_units)}个单位，战斗继续")
        
        # 计算战斗时长
        battle_start = combat_stats.get("battle_start_time")
        if battle_start:
            battle_duration = (datetime.now() - battle_start).total_seconds()
        else:
            battle_duration = 0
        
        # 计算蓝方战损比
        blue_surviving = len(blue_combat_units)
        blue_total = original_total_produced
        blue_lost = blue_total - blue_surviving
        blue_damage_ratio = round(blue_lost / blue_total, 4) if blue_total > 0 else 0.0
        
        # 生产分布 (A-E) - 与红方格式保持一致
        army_distribution = {}
        print(f"[调试] 开始计算army_distribution:")
        print(f"  original_produced_units: {original_produced_units}")
        print(f"  NAME_TO_LETTER映射: {NAME_TO_LETTER}")
        
        for name, produced_count in original_produced_units.items():
            letter = NAME_TO_LETTER.get(name)
            print(f"  映射: {name} -> {letter} (数量: {produced_count})")
            if letter:
                army_distribution[letter] = army_distribution.get(letter, 0) + produced_count
                print(f"    army_distribution[{letter}] = {army_distribution[letter]}")
            else:
                print(f"    [警告] 未找到映射: {name}")
        
        # 确保所有字母键存在
        for letter in ["A", "B", "C", "D", "E"]:
            army_distribution.setdefault(letter, 0)
        
        print(f"[调试] 最终army_distribution: {army_distribution}")

        # 检测是否为单一兵种（使用army_distribution字母）
        blue_single_type = None
        produced_letters = [k for k, v in army_distribution.items() if v > 0]
        if len(produced_letters) == 1:
            blue_single_type = produced_letters[0]
        
        print(f"[统计] 战损计算: 生产{blue_total} - 幸存{blue_surviving} = 损失{blue_lost} (损失率:{blue_damage_ratio:.2%})")
        
        # 更新combat_stats为简化的final_battle_record格式（与红方字段一致）
        combat_stats.clear()
        combat_stats.update({
            "battle_id": f"blue_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "army_distribution": army_distribution,            # A-E生产数量
            "unit_type_details": unit_type_details,            # 中文名称幸存数量
            "total_cost": original_total_cost,
            "result": result,
            "battle_duration_seconds": int(battle_duration),
            "damage_sustained_ratio": blue_damage_ratio,
            "red_combat_units": blue_surviving,  # 蓝方视角：自己的战斗单位
            "blue_combat_units": len(red_combat_units),  # 蓝方视角：敌方战斗单位
            "blue_single_type": blue_single_type,
            "total_produced": blue_total,
            "blue_lost": blue_lost,  # 蓝方视角：自己的损失
            # 保留兼容字段供Socket发送使用
            "final_surviving": blue_surviving,
            "loss_count": blue_lost,
            "loss_rate": round((blue_lost / blue_total) * 100, 2) if blue_total > 0 else 0.0
        })
        
    except Exception as e:
        print(f"[统计] 计算最终数据时出错: {e}")
        import traceback
        traceback.print_exc()


def save_combat_log():
    """保存战损日志到文件"""
    try:
        log_dir = "combat_logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{log_dir}/combat_log_{timestamp}.json"
        
        with open(log_filename, 'w', encoding='utf-8') as f:
            json.dump(combat_stats, f, ensure_ascii=False, indent=2)
        
        print(f"\n[日志] 战损统计已保存到: {log_filename}")
        return log_filename
    except Exception as e:
        print(f"\n[日志] 保存失败: {e}")
        return None


def print_combat_summary():
    """打印战损统计摘要（完整终局报告）"""
    print("\n" + "=" * 60)
    print("蓝方终局记录")
    print("=" * 60)
    
    if combat_stats:
        print(f"战斗结果: {combat_stats.get('result', 'unknown')}")
        print(f"作战单位生产统计(字母): {combat_stats.get('army_distribution', {})}")
        # 幸存战斗单位详情
        unit_details = combat_stats.get('unit_type_details', {})
        if unit_details:
            print(f"幸存战斗单位详情(字母):")
            for letter, count in unit_details.items():
                tank_name = TANKS.get(letter, {}).get('name', letter)
                print(f"  - {letter}({tank_name}): {count} 辆")
        else:
            print("幸存战斗单位详情: 无（全部阵亡）")
        print(f"总生产数量: {combat_stats.get('total_produced', 0)} 辆")
        print(f"损失数量: {combat_stats.get('blue_lost', 0)} 辆")
        print(f"蓝方战损比: {combat_stats.get('damage_sustained_ratio', 0):.2%}")
        print(f"战斗时长: {combat_stats.get('battle_duration_seconds', 0)} 秒")
        print(f"总成本: ${combat_stats.get('total_cost', 0)}")
        if combat_stats.get('blue_single_type'):
            print(f"蓝方单一兵种(字母): {combat_stats.get('blue_single_type')}")
    else:
        print("⚠️  无战损统计数据")
    print("=" * 60)


def manual_tank_production(api: GameAPI):
    """手动坦克生产循环"""
    print("\n" + "=" * 60)
    print("阶段2: 手动坦克生产 (后台自动防御已启动)")
    print("=" * 60)
    print(f"预算限制: ${BUDGET_LIMIT}")
    print("输入格式: 坦克编号 (例如: 2 表示生产最多的重型坦克)")
    print("程序会自动计算并生产最大数量")
    print("输入 'done' 或 'd' 完成生产")
    print("=" * 60)
    
    total_spent = 0
    
    while True:
        remaining_budget = BUDGET_LIMIT - total_spent
        
        if remaining_budget <= 0:
            print("\n" + "=" * 60)
            print("预算已用完！")
            print(f"总花费: ${total_spent}")
            print("=" * 60)
            break
        
        show_tank_menu(remaining_budget)
        
        try:
            user_input = input("\n请输入选择 (编号): ").strip().lower()
            
            if user_input in ['done', 'd', 'quit', 'q', 'exit']:
                print("\n生产完成，继续防御...")
                break
            
            tank_id = user_input
            
            if tank_id not in TANKS:
                print("❌ 无效的坦克编号！")
                continue
            
            tank_info = TANKS[tank_id]
            
            # 自动计算最大数量
            max_count = remaining_budget // tank_info["cost"]
            
            if max_count <= 0:
                print(f"❌ 预算不足！{tank_info['name']} 单价 ${tank_info['cost']}，剩余 ${remaining_budget}")
                continue
            
            # 显示将要生产的数量
            total_cost = tank_info["cost"] * max_count
            print(f"\n将生产 {max_count} 辆 {tank_info['name']}")
            print(f"花费: ${total_cost} | 剩余预算: ${remaining_budget - total_cost}")
            confirm = input("确认？(y/n): ").strip().lower()
            
            if confirm != 'y':
                print("取消生产")
                continue
            
            # 执行生产
            actual_cost = produce_tank(api, tank_info, max_count)
            total_spent += actual_cost
            
            print(f"\n当前总花费: ${total_spent} / ${BUDGET_LIMIT}")
            
        except KeyboardInterrupt:
            print("\n\n用户中断")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")
    
    print("\n" + "=" * 60)
    print("生产阶段结束")
    print(f"总花费: ${total_spent} / ${BUDGET_LIMIT}")
    print("=" * 60)


# ===== 主程序 =====
def main():
    print("=" * 60)
    print("手动坦克生产模式 + Socket通信")
    print("阶段1: 建造完整基地")
    print("阶段2: 手动/Socket生产坦克（预算 $10,000）")
    print("       + 后台自动防御")
    print("通信: 支持通过Socket接收ai_builder_v3.py指令")
    print("=" * 60)
    
    # 启动Socket服务器线程
    socket_thread = threading.Thread(target=socket_server_thread, daemon=True)
    socket_thread.start()
    print("\n✓ Socket服务器已启动（端口 8888）")
    
    # 记录游戏开始时间
    combat_stats["battle_start_time"] = datetime.now()
    combat_stats["game_start_time"] = datetime.now().isoformat()
    
    # 初始化 API
    api = GameAPI(host="localhost", port=7445, language="zh")
    
    # 查询并显示地图信息
    print("\n[地图信息] 查询地图大小...")
    try:
        map_info = api.map_query()
        print(f"✓ 地图大小: {map_info.MapWidth} × {map_info.MapHeight}")
        
        # 根据地图大小调整目标位置
        center_x = map_info.MapWidth // 2
        center_y = map_info.MapHeight // 2
        print(f"✓ 地图中心点: ({center_x}, {center_y})")
        
        # 为基地车选择合适的位置（避免太靠近边缘）
        base_x = min(80, map_info.MapWidth - 10)
        base_y = min(80, map_info.MapHeight - 10)
        print(f"✓ 蓝方基地建议位置: ({base_x}, {base_y})")
        
    except Exception as e:
        print(f"⚠️ 获取地图信息失败: {e}")
        # 使用默认值
        center_x, center_y = 45, 45
        base_x, base_y = 80, 80
        print(f"✓ 使用默认设置: 地图中心({center_x}, {center_y}), 基地位置({base_x}, {base_y})")
    
    # 部署基地车
    print("\n[初始化] 部署建造厂...")
    try:
        api.deploy_mcv_and_wait(5)
        print("✓ 建造厂就绪")
    except Exception as e:
        print(f"提示: {e}")
    
    time.sleep(3)
    
    # 阶段1: 建造所有建筑
    build_all_structures(api)
    
    time.sleep(5)
    
    # 启动后台防御
    start_background_defense(api)
    
    time.sleep(2)
    
    # 阶段2: 生产坦克（支持Socket指令；可选手动交互）
    if ENABLE_MANUAL_PRODUCTION:
        try:
            manual_tank_production(api)
        except KeyboardInterrupt:
            print("\n\n生产阶段用户中断")
        except Exception as e:
            print(f"\n生产阶段异常: {e}")
    else:
        print("\n[生产阶段] 跳过手动交互，等待红方通过Socket下发生产指令…")
        print("[提示] 红方可发送 'produce_tank' 指令；蓝方后台防御与队列处理持续运行。")
    
    # 继续防御模式
    print("\n" + "=" * 60)
    print("生产阶段结束，继续自动防御...")
    print("按 Ctrl+C 退出程序并查看战损统计")
    print("=" * 60)
    
    try:
        # 声明全局变量
        global game_over_signal, defense_running, game_over_event
        
        # 保持主线程运行，让后台防御继续工作
        # 同时检查游戏结束信号
        check_count = 0
        while defense_running:
            # 每5次循环显示一次状态（约5秒）- 更频繁的检查
            check_count += 1
            if check_count >= 5:
                print(f"\n[主循环状态] defense_running={defense_running}")
                print(f"[主循环状态] game_over_signal={game_over_signal}")
                print(f"[主循环状态] game_over_event.is_set()={game_over_event.is_set()}")
                check_count = 0
                
            # 检查游戏结束事件和信号
            if game_over_event.is_set() and game_over_signal and game_over_signal.get('red_defeated'):
                print(f"\n[主循环] *** 检测到game_over_signal! ***")
                print(f"[主循环] game_over_signal内容: {game_over_signal}")
                print("\n" + "=" * 60)
                print("收到红方战败通知")
                print("=" * 60)
                print(f"红方战败原因: {game_over_signal.get('reason', '未知原因')}")
                print("蓝方获胜！正在计算最终战损统计...")
                print("=" * 60)
                
                # 计算战损统计
                try:
                    print("\n正在计算最终战损统计...")
                    calculate_final_stats(api)
                    print_combat_summary()
                    # 不保存本地日志，直接发送统计
                    # 尝试发送战损统计给红方（持续重试）
                    print(f"\n正在发送战损统计给红方...")
                    stats_sent = False
                    retry_count = 0
                    max_retries = 3  # 最多3次大的重试周期
                    
                    while not stats_sent and retry_count < max_retries:
                        retry_count += 1
                        print(f"\n[发送战损] 第{retry_count}次大的发送尝试...")
                        print('22222222222222222222222222222222222222')
                        print(combat_stats)
                        stats_sent = send_battle_stats_to_red(combat_stats)
                        
                        if stats_sent:
                            print(f"\n[成功] 战损统计已成功发送给红方并得到确认")
                            game_over_signal['stats_sent'] = True
                            # 成功发送后停止防御并退出主循环
                            defense_running = False
                            break  # 退出重试循环
                        else:
                            if retry_count < max_retries:
                                print(f"\n[重试] 第{retry_count}次大的发送失败，等待20秒后重试...")
                                time.sleep(20)  # 大的重试间隔
                            else:
                                print(f"\n[失败] 所有发送尝试都已失败")
                    
                    if not stats_sent:
                        print(f"\n[处理完成] 战损统计发送失败，但程序已完成所有必要操作:")
                        print(f"  ✓ 战损统计已计算完成")
                        print(f"  ✓ 战损日志已保存到本地文件") 
                        print(f"  ✓ 蓝方获胜确认")
                        print(f"\n[可能原因] 红方程序可能已退出，无法接收战损统计")
                        print(f"[建议] 检查红方程序状态或查看本地保存的战损日志")
                        # 标记为已处理，停止防御并退出主循环
                        game_over_signal['stats_sent'] = True
                        defense_running = False
                        
                except Exception as e:
                    print(f"\n[错误] 处理战损统计时出错: {e}")
                    import traceback
                    traceback.print_exc()
                    # 出错时也不退出程序
                    game_over_signal = None
                    
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n程序异常: {e}")
    
    # 如果程序因为成功发送战损统计而退出
    if game_over_signal and game_over_signal.get('stats_sent'):
        print("\n" + "=" * 60)
        print("蓝方任务完成")
        print("=" * 60)
        print("✓ 红方战败通知已处理")
        print("✓ 战损统计已计算并发送给红方")
        print("✓ 红方已确认接收战损数据")
        print("✓ 蓝方程序正常退出")
        print("=" * 60)
    else:
        # 其他情况的退出处理
        try:
            stop_background_defense()
        except:
            pass
        
        # 如果还没发送过战损统计，尝试最后一次
        if not (game_over_signal and game_over_signal.get('stats_sent')):
            try:
                print(f"\n[最后尝试] 计算并发送战损统计...")
                calculate_final_stats(api)
                print_combat_summary()
                # 不保存本地日志，直接发送统计
                
                # 自动尝试发送战损统计
                print(f"\n[自动发送] 正在发送战损统计到红方...")

                success = send_battle_stats_to_red(combat_stats)
                if success:
                    print("[自动发送] ✓ 战损统计发送成功")
                else:
                    print("[自动发送] ✗ 战损统计发送失败")
                    
            except Exception as e:
                print(f"\n[错误] 最后统计保存失败: {e}")
                import traceback
                traceback.print_exc()
    
    print("\n程序结束")


if __name__ == "__main__":
    main()

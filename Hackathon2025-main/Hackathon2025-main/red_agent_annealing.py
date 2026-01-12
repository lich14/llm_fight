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
import socket
import threading
from typing import List, Dict, Any
from datetime import datetime
from tenacity import retry, wait_random_exponential, stop_after_attempt

# 添加库路径
current_dir = os.path.dirname(os.path.abspath(__file__))
library_path = os.path.join(current_dir, 'examples', 'mofa', 'examples', 'openra-controller')
sys.path.insert(0, library_path)

from OpenRA_Copilot_Library.game_api import GameAPI
from OpenRA_Copilot_Library.models import TargetsQueryParam, Location, Actor


# ===== 单位名称映射 =====
UNIT_DEFS = {
    "A": {"name": "防空车",     "cost": 300,  "build_time": 4},
    "B": {"name": "重型坦克",   "cost": 575,  "build_time": 10},
    "C": {"name": "猛犸坦克",   "cost": 1000, "build_time": 12},
    "D": {"name": "V2火箭发射车",   "cost": 450,  "build_time": 6},
    "E": {"name": "采矿车",     "cost": 550,  "build_time": 7},
}


LETTER_TO_NAME  = {k: v["name"] for k, v in UNIT_DEFS.items()}
NAME_TO_LETTER  = {v["name"]: k for k, v in UNIT_DEFS.items()}
LETTER_TO_COST  = {k: v["cost"] for k, v in UNIT_DEFS.items()}

# 游戏API返回的单位类型到配置名称的映射（与蓝方一致）
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
MIN_TANK_COST   = min(v["cost"] for v in UNIT_DEFS.values())

# 预算限制
BUDGET_LIMIT = 10000

# 全局生产统计
production_stats = {
    "total_cost": 0,
    "units_produced": {}
}

INITIAL_HARVESTER_IDS = set()
NON_COMBAT_TYPES = {
    '建造厂', '电厂', '核电站', '矿场', '兵营', '战车工厂',
    '雷达', '维修厂', '科技中心', '机场', '火焰塔',
    '特斯拉线圈', '防空导弹', '储存罐', '发电厂', '雷达站',
    '空军基地', '特斯拉塔'
}

# 固定战损日志文件名
BATTLE_LOG_FILE = "battle_results.json"

# 蓝方战损数据存储
blue_battle_stats = None

HISTORY_FILE = "game_history.json"

def load_history_games():
    """
    从 game_history.json 加载历史对局记录。
    如果文件不存在，返回空列表。
    """
    if not os.path.exists(HISTORY_FILE):
        print(f"[历史记录] 文件 {HISTORY_FILE} 不存在，这是第一局游戏")
        return []  # 返回空列表
    
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        print(f"[历史记录] 加载了 {len(history)} 局历史对局")
        return history
    except Exception as e:
        print(f"[历史记录] 加载失败: {e}")
        return []  # 加载失败时返回空列表
    

def append_history_record(record):
    hist = load_history_games()
    hist.append(record)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

import json
import re

def extract_json(text: str) -> str:
    """
    从任意 LLM 输出中提取第一个可解析 JSON 对象。
    自动忽略 markdown、注释、代码块、奇怪符号。

    返回：纯 JSON 字符串
    """

    # 去掉 markdown 代码块
    text = text.replace("```json", "").replace("```", "").strip()

    # 直接尝试整体解析
    try:
        json.loads(text)
        return text
    except:
        pass

    # 尝试用正则提取最外层大括号块
    json_candidates = re.findall(r"\{[\s\S]*\}", text)
    for cand in json_candidates:
        try:
            json.loads(cand)
            return cand
        except:
            continue

    raise ValueError(f"未找到有效 JSON：{text[:200]}")


def simplify_full_history(history_list):
    simplified = []

    for rec in history_list:
        red_init = rec.get("red", {}).get("initial_distribution", {})
        blue_init = rec.get("blue", {}).get("initial_distribution", {})

        # 红方结果来自 score_eval.category
        category = rec.get("score_eval", {}).get("category", "未知结果")

        simplified.append({
            "red_combo": red_init,
            "blue_combo": blue_init,
            "red_result": category
        })

    return simplified


def call_sa_llm(history):
    """
    使用 StreamingAgent 调用 SA Prompt，让 LLM 同时返回 red_combo / blue_combo。
    
    Args:
        history: 简化历史结构的列表
        best_combo: 当前最强组合，默认为单一C类型
        temperature: 模拟退火温度
    """
    
    # 如果没有提供best_combo，使用默认值
    # if best_combo is None:
    #     best_combo = {"C": 10}  # 默认最强组合
    
    # 构造完整的输入数据
    payload_to_llm = {
        "total_rounds": 20,  # 20
        "current_round": len(history) + 1,
        "history_games": history
    }

    # 格式化为JSON文本
    input_text = json.dumps(payload_to_llm, ensure_ascii=False, indent=2)
    
    # 构造 agent（退火提示词作为 role）
    agent = StreamingAgent(
        role=SA_PROMPT,            # 你的退火提示词（role 即 system prompt）
        model="gemini_2_5_flash"
    )

    # LLM 调用（user message 包含完整的SA输入）
    raw = agent.chat(input_text)

    print("\n🤖 LLM 原始响应：")
    print("-" * 50)
    print(raw)
    print("-" * 50)

    # 提取 JSON（自动去除 markdown / 代码块 / 噪声）
    try:
        clean = extract_json(raw)
        data = json.loads(clean)
        print("\n🧹 JSON 解析成功：", data)
        return data
    except Exception as e:
        print("❌ LLM 返回 JSON 无法解析:", e)
        raise


# 全局标志和事件
game_end_requested = False
game_end_event = threading.Event()
blue_battle_stats = None

# ===== 接收蓝方战损统计的Socket服务器 =====
def start_battle_stats_server(host='0.0.0.0', port=8899):
    """启动Socket服务器接收蓝方战损统计"""
    def server():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            s.listen(5)
            print(f"[Socket服务器] 战损统计服务器已启动，监听端口 {port}")
            
            while True:
                try:
                    conn, addr = s.accept()
                    data = conn.recv(65536)
                    if data:
                        message = json.loads(data.decode('utf-8'))
                        if message.get('action') == 'report_battle_stats':
                            global blue_battle_stats, game_end_requested, game_end_event
                            blue_battle_stats = message.get('blue_stats')
                            print(f"[Socket服务器] 已接收蓝方战损统计")
                            print(f"[Socket服务器] 蓝方数据: 生产{blue_battle_stats.get('total_produced', 0)}辆，损失{blue_battle_stats.get('loss_count', 0)}辆")
                            
                            # 设置退出标志，通知主程序结束游戏
                            game_end_requested = True
                            game_end_event.set()
                            print(f"[Socket服务器] 已设置游戏结束标志: game_end_requested={game_end_requested}")
                            print(f"[Socket服务器] 已触发游戏结束事件")
                            print(f"[Socket服务器] *** 蓝方战败，红方获胜！***")
                            
                            # 发送确认响应给蓝方
                            response = {
                                'status': 'success',
                                'message': '红方已成功接收蓝方战损统计'
                            }
                            conn.send(json.dumps(response, ensure_ascii=False).encode('utf-8'))
                            print(f"[Socket服务器] 已向蓝方发送确认响应")
                        else:
                            # 其他类型的消息
                            response = {
                                'status': 'error',
                                'message': f'未知消息类型: {message.get("action", "unknown")}'
                            }
                            conn.send(json.dumps(response, ensure_ascii=False).encode('utf-8'))
                    conn.close()
                except Exception as e:
                    print(f"[Socket服务器] 处理连接错误: {e}")
                    try:
                        conn.close()
                    except:
                        pass
        except Exception as e:
            print(f"[Socket服务器] 启动失败: {e}")
    
    # 使用守护线程启动服务器
    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    return thread

def build_clean_history_record(
    red_final_stats: dict,
    blue_stats: dict
) -> dict:
    """
    构造【唯一规范化】的历史战局记录（严格裁剪版）
    """

    duration = red_final_stats.get("battle_duration_seconds", 0)

    # --- Red ---
    red_initial = {}
    for k in ["A", "B", "C", "D", "E"]:
        red_initial[k] = int(
            red_final_stats.get("army_distribution", {}).get(k, 0)
        )

    red_remaining = {}
    for k, v in red_final_stats.get("unit_type_details", {}).items():
        if v > 0:
            red_remaining[k] = v

    red_result = red_final_stats.get("result")
    if red_result == "win":
        r_result = "win"
    elif red_result == "loss":
        r_result = "lose"
    else:
        r_result = "draw"
    
    # --- Blue ---
    # 蓝方初始分布：来自 socket 对方“生产总数 + 单一兵种”
    # blue_initial = {k: 0 for k in ["A", "B", "C", "D", "E"]}
    # blue_type = blue_stats.get("single_type") or blue_stats.get("type")
    blue_initial = blue_stats.get("army_distribution")
    blue_remaining = blue_stats.get("unit_type_details")

    blue_result = blue_stats.get("result")
    if blue_result == "win":
        b_result = "win"
    elif blue_result == "loss":
        b_result = "lose"
    else:
        b_result = "draw"
    
    print(duration)
    print(red_initial)
    print(r_result)
    print(red_remaining)
    print(blue_initial)
    print(b_result)
    print(blue_remaining)

    return {
        "timestamp": datetime.now().isoformat(),
        "duration": duration,
        "red": {
            "initial_distribution": red_initial,
            "result": r_result,
            "remaining": red_remaining
        },
        "blue": {
            "initial_distribution": blue_initial,
            "result": b_result,
            "remaining": blue_remaining
        }
    }

def evaluate_score_with_llm(final_stats):
    try:
        scoring_agent = StreamingAgent(
            role=SCORE_PROMPT,
            model="gemini_2_5_flash"
        )
        
        # 从clean_record结构中提取red方数据
        payload = final_stats

        raw = scoring_agent.chat(
            SCORE_PROMPT + "\n\n" + json.dumps(payload, ensure_ascii=False)
        )
        
        # 添加错误处理防止JSON解析失败
        if not raw or not raw.strip():
            print(f"[WARNING] LLM返回空响应，使用默认评分")
            return {"score": 0.0, "analysis": "LLM返回空响应"}
        
        # 去除可能的markdown代码块标记
        cleaned_raw = raw.strip()
        if cleaned_raw.startswith('```json'):
            cleaned_raw = cleaned_raw[7:]  # 去除 ```json
        if cleaned_raw.startswith('```'):
            cleaned_raw = cleaned_raw[3:]   # 去除 ```
        if cleaned_raw.endswith('```'):
            cleaned_raw = cleaned_raw[:-3]  # 去除结尾的 ```
        cleaned_raw = cleaned_raw.strip()
        
        return json.loads(cleaned_raw)
        
    except json.JSONDecodeError as e:
        print(f"[WARNING] JSON解析失败: {e}")
        print(f"[DEBUG] LLM原始响应: {repr(raw)}")
        return {"score": 0.0, "analysis": f"JSON解析失败: {e}"}
    except Exception as e:
        print(f"[ERROR] 评分计算失败: {e}")
        return {"score": 0.0, "analysis": f"评分计算失败: {e}"}


def save_combined_battle_log(red_stats, blue_stats=None):
    try:
        clean_record = build_clean_history_record(
            red_final_stats=red_stats,
            blue_stats=blue_stats or {}
        )
        score_eval = evaluate_score_with_llm(clean_record)
        clean_record["score_eval"] = score_eval

        append_history_record(clean_record)

        with open(BATTLE_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(clean_record, ensure_ascii=False) + '\n')

        print(f"\n[历史战局] 已记录一条 clean record")
        return True

    except Exception as e:
        print(f"\n[历史战局] 保存失败: {e}")
        return False


# ===== Socket 通信配置 =====
# 本机IP: 172.22.63.66 (红方)
# 蓝方服务器IP: 172.22.63.34
BLUE_AGENT_HOST = '172.22.63.66'  # 蓝方服务器IP
BLUE_AGENT_PORT = 8888


def _send_socket_request(request: dict, timeout: int = 5) -> dict:
    """通用Socket请求发送函数，去除重复代码
    
    Args:
        request: 要发送的请求字典
        timeout: 连接超时时间
    
    Returns:
        响应字典
    """
    try:
        # 创建Socket连接
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(timeout)
        client_socket.connect((BLUE_AGENT_HOST, BLUE_AGENT_PORT))
        
        # 发送请求
        client_socket.send(json.dumps(request).encode('utf-8'))
        
        # 接收响应
        response_data = client_socket.recv(4096)
        response = json.loads(response_data.decode('utf-8'))
        
        client_socket.close()
        return response
    
    except socket.timeout:
        print(f"[Socket客户端] 连接超时: {BLUE_AGENT_HOST}:{BLUE_AGENT_PORT}")
        return {'status': 'error', 'message': '连接超时'}
    except ConnectionRefusedError:
        print(f"[Socket客户端] 连接被拒绝，请确保blue_agent.py已在蓝方服务器上启动")
        return {'status': 'error', 'message': '连接被拒绝'}
    except Exception as e:
        print(f"[Socket客户端] 错误: {e}")
        return {'status': 'error', 'message': str(e)}


def send_tank_production_order(tank_type: str) -> dict:
    """通过Socket向blue_agent.py发送坦克生产指令（蓝方会自动建造到预算用完）
    
    Args:
        tank_type: 坦克类型（重型坦克/猛犸坦克/防空车/V2火箭发射车/采矿车）
    
    Returns:
        响应字典
    """
    request = {
        'action': 'produce_tank',
        'tank_type': tank_type
    }
    
    print(f"[Socket客户端] 发送指令: 建造 {tank_type} (蓝方将自动建造到预算用完)")
    response = _send_socket_request(request)
    print(f"[Socket客户端] 收到响应: {response}")
    
    return response


def send_multi_tank_production_order(tank_distribution: dict) -> dict:
    """通过Socket向blue_agent.py发送多种类型坦克生产指令
    
    Args:
        tank_distribution: 坦克类型和数量分布，例如 {"A": 5, "B": 3}
    
    Returns:
        响应字典
    """
    # 计算总成本
    total_cost = sum(LETTER_TO_COST[tank_type] * count for tank_type, count in tank_distribution.items())
    if total_cost > 10000:
        return {'status': 'error', 'message': f'总成本 ${total_cost} 超出预算 $10,000'}
    
    request = {
        'action': 'produce_multi_tanks',
        'tank_distribution': tank_distribution
    }
    
    print(f"[Socket客户端] 发送多坦克生产指令: {tank_distribution}")
    response = _send_socket_request(request)
    print(f"[Socket客户端] 收到响应: {response}")
    
    return response


def send_blue_agent_combo(blue_combo: dict) -> dict:
    """发送蓝方坦克组合生产指令
    
    Args:
        blue_combo: 蓝方坦克组合，例如 {"A": 5, "B": 3}
    
    Returns:
        响应字典
    """
    return send_multi_tank_production_order(blue_combo)


# send_red_multi_tank_production_order 已合并到 send_multi_tank_production_order
# 为保持兼容性，创建别名
send_red_multi_tank_production_order = send_multi_tank_production_order


def report_game_over_to_blue(side: str, status: str, reason: str = "") -> dict:
    """通知蓝方当前战局结果（主要在红方失败时调用）"""
    request = {
        'action': 'report_game_over',
        'side': side,
        'status': status,
        'reason': reason
    }
    
    response = _send_socket_request(request)
    if response.get('status') == 'success':
        print(f"[Socket客户端] 已上报战局: {status} ({reason})")
    else:
        print(f"[Socket客户端] 上报战局失败: {response.get('message')}")
    
    return response


def query_blue_agent_status() -> dict:
    """查询blue_agent.py的状态"""
    request = {'action': 'query_status'}
    return _send_socket_request(request, timeout=3)


# ===== StreamingAgent (复用自 fight.py) =====
class StreamingAgent:
    def __init__(
            self,
            role: str,
            api_key: str = "sk-1ceae40f665683d838eecb22bddbf710af8e20900d139b45f57de52a9ac3e663",
            model: str = "gpt-4o",
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
           stop=stop_after_attempt(3),
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
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"[LLM] 请求中... (尝试 {attempt+1}/{max_retries})")
                with requests.post(self.api_base,
                                   headers=self.headers,
                                   json=payload,
                                   stream=True,
                                   timeout=60) as r:  # 添加60秒超时
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
                    
                    if full and full != "null":
                        print(f"[LLM] ✓ 收到响应 ({len(full)} 字符)")
                        return full
                        
            except requests.exceptions.Timeout:
                print(f"[LLM] ✗ 请求超时 (尝试 {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    raise
            except requests.exceptions.RequestException as e:
                print(f"[LLM] ✗ 请求失败: {e} (尝试 {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    raise
        
        if not full or full == "null":
            raise Exception("LLM返回空响应")
        return full

SA_PROMPT = """
你是一个“坦克组合优化代理”，使用模拟退火（Simulated Annealing, SA）在组合空间中寻找最强的兵种组合。

你的输入将包含：
- total_rounds：本轮实验计划的总轮数（例如 20）
- current_round：当前是第几轮（例如 7）
- history_games：已有历史对局的精简格式

你需要根据这些信息**自主**推断：
1. 当前阶段的全局最强组合 best_combo  
2. 当前应该使用的退火温度 temperature（0~1 之间）  
3. 本轮要探索的 challenger 组合  
4. 本轮的红/蓝阵营分配方式，尤其要补齐缺失的对称测试  

========================================================
【坦克模型（先验知识）】
有五种坦克：A, B, C, D, E  
它们的单兵种相对强弱顺序稳定且可靠：
    C > B > A > D > E

因此，如果只考虑单一兵种，则最强的组合为10个C。现在由于你的任务是寻找更强的兵种组合，所以你需要在能够考虑混合兵种的情况下，找到最强的组合。
此排序仅作为组合优化过程的启发式参考，而组合强度必须从历史中学习。

========================================================
【预算规则】
每方预算上限为 10000。

单价：
- A: 300
- B: 575
- C: 1000
- D: 450
- E: 550

你的 red_combo 与 blue_combo 必须满足：
    Σ count[type] * price[type] ≤ 10000

你可以在内部推理中调整数量，但最终输出必须合法。

========================================================
【自主学习 best_combo 的规则】
你需要从 history_games 中学习当前最强组合，这不是人工输入，而是全局从数据中推断的。

你必须综合考虑：
- 胜负质量（如 “高质量胜利” 比 “普通胜利”更强）
- 是否完成了对称测试（红与蓝互换阵营都胜出）
- 该组合在多场对局中的稳健性（低波动性）
- 不可仅凭一场胜利将某组合视为最强

best_combo 必须是当前 evidence 下“最稳定、最具统治力”的组合。

========================================================
【对称实验处理】
对于组合对 (A, B)，必须存在：

1. 红=A, 蓝=B  
2. 红=B, 蓝=A  

两种方向的对局至少各一次，才能判断真实强弱。

你必须检查 history_games：

- 若某组合对缺乏对称测试 → 本轮优先补齐缺失方向  
- 若对称已完成 → 可以尝试新的 challenger 组合  

========================================================
【模拟退火（SA）策略】
你必须自主设定当前温度 temperature：

- early stage (current_round / total_rounds ≈ 0.0–0.3)：温度高 → 大步探索  
- mid stage (≈0.3–0.7)：温度中 → 适度扰动  
- late stage (≈0.7–1.0)：温度低 → 局部微调  

temperature 必须是 0~1 的浮点数。

本轮 challenger 组合应根据温度调整：
- 高温：允许加入新兵种或大幅修改数量  
- 中温：部分替换少量兵种，尝试小规模混编  
- 低温：仅微调 best_combo（±1~2 辆）  

========================================================
【本轮任务】
你必须完成三件事：

1. **推断 best_combo**  
   从 history 推断当前最强且对称验证充分的组合。

2. **生成 challenger_combo**  
   根据 temperature 在 best_combo 附近扰动，预算必须合法。

3. **决定红/蓝阵营分配**
   根据 history 判断对称测试是否缺失：
   - 若缺失某个方向 → 本轮分配必须补齐  
   - 若已完成对称测试 → 任意选择一个方向即可  

========================================================
【最终输出格式（必须严格 JSON，无多余文字）】

{
  "red_combo": {...},
  "blue_combo": {...},
  "new_temperature": 0.xx,
  "best_combo": {...},
  "reason": "解释你如何基于 history + SA 推断 best_combo、生成 challenger、温度策略、阵营分配逻辑"
}

要求：
- JSON 外不得出现任何内容
- red_combo & blue_combo 都必须合法（预算 ≤ 10000）
- best_combo 必须依据 history 自动推断
- new_temperature 必须基于当前轮数自动计算
- reason 要写明：
    - 为什么 best_combo 是最强候选
    - challenger 的扰动策略（基于 SA 温度）
    - 阵营分配是否为了补齐对称测试
"""

SCORE_PROMPT = """
你是红方实验的赛后评估器。

你需要根据给定的终局信息，
为本局红方所选择的坦克方案计算一个“表现分数（score）”。

------------------------------------------------
【评分规则（必须严格遵守）】

本局 score 等于红方优势值 A：

A =
    α × outcome
  + β × (R_red − R_blue)
  + γ × outcome × time_factor

其中权重固定为：

- α = 1.0   （胜负权重）
- β = 1.5   （兵力残余差权重）
- γ = 0.3   （速度加成权重）

------------------------------------------------
【变量定义】

- outcome =
    +1  （red 获胜）
    −1  （red 失败）

- R_side（兵力保有率） =
    战斗结束时该方剩余坦克的“总价值”
    ÷
    战斗开始时该方坦克的“初始总价值”

- 坦克价值（用于计算总价值）：
    A : 300
    B : 575
    C : 1000
    D : 450
    E : 550

- time_factor =
    clip(1 − duration / 1200, 0, 1)

------------------------------------------------
【评分含义提示】

- 胜负是最重要的信号（α = 1.0）
- 同样的胜利中，兵力保存更优的一方评分更高（β = 1.5）
- 在胜负结果相同的情况下，更快结束战斗的对局优于拖延的对局（γ = 0.3）
- 即便失败，如果有效消耗了对方高价值兵力，也具有信息价值
- 迅速、低交换率的失败是最低价值的失败

你不需要计算到非常精确的小数，
但你的分数应在符号、相对大小和趋势上
与上述公式保持一致。

------------------------------------------------
【你的任务】

1. 根据输入数据，估计本局的 score（即红方优势值 A，可为近似值）
2. 用一句话解释为什么该分数偏高或偏低
3. 判断这是一次：
   - 高质量胜利
   - 一般胜利
   - 有信息价值的失败
   - 低价值失败

------------------------------------------------
【输入数据格式】

你将收到一个 JSON，包含：
- red.initial_distribution
- red.remaining
- blue.initial_distribution
- blue.remaining
- red.result
- duration

------------------------------------------------
【输出格式（必须是 JSON）】

{
  "score": <数值或近似数值>,
  "assessment": "<一句话评价>",
  "category": "<高质量胜利 | 一般胜利 | 有信息价值的失败 | 低价值失败>"
}

不要输出任何 JSON 以外的内容。
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
            # time.sleep(2)
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
    
    # 计算电力余量
    power_margin = info.Power
    power_usage = info.PowerProvided - info.Power
    
    print(f"电力状态检查: {info.Power}/{info.PowerProvided} (余量: {power_margin}, 使用: {power_usage})")
    
    # 如果电力余量低于200或为负数，需要建造更多电力
    if power_margin < 200:
        print(f"\n⚠️  电力不足！需要建造更多电力设施")
        print(f"   当前余量: {power_margin} (建议余量 ≥ 200)")
        
        # 计算需要建造的核电站数量
        needed_power = 200 - power_margin
        nuclear_plants_needed = max(1, (needed_power + 699) // 700)  # 核电站提供700电力
        
        print(f"   需要建造 {nuclear_plants_needed} 个核电站")
        
        # 建造核电站
        for i in range(nuclear_plants_needed):
            if info.Cash >= 250:  # 核电站成本250
                print(f"   建造第 {i+1} 个核电站...")
                try:
                    api.produce("核电站", 1, True)
                    print(f"   ✓ 核电站 #{i+1} 已下单")
                    time.sleep(2)  # 短暂等待
                    
                    # 更新资金信息
                    info = api.player_base_info_query()
                except Exception as e:
                    print(f"   ✗ 建造核电站失败: {e}")
                    break
            else:
                print(f"   资金不足，无法建造更多核电站 (需要${250*(nuclear_plants_needed-i)}，当前${info.Cash})")
                break
        
        # 等待建造完成并再次检查
        print(f"\n等待核电站建造完成...")
        time.sleep(15)
        
        final_info = api.player_base_info_query()
        final_margin = final_info.Power
        print(f"建造后电力状态: {final_info.Power}/{final_info.PowerProvided} (余量: {final_margin})")
        
        if final_margin >= 200:
            print("✅ 电力充足，可以启动AI决策系统")
        else:
            print("⚠️  电力仍然不足，但继续启动AI系统")
    else:
        print(f"✅ 电力充足: {info.Power}/{info.PowerProvided} (余量: {power_margin})")


def build_all_structures(api: GameAPI):
    """建造所有建筑（不生产战斗单位）"""
    print("\n" + "=" * 60)
    print("阶段1: 建造完整基地")
    print("=" * 60)
    
    # 步骤1: 基础电力和资源
    print("\n[步骤1] 基础电力和资源")
    build_structure(api, "电厂", "电厂", 2)
    check_and_build_power(api)
    
    build_structure(api, "矿场", "矿场", 1)  # 减少到1个
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
    
    # 步骤5: 补充资源建筑和电力
    print("\n[步骤5] 补充资源设施和电力")
    build_structure(api, "矿场", "矿场", 1)  # 再建1个矿场，总共2个
    check_and_build_power(api)
    
    build_structure(api, "核电站", "核电站", 3)  # 增加到3个核电站
    check_and_build_power(api)
    
    # 步骤6: 防御建筑
    # print("\n[步骤6] 防御设施")
    # build_structure(api, "火焰塔", "火焰塔", 2)
    # check_and_build_power(api)
    
    # build_structure(api, "特斯拉线圈", "特斯拉线圈", 2)
    # check_and_build_power(api)
    
    # build_structure(api, "防空导弹", "防空导弹", 2)
    # check_and_build_power(api)
    
    print("\n" + "=" * 60)
    print("基地建设完成！现在交给 AI 指挥官接管")
    print("=" * 60)

def record_initial_harvesters(api: GameAPI):
    """记录基地阶段自动生成的两个采矿车"""
    units = api.query_actor(TargetsQueryParam(faction='自己')) or []
    for u in units:
        if getattr(u, "type", "") == "采矿车":
            INITIAL_HARVESTER_IDS.add(u.actor_id)

    print(f"[采矿车识别] 初始采矿车ID: {INITIAL_HARVESTER_IDS}")

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

def attack_move_all_combat_units(api: GameAPI):
    units = api.query_actor(TargetsQueryParam(faction='自己')) or []
    targets = []

    for u in units:
        if u.type in NON_COMBAT_TYPES:
            continue
        if u.type == "采矿车" and u.actor_id in INITIAL_HARVESTER_IDS:
            continue
        targets.append(u.actor_id)

    if targets:
        api.move_units_by_location_and_id(
            targets,
            location={"x":90, "y": 10},
            attack_move=True
        )
        print(f"[统一指令] {len(targets)} 个单位 attack_move 至 (90, 10)")

def continuous_attack_enemies(api: GameAPI):
    """持续攻击敌人 - 红方版本"""
    try:
        # 获取红方战斗单位
        my_units = api.query_actor(TargetsQueryParam(faction='自己')) or []
        combat_units = []
        
        for unit in my_units:
            unit_type = getattr(unit, 'type', '')
            if unit_type in NON_COMBAT_TYPES:
                continue
            if unit_type == "采矿车" and unit.actor_id in INITIAL_HARVESTER_IDS:
                continue
            combat_units.append(unit)
        
        if not combat_units:
            return
        
        # 获取敌方单位
        enemies = api.query_actor(TargetsQueryParam(faction='敌人')) or []
        if not enemies:
            return
        
        print(f"[持续攻击] 红方战斗单位: {len(combat_units)}, 敌方单位: {len(enemies)}")
        
        # 智能目标分配
        attack_success_count = 0
        attack_fail_count = 0
        
        for i, attacker in enumerate(combat_units):
            target = enemies[i % len(enemies)]  # 循环分配目标
            
            success = safe_attack_target(api, attacker, target)
            if success:
                attack_success_count += 1
                print(f"  ✓ {attacker.type}({attacker.actor_id}) → {target.type}({target.actor_id})")
            else:
                attack_fail_count += 1
                print(f"  ✗ {attacker.type}({attacker.actor_id}) → {target.type}({target.actor_id})")
        
        print(f"[攻击结果] 成功: {attack_success_count}, 失败: {attack_fail_count}")
        
    except Exception as e:
        print(f"[持续攻击异常] {e}")

# ===== 动作执行器 (从 fight.py 简化) =====
def build_red_combo_units(api, red_combo):
    """
    根据 red_combo = {"A":x, "B":x, ...} 自动生产红方坦克。
    使用中文名称生产。
    自动检查预算、build time、UNIT_DEFS 中的定义。
    """

    global production_stats

    if not red_combo:
        print("⚠️ red_combo 为空，跳过生产阶段")
        return

    print("\n" + "="*60)
    print("🔴 开始生产红方坦克组合")
    print("="*60)

    for letter, count in red_combo.items():
        if count <= 0:
            continue

        letter = str(letter).upper()

        if letter not in UNIT_DEFS:
            print(f"❌ 无法识别单位类型：{letter}（只能是 A~E）")
            continue

        unit_def = UNIT_DEFS[letter]
        unit_name = unit_def["name"]          # 中文
        cost = unit_def["cost"]
        build_time = unit_def["build_time"]

        # 预算检查
        remaining_budget = BUDGET_LIMIT - production_stats["total_cost"]
        if remaining_budget <= 0:
            print("❌ 已达到预算上限，停止生产")
            return

        max_affordable = remaining_budget // cost
        real_count = min(count, max_affordable)

        if real_count < count:
            print(f"⚠️ 预算不足：想造 {count} 个 {unit_name}，实际只能造 {real_count}")

        if real_count <= 0:
            continue

        print(f"\n[生产] {letter}({unit_name}) × {real_count} | cost={cost}, build_time={build_time}s")

        for i in range(real_count):
            print(f" → 生产 {unit_name} ({i+1}/{real_count}) ...")
            api.produce(unit_name, 1, False)

            # 更新统计
            production_stats["total_cost"] += cost
            production_stats["units_produced"][letter] = \
                production_stats["units_produced"].get(letter, 0) + 1

            time.sleep(build_time)

    print("\n🔴 红方组合生产完毕！")


# ===== AI 决策循环 =====
class AICommander:
    def __init__(self, api: GameAPI, agent: StreamingAgent, max_cycles: int = 300):
        self.api = api
        self.agent = agent
        self.max_cycles = max_cycles
        self.red_defeat_reported = False
        self.red_defeated = False  # 添加战败标志
        self.status_check_interval = 3
        self._last_status_query_cycle = -self.status_check_interval
        self.pending_defeat_reason = None
        
        # 初始化日志文件（与脚本同级目录）
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.log_dir = os.path.join(script_dir, "llm_logs")
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_filename = os.path.join(self.log_dir, f"game_log_{timestamp}.json")
        self.battle_start_time = datetime.now()
        self.log_data = {
            "side": "red",
            "start_time": self.battle_start_time.isoformat(),
            "timestamp": timestamp,
            "cycles": [],
            "initialization_errors": [],
            "final_battle_record": {}
        }
        print(f"[LOG] 日志文件已初始化: {self.log_filename}")
      
    def _calculate_final_stats(self):
        """计算终局统计数据（只使用中文名称 + 字母A-E，完全排除code）"""
        try:
            # ==========================================================
            # 1. 获取红方“战斗单位”（排除建筑 + 初始2个采矿车）
            # ==========================================================
            mine = self.api.query_actor(TargetsQueryParam(faction='自己')) or []
            red_combat_units = []

            for u in mine:
                utype = getattr(u, "type", "")

                # 跳过建筑
                if utype in NON_COMBAT_TYPES:
                    continue

                # 跳过初始采矿车（LLM永远不能看到/使用）
                if utype == "采矿车" and u.actor_id in INITIAL_HARVESTER_IDS:
                    continue

                red_combat_units.append(u)

            # ==========================================================
            # 2. 获取蓝方战斗单位（排除建筑 + 所有采矿车）
            # ==========================================================
            enemies = self.api.query_actor(TargetsQueryParam(faction='敌人')) or []
            blue_combat_units = []

            for e in enemies:
                etype = getattr(e, "type", "")

                if etype in NON_COMBAT_TYPES:
                    continue
                if etype == "采矿车":
                    continue

                blue_combat_units.append(e)

            # ==========================================================
            # 3. AI 生产数量（A-E字母）
            # ==========================================================
            army_distribution = production_stats.get("units_produced", {}).copy()
            for letter in ["A", "B", "C", "D", "E"]:
                army_distribution.setdefault(letter, 0)

            # ==========================================================
            # 4. 幸存单位详情（使用字母映射A-E）
            # ==========================================================
            unit_type_details = {}
            unit_counts = {}  # 中间统计，按API返回的类型

            # 首先按API类型进行统计
            for u in red_combat_units:
                utype = getattr(u, "type", "")
                
                # 不是坦克（如步兵/直升机），不统计
                # 这里只统计在UNIT_DEFS中定义的单位类型
                config_name = API_TYPE_TO_CONFIG_NAME.get(utype, utype)
                if config_name not in NAME_TO_LETTER:
                    continue
                    
                if utype not in unit_counts:
                    unit_counts[utype] = 0
                unit_counts[utype] += 1
            
            # 将API类型转换为字母格式
            for api_type, count in unit_counts.items():
                # 将游戏API类型转换为配置名称，再转换为字母
                config_name = API_TYPE_TO_CONFIG_NAME.get(api_type, api_type)
                letter = CONFIG_NAME_TO_LETTER.get(config_name)
                if letter:
                    unit_type_details[letter] = unit_type_details.get(letter, 0) + count
                else:
                    print(f"[警告] 未知单位类型映射: {api_type} -> {config_name}")
            
            print(f"[统计] API类型计数: {unit_counts}")
            print(f"[统计] 最终单位详情(字母): {unit_type_details}")

            # ==========================================================
            # 5. 计算红方幸存AI单位数量（使用unit_type_details的总数）
            # ==========================================================
            # 使用unit_type_details的总数作为准确的存活单位数量
            red_surviving_ai_units = sum(unit_type_details.values())
            print(f"[统计] 红方存活AI单位数量: {red_surviving_ai_units} (基于unit_type_details总数)")

            # ==========================================================
            # 6. 蓝方兵种是否单一
            # ==========================================================
            blue_type_counter = {}
            for e in blue_combat_units:
                etype = getattr(e, "type", "")
                blue_type_counter[etype] = blue_type_counter.get(etype, 0) + 1

            blue_single_type = list(blue_type_counter.keys())[0] if len(blue_type_counter) == 1 else None

            # ==========================================================
            # 7. 胜负判断（优先使用Socket信号，类似蓝方逻辑）
            # ==========================================================
            global game_end_requested, blue_battle_stats
            
            print(f"[胜负判定] 调试信息:")
            print(f"  game_end_requested: {game_end_requested}")
            print(f"  blue_battle_stats存在: {bool(blue_battle_stats)}")
            print(f"  红方剩余AI单位: {red_surviving_ai_units}")
            print(f"  蓝方剩余战斗单位: {len(blue_combat_units)}")
            
            # 首先检查是否收到蓝方战损统计中的胜负结果
            if game_end_requested and blue_battle_stats:
                blue_result = blue_battle_stats.get('result', 'unknown')
                if blue_result == 'win':
                    result = "loss"  # 蓝方胜利意味着红方失败
                    print(f"[胜负判定] *** 基于蓝方战损统计: 蓝方胜利，红方失败 ***")
                elif blue_result == 'loss':
                    result = "win"   # 蓝方失败意味着红方胜利
                    print(f"[胜负判定] *** 基于蓝方战损统计: 蓝方失败，红方胜利 ***")
                elif blue_result == 'draw':
                    result = "draw"  # 平局
                    print(f"[胜负判定] *** 基于蓝方战损统计: 平局 ***")
                else:
                    # 如果蓝方结果未知，回退到基于单位数量判定
                    print(f"[胜负判定] 蓝方结果未知({blue_result})，回退到单位数量判定")
                    result = None  # 标记需要继续判定
            else:
                result = None  # 标记需要继续判定
            
            # 如果没有Socket信号或需要回退判定，基于自身单位数量判定
            if result is None:
                if red_surviving_ai_units == 0:
                    result = "loss"
                    print(f"[胜负判定] 基于自身单位: 红方全部阵亡，红方失败")
                else:
                    result = "ongoing"
                    print(f"[胜负判定] 基于自身单位: 红方仍有{red_surviving_ai_units}个单位，战斗继续")

            # ==========================================================
            # 8. 战斗时长
            # ==========================================================
            battle_end_time = datetime.now()
            battle_duration = (battle_end_time - self.battle_start_time).total_seconds()

            # ==========================================================
            # 9. 红方战损比
            # ==========================================================
            total_produced = sum(army_distribution.values())
            red_lost = total_produced - red_surviving_ai_units
            red_damage_ratio = round(red_lost / total_produced, 4) if total_produced > 0 else 0.0

            # ==========================================================
            # 10. 蓝方作战单位数量
            # ==========================================================
            blue_surviving = len(blue_combat_units)

            # ==========================================================
            # 11. 生成最终战斗记录
            # ==========================================================
            final_record = {
                "battle_id": f"red_{self.log_data['timestamp']}",
                "army_distribution": army_distribution,   # A–E 生产数量
                "unit_type_details": unit_type_details,   # 中文名称幸存数量
                "total_cost": production_stats.get("total_cost", 0),
                "result": result,
                "battle_duration_seconds": int(battle_duration),
                "damage_sustained_ratio": red_damage_ratio,
                "red_combat_units": red_surviving_ai_units,
                "blue_combat_units": blue_surviving,
                "blue_single_type": blue_single_type,
                "total_produced": total_produced,
                "red_lost": red_lost
            }


            return final_record

        except Exception as e:
            print(f"[统计] 计算终局数据时出错: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _save_log(self):
        """保存日志文件和红蓝双方战损统计"""
        self.log_data["end_time"] = datetime.now().isoformat()
        self.log_data["total_cycles"] = len(self.log_data["cycles"])
        
        # 计算终局统计
        final_stats = self._calculate_final_stats()
        self.log_data["final_battle_record"] = final_stats
        
        # 打印终局报告
        if final_stats:
            print("\n" + "="*60)
            print("红方终局记录")
            print("="*60)
            print(f"战斗结果: {final_stats.get('result', 'unknown')}")
            
            # 显示作战单位生产统计（按字母代码）
            print(f"作战单位生产统计(字母): {final_stats.get('army_distribution', {})}")
            
            # 显示幸存单位详情（AI生产的战斗单位）
            unit_details = final_stats.get('unit_type_details', {})
            if unit_details:
                print(f"幸存战斗单位详情(字母):")
                for letter, count in unit_details.items():
                    unit_name = UNIT_DEFS.get(letter, {}).get('name', letter)
                    print(f"  - {letter}({unit_name}): {count} 辆")
            else:
                print(f"幸存战斗单位详情: 无（全部阵亡）")
            print(f"总生产数量: {final_stats.get('total_produced', 0)} 辆")
            print(f"损失数量: {final_stats.get('red_lost', 0)} 辆")
            print(f"红方战损比: {final_stats.get('damage_sustained_ratio', 0):.2%}")
            print(f"战斗时长: {final_stats.get('battle_duration_seconds', 0)} 秒")
            print(f"总成本: ${final_stats.get('total_cost', 0)}")
            print("="*60)
        
        try:
            with open(self.log_filename, 'w', encoding='utf-8') as f:
                json.dump(self.log_data, f, ensure_ascii=False, indent=2)
            print(f"\n[LOG] 完整游戏日志已保存到: {self.log_filename}")
            print(f"[LOG] 共记录 {self.log_data['total_cycles']} 个回合")
        except Exception as e:
            print(f"\n[LOG] 日志保存失败: {e}")
            return None
    
    # 公共方法接口，供主程序调用
    def calculate_final_stats(self):
        """公共方法：计算最终战损统计"""
        return self._calculate_final_stats()
    
    def save_combat_log(self):
        """公共方法：保存战损日志"""
        return self._save_log()
    
    def print_combat_summary(self):
        """公共方法：打印战损统计摘要"""
        final_stats = self._calculate_final_stats()
        if final_stats:
            print("\n" + "="*60)
            print("红方终局记录")
            print("="*60)
            print(f"战斗结果: {final_stats.get('result', 'unknown')}")
            print(f"作战单位生产统计(字母): {final_stats.get('army_distribution', {})}")
            
            unit_details = final_stats.get('unit_type_details', {})
            if unit_details:
                print(f"幸存战斗单位详情(字母):")
                for letter, count in unit_details.items():
                    unit_name = UNIT_DEFS.get(letter, {}).get('name', letter)
                    print(f"  - {letter}({unit_name}): {count} 辆")
            else:
                print(f"幸存战斗单位详情: 无（全部阵亡）")
                
            print(f"总生产数量: {final_stats.get('total_produced', 0)} 辆")
            print(f"损失数量: {final_stats.get('red_lost', 0)} 辆")
            print(f"红方战损比: {final_stats.get('damage_sustained_ratio', 0):.2%}")
            print(f"战斗时长: {final_stats.get('battle_duration_seconds', 0)} 秒")
            print(f"总成本: ${final_stats.get('total_cost', 0)}")
            if final_stats.get('red_single_type'):
                print(f"红方单一兵种(字母): {final_stats.get('red_single_type')}")
            print("="*60)
        else:
            print("\n⚠️  无战损统计数据")
    
    def stop(self):
        """公共方法：停止AI指挥官"""
        global game_end_requested
        game_end_requested = True
        print(f"\n[AI指挥官] 停止信号已发送")
        
        # 保存红蓝双方战损统计到固定日志文件
        global blue_battle_stats
        
        # 计算红方最终统计
        final_stats = self._calculate_final_stats()
        
        # 如果红方战败，需要等待蓝方发送战损统计
        print(f"\n[调试] 检查是否需要等待蓝方战损统计...")
        print(f"[调试] final_stats存在: {bool(final_stats)}")
        if final_stats:
            print(f"[调试] final_stats['result']: {final_stats.get('result', 'None')}")
        print(f"[调试] blue_battle_stats存在: {bool(blue_battle_stats)}")
        print(f"[调试] red_defeated标志: {self.red_defeated}")
        
        # 使用战败标志而不是依赖final_stats计算结果
        if self.red_defeated and not blue_battle_stats:
            print(f"\n[等待蓝方] 红方已战败，等待蓝方发送战损统计...")
            print(f"[等待蓝方] 最多等待60秒...")
            
            wait_time = 0
            max_wait = 60  # 增加到60秒等待时间
            while wait_time < max_wait and not blue_battle_stats:
                time.sleep(1)
                wait_time += 1
                if wait_time % 10 == 0:  # 每10秒显示一次进度
                    print(f"[等待蓝方] 已等待{wait_time}秒，还需等待{max_wait - wait_time}秒...")
            
            if blue_battle_stats:
                print(f"[等待蓝方] ✓ 已收到蓝方战损统计")
                print(f"[等待蓝方] 蓝方数据: 生产{blue_battle_stats.get('total_produced', 0)}辆，损失{blue_battle_stats.get('loss_count', 0)}辆")
            else:
                print(f"[等待蓝方] ✗ 等待超时，未收到蓝方战损统计")
                print(f"[等待蓝方] 将只保存红方数据")
        
        save_combined_battle_log(
            final_stats,
            blue_battle_stats,
            battle_start=self.battle_start_time
        )
    
    def _notify_blue_of_defeat(self, reason: str):
        """尝试通过Socket告知蓝方红方已失败"""
        self.pending_defeat_reason = reason
        if self.red_defeat_reported:
            return
        response = report_game_over_to_blue('red', 'defeated', reason)
        if response.get('status') == 'success':
            self.red_defeat_reported = True
            print("[Socket客户端] 蓝方已确认红方失败信号")
        else:
            print("[Socket客户端] 蓝方未确认失败信号，将在结束时重试")
    
    def _should_stop_for_blue_signal(self, cycle: int) -> bool:
        """周期性查询蓝方状态，若蓝方已结束则同步退出"""
        if cycle - self._last_status_query_cycle < self.status_check_interval:
            return False
        status = query_blue_agent_status()
        self._last_status_query_cycle = cycle
        if status.get('status') != 'success':
            print(f"[Socket客户端] 查询蓝方状态失败: {status.get('message')}")
            return False
        game_state = status.get('game_state') or {}
        blue_status = game_state.get('blue_status', 'ongoing')
        blue_reason = game_state.get('blue_reason', '')
        red_status = game_state.get('red_status')
        if red_status == 'defeated':
            self.red_defeat_reported = True
        if blue_status in {'defeated', 'victory'}:
            print("\n" + "=" * 60)
            print("蓝方状态同步")
            print("=" * 60)
            print(f"蓝方状态: {blue_status}")
            if blue_reason:
                print(f"原因: {blue_reason}")
            print("蓝方已结束战斗，红方同步退出。")
            print("=" * 60)
            return True
        return False
    
    def run(self):
        """
        单轮 AI 指挥模式：
        1. 调用一次 LLM，选择一种坦克 + 数量
        2. 一次性生产
        3. 统一 attack_move 到 (90, 10)
        4. 阻塞等待游戏结束信号
        5. 结算并保存日志
        """
        global game_end_requested, blue_battle_stats  # 添加blue_battle_stats引用

        print("\n" + "=" * 60)
        print("红方开始统一进攻）")
        print("=" * 60)

        try:
            # ==================================================
            # 1. 统一进攻指令
            # ==================================================
            time.sleep(3)

            print("\n[作战指令] 全体单位 attack_move → (90, 10)")
            attack_move_all_combat_units(self.api)

            # ==================================================
            # 2. 阻塞等待游戏结束（自身战败检测 + 蓝方信号）
            # ==================================================
            print("\n[等待] 等待游戏结束信号（来自蓝方或自身战败检测）")

            check_interval = 3  # 每3秒检测一次
            attack_interval = 5  # 每5秒进行持续攻击
            last_check = 0
            last_attack = 0
            
            while not game_end_requested:
                time.sleep(1)
                last_check += 1
                last_attack += 1
                
                # 周期性持续攻击
                if last_attack >= attack_interval:
                    print("\n[持续攻击] 红方执行持续攻击...")
                    continuous_attack_enemies(self.api)
                    last_attack = 0
                
                # 周期性检测红方是否战败
                if last_check >= check_interval:
                    try:
                        mine = self.api.query_actor(TargetsQueryParam(faction='自己')) or []
                        red_combat_units = []

                        for u in mine:
                            utype = getattr(u, "type", "")
                            
                            # 跳过建筑
                            if utype in NON_COMBAT_TYPES:
                                continue
                            
                            # 跳过初始采矿车
                            if utype == "采矿车" and u.actor_id in INITIAL_HARVESTER_IDS:
                                continue
                            
                            red_combat_units.append(u)
                        
                        print(f"[自检] 红方剩余战斗单位: {len(red_combat_units)}")
                        
                        # 如果红方战斗单位全部阵亡
                        if len(red_combat_units) == 0:
                            print("\n" + "=" * 60)
                            print("红方战败检测")
                            print("=" * 60)
                            print("✗ 红方所有战斗单位已阵亡")
                            print("✗ 红方战败")
                            print("=" * 60)
                            
                            # 设置战败标志
                            self.red_defeated = True
                            
                            # 尝试通知蓝方红方已失败
                            self._notify_blue_of_defeat("所有战斗单位阵亡")
                            
                            # 等待蓝方发送战损统计（给蓝方一些时间来响应）
                            print(f"\n[等待蓝方] 红方已失败，等待蓝方发送战损统计...")
                            wait_time = 0
                            max_wait = 30  # 等待30秒
                            while wait_time < max_wait and not blue_battle_stats:
                                time.sleep(1)
                                wait_time += 1
                                if wait_time % 5 == 0:  # 每5秒显示一次进度
                                    print(f"[等待蓝方] 已等待{wait_time}秒，还需等待{max_wait - wait_time}秒...")
                            
                            # 无论是否收到蓝方数据，都设置游戏结束标志
                            game_end_requested = True
                            break
                            
                        last_check = 0  # 重置计数器
                        
                    except Exception as e:
                        print(f"[自检] 检测红方单位时出错: {e}")
                        last_check = 0

            print("\n✅ 游戏结束信号已接收")

        except Exception as e:
            print(f"\n❌ AI 指挥官运行失败: {e}")
            import traceback
            traceback.print_exc()

        finally:
            print("\n[收尾] 计算终局战损与日志")

            final_stats = self._calculate_final_stats()
            self.log_data["final_battle_record"] = final_stats
            self._save_log()

            print("\n" + "=" * 60)
            print("AI 指挥官运行结束（单轮模式）")
            print("=" * 60)

# ===== 主程序 =====
def main():
    print("=" * 60)
    print("红方控制程序 + Socket 通信")
    print("自动红蓝组合生成（模拟退火 + LLM）")
    print("通信: Socket 控制 blue_agent.py / red_agent.py 生产坦克")
    print("目标: 自动化组合实验，持续优化最强组合")
    print("=" * 60)

    # ======================================================
    # 初始化：启动战损统计服务器
    # ======================================================
    print("\n[初始化] 启动战损统计服务器...")
    start_battle_stats_server()
    time.sleep(1)

    # ======================================================
    # 连接 blue_agent.py
    # ======================================================
    print("\n[连接检查] 尝试连接 blue_agent.py ...")
    blue_status = query_blue_agent_status()
    if blue_status.get("status") != "success":
        print(f"❌ 无法连接 blue_agent.py: {blue_status.get('message')}")
        if input("是否继续运行? (y/n): ").lower() != "y":
            return
    else:
        print(f"✓ blue_agent 连接成功，支持坦克: {blue_status.get('available_tanks')}")


    # ======================================================
    # 调用 LLM → 获取红蓝组合
    # ======================================================
    history = load_history_games()

    print("\n🤖 调用 LLM（模拟退火）生成红蓝组合...")
    llm_result = call_sa_llm(history)

    red_combo = llm_result["red_combo"]
    blue_combo = llm_result["blue_combo"]

    print("\n🔴 红方组合：", red_combo)
    print("🔵 蓝方组合：", blue_combo)
    print(f"🤖 confidence: {llm_result.get('confidence')}")
    print(f"🤖 说明: {llm_result.get('reason')}")

    # ======================================================
    # 将组合发送给蓝方 agent
    # ======================================================

    print("\n[发送组合给 blue_agent] ...")
    resp_blue = send_blue_agent_combo(blue_combo)
    print("➡ blue_agent 响应：", resp_blue)

    # ======================================================
    # 红方基地建造（完全沿用旧逻辑）
    # ======================================================
    print("\n" + "=" * 60)
    print("阶段：建造红方基地")
    print("=" * 60)

    api = GameAPI(host="localhost", port=7445, language="zh")

    print("\n[初始化] 部署建造厂...")
    try:
        api.deploy_mcv_and_wait(5)
        print("✓ 建造厂就绪")
    except Exception as e:
        print(f"⚠️ 部署建造厂异常: {e}")

    time.sleep(3)

    build_all_structures(api)
    record_initial_harvesters(api)

    print("\n等待关键建筑完成...")
    max_wait_time = 120
    wait_interval = 5
    elapsed = 0

    while elapsed < max_wait_time:
        my_buildings = api.query_actor(TargetsQueryParam(faction='自己'))

        war_factory = sum(1 for b in my_buildings if b.type == '战车工厂')
        tech_center = sum(1 for b in my_buildings if b.type == '科技中心')
        airfield = sum(1 for b in my_buildings if b.type in {"机场", "空军基地", "afld", "afld.td"})

        print(f"[{elapsed}s] 战车工厂:{war_factory}/2 | 科技中心:{tech_center}/1 | 机场:{airfield}/1")

        if war_factory >= 2 and tech_center >= 1 and airfield >= 1:
            print("✓ 关键建筑完成")
            break

        time.sleep(wait_interval)
        elapsed += wait_interval

    if elapsed >= max_wait_time:
        print("⚠️ 等待超时，继续运行")

    print("\n等待其他建筑完成中...")
    time.sleep(20)

    print("\n检查电力状况...")
    check_and_build_power(api)

    # ======================================================
    # 启动红方 AI 指挥官
    # ======================================================
    print("\n" + "=" * 60)
    print("阶段：AI 指挥官接管 (红方)")
    print("=" * 60)

    build_red_combo_units(api, red_combo)
    commander_agent = StreamingAgent(role="你是红方决策AI", model="gemini_2_5_flash")
    commander = AICommander(api, commander_agent, max_cycles=300)

    print("\n[AI指挥官] 开始执行主循环...")
    try:
        commander.run()
    except KeyboardInterrupt:
        print("\n[AI指挥官] 用户中断")
    except Exception as e:
        print(f"\n[AI指挥官] 运行异常: {e}")

    # ======================================================
    # 战斗结束 → 保存战损 + 历史记录
    # ======================================================
    print("\n" + "=" * 60)
    print("战斗结束，收集统计信息")
    print("=" * 60)

    if game_end_requested and blue_battle_stats:
        print(f"✓ 已接收蓝方战损统计")
        print(f"✓ 正在计算红方战损统计...")
        
        try:
            # 计算红方最终战损统计
            red_final_stats = commander.calculate_final_stats()
            
            # 保存红方战损日志
            log_filename = commander.save_combat_log()
            
            # 打印红方战损统计
            commander.print_combat_summary()
            
            print(f"\n✓ 红方战损统计已计算完成")
            if log_filename:
                print(f"✓ 红方战损日志已保存到: {log_filename}")
            
            # 保存组合战损日志（红蓝双方）
            if blue_battle_stats and red_final_stats:
                combined_filename = save_combined_battle_log(red_final_stats, blue_battle_stats)
                if combined_filename:
                    print(f"✓ 组合战损日志已保存到: {combined_filename}")
            
        except Exception as e:
            print(f"✗ 计算红方战损统计时出错: {e}")
            import traceback
            traceback.print_exc()

    
    print("✓ 历史记录已更新")
    print("=" * 60)
    print("红方程序结束")
    print("=" * 60)

if __name__ == "__main__":
    main()

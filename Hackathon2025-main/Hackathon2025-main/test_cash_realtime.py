#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试资金是否实时更新
持续监控资金变化，验证API是否返回实时数据
"""

import sys
import time
import os

# 添加库路径
current_dir = os.path.dirname(os.path.abspath(__file__))
library_path = os.path.join(current_dir, 'examples', 'mcp')
sys.path.insert(0, library_path)

from OpenRA_Copilot_Library.game_api import GameAPI
from OpenRA_Copilot_Library.models import TargetsQueryParam

def print_header():
    """打印头部"""
    print("=" * 80)
    print(" " * 25 + "资金实时监控测试程序")
    print("=" * 80)
    print("\n功能说明:")
    print("  • 每2秒查询一次资金")
    print("  • 显示资金变化趋势")
    print("  • 验证API是否返回实时数据")
    print("\n测试方法:")
    print("  1. 运行程序后观察初始资金")
    print("  2. 在游戏中进行操作（生产单位、建造建筑）")
    print("  3. 观察程序是否显示资金变化")
    print("  4. 或者等待采矿车采矿，观察资金增长")
    print("\n按 Ctrl+C 停止监控")
    print("=" * 80)
    print()

def main():
    """主函数"""
    print_header()
    
    # 连接API
    try:
        api = GameAPI('localhost', 7445, 'zh')
        print("✓ 已连接到游戏服务器\n")
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        input("\n按回车退出...")
        return
    
    print("=" * 80)
    print("开始监控资金变化...")
    print("=" * 80)
    print()
    
    # 记录历史数据
    cash_history = []
    count = 0
    last_cash = None
    
    try:
        while True:
            count += 1
            
            # 查询基地信息
            try:
                info = api.player_base_info_query()
                current_cash = info.Cash
                current_power = info.Power
                current_resources = info.Resources
                
                # 计算变化
                change = ""
                if last_cash is not None:
                    diff = current_cash - last_cash
                    if diff > 0:
                        change = f"(+${diff}) ⬆"
                    elif diff < 0:
                        change = f"(-${abs(diff)}) ⬇"
                    else:
                        change = "(不变) ➡"
                
                # 显示当前状态
                timestamp = time.strftime("%H:%M:%S")
                print(f"[{timestamp}] 第{count}次查询:")
                print(f"  💰 资金: ${current_cash:,} {change}")
                print(f"  ⚡ 电力: {current_power} / {info.PowerProvided}")
                print(f"  💎 资源: {current_resources}")
                
                # 记录历史
                cash_history.append(current_cash)
                last_cash = current_cash
                
                # 统计信息
                if len(cash_history) > 1:
                    min_cash = min(cash_history)
                    max_cash = max(cash_history)
                    avg_cash = sum(cash_history) // len(cash_history)
                    
                    print(f"\n  📊 统计信息:")
                    print(f"     最低: ${min_cash:,}")
                    print(f"     最高: ${max_cash:,}")
                    print(f"     平均: ${avg_cash:,}")
                    print(f"     波动: ${max_cash - min_cash:,}")
                
                # 查询单位信息（可选）
                if count % 5 == 0:  # 每5次查询显示单位统计
                    all_units = api.query_actor(TargetsQueryParam(faction='自己'))
                    harvesters = [u for u in all_units if u.type in ['采矿车', 'harv']]
                    print(f"\n  🚜 采矿车数量: {len(harvesters)}")
                
                print("-" * 80)
                
            except Exception as e:
                print(f"\n[错误] 查询失败: {e}")
                print("-" * 80)
            
            # 等待2秒
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print(" " * 25 + "监控已停止")
        print("=" * 80)
        
        # 最终统计
        if cash_history:
            print(f"\n最终统计:")
            print(f"  总查询次数: {count}")
            print(f"  监控时长: {count * 2} 秒")
            print(f"  初始资金: ${cash_history[0]:,}")
            print(f"  最终资金: ${cash_history[-1]:,}")
            print(f"  总变化: ${cash_history[-1] - cash_history[0]:,}")
            
            if cash_history[-1] != cash_history[0]:
                print(f"\n✓ 资金有变化 - API返回的是实时数据！")
            else:
                print(f"\n⚠ 资金没有变化")
                print(f"  可能原因:")
                print(f"    1. 游戏已暂停或未开始")
                print(f"    2. 没有采矿车在采矿")
                print(f"    3. 没有进行任何生产/建造")
                print(f"    4. 收入和支出刚好平衡")
            
            # 显示变化历史
            if len(cash_history) > 1:
                print(f"\n资金变化历史:")
                for i, cash in enumerate(cash_history, 1):
                    if i == 1:
                        print(f"  {i}. ${cash:,} (初始)")
                    else:
                        diff = cash - cash_history[i-2]
                        arrow = "⬆" if diff > 0 else "⬇" if diff < 0 else "➡"
                        print(f"  {i}. ${cash:,} ({diff:+,}) {arrow}")
                    
                    if i >= 10:  # 只显示前10条
                        if len(cash_history) > 10:
                            print(f"  ... (共{len(cash_history)}条记录)")
                        break
        
        print("\n感谢使用！")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[严重错误] {e}")
        import traceback
        traceback.print_exc()
        input("\n按回车退出...")

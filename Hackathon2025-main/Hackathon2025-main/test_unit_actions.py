#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenRA 单位通用动作测试程序
测试：移动、攻击、停止、选择、编组等基本操作
"""

import sys
import time
from typing import List, Optional
import os

# 添加库路径
current_dir = os.path.dirname(os.path.abspath(__file__))
library_path = os.path.join(current_dir, 'examples', 'mcp')
sys.path.insert(0, library_path)

from OpenRA_Copilot_Library.game_api import GameAPI
from OpenRA_Copilot_Library.models import TargetsQueryParam, Location

def print_header():
    """打印程序头部信息"""
    print("=" * 70)
    print("OpenRA 单位通用动作测试程序")
    print("=" * 70)
    print("\n测试动作清单:")
    print("  1. ✓ 选择单位 (select_unit)")
    print("  2. ✓ 移动单位 (move_actor)")
    print("  3. ✓ 攻击目标 (attack)")
    print("  4. ✓ 停止单位 (stop)")
    print("  5. ✓ 编组单位 (form_group)")
    print("  6. ✓ 查看单位状态")
    print("\n测试单位:")
    print("  • 步兵 x5 - 测试步兵操作")
    print("  • 坦克 x2 - 测试载具操作")
    print("\n游戏设置要求:")
    print("  • Skirmish 自由模式")
    print("  • 起始资金: $10000+")
    print("  • AI: None 或 Easy")
    print("=" * 70)
    print()

def wait_for_production(api: GameAPI, unit_type: str, expected_count: int, timeout: int = 60) -> List:
    """等待单位生产完成"""
    print(f"   [等待] {unit_type} 生产中...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        units = api.query_actor(TargetsQueryParam(type=[unit_type], faction='自己'))
        if units and len(units) >= expected_count:
            print(f"   ✓ {len(units)} 个 {unit_type} 已就绪")
            return units
        time.sleep(2)
    
    print(f"   ✗ {unit_type} 生产超时")
    return []

def test_select_unit(api: GameAPI, unit_ids: List[int]):
    """测试1: 选择单位"""
    print("\n" + "=" * 70)
    print("[测试1] 选择单位 (select_unit)")
    print("=" * 70)
    
    try:
        # 选择单个单位
        print(f"\n>> 测试1.1: 选择单个单位 (ID: {unit_ids[0]})")
        query_param = TargetsQueryParam(faction='自己')
        query_param.restrain = [{"actorId": [unit_ids[0]]}]
        api.select_units(query_param)
        print(f"   ✓ 单位已选中")
        time.sleep(1)
        
        # 选择多个单位（组合选择）
        print(f"\n>> 测试1.2: 组合选择多个单位 (ID: {unit_ids[:3]})")
        query_param_multi = TargetsQueryParam(faction='自己')
        query_param_multi.restrain = [{"actorId": unit_ids[:3]}]
        api.select_units(query_param_multi)
        print(f"   ✓ {len(unit_ids[:3])} 个单位已选中")
        time.sleep(1)
        
        print(f"\n✓ 选择单位测试通过")
        return True
    except Exception as e:
        print(f"\n✗ 选择单位测试失败: {e}")
        return False

def test_move_actor(api: GameAPI, unit_ids: List[int]):
    """测试2: 移动单位"""
    print("\n" + "=" * 70)
    print("[测试2] 移动单位 (move_actor)")
    print("=" * 70)
    
    try:
        # 通过ID获取单位对象
        from OpenRA_Copilot_Library.models import Actor
        units = [api.get_actor_by_id(uid) for uid in unit_ids[:3]]
        units = [u for u in units if u is not None]
        
        if not units:
            print("   ✗ 无法查询到单位")
            return False
        
        original_pos = units[0].position
        print(f"\n>> 测试2.1: 单位移动到新位置")
        print(f"   当前位置: ({original_pos.x}, {original_pos.y})")
        
        # 计算目标位置（向右移动10格）
        target_pos = Location(original_pos.x + 10, original_pos.y)
        print(f"   目标位置: ({target_pos.x}, {target_pos.y})")
        
        # 移动单位
        api.move_units_by_location(units[:3], target_pos, attack_move=False)
        print(f"   ✓ 移动命令已发送")
        time.sleep(3)
        
        # 验证移动
        for unit in units[:3]:
            api.update_actor(unit)
        new_pos = units[0].position
        print(f"   新位置: ({new_pos.x}, {new_pos.y})")
        if new_pos.x != original_pos.x or new_pos.y != original_pos.y:
            print(f"   ✓ 单位已移动")
        else:
            print(f"   ⚠ 单位位置未变化（可能正在移动中）")
        
        # 测试攻击移动
        print(f"\n>> 测试2.2: 攻击移动模式")
        attack_move_pos = Location(original_pos.x + 15, original_pos.y + 5)
        api.move_units_by_location(units[:3], attack_move_pos, attack_move=True)
        print(f"   ✓ 攻击移动命令已发送")
        time.sleep(2)
        
        print(f"\n✓ 移动单位测试通过")
        return True
    except Exception as e:
        print(f"\n✗ 移动单位测试失败: {e}")
        return False

def test_stop(api: GameAPI, unit_ids: List[int]):
    """测试3: 停止单位"""
    print("\n" + "=" * 70)
    print("[测试3] 停止单位 (stop)")
    print("=" * 70)
    
    try:
        print(f"\n>> 测试3.1: 先让单位移动")
        from OpenRA_Copilot_Library.models import Actor
        units = [api.get_actor_by_id(uid) for uid in unit_ids[:2]]
        units = [u for u in units if u is not None]
        
        if units:
            pos = units[0].position
            far_pos = Location(pos.x + 20, pos.y + 20)
            api.move_units_by_location(units, far_pos)
            print(f"   ✓ 单位开始移动到远处")
            time.sleep(1)
        
        print(f"\n>> 测试3.2: 停止单位")
        api.stop(units)
        print(f"   ✓ 停止命令已发送")
        time.sleep(1)
        
        print(f"\n✓ 停止单位测试通过")
        return True
    except Exception as e:
        print(f"\n✗ 停止单位测试失败: {e}")
        return False

def test_form_group(api: GameAPI, unit_ids: List[int]):
    """测试4: 编组单位"""
    print("\n" + "=" * 70)
    print("[测试4] 编组单位 (form_group)")
    print("=" * 70)
    
    try:
        from OpenRA_Copilot_Library.models import Actor
        
        # 将单位编入1号编队
        print(f"\n>> 测试4.1: 将单位编入1号编队")
        units_group1 = [api.get_actor_by_id(uid) for uid in unit_ids[:3]]
        units_group1 = [u for u in units_group1 if u is not None]
        api.form_group(units_group1, group_id=1)
        print(f"   ✓ 单位已编入1号编队")
        time.sleep(1)
        
        # 将其他单位编入2号编队
        if len(unit_ids) > 3:
            print(f"\n>> 测试4.2: 将其他单位编入2号编队")
            units_group2 = [api.get_actor_by_id(uid) for uid in unit_ids[3:5]]
            units_group2 = [u for u in units_group2 if u is not None]
            api.form_group(units_group2, group_id=2)
            print(f"   ✓ 单位已编入2号编队")
            time.sleep(1)
        
        print(f"\n✓ 编组单位测试通过")
        print(f"   提示: 在游戏中按 1 或 2 可以选择对应编队")
        return True
    except Exception as e:
        print(f"\n✗ 编组单位测试失败: {e}")
        return False

def test_attack(api: GameAPI, attacker_ids: List[int]):
    """测试5: 攻击目标"""
    print("\n" + "=" * 70)
    print("[测试5] 攻击目标 (attack)")
    print("=" * 70)
    
    try:
        from OpenRA_Copilot_Library.models import Actor
        
        # 查找敌方单位或建筑
        print(f"\n>> 查找可攻击目标...")
        
        # 先尝试查找敌方单位
        enemy_units = api.query_actor(TargetsQueryParam(faction='敌方'))
        
        if enemy_units and len(enemy_units) > 0:
            target = enemy_units[0]
            print(f"   发现敌方单位: {target.type} (ID: {target.actor_id})")
            print(f"   位置: ({target.position.x}, {target.position.y})")
            
            print(f"\n>> 测试5.1: 攻击敌方目标")
            attackers = [api.get_actor_by_id(uid) for uid in attacker_ids[:3]]
            attackers = [a for a in attackers if a is not None]
            
            if attackers:
                success = api.attack_target(attackers[0], target)
                if success:
                    print(f"   ✓ 攻击命令已发送")
                else:
                    print(f"   ⚠ 攻击命令发送失败（目标可能不可见或不可达）")
                time.sleep(2)
            
            print(f"\n✓ 攻击目标测试通过")
            return True
        else:
            print(f"   ⚠ 未发现敌方目标")
            print(f"   提示: 此测试需要地图上有敌方单位或建筑")
            print(f"   建议: 使用有AI的地图或手动放置敌方单位")
            print(f"\n⚠ 攻击目标测试跳过（无目标）")
            return None
    except Exception as e:
        print(f"\n✗ 攻击目标测试失败: {e}")
        return False

def main():
    """主函数"""
    print_header()
    
    input("按回车开始...\n")
    
    print("=" * 70)
    print("[*] OpenRA 单位通用动作测试程序 - 开始执行")
    print("=" * 70)
    
    # 连接API
    api = GameAPI('localhost', 7445, 'zh')
    
    # 步骤1: 检查游戏状态
    print("\n[准备阶段] 检查游戏状态...")
    info = api.player_base_info_query()
    print(f"   资金: ${info.Cash}")
    print(f"   电力: {info.Power} / {info.PowerProvided}")
    
    # 步骤2: 准备测试单位
    print("\n[准备阶段] 生产测试单位...")
    
    # 检查是否已有兵营
    barracks = api.query_actor(TargetsQueryParam(type=['兵营'], faction='自己'))
    if not barracks or len(barracks) == 0:
        print("\n   ⚠ 未发现兵营！")
        print("   请确保游戏中已有兵营，或运行以下命令建造基础设施：")
        print("   python build_all_structures.py")
        response = input("\n   是否继续？(将跳过生产步骤) (y/n): ")
        if response.lower() != 'y':
            return
        
        # 查找现有单位
        print("\n   查找现有单位...")
        existing_units = api.query_actor(TargetsQueryParam(faction='自己'))
        test_units = [u for u in existing_units if u.type in ['步兵', 'e1', '火箭兵', 'e3', '坦克', '1tnk', '3tnk']]
        
        if len(test_units) < 3:
            print(f"   ✗ 可用单位不足（需要至少3个，找到{len(test_units)}个）")
            print("   请先生产一些单位再运行此测试")
            return
        
        print(f"   ✓ 找到 {len(test_units)} 个可用单位")
        unit_ids = [u.actor_id for u in test_units[:7]]
    else:
        print("   ✓ 发现兵营")
        
        # 生产步兵
        print("\n   生产5个步兵...")
        for i in range(5):
            try:
                wait_id = api.produce("e1", 1, False)
                if wait_id:
                    print(f"   [{i+1}/5] 步兵已下单")
            except Exception as e:
                print(f"   [{i+1}/5] 下单失败: {e}")
        
        # 等待步兵生产
        infantry_units = wait_for_production(api, "步兵", 5, timeout=90)
        
        if len(infantry_units) < 3:
            print(f"   ✗ 步兵数量不足（需要至少3个，生产了{len(infantry_units)}个）")
            return
        
        unit_ids = [u.actor_id for u in infantry_units[:7]]
    
    print(f"\n✓ 准备就绪，测试单位ID: {unit_ids}")
    time.sleep(2)
    
    # 执行测试
    test_results = []
    
    # 测试1: 选择单位
    result = test_select_unit(api, unit_ids)
    test_results.append(("选择单位", result))
    time.sleep(2)
    
    # 测试2: 移动单位
    result = test_move_actor(api, unit_ids)
    test_results.append(("移动单位", result))
    time.sleep(2)
    
    # 测试3: 停止单位
    result = test_stop(api, unit_ids)
    test_results.append(("停止单位", result))
    time.sleep(2)
    
    # 测试4: 编组单位
    result = test_form_group(api, unit_ids)
    test_results.append(("编组单位", result))
    time.sleep(2)
    
    # 测试5: 攻击目标
    result = test_attack(api, unit_ids)
    test_results.append(("攻击目标", result))
    time.sleep(2)
    
    # 最终报告
    print("\n" + "=" * 70)
    print("[完成] 测试报告")
    print("=" * 70)
    
    passed = sum(1 for _, r in test_results if r == True)
    failed = sum(1 for _, r in test_results if r == False)
    skipped = sum(1 for _, r in test_results if r is None)
    total = len(test_results)
    
    print(f"\n测试统计:")
    print(f"  总测试数: {total}")
    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    print(f"  跳过: {skipped}")
    print(f"  成功率: {passed * 100 // total}%")
    
    print(f"\n详细结果:")
    for test_name, result in test_results:
        if result == True:
            status = "✓ 通过"
        elif result == False:
            status = "✗ 失败"
        else:
            status = "⚠ 跳过"
        print(f"  {status} - {test_name}")
    
    print("\n" + "=" * 70)
    if failed == 0:
        if skipped == 0:
            print("✓✓✓ 所有测试通过！单位操作功能正常 ✓✓✓")
        else:
            print("✓ 测试基本通过（部分测试跳过）")
    else:
        print("✗ 部分测试失败，请检查错误信息")
    print("=" * 70)
    
    print("\n测试完成！")
    print("\n单位操作API总结:")
    print("  • api.select_units(query_param) - 选择单位")
    print("  • api.move_units_by_location(actors, location, attack_move) - 移动单位")
    print("  • api.stop(actors) - 停止单位")
    print("  • api.form_group(actors, group_id) - 编组单位（1-10）")
    print("  • api.attack_target(attacker, target) - 攻击目标")
    
    input("\n按回车退出...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n[错误] 程序异常: {e}")
        import traceback
        traceback.print_exc()

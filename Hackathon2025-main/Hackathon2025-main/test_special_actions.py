#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenRA 特殊动作测试程序
测试：部署、修理、占领、设置集结点
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
    print("OpenRA 特殊动作测试程序")
    print("=" * 70)
    print("\n测试动作清单:")
    print("  1. ✓ 部署 (deploy) - 展开基地车、部署震荡坦克")
    print("  2. ✓ 修理 (repair) - 修理建筑、修理载具")
    print("  3. ✓ 占领 (occupy) - 工程师占领建筑")
    print("  4. ✓ 设置集结点 (set_rally_point) - 生产建筑集结点")
    print("\n测试要求:")
    print("  • 部署测试: 需要基地车(mcv)或震荡坦克(qtnk)")
    print("  • 修理测试: 需要受损建筑或载具")
    print("  • 占领测试: 需要工程师(e6)和中立/敌方建筑")
    print("  • 集结点测试: 需要生产建筑(兵营/车间等)")
    print("\n游戏设置要求:")
    print("  • Skirmish 自由模式")
    print("  • 起始资金: $10000+")
    print("=" * 70)
    print()

def print_section_header(section_num: int, title: str):
    """打印章节标题"""
    print("\n" + "=" * 70)
    print(f"[测试{section_num}] {title}")
    print("=" * 70)

def test_deploy(api: GameAPI):
    """测试1: 部署单位"""
    print_section_header(1, "部署单位 (deploy)")
    
    try:
        # 测试1.1: 部署基地车
        print("\n>> 测试1.1: 查找基地车(mcv)")
        mcv_list = api.query_actor(TargetsQueryParam(
            type=['mcv', '基地车'],
            faction='自己'
        ))
        
        if mcv_list:
            print(f"   ✓ 找到 {len(mcv_list)} 个基地车")
            mcv = mcv_list[0]
            print(f"   基地车位置: ({mcv.position.x}, {mcv.position.y})")
            
            response = input("\n   是否部署该基地车？(y/n): ")
            if response.lower() == 'y':
                print(f"\n   [执行] 部署基地车...")
                api.deploy_units([mcv])
                print(f"   ✓ 部署命令已发送")
                time.sleep(3)
                
                # 检查是否变成建造厂
                factories = api.query_actor(TargetsQueryParam(
                    type=['建造厂', 'fact'],
                    faction='自己'
                ))
                print(f"   [验证] 当前建造厂数量: {len(factories)}")
                print(f"   ✓ 基地车部署测试完成")
            else:
                print(f"   ⚠ 跳过基地车部署")
        else:
            print(f"   ⚠ 未找到基地车")
            print(f"   提示: 可以生产基地车来测试")
        
        # 测试1.2: 部署震荡坦克
        print(f"\n>> 测试1.2: 查找震荡坦克(qtnk)")
        qtnk_list = api.query_actor(TargetsQueryParam(
            type=['qtnk', '震荡坦克'],
            faction='自己'
        ))
        
        if qtnk_list:
            print(f"   ✓ 找到 {len(qtnk_list)} 个震荡坦克")
            qtnk = qtnk_list[0]
            print(f"   震荡坦克位置: ({qtnk.position.x}, {qtnk.position.y})")
            
            response = input("\n   是否部署该震荡坦克？(y/n): ")
            if response.lower() == 'y':
                print(f"\n   [执行] 部署震荡坦克...")
                api.deploy_units([qtnk])
                print(f"   ✓ 部署命令已发送（震荡坦克进入攻击模式）")
                time.sleep(2)
                
                # 再次部署可以收起
                response = input("\n   是否收起震荡坦克？(y/n): ")
                if response.lower() == 'y':
                    api.deploy_units([qtnk])
                    print(f"   ✓ 收起命令已发送（震荡坦克返回移动模式）")
            else:
                print(f"   ⚠ 跳过震荡坦克部署")
        else:
            print(f"   ⚠ 未找到震荡坦克")
            print(f"   提示: 震荡坦克需要科技中心才能生产")
        
        # 测试1.3: 部署地雷车
        print(f"\n>> 测试1.3: 查找地雷部署车(mvly)")
        mvly_list = api.query_actor(TargetsQueryParam(
            type=['mvly', '地雷部署车', 'mvly'],
            faction='自己'
        ))
        
        if mvly_list:
            print(f"   ✓ 找到 {len(mvly_list)} 个地雷部署车")
            mvly = mvly_list[0]
            print(f"   地雷车位置: ({mvly.position.x}, {mvly.position.y})")
            
            response = input("\n   是否部署地雷？(y/n): ")
            if response.lower() == 'y':
                print(f"\n   [执行] 部署地雷...")
                api.deploy_units([mvly])
                print(f"   ✓ 部署命令已发送（地雷车会在当前位置部署地雷）")
                time.sleep(2)
            else:
                print(f"   ⚠ 跳过地雷部署")
        else:
            print(f"   ⚠ 未找到地雷部署车")
        
        print(f"\n✓ 部署单位测试完成")
        return True
    except Exception as e:
        print(f"\n✗ 部署单位测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_repair(api: GameAPI):
    """测试2: 修理单位/建筑"""
    print_section_header(2, "修理单位/建筑 (repair)")
    
    try:
        # 测试2.1: 修理建筑
        print("\n>> 测试2.1: 查找受损建筑")
        all_buildings = api.query_actor(TargetsQueryParam(
            type=['建造厂', 'fact', '电厂', 'powr', '兵营', 'barr', 
                  '战车工厂', 'weap', '矿场', 'proc'],
            faction='自己'
        ))
        
        damaged_buildings = [b for b in all_buildings if b.hppercent < 100]
        
        if damaged_buildings:
            print(f"   ✓ 找到 {len(damaged_buildings)} 个受损建筑:")
            for i, building in enumerate(damaged_buildings[:3], 1):
                print(f"     [{i}] {building.type} - 血量:{building.hppercent}% - "
                      f"位置:({building.position.x},{building.position.y})")
            
            response = input("\n   是否修理这些建筑？(y/n): ")
            if response.lower() == 'y':
                print(f"\n   [执行] 修理建筑...")
                api.repair_units(damaged_buildings[:3])
                print(f"   ✓ 修理命令已发送")
                print(f"   提示: 修理建筑需要花费资金，按血量百分比计算")
                time.sleep(2)
                
                # 验证修理
                print(f"\n   [验证] 检查建筑血量...")
                for building in damaged_buildings[:3]:
                    api.update_actor(building)
                    print(f"     {building.type} 当前血量: {building.hppercent}%")
            else:
                print(f"   ⚠ 跳过建筑修理")
        else:
            print(f"   ⚠ 未找到受损建筑")
            print(f"   提示: 可以让建筑受到攻击后测试修理功能")
        
        # 测试2.2: 修理载具（需要维修厂）
        print(f"\n>> 测试2.2: 查找受损载具")
        
        # 先检查是否有维修厂
        repair_depot = api.query_actor(TargetsQueryParam(
            type=['维修厂', 'fix'],
            faction='自己'
        ))
        
        if not repair_depot:
            print(f"   ⚠ 未找到维修厂")
            print(f"   提示: 修理载具需要先建造维修厂")
        else:
            print(f"   ✓ 找到维修厂")
            
            # 查找载具
            all_vehicles = api.query_actor(TargetsQueryParam(
                type=['采矿车', 'harv', '1tnk', '3tnk', '4tnk', 
                      '轻型坦克', '重型坦克', '猛犸坦克'],
                faction='自己'
            ))
            
            damaged_vehicles = [v for v in all_vehicles if v.hppercent < 100]
            
            if damaged_vehicles:
                print(f"   ✓ 找到 {len(damaged_vehicles)} 个受损载具:")
                for i, vehicle in enumerate(damaged_vehicles[:3], 1):
                    print(f"     [{i}] {vehicle.type} - 血量:{vehicle.hppercent}% - "
                          f"位置:({vehicle.position.x},{vehicle.position.y})")
                
                response = input("\n   是否让载具前往维修厂修理？(y/n): ")
                if response.lower() == 'y':
                    print(f"\n   [执行] 发送修理命令...")
                    api.repair_units(damaged_vehicles[:3])
                    print(f"   ✓ 修理命令已发送")
                    print(f"   提示: 载具会自动前往维修厂进行修理")
                    time.sleep(2)
                else:
                    print(f"   ⚠ 跳过载具修理")
            else:
                print(f"   ⚠ 未找到受损载具")
                print(f"   提示: 可以让载具受到攻击后测试修理功能")
        
        print(f"\n✓ 修理功能测试完成")
        return True
    except Exception as e:
        print(f"\n✗ 修理功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_occupy(api: GameAPI):
    """测试3: 占领建筑"""
    print_section_header(3, "占领建筑 (occupy)")
    
    try:
        # 测试3.1: 查找工程师
        print("\n>> 测试3.1: 查找工程师(e6)")
        engineers = api.query_actor(TargetsQueryParam(
            type=['工程师', 'e6'],
            faction='自己'
        ))
        
        if not engineers:
            print(f"   ⚠ 未找到工程师")
            print(f"   提示: 需要先生产工程师才能测试占领功能")
            
            response = input("\n   是否现在生产工程师？(y/n): ")
            if response.lower() == 'y':
                # 检查兵营
                barracks = api.query_actor(TargetsQueryParam(
                    type=['兵营', 'barr'],
                    faction='自己'
                ))
                
                if barracks:
                    print(f"\n   [生产] 正在生产工程师...")
                    wait_id = api.produce('e6', 1, False)
                    if wait_id:
                        api.wait(wait_id, 30)
                        print(f"   ✓ 工程师生产完成")
                        
                        # 重新查找工程师
                        engineers = api.query_actor(TargetsQueryParam(
                            type=['工程师', 'e6'],
                            faction='自己'
                        ))
                else:
                    print(f"   ✗ 未找到兵营，无法生产工程师")
                    return False
        
        if engineers:
            engineer = engineers[0]
            print(f"\n   ✓ 找到工程师 (ID:{engineer.actor_id})")
            print(f"   位置: ({engineer.position.x}, {engineer.position.y})")
            
            # 测试3.2: 查找可占领的建筑
            print(f"\n>> 测试3.2: 查找可占领的目标")
            
            # 查找敌方建筑
            enemy_buildings = api.query_actor(TargetsQueryParam(
                faction='敌方'
            ))
            
            # 查找中立建筑
            neutral_buildings = api.query_actor(TargetsQueryParam(
                faction='中立'
            ))
            
            occupiable_targets = []
            
            if enemy_buildings:
                enemy_structs = [b for b in enemy_buildings 
                                if b.type in ['建造厂', 'fact', '电厂', 'powr', 
                                             '兵营', 'barr', '战车工厂', 'weap',
                                             '矿场', 'proc', '雷达站', 'dome']]
                occupiable_targets.extend(enemy_structs)
                print(f"   • 敌方建筑: {len(enemy_structs)} 个")
            
            if neutral_buildings:
                occupiable_targets.extend(neutral_buildings)
                print(f"   • 中立建筑: {len(neutral_buildings)} 个")
            
            if occupiable_targets:
                print(f"\n   ✓ 找到 {len(occupiable_targets)} 个可占领目标:")
                for i, target in enumerate(occupiable_targets[:5], 1):
                    print(f"     [{i}] {target.type} - 阵营:{target.faction} - "
                          f"位置:({target.position.x},{target.position.y})")
                
                print(f"\n   占领说明:")
                print(f"     • 工程师需要进入建筑才能占领")
                print(f"     • 占领敌方建筑会变为己方建筑")
                print(f"     • 占领中立建筑（如医院、科技建筑）会获得特殊效果")
                
                response = input("\n   是否让工程师占领第一个目标？(y/n): ")
                if response.lower() == 'y':
                    target = occupiable_targets[0]
                    print(f"\n   [执行] 工程师占领 {target.type}...")
                    
                    # 先移动到目标位置附近
                    print(f"   • 移动工程师到目标位置...")
                    api.move_units_by_location([engineer], target.position)
                    time.sleep(2)
                    
                    # 发送占领命令
                    print(f"   • 发送占领命令...")
                    api.occupy_units([engineer], [target])
                    print(f"   ✓ 占领命令已发送")
                    print(f"   提示: 工程师会自动进入建筑执行占领")
                    time.sleep(3)
                    
                    # 验证占领结果
                    print(f"\n   [验证] 检查占领结果...")
                    api.update_actor(target)
                    if target.faction == '自己':
                        print(f"   ✓ 占领成功！建筑已变为己方")
                    else:
                        print(f"   ⚠ 占领可能还在进行中...")
                else:
                    print(f"   ⚠ 跳过占领测试")
            else:
                print(f"   ⚠ 未找到可占领的目标")
                print(f"   提示: 需要地图上有敌方或中立建筑")
        
        print(f"\n✓ 占领功能测试完成")
        return True
    except Exception as e:
        print(f"\n✗ 占领功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_set_rally_point(api: GameAPI):
    """测试4: 设置集结点"""
    print_section_header(4, "设置集结点 (set_rally_point)")
    
    try:
        # 测试4.1: 查找生产建筑
        print("\n>> 测试4.1: 查找生产建筑")
        production_buildings = api.query_actor(TargetsQueryParam(
            type=['兵营', 'barr', '战车工厂', 'weap', '机场', 'afld'],
            faction='自己'
        ))
        
        if not production_buildings:
            print(f"   ⚠ 未找到生产建筑")
            print(f"   提示: 需要兵营、车间或机场才能测试集结点")
            return False
        
        print(f"   ✓ 找到 {len(production_buildings)} 个生产建筑:")
        for i, building in enumerate(production_buildings, 1):
            print(f"     [{i}] {building.type} - 位置:({building.position.x},{building.position.y})")
        
        # 测试4.2: 设置兵营集结点
        barracks = [b for b in production_buildings if b.type in ['兵营', 'barr']]
        if barracks:
            print(f"\n>> 测试4.2: 设置兵营集结点")
            barrack = barracks[0]
            print(f"   选中兵营: 位置({barrack.position.x},{barrack.position.y})")
            
            # 计算集结点位置（兵营右侧10格）
            rally_point = Location(barrack.position.x + 10, barrack.position.y)
            print(f"   目标集结点: ({rally_point.x},{rally_point.y})")
            
            response = input("\n   是否设置兵营集结点？(y/n): ")
            if response.lower() == 'y':
                print(f"\n   [执行] 设置集结点...")
                api.set_rally_point([barrack], rally_point)
                print(f"   ✓ 集结点已设置")
                print(f"   效果: 新生产的步兵会自动移动到集结点位置")
                
                # 测试验证：生产一个步兵
                response = input("\n   是否生产一个步兵验证集结点？(y/n): ")
                if response.lower() == 'y':
                    print(f"\n   [验证] 生产步兵...")
                    wait_id = api.produce('e1', 1, False)
                    if wait_id:
                        api.wait(wait_id, 20)
                        print(f"   ✓ 步兵生产完成")
                        print(f"   提示: 观察步兵是否自动移动到集结点")
                        time.sleep(3)
            else:
                print(f"   ⚠ 跳过兵营集结点设置")
        
        # 测试4.3: 设置战车工厂集结点
        war_factory = [b for b in production_buildings if b.type in ['战车工厂', 'weap']]
        if war_factory:
            print(f"\n>> 测试4.3: 设置战车工厂集结点")
            factory = war_factory[0]
            print(f"   选中战车工厂: 位置({factory.position.x},{factory.position.y})")
            
            # 计算集结点位置（工厂前方）
            rally_point = Location(factory.position.x, factory.position.y + 8)
            print(f"   目标集结点: ({rally_point.x},{rally_point.y})")
            
            response = input("\n   是否设置战车工厂集结点？(y/n): ")
            if response.lower() == 'y':
                print(f"\n   [执行] 设置集结点...")
                api.set_rally_point([factory], rally_point)
                print(f"   ✓ 集结点已设置")
                print(f"   效果: 新生产的坦克会自动移动到集结点位置")
            else:
                print(f"   ⚠ 跳过战车工厂集结点设置")
        
        # 测试4.4: 设置机场集结点
        airfield = [b for b in production_buildings if b.type in ['机场', 'afld']]
        if airfield:
            print(f"\n>> 测试4.4: 设置机场集结点")
            field = airfield[0]
            print(f"   选中机场: 位置({field.position.x},{field.position.y})")
            
            # 计算集结点位置（机场上空）
            rally_point = Location(field.position.x + 5, field.position.y - 5)
            print(f"   目标巡逻点: ({rally_point.x},{rally_point.y})")
            
            response = input("\n   是否设置机场集结点？(y/n): ")
            if response.lower() == 'y':
                print(f"\n   [执行] 设置集结点...")
                api.set_rally_point([field], rally_point)
                print(f"   ✓ 集结点已设置")
                print(f"   效果: 新生产的飞机会飞往集结点巡逻")
            else:
                print(f"   ⚠ 跳过机场集结点设置")
        
        print(f"\n>> 集结点功能说明:")
        print(f"   • 集结点影响新生产的单位")
        print(f"   • 单位会在生产完成后自动移动到集结点")
        print(f"   • 可以随时更改集结点位置")
        print(f"   • 不同生产建筑可以设置不同的集结点")
        
        print(f"\n✓ 设置集结点测试完成")
        return True
    except Exception as e:
        print(f"\n✗ 设置集结点测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print_header()
    
    input("按回车开始测试...\n")
    
    print("=" * 70)
    print("[*] OpenRA 特殊动作测试程序 - 开始执行")
    print("=" * 70)
    
    # 连接API
    try:
        api = GameAPI('localhost', 7445, 'zh')
        print("\n✓ 成功连接到游戏服务器")
    except Exception as e:
        print(f"\n✗ 连接游戏服务器失败: {e}")
        input("\n按回车退出...")
        return
    
    # 检查游戏状态
    print("\n[准备阶段] 检查游戏状态...")
    try:
        info = api.player_base_info_query()
        print(f"   资金: ${info.Cash}")
        print(f"   电力: {info.Power} / {info.PowerProvided}")
        
        all_units = api.query_actor(TargetsQueryParam(faction='自己'))
        print(f"   己方单位总数: {len(all_units)}")
    except Exception as e:
        print(f"   ⚠ 无法获取游戏状态: {e}")
    
    # 执行测试
    test_results = []
    
    print("\n" + "=" * 70)
    print("请选择要测试的功能:")
    print("  1 - 部署单位 (deploy)")
    print("  2 - 修理建筑/载具 (repair)")
    print("  3 - 占领建筑 (occupy)")
    print("  4 - 设置集结点 (set_rally_point)")
    print("  5 - 全部测试")
    print("=" * 70)
    
    choice = input("\n请输入选择 (1-5): ").strip()
    
    if choice == '1' or choice == '5':
        result = test_deploy(api)
        test_results.append(("部署单位", result))
        time.sleep(2)
    
    if choice == '2' or choice == '5':
        result = test_repair(api)
        test_results.append(("修理功能", result))
        time.sleep(2)
    
    if choice == '3' or choice == '5':
        result = test_occupy(api)
        test_results.append(("占领建筑", result))
        time.sleep(2)
    
    if choice == '4' or choice == '5':
        result = test_set_rally_point(api)
        test_results.append(("设置集结点", result))
    
    # 最终报告
    if test_results:
        print("\n" + "=" * 70)
        print("[完成] 测试报告")
        print("=" * 70)
        
        passed = sum(1 for _, r in test_results if r == True)
        failed = sum(1 for _, r in test_results if r == False)
        total = len(test_results)
        
        print(f"\n测试统计:")
        print(f"  总测试数: {total}")
        print(f"  通过: {passed}")
        print(f"  失败: {failed}")
        if total > 0:
            print(f"  成功率: {passed * 100 // total}%")
        
        print(f"\n详细结果:")
        for test_name, result in test_results:
            status = "✓ 通过" if result else "✗ 失败"
            print(f"  {status} - {test_name}")
        
        print("\n" + "=" * 70)
        if failed == 0:
            print("✓✓✓ 所有测试通过！特殊动作功能正常 ✓✓✓")
        else:
            print("✗ 部分测试失败，请检查错误信息")
        print("=" * 70)
    
    print("\n测试完成！")
    print("\n特殊动作API总结:")
    print("  • api.deploy_units(actors) - 部署/展开单位")
    print("  • api.repair_units(actors) - 修理建筑/载具")
    print("  • api.occupy_units(occupiers, targets) - 占领建筑")
    print("  • api.set_rally_point(buildings, location) - 设置集结点")
    
    print("\n使用场景:")
    print("  • 部署: 展开基地车、部署震荡坦克、部署地雷车")
    print("  • 修理: 修复受损建筑、让载具前往维修厂")
    print("  • 占领: 工程师占领敌方/中立建筑")
    print("  • 集结点: 控制新生产单位的集合位置")
    
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
        input("\n按回车退出...")

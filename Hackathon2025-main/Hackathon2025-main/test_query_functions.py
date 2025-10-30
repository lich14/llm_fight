#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenRA 己方信息查询功能测试程序
测试：己方单位、己方建筑、基地资源、生产队列、单位属性、地图信息
"""

import sys
import time
from typing import List, Dict, Any
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
    print("OpenRA 己方信息查询功能测试程序")
    print("=" * 70)
    print("\n测试内容清单:")
    print("  1. ✓ 己方单位查询")
    print("  2. ✓ 己方建筑查询")
    print("  3. ✓ 基地资源查询")
    print("  4. ✓ 生产队列查询")
    print("  5. ✓ 单位属性查询")
    print("  6. ✓ 地图信息查询")
    print("\n测试目的:")
    print("  • 验证所有查询API是否正常工作")
    print("  • 了解返回数据的结构和内容")
    print("  • 为AI决策提供信息基础")
    print("=" * 70)
    print()

def print_section_header(section_num: int, title: str):
    """打印章节标题"""
    print("\n" + "=" * 70)
    print(f"[测试{section_num}] {title}")
    print("=" * 70)

def test_query_own_units(api: GameAPI):
    """测试1: 查询己方单位"""
    print_section_header(1, "查询己方单位")
    
    try:
        print("\n>> 测试1.1: 查询所有己方单位")
        all_units = api.query_actor(TargetsQueryParam(faction='自己'))
        print(f"   ✓ 找到 {len(all_units)} 个己方单位")
        
        # 按类型分类统计
        unit_types = {}
        for unit in all_units:
            unit_types[unit.type] = unit_types.get(unit.type, 0) + 1
        
        print(f"\n   单位类型统计:")
        for unit_type, count in sorted(unit_types.items()):
            print(f"     • {unit_type}: {count} 个")
        
        # 查询特定类型单位
        print(f"\n>> 测试1.2: 查询特定类型单位（步兵）")
        infantry = api.query_actor(TargetsQueryParam(
            type=['步兵', 'e1', 'e2', 'e3', 'e4', 'e6', 'shok', 'thf', 'dog'],
            faction='自己'
        ))
        if infantry:
            print(f"   ✓ 找到 {len(infantry)} 个步兵单位")
            for i, unit in enumerate(infantry[:3], 1):
                print(f"     [{i}] {unit.type} - ID:{unit.actor_id} - "
                      f"位置:({unit.position.x},{unit.position.y}) - "
                      f"血量:{unit.hppercent}%")
        else:
            print(f"   ⚠ 未找到步兵单位")
        
        # 查询载具
        print(f"\n>> 测试1.3: 查询载具单位")
        vehicles = api.query_actor(TargetsQueryParam(
            type=['mcv', 'harv', 'apc', 'ftrk', 'jeep', 'truk', '1tnk', '3tnk', '4tnk'],
            faction='自己'
        ))
        if vehicles:
            print(f"   ✓ 找到 {len(vehicles)} 个载具单位")
            for i, unit in enumerate(vehicles[:3], 1):
                print(f"     [{i}] {unit.type} - ID:{unit.actor_id} - "
                      f"位置:({unit.position.x},{unit.position.y}) - "
                      f"血量:{unit.hppercent}%")
        else:
            print(f"   ⚠ 未找到载具单位")
        
        print(f"\n✓ 己方单位查询测试通过")
        return True
    except Exception as e:
        print(f"\n✗ 己方单位查询测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_query_own_buildings(api: GameAPI):
    """测试2: 查询己方建筑"""
    print_section_header(2, "查询己方建筑")
    
    try:
        print("\n>> 测试2.1: 查询所有己方建筑")
        
        # 查询所有建筑类型
        building_types = [
            '建造厂', 'fact', '兵营', 'barr', '战车工厂', 'weap', '机场', 'afld',
            '电厂', 'powr', '核电站', 'apwr', '矿场', 'proc', '储存罐', 'silo',
            '雷达站', 'dome', '维修厂', 'fix', '科技中心', 'stek', '军犬窝', 'kennel',
            '火焰塔', 'ftur', '特斯拉线圈', 'tsla', '防空导弹', 'sam',
            '铁幕装置', 'iron', '核弹发射井', 'mslo'
        ]
        
        all_buildings = api.query_actor(TargetsQueryParam(
            type=building_types,
            faction='自己'
        ))
        
        print(f"   ✓ 找到 {len(all_buildings)} 个建筑")
        
        # 按类型分类
        building_stats = {}
        for building in all_buildings:
            building_stats[building.type] = building_stats.get(building.type, 0) + 1
        
        print(f"\n   建筑类型统计:")
        for building_type, count in sorted(building_stats.items()):
            print(f"     • {building_type}: {count} 个")
        
        # 查询关键建筑
        print(f"\n>> 测试2.2: 查询关键生产建筑")
        key_buildings = ['建造厂', 'fact', '兵营', 'barr', '战车工厂', 'weap', '机场', 'afld']
        production_buildings = api.query_actor(TargetsQueryParam(
            type=key_buildings,
            faction='自己'
        ))
        
        if production_buildings:
            print(f"   ✓ 找到 {len(production_buildings)} 个生产建筑:")
            for building in production_buildings:
                print(f"     • {building.type} - ID:{building.actor_id} - "
                      f"位置:({building.position.x},{building.position.y}) - "
                      f"血量:{building.hppercent}%")
        else:
            print(f"   ⚠ 未找到生产建筑")
        
        # 查询防御建筑
        print(f"\n>> 测试2.3: 查询防御建筑")
        defense_buildings = api.query_actor(TargetsQueryParam(
            type=['火焰塔', 'ftur', '特斯拉线圈', 'tsla', '防空导弹', 'sam'],
            faction='自己'
        ))
        
        if defense_buildings:
            print(f"   ✓ 找到 {len(defense_buildings)} 个防御建筑:")
            for building in defense_buildings:
                print(f"     • {building.type} - 位置:({building.position.x},{building.position.y})")
        else:
            print(f"   ⚠ 未找到防御建筑")
        
        print(f"\n✓ 己方建筑查询测试通过")
        return True
    except Exception as e:
        print(f"\n✗ 己方建筑查询测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_query_base_resources(api: GameAPI):
    """测试3: 查询基地资源"""
    print_section_header(3, "查询基地资源")
    
    try:
        print("\n>> 测试3.1: 查询基地信息")
        info = api.player_base_info_query()
        
        print(f"\n   ✓ 基地资源信息:")
        print(f"     • 现金 (Cash): ${info.Cash}")
        print(f"     • 矿石 (Resources): {info.Resources} 单位")
        print(f"     • 总资金: ${info.Cash + info.Resources}")
        print(f"     • 电力消耗 (PowerDrained): {info.PowerDrained}")
        print(f"     • 电力供应 (PowerProvided): {info.PowerProvided}")
        print(f"     • 剩余电力 (Power): {info.Power}")
        
        # 电力状态分析
        print(f"\n   电力状态分析:")
        if info.Power > 0:
            power_percent = (info.Power * 100) // info.PowerProvided if info.PowerProvided > 0 else 0
            print(f"     ✓ 电力充足 ({power_percent}% 剩余)")
        elif info.Power == 0:
            print(f"     ⚠ 电力紧张（刚好够用）")
        else:
            print(f"     ✗ 电力不足（缺少 {-info.Power} 单位）")
        
        # 资金状态分析
        print(f"\n   资金状态分析:")
        total_money = info.Cash + info.Resources
        if total_money > 10000:
            print(f"     ✓ 资金充裕 (${total_money})")
        elif total_money > 5000:
            print(f"     ⚠ 资金中等 (${total_money})")
        else:
            print(f"     ✗ 资金紧张 (${total_money})")
        
        print(f"\n✓ 基地资源查询测试通过")
        return True
    except Exception as e:
        print(f"\n✗ 基地资源查询测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_query_production_queue(api: GameAPI):
    """测试4: 查询生产队列"""
    print_section_header(4, "查询生产队列")
    
    try:
        queue_types = ['Building', 'Defense', 'Infantry', 'Vehicle', 'Aircraft', 'Naval']
        
        print("\n>> 测试4.1: 查询所有生产队列")
        
        for queue_type in queue_types:
            try:
                queue_info = api.query_production_queue(queue_type)
                
                has_items = queue_info.get('has_ready_item', False)
                items = queue_info.get('queue_items', [])
                
                if items:
                    print(f"\n   [{queue_type}队列] - {len(items)} 个项目")
                    for i, item in enumerate(items, 1):
                        status = item.get('status', 'unknown')
                        name = item.get('chineseName', item.get('name', 'unknown'))
                        progress = item.get('progress_percent', 0)
                        
                        if status == 'completed':
                            print(f"     [{i}] ✓ {name} - 已完成 (可放置)")
                        elif status == 'in_progress':
                            print(f"     [{i}] ⏳ {name} - 建造中 ({progress}%)")
                        elif status == 'paused':
                            print(f"     [{i}] ⏸ {name} - 已暂停 ({progress}%)")
                        else:
                            print(f"     [{i}] ⏱ {name} - 等待中")
                else:
                    print(f"\n   [{queue_type}队列] - 空闲")
            except Exception as e:
                print(f"\n   [{queue_type}队列] - 查询失败: {e}")
        
        # 测试单个队列详细信息
        print(f"\n>> 测试4.2: 查询建筑队列详细信息")
        building_queue = api.query_production_queue('Building')
        
        if building_queue.get('queue_items'):
            print(f"   ✓ 建筑队列详细信息:")
            for item in building_queue['queue_items']:
                print(f"\n     项目: {item.get('chineseName', item.get('name'))}")
                print(f"       状态: {item.get('status')}")
                print(f"       进度: {item.get('progress_percent')}%")
                print(f"       剩余时间: {item.get('remaining_time')}秒")
                print(f"       总时间: {item.get('total_time')}秒")
                print(f"       剩余花费: ${item.get('remaining_cost')}")
                print(f"       总花费: ${item.get('total_cost')}")
                print(f"       所属建筑ID: {item.get('owner_actor_id')}")
        else:
            print(f"   ⚠ 建筑队列为空")
        
        print(f"\n✓ 生产队列查询测试通过")
        return True
    except Exception as e:
        print(f"\n✗ 生产队列查询测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_query_unit_attributes(api: GameAPI):
    """测试5: 查询单位属性"""
    print_section_header(5, "查询单位属性")
    
    try:
        # 查找一些单位来测试
        print("\n>> 测试5.1: 查询步兵单位属性")
        infantry = api.query_actor(TargetsQueryParam(
            type=['步兵', 'e1', 'e3'],
            faction='自己'
        ))
        
        if infantry:
            test_units = infantry[:2]  # 测试前2个单位
            attr_result = api.unit_attribute_query(test_units)
            
            print(f"   ✓ 查询到 {len(test_units)} 个单位的属性:")
            
            if 'attributes' in attr_result:
                for i, attr in enumerate(attr_result['attributes'], 1):
                    print(f"\n     [单位{i}] ID: {attr.get('actorId')}")
                    print(f"       速度 (Speed): {attr.get('speed')}")
                    print(f"       攻击范围 (AttackRange): {attr.get('attackRange')}")
                    print(f"       可攻击目标类型: {attr.get('targetTypes', [])}")
                    
                    # 显示攻击范围内的目标
                    targets = attr.get('targets', [])
                    if targets:
                        print(f"       攻击范围内的目标: {len(targets)} 个")
                        for target_id in targets[:3]:
                            print(f"         • 目标ID: {target_id}")
                    else:
                        print(f"       攻击范围内的目标: 无")
        else:
            print(f"   ⚠ 未找到步兵单位，跳过属性查询")
        
        # 查询载具属性
        print(f"\n>> 测试5.2: 查询载具单位属性")
        vehicles = api.query_actor(TargetsQueryParam(
            type=['harv', '采矿车', '1tnk', '3tnk', '轻型坦克', '重型坦克'],
            faction='自己'
        ))
        
        if vehicles:
            test_vehicle = vehicles[:1]
            attr_result = api.unit_attribute_query(test_vehicle)
            
            print(f"   ✓ 查询到载具属性:")
            
            if 'attributes' in attr_result:
                attr = attr_result['attributes'][0]
                print(f"     单位类型: {test_vehicle[0].type}")
                print(f"     速度: {attr.get('speed')}")
                print(f"     攻击范围: {attr.get('attackRange')}")
                print(f"     可攻击目标: {attr.get('targetTypes', [])}")
        else:
            print(f"   ⚠ 未找到载具单位")
        
        print(f"\n✓ 单位属性查询测试通过")
        return True
    except Exception as e:
        print(f"\n✗ 单位属性查询测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_query_map_info(api: GameAPI):
    """测试6: 查询地图信息"""
    print_section_header(6, "查询地图信息")
    
    try:
        print("\n>> 测试6.1: 查询地图基本信息")
        map_info = api.map_query()
        
        print(f"\n   ✓ 地图基本信息:")
        print(f"     • 地图宽度: {map_info.MapWidth}")
        print(f"     • 地图高度: {map_info.MapHeight}")
        print(f"     • 总格子数: {map_info.MapWidth * map_info.MapHeight}")
        
        # 统计可见和已探索区域
        print(f"\n>> 测试6.2: 统计地图探索状态")
        
        visible_count = 0
        explored_count = 0
        unexplored_count = 0
        
        for x in range(map_info.MapWidth):
            for y in range(map_info.MapHeight):
                if map_info.IsVisible[x][y]:
                    visible_count += 1
                elif map_info.IsExplored[x][y]:
                    explored_count += 1
                else:
                    unexplored_count += 1
        
        total = map_info.MapWidth * map_info.MapHeight
        print(f"\n   ✓ 地图探索统计:")
        print(f"     • 当前可见: {visible_count} 格 ({visible_count*100//total}%)")
        print(f"     • 已探索（迷雾中）: {explored_count} 格 ({explored_count*100//total}%)")
        print(f"     • 未探索: {unexplored_count} 格 ({unexplored_count*100//total}%)")
        print(f"     • 总探索率: {(visible_count+explored_count)*100//total}%")
        
        # 统计资源分布
        print(f"\n>> 测试6.3: 统计地图资源分布")
        
        ore_count = 0
        gem_count = 0
        total_resources = 0
        
        for x in range(map_info.MapWidth):
            for y in range(map_info.MapHeight):
                resource_type = map_info.ResourcesType[x][y]
                resource_amount = map_info.Resources[x][y]
                
                if resource_amount > 0:
                    total_resources += resource_amount
                    if resource_type == 'Ore':
                        ore_count += 1
                    elif resource_type == 'Gems':
                        gem_count += 1
        
        print(f"\n   ✓ 资源分布:")
        print(f"     • 矿石格子: {ore_count} 个")
        print(f"     • 宝石格子: {gem_count} 个")
        print(f"     • 总资源量: {total_resources} 单位")
        
        # 测试特定位置查询
        print(f"\n>> 测试6.4: 查询特定位置信息")
        
        # 查找己方建筑位置
        buildings = api.query_actor(TargetsQueryParam(
            type=['建造厂', 'fact'],
            faction='自己'
        ))
        
        if buildings:
            test_pos = buildings[0].position
            print(f"\n   测试位置: ({test_pos.x}, {test_pos.y})")
            
            height = map_info.Height[test_pos.x][test_pos.y]
            terrain = map_info.Terrain[test_pos.x][test_pos.y]
            visible = map_info.IsVisible[test_pos.x][test_pos.y]
            explored = map_info.IsExplored[test_pos.x][test_pos.y]
            
            print(f"     • 高度: {height}")
            print(f"     • 地形类型: {terrain}")
            print(f"     • 可见性: {'可见' if visible else '不可见'}")
            print(f"     • 探索状态: {'已探索' if explored else '未探索'}")
            
            # 使用get_value_at_location方法
            print(f"\n   使用get_value_at_location方法:")
            print(f"     • 高度: {map_info.get_value_at_location('Height', test_pos)}")
            print(f"     • 地形: {map_info.get_value_at_location('Terrain', test_pos)}")
        
        print(f"\n✓ 地图信息查询测试通过")
        return True
    except Exception as e:
        print(f"\n✗ 地图信息查询测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print_header()
    
    input("按回车开始测试...\n")
    
    print("=" * 70)
    print("[*] OpenRA 己方信息查询测试程序 - 开始执行")
    print("=" * 70)
    
    # 连接API
    try:
        api = GameAPI('localhost', 7445, 'zh')
        print("\n✓ 成功连接到游戏服务器")
    except Exception as e:
        print(f"\n✗ 连接游戏服务器失败: {e}")
        input("\n按回车退出...")
        return
    
    # 执行所有测试
    test_results = []
    
    # 测试1: 己方单位查询
    result = test_query_own_units(api)
    test_results.append(("己方单位查询", result))
    time.sleep(1)
    
    # 测试2: 己方建筑查询
    result = test_query_own_buildings(api)
    test_results.append(("己方建筑查询", result))
    time.sleep(1)
    
    # 测试3: 基地资源查询
    result = test_query_base_resources(api)
    test_results.append(("基地资源查询", result))
    time.sleep(1)
    
    # 测试4: 生产队列查询
    result = test_query_production_queue(api)
    test_results.append(("生产队列查询", result))
    time.sleep(1)
    
    # 测试5: 单位属性查询
    result = test_query_unit_attributes(api)
    test_results.append(("单位属性查询", result))
    time.sleep(1)
    
    # 测试6: 地图信息查询
    result = test_query_map_info(api)
    test_results.append(("地图信息查询", result))
    
    # 最终报告
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
    print(f"  成功率: {passed * 100 // total}%")
    
    print(f"\n详细结果:")
    for test_name, result in test_results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status} - {test_name}")
    
    print("\n" + "=" * 70)
    if failed == 0:
        print("✓✓✓ 所有测试通过！查询功能正常 ✓✓✓")
    else:
        print("✗ 部分测试失败，请检查错误信息")
    print("=" * 70)
    
    print("\n测试完成！")
    print("\n己方信息查询API总结:")
    print("  • api.query_actor(TargetsQueryParam) - 查询单位/建筑")
    print("  • api.player_base_info_query() - 查询基地资源和电力")
    print("  • api.query_production_queue(queue_type) - 查询生产队列")
    print("  • api.unit_attribute_query(actors) - 查询单位属性")
    print("  • api.map_query() - 查询地图信息")
    
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenRA 全建筑建造程序
建造所有建筑类型：生产建筑、基础设施、支援建筑、防御建筑、特殊建筑
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
from OpenRA_Copilot_Library.models import TargetsQueryParam

def print_header():
    """打印程序头部信息"""
    print("=" * 70)
    print("OpenRA 全建筑建造程序")
    print("=" * 70)
    print("\n目标建筑清单:")
    print("\n📦 生产建筑:")
    print("  • 建造厂 (fact) - 由基地车展开")
    print("  • 兵营 (barr) - 生产步兵")
    print("  • 战车工厂 (weap) - 生产载具和坦克")
    print("  • 空军基地 (afld) - 生产飞机")
    print("\n⚡ 基础设施:")
    print("  • 电厂 (powr) x6 - 基础发电")
    print("  • 核电站 (apwr) - 高级发电")
    print("  • 矿场 (proc) - 矿石精炼")
    print("  • 储存罐 (silo) - 存储资源")
    print("  • 雷达站 (dome) - 提供雷达视野")
    print("\n🔧 支援建筑:")
    print("  • 维修厂 (fix) - 修理载具")
    print("  • 科技中心 (stek) - 解锁高级单位")
    print("  • 军犬窝 (kennel) - 生产军犬")
    print("\n🛡️ 防御建筑:")
    print("  • 火焰塔 (ftur) x2 - 近距离防御")
    print("  • 特斯拉线圈 (tsla) x2 - 强力防御")
    print("  • 防空导弹 (sam) x2 - 对空防御")
    print("\n🚀 特殊建筑:")
    print("  • 铁幕装置 (iron) - 单位无敌")
    print("  • 核弹发射井 (mslo) - 发射核弹")
    print("\n游戏设置要求:")
    print("  • Skirmish 自由模式")
    print("  • 起始资金: $50000+ (建议$100000)")
    print("  • 科技等级: Unrestricted")
    print("  • AI: None")
    print("  • 地图: 选择大型地图（需要大量空间）")
    print("=" * 70)
    print()

def wait_for_building(api: GameAPI, building_name: str, timeout: int = 120, check_interval: int = 10) -> bool:
    """
    等待指定建筑建造完成
    
    Args:
        api: GameAPI实例
        building_name: 建筑名称
        timeout: 超时时间（秒）
        check_interval: 检查间隔（秒）
    
    Returns:
        bool: True表示建造成功，False表示超时
    """
    print(f"   [等待] {building_name} 建造完成...")
    elapsed = 0
    
    while elapsed < timeout:
        time.sleep(check_interval)
        elapsed += check_interval
        
        # 查询建筑（支持多种名称）
        possible_names = [building_name]
        if building_name == "车间":
            possible_names.append("战车工厂")
        elif building_name == "雷达":
            possible_names.append("雷达站")
        elif building_name == "机场":
            possible_names.extend(["空军基地", "afld"])
        
        buildings = api.query_actor(TargetsQueryParam(
            type=possible_names,
            faction='自己'
        ))
        
        if buildings and len(buildings) > 0:
            # 检查建筑是否完全建成（血量100%）
            for building in buildings:
                if building.hppercent >= 100:
                    print(f"      ✓ {building_name} 已完成！")
                    return True
            
            # 建筑存在但未完成
            print(f"      建造中... ({elapsed}秒，血量{buildings[0].hppercent}%)")
        else:
            print(f"      等待中... ({elapsed}秒)")
    
    print(f"      ✗ {building_name} 建造超时")
    return False

def build_structure(api: GameAPI, building_name: str, building_code: str, quantity: int = 1) -> int:
    """
    建造指定数量的建筑
    
    Args:
        api: GameAPI实例
        building_name: 建筑中文名称
        building_code: 建筑代码
        quantity: 建造数量
    
    Returns:
        int: 成功建造的数量
    """
    print(f"\n--- {building_name} (代码: {building_code}, 数量: x{quantity}) ---")
    
    success_count = 0
    
    # 批量下单
    if quantity > 1:
        print(f"   [批量下单] 下单 {quantity} 个 {building_name}...")
        for i in range(quantity):
            try:
                api.produce(building_code, 1, True)
                print(f"   [{i+1}/{quantity}] 已下单")
                time.sleep(0.5)
            except Exception as e:
                print(f"   [{i+1}/{quantity}] ✗ 下单失败: {e}")
        
        # 等待全部完成
        print(f"   [等待] 等待所有 {building_name} 建造完成...")
        for attempt in range(20):  # 最多等待3分钟
            time.sleep(10)
            buildings = api.query_actor(TargetsQueryParam(type=[building_code, building_name], faction='自己'))
            completed = len([b for b in buildings if b.hppercent >= 100]) if buildings else 0
            print(f"      第{attempt+1}轮: 已完成 {completed}/{quantity}")
            if completed >= quantity:
                success_count = quantity
                print(f"   ✓ 所有 {building_name} 建造完成！")
                break
    else:
        # 单个建筑
        try:
            api.produce(building_code, 1, True)
            print(f"   [下单] {building_name}")
            if wait_for_building(api, building_name, timeout=150):
                success_count = 1
        except Exception as e:
            print(f"   [错误] {e}")
    
    return success_count

def main():
    """主函数"""
    print_header()
    
    input("按回车开始...\n")
    
    print("=" * 70)
    print("[*] OpenRA 全建筑建造程序 - 开始执行")
    print("=" * 70)
    
    # 连接API
    api = GameAPI('localhost', 7445, 'zh')
    
    # 步骤1: 检查初始状态
    print("\n[步骤1] 检查游戏状态...")
    info = api.player_base_info_query()
    print(f"   资金: ${info.Cash}")
    print(f"   电力: {info.Power} / {info.PowerProvided}")
    
    if info.Cash < 40000:
        print("\n   [警告] 资金不足！建议至少$50000")
        print("   建造所有建筑大约需要: $40000+")
        response = input("   继续？(y/n): ")
        if response.lower() != 'y':
            return
    
    # 步骤2: 部署基地车 → 建造厂
    print("\n[步骤2] 部署基地车 → 建造厂...")
    try:
        api.deploy_mcv_and_wait(5)
        print("   ✓ 建造厂已就绪")
    except Exception as e:
        print(f"   [信息] {e}")
    
    time.sleep(3)
    
    # 统计变量
    total_buildings = 0
    successful_buildings = []
    failed_buildings = []
    
    # 步骤3: 建造电厂系统 (6个电厂)
    print("\n" + "=" * 70)
    print("[步骤3] 基础设施 - 电厂系统")
    print("=" * 70)
    
    count = build_structure(api, "电厂", "电厂", 6)
    total_buildings += count
    if count > 0:
        successful_buildings.append(f"电厂 x{count}")
    else:
        failed_buildings.append("电厂")
    
    time.sleep(5)
    
    # 步骤4: 建造矿场
    print("\n" + "=" * 70)
    print("[步骤4] 基础设施 - 矿场")
    print("=" * 70)
    
    count = build_structure(api, "矿场", "矿场", 1)
    total_buildings += count
    if count > 0:
        successful_buildings.append("矿场")
    else:
        failed_buildings.append("矿场")
    
    time.sleep(3)
    
    # 步骤5: 建造储存罐
    print("\n" + "=" * 70)
    print("[步骤5] 基础设施 - 储存罐")
    print("=" * 70)
    
    count = build_structure(api, "储存罐", "储存罐", 1)
    total_buildings += count
    if count > 0:
        successful_buildings.append("储存罐")
    else:
        failed_buildings.append("储存罐")
    
    time.sleep(3)
    
    # 步骤6: 建造雷达站
    print("\n" + "=" * 70)
    print("[步骤6] 基础设施 - 雷达站")
    print("=" * 70)
    
    count = build_structure(api, "雷达", "雷达", 1)
    total_buildings += count
    if count > 0:
        successful_buildings.append("雷达站")
    else:
        failed_buildings.append("雷达站")
    
    time.sleep(3)
    
    # 步骤7: 建造兵营
    print("\n" + "=" * 70)
    print("[步骤7] 生产建筑 - 兵营")
    print("=" * 70)
    
    count = build_structure(api, "兵营", "兵营", 1)
    total_buildings += count
    if count > 0:
        successful_buildings.append("兵营")
    else:
        failed_buildings.append("兵营")
    
    time.sleep(3)
    
    # 步骤8: 建造战车工厂
    print("\n" + "=" * 70)
    print("[步骤8] 生产建筑 - 战车工厂")
    print("=" * 70)
    
    count = build_structure(api, "战车工厂", "战车工厂", 1)
    total_buildings += count
    if count > 0:
        successful_buildings.append("战车工厂")
    else:
        failed_buildings.append("战车工厂")
    
    time.sleep(3)
    
    # 步骤9: 建造维修厂
    print("\n" + "=" * 70)
    print("[步骤9] 支援建筑 - 维修厂")
    print("=" * 70)
    
    count = build_structure(api, "维修厂", "维修厂", 1)
    total_buildings += count
    if count > 0:
        successful_buildings.append("维修厂")
    else:
        failed_buildings.append("维修厂")
    
    time.sleep(3)
    
    # 步骤10: 建造科技中心
    print("\n" + "=" * 70)
    print("[步骤10] 支援建筑 - 科技中心")
    print("=" * 70)
    
    count = build_structure(api, "科技中心", "科技中心", 1)
    total_buildings += count
    if count > 0:
        successful_buildings.append("科技中心")
    else:
        failed_buildings.append("科技中心")
    
    time.sleep(3)
    
    # 步骤11: 建造空军基地
    print("\n" + "=" * 70)
    print("[步骤11] 生产建筑 - 空军基地")
    print("=" * 70)
    
    count = build_structure(api, "机场", "机场", 1)
    total_buildings += count
    if count > 0:
        successful_buildings.append("空军基地")
    else:
        failed_buildings.append("空军基地")
    
    time.sleep(3)
    
    # 步骤12: 建造核电站
    print("\n" + "=" * 70)
    print("[步骤12] 基础设施 - 核电站")
    print("=" * 70)
    
    count = build_structure(api, "核电站", "核电站", 1)
    total_buildings += count
    if count > 0:
        successful_buildings.append("核电站")
    else:
        failed_buildings.append("核电站")
    
    time.sleep(3)
    
    # 步骤13: 建造军犬窝
    print("\n" + "=" * 70)
    print("[步骤13] 支援建筑 - 军犬窝")
    print("=" * 70)
    
    count = build_structure(api, "军犬窝", "军犬窝", 1)
    total_buildings += count
    if count > 0:
        successful_buildings.append("军犬窝")
    else:
        failed_buildings.append("军犬窝")
    
    time.sleep(3)
    
    # 步骤14: 建造防御建筑 - 火焰塔
    print("\n" + "=" * 70)
    print("[步骤14] 防御建筑 - 火焰塔")
    print("=" * 70)
    
    count = build_structure(api, "火焰塔", "火焰塔", 2)
    total_buildings += count
    if count > 0:
        successful_buildings.append(f"火焰塔 x{count}")
    else:
        failed_buildings.append("火焰塔")
    
    time.sleep(3)
    
    # 步骤15: 建造防御建筑 - 特斯拉线圈
    print("\n" + "=" * 70)
    print("[步骤15] 防御建筑 - 特斯拉线圈")
    print("=" * 70)
    
    count = build_structure(api, "特斯拉线圈", "特斯拉线圈", 2)
    total_buildings += count
    if count > 0:
        successful_buildings.append(f"特斯拉线圈 x{count}")
    else:
        failed_buildings.append("特斯拉线圈")
    
    time.sleep(3)
    
    # 步骤16: 建造防御建筑 - 防空导弹
    print("\n" + "=" * 70)
    print("[步骤16] 防御建筑 - 防空导弹")
    print("=" * 70)
    
    count = build_structure(api, "防空导弹", "防空导弹", 2)
    total_buildings += count
    if count > 0:
        successful_buildings.append(f"防空导弹 x{count}")
    else:
        failed_buildings.append("防空导弹")
    
    time.sleep(3)
    
    # 步骤17: 建造特殊建筑 - 铁幕装置
    print("\n" + "=" * 70)
    print("[步骤17] 特殊建筑 - 铁幕装置")
    print("=" * 70)
    
    count = build_structure(api, "铁幕装置", "铁幕装置", 1)
    total_buildings += count
    if count > 0:
        successful_buildings.append("铁幕装置")
    else:
        failed_buildings.append("铁幕装置")
    
    time.sleep(3)
    
    # 步骤18: 建造特殊建筑 - 核弹发射井
    print("\n" + "=" * 70)
    print("[步骤18] 特殊建筑 - 核弹发射井")
    print("=" * 70)
    
    count = build_structure(api, "核弹发射井", "核弹发射井", 1)
    total_buildings += count
    if count > 0:
        successful_buildings.append("核弹发射井")
    else:
        failed_buildings.append("核弹发射井")
    
    time.sleep(5)
    
    # 最终报告
    print("\n" + "=" * 70)
    print("[完成] 最终建造报告")
    print("=" * 70)
    
    info = api.player_base_info_query()
    all_units = api.query_actor(TargetsQueryParam(faction='自己'))
    
    # 统计所有建筑
    building_list = {}
    for unit in all_units:
        if unit.type in ['建造厂', '电厂', '核电站', '矿场', '储存罐', '雷达站', '兵营', 
                         '战车工厂', '车间', '机场', '空军基地', '维修厂', '科技中心', '军犬窝',
                         '火焰塔', '特斯拉线圈', '防空导弹', '铁幕装置', '核弹发射井']:
            building_list[unit.type] = building_list.get(unit.type, 0) + 1
    
    print(f"\n资源状态:")
    print(f"  剩余资金: ${info.Cash}")
    print(f"  电力: {info.Power} / {info.PowerProvided}")
    print(f"  总建筑数: {len([u for u in all_units if u.type in building_list.keys()])}")
    
    print(f"\n建造结果:")
    print(f"  成功建造: {total_buildings} 栋建筑")
    print(f"  成功类型: {len(successful_buildings)} / 17 种")
    
    if successful_buildings:
        print(f"\n✓ 成功建造:")
        for item in successful_buildings:
            print(f"    • {item}")
    
    if failed_buildings:
        print(f"\n✗ 未能建造:")
        for item in failed_buildings:
            print(f"    • {item}")
        print(f"\n失败原因可能:")
        print(f"  - 空间不足（建筑需要大量空间）")
        print(f"  - 电力不足")
        print(f"  - 资金不足")
        print(f"  - 科技等级限制")
    
    # 显示详细建筑清单
    if building_list:
        print(f"\n当前基地建筑清单:")
        for building_type, count in sorted(building_list.items()):
            print(f"  • {building_type}: {count} 栋")
    
    # 成功判断
    print("\n" + "=" * 70)
    if len(successful_buildings) >= 15:
        print("✓✓✓ 基地建设完成！大部分建筑已建造 ✓✓✓")
    elif len(successful_buildings) >= 10:
        print("✓ 基地基本完成")
    else:
        print("⚠ 基地建设未完成")
        print("\n提示: 建议使用大型地图并设置更多起始资金")
    print("=" * 70)
    
    print(f"\n电力分析:")
    print(f"  当前供电: {info.PowerProvided}")
    print(f"  当前耗电: {info.PowerDrained}")
    print(f"  剩余电力: {info.Power}")
    if info.Power > 0:
        print(f"  状态: ✓ 电力充足")
    else:
        print(f"  状态: ✗ 电力不足，需要建造更多电厂")
    
    print("\n程序执行完成！您现在拥有一个功能完整的基地！")
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenRA 全坦克建造程序
生产所有坦克单位：轻型坦克、重型坦克、猛犸坦克、V2火箭发射车、特斯拉坦克、震荡坦克
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
    print("OpenRA 全坦克建造程序")
    print("=" * 70)
    print("\n目标坦克:")
    print("  • 轻型坦克 (1tnk) - 盟军轻型坦克，速度快")
    print("  • 重型坦克 (3tnk) - 苏军犀牛坦克，平衡性好")
    print("  • 猛犸坦克 (4tnk) - 最强坦克，双管炮+导弹")
    print("  • V2火箭发射车 (v2rl) - 远程火箭攻击")
    print("  • 特斯拉坦克 (ttnk) - 电击攻击")
    print("  • 震荡坦克 (qtnk) - 地震波攻击")
    print("\n建筑依赖关系:")
    print("  基础坦克 (轻型/重型):")
    print("    ✓ 建造厂 → 电厂 → 矿场 → 战车工厂")
    print("  \n高级坦克 (猛犸/特斯拉/震荡):")
    print("    ✓ 战车工厂 + 维修厂 + 科技中心")
    print("  \nV2火箭:")
    print("    ✓ 战车工厂 + 雷达站")
    print("\n游戏设置要求:")
    print("  • Skirmish 自由模式")
    print("  • 起始资金: $30000+ (建议$50000)")
    print("  • 科技等级: Unrestricted")
    print("  • AI: None")
    print("=" * 70)
    print()

def wait_for_building(api: GameAPI, building_name: str, timeout: int = 120, check_interval: int = 10) -> bool:
    """
    等待指定建筑建造完成
    
    Args:
        api: GameAPI实例
        building_name: 建筑名称（支持中文或英文代码）
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

def check_can_produce(api: GameAPI, unit_code: str) -> tuple:
    """
    检查是否可以生产指定单位
    
    Returns:
        tuple: (can_produce: bool, reason: str)
    """
    try:
        result = api.can_produce(unit_code)
        return (result, "可生产" if result else "不可生产")
    except Exception as e:
        return (False, f"检查失败: {e}")

def produce_tank(api: GameAPI, tank_name: str, tank_code: str, quantity: int) -> int:
    """
    生产指定数量的坦克
    
    Args:
        api: GameAPI实例
        tank_name: 坦克中文名称
        tank_code: 坦克代码
        quantity: 生产数量
    
    Returns:
        int: 成功生产的数量
    """
    print(f"\n--- {tank_name} (代码: {tank_code}, 目标: x{quantity}) ---")
    
    # 检查是否可以生产
    can_produce, reason = check_can_produce(api, tank_code)
    print(f"   可生产: {can_produce} ({reason})")
    
    if not can_produce:
        print(f"   [跳过] {tank_name} - {reason}")
        print(f"   提示: 检查前置建筑和科技等级")
        return 0
    
    success_count = 0
    for i in range(quantity):
        try:
            wait_id = api.produce(tank_code, 1, False)
            if wait_id:
                api.wait(wait_id, 90)  # 坦克生产时间较长
                print(f"   [{i+1}/{quantity}] ✓ 完成")
                success_count += 1
            else:
                print(f"   [{i+1}/{quantity}] ✗ 下单失败")
                time.sleep(2)
        except Exception as e:
            print(f"   [{i+1}/{quantity}] ✗ 错误: {e}")
            time.sleep(2)
    
    return success_count

def main():
    """主函数"""
    print_header()
    
    input("按回车开始...\n")
    
    print("=" * 70)
    print("[*] OpenRA 全坦克建造程序 - 开始执行")
    print("=" * 70)
    
    # 连接API
    api = GameAPI('localhost', 7445, 'zh')
    
    # 步骤1: 检查初始状态
    print("\n[步骤1] 检查游戏状态...")
    info = api.player_base_info_query()
    print(f"   资金: ${info.Cash}")
    print(f"   电力: {info.Power} / {info.PowerProvided}")
    
    if info.Cash < 20000:
        print("\n   [警告] 资金不足！建议至少$30000")
        response = input("   继续？(y/n): ")
        if response.lower() != 'y':
            return
    
    # 步骤2: 部署基地车
    print("\n[步骤2] 部署基地车...")
    try:
        api.deploy_mcv_and_wait(5)
        print("   ✓ 基地车已部署")
    except Exception as e:
        print(f"   [信息] {e}")
    
    time.sleep(3)
    
    # 步骤3: 建造5个电厂（坦克需要更多电力）
    print("\n[步骤3] 建造电厂系统...")
    target_power_plants = 5
    
    current_plants = api.query_actor(TargetsQueryParam(type=['电厂'], faction='自己'))
    current_count = len(current_plants) if current_plants else 0
    need_to_build = max(0, target_power_plants - current_count)
    
    print(f"   当前电厂: {current_count}个，目标: {target_power_plants}个")
    
    if need_to_build > 0:
        # 批量下单
        for i in range(need_to_build):
            try:
                api.produce("电厂", 1, True)
                print(f"   [下单] 电厂 #{i+1}")
                time.sleep(0.5)
            except Exception as e:
                print(f"   [错误] 电厂 #{i+1} 下单失败: {e}")
        
        # 等待至少有4个电厂完成
        print("\n   等待电厂建造...")
        for attempt in range(15):  # 等待2.5分钟
            time.sleep(10)
            plants = api.query_actor(TargetsQueryParam(type=['电厂'], faction='自己'))
            plant_count = len(plants) if plants else 0
            info = api.player_base_info_query()
            print(f"      第{attempt+1}轮: {plant_count}个电厂, 电力: {info.Power}/{info.PowerProvided}")
            
            if plant_count >= 4:
                print("   ✓ 电厂系统就绪")
                break
    else:
        print("   ✓ 电厂已足够")
    
    time.sleep(5)
    
    # 步骤4: 建造矿场
    print("\n[步骤4] 建造矿场...")
    existing_proc = api.query_actor(TargetsQueryParam(type=['矿场'], faction='自己'))
    if existing_proc and len(existing_proc) > 0:
        print("   ✓ 矿场已存在")
    else:
        try:
            api.produce("矿场", 1, True)
            print("   [下单] 矿场")
            wait_for_building(api, "矿场", timeout=120)
        except Exception as e:
            print(f"   [错误] {e}")
    
    time.sleep(3)
    
    # 步骤5: 建造战车工厂
    print("\n[步骤5] 建造战车工厂...")
    existing_weap = api.query_actor(TargetsQueryParam(type=['战车工厂', '车间'], faction='自己'))
    if existing_weap and len(existing_weap) > 0:
        print("   ✓ 战车工厂已存在")
    else:
        try:
            api.produce("战车工厂", 1, True)
            print("   [下单] 战车工厂")
            wait_for_building(api, "车间", timeout=120)
        except Exception as e:
            print(f"   [错误] {e}")
    
    time.sleep(3)
    
    # 步骤6: 建造雷达站（解锁V2）
    print("\n[步骤6] 建造雷达站...")
    existing_radar = api.query_actor(TargetsQueryParam(type=['雷达', '雷达站'], faction='自己'))
    if existing_radar and len(existing_radar) > 0:
        print("   ✓ 雷达站已存在")
    else:
        try:
            api.produce("雷达", 1, True)
            print("   [下单] 雷达站")
            wait_for_building(api, "雷达", timeout=120)
        except Exception as e:
            print(f"   [错误] {e}")
    
    time.sleep(3)
    
    # 步骤7: 建造维修厂（解锁重坦）
    print("\n[步骤7] 建造维修厂...")
    existing_fix = api.query_actor(TargetsQueryParam(type=['维修厂'], faction='自己'))
    if existing_fix and len(existing_fix) > 0:
        print("   ✓ 维修厂已存在")
    else:
        try:
            api.produce("维修厂", 1, True)
            print("   [下单] 维修厂")
            wait_for_building(api, "维修厂", timeout=120)
        except Exception as e:
            print(f"   [错误] {e}")
    
    time.sleep(3)
    
    # 步骤8: 建造科技中心（解锁猛犸坦克等高级单位）
    print("\n[步骤8] 建造科技中心（解锁高级坦克）...")
    existing_tech = api.query_actor(TargetsQueryParam(type=['科技中心'], faction='自己'))
    if existing_tech and len(existing_tech) > 0:
        print("   ✓ 科技中心已存在")
    else:
        try:
            api.produce("科技中心", 1, True)
            print("   [下单] 科技中心")
            success = wait_for_building(api, "科技中心", timeout=150)
            if not success:
                print("   [警告] 科技中心未完成，高级坦克无法生产")
        except Exception as e:
            print(f"   [错误] {e}")
    
    time.sleep(5)
    
    # 步骤9: 检查建筑状态
    print("\n[步骤9] 检查建筑状态...")
    info = api.player_base_info_query()
    print(f"   当前电力: {info.Power} / {info.PowerProvided}")
    print(f"   剩余资金: ${info.Cash}")
    
    all_buildings = api.query_actor(TargetsQueryParam(faction='自己'))
    building_types = set()
    for building in all_buildings:
        if building.type in ['建造厂', '电厂', '矿场', '战车工厂', '车间', '雷达', '雷达站', '维修厂', '科技中心']:
            building_types.add(building.type)
    
    print(f"   已建成建筑: {', '.join(sorted(building_types))}")
    
    # 检查关键建筑
    has_weap = '战车工厂' in building_types or '车间' in building_types
    has_radar = '雷达' in building_types or '雷达站' in building_types
    has_fix = '维修厂' in building_types
    has_tech = '科技中心' in building_types
    
    if not has_weap:
        print("\n   [错误] 缺少战车工厂！无法生产坦克")
        return
    
    print("\n   建筑系统状态:")
    print(f"     战车工厂: {'✓' if has_weap else '✗'}")
    print(f"     雷达站: {'✓' if has_radar else '✗'} (V2需要)")
    print(f"     维修厂: {'✓' if has_fix else '✗'} (重坦需要)")
    print(f"     科技中心: {'✓' if has_tech else '✗'} (猛犸/特斯拉/震荡需要)")
    
    # 步骤9.5: 诊断科技等级限制
    print("\n[步骤9.5] 诊断科技等级...")
    tank_test_list = [
        ("轻型坦克", "1tnk"),      # 基础坦克
        ("重型坦克", "3tnk"),      # 需要维修厂
        ("V2火箭", "v2rl"),        # 需要雷达
        ("猛犸坦克", "4tnk"),      # 需要科技中心
    ]
    
    available_count = 0
    for name, code in tank_test_list:
        can_produce, _ = check_can_produce(api, code)
        if can_produce:
            available_count += 1
            print(f"   ✓ {name}: 可生产")
        else:
            print(f"   ✗ {name}: 不可生产")
    
    if available_count < 2:
        print("\n   [警告] 检测到科技等级限制！")
        print("   大部分坦克无法生产")
        print("\n   解决方案:")
        print("   1. 按 ESC → Abandon Game")
        print("   2. 回到主菜单")
        print("   3. 选择: Singleplayer → Skirmish")
        print("   4. 在游戏设置中找到 'Tech Level' 选项")
        print("   5. 将其改为 'Unrestricted' (无限制)")
        print("   6. Starting Cash 建议设置为 $50000")
        print("   7. 开始游戏后重新运行此脚本")
        print("\n   是否继续尝试生产可用坦克？")
        response = input("   (y=继续/n=退出): ")
        if response.lower() != 'y':
            return
    else:
        print(f"\n   ✓ 科技等级检查通过 ({available_count}/4 可生产)")
    
    # 步骤10: 生产所有坦克
    print("\n" + "=" * 70)
    print("[步骤10] 开始生产所有坦克")
    print("=" * 70)
    
    # 定义所有坦克类型 (名称, 代码, 数量, 优先级)
    # 优先级: 1=基础坦克, 2=中级坦克, 3=高级坦克
    tank_list = [
        ("轻型坦克", "1tnk", 3, 1),          # 基础坦克
        ("重型坦克", "3tnk", 4, 2),          # 需要维修厂
        ("V2火箭发射车", "v2rl", 5, 2),      # 需要雷达
        ("猛犸坦克", "4tnk", 5, 3),          # 需要科技中心+维修厂
        ("特斯拉坦克", "ttnk", 1, 3),        # 需要科技中心
        ("震荡坦克", "qtnk", 1, 3),          # 需要科技中心
    ]
    
    # 按优先级排序（先生产基础坦克）
    tank_list.sort(key=lambda x: x[3])
    
    total_produced = 0
    total_attempted = sum(item[2] for item in tank_list)
    successful_types = []
    failed_types = []
    
    for tank_name, tank_code, quantity, priority in tank_list:
        count = produce_tank(api, tank_name, tank_code, quantity)
        total_produced += count
        
        if count > 0:
            successful_types.append(f"{tank_name} x{count}")
        else:
            failed_types.append(tank_name)
        
        # 每个坦克之间稍微等待
        time.sleep(2)
    
    # 最终报告
    print("\n" + "=" * 70)
    print("[完成] 最终报告")
    print("=" * 70)
    
    info = api.player_base_info_query()
    all_units = api.query_actor(TargetsQueryParam(faction='自己'))
    
    # 统计坦克数量
    tank_codes = ['1tnk', '3tnk', '4tnk', 'v2rl', 'ttnk', 'qtnk']
    tank_units = [u for u in all_units if u.type in tank_codes or 
                  u.type in ['轻型坦克', '重型坦克', '猛犸坦克', 'V2火箭发射车', '特斯拉坦克', '震荡坦克']]
    
    print(f"\n资源状态:")
    print(f"  剩余资金: ${info.Cash}")
    print(f"  电力: {info.Power} / {info.PowerProvided}")
    print(f"  总单位数: {len(all_units)}")
    print(f"  坦克数量: {len(tank_units)}")
    
    print(f"\n生产结果:")
    print(f"  成功生产: {total_produced} / {total_attempted} 单位")
    print(f"  完成度: {total_produced * 100 // total_attempted if total_attempted > 0 else 0}%")
    print(f"  成功类型: {len(successful_types)} / 6 种")
    
    if successful_types:
        print(f"\n✓ 成功生产:")
        for item in successful_types:
            print(f"    • {item}")
    
    if failed_types:
        print(f"\n✗ 未能生产:")
        for item in failed_types:
            print(f"    • {item}")
        print(f"\n失败原因可能:")
        if not has_fix:
            print(f"  - 缺少维修厂（重坦需要）")
        if not has_radar:
            print(f"  - 缺少雷达站（V2需要）")
        if not has_tech:
            print(f"  - 缺少科技中心（猛犸/特斯拉/震荡需要）")
        print(f"  - 电力不足")
        print(f"  - 资金不足")
        print(f"  - 科技等级限制")
    
    # 成功判断
    print("\n" + "=" * 70)
    if total_produced >= total_attempted:
        print("✓✓✓ 任务完成！所有坦克已生产 ✓✓✓")
    elif len(successful_types) >= 4:
        print("✓ 任务基本完成！大部分坦克已生产")
    elif len(successful_types) >= 2:
        print("⚠ 部分完成 - 可能受建筑或科技等级限制")
        print("\n提示: 请确保游戏设置中 Tech Level 为 Unrestricted")
    else:
        print("✗ 任务未达标")
    print("=" * 70)
    
    # 显示坦克详细列表
    if tank_units:
        print(f"\n当前所有坦克列表:")
        for i, tank in enumerate(tank_units, 1):
            print(f"  {i}. {tank.type} (ID:{tank.actor_id}) - "
                  f"位置:({tank.position.x},{tank.position.y}) - "
                  f"血量:{tank.hppercent}%")
    
    print("\n程序执行完成！")
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenRA 全空军建造程序
生产所有空中单位：运输直升机、雌鹿直升机、黑鹰直升机、长弓武装直升机、雅克战机、米格战机
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
    print("OpenRA 全空军建造程序")
    print("=" * 70)
    print("\n目标空中单位:")
    print("  • 运输直升机 (tran) - 运输部队")
    print("  • 雌鹿直升机 (hind) - 苏军武装直升机")
    print("  • 黑鹰直升机 (mh60) - 盟军武装直升机")
    print("  • 长弓武装直升机 (heli) - 高级武装直升机")
    print("  • 雅克战机 (yak) - 苏军攻击机")
    print("  • 米格战机 (mig) - 苏军战斗机")
    print("\n建筑依赖关系:")
    print("  建造厂 → 电厂 x4 → 矿场 → 雷达站 → 空军基地")
    print("\n游戏设置要求:")
    print("  • Skirmish 自由模式")
    print("  • 起始资金: $25000+ (建议$40000)")
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
        if building_name == "雷达":
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

def produce_aircraft(api: GameAPI, aircraft_name: str, aircraft_code: str, quantity: int) -> int:
    """
    生产指定数量的飞机
    
    Args:
        api: GameAPI实例
        aircraft_name: 飞机中文名称
        aircraft_code: 飞机代码
        quantity: 生产数量
    
    Returns:
        int: 成功生产的数量
    """
    print(f"\n--- {aircraft_name} (代码: {aircraft_code}, 目标: x{quantity}) ---")
    
    # 检查是否可以生产
    can_produce, reason = check_can_produce(api, aircraft_code)
    print(f"   可生产: {can_produce} ({reason})")
    
    if not can_produce:
        print(f"   [跳过] {aircraft_name} - {reason}")
        print(f"   提示: 检查是否有机场和科技等级")
        return 0
    
    success_count = 0
    for i in range(quantity):
        try:
            wait_id = api.produce(aircraft_code, 1, False)
            if wait_id:
                api.wait(wait_id, 60)  # 飞机生产时间
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
    print("[*] OpenRA 全空军建造程序 - 开始执行")
    print("=" * 70)
    
    # 连接API
    api = GameAPI('localhost', 7445, 'zh')
    
    # 步骤1: 检查初始状态
    print("\n[步骤1] 检查游戏状态...")
    info = api.player_base_info_query()
    print(f"   资金: ${info.Cash}")
    print(f"   电力: {info.Power} / {info.PowerProvided}")
    
    if info.Cash < 20000:
        print("\n   [警告] 资金不足！建议至少$25000")
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
    
    # 步骤3: 建造4个电厂
    print("\n[步骤3] 建造电厂系统...")
    target_power_plants = 4
    
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
        
        # 等待至少有3个电厂完成
        print("\n   等待电厂建造...")
        for attempt in range(12):  # 等待2分钟
            time.sleep(10)
            plants = api.query_actor(TargetsQueryParam(type=['电厂'], faction='自己'))
            plant_count = len(plants) if plants else 0
            info = api.player_base_info_query()
            print(f"      第{attempt+1}轮: {plant_count}个电厂, 电力: {info.Power}/{info.PowerProvided}")
            
            if plant_count >= 3:
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
    
    # 步骤5: 建造雷达站（空军基地的前置建筑）
    print("\n[步骤5] 建造雷达站...")
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
    
    # 步骤6: 建造空军基地（机场）
    print("\n[步骤6] 建造空军基地（机场）...")
    existing_airfield = api.query_actor(TargetsQueryParam(type=['机场', '空军基地', 'afld'], faction='自己'))
    if existing_airfield and len(existing_airfield) > 0:
        print("   ✓ 机场已存在")
    else:
        try:
            api.produce("机场", 1, True)
            print("   [下单] 空军基地")
            success = wait_for_building(api, "机场", timeout=150)
            if not success:
                print("   [错误] 机场未完成，无法生产飞机！")
                print("   请检查是否有足够空间放置机场")
                response = input("   是否继续？(y/n): ")
                if response.lower() != 'y':
                    return
        except Exception as e:
            print(f"   [错误] {e}")
    
    time.sleep(5)
    
    # 步骤7: 检查建筑状态
    print("\n[步骤7] 检查建筑状态...")
    info = api.player_base_info_query()
    print(f"   当前电力: {info.Power} / {info.PowerProvided}")
    print(f"   剩余资金: ${info.Cash}")
    
    all_buildings = api.query_actor(TargetsQueryParam(faction='自己'))
    building_types = set()
    for building in all_buildings:
        if building.type in ['建造厂', '电厂', '矿场', '雷达', '雷达站', '机场', '空军基地', 'afld']:
            building_types.add(building.type)
    
    print(f"   已建成建筑: {', '.join(sorted(building_types))}")
    
    # 检查关键建筑
    has_radar = '雷达' in building_types or '雷达站' in building_types
    has_airfield = '机场' in building_types or '空军基地' in building_types or 'afld' in building_types
    
    print("\n   建筑系统状态:")
    print(f"     雷达站: {'✓' if has_radar else '✗'}")
    print(f"     机场: {'✓' if has_airfield else '✗'}")
    
    if not has_airfield:
        print("\n   [错误] 缺少机场！无法生产飞机")
        print("   请检查机场是否建造成功")
        return
    
    # 步骤7.5: 诊断科技等级限制
    print("\n[步骤7.5] 诊断科技等级...")
    aircraft_test_list = [
        ("雅克战机", "yak"),          # 基础战机
        ("米格战机", "mig"),          # 基础战机
        ("运输直升机", "tran"),       # 运输机
        ("雌鹿直升机", "hind"),       # 武装直升机
    ]
    
    available_count = 0
    for name, code in aircraft_test_list:
        can_produce, _ = check_can_produce(api, code)
        if can_produce:
            available_count += 1
            print(f"   ✓ {name}: 可生产")
        else:
            print(f"   ✗ {name}: 不可生产")
    
    if available_count < 2:
        print("\n   [警告] 检测到科技等级限制！")
        print("   大部分飞机无法生产")
        print("\n   解决方案:")
        print("   1. 按 ESC → Abandon Game")
        print("   2. 回到主菜单")
        print("   3. 选择: Singleplayer → Skirmish")
        print("   4. 在游戏设置中找到 'Tech Level' 选项")
        print("   5. 将其改为 'Unrestricted' (无限制)")
        print("   6. Starting Cash 建议设置为 $40000")
        print("   7. 开始游戏后重新运行此脚本")
        print("\n   是否继续尝试生产可用飞机？")
        response = input("   (y=继续/n=退出): ")
        if response.lower() != 'y':
            return
    else:
        print(f"\n   ✓ 科技等级检查通过 ({available_count}/4 可生产)")
    
    # 步骤8: 生产所有飞机
    print("\n" + "=" * 70)
    print("[步骤8] 开始生产所有空中单位")
    print("=" * 70)
    
    # 定义所有飞机类型 (名称, 代码, 数量, 优先级)
    # 优先级: 1=基础飞机, 2=高级飞机
    aircraft_list = [
        ("雅克战机", "yak", 3, 1),              # 苏军攻击机
        ("米格战机", "mig", 2, 1),              # 苏军战斗机
        ("运输直升机", "tran", 2, 1),           # 运输直升机
        ("雌鹿直升机", "hind", 2, 2),           # 苏军武装直升机
        ("黑鹰直升机", "mh60", 2, 2),           # 盟军武装直升机
        ("长弓武装直升机", "heli", 2, 2),       # 高级武装直升机
    ]
    
    # 按优先级排序（先生产基础飞机）
    aircraft_list.sort(key=lambda x: x[3])
    
    total_produced = 0
    total_attempted = sum(item[2] for item in aircraft_list)
    successful_types = []
    failed_types = []
    
    for aircraft_name, aircraft_code, quantity, priority in aircraft_list:
        count = produce_aircraft(api, aircraft_name, aircraft_code, quantity)
        total_produced += count
        
        if count > 0:
            successful_types.append(f"{aircraft_name} x{count}")
        else:
            failed_types.append(aircraft_name)
        
        # 每个飞机之间稍微等待
        time.sleep(2)
    
    # 最终报告
    print("\n" + "=" * 70)
    print("[完成] 最终报告")
    print("=" * 70)
    
    info = api.player_base_info_query()
    all_units = api.query_actor(TargetsQueryParam(faction='自己'))
    
    # 统计飞机数量
    aircraft_codes = ['yak', 'mig', 'tran', 'hind', 'mh60', 'heli']
    aircraft_units = [u for u in all_units if u.type in aircraft_codes or 
                      u.type in ['雅克战机', '米格战机', '运输直升机', '雌鹿直升机', '黑鹰直升机', '长弓武装直升机']]
    
    print(f"\n资源状态:")
    print(f"  剩余资金: ${info.Cash}")
    print(f"  电力: {info.Power} / {info.PowerProvided}")
    print(f"  总单位数: {len(all_units)}")
    print(f"  飞机数量: {len(aircraft_units)}")
    
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
        if not has_airfield:
            print(f"  - 缺少机场")
        print(f"  - 电力不足")
        print(f"  - 资金不足")
        print(f"  - 科技等级限制")
    
    # 成功判断
    print("\n" + "=" * 70)
    if total_produced >= total_attempted:
        print("✓✓✓ 任务完成！所有飞机已生产 ✓✓✓")
    elif len(successful_types) >= 4:
        print("✓ 任务基本完成！大部分飞机已生产")
    elif len(successful_types) >= 2:
        print("⚠ 部分完成 - 可能受科技等级限制")
        print("\n提示: 请确保游戏设置中 Tech Level 为 Unrestricted")
    else:
        print("✗ 任务未达标")
    print("=" * 70)
    
    # 显示飞机详细列表
    if aircraft_units:
        print(f"\n当前所有飞机列表:")
        for i, aircraft in enumerate(aircraft_units, 1):
            print(f"  {i}. {aircraft.type} (ID:{aircraft.actor_id}) - "
                  f"位置:({aircraft.position.x},{aircraft.position.y}) - "
                  f"血量:{aircraft.hppercent}%")
    
    print("\n提示: 飞机可以使用以下命令:")
    print("  • api.move_actor() - 移动飞机")
    print("  • api.attack() - 攻击目标")
    print("  • 战机会自动返回机场补给")
    
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

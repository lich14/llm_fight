#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
固定防御模式 - 简化版
按顺序建造所有建筑和单位，然后自动防御
"""

import sys
import os
import time

# 添加库路径
current_dir = os.path.dirname(os.path.abspath(__file__))
library_path = os.path.join(current_dir, 'examples', 'mcp')
sys.path.insert(0, library_path)

from OpenRA_Copilot_Library.game_api import GameAPI
from OpenRA_Copilot_Library.models import TargetsQueryParam


def quick_check_enemies(api: GameAPI) -> bool:
    """快速检查是否有敌人"""
    try:
        enemies = api.query_actor(TargetsQueryParam(faction='敌人'))
        return enemies and len(enemies) > 0
    except:
        return False


def quick_counter_attack(api: GameAPI):
    """快速反击敌人"""
    try:
        enemies = api.query_actor(TargetsQueryParam(faction='敌人'))
        if not enemies or len(enemies) == 0:
            return
        
        print(f"\n⚠️  紧急！发现 {len(enemies)} 个敌人入侵！")
        
        # 获取所有战斗单位
        mine = api.query_actor(TargetsQueryParam(faction='自己'))
        combat_units = []
        
        exclude_types = {'建造厂', '电厂', '核电站', '矿场', '兵营', '战车工厂', 
                        '雷达', '维修厂', '科技中心', '机场', '采矿车',
                        '火焰塔', '特斯拉线圈', '防空导弹', '储存罐'}
        
        for unit in mine:
            if unit.type not in exclude_types:
                combat_units.append(unit)
        
        if len(combat_units) > 0:
            print(f"  → 紧急反击！派遣 {len(combat_units)} 个单位")
            
            attack_count = 0
            for i, unit in enumerate(combat_units[:50]):  # 只派前50个单位，避免太慢
                enemy = enemies[i % len(enemies)]
                try:
                    if api.attack_target(unit, enemy):
                        attack_count += 1
                except:
                    pass
            
            print(f"  ✓ {attack_count} 个单位已开始反击")
        else:
            print("  ⚠️  暂无战斗单位！")
    except Exception as e:
        print(f"  反击失败: {e}")


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
    
    # 等待建造
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
            print("  → 自动建造核电站...")
            try:
                api.produce("核电站", 1, True)
                print("  ✓ 核电站已下单")
                time.sleep(10)
                
                # 再次检查电力
                new_info = api.player_base_info_query()
                print(f"  电力状态: {new_info.Power}/{new_info.PowerProvided}")
            except Exception as e:
                print(f"  ✗ 建造核电站失败: {e}")
        else:
            print(f"  ⚠️  资金不足，无法建造核电站 (需要$250，当前${info.Cash})")
    else:
        print(f"✓ 电力充足: {info.Power}/{info.PowerProvided}")


def produce_unit(api: GameAPI, name: str, code: str, count: int) -> int:
    """生产单位"""
    print(f"\n[生产] {name} x{count}")
    
    success = 0
    for i in range(count):
        try:
            api.produce(code, 1, False)
            if (i + 1) % 10 == 0:
                print(f"  已生产 {i+1}/{count}")
            success += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"  失败: {e}")
            break
    
    print(f"  ✓ 完成 {success}/{count}")
    return success


def auto_defense(api: GameAPI):
    """自动防御"""
    print("\n=== 进入自动防御模式 ===")
    print("监控敌人并自动反击...\n")
    
    check_count = 0
    
    while True:
        try:
            # 每10次循环检查一次电力
            check_count += 1
            if check_count >= 10:
                check_and_build_power(api)
                check_count = 0
            
            # 查询敌人
            enemies = api.query_actor(TargetsQueryParam(faction='敌人'))
            
            if enemies and len(enemies) > 0:
                print(f"\n⚠️  发现 {len(enemies)} 个敌人！")
                
                # 获取我方战斗单位
                mine = api.query_actor(TargetsQueryParam(faction='自己'))
                combat_units = []
                
                # 排除建筑和采矿车
                exclude_types = {'建造厂', '电厂', '核电站', '矿场', '兵营', '战车工厂', 
                                '雷达', '维修厂', '科技中心', '机场', '采矿车',
                                '火焰塔', '特斯拉线圈', '防空导弹', '储存罐'}
                
                for unit in mine:
                    if unit.type not in exclude_types:
                        combat_units.append(unit)
                
                print(f"  派遣 {len(combat_units)} 个单位反击")
                
                # 攻击敌人 - 使用 attack_target 方法
                attack_success = 0
                for i, unit in enumerate(combat_units):
                    enemy = enemies[i % len(enemies)]
                    try:
                        # 使用 attack_target 方法，传入 Actor 对象
                        result = api.attack_target(unit, enemy)
                        if result:
                            attack_success += 1
                    except Exception as e:
                        # 静默失败
                        pass
                
                if attack_success > 0:
                    print(f"  ✓ {attack_success} 个单位成功下达攻击命令")
                else:
                    print(f"  ⚠️  攻击命令未成功执行")
            else:
                print(".", end="", flush=True)
            
            time.sleep(3)
            
        except KeyboardInterrupt:
            print("\n\n退出防御模式")
            break
        except Exception as e:
            print(f"\n错误: {e}")
            time.sleep(3)


def main():
    print("=" * 60)
    print("固定防御模式 - 简化版")
    print("=" * 60)
    print("\n将建造:")
    print("  建筑: 电厂x2, 矿场x5, 兵营, 战车工厂x2")
    print("       雷达, 维修厂, 核电站, 科技中心, 机场")
    print("       火焰塔x2, 特斯拉线圈x2, 防空导弹x2")
    print("\n  单位: 步兵x50, 火箭兵x50")
    print("       重型坦克x10, 猛犸坦克x20, 防空车x10")
    print("       V2火箭x5, 米格战机x5")
    print("\n要求:")
    print("  - 起始资金 $20000+")
    print("  - Tech Level: Unrestricted")
    print("\n按回车开始...")
    input()
    
    api = GameAPI('localhost', 7445, 'zh')
    
    # 检查资金
    info = api.player_base_info_query()
    print(f"\n当前资金: ${info.Cash}")
    
    if info.Cash < 30000:
        print("⚠️  资金不足！建议至少 $50000")
        if input("继续? (y/n): ").lower() != 'y':
            return
    
    # 部署MCV
    print("\n[步骤1] 部署建造厂...")
    try:
        api.deploy_mcv_and_wait(5)
        print("✓ 建造厂就绪")
    except Exception as e:
        print(f"提示: {e}")
    
    time.sleep(3)
    
    # 快速建造基础设施 - 优先战车工厂
    print("\n" + "=" * 60)
    print("快速启动: 优先建造战车工厂和坦克！")
    print("=" * 60)
    
    print("\n[阶段1] 最小基础设施")
    build_structure(api, "电厂", "电厂", 2)
    quick_check_enemies(api) and quick_counter_attack(api)
    
    build_structure(api, "矿场", "矿场", 2)  # 先建2个矿场
    quick_check_enemies(api) and quick_counter_attack(api)
    
    build_structure(api, "战车工厂", "战车工厂", 1)
    quick_check_enemies(api) and quick_counter_attack(api)
    
    print("\n[阶段2] 紧急生产坦克！")
    produce_unit(api, "重型坦克(应急)", "3tnk", 5)
    quick_check_enemies(api) and quick_counter_attack(api)
    
    # 继续建造科技建筑
    print("\n[阶段3] 解锁高级科技")
    build_structure(api, "雷达", "雷达", 1)
    quick_check_enemies(api) and quick_counter_attack(api)
    
    build_structure(api, "维修厂", "维修厂", 1)
    quick_check_enemies(api) and quick_counter_attack(api)
    
    build_structure(api, "科技中心", "科技中心", 1)
    quick_check_enemies(api) and quick_counter_attack(api)
    
    # 大量生产猛犸坦克
    print("\n[阶段4] 大量生产猛犸坦克！")
    produce_unit(api, "猛犸坦克", "4tnk", 5)
    
    # 边生产边检查敌人
    for i in range(20):
        quick_check_enemies(api) and quick_counter_attack(api)
        time.sleep(2)
    
    # 补充其他建筑
    print("\n[阶段5] 补充其他建筑和单位")
    build_structure(api, "矿场(补充)", "矿场", 3)  # 再建3个矿场，总共5个
    quick_check_enemies(api) and quick_counter_attack(api)
    
    build_structure(api, "战车工厂(补充)", "战车工厂", 1)
    quick_check_enemies(api) and quick_counter_attack(api)
    
    build_structure(api, "兵营", "兵营", 1)
    quick_check_enemies(api) and quick_counter_attack(api)
    
    build_structure(api, "机场", "机场", 1)
    quick_check_enemies(api) and quick_counter_attack(api)
    
    build_structure(api, "核电站", "核电站", 1)
    quick_check_enemies(api) and quick_counter_attack(api)
    
    # 建造防御
    print("\n[阶段6] 建造防御建筑")
    check_and_build_power(api)
    
    build_structure(api, "火焰塔", "火焰塔", 2)
    quick_check_enemies(api) and quick_counter_attack(api)
    
    build_structure(api, "特斯拉线圈", "特斯拉线圈", 2)
    quick_check_enemies(api) and quick_counter_attack(api)
    
    build_structure(api, "防空导弹", "防空导弹", 2)
    quick_check_enemies(api) and quick_counter_attack(api)
    
    print("\n✓ 防御建筑建造完成")
    time.sleep(5)
    
    # 补充其他单位
    print("\n[阶段7] 补充其他战斗单位")
    produce_unit(api, "步兵", "步兵", 10)
    produce_unit(api, "火箭兵", "火箭兵", 10)
    produce_unit(api, "防空车", "ftrk", 5)
    produce_unit(api, "V2火箭发射车", "v2rl", 5)
    produce_unit(api, "米格战斗机", "mig", 5)
    
    print("\n✓ 所有单位生产完成")
    
    # 阶段4: 自动防御
    print("\n" + "=" * 60)
    print("阶段4: 自动防御")
    print("=" * 60)
    
    auto_defense(api)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()

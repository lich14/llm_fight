#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
相机移动接口测试程序
测试接口：move_camera_to, move_camera_by_location, move_camera_by_direction
"""

import os
import sys
import time

# 添加库路径
current_dir = os.path.dirname(os.path.abspath(__file__))
library_path = os.path.join(current_dir, 'examples', 'mcp')
sys.path.insert(0, library_path)

from OpenRA_Copilot_Library.game_api import GameAPI
from OpenRA_Copilot_Library.models import TargetsQueryParam, Location

def print_header():
    """打印测试标题"""
    print("\n" + "=" * 80)
    print(" " * 28 + "相机移动接口测试")
    print("=" * 80)
    print("\n测试接口:")
    print("  • api.move_camera_to(actor) - 移动相机到指定Actor位置")
    print("  • api.move_camera_by_location(location) - 移动相机到指定坐标")
    print("  • api.move_camera_by_direction(direction, distance) - 向某方向移动相机")
    print("=" * 80 + "\n")


def get_current_camera_position(api: GameAPI) -> Location:
    """获取当前相机位置（屏幕中心）"""
    try:
        screen_info = api.screen_info_query()
        center_x = (screen_info.ScreenMin.x + screen_info.ScreenMax.x) // 2
        center_y = (screen_info.ScreenMin.y + screen_info.ScreenMax.y) // 2
        return Location(center_x, center_y)
    except Exception as e:
        print(f"⚠️  获取相机位置失败: {e}")
        return None


def show_camera_info(api: GameAPI, prefix=""):
    """显示当前相机信息"""
    try:
        screen_info = api.screen_info_query()
        center = get_current_camera_position(api)
        
        print(f"{prefix}相机信息:")
        print(f"  屏幕范围: ({screen_info.ScreenMin.x}, {screen_info.ScreenMin.y}) → "
              f"({screen_info.ScreenMax.x}, {screen_info.ScreenMax.y})")
        if center:
            print(f"  中心位置: ({center.x}, {center.y})")
        
        # 显示鼠标位置
        if screen_info.IsMouseOnScreen:
            print(f"  鼠标位置: ({screen_info.MousePosition.x}, {screen_info.MousePosition.y})")
        else:
            print(f"  鼠标: 不在屏幕上")
            
    except Exception as e:
        print(f"{prefix}⚠️  无法获取相机信息: {e}")


def test_move_camera_to_actor(api: GameAPI):
    """测试1: 移动相机到Actor位置"""
    print("\n" + "=" * 80)
    print("[测试1] 移动相机到Actor位置 - move_camera_to()")
    print("=" * 80)
    
    try:
        # 查找一些单位和建筑
        print("\n查找可用的Actor...")
        
        # 优先查找建造厂
        factories = api.query_actor(TargetsQueryParam(type=['建造厂', 'fact'], faction='自己'))
        if factories:
            print(f"找到建造厂 (ID: {factories[0].actor_id})")
            
            print("\n移动相机前:")
            show_camera_info(api, "  ")
            
            print(f"\n移动相机到建造厂...")
            api.move_camera_to(factories[0])
            time.sleep(1)
            
            print("\n移动相机后:")
            show_camera_info(api, "  ")
            print("✓ 相机已移动到建造厂位置")
            return True
        
        # 查找基地车
        mcv = api.query_actor(TargetsQueryParam(type=['mcv'], faction='自己'))
        if mcv:
            print(f"找到基地车 (ID: {mcv[0].actor_id})")
            
            print("\n移动相机前:")
            show_camera_info(api, "  ")
            
            print(f"\n移动相机到基地车...")
            api.move_camera_to(mcv[0])
            time.sleep(1)
            
            print("\n移动相机后:")
            show_camera_info(api, "  ")
            print("✓ 相机已移动到基地车位置")
            return True
        
        # 查找任意自己的单位
        my_units = api.query_actor(TargetsQueryParam(faction='自己'))
        if my_units:
            unit = my_units[0]
            print(f"找到单位: {unit.type} (ID: {unit.actor_id})")
            
            print("\n移动相机前:")
            show_camera_info(api, "  ")
            
            print(f"\n移动相机到 {unit.type}...")
            api.move_camera_to(unit)
            time.sleep(1)
            
            print("\n移动相机后:")
            show_camera_info(api, "  ")
            print(f"✓ 相机已移动到 {unit.type} 位置")
            return True
        
        print("⚠️  未找到任何可用的Actor")
        return False
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_move_camera_by_location(api: GameAPI):
    """测试2: 移动相机到指定坐标"""
    print("\n" + "=" * 80)
    print("[测试2] 移动相机到指定坐标 - move_camera_by_location()")
    print("=" * 80)
    
    try:
        # 获取地图信息
        print("\n获取地图信息...")
        map_info = api.map_query()
        print(f"地图大小: {map_info.MapWidth} x {map_info.MapHeight}")
        
        # 测试移动到地图中心
        center_x = map_info.MapWidth // 2
        center_y = map_info.MapHeight // 2
        center_loc = Location(center_x, center_y)
        
        print(f"\n[2.1] 移动到地图中心 ({center_x}, {center_y})")
        print("\n移动前:")
        show_camera_info(api, "  ")
        
        api.move_camera_by_location(center_loc)
        time.sleep(1)
        
        print("\n移动后:")
        show_camera_info(api, "  ")
        print("✓ 相机已移动到地图中心")
        
        time.sleep(1)
        
        # 测试移动到地图左上角
        print(f"\n[2.2] 移动到地图左上角 (10, 10)")
        top_left = Location(10, 10)
        
        api.move_camera_by_location(top_left)
        time.sleep(1)
        
        print("\n移动后:")
        show_camera_info(api, "  ")
        print("✓ 相机已移动到左上角")
        
        time.sleep(1)
        
        # 测试移动到地图右下角
        bottom_right_x = map_info.MapWidth - 10
        bottom_right_y = map_info.MapHeight - 10
        print(f"\n[2.3] 移动到地图右下角 ({bottom_right_x}, {bottom_right_y})")
        bottom_right = Location(bottom_right_x, bottom_right_y)
        
        api.move_camera_by_location(bottom_right)
        time.sleep(1)
        
        print("\n移动后:")
        show_camera_info(api, "  ")
        print("✓ 相机已移动到右下角")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_move_camera_by_direction(api: GameAPI):
    """测试3: 向指定方向移动相机"""
    print("\n" + "=" * 80)
    print("[测试3] 向指定方向移动相机 - move_camera_by_direction()")
    print("=" * 80)
    
    try:
        # 先移动到地图中心作为起点
        print("\n准备: 移动到地图中心作为起点")
        map_info = api.map_query()
        center = Location(map_info.MapWidth // 2, map_info.MapHeight // 2)
        api.move_camera_by_location(center)
        time.sleep(1)
        
        print("\n起始位置:")
        show_camera_info(api, "  ")
        
        # 测试各个方向
        directions = [
            ("北", 10),
            ("东", 10),
            ("南", 10),
            ("西", 10),
            ("东北", 15),
            ("东南", 15),
            ("西南", 15),
            ("西北", 15)
        ]
        
        for i, (direction, distance) in enumerate(directions, 1):
            print(f"\n[3.{i}] 向{direction}移动 {distance} 格")
            
            before = get_current_camera_position(api)
            
            api.move_camera_by_direction(direction, distance)
            time.sleep(0.8)
            
            after = get_current_camera_position(api)
            
            if before and after:
                dx = after.x - before.x
                dy = after.y - before.y
                actual_dist = (dx**2 + dy**2)**0.5
                print(f"  位移: ({dx:+d}, {dy:+d}), 距离: {actual_dist:.1f}")
                print(f"  新位置: ({after.x}, {after.y})")
            
            print(f"✓ 已向{direction}移动")
            
            # 每次移动后返回中心
            if i < len(directions):
                api.move_camera_by_location(center)
                time.sleep(0.5)
        
        print("\n✓ 所有方向测试完成")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_camera_tracking(api: GameAPI):
    """测试4: 相机跟踪移动单位（综合测试）"""
    print("\n" + "=" * 80)
    print("[测试4] 相机跟踪移动单位（综合测试）")
    print("=" * 80)
    
    try:
        # 查找一个可移动的单位
        print("\n查找可移动的单位...")
        units = api.query_actor(TargetsQueryParam(type=['e1', '步兵'], faction='自己'))
        
        if not units:
            print("⚠️  未找到步兵，尝试查找任意单位...")
            units = api.query_actor(TargetsQueryParam(faction='自己'))
        
        if not units:
            print("⚠️  未找到可用单位，跳过此测试")
            return False
        
        unit = units[0]
        print(f"找到单位: {unit.type} (ID: {unit.actor_id})")
        print(f"当前位置: ({unit.position.x}, {unit.position.y})")
        
        # 移动相机到单位
        print("\n移动相机到单位位置...")
        api.move_camera_to(unit)
        time.sleep(1)
        
        # 让单位移动
        target = Location(unit.position.x + 10, unit.position.y + 10)
        print(f"\n让单位移动到 ({target.x}, {target.y})...")
        api.move_units_by_location([unit], target)
        
        # 跟踪单位移动
        print("\n开始跟踪单位移动（5秒）...")
        start_time = time.time()
        last_update = 0
        
        while time.time() - start_time < 5:
            if time.time() - last_update >= 1:
                # 更新单位位置
                api.update_actor(unit)
                
                # 相机跟随
                api.move_camera_to(unit)
                
                print(f"  单位位置: ({unit.position.x}, {unit.position.y})")
                last_update = time.time()
            
            time.sleep(0.1)
        
        print("✓ 相机跟踪测试完成")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


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
    
    # 显示初始相机位置
    print("=" * 80)
    print("[初始状态] 当前相机位置")
    print("=" * 80)
    show_camera_info(api, "\n")
    
    input("\n按回车开始测试...")
    
    # 执行测试
    results = []
    
    # 测试1: 移动到Actor
    results.append(("移动相机到Actor", test_move_camera_to_actor(api)))
    time.sleep(2)
    
    # 测试2: 移动到坐标
    results.append(("移动相机到坐标", test_move_camera_by_location(api)))
    time.sleep(2)
    
    # 测试3: 按方向移动
    results.append(("按方向移动相机", test_move_camera_by_direction(api)))
    time.sleep(2)
    
    # 测试4: 相机跟踪
    results.append(("相机跟踪单位", test_camera_tracking(api)))
    
    # 打印测试总结
    print("\n\n" + "=" * 80)
    print(" " * 32 + "测试总结")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n通过: {passed}/{total}")
    print("\n详细结果:")
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status}: {name}")
    
    print("\n" + "=" * 80)
    print(f"测试完成率: {passed/total*100:.1f}%")
    print("=" * 80)
    
    print("\n测试的API接口:")
    print("  ✓ api.move_camera_to(actor) - 跟随Actor")
    print("  ✓ api.move_camera_by_location(location) - 移动到坐标")
    print("  ✓ api.move_camera_by_direction(direction, distance) - 方向移动")
    print("  ✓ api.screen_info_query() - 获取屏幕信息")
    
    input("\n按回车退出...")


if __name__ == "__main__":
    main()

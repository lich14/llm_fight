#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单的基地车移动测试

快速测试move_mcv_to_location函数
"""

import sys
import time
from pathlib import Path

# 添加库路径
lib_path = Path(__file__).parent / "examples" / "mcp"
sys.path.insert(0, str(lib_path))

from OpenRA_Copilot_Library.game_api import GameAPI
from OpenRA_Copilot_Library.models import Location, TargetsQueryParam


def move_mcv_to_coords(api, target_x, target_y, auto_deploy=False, max_wait_time=60.0, pack_wait=3.0):
    """封装函数：将基地车或建造厂移动到指定坐标。

    Args:
        api: GameAPI 实例
        target_x, target_y: 目标坐标
        auto_deploy: 到达后是否自动展开
        max_wait_time: 移动超时时间
        pack_wait: 打包等待时间（如果需要先打包建造厂）

    Returns:
        bool: True 表示移动成功，False 表示失败（或抛出异常）
    """
    print("\n[4] 开始移动...")
    print(f"   目标坐标: ({target_x}, {target_y})")
    try:
        # 查找基地车或建造厂
        mcv_list = api.query_actor(TargetsQueryParam(type=['mcv'], faction='自己'))
        construction_list = api.query_actor(TargetsQueryParam(type=['建造厂', 'fact'], faction='自己'))

        if not mcv_list and not construction_list:
            raise RuntimeError("❌ 未找到基地车或建造厂")

        use_pack = False
        if mcv_list:
            print("✓ 使用基地车进行移动 (未展开)")
            use_pack = False
        else:
            print("✓ 使用建造厂，先打包为基地车再移动")
            use_pack = True

        target = Location(target_x, target_y)

        if use_pack:
            success = api.pack_and_move_construction_yard(
                location=target,
                max_wait_time=max_wait_time,
                auto_deploy=auto_deploy,
                pack_wait=pack_wait,
            )
        else:
            success = api.move_mcv_to_location(
                location=target,
                max_wait_time=max_wait_time,
                auto_deploy=auto_deploy,
            )

        return bool(success)

    except Exception:
        raise



def main():
    print("="*60)
    print("基地车移动功能 - 快速测试")
    print("="*60)
    
    # 连接游戏
    print("\n[1] 连接到OpenRA游戏...")
    try:
        api = GameAPI(host="localhost", port=7445)
        print("✓ 连接成功")
    except Exception as e:
        print(f"❌ 连接失败！{e}")
        print("   请确保游戏正在运行")
        return
    
    # 查找基地车
    print("\n[2] 查找基地车或建造厂...")
    mcv_list = api.query_actor(TargetsQueryParam(type=['mcv'], faction='自己'))
    construction_list = api.query_actor(TargetsQueryParam(type=['建造厂', 'fact'], faction='自己'))
    
    if not mcv_list and not construction_list:
        print("❌ 未找到基地车或建造厂")
        print("   可能原因：")
        print("   - 不在自由模式/遭遇战模式")
        print("   - 基地已被摧毁")
        return
    
    # 确定使用哪个流程
    if mcv_list:
        mcv = mcv_list[0]
        print(f"✓ 找到基地车（未展开）")
        print(f"   当前位置: ({mcv.position.x}, {mcv.position.y})")
        use_pack_function = False
    else:
        cy = construction_list[0]
        print(f"✓ 找到建造厂（已展开）")
        print(f"   当前位置: ({cy.position.x}, {cy.position.y})")
        print(f"   将会先打包成基地车再移动")
        use_pack_function = True
        # 为了计算距离，使用建造厂位置
        mcv = cy
    
    # 设置目标位置（默认行为：在当前位置基础上偏移固定距离）
    print("\n[3] 设置移动目标...")
    # 查询地图大小
    try:
        map_info = api.map_query()
        print(f"   地图大小: {map_info.MapWidth} × {map_info.MapHeight}")
    except Exception:
        print("   无法获取地图信息，使用默认安全距离")
        map_info = None

    # 计算安全的目标位置（相对移动，确保不超出边界）
    move_distance = 10  # 使用更短的移动距离
    target_x = mcv.position.x + move_distance
    target_y = mcv.position.y + move_distance

    # 如果有地图信息，检查边界并修正
    if map_info:
        max_x = map_info.MapWidth - 5
        max_y = map_info.MapHeight - 5
        if target_x >= max_x:
            target_x = mcv.position.x - move_distance
            print(f"   ⚠️  X坐标超出边界，改为向左移动")
        if target_y >= max_y:
            target_y = mcv.position.y - move_distance
            print(f"   ⚠️  Y坐标超出边界，改为向上移动")

    # 调用封装的函数（以坐标为参数）
    try:
        success = move_mcv_to_coords(api, target_x, target_y, auto_deploy=False)
    except Exception as e:
        print(f"\n❌ 出错: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 成功反馈由封装函数负责打印/抛错
    if success:
        print("\n" + "="*60)
        print("✓ 测试成功！基地车已到达目标位置")
        print("="*60)
        # 询问是否展开
        print("\n是否展开基地车？(y/n): ", end='')
        choice = input().strip().lower()
        if choice == 'y':
            print("\n[5] 展开基地车...")
            mcv_updated = api.query_actor(TargetsQueryParam(type=['mcv'], faction='自己'))
            if mcv_updated:
                api.deploy_units(mcv_updated)
                time.sleep(2)
                print("✓ 基地车已展开")
                # 验证建造厂
                construction = api.query_actor(TargetsQueryParam(type=['建造厂'], faction='自己'))
                if construction:
                    print(f"✓ 建造厂位置: ({construction[0].position.x}, {construction[0].position.y})")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")

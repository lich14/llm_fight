#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
建造与生产接口测试程序
测试接口：produce、place_building、manage_production
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
    print(" " * 25 + "建造与生产接口测试")
    print("=" * 80)
    print("\n测试接口:")
    print("  • api.produce(unit_type, quantity, auto_place) - 开始生产")
    print("  • api.place_building(queue_type, location) - 放置建筑")
    print("  • api.manage_production(queue_type, action) - 管理生产队列")
    print("  • api.query_production_queue(queue_type) - 查询队列状态")
    print("=" * 80 + "\n")


def setup_base_if_needed(api: GameAPI) -> bool:
    """如果没有建造厂，则自动展开基地车并建造基础设施"""
    print("\n[准备] 检查基地状态...")
    
    # 检查是否有建造厂
    factories = api.query_actor(TargetsQueryParam(type=['建造厂', 'fact'], faction='自己'))
    
    if factories:
        print("✓ 建造厂已存在")
        return True
    
    print("⚠️  未找到建造厂，尝试展开基地车...")
    
    # 查找基地车
    mcv = api.query_actor(TargetsQueryParam(type=['mcv'], faction='自己'))
    
    if not mcv:
        print("✗ 未找到基地车！请在游戏中选择有MCV的地图")
        return False
    
    print(f"找到基地车 (ID: {mcv[0].actor_id})")
    print("展开基地车...")
    
    api.deploy_units(mcv)
    print("等待建造厂建造完成...")
    time.sleep(3)
    
    # 验证建造厂
    factories = api.query_actor(TargetsQueryParam(type=['建造厂', 'fact'], faction='自己'))
    
    if factories:
        print("✓ 建造厂已就绪")
        return True
    else:
        print("✗ 建造厂建造失败")
        return False


def test_produce_building(api: GameAPI):
    """测试1: 开始生产建筑（不自动放置）"""
    print("\n" + "=" * 80)
    print("[测试1] 开始生产建筑 - produce()")
    print("=" * 80)
    
    try:
        print("\n生产电厂（不自动放置）...")
        wait_id = api.produce('电厂', 1, False)
        
        if wait_id:
            print(f"✓ 电厂生产已下单 (WaitID: {wait_id})")
        else:
            print("⚠️  生产命令返回 None")
        
        time.sleep(1)
        
        # 查询建筑队列
        queue = api.query_production_queue('Building')
        items = queue.get('queue_items', [])
        
        print(f"\n建筑队列状态:")
        print(f"  队列项目数: {len(items)}")
        print(f"  有就绪项目: {queue.get('has_ready_item', False)}")
        
        if items:
            item = items[0]
            name = item.get('chineseName', item.get('name', '未知'))
            progress = item.get('progress_percent', 0)
            status = item.get('status', 'unknown')
            
            print(f"\n第一个项目详情:")
            print(f"  名称: {name}")
            print(f"  进度: {progress:.1f}%")
            print(f"  状态: {status}")
            print(f"  是否完成: {item.get('done', False)}")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_wait_and_place(api: GameAPI):
    """测试2: 等待建筑完成并手动放置"""
    print("\n" + "=" * 80)
    print("[测试2] 等待建筑完成并放置 - place_building()")
    print("=" * 80)
    
    try:
        print("\n等待电厂建造完成...")
        
        max_wait = 30
        elapsed = 0
        
        while elapsed < max_wait:
            queue = api.query_production_queue('Building')
            items = queue.get('queue_items', [])
            has_ready = queue.get('has_ready_item', False)
            
            if items and items[0].get('done', False):
                print(f"✓ 电厂建造完成！(耗时: {elapsed}秒)")
                break
            
            if has_ready:
                print(f"✓ 有就绪项目！(耗时: {elapsed}秒)")
                break
            
            time.sleep(1)
            elapsed += 1
            
            if elapsed % 5 == 0:
                progress = items[0].get('progress_percent', 0) if items else 0
                print(f"  建造中... {progress:.1f}% ({elapsed}/{max_wait}秒)")
        
        if elapsed >= max_wait:
            print("⚠️  等待超时，但继续测试放置功能")
        
        # 获取建造厂位置作为参考
        factories = api.query_actor(TargetsQueryParam(type=['建造厂', 'fact'], faction='自己'))
        
        if factories:
            factory_pos = factories[0].position
            # 在建造厂旁边放置（向右偏移）
            placement_pos = Location(factory_pos.x + 5, factory_pos.y)
            
            print(f"\n尝试放置电厂到位置 ({placement_pos.x}, {placement_pos.y})...")
            api.place_building('Building', placement_pos)
            print("✓ 放置命令已发送")
            
            time.sleep(2)
            
            # 验证电厂是否放置成功
            power_plants = api.query_actor(TargetsQueryParam(type=['电厂', 'powr'], faction='自己'))
            print(f"✓ 当前电厂数量: {len(power_plants)}")
            
        else:
            print("⚠️  找不到建造厂，使用自动位置放置")
            api.place_building('Building')
            print("✓ 自动放置命令已发送")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_manage_production(api: GameAPI):
    """测试3: 管理生产队列（暂停、恢复）"""
    print("\n" + "=" * 80)
    print("[测试3] 管理生产队列 - manage_production()")
    print("=" * 80)
    
    try:
        # 先生产一些步兵
        print("\n准备: 生产5个步兵...")
        
        # 确保有兵营
        barracks = api.query_actor(TargetsQueryParam(type=['兵营', 'barr'], faction='自己'))
        if not barracks:
            print("正在建造兵营...")
            api.ensure_can_build_wait('兵营')
            time.sleep(2)
        
        api.produce('e1', 5, False)
        print("✓ 步兵生产已下单")
        time.sleep(1)
        
        # 查询初始队列
        queue = api.query_production_queue('Infantry')
        items = queue.get('queue_items', [])
        print(f"\n初始队列: {len(items)} 个项目")
        
        # 测试暂停
        print("\n[3.1] 测试暂停 (pause)")
        api.manage_production('Infantry', 'pause')
        print("✓ 暂停命令已发送")
        time.sleep(1)
        
        queue = api.query_production_queue('Infantry')
        items = queue.get('queue_items', [])
        if items and items[0].get('paused', False):
            print("✓ 验证成功: 队列已暂停")
        else:
            print("⚠️  暂停状态未确认")
        
        # 测试恢复
        print("\n[3.2] 测试恢复 (resume)")
        api.manage_production('Infantry', 'resume')
        print("✓ 恢复命令已发送")
        time.sleep(1)
        
        queue = api.query_production_queue('Infantry')
        items = queue.get('queue_items', [])
        if items and not items[0].get('paused', False):
            print("✓ 验证成功: 队列已恢复")
        else:
            print("⚠️  恢复状态未确认")
        
        # 测试取消（只能取消第一个）
        print("\n[3.3] 测试取消 (cancel)")
        queue = api.query_production_queue('Infantry')
        items_before = queue.get('queue_items', [])
        count_before = len(items_before)
        
        if count_before > 0:
            print(f"取消第一个项目（当前队列: {count_before} 个）...")
            api.manage_production('Infantry', 'cancel')
            print("✓ 取消命令已发送")
            time.sleep(1)
            
            queue = api.query_production_queue('Infantry')
            items_after = queue.get('queue_items', [])
            count_after = len(items_after)
            
            print(f"✓ 队列项目: {count_before} → {count_after}")
        else:
            print("⚠️  队列为空，跳过取消测试")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_auto_placement(api: GameAPI):
    """测试4: 自动放置建筑"""
    print("\n" + "=" * 80)
    print("[测试4] 自动放置建筑")
    print("=" * 80)
    
    try:
        print("\n生产电厂（自动放置模式）...")
        wait_id = api.produce('电厂', 1, True)
        
        if wait_id:
            print(f"✓ 电厂已下单 (WaitID: {wait_id}, 自动放置: True)")
            print("提示: 建筑完成后会自动放置到合适位置")
            
            print("\n等待建筑自动放置...")
            time.sleep(5)
            
            power_plants = api.query_actor(TargetsQueryParam(type=['电厂', 'powr'], faction='自己'))
            print(f"✓ 当前电厂数量: {len(power_plants)}")
            
            return True
        else:
            print("⚠️  生产命令返回 None")
            return False
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_query_all_queues(api: GameAPI):
    """测试5: 查询所有队列类型"""
    print("\n" + "=" * 80)
    print("[测试5] 查询所有生产队列")
    print("=" * 80)
    
    queue_types = ['Building', 'Defense', 'Infantry', 'Vehicle', 'Aircraft', 'Naval']
    
    print("\n所有队列状态:")
    for qtype in queue_types:
        try:
            queue = api.query_production_queue(qtype)
            items = queue.get('queue_items', [])
            has_ready = queue.get('has_ready_item', False)
            
            if items:
                first_item = items[0]
                name = first_item.get('chineseName', first_item.get('name', '?'))
                status = first_item.get('status', '?')
                progress = first_item.get('progress_percent', 0)
                
                status_str = f"{len(items)}项 | 首项:{name} ({progress:.0f}% {status})"
                if has_ready:
                    status_str += " [有就绪]"
            else:
                status_str = "空"
            
            print(f"  {qtype:10s}: {status_str}")
            
        except Exception as e:
            print(f"  {qtype:10s}: 查询失败 ({e})")
    
    return True


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
    
    # 检查初始状态
    print("=" * 80)
    print("[初始检查] 游戏状态")
    print("=" * 80)
    
    try:
        info = api.player_base_info_query()
        print(f"\n  资金: ${info.Cash:,}")
        print(f"  电力: {info.Power} / {info.PowerProvided}")
        
        if info.Cash < 3000:
            print(f"\n  ⚠️  警告: 资金不足！建议至少 $3000")
            response = input("\n  继续？(y/n): ")
            if response.lower() != 'y':
                return
    except Exception as e:
        print(f"\n  检查失败: {e}")
        input("\n按回车退出...")
        return
    
    input("\n按回车开始测试...")
    
    # 建设基地
    if not setup_base_if_needed(api):
        print("\n✗ 基地建设失败，无法继续测试")
        input("\n按回车退出...")
        return
    
    # 执行测试
    results = []
    
    # 测试1: 开始生产
    results.append(("开始生产建筑", test_produce_building(api)))
    time.sleep(1)
    
    # 测试2: 放置建筑
    results.append(("等待并放置建筑", test_wait_and_place(api)))
    time.sleep(1)
    
    # 测试3: 管理队列
    results.append(("管理生产队列", test_manage_production(api)))
    time.sleep(1)
    
    # 测试4: 自动放置
    results.append(("自动放置建筑", test_auto_placement(api)))
    time.sleep(1)
    
    # 测试5: 查询所有队列
    results.append(("查询所有队列", test_query_all_queues(api)))
    
    # 打印测试总结
    print("\n\n" + "=" * 80)
    print(" " * 30 + "测试总结")
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
    
    input("\n按回车退出...")


if __name__ == "__main__":
    main()

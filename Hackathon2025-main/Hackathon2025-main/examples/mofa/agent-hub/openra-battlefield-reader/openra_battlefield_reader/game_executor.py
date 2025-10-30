#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""游戏执行模块"""
import os
import sys
sys.path.append(os.getenv('OPENRA_PATH','.'))
from OpenRA_Copilot_Library import GameAPI, Location, TargetsQueryParam
import json
import time

class GameExecutor:
    """游戏执行器"""
    
    def __init__(self):
        self.api = GameAPI("localhost", 7445)
        self.execution_file = "execution_results.json"
        
    def execute_ai_decisions(self):
        """执行AI决策"""
        print("=== 执行AI决策 ===")
        
        # 读取AI分析结果
        analysis = self._load_ai_analysis()
        if not analysis:
            print("❌ 无法读取AI分析结果")
            return None
            
        results = {
            "executed_actions": [],
            "failed_actions": [],
            "production_results": {},
            "timestamp": time.time()
        }
        
        # 执行生产决策
        production_recs = analysis.get('production_recommendations', {})
        
        # 1. 执行步兵生产
        infantry_results = self._execute_infantry_production(
            production_recs.get('infantry_units', [])
        )
        results['production_results']['infantry'] = infantry_results
        
        # 2. 执行载具生产
        vehicle_results = self._execute_vehicle_production(
            production_recs.get('vehicle_units', [])
        )
        results['production_results']['vehicle'] = vehicle_results
        
        # 3. 执行建筑生产
        building_results = self._execute_building_production(
            production_recs.get('building_units', [])
        )
        results['production_results']['building'] = building_results
        
        # 4. 尝试放置建筑
        place_result = self._place_ready_buildings()
        if place_result:
            results['executed_actions'].append("放置就绪建筑")
        
        # 保存执行结果
        with open(self.execution_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        print("✅ AI决策执行完成")
        return results
    
    def _load_ai_analysis(self):
        """加载AI分析结果"""
        try:
            with open("ai_analysis.json", 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            print("❌ 无法读取AI分析文件")
            return None
    
    def _execute_infantry_production(self, infantry_units):
        """执行步兵生产"""
        results = []
        
        for unit in infantry_units:
            success = self._produce_unit(unit, "步兵")
            results.append({
                "unit": unit,
                "success": success
            })
            if success:
                time.sleep(1)  # 避免过快生产
                
        return results
    
    def _execute_vehicle_production(self, vehicle_units):
        """执行载具生产"""
        results = []
        
        for unit in vehicle_units:
            success = self._produce_unit(unit, "载具")
            results.append({
                "unit": unit,
                "success": success
            })
            if success:
                time.sleep(1)
                
        return results
    
    def _execute_building_production(self, building_units):
        """执行建筑生产"""
        results = []
        
        for unit in building_units:
            success = self._produce_unit(unit, "建筑")
            results.append({
                "unit": unit,
                "success": success
            })
            if success:
                time.sleep(1)
                
        return results
    
    def _produce_unit(self, unit_type, category):
        """生产单位"""
        try:
            # 使用GameAPI的封装方法
            wait_id = self.api.produce(unit_type, 1, auto_place_building=False)
            
            if wait_id is not None:
                print(f"🏭 生产{category}成功: {unit_type} (waitId: {wait_id})")
                return True
            else:
                print(f"❌ 生产{category}失败: {unit_type}")
                return False
                
        except Exception as e:
            print(f"❌ 生产{category}异常: {unit_type} - {e}")
            return False
    
    def _place_ready_buildings(self):
        """放置就绪建筑"""
        try:
            # 使用GameAPI的封装方法
            self.api.place_building("Building")
            print("🏗️ 尝试放置就绪建筑")
            return True
        except Exception as e:
            print(f"❌ 放置建筑失败: {e}")
        return False

def main():
    """主函数"""
    executor = GameExecutor()
    results = executor.execute_ai_decisions()
    
    if results:
        print(f"\n📊 执行结果总结:")
        total_success = 0
        total_attempts = 0
        
        for category, category_results in results['production_results'].items():
            success_count = sum(1 for r in category_results if r['success'])
            total_count = len(category_results)
            total_success += success_count
            total_attempts += total_count
            
            if total_count > 0:
                print(f"   {category}: {success_count}/{total_count} 成功")
        
        print(f"   总体成功率: {total_success}/{total_attempts}")
    
if __name__ == "__main__":
    main()
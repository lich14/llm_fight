#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""战场情况读取模块"""
import os
import sys
sys.path.append('/Users/liyao/Code/mofa/OpenCodeAlert/Copilot/openra_ai')
from OpenRA_Copilot_Library import GameAPI, Location, TargetsQueryParam
import json

class BattlefieldReader:
    """战场情况读取器"""
    
    def __init__(self):
        self.api = GameAPI(os.getenv('GAME_IP',"localhost"), os.getenv('GAME_PORT',7445))
        self.battlefield_file = "battlefield_state.json"
        
    def read_battlefield(self):
        """读取战场情况"""
        print("=== 读取战场情况 ===")
        
        battlefield_data = {
            "economy": self._read_economy(),
            "production": self._read_production_queues(),
            "map_info": self._read_map_info(),
            "screen_info": self._read_screen_info(),
            "timestamp": self._get_timestamp()
        }
        
        # 保存到文件
        with open(self.battlefield_file, 'w', encoding='utf-8') as f:
            json.dump(battlefield_data, f, ensure_ascii=False, indent=2)
            
        print("✅ 战场情况已读取并保存")
        return battlefield_data
    
    def _read_economy(self):
        """读取经济状况"""
        try:
            # 使用GameAPI的封装方法
            player_info = self.api.player_base_info_query()
            economy = {
                "cash": player_info.Cash + player_info.Resources,  # 根据文档：实际金钱=Cash+Resources
                "power": player_info.Power,
                "power_provided": player_info.PowerProvided,
                "power_drained": player_info.PowerDrained,
                "raw_data": {
                    "Cash": player_info.Cash,
                    "Resources": player_info.Resources,
                    "Power": player_info.Power,
                    "PowerProvided": player_info.PowerProvided,
                    "PowerDrained": player_info.PowerDrained
                }
            }
            print(f"💰 经济: ${economy['cash']} | ⚡电力: {economy['power']}/{economy['power_provided']}")
            return economy
        except Exception as e:
            print(f"❌ 读取经济失败: {e}")
            
        return {"cash": 0, "power": 0, "power_provided": 0, "power_drained": 0}
    
    def _read_production_queues(self):
        """读取生产队列"""
        queues = {}
        queue_types = ['Infantry', 'Vehicle', 'Building', 'Aircraft', 'Defense', 'Naval']
        
        for queue_type in queue_types:
            try:
                # 使用GameAPI的封装方法
                queue_data = self.api.query_production_queue(queue_type)
                queue_info = {
                    "items": len(queue_data.get('queue_items', [])),
                    "has_ready": queue_data.get('has_ready_item', False),
                    "queue_items": queue_data.get('queue_items', [])
                }
                queues[queue_type.lower()] = queue_info
                print(f"🏭 {queue_type}: {queue_info['items']}项目" + (" (有完成)" if queue_info['has_ready'] else ""))
            except Exception as e:
                print(f"❌ 读取{queue_type}队列失败: {e}")
                queues[queue_type.lower()] = {"items": 0, "has_ready": False, "queue_items": []}
                
        return queues
    
    def _read_map_info(self):
        """读取地图信息"""
        try:
            # 使用GameAPI的封装方法
            map_data = self.api.map_query()
            map_info = {
                "width": map_data.MapWidth,
                "height": map_data.MapHeight
            }
            print(f"🗺️ 地图: {map_info['width']} x {map_info['height']}")
            return map_info
        except Exception as e:
            print(f"❌ 读取地图失败: {e}")
            
        return {"width": 0, "height": 0}
    
    def _read_screen_info(self):
        """读取屏幕信息"""
        try:
            # 使用GameAPI的封装方法
            screen_data = self.api.screen_info_query()
            screen_info = {
                "screen_min": {"X": screen_data.ScreenMin.x, "Y": screen_data.ScreenMin.y},
                "screen_max": {"X": screen_data.ScreenMax.x, "Y": screen_data.ScreenMax.y},
                "mouse_on_screen": screen_data.IsMouseOnScreen
            }
            print(f"🖥️ 屏幕信息已读取")
            return screen_info
        except Exception as e:
            print(f"❌ 读取屏幕失败: {e}")
            
        return {}
    
    def _get_timestamp(self):
        """获取时间戳"""
        import time
        return time.time()

def main():
    """主函数"""
    reader = BattlefieldReader()
    battlefield = reader.read_battlefield()
    
    print(f"\n📊 战场状况总结:")
    print(f"   现金: ${battlefield['economy']['cash']}")
    print(f"   电力: {battlefield['economy']['power']}/{battlefield['economy']['power_provided']}")
    print(f"   生产队列总数: {sum(q['items'] for q in battlefield['production'].values())}")
    
if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Web对话式控制器"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import json
import time
import os
from battlefield_reader import BattlefieldReader
from ai_analyzer import AIAnalyzer
from game_executor import GameExecutor

class WebChatController:
    """Web对话式控制器"""
    
    def __init__(self, api_key):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'openra-ai-chat-secret-key'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self.battlefield_reader = BattlefieldReader()
        self.ai_analyzer = AIAnalyzer(api_key)
        self.game_executor = GameExecutor()
        self.is_running = False
        self.setup_routes()
        
    def setup_routes(self):
        """设置路由"""
        
        @self.app.route('/')
        def index():
            return render_template('chat.html')
            
        @self.socketio.on('connect')
        def handle_connect():
            emit('ai_message', {
                'message': '🤖 OpenRA AI助手已连接！',
                'type': 'system'
            })
            emit('ai_message', {
                'message': '你可以对我说：\n• "多生产战车！"\n• "专注防御"\n• "疯狂造兵"\n• "攻击敌人"',
                'type': 'info'
            })
            
        @self.socketio.on('disconnect')
        def handle_disconnect():
            print('用户断开连接')
            
        @self.socketio.on('user_message')
        def handle_message(data):
            user_input = data['message'].strip()
            
            if not user_input:
                emit('ai_message', {
                    'message': '❌ 请输入有效指令',
                    'type': 'error'
                })
                return
                
            # 回显用户消息
            emit('user_message_echo', {'message': user_input})
            
            if self.is_running:
                emit('ai_message', {
                    'message': '⏳ AI正在执行中，请稍等...',
                    'type': 'warning'
                })
                return
                
            # 异步执行AI循环
            threading.Thread(target=self.run_ai_cycle, args=(user_input,)).start()
            
        @self.socketio.on('stop_ai')
        def handle_stop():
            self.is_running = False
            emit('ai_message', {
                'message': '🛑 AI执行已停止',
                'type': 'system'
            })
    
    def save_user_input(self, text):
        """保存用户输入到JSON文件"""
        intent_data = {
            "raw_input": text,
            "intent_type": self._analyze_intent_type(text),
            "priority_units": self._extract_unit_preferences(text),
            "strategy": self._extract_strategy(text)
        }
        
        with open("user_intent.json", 'w', encoding='utf-8') as f:
            json.dump(intent_data, f, ensure_ascii=False, indent=2)
            
        return intent_data
    
    def _analyze_intent_type(self, text):
        """分析意图类型"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['战车', '载具', '坦克', '吉普']):
            return "vehicle_focus"
        elif any(word in text_lower for word in ['步兵', '士兵', '人员']):
            return "infantry_focus"
        elif any(word in text_lower for word in ['建筑', '基地', '防御']):
            return "building_focus"
        elif any(word in text_lower for word in ['攻击', '进攻', '战斗']):
            return "attack_focus"
        elif any(word in text_lower for word in ['防守', '防御', '守护']):
            return "defense_focus"
        else:
            return "balanced_development"
    
    def _extract_unit_preferences(self, text):
        """提取单位偏好"""
        preferences = []
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['步兵', '士兵']):
            preferences.append("infantry")
        if any(word in text_lower for word in ['战车', '载具', '坦克']):
            preferences.append("vehicle")
        if any(word in text_lower for word in ['建筑', '基地']):
            preferences.append("building")
            
        return preferences
    
    def _extract_strategy(self, text):
        """提取战略倾向"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['多多', '大量', '疯狂', '拼命']):
            return "aggressive_production"
        elif any(word in text_lower for word in ['稳定', '正常', '保持']):
            return "stable_development"
        elif any(word in text_lower for word in ['快速', '速度', '急']):
            return "rapid_expansion"
        else:
            return "standard"
    
    def run_ai_cycle(self, user_input):
        """运行AI循环"""
        self.is_running = True
        
        try:
            # 1. 保存用户输入
            self.socketio.emit('ai_message', {
                'message': f'📝 收到指令：{user_input}',
                'type': 'info'
            })
            
            intent_data = self.save_user_input(user_input)
            
            self.socketio.emit('ai_message', {
                'message': f'🎯 意图分析：{intent_data["intent_type"]}',
                'type': 'info'
            })
            
            time.sleep(1)
            
            # 2. 读取战场状态
            self.socketio.emit('ai_message', {
                'message': '🔍 正在读取战场状态...',
                'type': 'process'
            })
            
            battlefield_state = self.battlefield_reader.read_battlefield()
            
            if not battlefield_state:
                self.socketio.emit('ai_message', {
                    'message': '❌ 战场读取失败，请检查游戏连接',
                    'type': 'error'
                })
                return
            
            economy = battlefield_state.get('economy', {})
            self.socketio.emit('ai_message', {
                'message': f'💰 战场状况：现金${economy.get("cash", 0)}，电力{economy.get("power", 0)}/{economy.get("power_provided", 0)}',
                'type': 'info'
            })
            
            time.sleep(1)
            
            # 3. AI分析
            self.socketio.emit('ai_message', {
                'message': '🧠 AI正在分析战况...',
                'type': 'process'
            })
            
            ai_analysis = self.ai_analyzer.analyze_situation()
            
            if not ai_analysis:
                self.socketio.emit('ai_message', {
                    'message': '❌ AI分析失败',
                    'type': 'error'
                })
                return
            
            strategy = ai_analysis.get('recommended_strategy', '未知策略')
            self.socketio.emit('ai_message', {
                'message': f'🎯 AI策略：{strategy}',
                'type': 'success'
            })
            
            # 显示具体行动
            actions = ai_analysis.get('priority_actions', [])
            if actions:
                actions_text = '\n'.join([f'• {action}' for action in actions])
                self.socketio.emit('ai_message', {
                    'message': f'📋 执行计划：\n{actions_text}',
                    'type': 'info'
                })
            
            time.sleep(1)
            
            # 4. 执行决策
            self.socketio.emit('ai_message', {
                'message': '⚡ 正在执行AI决策...',
                'type': 'process'
            })
            
            execution_results = self.game_executor.execute_ai_decisions()
            
            if not execution_results:
                self.socketio.emit('ai_message', {
                    'message': '❌ 游戏执行失败',
                    'type': 'error'
                })
                return
            
            # 统计执行结果
            total_success = 0
            total_attempts = 0
            for category, results in execution_results.get('production_results', {}).items():
                success_count = sum(1 for r in results if r['success'])
                total_count = len(results)
                total_success += success_count
                total_attempts += total_count
            
            self.socketio.emit('ai_message', {
                'message': f'✅ 执行完成！成功率：{total_success}/{total_attempts}',
                'type': 'success'
            })
            
            self.socketio.emit('ai_message', {
                'message': '🤖 可以继续给我新的指令了！',
                'type': 'system'
            })
            
        except Exception as e:
            self.socketio.emit('ai_message', {
                'message': f'❌ 系统异常：{str(e)}',
                'type': 'error'
            })
        finally:
            self.is_running = False
    
    def run(self, host='127.0.0.1', port=5000, debug=True):
        """启动Web服务器"""
        print(f"🌐 OpenRA AI Web界面启动")
        print(f"🔗 访问地址：http://{host}:{port}")
        print("=" * 50)
        self.socketio.run(self.app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)

def main():
    """主函数"""
    API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
    
    controller = WebChatController(API_KEY)
    controller.run()

if __name__ == "__main__":
    main()
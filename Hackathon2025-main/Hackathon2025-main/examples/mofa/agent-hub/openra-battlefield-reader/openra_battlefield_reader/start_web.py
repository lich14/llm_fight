#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""启动Web对话界面"""

import sys
import os

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from web_chat_controller import WebChatController

def main():
    """启动Web界面"""
    API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
    
    print("🚀 启动OpenRA AI Web对话界面...")
    print("=" * 50)
    
    try:
        controller = WebChatController(API_KEY)
        controller.run(host='127.0.0.1', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n 再见！")
    except Exception as e:
        print(f" 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
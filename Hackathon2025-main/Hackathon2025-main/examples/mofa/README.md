# 红色警戒AI智能体系统

基于MoFA框架的红色警戒AI智能体，实现自动游戏控制和策略决策。

## 环境要求

- Python >= 3.10
- Rust 环境 (用于Dora运行时)
- OpenRA游戏客户端
- OpenAI API Key (或兼容的LLM服务)

## 安装步骤

### 1. 安装依赖环境

```bash
# 安装Rust环境
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 安装Dora运行时 
cargo install dora-cli

# 验证安装
dora --version
```

### 2. 安装MoFA框架

```bash
# 进入mofa框架目录
cd ~/mofa

# 安装MoFA框架
pip install -e .
```

### 3. 安装项目依赖

```bash
# 在项目根目录
cd ～/Hackathon2025/examples/mofa

# 安装各Agent依赖
pip install -e ./agent-hub/openra-battlefield-reader
pip install -e ./agent-hub/openra-battlefield-analyze  
pip install -e ./agent-hub/openra-execute
pip install -e ./node-hub/terminal-input
```

### 4. 配置环境变量

在项目根目录创建 `.env.secret` 文件：

```bash
# OpenAI API配置
LLM_API_KEY=your_openai_api_key_here
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=

# OpenRA游戏路径 
OPENRA_PATH=/path/to/your/OpenRA/Copilot/openra_ai

# 游戏连接配置
GAME_IP=localhost
GAME_PORT=7445
```

## 使用方法

### 1. 启动OpenRA游戏
确保OpenRA游戏已启动且API服务可用

### 2. 启动数据流

```bash
cd examples/openra-controller

# 启动Dora服务
dora up

# 构建数据流
dora build openra-controller.yml

# 运行数据流
dora start openra-controller.yml
```

### 3. 交互控制

在新终端中运行：

```bash
terminal-input
```

输入指令示例：
- "多多造步兵"
- "快速建造坦克"  
- "防守基地"
- "攻击敌人"

## 项目架构

### 数据流组件

1. **terminal-input**: 用户输入节点，接收命令并显示结果
2. **openra-battlefield-reader**: 战场状态读取器，分析用户意图并读取游戏状态
3. **openra-battlefield-analyze**: AI分析器，使用LLM分析战场并制定策略
4. **openra-execute**: 游戏执行器，将AI决策转换为游戏操作

### 数据流向

```
用户输入 → 战场读取 → AI分析 → 游戏执行 → 结果返回
```

### 核心文件

- `openra-controller.yml`: 数据流配置文件
- `agent-hub/*/main.py`: 各组件主要逻辑
- `examples/openra-controller/`: 运行示例和日志

## 常见问题

### 路径问题
如果遇到导入错误，检查：
1. MoFA框架是否正确安装
2. OPENRA_PATH环境变量是否正确设置
3. 各Agent是否正确安装

### 游戏连接问题
确保：
1. OpenRA游戏正在运行
2. API服务端口7445可访问
3. 游戏处于可控制状态

### AI分析失败
检查：
1. LLM_API_KEY是否正确配置
2. API服务是否可用
3. 网络连接是否正常

## 开发说明

### 添加新策略
修改 `agent-hub/openra-battlefield-analyze/ai_analyzer.py`

### 修改执行逻辑  
修改 `agent-hub/openra-execute/game_executor.py`

### 调试模式
在环境变量中设置 `WRITE_LOG=true` 启用详细日志
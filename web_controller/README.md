c c# SO-101 Web Controller

基于 LeRobot 框架的 SO-101 机械臂 Web 控制界面。通过浏览器实现机械臂的实时控制，支持所有关节的位置控制和状态监控。

## 功能特性

- 🌐 **Web界面控制**: 通过浏览器控制机械臂，无需安装客户端
- 🎛️ **实时关节控制**: 6个关节的独立位置控制（肩部旋转、抬升，肘部弯曲，腕部弯曲、旋转，夹爪）
- 📊 **实时状态监控**: 显示当前关节位置和系统状态
- 🔄 **WebSocket通信**: 10Hz频率的实时数据更新
- 🛡️ **安全机制**: 紧急停止功能和连接状态监控
- 📱 **响应式设计**: 支持桌面和移动设备
- 🔧 **完全集成**: 基于LeRobot现有代码，无需修改原项目

## 系统要求

- Python 3.10+
- LeRobot 项目环境
- SO-101 机械臂硬件
- 现代Web浏览器（Chrome, Firefox, Safari, Edge）

## 安装依赖

在LeRobot项目根目录下运行：

```bash
# 安装Web控制器额外依赖
pip install flask flask-socketio

# 确保LeRobot环境正确安装
pip install -e ".[feetech]"
```

## 快速开始

### 1. 连接机械臂

确保SO-101机械臂通过串口正确连接到计算机。

**Linux/Mac:**
```bash
# 查找串口设备
ls /dev/tty* | grep -E "(USB|ACM)"

# 设置串口权限（一次性设置）
sudo usermod -a -G dialout $USER
# 注销并重新登录使权限生效
```

**Windows:**
```bash
# 在设备管理器中查找COM端口
# 通常显示为 COM3, COM4 等
```

### 2. 启动Web控制器

在 `web_controller` 目录下运行：

```bash
# 基本用法（标准SO-101 Follower）
python run_controller.py --port /dev/ttyUSB0

# 使用已校准的SO-101 Leader机械臂
python run_controller.py --port /dev/cu.usbmodem5A7A0588301 --leader-config --robot-id my_so101_leader

# Windows用户
python run_controller.py --port COM3

# 自定义端口和调试模式
python run_controller.py --port /dev/ttyUSB0 --web-port 8080 --debug
```

### 3. 打开Web界面

在浏览器中访问：http://localhost:8080 (或自定义端口)

### 4. 操作步骤

1. **连接机械臂**: 点击"连接机械臂"按钮
2. **控制关节**: 使用滑动条调节各关节位置
3. **监控状态**: 查看实时关节位置和系统日志
4. **安全操作**: 需要时点击"紧急停止"

## 使用说明

### 配置类型选择

Web控制器支持三种配置模式：

1. **标准SO-101 Follower配置**（默认）
   - 适用于标准的SO-101 Follower机械臂
   - 使用默认的Follower硬件规格

2. **SO-101 Leader配置**（推荐用于你的情况）
   - 适用于已校准的SO-101 Leader机械臂
   - 使用你通过`lerobot-calibrate`创建的校准数据
   - 命令：`python run_controller.py --port /dev/cu.usbmodem5A7A0588301 --leader-config --robot-id my_so101_leader`

3. **自定义配置**
   - 适用于使用Leader硬件规格但需要Follower功能的机械臂
   - 使用混合齿轮比配置

### 界面布局

- **控制面板**: 连接/断开按钮，状态指示器，紧急停止
- **关节控制**: 6个关节的独立滑动条控制器
- **实时状态**: 当前关节位置的JSON格式显示
- **系统日志**: 操作历史和错误信息

### 关节说明

| 关节名称 | 英文名称 | 控制范围 | 说明 |
|---------|---------|----------|------|
| 肩部旋转 | shoulder_pan | -1.0 ~ 1.0 | 基座旋转 |
| 肩部抬升 | shoulder_lift | -1.0 ~ 1.0 | 第二关节抬升 |
| 肘部弯曲 | elbow_flex | -1.0 ~ 1.0 | 肘关节弯曲 |
| 腕部弯曲 | wrist_flex | -1.0 ~ 1.0 | 腕关节弯曲 |
| 腕部旋转 | wrist_roll | -1.0 ~ 1.0 | 腕关节旋转 |
| 夹爪 | gripper | -1.0 ~ 1.0 | 夹爪开合 |

### 安全功能

- **连接监控**: 自动检测连接状态
- **紧急停止**: 一键将所有关节复位到0位置
- **错误处理**: 友好的错误提示和恢复机制
- **关节复位**: 单独复位每个关节

## 命令行参数

```bash
python run_controller.py --help
```

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `--port` | 是 | - | 机械臂串口端口 |
| `--host` | 否 | 0.0.0.0 | Web服务器主机地址 |
| `--web-port` | 否 | 8080 | Web服务器端口 |
| `--debug` | 否 | False | 启用调试模式 |
| `--no-banner` | 否 | False | 不显示启动横幅 |
| `--leader-config` | 否 | False | 使用SO-101 Leader配置（适用于已校准的Leader机械臂） |
| `--robot-id` | 否 | my_so101_leader | 机械臂ID（用于匹配校准文件） |
| `--custom-config` | 否 | False | 使用自定义配置（适用于Leader硬件规格的Follower机械臂） |

## 网络配置

### 本地访问（推荐）
```bash
python run_controller.py --port /dev/ttyUSB0 --host 127.0.0.1
```

### 局域网访问
```bash
python run_controller.py --port /dev/ttyUSB0 --host 0.0.0.0
```

### 自定义端口
```bash
python run_controller.py --port /dev/ttyUSB0 --web-port 8080
```

## API接口

Web控制器提供RESTful API，可用于自定义客户端开发：

### HTTP接口

- `GET /api/status` - 获取机器人状态
- `POST /api/connect` - 连接机械臂
- `POST /api/disconnect` - 断开连接
- `POST /api/control` - 发送关节控制命令

### WebSocket接口

- `robot_status` - 实时状态更新
- `request_status` - 请求状态更新

## 故障排除

### 常见问题

**1. 连接失败**
```
[ERROR] Failed to connect: [Errno 13] Permission denied: '/dev/ttyUSB0'
```
解决方案：
- Linux/Mac: `sudo chmod 666 /dev/ttyUSB0` 或添加用户到dialout组
- Windows: 检查COM端口是否被其他程序占用

**2. 端口不存在**
```
[ERROR] Failed to connect: [Errno 2] No such file or directory: '/dev/ttyUSB1'
```
解决方案：
- 使用 `ls /dev/tty*` (Linux/Mac) 或设备管理器 (Windows) 确认正确端口
- 检查USB连接和驱动程序

**3. 网页无法访问**
```
This site can't be reached
```
解决方案：
- 检查防火墙设置
- 确认Web服务器端口未被占用（默认8080端口）
- 使用 `127.0.0.1` 替代 `localhost`
- 如果8080端口被占用，使用 `--web-port` 参数指定其他端口

**4. 机械臂响应缓慢**
- 检查串口波特率设置
- 减少控制频率
- 确认USB连接稳定

### 调试模式

启用调试模式获取详细日志：

```bash
python run_controller.py --port /dev/ttyUSB0 --debug
```

### 日志分析

系统日志显示在Web界面的"系统日志"面板中，包含：
- 连接状态变化
- 关节控制命令
- 错误和警告信息
- WebSocket连接状态

## 开发扩展

### 添加新功能

Web控制器采用模块化设计，可以轻松扩展：

1. **后端扩展**: 在 `robot_web_controller.py` 中添加新的API路由
2. **前端扩展**: 修改 `templates/robot_control.html` 添加新的UI组件
3. **WebSocket扩展**: 添加新的实时通信事件

### 代码结构

```
web_controller/
├── robot_web_controller.py    # Flask后端服务器
├── run_controller.py          # 启动脚本
├── templates/
│   └── robot_control.html     # Web界面模板
├── static/                    # 静态资源目录（CSS/JS）
└── README.md                  # 说明文档
```

## 项目集成

这个Web控制器完全独立于LeRobot主项目，不会影响现有代码：

- ✅ 独立目录结构
- ✅ 复用LeRobot接口
- ✅ 无需修改原始代码
- ✅ 可随时删除

## 许可证

本项目基于LeRobot项目，遵循Apache 2.0许可证。

## 致谢

- 基于 [Hugging Face LeRobot](https://github.com/huggingface/lerobot) 框架
- 使用 SO-101 机械臂硬件平台
- 感谢开源社区的贡献

---

**享受您的机械臂Web控制体验！** 🤖🌐
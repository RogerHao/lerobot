#!/usr/bin/env python3

"""
SO-101 Robot Web Controller Launcher

A simple launcher script for starting the web-based robot control interface.
This script provides command-line options for configuring the robot connection
and web server settings.

Usage:
    python run_controller.py --port /dev/ttyUSB0
    python run_controller.py --port COM3 --host 0.0.0.0 --web-port 8080 --debug

Author: Claude Code Assistant
Created for: SO-101 Master-Slave Teleoperation Project
"""

import argparse
import logging
import sys
from pathlib import Path

# Add the parent directory to sys.path to import LeRobot modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from robot_web_controller import RobotWebController


def setup_logging(debug: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    format_str = '[%(asctime)s] %(levelname)s in %(name)s: %(message)s'
    
    logging.basicConfig(
        level=level,
        format=format_str,
        datefmt='%H:%M:%S'
    )
    
    # Reduce werkzeug logging noise unless in debug mode
    if not debug:
        logging.getLogger('werkzeug').setLevel(logging.WARNING)


def validate_port(port: str) -> str:
    """Validate and normalize the serial port."""
    if not port:
        raise ValueError("Port cannot be empty")
    
    # Common port patterns
    if port.startswith('/dev/') or port.startswith('COM') or port.startswith('/dev/tty'):
        return port
    
    # Try to add common prefixes if user provided just the port name
    if port.isdigit():
        # Windows COM port
        return f"COM{port}"
    elif port.startswith('USB'):
        # Linux USB port
        return f"/dev/tty{port}"
    
    return port


def print_banner():
    """Print startup banner."""
    banner = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║            SO-101 机械臂 Web 控制界面                      ║
║                                                           ║
║  基于 LeRobot 框架的 Web 机械臂控制系统                    ║
║  Web-based Robot Control System powered by LeRobot       ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='SO-101 Robot Web Controller - 基于LeRobot的Web机械臂控制界面',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法 (Examples):
  # 使用默认设置连接到 /dev/ttyUSB0
  python run_controller.py --port /dev/ttyUSB0
  
  # Windows 系统使用 COM 端口
  python run_controller.py --port COM3
  
  # 自定义 Web 服务器设置
  python run_controller.py --port /dev/ttyUSB0 --host 0.0.0.0 --web-port 8080
  
  # 启用调试模式
  python run_controller.py --port /dev/ttyUSB0 --debug
  
  # 仅允许本地访问
  python run_controller.py --port /dev/ttyUSB0 --host 127.0.0.1

注意事项 (Important Notes):
  - 确保机械臂已正确连接并且串口权限正确
  - Linux/Mac 用户可能需要将用户添加到 dialout 组
  - 首次使用需要对机械臂进行校准
  - 使用 Ctrl+C 安全退出程序
        """
    )
    
    # Required arguments
    parser.add_argument(
        '--port', 
        type=str, 
        required=True,
        help='机械臂串口端口 (例如: /dev/ttyUSB0, COM3)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--host', 
        type=str, 
        default='0.0.0.0',
        help='Web服务器主机地址 (默认: 0.0.0.0, 允许所有IP访问)'
    )
    
    parser.add_argument(
        '--web-port', 
        type=int, 
        default=8080,
        help='Web服务器端口 (默认: 8080)'
    )
    
    parser.add_argument(
        '--debug', 
        action='store_true',
        help='启用调试模式 (显示详细日志)'
    )
    
    parser.add_argument(
        '--no-banner',
        action='store_true',
        help='不显示启动横幅'
    )
    
    parser.add_argument(
        '--custom-config',
        action='store_true',
        help='使用自定义配置（适用于使用Leader硬件规格的Follower机械臂）'
    )
    
    parser.add_argument(
        '--leader-config',
        action='store_true',
        help='使用SO-101 Leader配置（适用于已校准的Leader机械臂）'
    )
    
    parser.add_argument(
        '--robot-id',
        type=str,
        default='my_so101_leader',
        help='机械臂ID（用于匹配校准文件，默认: my_so101_leader）'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.debug)
    
    # Print banner unless disabled
    if not args.no_banner:
        print_banner()
    
    try:
        # Validate port
        robot_port = validate_port(args.port)
        
        # Create and configure controller
        controller = RobotWebController(
            robot_port=robot_port,
            host=args.host,
            port=args.web_port,
            use_custom_config=args.custom_config,
            use_leader_config=args.leader_config,
            robot_id=args.robot_id
        )
        
        # Print startup information
        print(f"🤖 机械臂端口: {robot_port}")
        print(f"🌐 Web服务器: http://{args.host}:{args.web_port}")
        print(f"🔧 调试模式: {'启用' if args.debug else '禁用'}")
        if args.leader_config:
            print(f"⚙️  硬件配置: SO-101 Leader (ID: {args.robot_id})")
        elif args.custom_config:
            print(f"⚙️  硬件配置: 自定义(Leader规格)")
        else:
            print(f"⚙️  硬件配置: 标准(Follower规格)")
        print()
        print("📋 使用说明:")
        print("  1. 在浏览器中打开上述网址")
        print("  2. 点击 '连接机械臂' 按钮")
        print("  3. 使用滑动条控制关节位置")
        print("  4. 使用 Ctrl+C 安全退出程序")
        print()
        print("⚠️  安全提示:")
        print("  - 首次使用请确保机械臂处于安全位置")
        print("  - 操作时请保持机械臂周围无障碍物")
        print("  - 出现异常情况立即点击 '紧急停止'")
        print()
        print("🚀 启动 Web 控制器...")
        print("=" * 60)
        
        # Start the controller
        controller.run(debug=args.debug)
        
    except KeyboardInterrupt:
        print("\n\n👋 收到退出信号，正在安全关闭...")
        print("感谢使用 SO-101 Web 控制器！")
        
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        print("\n🔍 故障排除:")
        print("  1. 检查机械臂是否正确连接")
        print("  2. 验证串口端口号是否正确")
        print("  3. 确认串口权限 (Linux/Mac: sudo usermod -a -G dialout $USER)")
        print("  4. 检查是否有其他程序占用端口")
        print("  5. 尝试使用 --debug 参数查看详细错误信息")
        
        sys.exit(1)


if __name__ == '__main__':
    main()
#!/usr/bin/env python3

"""
SO-101 Robot Web Controller

A Flask-based web interface for controlling SO-101 robotic arm through LeRobot.
Provides real-time joint control via web browser with sliders and status monitoring.

Author: Claude Code Assistant
Created for: SO-101 Master-Slave Teleoperation Project
"""

import json
import logging
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

# LeRobot imports - using relative imports to work from web_controller directory
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from lerobot.robots.so101_follower import SO101Follower, SO101FollowerConfig
from lerobot.errors import DeviceNotConnectedError, DeviceAlreadyConnectedError

# Import custom configuration for mixed hardware setup
try:
    from custom_so101_config import CustomSO101Follower, CustomSO101Config
    HAS_CUSTOM_CONFIG = True
except ImportError:
    HAS_CUSTOM_CONFIG = False

# Import SO-101 Leader configuration for web control
try:
    from so101_leader_config import SO101LeaderWebController, SO101LeaderWebConfig
    HAS_LEADER_CONFIG = True
except ImportError:
    HAS_LEADER_CONFIG = False


class RobotWebController:
    """
    Web controller for SO-101 robotic arm using Flask and LeRobot.
    
    Features:
    - Real-time joint position control via web sliders
    - Live status monitoring and feedback
    - Safe connection/disconnection handling
    - WebSocket support for real-time updates
    """
    
    def __init__(self, robot_port: str, host: str = "0.0.0.0", port: int = 8080, 
                 use_custom_config: bool = False, use_leader_config: bool = False, robot_id: str = None):
        """
        Initialize the web controller.
        
        Args:
            robot_port: Serial port for the SO-101 robot (e.g., "/dev/ttyUSB0")
            host: Web server host address
            port: Web server port (default: 8080)
            use_custom_config: Use custom config for Leader hardware as Follower
            use_leader_config: Use SO-101 Leader configuration with calibration
            robot_id: Robot ID for calibration file matching
        """
        self.robot_port = robot_port
        self.host = host
        self.port = port
        self.use_custom_config = use_custom_config
        self.use_leader_config = use_leader_config
        self.robot_id = robot_id
        
        # Flask app setup
        template_folder = Path(__file__).parent / "templates"
        static_folder = Path(__file__).parent / "static"
        
        self.app = Flask(
            __name__,
            template_folder=str(template_folder),
            static_folder=str(static_folder)
        )
        self.app.config['SECRET_KEY'] = 'so101_web_controller_secret'
        
        # SocketIO for real-time communication
        self.socketio = SocketIO(
            self.app,
            cors_allowed_origins="*",
            async_mode='threading'
        )
        
        # Robot setup
        self.robot: Optional[SO101Follower] = None
        self.is_connected = False
        self.current_positions: Dict[str, float] = {}
        
        # Status monitoring
        self.status_thread = None
        self.status_running = False
        
        # Setup Flask routes and WebSocket handlers
        self.setup_routes()
        self.setup_websocket_handlers()
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def create_robot_config(self):
        """Create robot configuration based on hardware setup."""
        if self.use_leader_config and HAS_LEADER_CONFIG:
            return SO101LeaderWebConfig(
                port=self.robot_port,
                id=self.robot_id,  # Use provided robot ID for calibration
                use_degrees=False  # Use normalized values (-1 to 1)
            )
        elif self.use_custom_config and HAS_CUSTOM_CONFIG:
            return CustomSO101Config(
                port=self.robot_port,
                cameras={},  # No cameras needed for web control
                use_degrees=False,  # Use normalized values (-1 to 1)
                disable_torque_on_disconnect=True
            )
        else:
            return SO101FollowerConfig(
                port=self.robot_port,
                cameras={},  # No cameras needed for web control
                use_degrees=False,  # Use normalized values (-1 to 1)
                disable_torque_on_disconnect=True
            )
    
    def setup_routes(self):
        """Setup Flask HTTP routes."""
        
        @self.app.route('/')
        def index():
            """Main control interface."""
            return render_template('robot_control.html')
        
        @self.app.route('/api/status')
        def get_status():
            """Get current robot connection status and joint information."""
            if self.is_connected and self.robot:
                try:
                    # Get joint names from robot
                    joints = list(self.robot.action_features.keys())
                    
                    # Get current positions and real ranges
                    try:
                        obs = self.robot.get_observation()
                        current_pos = {k: v for k, v in obs.items() if k.endswith('.pos')}
                    except Exception as e:
                        self.logger.warning(f"Failed to get observation: {e}")
                        current_pos = {joint: 0.0 for joint in joints}
                    
                    # Get real position ranges from calibration
                    joint_ranges = {}
                    if hasattr(self.robot, 'bus') and hasattr(self.robot.bus, 'calibration'):
                        for joint in joints:
                            motor_name = joint.replace('.pos', '')
                            if motor_name in self.robot.bus.calibration:
                                cal = self.robot.bus.calibration[motor_name]
                                joint_ranges[joint] = {
                                    "min": cal.range_min,
                                    "max": cal.range_max,
                                    "center": (cal.range_min + cal.range_max) // 2
                                }
                            else:
                                # Fallback to normalized range
                                joint_ranges[joint] = {"min": -1, "max": 1, "center": 0}
                    else:
                        # Fallback to normalized ranges
                        for joint in joints:
                            joint_ranges[joint] = {"min": -1, "max": 1, "center": 0}
                    
                    return jsonify({
                        "connected": True,
                        "joints": joints,
                        "current_positions": current_pos,  # Normalized positions
                        "joint_ranges": joint_ranges,  # Real position ranges
                        "robot_type": self.robot.name if self.robot else "unknown"
                    })
                except Exception as e:
                    self.logger.error(f"Error getting status: {e}")
                    return jsonify({
                        "connected": False,
                        "error": str(e)
                    })
            
            return jsonify({
                "connected": False,
                "joints": [],
                "current_positions": {},
                "joint_ranges": {},
                "robot_type": "none"
            })
        
        @self.app.route('/api/connect', methods=['POST'])
        def connect_robot():
            """Connect to the robot."""
            if self.is_connected:
                return jsonify({
                    "status": "info",
                    "message": "Robot already connected",
                    "connected": True
                })
            
            try:
                self.logger.info(f"Connecting to SO-101 robot on port {self.robot_port}")
                
                # Create robot instance based on configuration
                config = self.create_robot_config()
                
                if self.use_leader_config and HAS_LEADER_CONFIG:
                    self.robot = SO101LeaderWebController(config)
                    self.logger.info(f"Using SO-101 Leader configuration with ID: {self.robot_id}")
                elif self.use_custom_config and HAS_CUSTOM_CONFIG:
                    self.robot = CustomSO101Follower(config)
                    self.logger.info("Using custom configuration for Leader hardware as Follower")
                else:
                    self.robot = SO101Follower(config)
                    self.logger.info("Using standard SO-101 Follower configuration")
                
                # Connect to robot
                self.robot.connect(calibrate=False)  # Skip calibration for web control
                
                # Ensure torque is enabled for movement (if not already handled by robot class)
                if hasattr(self.robot, 'bus') and hasattr(self.robot.bus, 'enable_torque'):
                    try:
                        self.robot.bus.enable_torque()
                        self.logger.info("Torque enabled for all motors")
                    except Exception as e:
                        self.logger.warning(f"Failed to enable torque: {e}")
                
                self.is_connected = True
                
                # Start status monitoring
                self.start_status_monitoring()
                
                self.logger.info("Robot connected successfully")
                
                return jsonify({
                    "status": "success",
                    "message": f"Successfully connected to {self.robot.name}",
                    "connected": True,
                    "robot_type": self.robot.name
                })
                
            except DeviceAlreadyConnectedError:
                return jsonify({
                    "status": "info",
                    "message": "Robot already connected",
                    "connected": True
                })
            except Exception as e:
                self.logger.error(f"Failed to connect to robot: {e}")
                self.is_connected = False
                self.robot = None
                
                return jsonify({
                    "status": "error",
                    "message": f"Failed to connect: {str(e)}",
                    "connected": False
                })
        
        @self.app.route('/api/disconnect', methods=['POST'])
        def disconnect_robot():
            """Disconnect from the robot."""
            try:
                # Stop status monitoring
                self.stop_status_monitoring()
                
                if self.robot and self.is_connected:
                    # Disable torque before disconnecting for safety
                    if hasattr(self.robot, 'bus') and hasattr(self.robot.bus, 'disable_torque'):
                        try:
                            self.robot.bus.disable_torque()
                            self.logger.info("Torque disabled for safety")
                        except Exception as e:
                            self.logger.warning(f"Failed to disable torque during disconnect: {e}")
                    
                    self.robot.disconnect()
                    self.logger.info("Robot disconnected successfully")
                
                self.is_connected = False
                self.robot = None
                self.current_positions = {}
                
                return jsonify({
                    "status": "success",
                    "message": "Robot disconnected successfully",
                    "connected": False
                })
                
            except Exception as e:
                self.logger.error(f"Error during disconnect: {e}")
                # Force reset state even if disconnect failed
                self.is_connected = False
                self.robot = None
                
                return jsonify({
                    "status": "warning",
                    "message": f"Disconnected with warning: {str(e)}",
                    "connected": False
                })
        
        @self.app.route('/api/control', methods=['POST'])
        def control_joints():
            """Send joint control commands to the robot."""
            if not self.is_connected or not self.robot:
                return jsonify({
                    "status": "error",
                    "message": "Robot not connected"
                })
            
            try:
                # Get action from request
                action_data = request.get_json()
                if not action_data:
                    return jsonify({
                        "status": "error",
                        "message": "No action data provided"
                    })
                
                self.logger.info(f"Received joint command (real positions): {action_data}")
                
                # Convert real positions to normalized values for LeRobot
                normalized_action = {}
                for joint_name, real_position in action_data.items():
                    motor_name = joint_name.replace('.pos', '')
                    if (hasattr(self.robot, 'bus') and 
                        hasattr(self.robot.bus, 'calibration') and 
                        motor_name in self.robot.bus.calibration):
                        
                        cal = self.robot.bus.calibration[motor_name]
                        # Convert real position to normalized (-1 to 1)
                        normalized_pos = 2 * (real_position - cal.range_min) / (cal.range_max - cal.range_min) - 1
                        # Clamp to valid range
                        normalized_pos = max(-1, min(1, normalized_pos))
                        normalized_action[joint_name] = normalized_pos
                        
                        self.logger.info(f"Converted {joint_name}: {real_position} -> {normalized_pos:.3f}")
                    else:
                        # If no calibration, assume it's already normalized
                        normalized_action[joint_name] = real_position
                
                # Send normalized action to robot
                actual_action = self.robot.send_action(normalized_action)
                self.logger.info(f"Joint command executed successfully")
                
                return jsonify({
                    "status": "success",
                    "message": "Command sent successfully",
                    "action_sent": actual_action
                })
                
            except DeviceNotConnectedError:
                self.is_connected = False  # Update state
                return jsonify({
                    "status": "error",
                    "message": "Robot connection lost"
                })
            except Exception as e:
                self.logger.error(f"Control command failed: {e}")
                return jsonify({
                    "status": "error",
                    "message": f"Command failed: {str(e)}"
                })
    
    def setup_websocket_handlers(self):
        """Setup WebSocket event handlers for real-time communication."""
        
        @self.socketio.on('connect')
        def on_connect():
            """Handle client connection."""
            self.logger.info("Client connected to WebSocket")
            emit('status', {'message': 'Connected to robot controller'})
        
        @self.socketio.on('disconnect')
        def on_disconnect():
            """Handle client disconnection."""
            self.logger.info("Client disconnected from WebSocket")
        
        @self.socketio.on('request_status')
        def on_request_status():
            """Handle status request from client."""
            if self.is_connected and self.current_positions:
                emit('robot_status', {
                    'positions': self.current_positions,
                    'connected': True,
                    'timestamp': time.time()
                })
            else:
                emit('robot_status', {
                    'positions': {},
                    'connected': False,
                    'timestamp': time.time()
                })
    
    def start_status_monitoring(self):
        """Start background thread for status monitoring."""
        if self.status_thread and self.status_thread.is_alive():
            return
        
        self.status_running = True
        self.status_thread = threading.Thread(target=self._status_monitor_loop, daemon=True)
        self.status_thread.start()
        self.logger.info("Started status monitoring")
    
    def stop_status_monitoring(self):
        """Stop status monitoring thread."""
        self.status_running = False
        if self.status_thread:
            self.status_thread.join(timeout=2.0)
        self.logger.info("Stopped status monitoring")
    
    def _status_monitor_loop(self):
        """Background loop for monitoring robot status."""
        while self.status_running and self.is_connected:
            try:
                if self.robot:
                    # Get current observation
                    obs = self.robot.get_observation()
                    positions = {k: v for k, v in obs.items() if k.endswith('.pos')}
                    
                    self.current_positions = positions
                    
                    # Emit to connected clients
                    self.socketio.emit('robot_status', {
                        'positions': positions,
                        'connected': True,
                        'timestamp': time.time()
                    })
                    
            except Exception as e:
                self.logger.warning(f"Status monitoring error: {e}")
                # Don't break the loop for temporary errors
            
            time.sleep(0.1)  # 10Hz update rate
    
    def run(self, debug: bool = False):
        """
        Start the web server.
        
        Args:
            debug: Enable Flask debug mode
        """
        self.logger.info(f"Starting SO-101 Web Controller on http://{self.host}:{self.port}")
        self.logger.info(f"Robot port: {self.robot_port}")
        
        try:
            self.socketio.run(
                self.app,
                host=self.host,
                port=self.port,
                debug=debug,
                use_reloader=False,  # Disable reloader to avoid threading issues
                allow_unsafe_werkzeug=True  # Allow Werkzeug for development
            )
        except KeyboardInterrupt:
            self.logger.info("Shutting down web controller...")
        finally:
            # Cleanup
            self.stop_status_monitoring()
            if self.is_connected and self.robot:
                try:
                    self.robot.disconnect()
                except:
                    pass


if __name__ == '__main__':
    # Quick test run
    import argparse
    
    parser = argparse.ArgumentParser(description='SO-101 Robot Web Controller')
    parser.add_argument('--port', type=str, required=True, 
                       help='Robot serial port (e.g., /dev/ttyUSB0)')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                       help='Web server host (default: 0.0.0.0)')
    parser.add_argument('--web-port', type=int, default=8080,
                       help='Web server port (default: 8080)')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode')
    
    args = parser.parse_args()
    
    controller = RobotWebController(args.port, args.host, args.web_port)
    controller.run(debug=args.debug)
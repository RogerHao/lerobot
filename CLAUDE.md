# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LeRobot is a state-of-the-art machine learning library for real-world robotics in PyTorch. The codebase provides models, datasets, and tools for robotic manipulation with a focus on imitation learning and reinforcement learning. It includes support for various robot arms including SO-101, HopeJR, and ALOHA.

### Core Architecture

- **Modular Design**: Robots, teleoperators, cameras, motors, and policies are implemented as pluggable components
- **Robot-Teleoperator Pattern**: Each robot has a corresponding teleoperator for leader-follower control
- **Configuration-Driven**: All components use dataclass configurations for easy parameterization
- **Standardized Interfaces**: Consistent `connect()`, `disconnect()`, `get_observation()`, `send_action()` methods

### Key Directories

- `src/lerobot/robots/`: Robot implementations (followers)
- `src/lerobot/teleoperators/`: Teleoperator implementations (leaders)
- `src/lerobot/cameras/`: Camera integration (OpenCV, RealSense)
- `src/lerobot/motors/`: Motor control (Feetech, Dynamixel)
- `src/lerobot/policies/`: ML policies (ACT, Diffusion, TDMPC, etc.)
- `src/lerobot/datasets/`: Dataset management and processing
- `src/lerobot/scripts/`: Training and evaluation scripts

## Development Commands

### Environment Setup
```bash
# Create conda environment (Python 3.10 recommended)
conda create -y -n lerobot python=3.10
conda activate lerobot

# Install from source (editable)
pip install -e .

# With optional dependencies for SO-101
pip install -e ".[feetech]"

# All features
pip install -e ".[all]"
```

### Core Operations
```bash
# Find available cameras
lerobot-find-cameras

# Find available serial ports
lerobot-find-port

# Setup and calibrate motors
lerobot-setup-motors --robot.type=so101_follower --robot.port=/dev/ttyUSB0

# Teleoperate a robot
lerobot-teleoperate \
    --robot.type=so101_follower \
    --robot.port=/dev/ttyUSB0 \
    --teleop.type=so101_leader \
    --teleop.port=/dev/ttyUSB1 \
    --display_data=true

# Record demonstrations
lerobot-record \
    --robot.type=so101_follower \
    --robot.port=/dev/ttyUSB0 \
    --teleop.type=so101_leader \
    --teleop.port=/dev/ttyUSB1
```

### Training and Evaluation
```bash
# Train a policy
lerobot-train --config_path=lerobot/act_so100_test

# Evaluate a pretrained policy
lerobot-eval \
    --policy.path=lerobot/diffusion_pusht \
    --env.type=pusht \
    --eval.batch_size=10
```

### Development Tools
```bash
# Code formatting and linting
ruff format src/ tests/
ruff check src/ tests/ --fix

# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src/lerobot --cov-report=html
```

## SO-101 Master-Slave Teleoperation

For your master-slave robotic arm project using SO-101:

### Hardware Components
- **SO-101 Follower**: 6x STS3215 motors with 1/345 gearing
- **SO-101 Leader**: Mixed gearing (191/345/147) for optimal control
- **Communication**: Serial via Feetech protocol

### Key Implementation Files
- `src/lerobot/robots/so101_follower/so101_follower.py`: Follower arm control
- `src/lerobot/teleoperators/so101_leader/so101_leader.py`: Leader arm sensing
- `src/lerobot/teleoperate.py`: Main teleoperation loop
- `src/lerobot/motors/feetech/`: Feetech motor communication

### Network Teleoperation Architecture
The current implementation uses direct serial communication. For network-based teleoperation:

1. **Transport Layer**: `src/lerobot/transport/` contains networking components
2. **Async Processing**: `src/lerobot/async_inference/` for non-blocking operations
3. **Configuration**: Robot and teleoperator configs support network parameters

### Configuration Examples
```python
# Local teleoperation
robot_config = SO101FollowerConfig(
    port="/dev/ttyUSB0",
    cameras={"front": {"type": "opencv", "index_or_path": 0}}
)

# For network extension, consider:
# - Adding network transport to robot configs
# - Implementing TCP/UDP communication layers
# - Using the async inference framework
```

### Development Workflow
1. **Start with local teleoperation**: Test basic functionality
2. **Add network transport**: Extend existing transport classes
3. **Implement latency compensation**: Use prediction/interpolation
4. **Add safety mechanisms**: Timeout handling, connection monitoring

### Testing and Validation
```bash
# Test motor communication
python -c "from lerobot.motors.feetech import FeetechMotorsBus; bus = FeetechMotorsBus('/dev/ttyUSB0'); bus.connect()"

# Visualize robot state
python -m lerobot.scripts.visualize_dataset --repo-id your_dataset

# Test teleoperation loop
lerobot-teleoperate --robot.type=so101_follower --teleop.type=so101_leader
```

### Current Hardware Configuration

**SO-101 Robot on RDK-X5 (primary deployment):**
- **Host**: RDK-X5 (`ssh rdk-x5`, IP `192.168.32.170`, user `sunrise`, sudo pw: `112358`)
- **Serial Port**: `/dev/ttyACM0` (USB-A port, CDC ACM driver)
- **USB Chip**: CH340 (VID:PID=1A86:55D3) — must use USB-A port, Type-C port lacks CC negotiation
- **OS**: Linux 6.1.83 aarch64, Python 3.10.12
- **Installed**: lerobot 0.4.4 with feetech support, flask, flask-socketio
- **Calibration**: `~/.cache/huggingface/lerobot/calibration/robots/so101_follower/None.json` (copied from Mac)
- **No RTC**: System clock resets to Jan 2000 on reboot — must set date manually or via NTP

**RDK-X5 Known Issues:**
- USB-C port defaults to device/gadget mode (`35300000.usb2` role=device); switch to host with:
  `echo host | sudo tee /sys/devices/platform/soc/35000000.hsio_apb/35300000.usb2/35300000.usb/usb_role/35300000.usb-role-switch/role`
- No direct internet; route through Mac's Surge proxy:
  `export http_proxy=http://192.168.32.192:6152 https_proxy=http://192.168.32.192:6152`
- `~/.local/bin` not on PATH by default — prefix commands or `export PATH=$HOME/.local/bin:$PATH`

**SO-101 Robot on Mac (for calibration/development):**
- **Serial Port**: `/dev/cu.usbmodem5A7A0588301`
- **Calibration**: `~/.cache/huggingface/lerobot/calibration/robots/so101_follower/None.json`

### Web Controller

**Location**: `web_controller/` (this repo) and deployed to `rdk-x5:/home/sunrise/web_controller/`

Flask + WebSocket app for browser-based joint control over LAN.

```bash
# On RDK-X5: start the web controller
ssh rdk-x5
cd /home/sunrise/web_controller
python3 server.py --port /dev/ttyACM0

# Access from browser:
# http://192.168.32.170:8080
```

**Key files:**
- `web_controller/server.py`: Minimal backend using FeetechMotorsBus directly (lerobot 0.4.4 API)
- `web_controller/robot_web_controller.py`: Old backend (pre-0.4.4 API, not used on RDK-X5)
- `web_controller/templates/robot_control.html`: Web UI with slider controls

**Architecture**: server.py uses `FeetechMotorsBus` with `Motor(id, 'sts3215', MotorNormMode.DEGREES)` and calibration for degree-based read/write. Sliders range -150° to 150° (gripper -100° to 100°).

**Quick Start Commands:**
```bash
# Activate virtual environment (Mac development)
source .venv/bin/activate

# Calibrate on Mac, then scp to RDK-X5
lerobot-calibrate --robot.type=so101_follower --robot.port=/dev/cu.usbmodem5A7A0588301
scp ~/.cache/huggingface/lerobot/calibration/robots/so101_follower/None.json rdk-x5:/home/sunrise/.cache/huggingface/lerobot/calibration/robots/so101_follower/

# Setup motors (interactive, assigns motor IDs)
lerobot-setup-motors --robot.type=so101_follower --robot.port=/dev/cu.usbmodem5A7A0588301
```

### Important Notes
- All robot operations use normalized action spaces (-1 to 1 or degrees)
- Motor calibration is essential before first use
- The codebase uses Python 3.10+ and PyTorch 2.2+ (currently using Python 3.13.5)
- Rerun.io is used for visualization and debugging
- Virtual environment managed by `uv` in project root (`.venv/`)
- lerobot 0.4.4 API: motors use `Motor(id, model, MotorNormMode)` dataclass, `bus.read/write` require motor name arg, `normalize=False` for raw access
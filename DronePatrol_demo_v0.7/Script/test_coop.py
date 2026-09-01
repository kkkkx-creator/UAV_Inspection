# test_coop.py
# 第三阶段协同控制独立测试（不依赖 UE）
# 运行：python test_coop.py
import time
from uav_controller import UAVController, UAV_NAMES

controller = UAVController()
if not controller.connect_airsim():
    print("[FATAL] 无法连接 AirSim，请确认 UE 已 Play")
    exit(1)

# 1. 全部起飞
print("[TEST] 全部起飞...")
for name in UAV_NAMES:
    controller.client.takeoffAsync(vehicle_name=name)
time.sleep(5)

# 2. 测试编队保持（V 形）
print("\n[TEST] 编队保持 V 形...")
controller.execute_command({
    "type": "formationHold",
    "formation_type": "V",
    "formation_center": {"x": 0, "y": 0, "z": -15},
    "speed": 5.0,
})
time.sleep(15)

# 3. 测试运行时队形切换
print("\n[TEST] 切换到横排 line...")
controller.execute_command({"type": "formationSwitch", "formation_type": "line"})
time.sleep(10)

# 4. 测试协同巡逻
print("\n[TEST] 协同巡逻...")
controller.execute_command({"type": "patrol", "formation_type": "V", "speed": 5.0})
time.sleep(30)

# 5. 停止
print("\n[TEST] 停止协同控制...")
controller.execute_command({"type": "stopCoop"})
time.sleep(2)

# 6. 全部降落
print("\n[TEST] 全部降落...")
for name in UAV_NAMES:
    controller.client.landAsync(vehicle_name=name)
time.sleep(8)
print("[TEST] 测试完成")

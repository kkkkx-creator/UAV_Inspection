# debug_takeoff.py
# 一次性诊断脚本：找出无人机为什么不起飞
# 用法：
#   python debug_takeoff.py            # 诊断 UAV1
#   python debug_takeoff.py UAV2       # 诊断指定无人机

import airsim
import time
import sys


def check(name, client, tag):
    state = client.getMultirotorState(vehicle_name=name)
    pose = client.simGetObjectPose(name)
    print(f"\n----- [{tag}] {name} 状态 -----")
    print(f"  位置 (NED): ({pose.position.x_val:.2f}, {pose.position.y_val:.2f}, {pose.position.z_val:.2f})")
    print(f"  landed_state: {state.landed_state}")   # Landed=停在地面, Flying=飞行中
    print(f"  is_api_control_enabled: {client.isApiControlEnabled(name)}")
    print(f"  rc_data 是否初始化: {state.rc_data.is_initialized}")
    return pose.position.z_val


def main():
    print("=" * 60)
    print("  AirSim 起飞诊断脚本")
    print("=" * 60)

    client = airsim.MultirotorClient()
    client.confirmConnection()
    print("[OK] 已连接 AirSim\n")

    name = sys.argv[1] if len(sys.argv) > 1 else "UAV1"
    print(f"诊断目标: {name}\n")

    # 1. 起飞前
    z_before = check(name, client, "起飞前")

    # 2. 启用 API 控制
    print(f"\n>>> 步骤1: enableApiControl(True)")
    client.enableApiControl(True, vehicle_name=name)
    time.sleep(0.5)
    print(f"    is_api_control_enabled = {client.isApiControlEnabled(name)}")

    # 3. 解锁
    print(f"\n>>> 步骤2: armDisarm(True)")
    arm_result = client.armDisarm(True, vehicle_name=name)
    print(f"    armDisarm 返回值 = {arm_result}")
    time.sleep(0.5)

    # 4. 起飞（同步，等待结果）
    print(f"\n>>> 步骤3: takeoffAsync().join()")
    try:
        client.takeoffAsync(vehicle_name=name).join(timeout=10)
        print(f"    起飞命令执行完毕")
    except Exception as e:
        print(f"    起飞异常: {e}")

    time.sleep(2)

    # 5. 起飞后
    z_after = check(name, client, "起飞后")

    # 6. 结论
    print(f"\n{'=' * 60}")
    print(f"  诊断结论")
    print(f"{'=' * 60}")
    if z_after < -1.0:
        print(f"  ✓ 成功起飞! Z 从 {z_before:.2f} → {z_after:.2f} (负值 = 高于地面)")
        print(f"  → 说明问题就是缺 enableApiControl/armDisarm，主脚本已同步修复")
    elif z_after != z_before:
        print(f"  ⚠ Z 有变化 {z_before:.2f} → {z_after:.2f}，但幅度不大")
    else:
        print(f"  ✗ 起飞失败，无人机仍在原地 (Z={z_after:.2f})")
        print(f"\n  进一步排查方向：")
        print(f"  1. 打开 UE Output Log 看有没有 AirSim 报错")
        print(f"  2. 尝试下方 Fallback（直接 moveTo 移动）")

    # 7. Fallback：直接 moveTo 到 3 米高
    print(f"\n>>> Fallback: moveToPositionAsync 到 (0,0,-3) 即 3 米高")
    client.moveToPositionAsync(0, 0, -3, 2, vehicle_name=name)
    time.sleep(3)
    pose = client.simGetObjectPose(name)
    z_move = pose.position.z_val
    print(f"    moveTo 后 Z = {z_move:.2f}")
    if z_move < -1.0:
        print(f"  ✓ moveTo 可以起飞！说明应该用 moveTo 代替 takeoff")
    else:
        print(f"  ✗ moveTo 也无法移动，问题更深层（可能是飞控/时钟/碰撞）")


if __name__ == "__main__":
    main()

import airsim
import time

# 1. 连接到 AirSim
client = airsim.MultirotorClient()
client.confirmConnection()

print("=" * 50)
print("连接成功！开始无人机控制")
print("=" * 50)

# 2. 获取控制权
client.enableApiControl(True)
print("✓ 已获取 API 控制权")

# 3. 解锁无人机
client.armDisarm(True)
print("✓ 无人机已解锁")

# 4. 起飞（飞到 3 米高度）
print("起飞中...")
client.takeoffAsync().join()
print("✓ 起飞完成！")

# 5. 悬停 2 秒
time.sleep(2)

# 6. 上升到 10 米高度
print("上升到 10 米高度...")
client.moveToZAsync(-10, 5).join()
print("✓ 到达 10 米高度")

# 7. 向前飞行 20 米
print("向前飞行 20 米...")
client.moveToPositionAsync(20, 0, -10, 5).join()
print("✓ 向前飞行完成")

# 8. 向右飞行 15 米
print("向右飞行 15 米...")
client.moveToPositionAsync(20, 15, -10, 5).join()
print("✓ 向右飞行完成")

# 9. 向后飞行 20 米（返回）
print("向后飞行 20 米...")
client.moveToPositionAsync(0, 15, -10, 5).join()
print("✓ 向后飞行完成")

# 10. 向左飞行 15 米（回到原点上方）
print("向左飞行 15 米...")
client.moveToPositionAsync(0, 0, -10, 5).join()
print("✓ 向左飞行完成")

# 11. 悬停 3 秒
print("悬停中...")
client.hoverAsync().join()
time.sleep(3)

# 12. 降落
print("降落中...")
client.landAsync().join()
print("✓ 降落完成！")

# 13. 锁定无人机
client.armDisarm(False)
print("✓ 无人机已锁定")

# 14. 释放控制权
client.enableApiControl(False)
print("✓ 已释放控制权")

print("=" * 50)
print("飞行任务完成！")
print("=" * 50)
"""
test python environment
"""
import airsim

# connect to the AirSim simulator
client = airsim.MultirotorClient()
client.confirmConnection()

# get control
client.enableApiControl(True)

# unlock
client.armDisarm(True)

# Async methods returns Future. Call join() to wait for task to complete.
client.takeoffAsync().join()

state = client.getMultirotorState(vehicle_name='')
print(state)  # 获取状态信息，然后用强化学习进行训练

client.landAsync().join()

# lock
client.armDisarm(False)

# release control
client.enableApiControl(False)
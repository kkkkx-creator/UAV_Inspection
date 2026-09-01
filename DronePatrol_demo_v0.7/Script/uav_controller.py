# uav_controller.py
# ============================================================
# 多机协同控制 —— Python 端主控制器
# 功能：
#   1. 监听 UDP 9876 端口，接收 UE 发来的 JSON 指令
#   2. 调用 AirSim API 控制无人机（UAV1~UAV4）
#   3. 支持指令：起飞/降落/悬停/移动/编队/一键起飞全部/一键降落全部
#
# 运行方式：
#   1. 先启动 UE 编辑器并点击 Play（确保 AirSim 已运行）
#   2. 然后运行本脚本：python uav_controller.py
#   3. 在 UE 中点击按钮发送指令，观察无人机响应
#
# 依赖安装：
#   pip install airsim
# ============================================================

import socket
import json
import threading
import time
import sys
import math
import traceback

# ============ 配置 ============
UDP_HOST = "127.0.0.1"
UDP_PORT = 9876
UAV_NAMES = ["UAV1", "UAV2", "UAV3", "UAV4"]

# ================================================================
# 编队控制模块（内嵌于此，后续第二阶段可拆分为独立文件）
# ================================================================

def calculate_formation_positions(center, formation_type, num_uavs, spacing=10.0):
    """
    计算编队中每架无人机在 UE 坐标系（X/Y/Z，Z 向上）中的目标位置。

    参数:
        center: (x, y, z) 编队中心点
        formation_type: "V" | "line" | "column" | "diamond" | "grid"
        num_uavs: 无人机数量
        spacing: 无人机间距（米）

    返回:
        [(x, y, z), ...] 每架无人机的目标位置
    """
    cx, cy, cz = center
    positions = []

    if formation_type == "V":
        # V 形编队：领机在前，两侧向后展开
        for i in range(num_uavs):
            offset = (i + 1) // 2 * spacing
            if i == 0:
                # 领机（顶点）
                positions.append((cx + spacing, cy, cz))
            elif i % 2 == 1:
                # 右翼
                positions.append((cx - offset * 0.7, cy + offset, cz))
            else:
                # 左翼
                positions.append((cx - offset * 0.7, cy - offset, cz))

    elif formation_type == "line":
        # 横排编队
        half = (num_uavs - 1) * spacing / 2.0
        for i in range(num_uavs):
            positions.append((cx, cy - half + i * spacing, cz))

    elif formation_type == "column":
        # 纵列编队
        for i in range(num_uavs):
            positions.append((cx - i * spacing, cy, cz))

    elif formation_type == "diamond":
        # 菱形编队
        if num_uavs == 1:
            positions.append((cx, cy, cz))
        elif num_uavs == 2:
            positions.append((cx, cy + spacing, cz))
            positions.append((cx, cy - spacing, cz))
        elif num_uavs == 3:
            positions.append((cx + spacing, cy, cz))       # 前
            positions.append((cx - spacing, cy + spacing, cz))  # 左后
            positions.append((cx - spacing, cy - spacing, cz))  # 右后
        else:
            positions.append((cx + spacing, cy, cz))       # 前
            positions.append((cx, cy + spacing, cz))       # 右
            positions.append((cx - spacing, cy, cz))       # 后
            positions.append((cx, cy - spacing, cz))       # 左
            # 多余的排在后面
            for i in range(4, num_uavs):
                positions.append((cx - spacing - 5.0 * i, cy, cz))

    elif formation_type == "grid":
        # 2x2 网格（适合 4 架无人机）
        half = spacing / 2.0
        offsets = [
            (half, half), (half, -half), (-half, half), (-half, -half)
        ]
        for i in range(min(num_uavs, 4)):
            ox, oy = offsets[i]
            positions.append((cx + ox, cy + oy, cz))
        for i in range(4, num_uavs):
            positions.append((cx + spacing * i, cy, cz))

    else:
        # 默认：一字排开
        print(f"[WARN] Unknown formation type '{formation_type}', using 'line'")
        return calculate_formation_positions(center, "line", num_uavs, spacing)

    return positions


# ================================================================
# 第三阶段：基本协同控制算法（Leader-Follower）
# ================================================================

# 跟随者相对领航者的期望偏移（NED 水平面，单位：米）
# 键 = 队形类型；值 = 列表，第 i 项对应 UAV(i+2) 相对 UAV1 的 (dx, dy)
# 例：UAV2 相对 UAV1 偏移 FORMATION_OFFSETS["V"][0]
FORMATION_OFFSETS = {
    "V":       [(-10, -10), (-10, 10), (-20, 0)],
    "line":    [(0, -10), (0, 10), (0, 20)],
    "column":  [(-10, 0), (-20, 0), (-30, 0)],
    "diamond": [(-10, -10), (-10, 10), (-20, 0)],
}

# 预设巡逻路径（电力巡检矩形航线，NED，负 Z = 高度 15m）
# 可自行改成实际巡检场景的路径点
PATROL_WAYPOINTS = [
    (0, 0, -15),
    (30, 0, -15),
    (30, 30, -15),
    (0, 30, -15),
]


# ================================================================
# 主控制器类
# ================================================================

class UAVController:
    """多机协同主控制器"""

    def __init__(self):
        self.client = None
        self.udp_socket = None
        self.running = False
        self.monitor_thread = None

        # 第三阶段：协同控制状态
        self.coop_thread = None
        # Each cooperative run owns its own Event.  A shared bool makes an old
        # thread observable again if a new run is started immediately after it
        # is stopped.
        self._coop_stop_event = threading.Event()
        self.current_formation = "V"

        # AirSim 的 msgpackrpc 客户端非线程安全（内部 tornado IOLoop 是单例，
        # 多线程并发调用会抛 "IOLoop is already running"）。
        # 用可重入锁串行化所有 RPC 调用。
        self._client_lock = threading.RLock()

    # ----- 坐标定时输出 -----

    def start_position_monitor(self, interval=3.0):
        """每隔 interval 秒输出一次所有无人机坐标（后台线程）"""
        def _loop():
            while self.running:
                time.sleep(interval)
                if not self.running:
                    break
                try:
                    with self._client_lock:
                        print(f"\n[POS] ---- 无人机坐标快照 ----")
                        for name in UAV_NAMES:
                            pose = self.client.simGetObjectPose(name)
                            pos = pose.position
                            print(f"  {name}: ({pos.x_val:.1f}, {pos.y_val:.1f}, {pos.z_val:.1f})")
                        print()
                except Exception as e:
                    print(f"[POS] 读取坐标失败: {e}")

        self.monitor_thread = threading.Thread(target=_loop, daemon=True)
        self.monitor_thread.start()
        print(f"[INFO] 坐标监控已启动（每 {interval} 秒输出一次）\n")

    # ----- AirSim 连接 -----

    def connect_airsim(self):
        """连接 AirSim"""
        import airsim
        print("[INFO] Connecting to AirSim...")
        try:
            self.client = airsim.MultirotorClient()
            self.client.confirmConnection()
            print("[INFO] AirSim connected successfully!")

            # 关键：对每架无人机启用 API 控制并解锁，否则 takeoff/moveTo 会被静默忽略
            print("[INFO] 启用 API 控制 + 解锁电机 ...")
            for name in UAV_NAMES:
                self.client.enableApiControl(True, vehicle_name=name)
                self.client.armDisarm(True, vehicle_name=name)
                print(f"    {name}: apiControl=on, armed=on")
            print()

            # 列出所有无人机并验证（用全局坐标，能看到分散位置）
            print("  [全局坐标 global NED] 注意: Z 向下为正，负 Z = 高度")
            for name in UAV_NAMES:
                pose = self.client.simGetObjectPose(name)
                pos = pose.position
                print(f"  {name}: position=({pos.x_val:.1f}, {pos.y_val:.1f}, {pos.z_val:.1f})")
            print()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to connect to AirSim: {e}")
            print("[HINT] Make sure UE Editor is running with Play mode active AND AirSim plugin is loaded.")
            return False

    # ----- UDP 监听 -----

    def start_udp_listener(self):
        """启动 UDP 监听"""
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.bind((UDP_HOST, UDP_PORT))
        self.udp_socket.settimeout(1.0)  # 1 秒超时，使 `running` 标志能被检查到
        print(f"[INFO] UDP listener started on {UDP_HOST}:{UDP_PORT}")
        print("[INFO] Waiting for commands from UE...\n")

    # ----- 指令解析与执行 -----

    def execute_command(self, cmd_json):
        """解析并执行单条 JSON 指令"""
        cmd_type = cmd_json.get("type", "").strip()
        uav_id = cmd_json.get("uav_id", 0)
        speed = cmd_json.get("speed", 5.0)

        # 获取目标位置
        target = cmd_json.get("target", {})
        tx = target.get("x", 0)
        ty = target.get("y", 0)
        tz = target.get("z", 0)

        # 获取编队信息
        formation_type = cmd_json.get("formation_type", "V")
        fcenter = cmd_json.get("formation_center", {})
        fcx = fcenter.get("x", 0)
        fcy = fcenter.get("y", 0)
        fcz = fcenter.get("z", -10)  # 编队默认高度 10m（AirSim 使用负 Z 向上！）

        # 注意：AirSim 使用 NED 坐标系！
        # UE 坐标系: X(前), Y(右), Z(上)
        # AirSim NED: X(前/北), Y(右/东), Z(下/Down)
        # 但在 UE 内部，AirSim 已经做了转换，直接用 UE 坐标即可
        # 注意：moveToPositionAsync 的 z 在 AirSim 中表示 NED 的 Down，
        # 即负的 UE Z。但在简单使用中，直接映射为高度（负值=高度）

        print(f"\n{'='*60}")
        print(f"[CMD] Type: {cmd_type} | UAV: {uav_id} | Speed: {speed}")
        if cmd_type == "moveTo":
            print(f"      Target: ({tx:.1f}, {ty:.1f}, {tz:.1f})")
        if cmd_type == "formation":
            print(f"      Formation: {formation_type} | Center: ({fcx:.1f}, {fcy:.1f}, {fcz:.1f})")

        try:
            # 协同控制类指令（formationHold/patrol/stopCoop）内部会 join 后台线程，
            # 必须在锁外执行，否则后台线程在等锁、主线程在 join，互相等待卡 2 秒。
            if cmd_type == "formationHold":
                self._start_formation_hold(formation_type, fcx, fcy, fcz, speed)

            elif cmd_type == "patrol":
                self._start_patrol(speed, formation_type)

            elif cmd_type == "stopCoop":
                self._stop_cooperative()

            elif cmd_type == "formationSwitch":
                self.current_formation = formation_type
                print(f"  → 队形切换为: {formation_type}")

            else:
                # 其余指令都调 AirSim client，加锁串行化，避免与后台线程
                # （坐标监控/协同控制）并发 RPC 导致 "IOLoop is already running"
                with self._client_lock:
                    if cmd_type == "takeoff":
                        self._cmd_takeoff(uav_id)

                    elif cmd_type == "land":
                        self._cmd_land(uav_id)

                    elif cmd_type == "hover":
                        self._cmd_hover(uav_id)

                    elif cmd_type == "allTakeoff":
                        self._cmd_all_takeoff()

                    elif cmd_type == "allLand":
                        self._cmd_all_land()

                    elif cmd_type == "allHover":
                        self._cmd_all_hover()

                    elif cmd_type == "moveTo":
                        self._cmd_move_to(uav_id, tx, ty, tz, speed)

                    elif cmd_type == "formation":
                        self._cmd_formation(formation_type, fcx, fcy, fcz, speed)

                    elif cmd_type == "returnHome":
                        self._cmd_return_home(uav_id)

                    else:
                        print(f"[WARN] Unknown command type: '{cmd_type}'")
                        print(f"       Full JSON: {json.dumps(cmd_json, indent=2)}")

        except Exception as e:
            print(f"[ERROR] Command execution failed: {e}")
            traceback.print_exc()

    # ----- 单机指令 -----

    def _cmd_takeoff(self, uav_id):
        name = self._get_vehicle_name(uav_id)
        if not name:
            return
        print(f"  → {name}: Taking off...")
        self.client.takeoffAsync(vehicle_name=name)
        print(f"  ✓ {name}: Takeoff command sent.")

    def _cmd_land(self, uav_id):
        name = self._get_vehicle_name(uav_id)
        if not name:
            return
        print(f"  → {name}: Landing...")
        self.client.landAsync(vehicle_name=name)
        print(f"  ✓ {name}: Land command sent.")

    def _cmd_hover(self, uav_id):
        name = self._get_vehicle_name(uav_id)
        if not name:
            return
        print(f"  → {name}: Hovering...")
        self.client.hoverAsync(vehicle_name=name)
        print(f"  ✓ {name}: Hover command sent.")

    def _cmd_move_to(self, uav_id, x, y, z, speed):
        name = self._get_vehicle_name(uav_id)
        if not name:
            return
        # AirSim 的 moveToPositionAsync 使用 NED 坐标，Z 向下为正（负 Z = 高度）
        # UE 传入的 z 已经是 NED 高度值（例如 z=-10 表示 10 米高），直接透传即可
        print(f"  → {name}: Moving to NED({x:.1f}, {y:.1f}, {z:.1f}) at speed={speed} m/s")
        self.client.moveToPositionAsync(
            x, y, z, speed,
            vehicle_name=name
        )
        print(f"  ✓ {name}: MoveTo command sent.")

    def _cmd_return_home(self, uav_id):
        name = self._get_vehicle_name(uav_id)
        if not name:
            return
        print(f"  → {name}: Returning home...")
        self.client.goHomeAsync(vehicle_name=name)
        print(f"  ✓ {name}: Return home command sent.")

    # ----- 批量指令 -----

    def _cmd_all_takeoff(self):
        print(f"  → All UAVs: Taking off...")
        for name in UAV_NAMES:
            self.client.takeoffAsync(vehicle_name=name)
            print(f"    {name}: ✓")
        print(f"  ✓ All takeoff commands sent!")

    def _cmd_all_land(self):
        print(f"  → All UAVs: Landing...")
        for name in UAV_NAMES:
            self.client.landAsync(vehicle_name=name)
            print(f"    {name}: ✓")
        print(f"  ✓ All land commands sent!")

    def _cmd_all_hover(self):
        print(f"  → All UAVs: Hovering...")
        for name in UAV_NAMES:
            self.client.hoverAsync(vehicle_name=name)
            print(f"    {name}: ✓")
        print(f"  ✓ All hover commands sent!")

    def _cmd_formation(self, formation_type, cx, cy, cz, speed):
        """执行编队飞行"""
        # 计算编队中各机位置
        positions = calculate_formation_positions(
            (cx, cy, cz), formation_type, len(UAV_NAMES), spacing=15.0
        )

        print(f"  → Formation '{formation_type}': center=({cx:.1f}, {cy:.1f}, {cz:.1f})")
        for i, (name, pos) in enumerate(zip(UAV_NAMES, positions)):
            px, py, pz = pos
            print(f"    {name} → ({px:.1f}, {py:.1f}, {pz:.1f})")
            # pz 已经是 NED 高度（负值 = 高度），直接使用
            self.client.moveToPositionAsync(
                px, py, pz, speed,
                vehicle_name=name
            )
        print(f"  ✓ Formation commands sent!")

    # ----- 第三阶段：协同控制算法 -----

    def _start_formation_hold(self, formation_type, cx, cy, cz, speed):
        """启动 Leader-Follower 编队保持（后台线程）"""
        self._stop_cooperative(silent=True)  # 先停掉之前的协同控制
        self.current_formation = formation_type
        stop_event = threading.Event()
        self._coop_stop_event = stop_event
        self.coop_thread = threading.Thread(
            target=self._formation_hold_loop,
            args=((cx, cy, cz), speed, stop_event),
            daemon=True
        )
        self.coop_thread.start()
        print(f"  → 编队保持已启动: {formation_type} @ ({cx:.1f}, {cy:.1f}, {cz:.1f})")

    def _formation_hold_loop(self, leader_target, speed, stop_event):
        """编队保持主循环：领航者飞向目标，跟随者持续跟踪"""
        leader = UAV_NAMES[0]
        followers = UAV_NAMES[1:]

        tx, ty, tz = leader_target
        with self._client_lock:
            self.client.moveToPositionAsync(tx, ty, tz, speed, vehicle_name=leader)
        print(f"  [Hold] 领航者 {leader} → ({tx:.1f}, {ty:.1f}, {tz:.1f})")

        while not stop_event.is_set():
            try:
                offsets = FORMATION_OFFSETS.get(self.current_formation, FORMATION_OFFSETS["V"])
                self._update_followers(leader, followers, offsets, speed)
                # Event.wait() can be interrupted immediately by StopCoop;
                # time.sleep() would always add another 0.3 s to shutdown.
                stop_event.wait(0.3)
            except Exception as e:
                print(f"  [Hold] 编队保持出错: {e}")
                break
        print("  [Hold] 编队保持已停止。")

    def _start_patrol(self, speed, formation_type):
        """启动协同巡逻（领航者沿路径 + 跟随者保持队形）"""
        self._stop_cooperative(silent=True)
        self.current_formation = formation_type
        stop_event = threading.Event()
        self._coop_stop_event = stop_event
        self.coop_thread = threading.Thread(
            target=self._patrol_loop,
            args=(PATROL_WAYPOINTS, speed, stop_event),
            daemon=True
        )
        self.coop_thread.start()
        print(f"  → 协同巡逻已启动，队形: {formation_type}")

    def _patrol_loop(self, waypoints, speed, stop_event):
        """巡逻主循环：领航者逐点飞行，跟随者保持队形"""
        leader = UAV_NAMES[0]
        followers = UAV_NAMES[1:]

        print(f"  [Patrol] 开始巡逻，共 {len(waypoints)} 个路径点")
        while not stop_event.is_set():
            for wp in waypoints:
                if stop_event.is_set():
                    break
                wx, wy, wz = wp
                with self._client_lock:
                    self.client.moveToPositionAsync(wx, wy, wz, speed, vehicle_name=leader)
                print(f"  [Patrol] 领航者 → ({wx:.1f}, {wy:.1f}, {wz:.1f})")

                # 等待领航者到达路径点，期间持续保持队形
                while not stop_event.is_set():
                    with self._client_lock:
                        offsets = FORMATION_OFFSETS.get(self.current_formation, FORMATION_OFFSETS["V"])
                        self._update_followers(leader, followers, offsets, speed)
                        lp = self.client.simGetObjectPose(leader).position
                    # 水平距离 < 2 米认为到达，进入下一个路径点
                    if math.hypot(lp.x_val - wx, lp.y_val - wy) < 2.0:
                        break
                    stop_event.wait(0.3)
        print("  [Patrol] 巡逻已停止。")

    def _update_followers(self, leader, followers, offsets, speed):
        """Leader-Follower 核心：跟随者根据领航者当前位置更新目标"""
        with self._client_lock:
            lp = self.client.simGetObjectPose(leader).position
            lx, ly, lz = lp.x_val, lp.y_val, lp.z_val
            for fname, (dx, dy) in zip(followers, offsets):
                # 跟随者目标 = 领航者当前位置 + 期望偏移
                self.client.moveToPositionAsync(lx + dx, ly + dy, lz, speed, vehicle_name=fname)

    def _stop_cooperative(self, silent=False):
        """停止协同循环，并取消 AirSim 中残留的长时飞行任务。"""
        self._coop_stop_event.set()
        coop_thread = self.coop_thread
        # A later Ctrl+C must not make a new RPC request merely because a
        # controller object exists.  When PIE has already stopped, that RPC
        # would wait on a server which no longer exists.
        had_cooperative_task = coop_thread is not None

        if coop_thread and coop_thread.is_alive():
            coop_thread.join(timeout=2.0)
            if coop_thread.is_alive():
                # Do not take _client_lock here: the cooperative worker may be
                # blocked in an RPC while holding it.  Blocking this UDP thread
                # would prevent any later recovery command from being handled.
                print("[WARN] 协同线程未能在 2 秒内退出；保留线程引用，未发送取消任务请求。")
                return False

        self.coop_thread = None

        # moveToPositionAsync is asynchronous only on the Python side.  Each
        # request runs a long-lived task in AirSim's RPC worker.  Merely ending
        # our loop leaves the final task for every UAV active; when PIE then
        # destroys the RPC server it can wait indefinitely for those workers.
        # Explicitly cancelling all four tasks makes StopCoop a real hand-off
        # back to independent control and keeps End Play responsive.
        if had_cooperative_task and self.client is not None:
            try:
                with self._client_lock:
                    for name in UAV_NAMES:
                        self.client.cancelLastTask(vehicle_name=name)
                print("  → 已取消所有无人机的协同飞行任务。")
            except Exception as e:
                print(f"[WARN] 取消协同飞行任务失败: {e}")

        if not silent:
            print("  → 协同控制已停止。")
        return True

    # ----- 辅助方法 -----

    def _get_vehicle_name(self, uav_id):
        """将 UAV ID 转为名称"""
        if uav_id < 1 or uav_id > len(UAV_NAMES):
            print(f"[ERROR] Invalid UAV ID: {uav_id}. Valid range: 1~{len(UAV_NAMES)}")
            return None

        # 动态匹配：如果 settings.json 中名称不同，修改 UAV_NAMES 列表即可
        return UAV_NAMES[uav_id - 1]

    # ----- 主循环 -----

    def run(self):
        """主运行循环"""
        print("=" * 60)
        print("  Multi-UAV Cooperative Control System")
        print("  Python Controller v1.0")
        print("=" * 60)
        print()

        # 1. 连接 AirSim
        if not self.connect_airsim():
            print("[FATAL] Cannot proceed without AirSim connection.")
            print("        1. Open UE Editor")
            print("        2. Open your level (Map.umap)")
            print("        3. Click Play (Alt+P)")
            print("        4. Run this script again")
            return

        # 2. 启动 UDP 监听
        self.start_udp_listener()

        # 3. 主循环
        self.running = True
        buffer_size = 4096

        # 启动坐标定时输出
        self.start_position_monitor(interval=3.0)

        print("=" * 60)
        print("  Controller is READY. Send commands from UE!")
        print("  Press Ctrl+C to stop.")
        print("=" * 60)

        try:
            while self.running:
                try:
                    data, addr = self.udp_socket.recvfrom(buffer_size)
                    if data:
                        message = data.decode("utf-8").strip()
                        print(f"[UDP] Received {len(data)} bytes from {addr}")
                        try:
                            cmd = json.loads(message)
                            self.execute_command(cmd)
                        except json.JSONDecodeError as e:
                            print(f"[ERROR] Invalid JSON: {e}")
                            print(f"        Raw message: {message}")
                except socket.timeout:
                    # 超时是正常的（非阻塞监听），继续循环
                    continue
                except OSError as e:
                    print(f"[ERROR] Socket error: {e}")
                    break

        except KeyboardInterrupt:
            print("\n[INFO] Ctrl+C received, shutting down...")
        finally:
            self.shutdown()

    def shutdown(self):
        """清理资源"""
        self.running = False
        coop_stopped = self._stop_cooperative(silent=True)
        if self.udp_socket:
            self.udp_socket.close()
            print("[INFO] UDP socket closed.")
        # 关键：主动断开到 AirSim 的 RPC 长连接。
        # msgpackrpc 客户端在 Python 进程里维持一条 TCP 连接 + 后台 IOLoop 线程。
        # 若不主动 close，结束 Play 时 AirSim 的 RPC server 关闭流程会因客户端还连着而阻塞，
        # 导致整个编辑器卡死（协同控制高频调用后尤其明显）。
        if self.client is not None and coop_stopped:
            try:
                # MultirotorClient.client 就是 msgpackrpc.Client，close() 会关闭底层 TCP transport
                self.client.client.close()
                print("[INFO] AirSim RPC connection closed.")
            except Exception as e:
                print(f"[WARN] Failed to close RPC connection: {e}")
        elif self.client is not None:
            print("[WARN] 协同线程仍在 RPC 调用中；由进程退出回收连接，避免并发关闭客户端。")
        print("[INFO] Controller stopped. Goodbye!")


# ================================================================
# 独立测试模式（不依赖 UE）
# ================================================================

def test_mode():
    """独立测试：直接发送起飞指令给所有无人机"""
    import airsim
    print("[TEST] Running test mode — taking off all UAVs...")
    client = airsim.MultirotorClient()
    client.confirmConnection()
    for name in UAV_NAMES:
        print(f"  {name}: Taking off...")
        client.takeoffAsync(vehicle_name=name)
    print("[TEST] All takeoff commands sent. Run 'python uav_controller.py' for interactive mode.")


# ================================================================
# 入口
# ================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_mode()
    else:
        controller = UAVController()
        controller.run()

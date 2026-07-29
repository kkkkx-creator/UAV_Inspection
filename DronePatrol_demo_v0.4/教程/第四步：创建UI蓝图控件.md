很好，多无人机显示问题解决了！接下来我们进行 **第四步：创建 UI 蓝图控件（UMG）**，实现多机状态监控界面。

请确保你已经完成了前面的 C++ 类 `AUAVMonitor` 的编译，并且场景中已放置了该 Actor（拖入关卡即可）。现在开始创建 UI。

---

## 第四步：创建 UI 蓝图控件（UMG）

### 4.1 创建主界面 `WBP_MultiUAVMonitor`

1. 在 Content Browser 中，右键 → **User Interface → Widget Blueprint**，命名为 `WBP_MultiUAVMonitor`。
2. 双击打开设计器。

**设计布局**（参考下图思路）：

- 从左侧 Palette 拖入一个 **Canvas Panel** 作为根节点（自动生成）。
- 拖入一个 **TextBlock**，放在顶部居中，文字为 "多机状态监控"，字体大小 28，颜色白色。
- 拖入一个 **Scroll Box**，命名为 `UAVListScrollBox`，设置位置 (100, 80)，大小 (600, 500)。
- 拖入一个 **Button**，命名为 `RefreshBtn`，放在右下角 (700, 550)，大小 (100, 40)，按钮上放一个 TextBlock 文字 "刷新"。
- 拖入一个 **TextBlock**，命名为 `LastUpdateText`，放在刷新按钮左侧，显示 "最后更新: --:--:--"。

布局完成后记得编译并保存。

### 4.2 创建列表项 `WBP_UAVListItem`

1. 再次创建 Widget Blueprint，命名为 `WBP_UAVListItem`。
2. 设计条目布局（建议高度 120）：

```
Border (根节点，命名为 ItemBorder)
├── HorizontalBox
    ├── Image (StatusIcon，大小 32x32，颜色根据状态变化)
    ├── VerticalBox
        ├── TextBlock (UAVNameText，字体大小 18，粗体)
        ├── TextBlock (BatteryText，文字 "电量: --%")
        ├── TextBlock (PositionText，文字 "位置: (0,0,0)")
        ├── TextBlock (SpeedText，文字 "速度: -- km/h")
        ├── TextBlock (TaskText，文字 "任务: -- | 进度 --%")
        └── TextBlock (FaultText，文字 "�7�2 故障信息"，颜色红色，默认隐藏)
```

- 为每个 TextBlock 和 Image 设置合适的变量名称（在 Details 面板中可设置 "Is Variable" 为 true），以便在蓝图中动态修改。
- 比如 `UAVNameText`、`BatteryText`、`PositionText`、`SpeedText`、`TaskText`、`FaultText`、`StatusIcon`、`ItemBorder`（记得将 Border 的 Brush Color 设置为可动态修改）。

### 4.3 在 `WBP_UAVListItem` 中创建设置状态的函数

在 `WBP_UAVListItem` 的 **Graph** 中：

1. 点击 **Functions** 旁边的 `+` 新建函数，命名为 `SetUAVState`。
2. 为函数添加一个输入参数：类型为 **Structure**，搜索 `FUAVState`，命名为 `InState`。
   > 如果没有找到 `FUAVState`，请确保已经编译过 C++ 代码，并重启编辑器。然后可以在蓝图变量类型中看到自定义结构体。
3. 打开函数图表，拖出 `InState` 引脚 → **Break FUAVState**，获得各个字段。
4. 根据字段设置 UI 控件的文本和颜色：

   - **设置无人机名称**：`UAVNameText->Set Text` = `"UAV " + IntToString(UAVId)`。
   - **设置电量**：`BatteryText->Set Text` = `"电量: " + FloatToString(BatteryPercent) + "%"`。
     如果 `BatteryPercent < 20`，将 `BatteryText` 颜色设为橙色。
   - **设置位置**：`PositionText->Set Text` = `"位置: (" + FloatToString(Position.X) + ", " + FloatToString(Position.Y) + ", " + FloatToString(Position.Z) + ")"`。
   - **设置速度**：`SpeedText->Set Text` = `"速度: " + FloatToString(SpeedKmh) + " km/h"`。
   - **设置任务**：`TaskText->Set Text` = `"任务: " + TaskType + " | " + FloatToString(TaskProgress * 100) + "%"`。
   - **故障处理**：
     - 如果 `bHasFault == true`：设置 `FaultText` 可见，内容为 `"�7�2 " + FaultType`；设置 `ItemBorder` 的 Brush Color 为红色；`StatusIcon` 颜色红色。
     - 否则如果 `BatteryPercent < 20`：设置 `ItemBorder` 颜色为黄色，`StatusIcon` 黄色，故障文本隐藏。
     - 否则：设置 `ItemBorder` 颜色为绿色，故障文本隐藏。

   注意：修改 Border 的 Brush Color 需要先获取 Border 的 Brush 对象，然后设置 Tint Color。更简单的方法是：在 Border 的 Details 中，将 Brush Color 绑定到一个变量，然后在蓝图中设置该变量。或者直接使用 `Set Brush Color` 节点（需将 Border 提升为变量）。

### 4.4 在主界面中动态添加列表项

打开 `WBP_MultiUAVMonitor` 的 **Graph**。

1. **添加变量**：
   - `UAVMonitorRef`，类型为 `AUAVMonitor`（对象引用）。
   - `UAVItemsMap`，类型为 `Map`，键类型 `Int32`，值类型 `WBP_UAVListItem`（用于快速查找已有的条目）。

2. **在 Event Construct 中**：
   - 获取场景中的 `AUAVMonitor` 实例：
     - 使用 `Get All Actors of Class`（类选择 `AUAVMonitor`），然后取第一个元素，并 `Cast to AUAVMonitor`，赋值给 `UAVMonitorRef`。
   - 绑定委托事件：`UAVMonitorRef` 的 `OnUAVStateUpdated` → 连接到自定义事件 `OnStateUpdated`（你需要新建这个自定义事件）。
   - 同时，调用 `UAVMonitorRef->ForceUpdate()` 立即获取一次状态。

3. **创建自定义事件 `OnStateUpdated`**，输入参数 `NewState`（类型 `FUAVState`）。
   - 检查 `UAVItemsMap` 中是否已有该 `UAVId` 的条目：
     - 如果有，直接调用该条目的 `SetUAVState`。
     - 如果没有，则创建一个新条目：
       - `Create Widget` (Class: `WBP_UAVListItem`) → 存入局部变量 `NewItem`。
       - 调用 `NewItem->SetUAVState(NewState)`。
       - 将 `NewItem` 添加到 `UAVListScrollBox` 中（使用 `Add Child` 节点）。
       - 将 `NewItem` 添加到 `UAVItemsMap` 中，键为 `NewState.UAVId`。
   - 更新 `LastUpdateText` 的文本为当前时间（可用 `Now` 节点格式化）。

4. **RefreshBtn 的点击事件**：
   - 调用 `UAVMonitorRef->ForceUpdate()`。

编译并保存所有蓝图。

---

### 4.5 显示 UI 到屏幕

你需要确保 UI 被添加到视口。方法：在 **Player Controller 蓝图** 的 `BeginPlay` 中创建并添加。

如果你还没有 Player Controller 蓝图：
1. 右键 → Blueprint Class → 父类 `PlayerController`，命名为 `BP_DronePlayerController`。
2. 打开 `BP_DronePlayerController`，在 `Event BeginPlay` 中：
   - `Create Widget` (Class: `WBP_MultiUAVMonitor`) → 提升为变量 `MonitorUI`。
   - `Add to Viewport`。
3. 设置默认 Player Controller：编辑 → 项目设置 → Maps & Modes → Default Player Controller Class → 选择 `BP_DronePlayerController`。

---

### 4.6 运行测试

1. 确保关卡中已放置 `AUAVMonitor` Actor（如果还没有，从 C++ Classes 拖入场景任意位置）。
2. 点击 Play 运行。
3. 你应该看到 UI 界面显示四个无人机的实时状态，并且每 0.5 秒自动更新。点击刷新按钮可手动刷新。

---

## 可能出现的问题及解决

| 问题 | 解决方法 |
|------|----------|
| 蓝图中找不到 `FUAVState` 结构体 | 重新编译 C++ 代码，关闭编辑器再打开。 |
| 委托 `OnUAVStateUpdated` 没有触发 | 检查 `AUAVMonitor` 是否在场景中；检查 `UpdateAllUAVStates` 中是否调用了 `OnUAVStateUpdated.Broadcast`。 |
| UI 列表不显示任何条目 | 确认 `AUAVMonitor` 的 `UpdateAllUAVStates` 被定时调用（输出日志查看）。也可能是因为 `WBP_UAVListItem` 的 `SetUAVState` 函数未正确设置控件。 |
| 所有无人机列表项都重叠在一起 | 检查 `UAVListScrollBox` 是否有自动布局子控件功能（默认 Vertical Box 会自动排列）。确保添加 Child 时顺序正确。 |

---

## 下一步

成功看到 UI 显示实时状态后，你可以继续开发：
- **任务管理模块**：在 `FUAVState` 中已有字段，你可以在 `UpdateAllUAVStates` 中填充真实任务数据。
- **故障模拟界面**：点击故障条目可以弹出窗口，展示重分配任务的过程。
- **控制板**：为 UI 添加按钮，通过 AirSim API 控制选中的无人机（上下左右等）。

如果遇到任何具体问题（例如 UI 不显示、列表不更新等），请提供截图或错误日志，我会继续协助。
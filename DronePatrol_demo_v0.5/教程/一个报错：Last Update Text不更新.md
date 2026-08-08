>我运行之后确实看到了UI 界面显示四个无人机的实时状态，并且每 0.5 秒自动更新。但是更新时间一直保持不变🤔。在停止运行之后出现如图的报错。

---

你遇到的“最后更新时间”不更新以及运行停止后的报错，是因为 `Set Input Mode UI Only` 节点在关卡蓝图中没有指定目标 Player Controller，导致空引用错误，从而中断了后续代码执行（包括更新时间文本的逻辑）。

---

## 问题原因

在你的关卡蓝图中，`Set Input Mode UI Only` 节点缺少 **Player Controller 目标**，如图中红线所示。这个节点需要知道“哪个玩家控制器”要切换输入模式。没有目标时，它会尝试访问空对象，导致蓝图运行时错误，并跳过该节点之后的任何逻辑（包括更新 `LastUpdateText` 的代码）。

---

## 解决方案：修复关卡蓝图中的节点连接

### 步骤 1：打开关卡蓝图

1. 点击 UE4 顶部菜单 **蓝图 (Blueprint)** → **打开关卡蓝图 (Open Level Blueprint)**。
2. 找到你之前创建的 UI 显示逻辑（在 `Event BeginPlay` 后面）。

### 步骤 2：修改节点连接（关键）

当前你的节点顺序可能是：
```
Event BeginPlay → Create Widget → Add to Viewport → Set Input Mode UI Only → ...
```

**错误原因**：`Set Input Mode UI Only` 的 **`Player Controller`** 目标引脚没有连接，导致空引用。

**正确做法**：在 `Set Input Mode UI Only` 前面插入一个 **`Get Player Controller`** 节点，将其返回值连接到 `Set Input Mode UI Only` 的 **`Player Controller`** 目标引脚。

#### 修改后的正确连接顺序：

```
Event BeginPlay
    ↓
Create Widget (Class: WBP_MultiUAVMonitor) → Return Value 提升为变量 MonitorUI
    ↓
Add to Viewport (Target 连接到 Create Widget 的返回值)
    ↓
Get Player Controller (Index 0) → Return Value 连接到 Set Input Mode UI Only 的 Player Controller 目标引脚
    ↓
Set Input Mode UI Only (In Widget to Focus 连接到 MonitorUI，勾选 bShow Mouse Cursor)
    ↓
(可选) Set Show Mouse Cursor (Target 连接到同一个 Player Controller，Visible = true)
```

> **注意**：如果你在 `Set Input Mode UI Only` 中已经勾选了 **`bShow Mouse Cursor`**，就不需要再额外添加 `Set Show Mouse Cursor` 节点了。

### 步骤 3：检查 `WBP_MultiUAVMonitor` 中的更新时间逻辑

如果修复后时间文本仍然不更新，请检查 `WBP_MultiUAVMonitor` 蓝图中的 `OnStateUpdated` 事件：

1. 打开 `WBP_MultiUAVMonitor` 的 **事件图表 (Event Graph)**。
2. 找到 `OnStateUpdated` 自定义事件（或委托绑定的事件）。
3. 确认其中是否有更新 `LastUpdateText` 的节点。应该类似这样：

```
OnStateUpdated (输入 NewState)
    ↓
(更新列表项逻辑...)
    ↓
Get Current Time (或 Now 节点) → 格式化为字符串 → Set Text (LastUpdateText)
```

如果这个更新逻辑放在了错误的位置（**例如只在创建新条目时更新，这个Last Update Text的更新是不论branch的结果为真还是为假都要执行**），会导致时间不更新。应该**每次 `OnStateUpdated` 被调用时都更新**一次时间文本。

---

## 完整的修复方案（推荐）

### 方案 A：使用 `Set Input Mode Game and UI`（更稳定）

这个模式允许同时接收游戏控制（键盘/手柄）和 UI 点击，不容易产生空引用错误，且不需要 Player Controller 目标。

```
Event BeginPlay
    ↓
Create Widget → Add to Viewport
    ↓
Set Input Mode Game and UI (In Widget to Focus 连接到 UI，勾选 bShow Mouse Cursor)
```

> 这个节点不需要 Player Controller 目标，所以不会出现空引用错误。

### 方案 B：保留 `Set Input Mode UI Only` 但正确连接目标

按照上面的步骤 2 修复，连接 `Get Player Controller`。

---

## 验证是否修复

1. 重新编译并保存关卡蓝图。
2. 点击 **Play** 运行。
3. 观察界面右下角的“最后更新时间”是否每 0.5 秒自动更新（时间数字应该变化）。
4. 点击“刷新”按钮，时间也应该更新。
5. 停止运行，检查输出日志中是否还有红色报错。

---

## 其他可能的辅助原因

如果上述修复后更新时间仍然不动，可能是以下原因：

| 现象 | 可能原因 | 解决方法 |
|------|----------|----------|
| 时间文本完全不变化 | `LastUpdateText` 的变量引用丢失 | 在 `WBP_MultiUAVMonitor` 设计器中，确保 `LastUpdateText` 被提升为变量（在 Details 中勾选 Is Variable）。 |
| 时间只变化一次 | 委托只触发了一次 | 检查 `AUAVMonitor` 的定时器是否正确设置为循环（`true`）。 |
| 报错仍然存在 | 有其他节点也缺少目标 | 检查 `Set Show Mouse Cursor` 是否也缺少 Target，同样连接 `Get Player Controller`。 |

---

## 如果你还想保留 AirSim 的 WASD 控制

如果你发现修复后 WASD 键盘控制视角失效了，那是因为 `Set Input Mode UI Only` 把输入全部给了 UI。此时，请改用 **`Set Input Mode Game and UI`**，它会同时允许游戏和 UI 接收输入，这样无人机视角控制（WASD/F 键等）不会丢失。

---

## 总结

1. **根本原因**：`Set Input Mode UI Only` 缺少 Player Controller 目标，导致空引用错误，中断了后续代码执行。
2. **修复方法**：连接 `Get Player Controller` 到其目标引脚，或改用 `Set Input Mode Game and UI`。
3. **验证**：运行后观察更新时间是否变化，停止后无报错即成功。

如果你按上述步骤修复后还有问题，请截图你的关卡蓝图节点连接，我可以更精确地帮你定位。
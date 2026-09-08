---
area: "[[Unreal Engine]]"
tags: [UE5, AI, Navigation, Recast, Detour, Crowd, 避障, 源码分析]
created: 2026-09-08
source_engine: UE 5.4.4
---

# UE5 DetourCrowd 群体避障：从 UE Gameplay AI 到底层速度采样的源码架构

> **分析源码版本**：当前引擎仓库 `F:\10_Projects\RA\AEngine`，UE **5.4.4**。  
> **核心结论**：UE 的 Crowd 并不是用 Detour 接管角色运动；它把 Detour 用作一个**集中式的局部导航、转向与速度决策器**。`UCrowdFollowingComponent` 将 UE 路径跟随输入交给 `UCrowdManager`，后者驱动 `dtCrowd` 批量求解；最终仍由 `UCharacterMovementComponent` 执行速度与碰撞运动。

---

## 1. 模块定位：DetourCrowd 解决什么问题？

普通 `UPathFollowingComponent` 的工作模型是：AI 沿 NavMesh 路径点或路径段移动。多名 AI 共用狭窄通道时，单个 AI 虽能找到全局可达路径，却不知道附近其他 AI 的局部速度、身体半径和墙面边界，常出现：

- 迎面相撞、互相卡住；
- 多人挤在门口或拐角形成局部死锁；
- 通过狭窄处时来回抖动；
- 单纯 RVO 推开角色后，角色偏离 NavMesh，甚至被挤入不可走区域。

DetourCrowd 的职责是：

```text
全局寻路（Recast / A*）
  → 提供 poly corridor，即“可走多边形序列”
  → DetourCrowd 在 corridor 内产生局部转向与安全速度
  → UE MovementComponent 实际移动角色
```

它不是完整的“群体战略规划器”，也不是碰撞物理系统。其强项是：**在 NavMesh 约束下，让一批正在移动的 agent 做局部避障和路径跟随。**

---

## 2. 引擎架构位置

```text
UWorld / Game Thread
  └─ UNavigationSystemV1
      ├─ ARecastNavMesh
      │   └─ dtNavMesh / dtNavMeshQuery
      │
      └─ UCrowdManager                         [UE 世界的集中调度器]
          ├─ ActiveAgents: TMap<Interface, Data>
          ├─ dtCrowd                            [Detour 的批量求解器]
          │   ├─ dtPathQueue                    [路径请求/增量寻路]
          │   ├─ dtProximityGrid                [近邻粗筛]
          │   ├─ dtLocalBoundary / SharedBoundary [墙体边界]
          │   ├─ dtPathCorridor                 [每 agent 的 poly corridor]
          │   └─ dtObstacleAvoidanceQuery       [速度候选采样]
          │
          └─ ApplyVelocity()
              └─ UCrowdFollowingComponent
                  └─ UPathFollowingComponent
                      └─ UNavMovementComponent / UCharacterMovementComponent
                          └─ Sweep、碰撞、重力、RootMotion、网络移动

AAIController
  └─ PathFollowingComponent
      └─ UCrowdFollowingComponent               [启用 Crowd 后替换默认组件]
```

相关源码：

```text
Engine/Source/Runtime/AIModule/
  Classes/DetourCrowdAIController.h
  Private/DetourCrowdAIController.cpp
  Classes/Navigation/CrowdManager.h
  Private/Navigation/CrowdManager.cpp
  Classes/Navigation/CrowdFollowingComponent.h
  Private/Navigation/CrowdFollowingComponent.cpp

Engine/Source/Runtime/Navmesh/
  Public/DetourCrowd/DetourCrowd.h
  Private/DetourCrowd/DetourCrowd.cpp
  Private/DetourCrowd/DetourObstacleAvoidance.cpp
```

---

## 3. 三个 UE 层核心类

| 类 | 一句话职责 | 关键设计 |
|---|---|---|
| `ADetourCrowdAIController` | 将默认 PathFollowingComponent 替换为 Crowd 版本的便捷 AIController | 纯构造期组件替换 |
| `UCrowdFollowingComponent` | 将 UE 寻路/移动接口与 Detour agent 双向适配 | Adapter；继承 `UPathFollowingComponent` 并实现 `ICrowdAgentInterface` |
| `UCrowdManager` | 管理 World 内 agent，并统一调度 `dtCrowd` | Mediator / Facade / 批量求解器适配层 |

### 3.1 ADetourCrowdAIController：只是一个配置入口

源码：`AIModule/Private/DetourCrowdAIController.cpp`

```cpp
ADetourCrowdAIController::ADetourCrowdAIController(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer.SetDefaultSubobjectClass<UCrowdFollowingComponent>(
        TEXT("PathFollowingComponent")))
{
}
```

这个类没有 Crowd 算法。它通过 Unreal 的默认子对象替换机制，把 `AAIController` 原本的 `PathFollowingComponent` 换成 `UCrowdFollowingComponent`。

因此项目中也可以不继承该类，而是在自定义 AIController 构造函数里使用同样的 `SetDefaultSubobjectClass`。

### 3.2 UCrowdFollowingComponent：双向适配器

它的两个方向：

```text
上行：UE Path Following → DetourCrowd
  MoveTo / SetMoveSegment / Pause / Resume / Abort
    → SetAgentMovePath / SetAgentMoveTarget / ClearAgentMoveTarget

下行：DetourCrowd → UE Movement
  dtCrowd 算出 nvel、next corner
    → ApplyCrowdAgentVelocity
    → RequestPathMove / RequestDirectMove
    → CharacterMovement 实际移动
```

它不是单纯的“避障组件”，而是把原有路径跟随状态机保留下来，同时把局部 steering 的决定权交给 Crowd。

### 3.3 UCrowdManager：集中式仲裁者

`UCrowdManager` 是 `UNavigationSystemV1` 维度的对象；同一个 World 的 Crowd agent 在此汇聚。

集中式设计的原因：局部避障天然需要同时看见邻居。若每个 Agent 独立做逻辑：

- 每个 Agent 都要重复查询其他 Agent；
- 没有统一的邻居筛选和墙面边界缓存；
- 难以让所有 Agent 在同一时刻基于一致快照求解；
- 不能利用连续数组、空间网格和批量 NavMesh 查询。

因此 Detour 的 `dtCrowd` 使用固定容量 Agent 池及批处理数据结构；UE 侧用 `ActiveAgents` 保存“组件对象 ↔ Detour 索引”的映射。

---

## 4. 生命周期：注册、移动、注销

### 4.1 注册

```text
UCrowdFollowingComponent::Initialize()
  → RegisterCrowdAgent()
  → UCrowdManager::RegisterAgent(ICrowdAgentInterface*)
  → UCrowdManager::AddAgent()
  → dtCrowd::addAgent()
  → 返回固定 Agent Pool 中的 AgentIndex
```

源码重点：

- `CrowdFollowingComponent.cpp:460`：组件初始化时注册；如果导航系统尚未初始化，会监听 `OnNavigationInitDone`，避免 BeginPlay / Possess 时序导致注册失败。
- `CrowdManager.cpp:685`：`AddAgent()` 构造 `dtCrowdAgentParams`，坐标转为 Recast 坐标后调用 `DetourCrowd->addAgent()`。

```cpp
AgentData.AgentIndex = DetourCrowd->addAgent(&RcAgentPos.X, Params, DefaultFilter);
```

`AgentIndex` 是 Handle，而不是长期持有 `dtCrowdAgent*` 指针。这符合 Detour 固定 Agent 池的对象池模型。

### 4.2 取消注册

```text
UCrowdFollowingComponent::Cleanup / BeginDestroy
  → UCrowdManager::UnregisterAgent()
  → UCrowdManager::RemoveAgent()
  → dtCrowd::removeAgent(AgentIndex)
```

源码：

```text
CrowdFollowingComponent.cpp:485~509
CrowdManager.cpp:715~721
```

必须成对处理。否则 `dtCrowd` 内仍会把已经被销毁的 UE 对象视为 active agent。

### 4.3 暂停、恢复与中止

| UE PathFollowing 行为 | Crowd Manager 调用 | Detour 语义 |
|---|---|---|
| `AbortMove` | `ClearAgentMoveTarget` | 清除目标，停止 Crowd 移动请求 |
| `PauseMove` | `PauseAgent` | agent 进入等待/暂停状态 |
| `ResumeMove` | `ResumeAgent` | 恢复并可选强制 replan |
| `OnPathFinished` | `ClearAgentMoveTarget` | 结束目标请求 |

这说明 Crowd 并未绕过 UE 的 PathFollowing 状态机，而是作为该状态机的求解后端。

---

## 5. 发起 MoveTo 后的调用链

### 5.1 NavMesh 路径：把长 corridor 切成小段

`UCrowdFollowingComponent::SetMoveSegment()` 是关键入口之一：

```text
AIController::MoveTo...
  → UPathFollowingComponent 取得 FNavMeshPath
  → UCrowdFollowingComponent::SetMoveSegment()
  → 从 FNavMeshPath::PathCorridor 读取 poly ref 序列
  → 截取当前的一段 corridor
  → UCrowdManager::SetAgentMovePath()
  → dtCrowd::setAgentCorridor / requestMoveTarget
```

源码：`CrowdFollowingComponent.cpp:762` 起。

UE 特意不依赖常规 `PathPoints`：Crowd 模式下路径后处理会被禁用，`PathPoints` 可能只剩起终点；真正的完整路线在 `FNavMeshPath::PathCorridor` 中。

当前实现每段默认最多 **15 个 poly**：

```cpp
const int32 PathPartSize = 15;
```

这是为了避免 Crowd 只在过长路径的局部前缀中做有限搜索而陷入局部问题。到达当前段末尾后，PathFollowing 再推进下一段。

### 5.2 Direct Path：没有 NavMesh corridor 时

若拿到的是 `FAbstractNavigationPath`（直线移动），组件不使用完整 crowd path-corridor；它把目标方向通过：

```text
UCrowdManager::SetAgentMoveDirection()
  → dtCrowd::requestMoveVelocity()
```

交给 Crowd 做“速度请求”式局部避障。

---

## 6. 每帧总调用链：UCrowdManager::Tick

> 默认运行在 **Game Thread**。该实现没有把整套 Crowd 求解拆到 TaskGraph；所有 agent 在一次 Tick 中基于同一批位置、速度快照被统一更新。

源码：`AIModule/Private/Navigation/CrowdManager.cpp:231`

```text
UCrowdManager::Tick(DeltaTime)
  │
  ├─ dtCrowd::cacheActiveAgents()
  │
  ├─ 对每个 UE Agent：PrepareAgentStep()
  │    ├─ UE 坐标 → Recast 坐标
  │    ├─ 写入 dtCrowdAgent::npos
  │    ├─ 写入 dtCrowdAgent::vel
  │    └─ 更新 params.maxSpeed
  │
  ├─ dtCrowd::updateStepCorridor()        [先用上帧积分结果贴回 NavMesh]
  ├─ dtCrowd::updateStepPaths()           [路径有效性、异步请求、拓扑优化]
  ├─ dtCrowd::updateStepProximityData()   [空间网格、近邻、墙边界]
  │    └─ UCrowdManager::PostProximityUpdate()
  ├─ dtCrowd::updateStepNextMovePoint()   [string pulling、角点、Off-mesh]
  │    └─ UCrowdManager::PostMovePointUpdate()
  ├─ dtCrowd::updateStepSteering()        [期望速度 dvel]
  ├─ dtCrowd::updateStepAvoidance()       [候选速度采样 → nvel]
  ├─ dtCrowd::updateStepMove()             [可选位置积分与推开]
  ├─ UCrowdManager::UpdateAgentPaths()    [UE SmartLink / Poly 状态协作]
  ├─ dtCrowd::updateStepOffMeshVelocity()
  │
  └─ 对每个 simulated agent：ApplyVelocity()
       └─ UCrowdFollowingComponent::ApplyCrowdAgentVelocity()
          └─ MovementComponent 真实移动
```

这里最重要的边界是：

```text
Tick 开始：UE 真实位置、真实速度 → Detour 的 npos / vel
Tick 结束：Detour 算出的 nvel、next corner → UE MovementComponent
```

`UCrowdManager` 本质上就是两个运行时模型间每帧的同步层。

---

## 7. dtCrowd 内部流水线深度解析

### 7.1 Step 0：路径走廊回贴 `updateStepCorridor`

源码：`DetourCrowd.cpp:1670`

```text
dtCrowdAgent::npos
  → dtPathCorridor::movePosition()
  → 在当前 NavMesh corridor 中移动并投影到有效位置
  → 获得约束后的 npos
```

目的：即使上一步的局部避障 / MovementComponent 移动导致位置轻微偏离，也尽量把 Crowd 的导航状态保持在合法 corridor 中。

当 agent 没有位置目标，只是速度目标时，会把 corridor 截短为当前 poly，避免错误继承旧路径。

### 7.2 Step 1：路径有效性与再规划 `updateStepPaths`

源码：`DetourCrowd.cpp:1235`

```text
checkPathValidity()
  → 检查当前 corridor / target poly 是否仍有效

updateMoveRequest()
  → 处理 requestMoveTarget 的排队与增量寻路

updateTopologyOptimization()
  → 按时间间隔尝试改善 corridor 的 poly 路径结构
```

Detour 的路径并非每帧完整同步 A*；`dtPathQueue` 会做增量寻路，避免大量 agent 同一帧触发全量路径计算。

### 7.3 Step 2：近邻和墙面数据 `updateStepProximityData`

源码：`DetourCrowd.cpp:1247`

```text
所有 active agents
  → 插入 dtProximityGrid（2D 空间网格）

对每个 walking agent
  ├─ SharedBoundary / LocalBoundary 缓存附近 NavMesh 边缘
  └─ getNeighbours() 在网格中筛出附近 agent
```

`collisionQueryRange` 决定 agent 感知其他 agent 和墙的范围。它越大：

- 越早开始让行；
- 可见邻居越多；
- 避障更平滑但 CPU 开销更高；
- 在拥挤环境中过大可能让 agent 过度保守。

UE 还对墙体边界加了共享缓存 `dtSharedBoundary`，避免每个 agent 重复做相同 NavMesh 邻域查询。

### 7.4 Step 3：下一个转向点 `updateStepNextMovePoint`

源码：`DetourCrowd.cpp:1316`

主要工作：

1. `dtPathCorridor::findCorners()` 对 poly corridor 做 string pulling，得到局部直线路径角点；
2. 依据 `DT_CROWD_OPTIMIZE_VIS`，尝试通过可见性 raycast 跳过冗余角点；
3. 检查是否接近 Off-mesh Link，准备切入 Off-mesh 状态。

UE 扩展：

- `DT_CROWD_OPTIMIZE_VIS_MULTI`：一次检查多个候选转角；
- `DT_CROWD_OFFSET_PATH`：以 Agent 半径为尺度偏移拐角，减轻贴墙切角；
- `m_raycastSingleArea`：限制可见性优化不可跨 Area Type，避免走捷径破坏区域代价语义。

### 7.5 Step 4：期望速度 `updateStepSteering`

源码：`DetourCrowd.cpp:1432`

先产生“不考虑即时碰撞”时想走的速度 `dvel`：

```text
有位置目标：朝下一个 corner
有速度目标：直接采用 target velocity
```

可选策略：

- `DT_CROWD_ANTICIPATE_TURNS`：根据下一个角点提前转弯，减少直角折线运动；
- `DT_CROWD_SLOWDOWN_AT_GOAL`：靠近终点时减速；
- `DT_CROWD_SEPARATION`：依据附近 agent 加一个分离偏置，避免“虽然不碰撞但贴得太近”。

分离不是最终避障。它是对期望速度的柔性偏置；真正针对潜在撞击时间的选择在下一步完成。

### 7.6 Step 5：速度避障 `updateStepAvoidance`

源码：`DetourCrowd.cpp:1533`

```text
对每个 walking agent：
  ├─ 邻居 agent → dtObstacleAvoidanceQuery::addCircle()
  ├─ NavMesh 墙段 → addSegment()
  └─ sampleVelocity(...)
       输入：当前位置、半径、当前速度 vel、期望速度 dvel
       输出：新速度 nvel
```

这里的输入障碍分两类：

```text
圆形动态障碍：其他 Crowd Agent
线段静态障碍：LocalBoundary 中的 NavMesh 边缘 / 墙
```

因此它比只看角色的 RVO 更能维持“沿着可走区域运动”的约束。

### 7.7 Step 6：可选积分和位置推开 `updateStepMove`

源码：`DetourCrowd.cpp:1591`

该步骤：

1. 按 `nvel` 对 `npos` 积分；
2. 至多 4 轮处理相交圆的重叠位移；
3. 通过平均 displacement 把仍然重叠的 agent 分开。

UE 通过 `UCrowdManager::bResolveCollisions` 控制是否调用此步骤。

> **默认更安全的做法是 `bResolveCollisions=false`。**
>
> 这是因为 UE 通常仍希望 `CharacterMovementComponent` 执行碰撞 Sweep、重力、Root Motion、网络平滑等。若 Crowd 直接写位置，又由 CMC 做碰撞，两个系统可能争夺位置控制权，表现为抖动、穿透、卡墙或网络不一致。

### 7.8 Step 7：Off-mesh Link

Detour 原始流程包含 `updateStepOffMeshAnim()`；UE Tick 使用 `updateStepOffMeshVelocity()`，注释明确指出 UE 版本基于速度与距离检查，而不是原始固定时间动画逻辑。

这样 UE 可以继续让 PathFollowing / MovementComponent / SmartLink 逻辑参与跳跃、门、梯子或自定义链接的实际执行。

---

## 8. 速度采样算法：dtObstacleAvoidanceQuery

### 8.1 核心思想

Detour 不直接求解析式的“唯一最佳避障速度”，而是在速度空间中采样候选速度：

```text
期望速度 dvel 周围生成候选 vcand
  → 预测该候选速度与圆形邻居、墙线段的碰撞时间
  → 对每个候选速度打分
  → 选择总 penalty 最小的 nvel
```

这是一种“采样式速度障碍 / RVO 风格”的局部规划方法。

### 8.2 候选速度评分

源码：`DetourObstacleAvoidance.cpp:323`，`processSample()`。

总惩罚大意：

```text
penalty =
  weightDesVel × 与期望速度 dvel 的距离
+ weightCurVel × 与当前速度 vel 的距离
+ weightSide   × 侧向偏置
+ weightToi    × 即将碰撞的时间代价
```

对应代码：

```cpp
vpen = weightDesVel * distance(vcand, dvel)
vcpen = weightCurVel * distance(vcand, vel)
spen = weightSide * side
tpen = weightToi * (1 / (0.1 + tmin / horizTime))
```

解释：

| 项 | 意义 | 调高后的表现 |
|---|---|---|
| `weightDesVel` | 贴近路径期望速度 | 更坚定向目标走，避让更弱或更晚 |
| `weightCurVel` | 保持速度连续 | 更平滑，减少突然急转或急停 |
| `weightSide` | 侧向选择偏置 | 减少双方左右摇摆，但可能形成偏侧行为 |
| `weightToi` | 惩罚即将发生的碰撞 | 更积极提前避让 |
| `horizTime` | 碰撞预测时间窗 | 大：更早避让；小：更临近才反应 |

### 8.3 圆形障碍的相对速度

对邻居 agent，`processSample()` 用候选速度、自己当前速度和邻居当前速度构造相对速度，并通过 sweep circle-circle 估计最早碰撞时间。

这就是“动态障碍”部分：它不是只看邻居当前位置，也考虑邻居正在往哪走。

### 8.4 墙段约束

对于 NavMesh 边缘：

- 若候选速度会立即撞上墙段，直接丢弃该候选；
- 若非常接近边界，UE 的代码会把候选判为无效；
- 对 `DT_CROWD_BOUNDARY_IGNORE` 墙段允许在一定条件下弱化影响。

这使 Crowd 的局部避障不只是“角色相互推开”，还会避开 NavMesh 可行走区域之外的边界。

### 8.5 Adaptive Sampling

`sampleVelocityAdaptive()` 的策略：

```text
1. 以 desired velocity 朝向建立初始圆形 / 环形候选图样；
2. 第一轮在较大范围采样；
3. 找到当前最佳候选；
4. 缩小采样半径；
5. 重复 depth 次，逐层精化。
```

控制成本的关键参数：

```text
adaptiveDivs × adaptiveRings × adaptiveDepth
```

提高它们会使速度选择更精细，但每个 agent 每帧的候选数上升，拥挤人群的成本会快速放大。

---

## 9. UE → Detour 数据映射

`UCrowdManager::GetAgentParams()` 位于 `CrowdManager.cpp:723`。

| UE 数据 | dtCrowdAgentParams 字段 | 用途 |
|---|---|---|
| Capsule 半径 | `radius` | 邻居碰撞、墙面避让、路径偏移 |
| Capsule 高度 | `height` | 近邻垂直范围判断 |
| 最大移动速度 | `maxSpeed` | 每帧 `PrepareAgentStep()` 更新 |
| Collision Query Range | `collisionQueryRange` | 邻居与墙边界感知范围 |
| Path Optimization Range | `pathOptimizationRange` | 可见性 shortcut 范围 |
| Separation Weight | `separationWeight` | 分离转向强度 |
| Avoidance Quality | `obstacleAvoidanceType` | 选择 avoidance 配置槽 |
| Avoidance Range Multiplier | `avoidanceQueryMultiplier` | 放大避障速度搜索范围 |
| Avoidance Group | `avoidanceGroup` | 自身所属碰撞 / 避让分组 |
| Groups To Avoid | `groupsToAvoid` | 需要避开的 group mask |
| Groups To Ignore | `groupsToIgnore` | 忽略的 group mask |

开关映射到 `updateFlags`：

```text
IsCrowdAnticipateTurnsActive()       → DT_CROWD_ANTICIPATE_TURNS
IsCrowdObstacleAvoidanceActive()     → DT_CROWD_OBSTACLE_AVOIDANCE
IsCrowdSeparationActive()            → DT_CROWD_SEPARATION
IsCrowdOptimizeVisibilityEnabled()   → DT_CROWD_OPTIMIZE_VIS / _MULTI
IsCrowdOptimizeTopologyActive()      → DT_CROWD_OPTIMIZE_TOPO
IsCrowdPathOffsetEnabled()           → DT_CROWD_OFFSET_PATH
IsCrowdSlowdownAtGoalEnabled()       → DT_CROWD_SLOWDOWN_AT_GOAL
```

---

## 10. 关键数据结构

### 10.1 UE 层

```text
UCrowdManager
  ├─ ActiveAgents : TMap<ICrowdAgentInterface*, FCrowdAgentData>
  ├─ DetourCrowd  : dtCrowd*
  ├─ AvoidanceConfig[]
  ├─ SamplingPatterns[]
  ├─ MaxAgents / MaxAgentRadius
  ├─ MaxAvoidedAgents / MaxAvoidedWalls
  ├─ PathOptimizationInterval
  └─ bResolveCollisions 等配置
```

`FCrowdAgentData` 的重要语义：

```text
AgentIndex      ：dtCrowd 固定池下标；有效性 Handle。
bIsSimulated    ：该 UE Agent 是否接收 Crowd 计算出的速度。
bWantsPathOptimization：是否按时间间隔开放可见性路径优化。
LinkFilter      ：SmartLink / 特殊链接过滤器。
```

### 10.2 Detour 层：dtCrowdAgent

```text
dtCrowdAgent
  ├─ corridor : dtPathCorridor
  ├─ boundary : dtLocalBoundary
  ├─ neis[]   : 附近 agent
  ├─ npos     : Crowd 当前导航位置
  ├─ vel      : 从 UE 同步来的当前速度
  ├─ dvel     : steering 后的期望速度
  ├─ nvel     : avoidance 后的安全速度
  ├─ cornerVerts / cornerFlags
  ├─ targetRef / targetPos / targetState
  └─ params   : dtCrowdAgentParams
```

最易混淆的三个速度：

```text
vel  ：角色当前真实速度，由 UE 每帧写入 Detour。
dvel ：不考虑即时碰撞时，agent 希望沿路径走出的速度。
nvel ：考虑邻居和墙后，Detour 选出的下一帧安全速度。
```

最终 UE 使用的是 `nvel`。

---

## 11. 为什么 UE 不用 Detour 直接移动角色？

`CrowdManager.cpp:741~742` 的注释明确说明：

```text
skip maxAcceleration, we don't use Detour's movement code
```

并且 `ApplyVelocity()` 做的是：

```text
dtCrowdAgent::nvel
  → Recast2UnrealPoint
  → UCrowdFollowingComponent::ApplyCrowdAgentVelocity()
  → UE MovementComponent
```

这是正确的职责分离：

| 层 | 管什么 |
|---|---|
| DetourCrowd | 局部 steering、安全速度、走廊、近邻、墙边界 |
| CharacterMovement | 碰撞 Sweep、落地、重力、台阶、Root Motion、网络预测 / 纠正 |
| PathFollowing | MoveTo 生命周期、完成 / 中止、目标追踪、SmartLink 状态 |

如果让 Detour 直接控制最终 transform，会绕开或冲突于 UE 的角色移动、物理碰撞和网络同步机制。

---

## 12. DetourCrowd 与 RVO Avoidance 的区别

| 维度 | DetourCrowd | `URVOAvoidanceComponent` / Movement RVO |
|---|---|---|
| Agent 间避让 | 有 | 有 |
| NavMesh 墙体边界 | 有，读取 LocalBoundary | 通常不理解 NavMesh 边界 |
| Path Corridor | 有 | 无 |
| 目标路径优化 | 有 | 无 |
| 集中式 batch 求解 | 有 | 更偏各运动体局部处理 |
| 适合 | 大量 AI 挤在 NavMesh 走廊 | 简单动态体分离 |
| 风险 | 参数复杂、CPU 成本更高 | 可能被推离可走区域 |

常见错误是同时开启两套避障，让 Crowd 与 RVO 都修改速度。结果通常是：过度避让、震荡、无法靠近目标。应明确一个系统拥有主要局部避障决策权。

---

## 13. 性能模型与调参建议

### 13.1 成本来自哪里

粗略地说，每帧成本由：

```text
Agent 数量
× 邻居查询成本
× 每 agent 最大邻居数
× 每 agent 墙段数量
× 速度采样候选数
× 路径优化 / 重规划频率
```

影响最大的配置：

| 配置 | 增大后的收益 | 增大后的代价 |
|---|---|---|
| `MaxAgents` | 可模拟更多人 | 内存、总体 Tick 成本上升 |
| `collisionQueryRange` | 更早、更平滑的让行 | 更多邻居和边界查询 |
| `MaxAvoidedAgents` | 近邻判断更完整 | 避障采样成本增加 |
| `MaxAvoidedWalls` | 墙边更稳定 | LocalBoundary 处理增加 |
| Avoidance Quality | 速度更合理 | 候选采样数显著增加 |
| `PathOptimizationInterval` | 更频繁走捷径 | 更多 raycast / corridor 优化 |
| `bResolveCollisions` | Crowd 内部额外分离 | 位置控制冲突风险 + 额外迭代 |

### 13.2 实用建议

1. **先限制 crowd 的真实参与者数量。** 远距离 AI 使用低频移动、动画代理、Mass 或简化 steering，不要把几百个不可见单位都塞入 `dtCrowd`。
2. **`collisionQueryRange` 不要盲目放大。** 通常设为角色半径的若干倍，再以狭窄通道和密集人群测试为准。
3. **先提升 `weightToi`，再盲目提升采样质量。** 若问题是避让太晚，提高时间碰撞惩罚和预测窗通常更直接。
4. **保留 MovementComponent 的位置权威。** 除非你有完整的自定义移动方案，否则避免启用 `bResolveCollisions`。
5. **路径优化限频。** UE 通过 `PathOptimizationInterval` 对 `DT_CROWD_OPTIMIZE_VIS` 做节流，避免每帧 raycast shortcut。
6. **动态 NavMesh 是高成本交界。** NavMesh 更新会导致 Crowd 状态检查、路径失效与 agent 重建 / 重规划；频繁生成动态障碍时需重点 profile。

---

## 14. 网络游戏中的位置

DetourCrowd 是 AI 局部决策，不是网络同步系统。

一般推荐：

```text
Server（Authority）
  → 跑 AIController / CrowdManager / CharacterMovement
  → 得到权威位置与速度
  → Actor / CharacterMovement 复制给 Client

Client
  → 接收 replicated movement，进行网络平滑和表现
```

不要让客户端独立运行 Crowd 并把结果当作权威位置，否则会出现：

- 浮点和帧时间差异造成分歧；
- 邻居集合不同造成速度选择不同；
- 网络纠正频繁；
- AI 位置可被客户端篡改或误预测。

如果客户端只是为了视觉预测运行简化 Crowd，也必须把它视为纯表现，并接受 Server 纠正。

---

## 15. 扩展点与修改影响

### 15.1 推荐扩展点

`UCrowdManager` 提供适合继承的 hook：

```text
PostProximityUpdate()
  → 邻居 / 边界更新完成后；适合读取附近 agent 数据。

PostMovePointUpdate()
  → 新角点已得到、尚未 steering / avoidance；适合更新移动目标或插入自定义 steering 逻辑。

ApplyVelocity()
  → Detour 结果即将写回 UE；适合接入特殊移动组件。
```

项目可通过配置 `CrowdManagerClass` 使用子类，而不是修改引擎源码。

### 15.2 不建议直接改的位置

| 修改点 | 容易影响 |
|---|---|
| `dtCrowdAgent` 结构 | Agent 池布局、初始化、Debug、所有 updateStep |
| `processSample()` penalty | 所有 agent 的绕行风格、死锁概率、性能 |
| `updateStepMove()` | CMC 碰撞、Root Motion、网络平滑 |
| `SetMoveSegment()` 的分段策略 | PathFollowing 到达逻辑、Off-mesh Link、局部最小问题 |
| 坐标转换 | UE 左手 Z-up 与 Recast 坐标边界，错误会造成整体方向 / 高度异常 |

---

## 16. 常见问题定位

### 16.1 Agent 不参与 Crowd

检查：

```text
1. AIController 是否使用 UCrowdFollowingComponent？
2. UCrowdManager 是否存在且已绑定 ARecastNavMesh？
3. Component 是否注册成功？
4. AgentIndex 是否 >= 0？
5. 是否超过 MaxAgents？
6. SimulationState 是否为 Enabled，而非 Disabled / ObstacleOnly？
7. NavMesh 与 CrowdManager::GetNavData() 是否同一个 ARecastNavMesh？
```

断点：

```text
UCrowdFollowingComponent::Initialize
UCrowdManager::RegisterAgent
UCrowdManager::AddAgent
```

### 16.2 Agent 会走路但完全不避让

检查：

```text
1. DT_CROWD_OBSTACLE_AVOIDANCE 是否启用？
2. collisionQueryRange 是否 > 0？
3. Agent 是否被标记为 bIsSimulated？
4. Avoidance Quality 是否正确映射到配置槽？
5. 其他对象是否也注册为 Crowd agent？
6. 是否同时有 RVO 在覆盖速度？
```

断点：

```text
UCrowdManager::GetAgentParams
UCrowdManager::Tick
 dtCrowd::updateStepProximityData
 dtCrowd::updateStepAvoidance
UCrowdManager::ApplyVelocity
```

观察：`ag->vel`、`ag->dvel`、`ag->nvel`、`ag->nneis`。

### 16.3 拐角抖动或在门口卡住

优先检查：

```text
- Agent 半径与 Recast NavMesh Agent Radius 是否一致；
- Path Offset 是否启用；
- collisionQueryRange 是否过小或过大；
- SeparationWeight 是否过高；
- 目标是否在不可到达 / 部分路径末端；
- 是否存在 SmartLink / Off-mesh Link；
- bResolveCollisions 是否与 CMC 冲突；
- 多个避障系统是否同时写速度。
```

### 16.4 角色突然回弹或穿模

重点看：

```text
- bResolveCollisions 是否开启；
- ApplyCrowdAgentPosition 是否与 CharacterMovement 碰撞竞争；
- RootMotion 是否覆盖移动；
- 服务端与客户端是否都在跑 AI Crowd；
- NavMesh 是否在频繁动态更新。
```

---

## 17. 调试工具与断点

### 17.1 性能

```text
stat AICrowd
```

可查看 Crowd Tick 以及 Corridor、Paths、Proximity、Steering、Avoidance、Movement 等分步耗时。

### 17.2 Debug 绘制

常用控制台变量：

```text
ai.crowd.DebugSelectedActors 1
ai.crowd.DrawDebugPath 1
ai.crowd.DrawDebugVelocityObstacles 1
ai.crowd.DrawDebugNeighbors 1
ai.crowd.DrawDebugCorners 1
ai.crowd.DrawDebugBoundaries 1
ai.crowd.DebugVisLog 1
```

其中最关键的是：

- **Velocity Obstacles**：观察候选速度及 penalty，判断“为什么它选这个方向”；
- **Neighbors**：确认 agent 实际感知到了谁；
- **Boundaries**：确认墙段是否正确进入避障输入；
- **Path / Corners**：确认 corridor 与 string-pulling 是否合理。

### 17.3 源码断点顺序

```text
1. UCrowdFollowingComponent::SetMoveSegment
2. UCrowdManager::SetAgentMovePath
3. UCrowdManager::Tick
4. UCrowdManager::PrepareAgentStep
5. dtCrowd::updateStepProximityData
6. dtCrowd::updateStepSteering
7. dtCrowd::updateStepAvoidance
8. dtObstacleAvoidanceQuery::processSample
9. UCrowdManager::ApplyVelocity
10. UCrowdFollowingComponent::ApplyCrowdAgentVelocity
```

---

## 18. 阅读路线

```text
第一层：UE 接入
  DetourCrowdAIController.cpp
    → CrowdFollowingComponent.cpp
    → CrowdManager.cpp

第二层：每帧 Crowd 算法
  DetourCrowd.cpp::update()
    → updateStepProximityData()
    → updateStepNextMovePoint()
    → updateStepSteering()
    → updateStepAvoidance()
    → updateStepMove()

第三层：真正的避障评分
  DetourObstacleAvoidance.cpp
    → prepare()
    → processSample()
    → sampleVelocityAdaptive()

第四层：路径与边界基础设施
  DetourPathCorridor.cpp
  DetourLocalBoundary.cpp
  DetourSharedBoundary.cpp
  DetourProximityGrid.cpp
  DetourPathQueue.cpp
```

---

## 19. 最终速记

```text
ADetourCrowdAIController
  = 用 CrowdFollowingComponent 替换默认 PathFollowingComponent 的便捷类。

UCrowdFollowingComponent
  = UE PathFollowing 与 Detour agent 之间的双向 Adapter。

UCrowdManager
  = 一个 World 内所有 Crowd agent 的集中调度器。

dtCrowd
  = corridor、近邻、墙边界、steering、避障速度采样的核心求解器。

vel / dvel / nvel
  = 当前真实速度 / 期望路径速度 / 避障后的安全速度。

DetourCrowd 不直接负责最终角色运动。
  = 它给 CMC 建议安全速度；CharacterMovement 仍负责真实移动与碰撞。
```

---

## 参考源码

```text
Engine/Source/Runtime/AIModule/Private/DetourCrowdAIController.cpp
Engine/Source/Runtime/AIModule/Private/Navigation/CrowdFollowingComponent.cpp
Engine/Source/Runtime/AIModule/Private/Navigation/CrowdManager.cpp
Engine/Source/Runtime/AIModule/Classes/Navigation/CrowdManager.h
Engine/Source/Runtime/Navmesh/Public/DetourCrowd/DetourCrowd.h
Engine/Source/Runtime/Navmesh/Private/DetourCrowd/DetourCrowd.cpp
Engine/Source/Runtime/Navmesh/Private/DetourCrowd/DetourObstacleAvoidance.cpp
```

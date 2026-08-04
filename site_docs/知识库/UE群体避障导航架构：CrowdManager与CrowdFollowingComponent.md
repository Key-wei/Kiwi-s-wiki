---
area: "[[Unreal Engine]]"
tags: [UE, AI, 导航, Crowd, Detour, 架构]
created: 2026-07-16
---
## 定义

UE 的**群体避障导航（Crowd Simulation）** 是一套让多个 AI 在共享导航网格上互相避让、又不会被推下悬崖或挤进墙里的移动方案。它由三个类协作实现，一句话概括三者关系：

> `ADetourCrowdAIController` 只是"配置开关"，把 AIController 默认的 `PathFollowingComponent` 替换成 `UCrowdFollowingComponent`；后者是**双向适配器**，把 UE 的寻路/移动世界翻译给 Detour；`UCrowdManager` 是**中心化仲裁器**，持有底层 C 库 `dtCrowd`，每帧统一对所有 agent 做转向与避障求解。

与 `AvoidanceManager`(RVO) 的关键区别：RVO 只看 agent、不看 navmesh，会把人推到不可行走区域；Crowd 方案避障时**始终尊重 navmesh 边界**，代价是更慢。

来源：`Engine/Source/Runtime/AIModule`（UE5 引擎源码，本地 `F:\RA\AEngine`），排查基于 `keywei` 分支的怪物巡逻 AI 工作。

## 在引擎中的位置

```
World
 └─ UNavigationSystemV1            (导航子系统，拥有 crowd manager)
     ├─ ARecastNavMesh (dtNavMesh) (导航网格数据源)
     └─ UCrowdManager  (dtCrowd)   ← 仲裁核心
          ▲ RegisterAgent / SetAgentMovePath / ApplyVelocity
     UCrowdFollowingComponent      (每个 AI 一个，agent 适配器)
          ▲ SetDefaultSubobjectClass
     ADetourCrowdAIController       (仅做组件替换)
          └─ ACharacter → UCharacterMovementComponent (最终执行移动)
```

## 三个类的职责

| 类 | 一句话职责 | 关键实现 |
|---|---|---|
| `ADetourCrowdAIController` | 构造时把寻路组件换成 Crowd 版 | 仅一行 `SetDefaultSubobjectClass<UCrowdFollowingComponent>` |
| `UCrowdFollowingComponent` | 对下实现 `ICrowdAgentInterface`(UE→Detour)，对上覆写 `PathFollowingComponent`(Detour→UE) | 双向适配器 |
| `UCrowdManager` | 封装 `dtCrowd`，每帧对全体 agent 统一 steering/avoidance | 中心化仲裁 + Facade |

`ADetourCrowdAIController` 的全部实现只有：
```cpp
ADetourCrowdAIController::ADetourCrowdAIController(const FObjectInitializer& OI)
    : Super(OI.SetDefaultSubobjectClass<UCrowdFollowingComponent>(TEXT("PathFollowingComponent")))
{}
```
它不含任何逻辑——所有能力都来自被替换进去的组件。项目也可以给普通 AIController 同时挂两个组件，在 move 请求间切换。

## 核心设计思想（Why）

**为什么用「中心化 Manager + 逐 agent 组件」而非纯组件？**
避障是天然全局的问题——A 要避 B，就必须知道 B 的位置和速度。若每个组件各自算，会产生 N² 两两查询且无法共享 navmesh 边界缓存。Epic 把求解逻辑**上提到单一 Manager**，agent 只负责"报告状态 / 接收结果"。这是典型的 **Mediator（中介者）** 结构。

几个关键决策：
- **中心化 + 数据导向**：`dtCrowd` 内部按 agent 数组批处理（`cacheActiveAgents` → 一系列 `updateStep*`），cache-friendly，无逐对象虚函数分派。
- **接口解耦**：Manager 只认 `ICrowdAgentInterface`，不认具体类。因此**玩家角色也能作为"障碍"注册进来**（实现接口 + `RegisterAgent`），却不被 crowd 驱动移动。
- **归属于 NavigationSystem**：`UCrowdManager` 的 Outer 是 `UNavigationSystemV1`（`NewObject(this,...)`），所以 `GetWorld()` 要经 `GetOuter()→NavSys→GetWorld()`。这让它随 navmesh 生命周期走、天然做 World 隔离（PIE 多世界各有自己的 CrowdManager）。
- **不用 Detour 的移动代码**：`GetAgentParams` 明确 `skip maxAcceleration, we don't use Detour's movement code`。Epic 只借 Detour 的**转向与避障求解**，最终移动交给 `CharacterMovementComponent`，角色仍受重力/碰撞/RootMotion 约束。`bResolveCollisions` 默认 `false` 正因位置解算权留给 CMC。
- **可替换**：`CrowdManagerClass` 是软引用配置，项目可继承覆写 `PostProximityUpdate`/`PostMovePointUpdate` 等 hook 注入定制逻辑，无需改引擎。

## 每帧调用链（核心）

全部运行在**游戏线程**（无跨线程，是简化设计的一部分）。`UCrowdManager::Tick` 是心脏：
```
UCrowdManager::Tick(DeltaTime)
  dtCrowd->cacheActiveAgents()
  ── 读 UE 最新状态灌进 dtCrowd ──
  for agent: PrepareAgentStep()  → 写 ag->npos / ag->vel / maxSpeed
  ── Detour 分步流水线（每步一个 stat 计时域）──
  updateStepCorridor        (走廊推进)
  updateStepPaths           (路径重规划, 受 bAllowPathReplan 控)
  updateStepProximityData   → PostProximityUpdate()   [hook]
  updateStepNextMovePoint   → PostMovePointUpdate()    [hook, moving-goal 追踪]
  updateStepSteering        (转向)
  updateStepAvoidance       (RVO 避障采样)
  [updateStepMove]          (仅 bResolveCollisions 时才解位置)
  UpdateAgentPaths()        (检测 poly 变化/smart link → 回调组件)
  updateStepOffMeshVelocity
  ── 把求解结果灌回 UE ──
  for agent: ApplyVelocity() → comp->ApplyCrowdAgentVelocity()
      → MovementComp->RequestPathMove() 或 RequestDirectMove()
         → UCharacterMovementComponent 实际位移
```

**关键对称性**：Tick 开头**读 UE 状态灌给 Detour**，Tick 结尾**读 Detour 结果灌回 UE**。CrowdManager 本质是这两个世界之间每帧一次的**同步泵**。

发起移动（下行）时，`SetMoveSegment` 会把 A* 返回的长 corridor **切成 15 个 poly 的小段**喂给 Detour——防止 crowd 因只看前几步而陷入局部最小；同时 `OnPathfindingQuery` 给查询打上 `SkipStringPulling`，crowd 模式**故意不拉直路径**，改从 `PathCorridor`(poly 序列) 读取。

## 关键数据结构

- `UCrowdManager::DetourCrowd (dtCrowd*)` — 底层求解器，裸指针，手动 alloc/free（`BeginDestroy` 里 `dtFreeCrowd`）。
- `UCrowdManager::ActiveAgents (TMap<ICrowdAgentInterface*, FCrowdAgentData>)` — **UE 对象世界 ↔ Detour index 世界的唯一桥梁**。
- `FCrowdAgentData::AgentIndex` — 在 dtCrowd 固定池中的下标，`>=0` 即有效（`IsValid()` 就是判这个）。**Handle 模式**：dtCrowd 是固定容量对象池，用整型 index 而非指针引用 agent。
- `FCrowdAgentData::bIsSimulated` — 区分"被 crowd 驱动移动"还是"仅作障碍"。
- `UCrowdFollowingComponent::SimulationState` — Enabled / ObstacleOnly / Disabled 总开关；几乎每个覆写方法开头都先查 `IsCrowdSimulationEnabled()`。

## 坐标系转换（易错点）

UE 是左手 Z-up，Recast/Detour 是右手 Y-up。所有跨越边界的点都要 `Unreal2RecastPoint` / `Recast2UnrealPoint`。读这套代码时**看到坐标就要想到系转换**，否则很容易看晕。参见 [[RecastNavigation 算法解析：从三角形汤到群体寻路]]。

## 设计模式清单

- **Mediator（中介者）**：CrowdManager 仲裁所有 agent，agent 间不直接通信。整套骨架。
- **Adapter（适配器）**：CrowdFollowingComponent 双向适配。
- **Handle / 对象池**：`dtCrowd` 固定池 + `AgentIndex` 句柄。
- **Strategy（策略）**：`AvoidanceConfig[]` + `AvoidanceQuality`(Low/Medium/Good/High) 运行时切换避障精度档位。
- **Template Method + 可替换实现**：空 hook `PostProximityUpdate`/`PostMovePointUpdate` + 软引用 `CrowdManagerClass`。
- **Facade（外观）**：把 Detour 一堆 C API 包成语义化的 `SetAgentMoveTarget` 等方法。

## 性能与踩坑

- **限频更新**：路径优化按 `PathOptimizationInterval`(默认 0.5s) 计时，navmesh 位置检查按 `NavmeshCheckInterval`(1s)，不是每帧做。
- **BatchQuery**：Tick 内把整帧 navmesh 查询包成一批（`BeginBatchQuery/FinishBatchQuery`），避免反复加锁。
- **MaxAgents=50 硬上限**：超出不被模拟。
- **navmesh 重建 = 整个 dtCrowd 重建**：`OnNavMeshUpdate` 会 `DestroyCrowdManager + CreateCrowdManager`，所有 agent 重新 `AddAgent`。动态导航场景要警惕这个隐性成本。
- **`bResolveCollisions=true` 会抢位置控制权**：crowd 直接改角色位置，与 CMC 碰撞/RootMotion 冲突，极易穿模抖动，默认 false 是有原因的。
- **多人游戏**：crowd 通常只在权威端跑，客户端靠移动同步，改行为要确认在哪端生效。
- **时序陷阱**：组件在关卡 BeginPlay 期间 possess 已放置 Pawn 时，CrowdManager 可能尚未创建，`Initialize()` 用 `OnNavigationInitDone` 委托延迟补注册，注册失败则降级 `Disabled`。**读档恢复 / 巡逻点切换后，agent 的重新注册时序与 `SetMoveSegment` 的 PathPart 状态是重点排查交界面。**

## 调试

控制台变量（需先开 `ai.crowd.DebugSelectedActors 1`，只对编辑器选中 Pawn 生效）：
```
ai.crowd.DrawDebugPath 1               画当前 corridor
ai.crowd.DrawDebugVelocityObstacles 1  画 RVO 避障采样（最直观看避障决策）
ai.crowd.DrawDebugNeighbors 1          画被感知的邻居
ai.crowd.DrawDebugCorners 1            画路径角点
ai.crowd.DrawDebugBoundaries 1         画共享 navmesh 边界（不依赖选中）
ai.crowd.DebugVisLog 1                 记录进 VisualLogger 回放
```
断点建议：`UCrowdManager::Tick`(看节奏)、`ApplyVelocity`(agent 乱动看 `ag->nvel`)、`SetMoveSegment`(卡点/切段异常)、`AddAgent`(没被模拟看 `AgentIndex>=0` 与 `bIsSimulated`)。工具：Gameplay Debugger（AI 分类）、VisualLogger、`stat AICrowd`（各 step 耗时）。

## 相关概念

- [[RecastNavigation 算法解析：从三角形汤到群体寻路]]
- [[UE导航系统NavigationSystem]]
- [[Mediator中介者模式]]
- [[对象池模式]]

## 参考资料

- `Engine/Source/Runtime/AIModule/Classes/DetourCrowdAIController.h` / `.cpp`
- `Engine/Source/Runtime/AIModule/Classes/Navigation/CrowdFollowingComponent.h` / `Private/.../CrowdFollowingComponent.cpp`
- `Engine/Source/Runtime/AIModule/Classes/Navigation/CrowdManager.h` / `Private/.../CrowdManager.cpp`
- `Engine/Source/Runtime/NavigationSystem/Private/NavigationSystem.cpp:1359`（`CreateCrowdManager` 归属与创建时机）
- 底层算法：`Engine/Source/Runtime/Navmesh/`（`DetourCrowd.cpp` / `DetourObstacleAvoidance.cpp` / `DetourPathCorridor.cpp`）

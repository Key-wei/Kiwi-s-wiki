# UE5 网络同步模块源码深度解析

> **源码版本**：当前仓库 `UE 5.4.4`  
> **仓库根目录**：`F:\10_Projects\RA\AEngine`  
> **目标**：从引擎源码架构视角建立“游戏启动 → 建图 → 登录 → Gameplay Framework 创建 → 每帧收包/模拟/发包 → 属性复制 / RPC → Travel 与销毁”的完整认知。

---

## 1. 核心结论

UE 的多人网络不是由 `GameMode` 单独“同步游戏”的。

它由两层系统协作：

```text
┌─────────────────────────────────────────────────────────────┐
│ Gameplay Framework：定义“游戏里谁负责什么”                    │
│                                                             │
│ GameInstance / World / GameMode / GameState                 │
│ PlayerController / PlayerState / Controller / Pawn          │
│ GameSession / GameNetworkManager / WorldSettings            │
└───────────────────────▲─────────────────────────────────────┘
                        │ 使用 Actor、RPC、Replicated Property
┌───────────────────────┴─────────────────────────────────────┐
│ Networking / Replication：定义“数据如何跨机器传输”             │
│                                                             │
│ UNetDriver → UNetConnection → UChannel → UActorChannel       │
│ PackageMap / NetGUID / FRepLayout / FObjectReplicator        │
│ Legacy Replication / ReplicationGraph / Iris                 │
└─────────────────────────────────────────────────────────────┘
```

- **Gameplay Framework**：决定权威、对象归属、玩家身份、出生、比赛状态。
- **网络层**：决定对象是否相关、属性是否变化、如何序列化、何时发送、如何接收并执行 RPC / `OnRep`。

---

## 2. 启动入口：从引擎启动到第一个 World

### 2.1 主调用链

普通 Game 或 Dedicated Server 的主要启动路径：

```text
FEngineLoop::Init
  → 创建 UGameEngine
  → UGameEngine::Init
  → 创建 UGameInstance
  → UGameEngine::Start
      → UGameInstance::StartGameInstance
          → UEngine::Browse(WorldContext, URL, Error)
          → LoadMap / 创建或进入 World
```

源码入口：

```text
Engine/Source/Runtime/Engine/Private/GameEngine.cpp
  UGameEngine::Start()
  └─ GameInstance->StartGameInstance();       // 约 1223 行

Engine/Source/Runtime/Engine/Private/GameInstance.cpp
  UGameInstance::StartGameInstance()          // 599 行
  └─ Engine->Browse(*WorldContext, URL, Error) // 655 行
```

`UGameInstance::StartGameInstance()` 的职责：

1. 读取默认地图及命令行地图覆盖参数；
2. 构造 `FURL`；
3. 调用 `UEngine::Browse()`；
4. 由 `Browse` 判断是加载本地地图、Listen Server 开图、连接远端服务器、播放 Replay，还是 Travel。

### 2.2 GameInstance 生命周期

```text
进程启动
  └─ UGameInstance 创建一次
      ├─ World A
      ├─ Travel
      ├─ World B
      └─ Travel
          └─ World C
进程退出
  └─ UGameInstance 销毁
```

`UGameInstance` 跨地图，但不跨进程，也不跨机器。Server 与每个 Client 都拥有独立的 `GameInstance`。

因此，`GameInstance` 不能作为自动联网同步的数据容器。

---

## 3. UWorld：网络与 Gameplay 的汇合点

`UWorld` 是一张地图运行时的总调度中心，典型持有关系如下：

```text
UWorld
 ├─ PersistentLevel / Streaming Levels
 ├─ AuthorityGameMode          // 仅 Server 有
 ├─ GameState                  // Server 与 Client 都有
 ├─ NetDriver                  // 游戏网络驱动
 ├─ DemoNetDriver              // Replay 时可能存在
 ├─ NetworkManager
 ├─ PlayerController 列表
 ├─ WorldSettings
 ├─ Physics / Navigation / TimerManager
 └─ WorldSubsystems
```

核心源码：

```text
Engine/Source/Runtime/Engine/Private/LevelTick.cpp
  UWorld::Tick(ELevelTick TickType, float DeltaSeconds) // 1272 行
```

### 3.1 一帧中的网络时序

```text
Game Thread

UWorld::Tick
  │
  ├─ BroadcastTickDispatch(DeltaSeconds)
  ├─ BroadcastPostTickDispatch()
  │     └─ 处理进入的数据包、Bunch、RPC、属性更新
  │
  ├─ Actor Tick
  │   ├─ Pawn / CharacterMovement
  │   ├─ Controller
  │   ├─ Components
  │   ├─ Physics
  │   └─ Timers / Latent Actions
  │
  ├─ UpdateCameraManager
  │     └─ 为 relevancy / priority 构建观察视角
  │
  ├─ BroadcastPreTickFlush()
  ├─ BroadcastTickFlush(RealDeltaSeconds)
  │     └─ ServerReplicateActors / Iris PreSendUpdate
  │
  └─ BroadcastPostTickFlush()
```

对应源码位置：

```text
LevelTick.cpp
  1337~1344：网络接收与客户端网络 Tick
  1489~1619：Actor Tick Groups
  1576~1584：更新 PlayerController Camera
  1652~1666：网络发送 TickFlush / PostTickFlush
```

含义：

- **收包在前**：本帧收到的 RPC、属性同步优先写入本地世界；
- **Gameplay Tick 在中间**：游戏逻辑基于最新已接收状态执行；
- **发包在后**：服务端复制本帧计算出的权威新状态。

多数网络 Gameplay 逻辑都在 **Game Thread** 上执行。`UNetDriver::ProcessRemoteFunction()` 也明确要求必须在 Game Thread 调用。

---

## 4. 网络基础骨架：NetDriver、Connection 与 Channel

```text
UWorld
  └─ UNetDriver
      ├─ ServerConnection               // Client：唯一的到 Server 的连接
      ├─ ClientConnections[]            // Server：每个 Client 一条连接
      ├─ ReplicationDriver              // 可选：Replication Graph
      ├─ ReplicationSystem              // 可选：Iris
      ├─ NetworkObjectList
      └─ PackageMap / NetGUID 系统

UNetConnection
  ├─ 低层 Socket / 传输连接
  ├─ PackageMap
  ├─ OpenChannels[]
  ├─ ActorChannel 映射
  ├─ PlayerController
  ├─ ViewTarget
  ├─ CurrentNetSpeed / QueuedBits
  └─ Connection State / Login State

UChannel
  ├─ ControlChannel      // Hello、Login、Welcome、Join、Travel
  ├─ UActorChannel       // Actor、属性、组件、子对象、RPC
  ├─ VoiceChannel
  └─ 自定义 Channel
```

### 4.1 UNetDriver 的定位

`UNetDriver` 是一个 `UWorld` 的网络会话调度器，而不是某一个客户端。

它负责：

- Client：管理到 Server 的唯一 `ServerConnection`；
- Server：管理全部 `ClientConnections`；
- 驱动收包、连接维护、发包；
- 服务端复制调度；
- RPC 发送；
- 分派 Legacy Replication、ReplicationGraph 或 Iris。

关键源码：

```text
Engine/Source/Runtime/Engine/Private/NetDriver.cpp
  UNetDriver::TickDispatch() // 2263 行
  UNetDriver::TickFlush()    // 953 行
```

### 4.2 收包链路

```text
UWorld::BroadcastTickDispatch
  → UNetDriver::TickDispatch
      → UNetConnection::PreTickDispatch
      → 底层 socket 收包
      → UNetConnection::ReceivedPacket
      → 一个 Packet 被拆成多个 Bunch
      → 找到或创建对应 Channel
      → ControlChannel / UActorChannel 消费数据
```

关键入口：

```text
Engine/Source/Runtime/Engine/Private/NetConnection.cpp
  UNetConnection::ReceivedPacket() // 2788 行
```

一个 Packet 可以携带多个 `FInBunch`；Bunch 才是能交给某个 Channel 处理的逻辑网络消息片段。

---

## 5. 建连、握手与登录：从 Socket 到玩家

“连接建立”与“玩家已创建”是两个不同阶段。

### 5.1 客户端连接服务端

```text
客户端 OpenLevel("ip") / ClientTravel
  → UEngine::Browse
  → 创建 UPendingNetGame
  → UPendingNetGame::InitNetDriver
  → NetDriver->InitConnect(...)
  → 低层连接建立
  → ControlChannel 交换控制消息
```

源码：

```text
Engine/Source/Runtime/Engine/Private/PendingNetGame.cpp
  NetDriver->InitConnect(...)                // 55 行
  UPendingNetGame::NotifyControlMessage()    // 225 行
```

### 5.2 控制协议主流程

```text
Client                                     Server
  │                                           │
  ├─ NMT_Hello ─────────────────────────────► │ 版本、特性、加密协商
  │ ◄──────────────────────── NMT_Challenge ─┤
  ├─ NMT_Login ─────────────────────────────► │ 登录、URL、UniqueId
  │ ◄──────────────────────── NMT_Welcome ───┤ 告诉 Client 需加载的地图
  │       Client LoadMap                       │
  ├─ NMT_Join ──────────────────────────────► │
  │                                           ├─ GameMode::Login
  │                                           ├─ Spawn PlayerController
  │                                           ├─ PostLogin
  │                                           └─ HandleStartingNewPlayer
```

服务端控制消息入口：

```text
Engine/Source/Runtime/Engine/Private/World.cpp
  UWorld::NotifyControlMessage(...) // 6433 行
```

`NMT_Hello` 阶段会执行：

- 网络版本兼容性校验；
- 运行时网络特性兼容性校验；
- 加密 Token 处理；
- Challenge 流程。

### 5.3 Welcome 与地图同步

服务端入口：

```cpp
UWorld::WelcomePlayer(UNetConnection* Connection)
```

源码：`World.cpp` 约 6352 行。

该函数的职责：

1. 确定服务端当前地图；
2. 记录客户端应处于的 World Package；
3. 允许 `GameInstance` 修改客户端 Travel URL；
4. 读取 `AuthorityGameMode` 类路径；
5. 发送 `NMT_Welcome(LevelName, GameName, RedirectURL)`；
6. 将连接状态标记为 `Welcomed`；
7. 等待 Client 加载地图并发送 `NMT_Join`。

因此地图 / World 本身是网络握手的一部分。Actor 复制开始前，客户端需要进入兼容 World，并具备通过 `PackageMap / NetGUID` 解析对象引用的能力。

---

## 6. Gameplay Framework 的权威分布

| 对象 | Server | Owning Client | Other Clients | 复制语义 |
|---|---:|---:|---:|---|
| `UGameInstance` | 有 | 有 | 有 | 各端独立，不复制 |
| `UWorld` | 有 | 有 | 有 | 各端独立，不复制 |
| `AGameModeBase` | 有 | 无 | 无 | 仅服务器规则权威 |
| `AGameStateBase` | 有 | 有 | 有 | Server 写、Client 读 |
| `APlayerController` | 有 | 有 | 通常无 | 输入、拥有权、私有 RPC |
| `APlayerState` | 有 | 有 | 有 | 玩家公共状态 |
| `APawn / ACharacter` | 有 | 有 | 视相关性而定 | Server 权威实体状态 |
| `AHUD / UUserWidget` | 无或本地 | 有 | 各自本地 | 不复制 |
| `AGameSession` | 有 | 通常无 | 通常无 | Server 会话 / 登录管理 |

---

## 7. GameInstance：跨地图本地容器

```text
UGameInstance
 ├─ LocalPlayers
 ├─ GameInstanceSubsystems
 ├─ Online Session / Replay / Travel 支持
 ├─ Persistent Services
 └─ 当前 WorldContext
```

适合：

- 账号或本机缓存；
- 跨图临时状态；
- 本地服务；
- Online Session 管理；
- `UGameInstanceSubsystem`。

不适合：

- 房间人数；
- 比赛倒计时；
- 全局阵营分数；
- 所有客户端必须一致的数据。

正确拆分：

```text
跨地图、本机持久状态              → GameInstance
全局且需要同步的本局状态           → GameState
每个玩家都可见的玩家状态           → PlayerState
仅该玩家可见/拥有者专属的数据       → PlayerController / OwnerOnly Actor
角色实体状态                       → Pawn / Character / Component
```

---

## 8. GameMode：服务器规则权威

`AGameModeBase` 是本局游戏规则与玩家生命周期的服务器控制器。

> `GameMode` 只存在于 Server。Client 上 `GetAuthGameMode()` 通常为 `nullptr`。

```text
Server
  World
   ├─ AuthorityGameMode = AGameModeBase
   └─ GameState = AGameStateBase

Client
  World
   ├─ AuthorityGameMode = null
   └─ GameState = replicated copy
```

关键源码：

```text
Engine/Source/Runtime/Engine/Private/GameModeBase.cpp
  AGameModeBase::InitGame()                // 81 行
  AGameModeBase::PreInitializeComponents() // 115 行
  AGameModeBase::StartPlay()               // 203 行
  AGameModeBase::RestartPlayer()           // 1244 行
```

### 8.1 创建 GameState 与 NetworkManager

`AGameModeBase::PreInitializeComponents()` 的主要流程：

```text
GameMode::PreInitializeComponents
  ├─ Spawn GameStateClass
  ├─ World->SetGameState(GameState)
  ├─ GameState->AuthorityGameMode = this
  ├─ 网络服务器时 Spawn GameNetworkManager
  └─ InitGameState()
```

这个设计把：

```text
服务端私有的“规则决策”      → GameMode
客户端需要获知的“规则状态”   → GameState
```

明确分离。

### 8.2 InitGame

```text
AGameModeBase::InitGame(MapName, Options, ErrorMessage)
  ├─ 保存 OptionsString
  ├─ Spawn GameSession
  ├─ GameSession::InitOptions
  ├─ 自动登录或注册 Server
  └─ 广播 GameModeInitializedEvent
```

适合：

- 解析 URL Options；
- 初始化服务端规则；
- 创建 / 注册 Session；
- 地图级玩法初始化。

### 8.3 玩家出生链路

```text
Client Join
  → UWorld::NotifyControlMessage(NMT_Join)
  → GameMode::Login
  → Spawn PlayerController
  → GameMode::PostLogin(NewPlayer)
  → GameMode::HandleStartingNewPlayer(NewPlayer)
  → GameMode::RestartPlayer(NewPlayer)
  → SpawnDefaultPawnFor(...)
  → NewPlayer->Possess(Pawn)
```

源码入口：

```text
GameModeBase.cpp
  AGameModeBase::RestartPlayer()              // 1244 行
  AGameModeBase::RestartPlayerAtPlayerStart() // 1267 行
  AGameModeBase::FinishRestartPlayer()        // 1365 行
```

---

## 9. GameState：服务器规则状态的复制投影

`AGameStateBase` 保存“Client 需要知道的当前局面”。

```text
Server:
  GameMode 改变规则状态
     ↓
  GameState 写入 Replicated Property
     ↓
  NetDriver / Iris 复制
     ↓
Client:
  GameState 属性更新
     ↓
  OnRep / UI / 客户端表现
```

### 9.1 BeginPlay 为什么由 GameState 传播

源码：

```cpp
void AGameModeBase::StartPlay()
{
    GameState->HandleBeginPlay();
}
```

`AGameStateBase::HandleBeginPlay()`：

```cpp
bReplicatedHasBegunPlay = true;
GetWorldSettings()->NotifyBeginPlay();
GetWorldSettings()->NotifyMatchStarted();
```

客户端收到该复制字段后：

```cpp
void AGameStateBase::OnRep_ReplicatedHasBegunPlay()
{
    if (bReplicatedHasBegunPlay && GetLocalRole() != ROLE_Authority)
    {
        GetWorldSettings()->NotifyBeginPlay();
        GetWorldSettings()->NotifyMatchStarted();
    }
}
```

完整语义：

```text
Server GameMode::StartPlay
  → GameState.bReplicatedHasBegunPlay = true
  → 复制到 Client
  → Client GameState::OnRep_ReplicatedHasBegunPlay
  → Client WorldSettings::NotifyBeginPlay()
  → Client World 内 Actor 进入 BeginPlay 生命周期
```

---

## 10. PlayerController：连接、输入与 RPC 枢纽

`APlayerController` 的典型分布：

```text
Server：每个玩家都有一个 PlayerController
Owning Client：拥有自己的 PlayerController
Other Clients：通常不存在该 PlayerController
```

它承载的是天然偏私有 / 控制性质的数据：

- 本地输入；
- Camera；
- UI 入口；
- Client RPC；
- Server RPC；
- `Possess` 控制关系；
- 玩家所属连接身份。

其他玩家通常只需看到你的 Pawn 与 PlayerState，而不应看到你的镜头、鼠标、HUD 或私有 UI 状态。

### 10.1 RPC 发送路径

```text
Actor / Component 调用 Net UFUNCTION
  → AActor::CallRemoteFunction
  → UNetDriver::ProcessRemoteFunction
  → 选择 owning connection 或 relevant connections
  → UActorChannel 写 RPC Bunch
  → UNetConnection / Socket
```

源码：

```text
Engine/Source/Runtime/Engine/Private/Actor.cpp
  AActor::CallRemoteFunction() // 5055 行

Engine/Source/Runtime/Engine/Private/NetDriver.cpp
  UNetDriver::ProcessRemoteFunction() // 7418 行
```

### 10.2 RPC 归属规则

```text
Server RPC
  Client → Server
  必须由拥有该 Actor 的 Client 从有效 owning connection 发起。

Client RPC
  Server → 某一个 owning client
  Actor 必须能够找到对应 owning connection。

NetMulticast RPC
  Server → 当前与该 Actor 相关的 Client。
```

`NetMulticast` 并不等于无条件全服广播。`UNetDriver::ProcessRemoteFunction()` 会检查：

```text
Actor->IsNetRelevantFor(...)
```

---

## 11. PlayerState：玩家公共身份与公共状态

`APlayerState` 的职责是每个玩家可被所有相关客户端看见的公共数据：

```text
每名玩家一份 PlayerState
  ├─ Server：权威版本
  ├─ Owning Client：复制版本
  └─ Other Clients：复制版本
```

适合：

- 玩家名称；
- 队伍；
- 分数；
- Ping；
- 准备状态；
- 公开角色选择；
- 可公开展示的等级、称号、阵营。

不适合：

- 私有背包；
- 未公开匹配信息；
- 本地 UI 临时状态；
- 服务端安全校验状态。

经验原则：

```text
其他玩家需要看到的数据  → PlayerState
只有本人需要看到的数据  → PlayerController / OwnerOnly Replication
角色实体的数据          → Pawn / Component
```

---

## 12. Pawn、Character、Controller 与移动同步

```text
PlayerController
  └─ Possess
      └─ Pawn / Character
          ├─ MovementComponent
          ├─ Mesh / Ability / Inventory Components
          └─ Replicated Properties
```

### 12.1 网络角色

```text
Server 上的 Pawn:
  LocalRole = ROLE_Authority

拥有该 Pawn 的 Client:
  LocalRole = ROLE_AutonomousProxy

其他 Client:
  LocalRole = ROLE_SimulatedProxy
```

语义：

- `ROLE_Authority`：拥有最终状态裁决权；
- `ROLE_AutonomousProxy`：拥有者，可执行客户端预测并上传输入；
- `ROLE_SimulatedProxy`：观察者，通常基于服务端状态进行插值模拟。

### 12.2 CharacterMovement 的基本模型

```text
Autonomous Client
  ├─ 本地预测执行输入
  ├─ 保存 Move
  └─ ServerMove RPC 上传 Compressed Move
           ↓
Server
  ├─ 按同一移动逻辑重演 / 验证
  ├─ 得到权威位置、速度、移动模式
  └─ 必要时发送 ClientAdjustment
           ↓
Owning Client
  ├─ 收到修正
  └─ 回滚到 Server 状态后重放未确认 Move

Simulated Proxy
  └─ 接收 replicated movement 并进行网络平滑
```

在 Legacy 复制路径里，`UNetDriver::ServerReplicateActors()` 对连接处理时会调用：

```cpp
Connection->PlayerController->SendClientAdjustment();
```

位置：`NetDriver.cpp` 5890～5903 行。

---

## 13. 属性复制：从 UPROPERTY 到 OnRep

### 13.1 声明与注册

```cpp
UPROPERTY(ReplicatedUsing = OnRep_Health)
float Health;

void AMyCharacter::GetLifetimeReplicatedProps(
    TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(AMyCharacter, Health);
}

UFUNCTION()
void OnRep_Health();
```

完整过程：

```text
UPROPERTY(Replicated)
  → 字段具有复制资格

GetLifetimeReplicatedProps()
  → 注册类型级别的复制描述

DOREPLIFETIME(...)
  → 注册字段与复制条件

Server 修改 Health
  → 下一次 Actor 被复制时，系统比较或捕获变化

Client 收包
  → 反序列化字段
  → 写入本地副本
  → 必要时调用 OnRep_Health
```

### 13.2 PreReplication：复制前状态准备

关键源码：

```text
Engine/Source/Runtime/Engine/Private/Actor.cpp
  AActor::PreReplication()     // 1529 行
  AActor::CallPreReplication() // 1556 行
```

`AActor::PreReplication()` 默认会：

1. 调用 `GatherCurrentMovement()`；
2. 填充 `ReplicatedMovement`；
3. 准备 Attachment Replication 数据；
4. 更新 active override。

核心含义：

```text
复制调度前
  → Actor::PreReplication
      → GatherCurrentMovement
      → 写入 ReplicatedMovement
      → 本轮进入属性比较 / 序列化
```

`CallPreReplication()` 会继续对所有复制组件调用：

```cpp
Component->PreReplication(...)
```

因此复杂 Actor 的复制前准备是：

```text
Actor::PreReplication
  ├─ Actor 自身复制字段
  └─ Replicated Components 的 PreReplication
```

### 13.3 为什么不要在 Client 直接改 Replicated Property

普通属性复制方向是：

```text
Authority Server → Client Replica
```

Client 直接修改：

```cpp
Health -= 10;
```

只会改本地副本；下一次服务端权威值复制下来，通常会被覆盖。

正确链路：

```text
Client 行为意图
  → Server RPC
  → Server 校验
  → Server 修改权威属性
  → 属性复制给相关 Client
  → Client OnRep 更新 UI / 表现
```

---

## 14. 服务端发包：TickFlush 与 ServerReplicateActors

### 14.1 网络发送入口

```text
UWorld::Tick
  → BroadcastTickFlush
  → UNetDriver::InternalTickFlush
  → UNetDriver::TickFlush
```

源码：

```text
Engine/Source/Runtime/Engine/Private/NetDriver.cpp
  UNetDriver::TickFlush() // 953 行
```

UE 5.4.4 在该函数中存在两个主要复制分支：

```text
Legacy:
  UNetDriver::ServerReplicateActors()

Iris:
  UReplicationSystem::PreSendUpdate()
```

### 14.2 Legacy ServerReplicateActors 的五阶段

源码：

```text
Engine/Source/Runtime/Engine/Private/NetDriver.cpp
  UNetDriver::ServerReplicateActors() // 5757 行
```

```text
ServerReplicateActors(DeltaSeconds)
  │
  ├─ 1. ServerReplicateActors_PrepConnections()
  │      └─ 决定本帧要更新哪些连接
  │
  ├─ 2. ServerReplicateActors_BuildConsiderList()
  │      ├─ 遍历活跃网络 Actor
  │      ├─ 检查 NetUpdateFrequency / NextUpdateTime
  │      ├─ 调用 Actor::CallPreReplication()
  │      └─ 构建本帧候选 Actor
  │
  └─ 3. 对每条 ClientConnection：
      ├─ 构建 FNetViewer
      ├─ PlayerController::SendClientAdjustment()
      ├─ 4. PrioritizeActors()
      │      └─ relevance、距离、上次更新时间、优先级
      ├─ 5. ProcessPrioritizedActorsRange()
      │      └─ 打开/复用 ActorChannel，复制 Actor
      └─ MarkRelevantActors()
             └─ 维护 relevance、channel 生命周期、dormancy
```

关键位置：

```text
BuildConsiderList                  // 5813 行
FNetViewer 创建                    // 5877~5887 行
SendClientAdjustment               // 5890~5903 行
PrioritizeActors                   // 5920 行
ProcessPrioritizedActorsRange      // 5924 行
MarkRelevantActors                 // 5926 行
```

---

## 15. Relevancy、Priority、NetUpdateFrequency 与 Dormancy

### 15.1 Relevancy：该连接是否需要知道该 Actor

核心判断近似为：

```text
Actor->IsNetRelevantFor(Viewer, ViewTarget, ViewLocation)
```

常见影响因素：

- 距离；
- Owner；
- `bAlwaysRelevant`；
- `bOnlyRelevantToOwner`；
- 附着关系；
- ViewTarget / ViewLocation；
- ReplicationGraph 或 Iris 自定义过滤。

Relevancy 是 **per connection** 的：

```text
Actor X
  ├─ 对 Client A：Relevant
  ├─ 对 Client B：Not Relevant
  └─ 对 Client C：Relevant
```

### 15.2 Priority：相关不代表本帧必然发送

带宽或 CPU 不足时，UE 会综合：

```text
NetPriority
LastRepTime
距离与观察视角
bPendingNetUpdate
连接带宽预算
本帧 CPU 是否 Saturated
```

对 Actor 排序后再发送。

因此：

- `NetUpdateFrequency` 调高不等于最终显示更新率一定提高；
- 远处或低优先级 Actor 在拥挤网络条件下可能延迟；
- 高价值、近距离、长时间未更新的 Actor 更容易获得发送机会。

### 15.3 Dormancy：静态对象不要持续比较

典型对象：

```text
门、宝箱、静态建筑、已落地掉落物
```

优化思路：

```text
长时间不变化
  → 进入 Dormant
  → 减少 consideration、属性比较和复制器维护
  → 状态变化时 FlushNetDormancy / 唤醒
```

常见错误：

```text
Server 修改了 Dormant Actor 的复制属性
  但没有唤醒或 FlushNetDormancy
  → Client 可能无法及时收到更新
```

---

## 16. UActorChannel：每条连接上的 Actor 复制会话

`UActorChannel` 的正确理解：

```text
“某一条 Connection 上，某一个 Actor 的复制会话”
```

而不是全局唯一的 Actor 网络通道：

```text
Server Connection A → Actor X → ActorChannel AX
Server Connection B → Actor X → ActorChannel BX
```

每个连接都有独立状态：

- 对该 Actor 是否相关；
- 上次发给该客户端的状态；
- 属性 Delta；
- Dormancy 状态；
- Reliable Bunch 未确认队列；
- 已知子对象。

所以 Server 并非只生成一份“Actor X 网络包”然后直接广播，而是按连接计算：

```text
Actor X 对 Connection A 的可见状态
Actor X 对 Connection B 的可见状态
Actor X 对 Connection C 的可见状态
```

这也是大量玩家与大量 Actor 时复制成本高的根本原因。

---

## 17. PackageMap 与 NetGUID：对象引用如何跨机器

当复制字段包含：

```cpp
UPROPERTY(Replicated)
AActor* TargetActor;
```

UE 不会传 Server 的内存指针，而是：

```text
Server UObject / Actor
  → 分配或解析 FNetworkGUID
  → 包中发送 NetGUID
  → Client 的 PackageMap 查询该 GUID
  → 得到本地 UObject / Actor
```

结构：

```text
Object Reference
  → FNetworkGUID
  → UPackageMapClient
  → NetGUIDCache
  → Client UObject / Actor
```

它解决：

1. Server / Client 内存地址不同；
2. 对象或子关卡可能尚未加载，映射需要延迟。

这也是 RPC 参数和对象引用可能出现以下问题的原因：

- Unmapped GUID；
- RPC 延迟；
- 目标对象尚未 Spawn；
- 子关卡尚未可见；
- Travel / Streaming 期间映射失效或延后。

---

## 18. RPC：发送、接收与最终执行

### 18.1 发送侧

```text
Gameplay 调用 Server / Client / NetMulticast UFUNCTION
  → AActor::CallRemoteFunction
  → UNetDriver::ProcessRemoteFunction
  ├─ Iris：ReplicationSystem::SendRPC
  ├─ ReplicationGraph：ReplicationDriver::ProcessRemoteFunction
  └─ Legacy：找到 ActorChannel，序列化 RPC 参数
      → UNetConnection
      → Packet / Socket
```

`UNetDriver::ProcessRemoteFunction()` 的优先级：

```text
Iris
  → ReplicationSystem->SendRPC(...)

否则 ReplicationGraph
  → ReplicationDriver->ProcessRemoteFunction(...)

否则 Legacy 默认路径
  → InternalProcessRemoteFunction(...)
```

### 18.2 接收侧

```text
Socket 收到 Packet
  → UNetConnection::ReceivedPacket
  → Bunch 路由至 UActorChannel
  → 读取 Function / Object / 参数
  → FRepLayout::ReceivePropertiesForRPC
  → ShouldCallRemoteFunction 校验
  → UObject::ProcessEvent(Function, Params)
```

当前源码中最终执行位置：

```text
Engine/Source/Runtime/Engine/Private/DataReplication.cpp
  Connection->Driver->ForwardRemoteFunction(...)
  Object->ProcessEvent(Function, Parms); // 约 1368~1377 行
```

### 18.3 RPC 的安全边界

网络层只负责路由，不保证 Gameplay 请求合法。

例如：

```text
Client: ServerTryBuyItem(ItemId)
Server:
  ├─ 玩家是否拥有该连接？
  ├─ ItemId 是否有效？
  ├─ 交互距离是否满足？
  ├─ 金币是否足够？
  ├─ 冷却是否允许？
  └─ 通过后才修改权威状态并复制结果
```

服务端必须校验所有会影响权威状态的 Client 请求。

---

## 19. Legacy、ReplicationGraph 与 Iris

### 19.1 Legacy Replication

```text
UNetDriver::ServerReplicateActors
  → Consider List
  → 按连接做 Relevancy / Priority
  → UActorChannel
  → FObjectReplicator / FRepLayout
```

优点：

- 逻辑直观；
- 适合中小规模项目；
- 有成熟的调试经验与源码路径。

限制：

- 传统结构容易走向“活跃 Actor × Connection”的高成本；
- 大世界、海量 Actor、高并发时 CPU 压力明显。

### 19.2 ReplicationGraph

入口：

```cpp
if (ReplicationDriver)
{
    return ReplicationDriver->ServerReplicateActors(DeltaSeconds);
}
```

它主要替换：

```text
如何组织 Actor
如何为每个连接找到相关 Actor
```

通常按以下节点组织：

- 空间格子；
- Always Relevant；
- Owner Relevant；
- Connection-specific；
- Dormancy；
- 自定义玩法规则节点。

本质是避免每帧以朴素方式遍历全部 Actor 再对每个连接筛选。

### 19.3 Iris

UE 5.4.4 的 `UNetDriver::TickFlush()` 中：

```cpp
ReplicationSystem->PreSendUpdate(...)
```

Iris 的相关源码目录：

```text
Engine/Source/Runtime/Experimental/Iris/Core/
  Private/Iris/ReplicationSystem/
  Public/Iris/ReplicationSystem/
```

概念结构：

```text
Replication System
  ├─ NetObject
  ├─ Replication State
  ├─ Fragments
  ├─ Filtering
  ├─ Prioritization
  ├─ Polling
  ├─ Serialization
  └─ RPC Support
```

两者不要混淆：

- **ReplicationGraph**：主要是 Actor 组织、相关性与连接复制列表的可扩展调度方案；
- **Iris**：是更深入的对象复制状态、过滤、序列化、调度与 RPC 架构演进。

---

## 20. Actor 生命周期与网络生命周期

普通 Actor 生命周期：

```text
SpawnActor
  → Constructor
  → PostActorCreated
  → OnConstruction
  → PreInitializeComponents
  → InitializeComponent
  → PostInitializeComponents
  → BeginPlay
  → Tick
  → EndPlay
  → Destroyed
  → GC
```

网络生命周期：

```text
Server Actor Spawn
  → bReplicates = true
  → 加入 NetworkObjectList
  → 对某 Connection 变为 Relevant
  → 创建 UActorChannel
  → 初始 Spawn / Replication Bunch
  → Client 创建或关联 Actor
  → 属性更新 / RPC / 子对象同步
  → 不再 Relevant：Channel 关闭或滞后保留
  → Dormant / Wake
  → Destroy Replication
  → Client 销毁对应 Actor
```

注意：

- `BeginPlay` 不等于“网络初始化完成”；
- `OnRep` 与 `BeginPlay` 的先后不应被硬编码假设；
- Actor Reference 可能暂时未映射；
- Streaming、Dormancy、Travel 都可能改变实际到达顺序。

推荐采用：

- `OnRep`；
- 显式初始化状态机；
- `PostNetInit` / `PostNetReceive` 等网络钩子；
- 对未映射对象引用做好容错；
- 在 Possess、Owner、PlayerState 改变时重新绑定依赖。

---

## 21. Level Streaming 与网络 Actor 初始化

Level 加入 World 时，网络相关初始化链路：

```text
UWorld::AddToWorld
  → Level->InitializeNetworkActors()
  → Level->RouteActorInitialize(...)
  → Level->SortActorList()
```

源码：

```text
Engine/Source/Runtime/Engine/Private/World.cpp
  3344~3351：InitializeNetworkActors
  3357~3371：RouteActorInitialize
```

Client 使子关卡可见后还会向 Server 上报：

```cpp
LocalPlayerController->ServerUpdateLevelVisibility(LevelVisibility);
```

源码：`World.cpp` 3409～3417 行。

这意味着：

```text
Level 已加载
  ≠ 该 Level 的 Actor 已可安全完成网络交互
```

还要考虑：

- 该连接是否已确认 Level Visible；
- Server 认为该连接哪些 Streaming Levels 可见；
- Actor 所属 Level；
- NetGUID 是否能解析；
- Travel / World Partition / 子关卡卸载时机。

---

## 22. 常用 Gameplay 数据应该放在哪里

| 需求 | 推荐对象 |
|---|---|
| 跨地图、本机账号、缓存、网络服务 | `GameInstance` / `GameInstanceSubsystem` |
| 服务器规则、登录、出生、胜负裁决 | `GameMode` / `GameSession` |
| 全局可见的对局阶段、时间、比分 | `GameState` |
| 每个玩家公开资料、队伍、分数、名字 | `PlayerState` |
| 本玩家输入、镜头、私有 Client RPC、UI 入口 | `PlayerController` |
| 角色位置、生命、动作、可见装备 | `Pawn` / `Character` / Components |
| 仅拥有者可见的私有角色数据 | Pawn / Component + `COND_OwnerOnly` |
| 本地 UI、Widget 动画、表现缓存 | `HUD` / `Widget` / `LocalPlayerSubsystem` |
| 大量可变集合，如背包、Buff、任务 | `FastArraySerializer` 或 Iris 对象状态 |

---

## 23. 调试路线

### 23.1 Client 为什么没有收到属性

按以下顺序排查：

```text
1. Server 是否真的修改了权威变量？
2. Actor 是否 bReplicates？
3. 属性是否通过 DOREPLIFETIME 注册？
4. 是否被条件复制过滤？
5. Actor 对该 Connection 是否 Relevant？
6. Actor 是否 Dormant？
7. 是否因 Priority / 带宽预算而延后？
8. Client 是否已有该 Actor，NetGUID 是否已映射？
9. OnRep 是否被实际调用？
```

推荐断点：

```text
AActor::CallPreReplication
UNetDriver::ServerReplicateActors_BuildConsiderList
UNetDriver::ServerReplicateActors_PrioritizeActors
UActorChannel::ReplicateActor
FObjectReplicator / FRepLayout 的发送逻辑
```

### 23.2 Server RPC 为什么没执行

```text
1. 是否由 owning client 发起？
2. Actor 是否存在有效 Owner / OwningConnection？
3. UFUNCTION 网络标记是否正确？
4. 是否在 Game Thread 调用？
5. Actor 是否正 Destroy 或 TearOff？
6. Connection 是否处于 Open 状态？
7. Server 是否收到相应 Packet / Bunch？
```

推荐断点：

```text
AActor::CallRemoteFunction
UNetDriver::ProcessRemoteFunction
UNetConnection::ReceivedPacket
DataReplication.cpp 中 RPC 接收与 Object->ProcessEvent
```

### 23.3 BeginPlay 或初始化顺序异常

推荐断点：

```text
AGameModeBase::StartPlay
AGameStateBase::HandleBeginPlay
AGameStateBase::OnRep_ReplicatedHasBegunPlay
UWorld::BeginPlay
ULevel::InitializeNetworkActors
ULevel::RouteActorInitialize
```

---

## 24. 推荐源码阅读路线

不要从 `NetDriver.cpp` 第一行读到最后一行；应按问题驱动阅读。

### 第一阶段：先建立 Gameplay 语义

```text
GameInstance.cpp
  → GameEngine.cpp
  → World.cpp
  → GameModeBase.cpp
  → GameStateBase.cpp
  → PlayerController.cpp
  → PlayerState.cpp
  → Pawn.cpp / Character.cpp
```

目标：理解谁在 Server、谁在 Client、谁应同步、谁不应同步。

### 第二阶段：读普通属性复制

```text
LevelTick.cpp
  → NetDriver.cpp::TickFlush
  → NetDriver.cpp::ServerReplicateActors
  → Actor.cpp::CallPreReplication / PreReplication
  → ActorChannel.cpp
  → DataReplication.cpp
  → RepLayout / ObjectReplicator
```

目标：理解 `UPROPERTY(Replicated)` 如何从服务端变量变动抵达客户端 `OnRep`。

### 第三阶段：读连接与 RPC

```text
PendingNetGame.cpp
  → NetDriver.cpp::InitConnect / InitListen
  → NetConnection.cpp::ReceivedPacket
  → World.cpp::NotifyControlMessage
  → World.cpp::WelcomePlayer
  → Actor.cpp::CallRemoteFunction
  → NetDriver.cpp::ProcessRemoteFunction
  → DataReplication.cpp 的 RPC 接收与执行
```

目标：理解握手、登录、Join、RPC 路由、参数反序列化与 `ProcessEvent`。

### 第四阶段：读规模化方案

```text
NetDriver.cpp
  → ReplicationGraph 模块
  → Experimental/Iris/Core
  → 项目自身 ReplicationGraph / Iris 配置
```

目标：理解高并发、海量 Actor 下如何优化相关性、过滤与优先级调度。

---

## 25. 示例：一次“玩家开火”的端到端网络链路

```text
[Owning Client]

PlayerController 输入
  → Pawn / WeaponComponent 本地预测表现
  → ServerFire(TargetData) RPC
  → AActor::CallRemoteFunction
  → UNetDriver::ProcessRemoteFunction
  → UNetConnection 发包


[Server]

UNetConnection::ReceivedPacket
  → UActorChannel 接收 RPC Bunch
  → DataReplication 反序列化 RPC 参数
  → UObject::ProcessEvent(ServerFire_Implementation)
  → 校验距离、弹药、冷却、命中
  → 修改权威 Health、Ammo、Gameplay State
  → 可选：NetMulticast 播放短暂表现
  → 本帧 UWorld::TickFlush
      → Legacy ServerReplicateActors
        或 Iris ReplicationSystem::PreSendUpdate
      → 按 Connection Relevancy / Priority 复制变化


[All Relevant Clients]

UNetConnection::ReceivedPacket
  → UActorChannel / 属性反序列化
  → Health、Ammo 等字段更新
  → OnRep_Health / OnRep_Ammo
  → UI、动画、特效等客户端表现更新
```

---

## 26. 最终速记

```text
UGameInstance
  进程级、跨地图、本机服务容器；不自动网络复制。

UWorld
  一张地图的运行时总调度中心；网络与 Gameplay 在此汇合。

UNetDriver
  一个 World 的网络收发、连接管理与复制调度器。

UNetConnection
  一条远端连接的状态、Channel、带宽与收发上下文。

UActorChannel
  某条连接上某个 Actor 的复制会话。

AGameMode
  仅 Server 存在；负责规则、登录、出生、胜负裁决。

AGameState
  Server 规则状态向 Client 的复制镜像。

APlayerController
  拥有连接、输入、Client/Server RPC 的枢纽。

APlayerState
  每个玩家对全体可见的公共身份与战局数据。

APawn / ACharacter
  可控制、可模拟、可复制的游戏实体。
```


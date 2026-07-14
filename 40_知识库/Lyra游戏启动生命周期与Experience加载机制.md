---
area:
tags: [UE, Lyra, 生命周期, Experience, GameFeature, 启动流程]
created: 2026-07-14
source: Lyra / Source/LyraGame（GameModes, System）+ Config/DefaultEngine.ini, DefaultGame.ini
aliases: [Lyra启动流程, Experience加载机制, Lyra生命周期]
---
# Lyra 游戏启动生命周期与 Experience 加载机制

## 定义
Lyra 的启动不是传统 UE 项目那种「GameMode 里写死一堆玩法逻辑」的模式，而是一套**数据驱动 + 异步加载 + 插件化（GameFeature）**的启动架构。核心思想一句话：

> 地图只负责把关卡摆出来，「这一局到底是什么玩法」完全由一个叫 `Experience`（体验）的数据资产异步决定；玩家在 Experience 加载完成前一直被「挂起」，加载完才真正 Spawn。

传统做法是「一个 GameMode 子类 = 一种玩法」，玩法之间靠 `if/switch` 或继承树切换。Lyra 抛弃了这套，把「玩法」抽象成可插拔的数据资产 + 插件，换玩法只需换一个 `ExperienceDefinition`，策划不写 C++ 也能配出新模式。

## 全局位置
在整个 Engine 启动链中的层级：

```
引擎启动 (Launch)
  └─ UGameEngine::Init
       ├─ AssetManager (LyraAssetManager)   ← 全局单例，最早初始化
       └─ GameInstance  (ULyraGameInstance) ← 进程级，跨关卡存活
            └─ World / GameMode (ALyraGameMode)      ← 每张地图一个（仅服务端权威）
                 └─ GameState (ALyraGameState)        ← 每张地图一个（客户端也有）
                      └─ ExperienceManagerComponent   ← 玩法加载的“心脏”
                           └─ GameFeatureSubsystem     ← 按需启用玩法插件
                                └─ GameFeatureAction    ← 真正把玩法“装配”到世界
```

配置层入口（`Config/DefaultEngine.ini`）确定了这条链的起点：

```ini
AssetManagerClassName=/Script/LyraGame.LyraAssetManager
GlobalDefaultGameMode=/Game/B_LyraGameMode.B_LyraGameMode_C
GameInstanceClass=/Game/B_LyraGameInstance.B_LyraGameInstance_C
GameDefaultMap=/Game/System/FrontEnd/Maps/L_LyraFrontEnd.L_LyraFrontEnd
```

## 为什么这样设计
| 维度 | 动机 |
|---|---|
| 解耦 | 玩法逻辑（武器、AI、UI、输入）封装成 GameFeature 插件，与主程序 `LyraGame` 模块零编译依赖，可独立开关 |
| 数据驱动 | 换玩法 = 换一个 `ExperienceDefinition` 数据资产，无需改 C++ |
| 异步无卡顿 | Experience 及依赖资产全部异步流式加载，加载期显示 Loading Screen，不阻塞主线程 |
| 网络同步 | `CurrentExperience` 是 Replicated 属性——服务端决定玩法，客户端通过 `OnRep` 自动走同样加载流程，天然对齐 C/S |
| 按需内存 | 只有当前 Experience 需要的 GameFeature 才 Load+Activate，退出时 Deactivate，内存随玩法进出 |

代价是启动链路变长、时序更绕（大量异步回调 + 委托），调试门槛高；换来的是可扩展性和模块隔离，这正是一个「示范工程」的核心卖点。

## 四阶段生命周期
```
【阶段0：引擎级 一次性初始化】（进程启动，跨所有关卡只做一次）
 UGameEngine::Init
   → GEngine->AssetManager = LyraAssetManager   （由 DefaultEngine.ini 指定类名）
   → ULyraAssetManager::StartInitialLoading()    ← 引擎调用
        ├─ Super::StartInitialLoading()  扫描所有 PrimaryAsset（Experience/GameData/Map…）
        ├─ STARTUP_JOB: InitializeGameplayCueManager()  预加载常驻 GameplayCue
        ├─ STARTUP_JOB: GetGameData()  同步加载 DefaultGameData（权重25，最重）
        └─ DoAllStartupJobs()  跑完所有启动任务（服务端直跑，客户端带进度条）

【阶段1：GameInstance 级】（进程级，第一张地图之前）
 ULyraGameInstance::Init()   ← 引擎调用
   → 注册 4 个 InitState（Spawned→DataAvailable→DataInitialized→GameplayReady）
   → 绑定 CommonSession / CommonUser 等在线子系统事件

【阶段2：地图/关卡级】（每次 OpenLevel / ServerTravel 触发）
 ALyraGameMode::InitGame()          ← 引擎在地图加载时调用
   → SetTimerForNextTick(HandleMatchAssignmentIfNotExpectingOne)  延一帧
 ALyraGameMode::InitGameState()     ← 引擎调用
   → ExperienceComponent->CallOrRegister_OnExperienceLoaded(OnExperienceLoaded)  注册回调
 [下一帧] HandleMatchAssignmentIfNotExpectingOne()
   → 按优先级决定用哪个 Experience → OnMatchAssignmentGiven()
   → ExperienceManagerComponent->SetCurrentExperience(ExperienceId)

【阶段3：Experience 加载（异步状态机，本架构的心脏）】
 SetCurrentExperience → StartExperienceLoad → OnExperienceLoadComplete
   → LoadAndActivateGameFeaturePlugin（逐个异步）→ OnExperienceFullLoadCompleted
   → 执行所有 GameFeatureAction（Register→Load→Activate）
   → LoadState = Loaded，广播 OnExperienceLoaded（High/Normal/Low 三档优先级）

【阶段4：玩家进入】
 OnExperienceLoaded 回调 → ALyraGameMode::OnExperienceLoaded
   → 遍历所有已连接但没 Pawn 的 PlayerController → RestartPlayer → Spawn Pawn
```

关键设计点：GameMode 的 `HandleStartingNewPlayer` 被重写——如果 Experience 没加载完，玩家登录后**不 Spawn**，一直等到 `OnExperienceLoaded` 回调里统一补 Spawn。

## 核心调用链
全程运行在 **Game Thread**，异步加载部分由 **StreamableManager** 在后台线程做 IO、回主线程发回调。

### ① 服务端决定玩法
`HandleMatchAssignmentIfNotExpectingOne` 按优先级裁决用哪个 Experience（高者胜）：

```
Matchmaking 分配 > URL Options > DeveloperSettings(PIE) > CommandLine
  > WorldSettings > Dedicated Server > Default(B_LyraDefaultExperience)
```

选定后 `OnMatchAssignmentGiven → SetCurrentExperience(Id)`。

### ② 异步加载资产 + 插件
```
StartExperienceLoad  [GameThread 发起]
  → AssetManager.ChangeBundleStateForPrimaryAssets(...)  [后台 IO 加载 Bundle]
  → BindCompleteDelegate(OnExperienceLoadComplete)
      ↓ (资产就绪，回到 GameThread)
OnExperienceLoadComplete
  → 收集 GameFeaturePlugin URL
  → UGameFeaturesSubsystem::LoadAndActivateGameFeaturePlugin(url, 回调)  [异步，逐个]
      ↓ (每个插件完成 NumGameFeaturePluginsLoading--)
OnExperienceFullLoadCompleted   （计数归零时触发）
  → 执行 GameFeatureAction：OnGameFeatureRegistering → Loading → Activating
  → LoadState = Loaded
  → OnExperienceLoaded_HighPriority / Normal / LowPriority 依次 Broadcast
```

### ③ 客户端镜像同一流程（无需 GameMode）
```
Server 改 CurrentExperience → 网络复制 → Client: OnRep_CurrentExperience
  → StartExperienceLoad()  （客户端走完全相同的加载状态机）
```

### ④ 玩家出生
```
OnExperienceLoaded → ALyraGameMode::OnExperienceLoaded
  → for each PlayerController without Pawn:
      PlayerCanRestart → RestartPlayer
        → SpawnDefaultPawnAtTransform_Implementation
            → GetPawnDataForController（从 Experience->DefaultPawnData 取）
            → SpawnActor<APawn>(PawnData->PawnClass)  bDeferConstruction=true
            → PawnExtComp->SetPawnData(PawnData)   ← 关键：把数据注入 Pawn
            → FinishSpawning()
```

`bDeferConstruction=true` 的原因：要在 `FinishSpawning` 之前先把 `PawnData` 塞进 `LyraPawnExtensionComponent`，这样 Pawn 的组件在初始化（BeginPlay / InitState 流转）时就能拿到数据来源。这是 Lyra「数据先行」设计的体现。

## 数据流
玩法配置层层下沉到 Pawn，全程数据驱动、无硬编码玩法：

```
DefaultEngine.ini / DefaultGame.ini        （配置层）
  → AssetManager类 / GameInstance类 / GameMode类 / DefaultMap / PrimaryAssetTypesToScan
      ↓
ExperienceDefinition 资产 (B_LyraDefaultExperience)   （玩法定义层）
  ├─ GameFeaturesToEnable[]   → 要启用哪些插件
  ├─ Actions[] / ActionSets[] → 要执行哪些装配动作
  └─ DefaultPawnData          → 默认角色数据
      ↓
ExperienceManagerComponent（GameState 上的组件）      （运行时装配层）
  → 加载资产 → 启用 GameFeature → 执行 Action
      ↓
GameFeatureAction（AddComponents / AddInputBinding / AddWidget…）  （效果注入层）
  → 往世界里的 Actor 动态挂组件、绑输入、加 UI
      ↓
LyraPawnExtensionComponent  ← SetPawnData(PawnData)   （Pawn 数据落地）
  → 驱动 Pawn 的能力(ASC)、输入、相机等按数据初始化
```

## 关键成员（ExperienceManagerComponent）
组件本身是整个启动的异步状态机，最影响逻辑的成员：

- `CurrentExperience` → 当前玩法定义 → `SetCurrentExperience`/`OnRep` 时写入 → GameMode 与各系统读取。**Replicated**，服务端权威、客户端镜像。
- `LoadState` → 加载状态枚举（Unloaded→Loading→LoadingGameFeatures→ExecutingActions→Loaded）→ 每个异步回调推进 → `IsExperienceLoaded()` / `ShouldShowLoadingScreen()` 读取。
- `NumGameFeaturePluginsLoading` → 剩余未加载完的插件计数 → 每个插件回调 `--` → 归零即触发 `OnExperienceFullLoadCompleted`。本质是一个**异步 join 计数器**。
- `OnExperienceLoaded_High/Normal/LowPriority` → 三档优先级委托 → Loaded 时按序 Broadcast → 让「底层系统先于业务逻辑」初始化（例如 ASC 要先于 UI 就绪）。

## 关键函数
- `ALyraGameMode::HandleMatchAssignmentIfNotExpectingOne` —— 启动后延一帧调用，按优先级裁决用哪个 Experience。延一帧是为了让 URL Options、命令行等启动参数先完成初始化。
- `ExperienceManagerComponent::StartExperienceLoad` —— 客户端与服务端**共用入口**（服务端由 SetCurrentExperience 调，客户端由 OnRep 调），保证 C/S 加载逻辑完全一致。
- `OnExperienceFullLoadCompleted` —— 真正「完成」的收口点，执行所有 GameFeatureAction 并翻转 `LoadState=Loaded`。内建 `lyra.chaos.ExperienceDelayLoad` 混沌测试延迟，故意拖慢加载以测 Loading Screen 健壮性。
- `ALyraGameMode::OnExperienceLoaded` —— 玩法就绪后批量补 Spawn 那些提前登录、被挂起的玩家。这是「玩家为什么等玩法加载完才出生」的答案。

## 设计模式
- **State Machine**：`ELyraExperienceLoadState` 驱动整个异步加载。
- **Observer / 委托**：三档优先级 `OnExperienceLoaded` + `CallOrRegister`（已加载则立即回调，否则注册等待）——经典的「迟到者也能拿到结果」模式，参见 [[UE设计模式-简单工厂模式（CommonGameDialogDescriptor）]] 系列里对委托的讨论。
- **Data-Driven / 策略**：`ExperienceDefinition` 数据资产即可插拔的玩法策略。
- **Plugin / GameFeature**：玩法作为可热插拔插件，是 UE 官方推的模块化方案。
- **Singleton**：`ULyraAssetManager::Get()`。
- **Deferred Construction**：Pawn 延迟构造 + 数据注入。

## 性能考量
- **全程异步流式加载**：`ChangeBundleStateForPrimaryAssets` 走 StreamableManager 后台 IO，主线程不阻塞，加载期靠 Loading Screen 遮盖。
- **Bundle 精准加载**：根据 NetMode 只加载需要的 Bundle（`LoadStateClient` / `LoadStateServer` / `Equipped`），专用服务器不加载客户端资源，省内存。
- **启动任务加权进度**（`STARTUP_JOB_WEIGHTED`）：`GetGameData` 权重 25，让进度条更贴近真实耗时。
- **专用服务器快路径**：`DoAllStartupJobs` 里 `IsRunningDedicatedServer()` 直接跑任务、跳过进度回调开销。

## 修改影响
- 改 **Experience 选择优先级**（`HandleMatchAssignmentIfNotExpectingOne`）→ 影响所有关卡进入哪个玩法，PIE/命令行/Matchmaking 全受影响，极易踩坑。
- 改 **Spawn 时机**（`OnExperienceLoaded` / `HandleStartingNewPlayer`）→ 直接影响玩家出生、重连、Bot 生成；时机错了会导致 Pawn 拿不到 PawnData。
- 改 **GameFeatureAction 激活顺序** → 影响能力(GAS)、输入、UI 的注册顺序，`HighPriority` 委托里的系统假设自己最先跑。
- 改 **CurrentExperience 复制** → 破坏 C/S 玩法一致性，客户端可能永远停在 Loading。

## 调试建议
- **断点位置**：`HandleMatchAssignmentIfNotExpectingOne`（看选中的 ExperienceId）、`StartExperienceLoad`、`OnExperienceFullLoadCompleted`（看 LoadState 翻转）、`OnExperienceLoaded`（看谁触发 Spawn）。
- **日志**：`LogLyraExperience` 通道全程打点（`EXPERIENCE: StartExperienceLoad...` / `Identified experience...`），开 `-LogCmds="LogLyraExperience Verbose"`。
- **控制台命令**：`Lyra.DumpLoadedAssets` 看 AssetManager 加载了什么；`lyra.chaos.ExperienceDelayLoad.MinSecs` 人为拖慢加载测 Loading Screen。
- **观察变量**：`LoadState`、`NumGameFeaturePluginsLoading`、`CurrentExperience`。
- 卡在 Loading 不动 → 多半是 `OnMatchAssignmentGiven` 里 ExperienceId 无效（日志会打 `loading screen will stay up forever`）。

## 相关概念
- [[UE设计模式-工厂方法模式（GameSettingScreen.CreateRegistry）]]
- [[UE设计模式-简单工厂模式（CommonGameDialogDescriptor）]]
- [[Lyra GameFeature 插件与 GameFeatureAction 装配机制]]
- [[LyraPawnExtensionComponent 与 InitState 组件握手机制]]
- [[Lyra AssetManager 启动任务与 GameData 加载]]

## 参考资料
- 源码：`Source/LyraGame/GameModes/LyraGameMode.cpp`、`LyraExperienceManagerComponent.cpp`、`System/LyraGameInstance.cpp`、`System/LyraAssetManager.cpp`
- 配置：`Config/DefaultEngine.ini`（AssetManager/GameInstance/GameMode/DefaultMap）、`Config/DefaultGame.ini`（PrimaryAssetTypesToScan、LyraGameDataPath、DefaultPawnData）
- 排查过程：本地仓库 `F:\30_Resources\Personal\LyraStarterGame` 源码通读（2026-07）

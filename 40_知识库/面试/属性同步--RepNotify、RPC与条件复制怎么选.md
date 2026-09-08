## 一、先讲清楚 UE4 的网络架构长什么样

在讨论”属性同步”之前，得先明白 UE4 是**客户端-服务器（Client-Server）架构**：

```text
                ┌──────────────┐
                │  Dedicated                 │
                │    Server                  │  ← 权威端（Authority）
                │   （DS）                   │    所有关键数据的唯一真相
                └──────┬───────┘
                                      │
        ┌──────────────┼────────────┐
        │                             │                        │
   ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
   │Client A          │    │   Client B │    │    │         Client C │  ← 客户端只是"镜像"
   └─────────┘    └─────────┘    └─────────┘
```

**核心原则**（记住这三条，后面所有内容都是这三条的推论）：

1. **服务器是唯一权威**：所有关键状态（血量、位置、装备）都以 DS 上的为准
2. **客户端不可信**：客户端只是把服务器状态”渲染”出来
3. **两种同步手段**：

- **属性同步（[Replication](https://zhida.zhihu.com/search?content_id=279067661&content_type=Article&match_order=1&q=Replication&zhida_source=entity)）**：服务器 → 客户端**单向**、传递**状态**
- **RPC（远程过程调用）**：**双向**、传递**事件**

  

**画个更直观的比喻**：

```text
属性同步 = 服务器的"公告栏"
         DS 每次改变公告栏内容，客户端就会看到最新版本
         你什么时候来看都能看到当前状态

RPC     = 服务器的"广播喇叭"
         DS 喊一嗓子，当时听到的人就响应
         没听到？那就永远错过了
```

这个比喻你先记住，后面选型全靠它。

---

## 二、属性同步（Replication）——是什么、为什么、怎么做

### 2.1 是什么

**属性同步**：把一个 [UPROPERTY](https://zhida.zhihu.com/search?content_id=279067661&content_type=Article&match_order=1&q=UPROPERTY&zhida_source=entity) 变量标记为 `Replicated`，DS 上这个变量的值一旦变化，UE 会自动把新值下发给所有客户端。

```text
UCLASS()
class AMyCharacter : public ACharacter
{
    GENERATED_BODY()
public:
    AMyCharacter()
    {
        bReplicates = true;  // ① Actor 总开关必须打开
    }

    UPROPERTY(Replicated)    // ② 属性标记为可同步
    float Health = 100.f;

    // ③ 告诉 UE 这个属性怎么同步
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
};

void AMyCharacter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(AMyCharacter, Health);
}
```

三步走：**Actor 开总开关**、**变量打标记**、**注册到复制列表**。

### 2.2 为什么要有属性同步（RPC 不够用吗？）

来看一个经典场景：

> **场景**：一个 MOBA 游戏，A 玩家在 3 秒前把 B 玩家打成 20 血。此时 C 玩家从远处走过来，第一次进入 B 的可见范围（成为”相关”）。  
> C 客户端上，B 的血量应该显示多少？

如果用 RPC 广播扣血事件：Multicast_TakeDamage(20)；**3 秒前那次广播时**，UE 会做两件事：

1. 遍历所有玩家的 Connection
2. 对每个 Connection 检查：”这个 Actor 对你相关吗？”（距离、视野、ViewTarget 等）

C 当时离得太远，**B 这个 Actor 对 C 不相关，UE 直接跳过 C 这条 Connection**——哪怕这个 RPC 是 Reliable 的，也**不会**为 C 保留、等它相关时再补发。

3 秒后 C 走过来，UE 才开始把 B 同步到 C 的世界。但那次 `TakeDamage(20)` 的广播已经**永远消失**了。C 看到的 B 是**默认满血** ❌

> 💡 **这就是 RPC 的”过时不候”本质**： RPC 只在发送那一刻，对当时相关的 Connection 生效。 **不相关的 Connection = 直接丢弃，不补发**。

如果用属性同步 Health，DS 上 `Health = 20`——这是**当前状态**，而不是”发生过什么”。C 进入范围、B 对 C 变得相关时，UE 会自动把 B 当前的所有可同步属性**打包推送**给 C——包括 `Health = 20`。

C **立刻**看到 B 是残血 ✅

> 💡 **这就是属性同步的”来者不拒”本质**： 属性同步传递的是”世界当前长什么样”。 **任何时候变得相关的 Connection，都能拿到最新快照**。

**这就是核心区别**：

|维度|属性同步|RPC|
|---|---|---|
|传递的是|状态（当前是什么）|事件（发生了什么）|
|迟到者能否感知|✅ 能（同步当前值）|❌ 不能（错过就错过）|
|网络可靠性|一定送达（Reliable）|可选 Reliable/Unreliable|
|频率|帧末打包，可能合并|立即或帧末，取决于可靠性|

**一句话**：**属性同步是”来者不拒”，RPC 是”过时不候”**。（这个说法来自知乎作者，非常精辟）

### 2.3 怎么做——三种同步方式对比

UE4 里属性同步分**三档**，从简单到强大：

### 档位 1：`Replicated`——只同步值，不做任何回调

```text
UPROPERTY(Replicated)
float Health = 100.f;
```

**适用场景**：只是显示数字，比如 Tick 里读取 `Health` 更新 UI。

### 档位 2：`[ReplicatedUsing](https://zhida.zhihu.com/search?content_id=279067661&content_type=Article&match_order=1&q=ReplicatedUsing&zhida_source=entity)`（RepNotify）——同步值 + 触发回调

```text
UPROPERTY(ReplicatedUsing = OnRep_Health)
float Health = 100.f;

UFUNCTION()
void OnRep_Health();  // 客户端收到新值时自动调用
void AMyCharacter::OnRep_Health()
{
    // 客户端接到新血量时的表现层反应
    PlayHitEffect();
    UpdateHealthBar();
    if (Health <= 0)
    {
        PlayDeathAnimation();
    }
}
```

**RepNotify 的关键价值**：它保证**回调触发时，值已经是新值**。这解决了一个非常反直觉的问题——

**⚠️ 一个新手容易踩的坑**：

```text
// ❌ 错误做法：DS 上改完属性立刻调 RPC 让客户端做事
Health -= 20;
Multicast_OnDamaged();  // 客户端收到 RPC 时，Health 可能还没同步过来！
```

网络同步是有时序的。RPC 和属性同步都是**帧末打包**，但**到达客户端的顺序不保证**。你在 DS 上是”先改属性再发 RPC”，客户端可能是”先收到 RPC 再收到属性”。

**✅ 正确做法**：把逻辑写在 `OnRep_Health` 里，UE 保证回调触发时 `Health` 已经是最新值。

### 档位 3：`[DOREPLIFETIME_CONDITION](https://zhida.zhihu.com/search?content_id=279067661&content_type=Article&match_order=1&q=DOREPLIFETIME_CONDITION&zhida_source=entity)`——条件复制

不是所有属性都要同步给所有客户端。比如：

- 玩家的**背包物品**——只需要同步给玩家自己，不用同步给其他玩家（省带宽 + 防作弊）
- 玩家的**位置和血量**——所有人都需要看到

UE 提供了**条件复制**：

```text
void AMyCharacter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    
    // 血量：所有人都能看到
    DOREPLIFETIME(AMyCharacter, Health);
    
    // 背包：只同步给自己（OwnerOnly）
    DOREPLIFETIME_CONDITION(AMyCharacter, Inventory, COND_OwnerOnly);
    
    // 移动数据：只同步给非本地玩家（本地玩家自己算，模拟端才需要）
    DOREPLIFETIME_CONDITION(AMyCharacter, ReplicatedMovement, COND_SimulatedOnly);
    
    // 初始化后不再同步：比如角色的固定属性
    DOREPLIFETIME_CONDITION(AMyCharacter, MaxHealth, COND_InitialOnly);
}
```

**常用 Condition 一览**：

|枚举|含义|典型用途|
|---|---|---|
|COND_None|所有客户端都同步|通用状态（血量、位置）|
|COND_OwnerOnly|只同步给拥有者|背包、金币、私有信息|
|COND_SkipOwner|不同步给拥有者|本地玩家自己算过的数据|
|COND_SimulatedOnly|只同步给模拟端|别人看到的位置/朝向|
|COND_InitialOnly|只在初始化时同步一次|固定不变的配置|
|COND_Custom|自定义条件|复杂业务规则|

**条件复制的价值**：

1. **省带宽**：DS 的上行带宽是稀缺资源，房间 100 人时每个字节都要抠
2. **防作弊**：其他玩家的私有数据（比如手牌）绝不能同步到别人的客户端

---

## 三、RPC——是什么、为什么、怎么做

### 3.1 是什么

**RPC（Remote Procedure Call）**：在本地调用一个函数，UE 帮你把这个调用**转发到远端机器**上执行。

三种类型：

|类型|谁调用|谁执行|用途|
|---|---|---|---|
|Server|客户端|DS|客户端上报操作（我要开枪）|
|Client|DS|拥有者客户端|DS 通知玩家（弹出 UI）|
|[NetMulticast](https://zhida.zhihu.com/search?content_id=279067661&content_type=Article&match_order=1&q=NetMulticast&zhida_source=entity)|DS|DS + 所有客户端|广播事件（爆炸特效）|

```text
// 客户端调用，DS 执行
UFUNCTION(Server, Reliable, WithValidation)
void Server_Fire(FVector Direction);

// DS 调用，拥有者客户端执行
UFUNCTION(Client, Reliable)
void Client_ShowRewardUI(int32 Gold);

// DS 调用，所有客户端执行
UFUNCTION(NetMulticast, Unreliable)
void Multicast_PlayExplosionEffect(FVector Location);
```

### 3.2 为什么要有 RPC

回到那个”公告栏 vs 广播喇叭”的比喻：

- 有些信息是**持续状态**——用公告栏（属性同步）
- 有些信息是**瞬时事件**——用广播喇叭（RPC）

**举个例子**：

```text
// 玩家开枪的瞬间要播放一个开火特效
Multicast_PlayFireEffect();  // ✅ RPC 合适

// 玩家当前的血量
UPROPERTY(ReplicatedUsing = OnRep_Health)  // ✅ 属性同步合适
float Health;
```

如果强行用属性同步做”开火特效”——你得加个 `bool bIsFiring`，然后 `OnRep_bIsFiring` 播特效，然后还得手动改回 `false`……**用错工具**。

反过来，如果用 RPC 做血量——新玩家进来看不到当前血量。**也是用错工具**。

### 3.3 Reliable vs Unreliable

```text
UFUNCTION(Server, Reliable)         // 保证送达，网络差会重传
UFUNCTION(Server, Unreliable)       // 不保证送达，丢了就丢了
```

**选择原则**：

|场景|选择|原因|
|---|---|---|
|开枪、扣血、扣金币|Reliable|关键逻辑，绝不能丢|
|脚步声、特效、非关键动画|Unreliable|丢了无所谓，别堵塞网络|
|高频调用（Tick 内）|优先 Unreliable|Reliable 队列会撑爆|

**⚠️ 一个陷阱**：Reliable RPC 的发送队列是有上限的，队列满了会**踢玩家下线**。所以别在 Tick 里发 Reliable RPC。

### 3.4 RPC 的”过时不候”陷阱

看两个真实场景（来自实际项目沉淀）：

**陷阱 1：广播 RPC 会被视野过滤**

DS 发广播 RPC 时，UE 会检查每个 Connection 的 `ViewTarget`。如果玩家还没初始化好 `ViewTarget`（比如刚连上服务器的下一帧），这个 RPC 会**被直接丢弃**。

```text
// ❌ 危险：Controller 初始化时立刻广播
void AMyPlayerController::BeginPlay()
{
    Super::BeginPlay();
    Multicast_AnnouncePlayerJoined();  // 大概率被过滤！
}
```

**陷阱 2：弱网玩家收不到广播**

当某个客户端断线超过 1.5 秒，UE 会把该 Connection 的 `ViewTarget` 设为 null。这段时间内的所有广播 RPC，这个玩家都**收不到**。

这就引出了本文的重头戏——

---

## 四、【重点】什么时候用属性同步，什么时候用 RPC？

### 4.1 一张决策表

面对一个同步需求，先问自己四个问题：

```text
Q1：这是"当前状态" 还是 "瞬时事件"？
    状态 → 属性同步
    事件 → RPC

Q2：迟到者需要感知吗？
    需要 → 属性同步
    不需要 → RPC

Q3：断线重连后需要恢复吗？
    需要 → 属性同步（必须）
    不需要 → RPC 也可以

Q4：需要双向通信（客户端 → DS）吗？
    需要 → RPC（属性同步是单向的）
    不需要 → 都可以，看 Q1-Q3
```

### 4.2 常见需求场景对照表

|需求|选择|理由|
|---|---|---|
|玩家血量|✅ 属性同步（RepNotify）|状态；迟到者要看；断线重连要恢复|
|玩家位置|✅ 属性同步（内置）|状态；持续变化|
|开火特效|✅ Multicast RPC|瞬时事件；迟到者不需要看|
|爆炸伤害|✅ Multicast RPC|瞬时事件|
|装备列表|✅ 属性同步（OwnerOnly）|状态；需要防作弊|
|玩家上报”我要开枪”|✅ Server RPC|双向；单次事件|
|匹配成功通知玩家|✅ Client RPC|单次事件|
|房间当前波次|✅ 属性同步（RepNotify）|状态；断线重连要恢复|
|倒计时开始|✅ Multicast RPC|事件（起点确定，客户端本地推算）|
|剩余倒计时秒数|✅ 属性同步|状态（迟到者要看到剩余多少）|

### 4.3 【DS 项目实战】断线重连场景——必须用属性同步

这是我在实际项目中总结的**最核心的一条经验**，也是很多新手会栽跟头的地方。

**场景描述**：

> 一个 DS 房间战斗打到第 5 波，血量还剩 30，此时玩家 A 手机没信号断线。10 秒后 A 重连回房间——他应该看到：**当前是第 5 波、血量 30**，而不是”第 1 波、满血”。

**如果用 RPC 传递状态**：

```text
// ❌ 错误做法
UFUNCTION(NetMulticast, Reliable)
void Multicast_OnWaveStart(int32 WaveIndex);  // 波次开始时广播

UFUNCTION(NetMulticast, Reliable)
void Multicast_OnHealthChanged(float NewHealth);  // 血量变化时广播
```

**问题**：

- 玩家 A 断线时错过了”第 5 波开始”的广播
- 玩家 A 断线时错过了”血量从 100 掉到 30”的广播
- 重连后 A 客户端上的状态还停留在断线前的”第 4 波、血量 100”
- **DS 不会为了 A 一个人再补发所有历史 RPC**

**✅ 正确做法：用属性同步**

```text
// 波次管理器
UCLASS()
class AWaveManager : public AActor
{
    GENERATED_BODY()
public:
    AWaveManager()
    {
        bReplicates = true;
        bAlwaysRelevant = true;  // 关键：断线重连后必然要同步
    }

    UPROPERTY(ReplicatedUsing = OnRep_CurrentWave)
    int32 CurrentWave = 0;

    UPROPERTY(ReplicatedUsing = OnRep_WaveState)
    EWaveState WaveState = EWaveState::Idle;

    UFUNCTION()
    void OnRep_CurrentWave();
    
    UFUNCTION()
    void OnRep_WaveState();
};

// 角色血量
UPROPERTY(ReplicatedUsing = OnRep_Health)
float Health = 100.f;
```

**为什么属性同步天然支持断线重连**？

回到我们的比喻：**属性同步是”公告栏”**。DS 上公告栏的内容就是**当前真相**。玩家断线重连时，UE 会自动把所有相关 Actor 的**当前属性值**推送给他——不管他离开多久，都能看到最新状态。

而 **RPC 是”广播喇叭”**，喊过就没了。DS 不会为断线玩家保存 RPC 历史。

### 4.4 一个混合使用的经典案例

**需求**：塔防波次开始时，所有玩家听到”敌人来袭”的语音提示。

**错误做法 1**（纯 RPC）：

```text
Multicast_PlayWaveStartAudio();  // 断线重连玩家听不到
Multicast_ShowWaveUI(5);          // 断线重连玩家看不到当前波次
```

**错误做法 2**（纯属性同步）：

```text
UPROPERTY(ReplicatedUsing = OnRep_WaveState)
EWaveState State;  // 播语音放在 OnRep 里？重连玩家会重复听语音！
```

**✅ 正确做法（混合使用）**：

```text
// 状态用属性同步——保证断线重连能看到当前波次
UPROPERTY(ReplicatedUsing = OnRep_CurrentWave)
int32 CurrentWave;

UFUNCTION()
void OnRep_CurrentWave()
{
    UpdateWaveUI(CurrentWave);  // 只更新 UI，不播语音
}

// 瞬时事件用 RPC——只有当时在场的玩家听到语音
UFUNCTION(NetMulticast, Unreliable)
void Multicast_PlayWaveStartAudio();

// DS 侧的波次开始逻辑
void AWaveManager::StartNextWave()
{
    CurrentWave++;                          // ← 属性变化，自动同步（保证状态）
    Multicast_PlayWaveStartAudio();         // ← 事件广播（当下听到语音）
}
```

**这就是分工**：

- 属性同步 = **写公告栏**（谁来了都能看当前波次）
- RPC = **喊一嗓子**（当下在场的听语音，迟到者不用重听）

---

## 五、总结与决策清单

### 5.1 核心模型

```text
┌─────────────────────────────────────────────┐
│                                             │
│    属性同步 = 公告栏 = 状态 = 来者不拒       │
│    RPC     = 广播喇叭 = 事件 = 过时不候      │
│                                             │
└─────────────────────────────────────────────┘
```

### 5.2 三条铁律

1. **凡是断线重连需要恢复的，必须用属性同步**——血量、位置、波次、装备、金币
2. **凡是”错过就没了”的瞬时表现，用 RPC**——特效、语音、一次性提示
3. **绝对不要在 RPC 里传递持久状态**——你以为省事了，未来会加倍还回来

### 5.3 面试问答备忘

**Q：RepNotify 相比普通 Replicated 的价值？** A：保证回调触发时值已经是新值，避免”改属性 + 发 RPC”顺序不一致的问题；同时可以把表现层逻辑（播特效、更新 UI）集中在 OnRep 里，代码更清晰。

**Q：为什么状态不能用 RPC？** A：RPC 是”过时不候”的瞬时事件，不为迟到者/断线重连玩家保留历史。而属性同步是”来者不拒”的当前状态快照，UE 会在客户端建立 Actor 时自动推送最新值。

**Q：条件复制的价值？** A：省带宽 + 防作弊。玩家的私有信息（背包、手牌）用 `COND_OwnerOnly` 只同步给自己；模拟端才需要的数据用 `COND_SimulatedOnly` 排除本地玩家。

**Q：Reliable RPC 能滥用吗？** A：不能。Reliable 有发送队列上限，队列满会踢玩家下线；Tick 内绝不能发 Reliable RPC。高频事件优先用 Unreliable，或者干脆改用属性同步。
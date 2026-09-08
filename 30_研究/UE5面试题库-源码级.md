# UE5 客户端面试题库 · 源码级

> 引擎版本 **UE 5.4.4**（`F:\10_Projects\RA\AEngine`）
> 所有行号均实际核对过。**注意：网上大量 UE4 时代的 GC / GAS 文章在 5.4 已过时。**

---

## 使用说明

分三档，按这个顺序记：

| 档位 | 含义 | 怎么用 |
|---|---|---|
| 🔴 **必背** | 一个字都不能错的结论 + 行号 | 背下来，能默写 |
| 🟠 **要理解** | 机制原理，要能自己讲出来 | 理解后用自己的话说 |
| 🟢 **加分** | 说出来显得读过源码 | 记住关键词，能提一句 |

每题结构：**问题 → 一句话答案 → 展开 → 你的项目怎么接 → 追问预案**

---

# 第 0 章 · 开局必背卡（考前十分钟看这个）

## 十条核心结论

| # | 结论 | 行号 |
|---|---|---|
| 1 | `TickInterval` 是**重新排队**，不是跳过这一帧 | `TickTaskManager.cpp:970` |
| 2 | `bShouldCallTick=false` **不能**省掉 `GetDataView` | `StateTreeExecutionContext.cpp:2179` |
| 3 | 多个 `Multiply` Modifier 是**加法叠加**（两个 ×1.5 = ×2.0） | `GameplayEffectTypes.cpp:106` |
| 4 | Clamp **必须**同时写 `PreAttributeChange` 和 `PreAttributeBaseChange` | `LyraHealthSet.cpp:189/196` |
| 5 | GC 里"标记全世界不可达"是 **O(1) 的 flag 交换** | `GarbageCollection.cpp:4263` |
| 6 | `Destroy()` 之后默认最多 **60 秒**才真正释放内存 | `UnrealEngine.cpp:1602` |
| 7 | **Infinite GE 根本不跑 Executions**（ExecCalc 不会被调） | `GameplayEffect.cpp:4225` |
| 8 | StateTree 的 `StateCompleted` 在抢占式迁移时**不会被调**，清理必须写 `ExitState` | `StateTreeTaskBase.h:55` |
| 9 | GAS 里**冷却和消耗检查在 Tag 检查之前** | `GameplayAbility.cpp:393/403/413` |
| 10 | 移动端 `gc.MaxObjectsInGame` 只有 **131072**（PC 是 2M） | `AndroidEngine.ini:13` |

## 三个"绝不能吹"的点

1. **SignificanceManager 我没用过** —— 它在 `Engine/Plugins/Runtime/SignificanceManager/`，`uplugin:13` 写着 `"EnabledByDefault": false`，而且 `Update()` 在插件内**零调用者**，必须业务自己调。
2. **网络同步 / DS 我没做过** —— 项目是单机/本地 AI，GAS 没跑过 Replication。可以讲机制，但要说清是知识储备。
3. **图形 API / Shader 我没写过** —— 我的工作在 Gameplay 层，性能优化集中在 GameThread 和逻辑层。

诚实说这三条**不减分**。硬吹被追问细节才是致命的。

---

# 第 1 章 · StateTree（简历占比最大，必问）

## 🔴 Q1-1 `bShouldCallTick = false` 到底省了什么？

**一句话**：省掉绑定属性拷贝 + 两个 profiling scope + 虚函数调用，但**省不掉 `GetDataView`**。

**核心那一行**（`StateTreeExecutionContext.cpp:2189`）：

```cpp
const bool bNeedsTick = bShouldTickTasks
    && (Task.bShouldCallTick || (bHasEvents && Task.bShouldCallTickOnlyOnEvents));
if (!bNeedsTick) { continue; }        // :2191
```

`continue` 掉之后省三块，**按开销从大到小**：

| 省掉的                | 位置                                   | 说明                                                                                  |
| ------------------ | ------------------------------------ | ----------------------------------------------------------------------------------- |
| **绑定属性拷贝**         | `:2198` `CopyBatchOnActiveInstances` | 最实质的节省。`TaskBase.h:90` 注释原话："Not ticking implies **no property copy**"              |
| 两个 profiling scope | `:2206-2207`                         | `QUICK_SCOPE_CYCLE_COUNTER` + `CSV_SCOPED_TIMING_STAT_EXCLUSIVE`，Development 下不是零成本 |
| 虚函数派发 + Task 逻辑    | `:2209`                              |                                                                                     |

**⚠️ 必须主动补的自我修正**：

> `:2179` 的 `GetDataView` 在判定**之前**，省不掉。所以 `bShouldCallTick=false` 是"遍历到但不做事"，**不是"从遍历中消失"**。

主动说这句 = 证明你读的是源码不是文档。

### 你的答法（背这段）

> 拆出来的 8 个 Task 里只有 3 个真需要每帧：MovingToPoint（判到达）、PlayingMontage（等动画）、Waiting（走计时）。剩下 5 个是瞬时逻辑，我设 `bShouldCallTick = false`，改成在 `EnterState` 里干完直接 `return Succeeded`，靠 `OnStateSucceeded` 推进。
>
> 收益在 `bNeedsTick` 那行判定——为 false 就 continue，跳过绑定拷贝、两个 profiling scope、虚调用。不过 `GetDataView` 在判定之前，那部分省不掉。

### 追问预案

**Q：想彻底不遍历有办法吗？**
> 只有 `bTaskEnabled == false`（`TaskBase.h:105`，判定在 `:2183`），但它的 continue 也在 `GetDataView` 之后，同样省不掉，而且是资产配置不是运行时开关。真要让 Task 消失只能不进那个 State。

**Q：不 Tick 的 Task 还能推动状态机吗？**
> 能，两条路：① `EnterState` 返回非 Running（`:1391`）② `bShouldAffectTransitions = true`（`TaskBase.h:101`）+ 重写 `TriggerTransitions()`，在 `:2499` 被调，比 Tick 便宜且不做属性拷贝。

---

## 🔴 Q1-2 OnTick vs OnEvent 的成本差异

**一句话**：OnTick 每帧跑 `TestAllConditions`，OnEvent 在事件队列空时 O(1) 早退，整个条件求值一次都不进。

**核心短路**（`:2557-2566`）：

```cpp
bShouldTrigger = Transition.Trigger == OnTick                    // 恒 true
              || (Transition.Trigger == OnEvent && HasEventToProcess(Tag));
if (bShouldTrigger) { bPassed = TestAllConditions(...); }        // :2566
```

| | OnTick | OnEvent（无事件） |
|---|---|---|
| Transition 表扫描（`:2509`） | 有 | 有（**省不掉**） |
| `TestAllConditions`（`:2248`） | **每帧全跑** | 不跑 |
| 带校验的绑定拷贝（`:2276`） | 每帧 | 不跑 |
| `ResetObjects`（`:2292`） | 每帧 | 不跑 |
| 括号栈表达式求值（`:2301-2334`） | 每帧 | 不跑 |

`HasEventToProcess` 在队列空时 `EventsToProcess.IsEmpty()` 直接早退（`ExecutionContext.h:213`），成本 = 两次整数比较。

**🟢 隐藏陷阱**：`:2557` 用的是 `==` 精确匹配不是 `EnumHasAnyFlags`，所以 **OnTick 和 OnEvent 互斥**。配 `OnTick | OnEvent` 想做双保险会两边都不匹配、永不触发。

### 你的答法

> 重构初版我几个关键迁移配的是 OnTick + Condition，比如"到达墙体了吗""墙体资源还可用吗"。Profile 后发现 `StateTree_TestConditions` 这个 CSV stat（`:2250`）在 40 只僵尸下明显偏高。
>
> 原因在 `:2557`：OnTick 恒 true，每帧进 `TestAllConditions`。而这个函数每个条件都要 `GetDataView` + 带校验的绑定拷贝 + 虚函数 `TestCondition` + `ResetObjects`（因为 Condition 实例数据是 shared 的），最后还有一套括号栈表达式求值。
>
> 改成 OnEvent + GameplayTag 后，事件队列空时直接早退。落地方式是让"到达检测"的所有权归到明确一方——MoveTo 完成的回调里 `SendEvent`，而不是让 Transition 每帧轮询。
>
> 有个坑：`:2557` 用 `==` 不是 `EnumHasAnyFlags`，所以两者互斥，不能配 `OnTick | OnEvent` 做双保险，得配成两条独立 Transition。

---

## 🟠 Q1-3 为什么 `ExitState` 一定会被调用？

**一句话**：靠一对"进入失败水位标" + 节点的广度优先布局，用**一个整数比较**代替"已进入 Task 集合"容器。

**三步机制**：

```cpp
// :1267-68  EnterState 开头
Exec.EnterStateFailedTaskIndex = FStateTreeIndex16::Invalid;
// 注释原话："This will make all tasks to be accepted"

// :1404-06  某 Task Failed 时记水位标然后 break
Exec.EnterStateFailedTaskIndex = FStateTreeIndex16(TaskIndex);

// :1561  ExitState 用它筛选
if (TaskIndex <= Exec.EnterStateFailedTaskIndex.Get())
```

**三层精妙（这是加分点）**：

1. **利用节点 BF 布局** —— `:1559` 注释："The task order in the tree (BF) allows us to use the comparison"。零分配零查找。
2. **Invalid = MAX_uint16 是刻意的** —— 没失败时 `TaskIndex <= MAX_uint16` 恒真，**同一个比较式无分支覆盖正常和失败两条路**。
3. **`ActiveStates` 只含真正 Enter 过的状态** —— `:1294-95` 注释 + `:1317` 逐个 Push。

**🔴 配套必背**：`StateCompleted` **不是必然调用的**。`TaskBase.h:55` 注释："StateCompleted is **not** called if conditional transition changes the state"。抢占式迁移直接 `ExitState`。**所以清理必须写在 ExitState。**

### 你的答法

> 重构前最难写对的是清理。单 Task 管 9 阶段，`ExitState` 里要根据枚举判断该取消 MoveTo、还是停 Montage、还是释放墙体占用，漏一个 case 就是泄漏。而抢占式迁移时 `StateCompleted` 不会被调，所有清理都得在 `ExitState`，让那个大 switch 更难维护。
>
> 拆开后每个 Task 的 `ExitState` 只干一件事，而且引擎保证配对——`:1404` 记水位标，`:1561` 用 `TaskIndex <= EnterStateFailedTaskIndex` 筛选，失败点之前的 Task 一定被 Exit。所以我能放心把"占用墙体"和"释放墙体"写成一对 Enter/Exit。

---

## 🟠 Q1-4 StateTree vs BehaviorTree

**⚠️ 这题有反杀点**。如果你说"BT 每帧从根遍历整棵树"，好的面试官会追："你确定？UE 的 BT 有 SearchData 和局部重搜。"

**准确说法（背这段）**：

> BT 的开销不在"重走一遍树"，而在**每帧 tick 所有活跃的 Decorator/Service 来监视条件是否变化**（`BehaviorTreeComponent.cpp:1743-52`）。条件一变触发 `RequestExecution` 局部重搜（`:1785`）。所以 BT 是"**持续轮询条件 + 变化时重新规划**"。
>
> StateTree 是"**状态驻留 + 只在显式 Transition 触发时重选**"（`StateTreeExecutionContext.cpp:2418` → `:2788`）。BT 把"什么时候该换行为"分摊到每帧条件轮询；StateTree 收敛成 Transition 表的一次查表 + 条件求值，还能配成 OnEvent 连查表都省掉。

**接项目**：

> 我们巡逻状态平均驻留秒级，切换稀疏。BT 的 Decorator 模型会把"监视切换条件"摊到每帧；StateTree 允许我做成 OnEvent——僵尸走向巡逻点的几百帧里，引擎只跑 MoveTo 一个 Task 的 Tick，Transition 连条件都不求值。

---

## 🟠 Q1-5 共享数据放 AIController 上的利弊（考判断力，不考记忆）

**双向论证，讲代价比讲收益更加分。**

**利**：
1. N² → N（8 个 Task 两两共享，Property Binding 要拉组合级连线）
2. **生命周期跨状态进出**（最硬的理由）—— Task 的 InstanceData 在 `UpdateInstanceData`（`:652`）按状态激活分配，**状态退出数据就没了**；而"路线进度""失败计数"要跨越多次状态进出存活
3. **可调试** —— `InstanceStructs`（`InstanceData.h:233`）是裸内存块，调试器几乎不可读

**弊（诚实讲）**：
1. **绕过编译期类型安全** —— Property Binding 的检查在 `ResolveCopyType`（`PropertyBindings.cpp:433`），类型不兼容**资产编译就失败**
2. **Task 复用性下降** —— 绑定驱动的 Task 输入输出是自描述的；读 Controller 上下文的 Task 依赖藏在 .cpp 里。**"我实现了 10 个自定义 Task"的复用价值被打了折**
3. **"唯一写入方"是纪律不是机制** —— 编译器不检查

**加分收尾（主动给"如果重来"）**：

> 第二版我会分层：跨状态、长生命周期的路线级数据留 Controller；单次流转的短生命周期数据（这次的点位坐标、找到的墙体）改用 Property Binding。判断标准是**这份数据的生命周期是否跨越状态进出**。

---

## 🟢 Q1-6 三层失败语义的机制映射

| 层 | 用的原语 | 为什么是这个 |
|---|---|---|
| **路线级放弃** | `Failed` + **冒泡到子树出口** | `:2674` 逆序冒泡 + `:2716` 终止 = **try/catch**；不在点位状态配 handler 即为"未捕获" |
| **单点级快换** | `SelectionFallback::NextSelectableSibling` | `StateTreeTypes.h:474`，实现 `:2897-2921`。走兄弟链，**一次 SelectState 内完成，没有 Exit/Enter 往返** —— 这才是"不停留" |
| **到点后先停再换** | `Succeeded` + `SendEvent` + 带 Delay 的中间状态 | **它不是失败，是"成功了但结果需要转向"**。用 Failed 会丢失"到达了"这个信息 |

**关键洞察**：`Succeeded` 说"移动做完了"，事件说"但点位资源没了"——把**流程结果**和**业务原因**解耦。三层都用 Failed 就只能靠错误码区分，退回 switch 时代。

**两个机制细节**：
- **事件迁移天然优先于完成迁移**，不用配优先级。OnEvent 在第一段循环（`:2557`），完成迁移在第二段且被 `:2647` 的 `Priority == None` 守卫屏蔽
- 等待用 `Transition.Delay`（类型 `FStateTreeRandomTimeDuration`，`:516`），`GetRandomDuration()`（`:2577`）**自带随机**，一群僵尸不会同步

**追问：所有点位都不可用会死循环吗？**
> 三道闸：`MaxIterations=5`（`:464`）→ 跳回 Root（`:2724`）→ 整树 Failed（`:2739`）。**但这是"引擎不崩"的保护，不是"业务正确"的保护**。正确做法是维护重试计数，超过点位总数就升级成路线级失败——三层之间要有升级路径。

---

## 🟢 Q1-7 同 State 多 Task 的陷阱

`:2217-2231`：`Result` 被**后写覆盖**，且 Failed 会置 `bShouldTickTasks=false` 但**不 break**（为了继续更新 data view 让属性绑定正常）。

**所以同 State 多 Task 的完成语义依赖编辑器排列顺序** —— `:2216` 挂着 Epic 自己的 `// TODO: Add more control over which states can control the failed/succeeded result.`

**你的答法**：我是一个 State 一个主 Task，只在确实同生同死的地方用并行（比如 MovingToPoint 上同时挂 MoveTo 和播行走音效）。

---

## StateTree 自我批评（说出来加分）

> 回头看，`ArrivedAtPoint` 和 `GetNextPoint` 有点过度拆分——都是瞬时的、无条件流转的、也没被复用。如果只保留有独立 Transition 分支或有复用价值的状态，**5-6 个可能是更合适的粒度**。我当时拆到 8 个有一部分是"既然在拆就拆彻底"的惯性。

---

# 第 2 章 · 性能优化

## 🔴 Q2-1 `TickInterval` 是"跳过"还是"重新排队"？

**这题最能筛人。大多数人答"跳过"。**

**一句话**：**重新排队**。从活跃 TSet 摘出，挂到按剩余冷却排序的侵入式链表上。

**四步流程**：

| 步骤 | 位置 | 做什么 |
|---|---|---|
| 排队后摘出 | `TickTaskManager.cpp:970-974` | `It.RemoveCurrent()` 从 `AllEnabledTickFunctions` 删掉 |
| 暂存 | `:846-850` | `RescheduleForInterval` |
| 帧尾插链表 | `:1126` → `:895-956` | 插入 `AllCoolingDownTickFunctions` |
| 下帧只看到期的 | `:750-764` | 累加 `CumulativeCooldown`，`>= DeltaSeconds` 就 **break** |

**关键设计**：链表节点存的是 **`RelativeTickCooldown`——相对于前一个节点的增量**，不是绝对时间（`EngineBaseTypes.h:274-278`）。

> **设计意图**：每帧调度成本只和"本帧真正到期的数量"成正比。1 万个 5 秒 interval 的怪物，每帧只碰 ~40 个节点，其余 9960 个连一次比较都不做。"跳过"实现要每帧遍历 1 万次做时间比较。

**🔴 你项目必踩的坑**：

```
AActor::SetActorTickInterval             Actor.cpp:1312         只改字段，不动调度状态
FTickFunction::UpdateTickIntervalAndCoolDown  TickTaskManager.cpp:1898   立即生效
```

`SetActorTickInterval` 如果此刻 tick 正在冷却链表上，新值**要等这轮冷却走完**才生效。Component 侧有 `SetComponentTickIntervalAndCooldown`（`ActorComponent.cpp:1247`），**Actor 侧没有对应 API**。

### 你的答法

> 我做的是分档 interval（近距 0、中距 0.1s、远距 0.5s）。有个坑：`SetActorTickInterval` 只改字段，如果 tick 正在冷却链表上，新值要等这轮冷却走完才生效——想立即生效得走 `UpdateTickIntervalAndCoolDown`。
>
> 更远的怪物我直接 `SetActorTickEnabled(false)` 而不是给个很大的 interval，因为 disabled 是把 tick function 挪到 `AllDisabledTickFunctions`、连 `QueueTickFunction` 都不调，是真正零成本；interval 再大也还占一个链表节点。

**追问：interval 会累积漂移吗？**
> 不会。`:984` 和 `:809` 都是 `RescheduleForInterval(TickFunction, TickInterval - (DeltaSeconds - CumulativeCooldown))`，注释就是 `// Give credit for any overrun`。

---

## 🔴 Q2-2 销毁大量 Actor 为什么卡？（成本清单）

**一句话**：五类成本，**前四类是 `Destroy()` 当帧同步付掉的**，只有第五类是 GC 的。

| # | 成本 | 位置 | 线程 |
|---|---|---|---|
| ① | 组件反注册（含 tick function 摘链） | `LevelActor.cpp:1001` → `ActorComponent.cpp:1774` | GT |
| ② | **渲染代理销毁** | `PrimitiveComponent.cpp:798` → `RendererScene.cpp:2587` | **GT 派发 + RT 执行** |
| ③ | 物理体销毁（Chaos broadphase 更新） | `PrimitiveComponent.cpp:971` | GT |
| ④ | overlap / delegate 级联广播 | `LevelActor.cpp:930`、`:876` | GT |
| ⑤ | GC 压力 | 延迟到 GC 帧 | — |

**🟢 两个隐藏热点（说出来加分）**：

1. **①里藏着 O(N·M)** —— tick function 摘链时如果该组件在 CoolingDown 状态，是 **O(链表长度) 的线性搜索**（`TickTaskManager.cpp:1330-1370`）。**你既用了 interval 降频、又要批量销毁，正好撞上这个组合。**

2. **②的成本一半在 Render Thread，GT profiler 里看不见** —— GT 侧付 `STAT_RemoveScenePrimitiveGT`，RT 侧付 `FPrimitiveSceneInfo` 从 `FScene::Primitives` 移除 + GPU 资源释放。而且逐个 `RemovePrimitive` 会退化成 N 次 `ENQUEUE_RENDER_COMMAND`（批量接口在 `:2630`）。

### 你的答法

> 我限制每帧销毁 N 个。测法：`STAT_DestroyActor`（`LevelActor.cpp:804`）看单个怪物 Destroy 的 GT 总耗时，再拆 `STAT_UnregisterComponent`、`STAT_ComponentDestroyRenderState`、`STAT_RemoveScenePrimitiveGT`，按帧预算反推。
>
> 有一点我特别注意：渲染代理销毁的成本一半在 Render Thread，GT 的 profiler 里看不出来，所以我同时看了 Insights 的 RT 时间轴上 `FRemovePrimitiveCommand` 有没有堆积。

> ⚠️ **需要你补真实数据**。如果 N 当时是拍的，就说"当时是拍的值，事后用 Insights 验证了待销毁队列长度稳定在预期范围"——比编推导过程安全。

---

## 🔴 Q2-3 `Destroy()` 之后何时真正释放内存？

**一句话**：三段，跨度可能 60 秒。

**第一段：当帧同步（GT）**

`Actor.cpp:4748` → `LevelActor.cpp:802`，同步做完：`bActorIsBeingDestroyed = true`（`:871`）→ `EndPlay` → 解除附着 → `ClearComponentOverlaps` → **`UnregisterAllComponents`（`:1001`，最贵）** → `MarkAsGarbage`（`:1004`）→ 反注册 tick function（`:1011`）

打完 Garbage 标记后 `IsValid(Actor)` 立刻 false，**但对象内存还完好**。

**第二段：等 GC**

默认 `gc.TimeBetweenPurgingPendingKillObjects = 60.0f`（`UnrealEngine.cpp:1602`）。**最多等 60 秒。**

**第三段：GC 三小步**
1. `GatherUnreachableObjects`（`GarbageCollection.cpp:5074`）
2. `UnhashUnreachableObjects`（`:5908`）→ `ConditionalBeginDestroy()`
3. `IncrementalDestroyGarbage`（`:4643`）→ `ConditionalFinishDestroy()` → 真正析构 + `FreeUObject`

**一句话总结**：`Destroy()` 让 Actor 逻辑死亡 + 表现死亡（当帧同步），内存死亡要等 GC。

**🟢 追问：`IsPendingKillPending()` 和 `IsValid()` 的区别？**
> `Actor.h:3120`：`return bActorIsBeingDestroyed || !IsValidChecked(this);` 是**两个条件的或**。`bActorIsBeingDestroyed` 在 `DestroyActor` 一进门就置上（`:871`），Garbage 标记要到 `:1004`。**所以在 `EndPlay` 回调里 `IsValid(this)` 还是 true，但 `IsPendingKillPending()` 已经是 true。**

---

## 🟠 Q2-4 GC 为什么随对象数变慢？（5.4 版本）

**⚠️ 别答 UE4 的答案。** 5.4 里静态 `EInternalObjectFlags::Unreachable` 已 `UE_DEPRECATED`。

**三个反直觉的事实**：

**① Root set 不是扫出来的，是维护出来的**
```cpp
// GarbageCollection.cpp:585-586
static TSet<int32> GRoots;
```
`AddToRoot()` 往里加索引。标记起点 O(RootCount) 不是 O(TotalObjects)。

**② "标记全世界不可达"是 O(1)**
```cpp
// GarbageCollection.cpp:4263  MarkObjectsAsUnreachable 核心就这一行
Swap(GReachableObjectFlag, GMaybeUnreachableObjectFlag);
```
**交换两个 flag 位的语义**，不遍历任何对象。这是 5.4 最重要的优化。

**③ 真正的 O(N) 只有两处**
- `GatherUnreachableObjects`（`:5074`，上界 `GetObjectArrayNum()`）—— 引擎为此把 `FUObjectItem` 做了 `GCC_PACK(4)`（`UObjectArray.h:33-37`），只读打包的 flags 不碰 `UObject` 本体
- **KeepFlags 慢分支**（`:4215-4232`）—— 遍历所有对象**并解引用每个 `UObject` 读 `ObjectFlags`**。源码注释原话："**This is super slow** as we need to look through all existing UObjects and access their memory"。**而引擎主循环调的正是 `TryCollectGarbage(GARBAGE_COLLECTION_KEEPFLAGS, ...)`（`UnrealEngine.cpp:1932`）—— 这条慢路径在正常 gameplay 里是活的**，每对象一次 cache miss

**🟢 移动端的墙（投手游公司必提）**：`gc.MaxObjectsInGame` PC 默认 2M，但 **Android/iOS 覆盖成 131072**（`AndroidEngine.ini:13`、`BaseIOSEngine.ini:9`）。撞了直接 fatal。

---

## 🔴 Q2-5 你埋的 Counter 用的是哪个宏？

**两个宏本质不同**：

```cpp
// TRACE_INT_VALUE 展开（CountersTrace.h:186）—— 函数局部 static
static FCounterInt __TraceCounter<__LINE__>(DisplayName, Hint);
```
→ 标识符带 `__LINE__`，**任何其他行、其他文件都无法引用**。只能 `Set()`（绝对赋值），**不能 Add/Increment**。

```cpp
// TRACE_DECLARE_INT_COUNTER 展开（CountersTrace.h:202）—— 可链接的全局对象
FCounterInt __GTraceCounter##Name(...);
```
→ 配 `_EXTERN` 在头文件里 extern，才能让 `TRACE_COUNTER_INCREMENT` / `ADD` 从**不同 TU 修改同一个计数器**。

### 你的答法

> 我用的是 `TRACE_INT_VALUE`，因为 counter 都是在调度器的 Tick 里一处集中上报当前值（活跃数、休眠数、本帧回收数），不需要跨 TU 增减。如果要在 spawn 和 despawn 两处分别 increment/decrement，就得用 `TRACE_DECLARE_INT_COUNTER` + `_EXTERN` 声明成全局对象，因为 `TRACE_INT_VALUE` 展开出的是带 `__LINE__` 的函数局部 static，别处引用不到。

**🟢 两个加分点**：
- **多线程**：非 atomic 版本的 `Value` 是裸 `int64`（`:171`），在 `ParallelFor` 里 increment 是数据竞争，要用 `TRACE_DECLARE_ATOMIC_INT_COUNTER`
- **关闭时成本**：每个 mutator 都被 channel 门控，值没变时提前返回。**本地 `Value` 始终维护，只是不发包** —— 热路径上可以放心埋

**🔴 最有说服力的一条 counter**：**待销毁队列长度**。它的曲线应该是**锯齿而不是尖刺** —— 这直接证明分帧销毁生效了。

---

## 🟢 Q2-6 TickGroup 与 TaskGraph 的关系

**一句话**：帧开头一次性创建所有 tick task 并 **Hold 住**，TickGroup 推进只是分批 **Unlock**。

```
TickTaskManager.cpp:443   ConstructAndHold(...)     ← 创建但不放行
TickTaskManager.cpp:672   TickArray[Index]->Unlock() ← 这一刻才进 TaskGraph 队列
```

**设计意图**：依赖关系（Prerequisites）在排队阶段一次性算完，运行时不需要再做调度判断。

**两个要点**：
- **TickGroup 是"最早可开始"不是"一定在"**。Prerequisite 会把你往后拖：`MyActualTickGroup = Max(MaxPrerequisiteTickGroup, ...)`（`:2010`）。**随手 `AddTickPrerequisiteActor` 可能让 Actor 从 PrePhysics 掉到 PostPhysics。**
- `TG_StartPhysics`/`TG_EndPhysics` 不可降级（`:104-113`）

**接项目**：
> 我的调度器放 `TG_PrePhysics` 且 `bHighPriority = true`（`EngineBaseTypes.h:214`，注释就是 "Run this tick first within the tick group"），这样同一帧内它做出的休眠/唤醒决定能立刻影响本帧后续的怪物 tick；否则决策要延迟一帧。

---

# 第 3 章 · GAS

## 🔴 Q3-1 Aggregator 的计算公式（最高频）

**公式（背下来）**：

```cpp
// GameplayEffectAggregator.cpp:79
return ((InlineBaseValue + Additive) * Multiplicitive) / Division;
```

$$\text{Result} = \frac{(\text{Base} + \sum\text{Add}) \times \sum\text{Mul}}{\sum\text{Div}}$$

**Override 短路**（`:60-66`）：第一条 `Qualifies()` 的直接 return，忽略一切其他 Mod。

**🔴 Bias 机制（最容易踩的坑）**：

```cpp
// GameplayEffectTypes.cpp:106
static const float ModifierOpBiases[] = {0.f, 1.f, 1.f, 0.f};
//                                       Add  Mul  Div  Override

// SumMods（:194-207）
float Sum = Bias;
for (Mod : InMods)
    if (Mod.Qualifies())
        Sum += (Mod.EvaluatedMagnitude - Bias);
```

**所以两个 `×1.5` 的结果是 `×2.0`，不是 `×2.25`**：`1 + (1.5-1) + (1.5-1) = 2.0`

**算例（能现场推）**：MaxHealth Base=100，挂 `+50`、`+30`、`×1.5`、`×1.2`
```
Additive       = 0 + 50 + 30              = 80
Multiplicitive = 1 + (1.5-1) + (1.2-1)    = 1.7      ← 不是 1.5×1.2=1.8
Result = ((100 + 80) × 1.7) / 1 = 306
```

**想要真乘法**：放到不同的 Evaluation Channel —— 上一个 Channel 的输出是下一个的 BaseValue（`:232-235`）。

### 你的答法（这个经历比理论有说服力）

> 服装防护体系一开始我设计成每件装备给一个 Multiply Modifier——面具 ×0.7、防护服 ×0.6、手套 ×0.9，预期 `0.7×0.6×0.9=0.378`。实测是 **0.2**，防护效果远超预期，平衡崩了。
>
> 查到 `SumMods` 的 Bias 逻辑才明白：`1 + (0.7-1) + (0.6-1) + (0.9-1) = 0.2`，Multiply 是**加法叠加**。
>
> 最后改成每件装备给 Add Modifier（防护点数），在结算里自己算 `防护率 = 总点数/(总点数+100)` 的递减曲线，参数从 DataTable 读。既符合 Add 语义，又做出了"堆防护有递减收益"的手感。
>
> 另外我用 Override 做了"致命疾病"——患病时直接 Override 防护值为 0，无视一切装备。正好利用了 Override 短路一切的特性。

**追问：两个 Override 同时生效？**
> `:60-66` 遇到第一条 `Qualifies()` 就 return，**注册顺序在前的胜出**。GAS 没有 Override 优先级，要做优先级得靠 Channel 或 Tag 互斥。

**追问：叠层怎么参与计算？**
> 不在 Aggregator 里，算 magnitude 时就乘进去了。`ComputeStackedModifierMagnitude`（`GameplayEffectTypes.cpp:112-130`）同样用 Bias 平移，且 **Override 完全无视叠层**（注释 `:121`）。

---

## 🔴 Q3-2 六个钩子的时机 + Clamp 该放哪（最高频）

**这是区分"抄过 Lyra"和"读过源码"的分水岭。**

| 场景 | PreGEExecute | PreAttrBaseChange | PreAttributeChange |
|---|---|---|---|
| Instant GE | ✅ | ✅ | ✅ |
| **Periodic GE 每 tick** | ✅ | ✅ | ✅ |
| Duration GE **挂载** | ❌ | ❌ | ✅ |
| Duration GE **过期移除** | ❌ | ❌ | ✅ |
| Duration GE 被 Tag 抑制 | ❌ | ❌ | ✅ |
| 叠层数变化 | ❌ | ❌ | ✅ |
| `SetHealth()` | ❌ | ✅ | ✅ |
| `InitHealth()` | ❌ | ❌ | ❌ |

**引擎注释是最好的答案**（`AttributeSet.h:209-215`，背这段）：

> `PreAttributeChange`... **There is no additional context provided here since anything can trigger this. Executed effects, duration based effects, effects being removed, immunity being applied, stacking rules changing, etc.**

**三组钩子的分工**：

| 钩子 | 能拿到什么 | 该写什么 |
|---|---|---|
| `Pre/PostGameplayEffectExecute` | **`FGameplayEffectModCallbackData`**（EffectSpec、Target、可写的 EvaluatedData） | Meta Attribute 转换、免疫判定、事件广播、结算日志 |
| `Pre/PostAttributeBaseChange` | 只有 Attribute + NewValue，**是 const** | **只准 clamp BaseValue** |
| `Pre/PostAttributeChange` | 只有 Attribute + NewValue | 纯 clamp、纯派生 |

### 🔴 Clamp 必须双写

Lyra 把同一个 `ClampAttribute` 挂在两个钩子上（`LyraHealthSet.cpp:189` 和 `:196`）。**推理链**：

1. `PreAttributeChange` 拦的是 `SetCurrentValue`（`AttributeSet.cpp:100-101`），**只 clamp CurrentValue**
2. BaseValue 走完全另一条路：`SetAttributeBaseValue`（`GameplayEffect.cpp:3705`）→ `:3720` `PreAttributeBaseChange` → `:3732` `SetBaseValue`，**根本不经过 `PreAttributeChange`**
3. **只写前者的后果（"负血债"）**：Instant GE 打 `-9999` → BaseValue 变 `-9899` 真实存在 → CurrentValue 被 clamp 到 0（UI 看起来正常）→ 之后吃 `+100` → BaseValue 变 `-9799`，CurrentValue 还是 0 → **加血无效**

### 你的答法

> 这个坑我踩得很实。辐射值最初只在 `PreAttributeChange` 里 clamp 到 [0,1000]，测试发现玩家在高辐射区待久后吃满抗辐射药，辐射值卡在 1000 掉不下来。debug 到 `FGameplayAttributeData` 才发现 BaseValue 已经 3000+ 了——Periodic 辐射 GE 每 tick execute 直接怼 BaseValue，`PreAttributeChange` 完全没拦住。改成和 Lyra 一样双写就好了。部位健康也是同样处理。

**🟢 一个"我读过源码"的细节**：`AttributeSet.h:222` 注释说 `PreAttributeBaseChange` 只在"有 Aggregator 时"调用，**但这是错的**。看 `GameplayEffect.cpp:3720`，它在检查 `AttributeAggregatorMap.Find`（`:3741`）之前就无条件调了。主动指出注释和实现不一致很加分。

---

## 🔴 Q3-3 MMC vs ExecCalc

**一句话**：**MMC 回答"这个 Modifier 的数值是多少"（返回 float）；ExecCalc 回答"这次结算要改哪些属性各改多少"（输出一组 mod）**。

| | MMC | ExecCalc |
|---|---|---|
| 虚函数 | `CalculateBaseMagnitude` → float，**const** | `Execute(params, OUT output)` |
| 能改几个属性 | 1 个 | 任意多个 |
| **适用 DurationPolicy** | **全部** | **只有 Instant 和 Periodic** |
| 真乘法叠加 | ❌ 受 Bias 限制 | ✅ 普通 C++ 连乘 |
| 外部依赖动态重算 | ✅ | ❌ |
| GE 资产后处理系数 | ✅ Coefficient / Curve | ❌ |
| 触发条件 GE | ❌ | ✅ |

**MMC 的后处理公式**（`GameplayEffect.cpp:1044`）：
$$\text{Final} = \text{Coefficient} \times (\text{MMC结果} + \text{PreAdd}) + \text{PostAdd}$$
三个系数都是 `FScalableFloat`，能在 GE 资产里配 + 挂 CurveTable 按等级缩放。**逻辑在 C++、数值给策划**，这是 MMC 的一大优势。

### 你的答法

> 我两个都用了，分工是刻意的：
>
> **ExecCalc 用于一次性辐射结算**。捕获 Target 的防护值、Source 的辐射源强度，都设 `bSnapshot = false`（穿脱防护服要立刻生效）。算的是 `辐射源强度 × 距离衰减 × (1-防护率) × 天气系数`——**这是真连乘，Modifier 做不到**。然后一次输出多条 mod。还用了 `ShouldTriggerConditionalGameplayEffects`，单次辐射超临界值时触发"急性辐射病"debuff。
>
> **MMC 用于持续状态的动态数值**。天气辐射的 Infinite GE 上挂 MMC 算累积速率（酸雨 ×2、晴天 ×1、室内 ×0.1）。这里必须用 MMC：**Infinite GE 根本不跑 Executions**——我踩过这个坑，配了 ExecCalc 一直不生效，跟到 `GameplayEffect.cpp:4225` 那个 `if (Period <= NO_PERIOD)` 才明白。

> ⚠️ **`GetExternalModifierDependencyMulticast`（MMC 的外部依赖自动重算）如果你实际没用过，别提**。它是冷门 API，被追问"返回的 delegate 是什么类型、注册在哪"（答案：`GameplayEffect.cpp:4643`）答不上来更糟。诚实版："天气变化时我是手动移除重挂 GE 的，后来才知道有外部依赖机制。"

**追问：`bSnapshot` 是什么？**
> `true` = Spec 创建时拍快照，之后源属性怎么变都不影响（Lyra 的 BaseDamage 是 true——子弹出膛时攻击力就定了）。`false` = 只存 Aggregator 引用，每次求值实时读（适合光环）。

---

## 🟠 Q3-4 Meta Attribute：为什么要 `Damage` 中间属性

**五个理由，按重要性**：

1. **结算逻辑统一收口** —— 所有伤害来源只往 `Damage` 上 Add，`PostGameplayEffectExecute` 成为唯一"伤害落地"点
2. **Modifier 阶段和 Execute 阶段能力不同** —— Duration Modifier 只能四则运算，"伤害 = 基础 × 距离衰减 × 材质衰减 - 护甲"只能在 ExecCalc 里写
3. **🔴 Health 可以被锁成只读** —— `meta = (HideFromModifiers)`（`LyraHealthSet.h:72`）让**策划在 GE 资产的 Modifier 下拉框里根本选不到 Health**。把约定用工具链强制执行
4. BaseValue 语义正确（Health 是状态量要存档，Damage 是事件量）
5. **不用复制** —— `LyraHealthSet.cpp:30-36` 只复制了 Health 和 MaxHealth

**转换代码模板**（`LyraHealthSet.cpp:148-149`）：
```cpp
SetHealth(FMath::Clamp(GetHealth() - GetDamage(), MinimumHealth, GetMaxHealth()));
SetDamage(0.0f);          // ← 立即清零，这是 Meta Attribute 的标志
```

### 你的答法

> 辐射结算就是这个模式。定义 `IncomingRadiation` 中间属性，所有辐射源（天气、区域 Volume、污染食物）只往它加值，结算写在 `PostGameplayEffectExecute`：`IncomingRadiation × (1-服装防护) × (1-药物抗性) → 累加到 RadiationLevel`，然后清零。
>
> `RadiationLevel` 我也标了 `HideFromModifiers`，策划配 DataTable 时只能配 `IncomingRadiation`，不会有人手滑直接改辐射值。症状阈值判定也在同一个函数里，能拿到 `EffectSpec` 判断辐射来源挂不同的 Cue。潮湿/感冒/过热复用了同一套模板。

**🟢 追问：Meta Attribute 能被客户端预测吗？**
> 不能。`GameplayPrediction.h:224-230` 有专门一段。因为转换在 `PostGameplayEffectExecute`，而预测会把 Instant GE 强行当 Infinite 处理（`AbilitySystemComponent.cpp:861-862`），Infinite 不走 execute 路径，钩子永不触发。**这也是 Lyra 的 ExecCalc 整个函数体被 `#if WITH_SERVER_CODE` 包起来的原因**（`LyraDamageExecution.cpp:37`）。

**追问：为什么 Damage 和 Healing 要分两个属性？**
> ① Multiply 语义会崩（`×1.5` 对混正负的属性，一个"易伤"debuff 会同时变成"强化治疗"）② 免疫要分开配 ③ Tag 和 Cue 要分开。

---

## 🟠 Q3-5 三种 DurationPolicy 的本质区别

**分叉就在一个 if**（`AbilitySystemComponent.cpp:875` / `:949`）：

```cpp
875:  if (DurationPolicy != Instant || bTreatAsInfiniteDuration)
877:      ApplyGameplayEffectSpec(...)      // 进容器，注册 Aggregator Mod，改 CurrentValue
949:  else if (DurationPolicy == Instant)
952:      ExecuteGameplayEffect(...)        // 改 BaseValue，用完即焚
```

`:951` 注释：`it never gets added to ActiveGameplayEffects`

**🔴 Periodic GE 是"披着 Duration 外衣的 Instant"** —— `:4225` 的 `if (Period <= NO_PERIOD)` 是分水岭。**有 Period 的 GE 不注册任何 Aggregator Mod**，而是起定时器（`:4269`），每次到期走 `ExecuteActiveEffectsFrom`（`:4388`）——**和 Instant 完全相同的路径，改 BaseValue，触发 Pre/PostGameplayEffectExecute**。

### 你的答法

> 三种我都按语义选过：
> - **辐射累积** = Infinite/HasDuration + `Period=1`。选 Periodic 而不是 Duration Modifier，因为我需要每秒触发 `PostGameplayEffectExecute` 跑防护率结算
> - **抗辐射药** = HasDuration + Multiply 改累积速率。吃两颗自然叠加，到期各自撤销，完全不用管账
> - **服装防护** = Infinite + Add。穿脱就是挂/摘 GE
> - **辐射注射器**（瞬间降 200）= Instant 改 BaseValue

**🔴 追问：想做"5 秒持续掉血"，用 Duration GE + Modifier 改 Health 行不行？**
> 不行，两层错。① 语义错：那是"临时降低血量"，5 秒后自动恢复 ② `Health` 标了 `HideFromModifiers`，编辑器里选不到。正确做法：`HasDuration` + `Duration=5` + `Period=1`，Modifier 改 `Damage`。

---

## 🟠 Q3-6 `HasTag` vs `HasTagExact`

**两个函数的真实代码**（`GameplayTagContainer.h:305-330`）：

```cpp
HasTag:      return GameplayTags.Contains(T) || ParentTags.Contains(T);
HasTagExact: return GameplayTags.Contains(T);
```

**差别就是多查一个数组，没有任何字符串操作。** 层级匹配靠**插入时预展开的父列表**（`.cpp:707` 的 `ExtractParentTags`），不是运行时 split。

`AddTag(State.Debuff.Radiation.Severe)` 后：
```
GameplayTags = { State.Debuff.Radiation.Severe }
ParentTags   = { State.Debuff.Radiation, State.Debuff, State }
```

**GAS 把成本从"每次查询"前移到了"每次插入"。** 代价是 `RemoveTag` 必须**从头重建整个父表**（`.cpp:760` 注释解释：`A.B` 和 `A.C` 都贡献了父 `A`）。

### 你的答法

> 层级计数让我不用写状态机。症状 Tag 设计成 `Status.Radiation.Weak/.Tired/.Nausea`，行走速度的 GE 只配一条 `ActivationRequiredTags = Status.Radiation` 就能命中所有症状等级。
>
> 还有个坑：我用 `RegisterGameplayTagEvent` 触发症状音效，一开始用 `AnyCountChange`，玩家从辐射区A走到区B（两 Volume 短暂重叠）时音效重复播——计数 1→2→1 触发了两次。换成 `NewOrRemoved` 就对了，因为 `SignificantChange = (OldCount == 0 || NewTagCount == 0)`（`GameplayEffectTypes.cpp:579`）只在 0↔非0 时为真。

---

## 🟠 Q3-7 InstancingPolicy 三选一

**🟢 引擎默认是 `InstancedPerExecution`**（`GameplayAbility.cpp:84`）—— 冷知识，大多数教程不讲。

| | NonInstanced | InstancedPerActor | InstancedPerExecution |
|---|---|---|---|
| 成员变量 | **绝对不能有**（所有 Actor 共享 CDO） | ✅ 跨激活保留 | ✅ 单次激活内 |
| AbilityTask | ❌ 不安全 | ✅ | ✅ |
| 网络复制 | 只能 LocalOnly | ✅ | ❌ 非法（`:1886` 报 error） |
| 结束时 | 无事 | 实例复用 | `MarkAsGarbage()` |
| 什么时候用 | 纯无状态 + 数量极大 | **绝大多数情况** | 需要多个并发实例各自独立状态 |

**`NonInstanced` 的机制根源**：`InternalTryActivateAbility:1723-1724` 让 `AbilitySource` 落到 CDO 上，`CanActivateAbility` 和 `ActivateAbility` 全在 CDO 上跑。

### 你的答法（这个 bug 经历有说服力）

> "辐射伤害脉冲"（区域辐射源周期性影响范围内玩家）我最初用 `NonInstanced` 想省内存，地图上有几十个辐射源。后来改成 `InstancedPerActor`——因为我需要在实例里缓存"上一帧受影响的玩家列表"做进出区域的 Cue 切换，`NonInstanced` 下这个成员变量被所有辐射源共享，完全错乱。这个 bug 让我理解了 `GetPrimaryInstance()` 返回 nullptr 意味着什么。

---

## 🟢 Q3-8 版本差异（主动提 = 加分）

引擎是 **5.4.4**。`ActivationOwnedTags` / `ActivationBlockedTags` / `ActivationRequiredTags` 在 5.4 里还是裸 `FGameplayTagContainer`（`GameplayAbility.h:749/753/757`），**5.5+ 重构进了 `FGameplayTagRequirements`，`AbilityTags` 改名成 `GetAssetTags()`**。

如果面试官用 5.5+，主动说"我看的是 5.4，5.5 之后这块重构成 `FGameplayTagRequirements` 了"。

**另一个冷知识**（`GameplayAbility.cpp:340` 的检查顺序）：**冷却和消耗检查在 Tag 检查之前**（`:393` CheckCooldown → `:403` CheckCost → `:413` DoesAbilitySatisfyTagRequirements）。

---

## 🟢 一个建议去用的引擎设施

`UGameplayTagReponseTable`（`GA/Public/GameplayTagResponseTable.h:60`）—— DataAsset，可配「`Status.Radiation` 每 1 层计数 → 挂 1 级症状 GE」，自动注册 tag 事件、自动增减 GE，支持正负 Tag 抵消和软上限（`SoftCountCap`，`:35`）。

**你的症状联动系统正是它的设计目标场景**。面试时可说"后来发现引擎有这个，如果重做会直接用"——展示持续学习。

---

# 第 4 章 · 角色 3C 与动画

> 本章结论不是背文档得来的：直接在 `ABP_Player_3C.uasset` 二进制里 grep 函数名字符串核对过真实用到了哪几个节点（Blueprint 图不进 Git diff，没法靠 commit log 看，只能扫资产）。**这比"我用了 AnimationLocomotionLibrary"这种泛泛的话更能扛住追问。**

## 🔴 Q4-1 Distance Matching 到底用了哪几个函数？（简历写"重建 Locomotion 架构"，必须能拆开讲）

**先说实测结论**（`grep -c <函数名> ABP_Player_3C.uasset`，命中次数=蓝图图里的节点引用数）：

| 函数 | 命中 | 用了没 |
|---|---|---|
| `AdvanceTimeByDistanceMatching` | 3 | ✅ |
| `PredictGroundMovementStopLocation` | 2 | ✅ |
| `DistanceMatchToTarget` | 2 | ✅ |
| `SetPlayrateToMatchSpeed` | 1 | ✅ |
| `PredictGroundMovementPivotLocation` | 0 | ❌ **没用** |
| `UDistanceCurveModifier`（编辑器工具） | 0 | ❌ 没查到直接引用 |

**⚠️ 诚实的边界**：只做了「停」（Stop）这条链路的 Distance Matching，没做「转向」（Pivot）。面试官如果问"急停和变向都做了距离匹配吗"，答案是**只有急停**，别顺嘴说全做了。

### 四个函数各自解决什么问题（源码：`AnimDistanceMatchingLibrary.h` / `AnimCharacterMovementLibrary.h`）

1. **`PredictGroundMovementStopLocation(Velocity, ...BrakingFriction, GroundFriction, BrakingDecelerationWalking)`**
   纯数学预测，**不摸任何 UObject**，用 `CharacterMovementComponent` 的刹车摩擦/地面摩擦/制动减速度几个标量，算出角色**当前速度下还要滑多远才能停下**，返回一个局部空间向量，长度就是"距停止点的距离"。

2. **`DistanceMatchToTarget(SequenceEvaluator, DistanceToTarget, DistanceCurveName)`**
   拿上面算出的"还要走多远"，去动画自带的**距离曲线**（时间→已行进距离的映射，由 `UDistanceCurveModifier` 在导入时预烤进动画）里反查，**直接把播放头跳到"曲线上还剩这么多距离"对应的时间点**。本质是**用距离代替时间做索引**，消除了"停止动作"和"角色实际减速曲线"不匹配导致的脚滑。

3. **`AdvanceTimeByDistanceMatching(UpdateContext, SequenceEvaluator, DistanceTraveled, DistanceCurveName, PlayRateClamp)`**
   和上面反过来：**已经走了多远** → 推进播放头到曲线对应位置，效果等价于"用行进距离而不是 DeltaTime 去推进动画"，常用在起步（Start）这类"动画和实际移动速度不完全同步"的过渡动作上。

4. **`SetPlayrateToMatchSpeed(SequencePlayer, SpeedToMatch, PlayRateClamp)`**
   给循环动作（走/跑/冲刺 Loop）用的，**假设动画匀速**，直接用 `播放速率 = 当前速度 / 动画作者速度` 去改 Play Rate，比距离匹配轻量很多——**循环动作不需要距离匹配，因为它本来就该一直循环，不存在"停在哪一帧"的问题**。

### 你的答法（背这段）

> 用的是引擎自带的 `AnimationLocomotionLibrary` 插件，但只覆盖了"停"这条链路，没做转向。具体是：`PredictGroundMovementStopLocation` 用 CMC 的刹车/摩擦参数（走 Property Access 绑定，因为这几个函数标了 `BlueprintThreadSafe`，不能直接访问 Actor）算出还要滑多远，再用 `DistanceMatchToTarget` 拿这个距离去停止动画的距离曲线里反查播放时间，把脚步和实际减速曲线对齐，消除了原来固定播放停止动画导致的脚滑。走/跑循环动作没用距离匹配，用 `SetPlayrateToMatchSpeed` 按速度比调 Play Rate 就够了，因为循环动作没有"该停在哪一帧"的问题。
>
> 转向（Pivot）没接距离匹配，当时是靠加大转向 Blend Space 的样本密度 + Inertialization 过渡糊过去的，效果没有距离匹配精确，这是能补的点。

### 追问预案

**Q：距离曲线是怎么来的？**
> `UDistanceCurveModifier` 是个 Anim Modifier，导入/重新保存动画时自动跑一遍，把根骨骼每帧的**已行进距离**烤成一条曲线存进动画资产。跑向"停止"的动画从倒数第一帧往前推距离是负的、往后是 0，这样 `DistanceMatchToTarget` 才能拿"剩余距离"反查到正确的帧。

**Q：为什么这些函数都标 `BlueprintThreadSafe`？跟你有什么关系？**
> 见 Q4-2——因为它们要能在动画图的 Worker Thread 更新阶段被调用，所以不能直接摸 GameThread 才安全的 UObject，只能吃纯数值参数，靠 Property Access 在 GameThread 侧先把值拷出来再传进图里。

---

## 🟠 Q4-2 AnimInstanceProxy 与多线程动画更新（Distance Matching 为什么必须设计成"纯函数"）

**一句话**：`NativeUpdateAnimation` 在 **Game Thread** 跑，只管"收集数据"；真正的图求值 `NativeThreadSafeUpdateAnimation` 可能在 **Worker Thread** 跑，所以**图里能调的函数必须不碰 GameThread 专属数据**——这正是 Q4-1 那几个 Distance Matching 函数全部只吃标量/向量参数、不吃 `ACharacter*` 的原因。

**调用链**（`AnimInstance.h:1304-1312` 注释 + 实测调用点）：

```
UAnimInstance::UpdateAnimation()          — AnimInstance.cpp:479，GameThread
    → NativeUpdateAnimation()             — :596，GameThread。"建议只收集数据"
    ...
FAnimInstanceProxy 的图更新阶段（并行任务里）
    → NativeThreadSafeUpdateAnimation()   — AnimInstanceProxy.cpp:1299，可能是 Worker Thread
```

引擎注释原话（`AnimInstance.h:1307-1308`）："It is usually a good idea to simply gather data in this step and for the bulk of the work to be done in `NativeThreadSafeUpdateAnimation`"——**GT 阶段只做"抄近道能拿到的数据"，重活丢给可并行的阶段**。

**AnimInstanceProxy 存在的意义**：`UAnimInstance` 本身是 UObject，GC/反射都绑在 GameThread 语义上；把每帧要用的运行时数据（骨骼变换、图的求值上下文）拷进一个不是 UObject 的 `FAnimInstanceProxy`，worker thread 只碰 Proxy 副本，**GameThread 侧的 `UAnimInstance` 随时可能被别的系统改写也不会和求值线程打架**——这是"数据隔离"而不是严格意义上的双缓冲，但效果类似：读/写分处两侧，互不锁。

**这就是为什么 `BlueprintThreadSafe` 是编译期强制的**：Animation Blueprint 编译时会检查图里每个函数调用，摸了非线程安全数据（比如直接 `GetOwner()`）就编译报错，逼你用 Property Access 在安全的时机把值抄出来再喂给图。Distance Matching 那组函数全部设计成"只吃值、不吃引用类型的 GameThread 对象"，就是为了能被扔进这条并行路径。

### 你的答法

> 项目开了 `bUseMultiThreadedAnimationUpdate`，所以我写自定义动画逻辑时会注意：真正每帧要算的东西尽量放蓝图图里用线程安全节点做，`NativeUpdateAnimation` 只做"从 Character 上抄值"这类必须在 GameThread 做的事。踩过一次坑：一开始想在图里直接查询战斗组件的状态判断要不要触发某个混合，编译直接报"not thread safe"，才去查 `AnimInstanceProxy` 这套双阶段更新，改成在 GameThread 阶段把状态量抄成图里能读的一个 bool/float，图里只做纯计算。

**追问：为什么不干脆全部放 GameThread 算？**
> 多线程动画更新的收益就是把骨骼求值这块摊到 worker thread 并行，角色越多、骨骼越复杂收益越明显；全放 GameThread 等于放弃这部分并行度，AI 数量一多 GameThread 单帧时间会被动画图直接顶满。

---

## 🟢 Q4-3 Inertialization：确认用了，解决什么问题

**先说实测**：`ABP_Player_3C.uasset` 里能 grep 到 `AnimNode_Inertialization` 引用（2 处），说明状态机过渡不是纯 Blend，接了 Inertialization 节点/请求。

**核心数学**（`AnimNode_Inertialization.cpp:107` `CalcInertialFloat`，注释原话翻译）：

> 用旧姿势与新姿势的差值 `x0`（位置差）和差值的变化速度 `v0`，构造一条**五次多项式曲线**，边界条件是：在混合结束时间 `t1`，曲线值、一阶导、二阶导**全部收敛到 0**。

**和普通 Blend 的本质区别**：
- **Blend** 需要"旧姿势"和"新姿势"两条都存在，按权重插值——如果旧姿势本身就是突变来的（比如上一次过渡还没走完又被打断），插值出来的还是不连续
- **Inertialization** 不需要旧姿势，只需要**当前的位置差和速度差**这两个数，用曲线把这个差值"追平到 0"，天然支持连续打断（打断了再打断，新的 `CalcInertialFloat` 直接拿当前偏差重新算一条新曲线），这是它取代 Blend 成为 UE5 状态机默认过渡方式的原因

### 你的答法

> 巡逻和战斗状态频繁切换，纯 Blend 在"过渡还没播完又要再切一次"时会看到明显的二次抖动，因为 Blend 是按固定权重曲线走的，不管当前实际差值是多少。换成 Inertialization 后，无论什么时候打断，它都是拿"此刻的姿势差和差值变化速度"重新算一条收敛曲线，所以能连续打断也不会跳变，这也是我们没有额外做 Pivot 的距离匹配、但转向手感还能接受的原因——Inertialization 兜了底。

---

# 附录 A · 需要你补的真实数据

这几处我不能替你编，但它们决定答得像"做过"还是"看过文章"：

| # | 需要的数据 | 用在哪 |
|---|---|---|
| 1 | 每帧销毁上限 N 是多少？怎么定的？ | Q2-2 |
| 2 | 优化前后对比（同屏怪物上限 / GameThread 帧耗时 / 帧率） | Q2-2、简历 |
| 3 | 埋的 7 条 Counter 具体是哪几条？ | Q2-5 |
| 4 | 休眠半径、滞回比例、回收延迟的实际数值 | 简历追问 |

**如果某个数字当时是拍的**，就诚实说"当时是拍的值，事后用 Insights 验证了效果"——比编推导过程安全得多。

---

# 附录 B · 面试当天的三个提醒

1. **被问到没做过的（网络同步 / 渲染 / Shader）** —— 直接说没做过，然后讲你知道的机制。硬吹被追问细节是致命的。
2. **主动说自我修正**（`GetDataView` 省不掉、BT 不是每帧从根 DFS、Task 可能过度拆分）—— 这些比答对题目更能证明你真读过源码。
3. **口头讲精确参数是加分，写在简历上是减分**。面试时说出「0.95 滞回、1.75 倍回收半径、30 秒最短休眠、每帧最多销毁 4 个」，证明你真调过参。

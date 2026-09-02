---
type: reference
area: "[[个人成长]]"
created: 2026-09-02
tags: [面经, 面试, UE, UnrealEngine, 游戏客户端, C++, GAS, 行为树]
---
## UE 游戏客户端面经高频题汇总
> 从牛客、GitHub、CSDN、博客园等公开面经中提取的 UE 游戏客户端开发高频面试题。覆盖数据结构与算法、网络、C++ 与现代 C++、UE C++、GAS、3C、行为树 / StateTree。配套零散知识点收集见 [[UE查缺补漏]]、[[C++查缺补漏]]、[[算法查缺补漏]]。

### 信源与可信度

| 信源 | 类型 | 价值 |
|---|---|---|
| [Game-Client-Interview-2025](https://github.com/ShawnHu0815/Game-Client-Interview-2025) | 88 场面试（37 实习 + 51 秋招）录音复盘，**带频次统计** | ★★★★★ |
| [UE游戏客户端24秋招总结+面经](https://www.nowcoder.com/discuss/551028311208620032) | 牛客，英雄游戏/网易互娱/雷火/腾讯光子/吉比特/数字天空逐轮题目 | ★★★★★ |
| [Genius-pig/UEInterview](https://github.com/Genius-pig/UEInterview) | 55 题 UE 专项题库 | ★★★★ |
| [【UE4】UE4笔试面试题](https://www.cnblogs.com/caedmom/p/9640346.html) | 100 题 UE 笔试题（十部分） | ★★★★ |
| [腾讯光子游戏引擎开发方向面经](https://www.nowcoder.com/discuss/613002354509570048) | 渲染 / 图形学侧重 | ★★★★ |
| [游戏客户端开发日常实习面经](https://www.nowcoder.com/discuss/632369695965929472) | 字节绿洲 / 腾讯魔方 | ★★★ |
| [腾讯2020 unreal虚幻面试题](https://blog.csdn.net/qq_17347313/article/details/107877912) | 偏工程 / 工具链 | ★★★ |

采集局限需明确记录：检索时仅有网页抓取能力、无搜索 API，DuckDuckGo 全线 CAPTCHA、Brave 两轮后 429、知乎 403、Bing 返回缓存串页。**StateTree 未找到任何真实面经样本**，详见第八节。

### 一、频次统计（唯一有真实计数的数据）

来自 88 场面试的穷举统计。原作者提示：出现频次超过 10 的问题不仅要准备答案，还要深入理解，避免被追问时卡壳。

#### 第一梯队（15~14 次）
- 虚函数实现原理（vptr / vtable）— 15
- 对象池 Object Pool — 15
- 智能指针（shared_ptr / unique_ptr）— 14

#### 第二梯队（12~9 次）
- Lua 元表 & 元方法 — 12
- Lua OOP 实现原理 — 12
- 哈希表实现及冲突 — 11
- 红黑树 — 10
- Unity 协程原理 — 10
- **UE 垃圾回收（GC）机制 — 9**
- 内存对齐 — 9

#### 第三梯队（8~7 次）
- 右值引用与移动语义 — 8
- 协程 vs 线程 — 8
- 排序算法 — 8
- 生命周期函数流程 — 8
- C++ 多态机制 — 7
- Lua Table 底层 — 7
- C# GC — 7
- AssetBundle — 7
- **UE 反射机制 — 7**
- UnLua 插件原理 — 7

#### 第四梯队（6~4 次）
- 内存分区 — 6｜单例 / 观察者 — 6｜FSM 有限状态机 — 6｜DrawCall 优化 — 6
- C++ 类内存布局 — 5｜Lua 语法闭包 — 5｜编译链接流程 — 5｜锁机制 — 5｜四叉树 — 5｜A* — 5｜UGUI 适配 — 5
- 状态同步 vs 帧同步 — 4｜堆 vs 栈 — 4｜堆结构 — 4｜点在三角形内 — 4｜点乘 vs 叉乘 — 4｜**GAS — 4**

#### 非技术项反而最高频
- 实习模块细节深度拆解 — **43**
- 遇到的问题及解决方案 — **26**
- 想做客户端的原因 — 12
- 为什么选择游戏行业 — 11
- Offer 选择因素 — 9

这是个重要信号：**简历项目的深挖远超任何单个八股题**。

### 二、C++ 与现代 C++ 新特性

#### 多态与虚函数（最高频，几乎必问 + 必追问）
- 多态、重写、重载的区别；纯虚函数；`override` / `final` 关键字
- 虚函数怎么实现？**子类和父类是否共用一张虚函数表**
- C++ 内存区域划分，**虚表应该放在哪个区**
- 空类 `sizeof`？有虚函数后？**多继承两个带虚函数的父类**？
- 菱形继承的问题与解决方案
- 继承类调用虚函数的完整流程
- **构造函数内可以调用虚函数吗？析构函数呢？**
- 虚函数与纯虚函数的区别

#### 智能指针（14 次，第一梯队）
- 常用智能指针有哪些；`weak_ptr` 的作用；`shared_ptr` 引用计数机制
- **手写实现 `shared_ptr`**（吉比特、腾讯光子都考过）
- UE 侧：UE 中的智能指针有哪些（`TSharedPtr` / `TWeakPtr` / `TUniquePtr`）
- **为什么需要 `TWeakPtr`**
- UObject 该用什么指针（`TObjectPtr` / `UPROPERTY` 强引用 vs `TWeakObjectPtr`）

#### 内存
- 内存对齐：规则、`struct` 内存对齐、**内存对齐为什么快**
- 堆内存 vs 栈内存区别；**为什么栈的访问效率比堆高**；堆内存分配慢有什么优化方法
- 内存碎片为何产生
- 深拷贝与浅拷贝；浅拷贝会带来什么问题
- C++ 内存管理；C 语言内存分配
- 大端小端：概念、如何判断、**手写判断代码**

#### 现代 C++ 特性
- 左值与右值怎么理解、区别；**右值引用与移动语义**（8 次）
- 类型推断两个关键字（`auto` / `decltype`）怎么用？**举一个只能用 `decltype` 才能解决的场景**
- `nullptr` 和 `NULL` 的区别，前者的优点
- `inline` 内联函数的作用
- `const` 的各种用法
- `static` 的作用；静态全局变量存在哪个区；**静态局部变量若是类类型，什么时候初始化**；`static` 和 `extern` 的区别
- 单例模式实现、如何确保唯一性（线程安全）
- STL：`vector` 扩容机制及性能问题、`map` 与 `unordered_map` 区别、`set` / `map` 有序无序、**四个容器增删改查的复杂度**
- 手写 `vector`（重点扩容）、手写 `unordered_map`
- 指针为什么危险
- C 语言 / C++ 编译链接流程

### 三、数据结构与算法

#### 概念题
- 哈希表实现 + **哈希冲突解决方法**（11 次）
- 红黑树（10 次）
- 四叉树空间分割（5 次）；**kd-tree 及其更新实现**（网易互娱深挖）
- 堆：是什么、用什么存、怎么建堆、怎么插入、怎么删除
- BVH：介绍、**广度优先遍历 BVH**、BVH vs 八叉树优劣、**同场景同粒度哪个树更深**
- 排序算法（快排 / 归并 / 堆排）、代码复杂度分析
- A* 算法（5 次）
- 点乘 vs 叉乘；点在三角形内判定；判断两线段是否相交
- 并查集（数字天空：**并查集在 GC 中的应用**）

#### 手撕题（实际考过的）
- 三数之和｜用栈实现前序遍历（非递归）｜堆排序｜链表排序
- 链表判环 + **证明算法可行性**｜数组三等分点｜最大区间和
- 第 k 大的数｜最长上升子序列｜删除最大的 N 个数
- n 个多边形放入边长 x 的矩形，求 x 最小值
- **如何在平面三角形内等概率随机一点**

#### 智力题（游戏公司偏爱）
- 15 匹马 5 个赛道选前 5 名
- 100 层楼 2 个鸡蛋测临界位置
- 两个沙漏得到连续 9 分钟

### 四、网络相关

#### 计算机网络基础
- **TCP 和 UDP 区别**；报文段各字段；**TCP 头部比 UDP 多多少字节**
- 三次握手；拥塞控制完整流程；滑动窗口的用途
- **TCP 分包 / 粘包与解包**
- 设计一个文件传输系统（选 TCP 还是 UDP 并说明权衡）
- **状态同步 vs 帧同步**（4 次）
- 进程和线程的区别；多线程如何保证同步；锁机制（死锁 / 悲观锁 / 乐观锁）；协程 vs 线程
- UE 服务器默认监听端口是哪个？用 UDP 还是 TCP？

#### UE 网络同步（被问得非常细，是 UE 客户端岗的分水岭）
- UE 网络同步整体机制、**角色权限（Authority / Role / RemoteRole）**、属性同步、RPC
- UE 中的 RPC 事件有哪些（Server / Client / NetMulticast + Reliable / Unreliable）
- **Reliable 的意义，如何实现对应操作**
- 客户端能执行 RPC 的对象有哪些？**客户端对某 Actor 的 RPC 调用失败，可能原因是什么**
- **在 `BeginPlay` 之后调用 RPC，客户端却没执行到，可能原因**
- 如何设置 Actor 的同步间隔（`NetUpdateFrequency`）；如何更改 UE 默认的同步带宽
- 场景题：服务器生成 Actor 的属性同步流程
- **一帧内某属性多次变更，如何优化通信带宽**；一帧内只更新一次的数据结构该怎么设计
- 数据的序列化 / 反序列化
- C++ 中如何给组件或 Actor 设置同步
- `ProjectileComponent` 是否同步？若未同步如何处理
- **动画蓝图是否支持同步？若不支持有什么解决方案**
- 客户端未连接服务器前，有无与服务器通信的方案
- 如何基于 UE 网络接口实现一个网络层（如 Steam）
- 连接服务器的命令是什么、如何传参
- UE 服务器是否适用于 MMO？若不适应有什么方案
- 如何配置专用服务器（Dedicated Server）
- 子弹穿墙问题怎么解决

### 五、UE C++ 与引擎核心

#### 反射与 UObject（GC 9 次 / 反射 7 次，UE 侧绝对核心）
- **UE 垃圾回收机制**：怎么实现、如何避免 / 优化 GC 影响、底层细节（数字天空追问到并查集）
- **UE 反射系统**：是什么、如何与 C++ 交互、**UBT / UHT 如何实现反射**、扩展反射功能的应用场景
- `UFUNCTION` / `UPROPERTY` 等宏的作用；`*.generated.h` 是什么
- **UE Cast 的底层实现**
- UE C++ 语法与标准 C++ 的区别
- UE 的 Subsystem（引擎子系统）是什么、生命周期、如何创建自定义 Subsystem
- 容器：`TArray` / `TMap` 详解、何时使用、性能特性
- UE 中的字符串类型有哪些（`FString` / `FName` / `FText`）；各种字符编码如何转换
- UE 是否自动管理 `UStruct` 内存

#### 生命周期与游戏框架
- **Actor 生命周期**：`BeginPlay` / `Tick` / `EndPlay` 触发时机；`EndPlay` 在哪些时机会调用
- **GameMode 运行流程**：从 `InitGame` 到 `Logout`
- UE 游戏框架包含哪些内容（GameInstance / GameMode / GameState / PlayerController / PlayerState / Pawn / Character）
- `Tick` 中的帧时间是否可靠？不可靠怎么办
- **`Set Global Time Dilation` 具体做了什么**
- UE 中的 Delegates 有哪些（单播 / 多播 / 动态 / 事件）；如何实现一个多播事件

#### 工程与工具链
- UE 源码怎么获取；编译引擎耗时太长有什么解决方案
- 插件中的 `LoadingPhase` 是什么；为什么用插件而不放在蓝图里
- 团队项目如何处理 DDC；如何切换引擎版本
- 如何在 UE 中使用静态库 / 动态库；C++ 中要用 Windows 头文件怎么办
- 如何分析性能瓶颈；打包版本如何跟踪调试；打包资源加密方案
- 蓝图在版本控制里无法 diff，有什么解决方案
- Editor Utility Widgets 自定义工具面板
- 手动合批实现、如何判断合批成功

#### UI
- **Slate 还是 UMG？Slate 的性能问题，Slate 如何调试**
- UI 中的锚是干什么的；更新 UI 的方式有哪些；3D Widget 如何使用
- UI 层级管理与显示；UI 渲染的底层实现；UI 排行榜做法

#### 渲染与其他
- 渲染管线主要阶段；自定义渲染通道与后处理；UE 的 AA 算法有哪些
- Niagara vs UE4 Cascade 的优势、GPU 粒子通信；Lumen；Nanite
- UE5 Enhanced Input 增强输入系统
- 如何理解 UE 中的多线程
- UE 碰撞类型有哪些；**不使用物理引擎如何实现自定义多边形碰撞检测**
- SaveGame 系统 / 数据存取方法；UE 内置伤害接口是什么，有哪些类型
- Actor 中的输入事件无法触发，可能原因有哪些
- 对根组件设置 Scale 会有问题吗
- 如何把某 Actor 的组件替换为其派生组件

### 六、GAS（Gameplay Ability System）

需坦率标注：**GAS 在 88 场统计中仅出现 4 次**，属中低频、非通用考点，**主要看简历**——简历写了 GAS 会被深挖，没写通常不问。中文面经里 GAS 原题极少，以下按 GAS 架构本身整理准备方向，属**推断而非实证原题**。

- ASC（AbilitySystemComponent）挂在哪里？Character 上还是 PlayerState 上，各自适用场景与权衡（多人游戏放 PlayerState 便于跨重生保留）
- AttributeSet：属性定义、`ATTRIBUTE_ACCESSORS` 宏、BaseValue 与 CurrentValue 的区别
- `PreAttributeChange` / `PostGameplayEffectExecute` 各自的职责与调用时机
- GameplayEffect 三种时长类型：Instant / Duration / Infinite；Modifier 与 Execution（`GameplayEffectExecutionCalculation`）的区别
- GameplayTag 的层级设计与匹配；ActivationRequiredTags / BlockedTags
- GameplayAbility 的激活流程；`CommitAbility` 做了什么；Cost 与 Cooldown 如何用 GE 实现
- AbilityTask 的作用与生命周期（如 `WaitTargetData`、`PlayMontageAndWait`）
- **GAS 的网络模型**：`EGameplayEffectReplicationMode`（Full / Mixed / Minimal）如何选；Prediction（客户端预测）机制与 `FPredictionKey`
- GAS 的性能开销与优化策略
- GAS 与 GameplayMessageSubsystem / Lyra 中的实践，参见 [[Lyra工程拆解]]

### 七、3C（Character / Control / Camera）

同样需标注：**没有以「3C」为名的独立面经题组**，相关题目散落在角色移动与动画里。

#### 角色与控制
- `CharacterMovementComponent` 的网络同步模型（Client Prediction + Server Correction + Replay）
- 角色权限与移动模式（Walking / Falling / Flying / Swimming / Custom）
- 相机跟随、`SpringArmComponent`、相机与角色旋转的解耦设置
- **顿帧（Hit Stop）如何实现**（英雄游戏原题，与 `Global Time Dilation`、`CustomTimeDilation` 相关；注意面试官紧接着追问了 `Set Global Time Dilation` 具体做了什么）
- 四元数：四个数字分别是什么含义、如何插值、**SLerp / NLerp / Lerp 的区别**、四元数相对欧拉角的优点
- UE 中的变换、旋转与向量运算
- 输入：Enhanced Input、轴输入事件值为 0 时是否触发、玩家操作事件放 PlayerController 还是 Pawn

#### 动画（实际考得比「3C」这个词更多）
- AnimBP 动画状态机 vs Montage：各自适用场景、**哪个更适合做近战攻击**
- **如何实现上下肢分离的换弹动画（边跑边换弹）**——层级混合 Layered Blend Per Bone
- 如何创建根骨骼动画节点以便代码调用
- Montage 播完如何获取响应事件；如何获取动画的执行事件
- Montage 是什么
- 动画与声音、特效如何匹配同步

### 八、行为树 / StateTree

#### Behavior Tree（有大量实证原题）
- **AI 行为树的节点有哪些**（英雄游戏原题）
- Service、Task、Decorator 各自的功能；**敌人寻路到玩家跟前执行攻击，该选哪个节点实现**
- **Selector、Sequence、Parallel（SimpleParallel）的运作流程**
- **Service 的执行时机是什么时候**
- **Observer Aborts 的用途是什么**
- 如何实现自定义 AI 行为与决策树（自定义 Service / 自定义 Task）
- UE 的 AI 感知组件有哪些（AIPerception：Sight / Hearing / Damage）
- 在客户端能否获取到 AIController；如何销毁 AIController；如何给 AI 增加 PlayerState
- **对 Actor 调用 `AIMoveTo` 失败了，可能原因是什么**
- 导航网格与寻路组件各自的作用；如何让原本不支持寻路的 Actor 实现寻路
- 游戏中的 AI 技术有哪些；FSM 有限状态机（6 次）

#### StateTree：本次检索的明确空白
**未找到任何真实面经样本**——不是漏检，是确实没有。可能原因：StateTree 是 UE5 较新特性，尚未沉淀进校招题库。抓到的都是技术文档而非面经：
- [Epic 官方 StateTree 文档](https://dev.epicgames.com/documentation/zh-cn/unreal-engine/state-tree-in-unreal-engine)
- [SegmentFault：UE5 StateTree 源码剖析](https://segmentfault.com/a/1190000043713433)
- [CSDN：StateTree 框架拆解](https://blog.csdn.net/qiuzijian/article/details/132894247)
- [知乎：UE5 StateTree 介绍](https://zhuanlan.zhihu.com/p/558696301)

若要准备，核心对比点：StateTree = 行为树的 Selector + 状态机的 State / Transition。相比 BT 的优势在于扁平化、避免深层黑板耦合、Schema 约束、性能（无需每帧遍历整树）。

### 九、备考优先级建议

1. **虚函数 + 智能指针 + 内存对齐 / 分区**——三者合计出现 38 次，且必被追问到实现层。
2. **UE GC + 反射 + Cast 底层**——UE 侧的绝对核心，网易雷火 / 数字天空会一路挖到 UBT / UHT 和并查集。
3. **网络同步**——UE 客户端岗的分水岭。属性同步、RPC 失败排查、带宽优化场景题，是区分「会用」和「懂原理」的地方。
4. **把实习 / 项目讲透**——43 次 + 26 次，比任何八股都高。准备好每个模块的设计权衡与踩坑复盘。
5. GAS / StateTree 属于加分项而非必考项，按简历深度投入即可。

### 相关
- [[UE查缺补漏]] · [[C++查缺补漏]] · [[算法查缺补漏]]
- [[Lyra工程拆解]]

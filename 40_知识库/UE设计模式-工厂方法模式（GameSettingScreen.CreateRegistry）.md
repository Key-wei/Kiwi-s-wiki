---
area:
tags: [UE, 设计模式, FactoryMethod]
created: 2026-07-10
source: Lyra / Plugins/GameSettings + Source/LyraGame
aliases: [虚拟构造函数, Virtual Constructor]
---
# 跟着 Lyra 源码重学 GoF 设计模式（1）：工厂方法模式

> 前言：这篇文章是我用 Lyra 项目拆解 GoF 设计模式系列的第一篇。

我写这个系列的目的，不是重新复述教科书里的定义，也不是把 UML 类图再画一遍，而是希望把设计模式放回真实工程里观察：它到底解决了什么问题？为什么项目代码会长成这样？如果不用这个模式，代码会在哪里变得难维护？

Lyra 是一个很适合做这件事的样本。它不是为了讲设计模式而写的示例代码，而是一个真实的 UE 项目：有 UI、有设置系统、有 Gameplay、有插件分层，也有大量为了扩展性、生命周期和引擎机制而做出的工程取舍。正因为它不“教科书”，反而更适合帮助我们理解设计模式在实际项目里的样子。

这个系列会按 GoF 的三大类来拆：

- 创建型模式：关注对象如何被创建，以及创建流程如何和具体类型解耦；
- 结构型模式：关注类和对象如何组合成更大的结构；
- 行为型模式：关注对象之间如何协作、通信和分配职责。

本文属于第一类：**创建型模式**。我们从工厂方法模式开始，因为它在 UE 里非常常见，也很容易被误解成“把 `new` 或 `NewObject` 包一层函数”。但在真实工程里，它真正有价值的地方并不是隐藏创建语句，而是：**把稳定流程留在父类，把具体创建哪一种对象这个变化点交给子类**。

# 意图
工厂方法是一种创建型模式：它
的核心思想是： 
> 父类定义创建对象的流程，但把具体创建哪一种对象交给子类决定。

简单来说： 父类负责： - 什么时候创建； - 创建之后做什么； - 后续流程如何执行。 子类负责： - 到底创建哪个具体类型。 它解决的问题不是「怎么写 NewObject」，而是： > 当创建流程固定，但创建出来的对象类型可能变化时，如何避免父类和具体类型强绑定。

本文我们用 Lyra 的设置界面作为案例贯穿讲解。
![[Pasted image 20260710124454.png]]
# 问题
## 如果不用工厂会发生什么？
假设现在要做一个设置菜单。
里面有：
- 音量
- 鼠标灵敏度
- 是否开启 VSync
- 分辨率
- 全屏模式
![[Pasted image 20260710130514.png|697]]
![[Pasted image 20260710130540.png]]
最直接的做法就是在设置界面里写大量判断。设置界面一边遍历所有设置，一边判断：
> 如果这是布尔值，就创建一个复选框。
> 如果这是数字，就创建一个滑块。
> 如果这是枚举，就创建一个下拉框。
> 如果这是按钮，就创建一个按钮。

刚开始只有五种设置，看起来没什么问题。但是随着项目越来越大：
- HDR 设置
- 色盲模式
- 键位绑定
- 手柄震动
- 动态分辨率
这些新的设置类型都会不断出现。于是设置界面就会越来越臃肿，因为每增加一种设置类型，都要修改设置界面的代码。设置界面不仅负责"显示"，还负责"决定创建什么控件"。两个职责耦合在了一起。
# Lyra做了什么
Lyra 把这两个职责拆开了。
首先，它只负责描述：这里有一个设置。而不会描述：它应该长成什么样。
例如，一个音量设置对象：
它知道：
- 自己代表 Master Volume；
- 当前值是多少；
- 修改后应该如何应用到音频系统。
但是它不知道：
- 自己最终应该显示成 Slider；
- Slider 的样式是什么；
- UI 应该如何布局。
同样，一个"是否开启 VSync"也只知道我是一个布尔值它也不知道：我要画成一个复选框。这些 `UGameSetting` 对象本身并不是 UI 控件，而是一个**设置项的运行时描述对象**。
## 真正决定 UI 的是谁？
真正负责决定 UI 的，是后面的工厂。
当设置界面开始生成时，它会把每一个设置对象交给工厂。
工厂看到以后，会问一个问题：
> 这是什么类型的设置？
如果是布尔值，就返回一个复选框。
如果是数值，就返回一个滑块。
如果是枚举，就返回一个下拉框。
最后，设置界面只负责把这些已经创建好的控件按顺序摆出来。
# 结构
时序图：
![[Pasted image 20260710125409.png]]

首先：设置界面刚打开的时候，并不知道要显示哪些控件。
所以UGameSettingRegistry中返回了所有的UGameSetting:
├── Master Volume 
├── Music Volume 
├── Mouse Sensitivity 
├── Fullscreen
├── VSync
└── Resolution
接着遍历每一个Setting，调用CreateWidiget()给工厂处理，判断Setting的类型并返回对应的Widiget，接着创建子控件设置到SettingWidget上
# 代码实现（Lyra 源码）

这一段是本文真正要抓住的工厂方法落点：

> `UGameSettingScreen` 不直接知道自己要创建哪一种 `UGameSettingRegistry`，它只知道：我需要一个 Registry，然后我要把它接到设置面板、变更追踪和缓存流程里。

也就是说，父类掌握的是**稳定流程**，子类只填一个**变化点**。

## 1. 父类：把稳定流程收在自己手里

先看基类声明：

![[Pasted image 20260710131631.png]]```

这里最重要的是两个函数：

- `GetOrCreateRegistry()`：父类自己的流程函数。
- `CreateRegistry()`：留给子类重写的工厂方法。

注意：`CreateRegistry()` 返回的是 `UGameSettingRegistry*`，也就是产品基类，而不是 `ULyraGameSettingRegistry*`。这就是解耦点。父类只依赖抽象产品，不依赖 Lyra 的具体产品。

真正的流程在这里：
![[Pasted image 20260710131733.png]]

这段代码看起来很短，但它把四件容易漏的事情统一收住了：

1. 判断是否已经创建过。
2. 调用工厂方法创建 Registry。
3. 给 Registry 绑定设置变化事件。
4. 把 Registry 塞给 `Settings_Panel`，并缓存起来。

如果不用工厂方法，这四步就很容易散落到每一个具体设置界面里。每个界面都要自己写一遍：先创建、再绑定、再塞面板、再缓存。只要某个界面忘了绑定 `OnSettingChangedEvent`，设置改变后的 dirty 状态、Apply / Cancel 逻辑就可能出问题。

所以这里的关键不是“少写一行 `NewObject`”，而是：

> 父类把创建之后必须发生的流程固定下来，子类没有机会漏接线。

## 2. 子类：只回答“我要造哪一个”

Lyra 的具体设置界面只重写了 `CreateRegistry()`：

![[Pasted image 20260710131822.png]]
实现也很直接：
![[Pasted image 20260710131837.png]]

子类只做两件事：

1. 创建 Lyra 自己的 `ULyraGameSettingRegistry`。
2. 用当前 `LocalPlayer` 初始化它。

它不需要关心：

- 创建好的 Registry 要不要缓存；
- 要不要绑定 `OnSettingChangedEvent`；
- 要不要塞进 `Settings_Panel`；
- 后续 Apply / Cancel / DirtyState 怎么联动。

这些全部是父类流程。

这就是工厂方法在工程里的舒服之处：

> 子类越简单，父类流程越稳定，越不容易因为扩展而破坏已有行为。

## 3. 角色映射

把 Lyra 这段代码对应回工厂方法模式，可以这样看：

| 工厂方法角色 | Lyra 中的代码 | 说明 |
|---|---|---|
| Creator / 创建者基类 | `UGameSettingScreen` | 定义稳定流程 `GetOrCreateRegistry()` |
| Factory Method / 工厂方法 | `CreateRegistry()` | 留给子类决定创建哪种 Registry |
| ConcreteCreator / 具体创建者 | `ULyraSettingScreen` | 重写 `CreateRegistry()` |
| Product / 产品基类 | `UGameSettingRegistry` | 父类只依赖这个抽象类型 |
| ConcreteProduct / 具体产品 | `ULyraGameSettingRegistry` | Lyra 项目自己的设置注册表 |
| Client / 使用者 | `UGameSettingScreen::GetOrCreateRegistry()`、`Settings_Panel` | 拿到 Registry 后继续走通用流程 |

最容易误解的一点是：`ULyraSettingScreen` 本身既是一个 UI 页面，也是一个“具体创建者”。在真实项目里，模式角色经常不会单独拆成一个纯粹的 `Factory` 类，而是藏在某个业务基类的虚函数里。

这也是 UE 代码里很常见的形态：

> 不一定有一个叫 `Factory` 的类；只要“父类定义流程，子类重写创建步骤”，它就是工厂方法的落地。

## 4. 调用链完整走一遍

可以把这段代码想成下面这条链：

```text
设置界面需要 Registry
        │
        ▼
UGameSettingScreen::GetOrCreateRegistry()
        │
        ├─ 如果 Registry 已经存在：直接返回缓存
        │
        └─ 如果 Registry 不存在：
              │
              ▼
        调用虚函数 CreateRegistry()
              │
              ▼
        ULyraSettingScreen::CreateRegistry()
              │
              ├─ NewObject<ULyraGameSettingRegistry>()
              ├─ CastChecked<ULyraLocalPlayer>(GetOwningLocalPlayer())
              └─ NewRegistry->Initialize(LocalPlayer)
              │
              ▼
        返回 UGameSettingRegistry* 给父类
              │
              ▼
        父类继续统一流程：
              ├─ 绑定 OnSettingChangedEvent
              ├─ Settings_Panel->SetRegistry(NewRegistry)
              └─ Registry = NewRegistry
```

这里的分工非常清楚：

- “造什么”是子类的责任。
- “造完之后怎么接进系统”是父类的责任。

这也是本文标题里说的：把稳定流程和变化类型分离。

# 和教科书有什么不一样（UE 的落地差异）

教科书里的工厂方法通常长这样：

```cpp
class Creator
{
public:
    void Operation()
    {
        Product* P = CreateProduct();
        P->DoSomething();
    }

protected:
    virtual Product* CreateProduct() = 0;
};

class ConcreteCreator : public Creator
{
protected:
    virtual Product* CreateProduct() override
    {
        return new ConcreteProduct();
    }
};
```

Lyra 里的形状几乎一样，只是换成 UE 习语：
差异主要在三个地方。
## 1. 纯虚函数：UE 里常见 `PURE_VIRTUAL`

在普通 C++ 里，我们会写：

```cpp
virtual Product* CreateProduct() = 0;
```

但 Lyra 这里写的是：

```cpp
virtual UGameSettingRegistry* CreateRegistry() PURE_VIRTUAL(, return nullptr;);
```

`PURE_VIRTUAL` 的作用可以理解成：

- 语义上告诉你：这个函数应该由子类实现；
- 同时给链接器一个兜底函数体；
- 如果运行时真的调用到基类实现，会走 UE 的错误提示路径，并返回宏里给出的兜底值。

所以它既保留了“强制子类实现”的设计意图，又更符合 UE 的 UObject / 模块链接习惯。

## 2. 创建 UObject：不要用裸 `new`

Lyra 子类里没有写：

```cpp
auto* NewRegistry = new ULyraGameSettingRegistry(); // 不要这样
```

而是写：

```cpp
ULyraGameSettingRegistry* NewRegistry = NewObject<ULyraGameSettingRegistry>();
```

原因是 `ULyraGameSettingRegistry` 是 UObject 家族对象。UObject 的生命周期、反射、GC、Outer、序列化等机制都依赖 UE 自己的对象系统。用裸 `new` 会绕开这些机制。

如果这个产品是 UObject，那么工厂方法里通常应该用：

- `NewObject<T>()` 创建普通 UObject；
- `CreateWidget<T>()` 创建 UUserWidget；
- `SpawnActor<T>()` 创建 Actor；
- 或者由 Subsystem / AssetManager / Factory 类提供的专门创建接口。

也就是说，工厂方法解决的是“谁决定创建哪种产品”，而 UE 的创建 API 解决的是“这种产品应该按引擎规则怎么出生”。这两件事不要混在一起。

## 3. 缓存对象：用 `UPROPERTY` 挂住引用

基类里缓存 Registry 的字段是：

```cpp
// Plugins/GameSettings/Source/Public/Widgets/GameSettingScreen.h:79
UPROPERTY(Transient)
mutable TObjectPtr<UGameSettingRegistry> Registry;
```

这不是随便写的。

因为 Registry 是 UObject，如果父类创建完以后只存在一个普通裸指针引用，就要非常小心 GC 可见性。Lyra 用 `UPROPERTY(Transient)` + `TObjectPtr` 表达了两个意思：

- 这是 UObject 引用，应该被 UE 对象系统看见；
- 它只是运行时临时状态，不需要被保存成资产数据。

所以，在 UE 里写工厂方法时，不能只照搬 GoF 的类图，还要同时考虑 UObject 生命周期。

# 适用场景

工厂方法适合用在这种结构里：

> 上层流程稳定，但中间某一步要创建的具体类型会因为项目、平台、玩法、子类而变化。

放到 UE 项目里，常见场景有这些。

## 1. 父类有统一生命周期，子类只替换产品

比如 Lyra 的设置页：

- 打开设置页；
- 获取 Registry；
- 绑定变更事件；
- 塞进 Panel；
- 追踪 Apply / Cancel；
- 关闭时处理状态。

这些流程对所有设置页都一样，所以应该放父类。

但不同项目可能有不同 Registry：

- `ULyraGameSettingRegistry`；
- `UShooterGameSettingRegistry`；
- `UMobileGameSettingRegistry`；
- `UConsoleGameSettingRegistry`。

这时就很适合用工厂方法。

## 2. 创建之后必须统一接线

如果创建后还要做很多固定动作，工厂方法特别有价值。

Lyra 里创建 Registry 之后马上做了：

```cpp
NewRegistry->OnSettingChangedEvent.AddUObject(this, &ThisClass::HandleSettingChanged);
Settings_Panel->SetRegistry(NewRegistry);
Registry = NewRegistry;
```

这些接线如果分散到子类里，迟早有人漏掉。

因此，判断要不要用工厂方法，可以问自己一句：

> 创建完这个对象之后，有没有一串所有子类都必须遵守的标准流程？

如果有，父类就应该把这串流程收住，只把“创建哪一个”开放出去。

## 3. 框架代码要让项目代码扩展

`Plugins/GameSettings` 是插件层，`Source/LyraGame` 是项目层。

插件层不应该硬编码：

```cpp
NewObject<ULyraGameSettingRegistry>();
```

因为插件不应该知道 Lyra 项目里的具体类。

所以它只能说：

```cpp
UGameSettingRegistry* NewRegistry = this->CreateRegistry();
```

这就是插件 / 框架常用工厂方法的原因：

> 上游框架定义流程，下游项目填具体类型。

## 4. 不适合的情况

工厂方法也不是越多越好。

下面几种情况不一定适合：

- 只有一个具体类型，而且未来也不太会变；
- 创建逻辑只是简单 `NewObject`，创建后没有统一接线；
- 类型选择来自数据表、配置或资产，而不是来自子类差异；
- 产品族很多、而且要成套创建，这时可能更接近抽象工厂；
- 只是想把 `switch` 从一个地方挪到另一个地方，这通常更像简单工厂。

如果类型主要由数据决定，在 UE 里更常见的替代方案是：

```cpp
UPROPERTY(EditDefaultsOnly)
TSubclassOf<UMyProduct> ProductClass;
```

然后在运行时：

```cpp
UMyProduct* Product = NewObject<UMyProduct>(Outer, ProductClass);
```

这叫数据驱动创建，不一定需要再额外引入一层子类工厂。

# 实现方式（步骤）

如果要在自己的 UE 代码里复刻 Lyra 这种工厂方法，可以按这个步骤写。

## 第一步：定义产品基类

先让所有可能被创建的对象有一个共同父类或接口。

```cpp
UCLASS(Abstract)
class UMySettingRegistryBase : public UObject
{
    GENERATED_BODY()

public:
    virtual void Initialize(ULocalPlayer* InLocalPlayer) {}
};
```

重点是：父类流程只依赖 `UMySettingRegistryBase`，不要依赖 `UMyLyraSettingRegistry` 这种具体类。

## 第二步：在创建者基类里声明工厂方法

```cpp
UCLASS(Abstract)
class UMySettingScreenBase : public UUserWidget
{
    GENERATED_BODY()

protected:
    virtual UMySettingRegistryBase* CreateRegistry() PURE_VIRTUAL(, return nullptr;);

private:
    UMySettingRegistryBase* GetOrCreateRegistry();

private:
    UPROPERTY(Transient)
    TObjectPtr<UMySettingRegistryBase> Registry;
};
```

这里的返回值一定用产品基类。

不要写成：

```cpp
virtual UMyLyraSettingRegistry* CreateRegistry(); // 不推荐
```

因为这样基类又重新依赖具体产品了，工厂方法的解耦意义会变弱。

## 第三步：父类流程只调用工厂方法，不直接创建具体类

```cpp
UMySettingRegistryBase* UMySettingScreenBase::GetOrCreateRegistry()
{
    if (Registry == nullptr)
    {
        UMySettingRegistryBase* NewRegistry = CreateRegistry();

        // 这里放所有子类都必须遵守的统一接线流程
        // NewRegistry->OnChanged.AddUObject(...);
        // SettingPanel->SetRegistry(NewRegistry);

        Registry = NewRegistry;
    }

    return Registry;
}
```

这一步是整个模式最核心的地方。

父类不写：

```cpp
NewObject<UMyLyraSettingRegistry>();
```

父类只写：

```cpp
CreateRegistry();
```

## 第四步：子类重写工厂方法

```cpp
UCLASS(Abstract)
class UMyLyraSettingScreen : public UMySettingScreenBase
{
    GENERATED_BODY()

protected:
    virtual UMySettingRegistryBase* CreateRegistry() override;
};

UMySettingRegistryBase* UMyLyraSettingScreen::CreateRegistry()
{
    UMyLyraSettingRegistry* NewRegistry = NewObject<UMyLyraSettingRegistry>(this);
    NewRegistry->Initialize(GetOwningLocalPlayer());
    return NewRegistry;
}
```

子类只写变化点，不复制父类流程。

如果以后有移动端设置页：

```cpp
UMySettingRegistryBase* UMyMobileSettingScreen::CreateRegistry()
{
    UMyMobileSettingRegistry* NewRegistry = NewObject<UMyMobileSettingRegistry>(this);
    NewRegistry->Initialize(GetOwningLocalPlayer());
    return NewRegistry;
}
```

父类 `GetOrCreateRegistry()` 一行都不用改。

# Do / Don't

## Do

- ✅ **让工厂方法返回产品基类**：例如返回 `UGameSettingRegistry*`，而不是 `ULyraGameSettingRegistry*`。
- ✅ **把创建后的统一流程放在父类**：绑定事件、注册、塞 UI、缓存，都应该由父类统一做。
- ✅ **UObject 产品用 UE 创建 API**：`NewObject`、`CreateWidget`、`SpawnActor`，不要裸 `new`。
- ✅ **缓存 UObject 引用时用 `UPROPERTY` / `TObjectPtr`**：让 GC 能看见引用关系。
- ✅ **子类只写变化点**：子类越薄，越说明父类流程封装得好。

## Don't

- ❌ **不要让父类依赖具体产品类**：否则工厂方法就变成了“把 new 换了个位置”。
- ❌ **不要让每个子类复制完整流程**：一旦复制，就会出现某个子类漏绑定、漏缓存、漏初始化。
- ❌ **不要为了一个永远不变的类型硬套工厂方法**：那只是增加类层级。
- ❌ **不要在 UObject 上使用裸 `new`**：会绕过 UE 对象系统。
- ❌ **不要把所有类型判断都塞进工厂方法子类**：如果你写出巨大 `switch`，那可能已经变成简单工厂或数据驱动创建了。

# 优缺点

## 优点

### 1. 解耦框架和项目

`UGameSettingScreen` 属于 `GameSettings` 插件，`ULyraGameSettingRegistry` 属于 Lyra 项目。

插件层不能依赖项目层，所以父类不能直接创建 Lyra 的 Registry。工厂方法让插件只依赖 `UGameSettingRegistry`，具体类型由项目子类决定。

这对 UE 插件特别重要：插件越通用，越不应该知道下游项目的具体类。

### 2. 固定流程只写一遍

`GetOrCreateRegistry()` 里那几步：

```cpp
CreateRegistry();
AddUObject(...);
SetRegistry(...);
Registry = NewRegistry;
```

只写在父类一处。

以后如果要加日志、加校验、加埋点、加空指针保护，也只改父类。

### 3. 子类扩展成本低

下游想换 Registry，只要继承并重写：

```cpp
virtual UGameSettingRegistry* CreateRegistry() override;
```

不用理解整套设置面板如何绑定、如何缓存、如何追踪变更。

这就是框架设计里的“窄扩展点”：开放的口子越小，越不容易被误用。

### 4. 更符合开闭原则

新增一个具体 Registry，不需要改 `UGameSettingScreen`。

父类对修改关闭，对扩展开放。

## 缺点

### 1. 类数量会上升

如果每一种产品都要配一个创建者子类，类会变多。

例如：

```text
ULyraSettingScreen       -> ULyraGameSettingRegistry
UMobileSettingScreen     -> UMobileGameSettingRegistry
UConsoleSettingScreen    -> UConsoleGameSettingRegistry
```

当变化维度很多时，继承层级可能会膨胀。

### 2. 不适合简单条件分支

如果只是根据一个枚举创建不同对象：

```cpp
switch (SettingType)
{
case Bool: return CreateCheckbox();
case Number: return CreateSlider();
}
```

这更像简单工厂，不一定需要为每种类型建立一个子类。

### 3. 不适合纯数据驱动场景

如果设计师希望在蓝图或 DataAsset 里直接配置类型，那么 `TSubclassOf` 往往更直观。

工厂方法更适合“行为随子类变化”，而不是“类型随配置变化”。

# UE 中还有哪些类似写法？

Lyra 里还有一些同样带有“父类流程 + 子类填空”味道的写法。

## 1. GameMode 决定默认 Pawn

`ALyraGameMode` 重写了 `GetDefaultPawnClassForController_Implementation`：

```cpp
// Source/LyraGame/GameModes/LyraGameMode.cpp:332
UClass* ALyraGameMode::GetDefaultPawnClassForController_Implementation(AController* InController)
```

这个函数回答的是：

> 对这个 Controller，应该使用哪一种 PawnClass？

后面 `SpawnDefaultPawnAtTransform_Implementation` 会使用这个 PawnClass 创建 Pawn：

```cpp
// Source/LyraGame/GameModes/LyraGameMode.cpp:345
APawn* ALyraGameMode::SpawnDefaultPawnAtTransform_Implementation(AController* NewPlayer, const FTransform& SpawnTransform)
```

这和 `CreateRegistry()` 的味道很像：上层 Spawn 流程稳定，具体 Pawn 类型由可重写函数决定。

## 2. UserWidget 的 Native* 钩子

`UGameSettingScreen` 本身也重写了 `NativeGetDesiredFocusTarget()`：

```cpp
// Plugins/GameSettings/Source/Private/Widgets/GameSettingScreen.cpp:48
UWidget* UGameSettingScreen::NativeGetDesiredFocusTarget() const
```

这种 `Native*` 函数在 UE UI 里很常见。它们未必都是严格的工厂方法，但经常体现同一种框架思路：

> 引擎或父类定义调用时机，项目子类填具体行为。

## 3. GameFeature / DataAsset 中的类型替换

另一类相近方案是 `TSubclassOf` 数据驱动。

例如 Pawn、Ability、Widget 这类对象，经常不是通过子类工厂方法决定，而是通过 DataAsset 配置类型，然后运行时 `NewObject` / `SpawnActor` / `CreateWidget`。

它和工厂方法的区别是：

- 工厂方法：类型决策在子类代码里；
- 数据驱动：类型决策在资产或配置里。

# 与其他模式的关系

## 1. 和模板方法模式

工厂方法常常嵌在模板方法里。

在本文案例中：

```cpp
UGameSettingScreen::GetOrCreateRegistry()
```

就是一个小型模板方法。它定义了固定流程：

```text
检查缓存 -> 创建 Registry -> 绑定事件 -> 塞进 Panel -> 缓存 -> 返回
```

其中 `CreateRegistry()` 是被子类重写的步骤。

所以可以说：

> 工厂方法经常不是单独出现，而是作为模板方法中的一个可变步骤出现。

## 2. 和简单工厂

简单工厂通常是一个集中函数：

```cpp
UWidget* CreateWidgetForSetting(UGameSetting* Setting)
{
    if (Setting->IsBool()) return CreateCheckbox();
    if (Setting->IsNumber()) return CreateSlider();
    return nullptr;
}
```

它的特点是：创建逻辑集中在一个函数里，通常靠 `if` / `switch` 判断。

工厂方法则是：

```cpp
virtual UGameSettingRegistry* CreateRegistry();
```

它的特点是：创建决策下放给子类，靠多态扩展。

一句话区分：

> 简单工厂靠条件分支选类型；工厂方法靠子类重写选类型。

## 3. 和抽象工厂

如果一个创建者不只是创建一个 Registry，而是要创建一整套相关对象：

- Registry；
- Setting Row Widget；
- Detail Panel；
- Apply Button；
- Reset Button；

并且这些对象要成套替换，比如 PC UI 一套、主机 UI 一套、移动端 UI 一套，那就更接近抽象工厂。

工厂方法通常只关注一个产品创建点；抽象工厂关注一组产品族。

## 4. 和数据驱动创建

UE 里经常可以不用继承工厂，而是把类型写进资产：

```cpp
UPROPERTY(EditDefaultsOnly)
TSubclassOf<UUserWidget> SettingRowWidgetClass;
```

这种方式更适合设计师调参，工厂方法更适合程序框架扩展。

两者不是互斥的。实际项目里也可以这样组合：

- 工厂方法决定使用哪套配置；
- 配置里用 `TSubclassOf` 决定具体 Widget 类型。

# 一句话总结

工厂方法的本质不是“把 `NewObject` 包一层虚函数”，而是：

> 父类把稳定且容易漏的流程牢牢握住，只把“创建哪一种具体产品”这个变化点开放给子类。

在 Lyra 的 `GameSettingScreen.CreateRegistry` 案例里，`UGameSettingScreen` 负责 `GetOrCreateRegistry()` 的完整流程，`ULyraSettingScreen` 只负责返回 `ULyraGameSettingRegistry`。流程只有一份，具体类型可以替换，这就是工厂方法在 UE 项目里的典型价值。

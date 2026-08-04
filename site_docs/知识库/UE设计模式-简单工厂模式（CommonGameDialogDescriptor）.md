---
area:
tags: [UE, 设计模式, SimpleFactory, Factory]
created: 2026-07-10
source: Lyra (LyraStarterGame) / Plugins/CommonGame · Source/LyraGame/UI · Source/LyraGame/Camera
---
# 简单工厂

# 这个模式是什么

简单工厂的意图：**把"创建并初始化一个对象"的活儿，从调用方手里挪到一个专门的函数里。** 
考虑一个简单的软件应用场景，一个系统可以提供多个外观不同的按钮（如圆形按钮、矩形按钮、菱形按钮等）， 这些按钮都源自同一个基类，不过在继承基类后不同的子类修改了部分属性从而使得它们可以呈现不同的外观，如果我们希望在使用这些按钮时，不需要知道这些具体按钮类的名字，只需要知道表示该按钮类的一个参数，并提供一个调用方便的方法，把该参数传入方法即可返回一个相应的按钮对象，此时，就可以使用简单工厂模式。

Gong of Four 没把它列为正式的 23 个模式之一，它更像工厂方法的简化前身。但思想是一样的：**让"怎么造"这件事有个唯一的、可控的出口**，而不是散落在每个用到它的地方。

带着这个框，我们来看 Lyra 里一个很典型的例子。

# 这个类要解决什么问题

我找了 `UCommonGameDialogDescriptor`。

**① 它是什么。** 它不是一个界面，你在屏幕上永远看不到它。它是一张"**要弹一个什么样的对话框**"的说明单：标题写什么（`Header`）、正文写什么（`Body`）、下面摆几个按钮、每个按钮是确认还是取消（`ButtonActions`）。

**② 它运行时变成什么。** 真正把它画到屏幕上的是另一个类 `ULyraConfirmationScreen`（一个 UMG 控件）。它拿到这张说明单，把 `Header` 塞进标题控件、`Body` 塞进正文、按 `ButtonActions` 一个个生成按钮，最后成为玩家看到的那个弹框。

```
UCommonGameDialogDescriptor   →   ULyraConfirmationScreen   →   玩家看到的弹框
（纯数据：弹什么）                 （UMG 控件：怎么画）            （运行时画面）
```

>
![](Pasted image 20260710114255.png)
这里顺带回答一个问题：为什么要单独搞这么一个"数据类"，而不是让 UI 控件自己存标题和按钮？因为"弹什么"和"怎么画"是两件会各自变化的事。同一张说明单，既能喂给正常的确认框，也能喂给样式不同的报错框（Lyra 里 `ShowConfirmation` 和 `ShowError` 用的就是同一种 Descriptor、不同的 Widget）。数据和皮肤解耦，谁变都不影响另一边。

**③ 为什么不能直接朴素地写。** 这张说明单看着简单，但它容易被拼错——每个要弹框的地方若都自己 `NewObject` 再手工拼按钮，迟早出岔子。**④ 所以 Epic 才有了下面这套东西**，我们看它是怎么被"造"出来的。

# 先看源码

来自 `Plugins/CommonGame/Source/Private/Messaging/CommonGameDialog.cpp:26`。

```cpp
UCommonGameDialogDescriptor* UCommonGameDialogDescriptor::CreateConfirmationOkCancel(const FText& Header, const FText& Body)
{
    UCommonGameDialogDescriptor* Descriptor = NewObject<UCommonGameDialogDescriptor>();
    Descriptor->Header = Header;
    Descriptor->Body   = Body;

    FConfirmationDialogAction ConfirmAction;
    ConfirmAction.Result = ECommonMessagingResult::Confirmed;
    ConfirmAction.OptionalDisplayText = LOCTEXT("Ok", "Ok");

    FConfirmationDialogAction CancelAction;
    CancelAction.Result = ECommonMessagingResult::Cancelled;
    CancelAction.OptionalDisplayText = LOCTEXT("Cancel", "Cancel");

    Descriptor->ButtonActions.Add(ConfirmAction);
    Descriptor->ButtonActions.Add(CancelAction);
    return Descriptor;
}
```

它的邻居还有 `CreateConfirmationOk`、`CreateConfirmationYesNo`、`CreateConfirmationYesNoCancel`，四个函数返回的都是同一个类，区别只在里面的按钮配置。

# 为什么这么设计

先想一个问题：这张说明单本身很简单，就是标题、正文加一个按钮数组。既然这么简单，为什么不让调用方自己 `NewObject` 然后填一下？

因为麻烦的不是"造对象"，而是"把按钮配对"。

一个"确认/取消"框，要往 `ButtonActions` 里塞两个 `FConfirmationDialogAction`：一个 `Result` 是 `Confirmed`、文案 "Ok"，一个是 `Cancelled`、文案 "Cancel"。而下游的 `ULyraConfirmationScreen::SetupDialog` 会 `switch(Action.Result)` 去决定按钮绑哪个输入（确认键/返回键）——枚举配错，按钮的行为就错了。

假如没有这几个工厂函数，每个要弹框的地方都得自己拼一遍：

```
业务A ──→ NewObject ──→ 填 Header/Body ──→ 手拼 Confirmed 按钮 ──→ 手拼 Cancelled 按钮
业务B ──→ NewObject ──→ 填 Header/Body ──→ 只拼了一个按钮（忘了 Cancel）
业务C ──→ NewObject ──→ 填 Header/Body ──→ Result 填错，按钮绑错了输入
```

同一份拼装逻辑，被复制到几十个调用点，每一份都可能漏按钮、配错枚举、文案不统一。想给所有确认框的 "Ok" 换个本地化 key？满项目搜。

工厂把这条链收成一根：

```
业务 ──→ CreateConfirmationOkCancel(标题, 正文)
              │
              └─→ NewObject ──→ 填字段 ──→ 拼好两个按钮 ──→ 返回
```

调用点从"五步、每步都可能错"变成"一行、不可能错"。按钮配对这件事，全项目**只有一份实现**——这才是 Epic 想收起来的东西。不是 `NewObject` 值得收，是那段易错的初始化值得收。

# 和教科书有什么不一样

教科书里的简单工厂通常是"一个函数按类型分发不同的类"：

```
教科书：
  Create(EType type)
      switch(type)
        case A: return new A;
        case B: return new B;
```

而这里是"一个类型、多个语义化的创建入口"：

```
UE：
  CreateConfirmationOk(...)        ┐
  CreateConfirmationOkCancel(...)  ├─→ 都返回同一个类
  CreateConfirmationYesNo(...)     ┘   区别在内部预设
```

差别的根源在 UE：

一是 `UObject` 根本不能 `new`，只能走 `NewObject`——工厂天然就得包住它。二是把配方拆成多个具名函数，蓝图侧可以逐个引用（`UFUNCTION` 一个个暴露），比传一个 `enum` 再 switch 友好得多。三是新增一种配方只要加个函数，不用回去改一个越来越长的 `switch`。

# UE 中还有哪些类似写法？

- `UCommonGameDialogDescriptor::CreateConfirmation*`：同一个类，四种按钮预设。`CommonGameDialog.cpp:11`
- `ULoadingProcessTask::CreateLoadingScreenProcessTask`：带 `WorldContextObject`，工厂内部找到 Subsystem、`NewObject`、再注册进去，失败就返回 `nullptr`。`LoadingProcessTask.cpp:13`
- `ULyraCameraModeStack::GetCameraModeInstance`：入参是 `TSubclassOf`，按传入的类造对象，还顺手做了"同类只造一次"的缓存。`LyraCameraMode.cpp:343`

# 什么时候应该这样写？

✔ 创建后面跟着一段固定但啰嗦的初始化（拼数组、配枚举、设默认值）。
✔ 这段初始化会在很多地方重复，且改动会牵一发动全身。
✔ 需要在创建时顺带做副作用：找 World、挂 `Outer`、注册进某个 Subsystem。
✔ 蓝图也要能创建同一种对象。

什么时候别用：如果只是一次性、无重复、无初始化的创建，直接 `NewObject` 就好，包一层工厂纯属噪音。如果产品种类会不断膨胀、且要在运行时按数据决定具体子类，简单工厂会越写越长——那时该换成工厂方法或数据驱动（`TSubclassOf` / `UDataAsset`）。

# 一句话总结

Epic 这样写，本质不是为了隐藏 `NewObject`，而是为了让"这种对象该怎么拼出来"这件事，在整个项目里**只有一份答案**。

---

## 📸 待补截图清单

截好后放进 `40_知识库/attachments/`，文件名保持与下方一致，文中占位即可自动显示。

- [ ] **simple-factory-dialog-runtime.png** —— 运行时的确认框
  - 怎么拿：编辑器里 PIE 运行 Lyra，触发一个会弹确认框的场景（如按 ESC 打开菜单里的"退出到主菜单/退出游戏"确认）。
  - 要框住：完整弹框，能看清标题、正文、底部的 OK / Cancel 按钮，用来对应 `Header / Body / ButtonActions`。
- [ ] **simple-factory-widget-tree.png**（可选，增强"数据 vs 表现"这一段）
  - 怎么拿：内容浏览器搜 `W_ConfirmationScreen`（`ULyraConfirmationScreen` 的蓝图控件）→ 双击打开。
  - 要框住：左侧控件层级树里的 `Text_Title` / `RichText_Description` / `EntryBox_Buttons`，正好对应 `SetupDialog` 里被赋值的那几个控件。

## 关联
- [[UE设计模式-工厂方法模式]]
- [[NewObject 与 UObject 创建]]
- [[TSubclassOf]]
- [[Subsystem]]
- [[UMG 数据与表现分离]]

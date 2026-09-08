# slua 源码解析：Lua 与 UE 对象系统的双向绑定

> slua 本质是一层"胶水层"：把 Lua VM 接入 UE 的对象生命周期、反射系统与 GC 系统，让 Lua 脚本能像蓝图一样读写 UObject 属性、调用 UFunction，同时不破坏 UE 自己的内存管理。

## 一、slua 的核心职责

- 创建并管理 Lua VM
- 加载执行 Lua 脚本
- 把 UE 的 UObject / UClass / UStruct / UEnum 暴露给 Lua
- 把 Lua 回调接入 UE 生命周期：Tick、Delegate、网络等系统
- 解决 Lua GC 与 UE GC 之间的对象生命周期问题

## 二、启动与初始化调用链

### 2.1 从游戏启动到 LuaState 创建

```text
UE 游戏启动
  → 创建 NS_SLUA::LuaState
      → LuaState::init()
      → luaL_newstate()   创建 lua_State
          → 注册 C++ 函数 / UE 类型绑定 / require loader
      → LuaState::doFile()加载并执行入口脚本
```

### 2.2 LuaState::init() 具体做了什么

- 创建 Lua VM（`luaL_newstate()`）
- 把 `this`（LuaState 指针）保存到 `lua_State` 的 extraspace
- 打开 Lua 标准库
- 注册 slua 自己提供的 C 函数
- 注册 `require` 的自定义 loader
- 建立 UObject / UClass / UStruct 缓存表
- 注册各种容器（Array/Map/Set/Struct）的元表
- 注册错误处理、调试、性能统计相关钩子

从 `lua_State*` 反查 `LuaState*` 的写法：

```cpp
LuaState* state = LuaState::get(L);
// 实现等价于：
return (LuaState*)*((void**)lua_getextraspace(L));
```

## 三、LuaState —— slua 的 VM 管理器

`NS_SLUA::LuaState` 是 slua 对 Lua 虚拟机的封装对象，同时接入了 UE 的四类机制：

| 接入机制 | 作用 |
|---|---|
| `FUObjectDeleteListener` | UE 对象销毁时通知 slua，使 Lua 侧的包装对象失效，避免 UE 已 `Destroy` 后 Lua 仍持有野指针 |
| `FUObjectCreateListener` | UE UObject 创建时可接收通知 |
| `FGCObject` | 向 UE GC 报告哪些 UObject 仍被 Lua 持有 |
| `FTickableGameObject` | 每帧驱动 Lua Tick：Tick LuaActor、增量 GC、清理失效协程或延迟任务 |

生命周期：

```text
C++ 创建 LuaState
  → Init：创建 lua_State* L，配置 Lua，注册 slua 能力
  → 执行 DoFile / DoString / RequireModule
  → 运行中 LuaState::Tick()（每帧）
  → LuaState::Close() → lua_close(L)
```

对象销毁时，slua 会先 `NotifyObjectDeleted`，再 `UnlinkUObject`，并把对应 userdata 标记为 `HAD_FREE`，全程绑定 LuaState 自身的生命周期。

## 四、userdata —— Lua 侧承载 UE 对象的容器

### 4.1 为什么不能直接用 Lua table 存 UObject*

Lua 原生数据类型无法安全承载一个 C++/UE 对象，例如 `UObject* Obj`：

- Lua 不知道这个指针指向什么类型
- Lua 不知道这个对象是否已经被 UE 销毁
- Lua 不知道怎么读取 UProperty
- Lua 不知道该怎么调用 UFUNCTION
- Lua GC 也不知道指针释放时是否要做 C++ 清理

因此需要 Lua C API 提供的 `userdata`：一块由 Lua 管理生命周期的原生内存，C++ 可以在里面放指针、结构体或自定义数据，再通过元表定义属性访问、函数调用、GC 清理等行为。

```cpp
void* memory = lua_newuserdata(L, size);
```

### 4.2 userdata 的内部结构

```cpp
struct UDBase {
    uint32  flag;   // UD_UOBJECT / UD_HADFREE / ...
    void*   parent;
    UObject* ud;    // 真正的 UObject* 指针
};
```

`flag` 常见标记：

| 标记 | 含义 |
|---|---|
| `UD_UOBJECT` | 该 userdata 包装的是 UObject |
| `UD_USTRUCT` | 包装的是 UStruct |
| `UD_AUTOGC` | Lua GC 时需要执行释放/清理逻辑 |
| `UD_HADFREE` | 底层 C++ / UE 对象已经失效 |
| `UD_REFERENCE` | 是引用型数据，而非独立副本 |

Lua 不会直接拿裸指针做成员访问，而是通过 userdata 的元表进行访问控制：读 `actor.Health` 会触发元表的 `__index`，等价于 `actor.__index(actor, "Health")`。

### 4.3 userdata 的元表结构

```text
userdata
  └── metatable
        ├─ __index
        ├─ __newindex
        ├─ __gc
        ├─ __eq
        ├─ __tostring
        └─ ...
```

`actor.Health` 触发 `actor 的元表.__index(actor, "Health")`，最终走到 `LuaObject::objectIndex(...)`，再通过 UE 反射读取 `FProperty`。
`actor.Health = 100` 触发 `__newindex`，最终进入 `LuaObject::objectNewIndex(...)`。

## 五、Lua 元表机制基础

元表（metatable）可以修改一个值在面对未知操作时的行为，比如定义 `a + b` 的计算方式。当 Lua 尝试相加两个表时，会先检查其中一个是否有元表，且元表中是否有 `__add` 字段。

获取/设置元表：`getmetatable(t)`、`setmetatable(t, mt)`。

```lua
t = {}
t1 = {}

t.a = 123
t1.a = 4

t.func = function() return 1 end
t1.func = function() return 2 end

-- 定义元表
mt = {}
setmetatable(t, mt)
setmetatable(t1, mt)

-- 为元表定义 __add
mt.__add = function(a, b)
    print(a.func() + b.func())
    return a.a + b.a
end

print(t + t1)
```

常见元方法：

| 键 | 描述 |
|---|---|
| `__add` | 改变加法操作符的行为 |
| `__sub` | 改变减法操作符的行为 |
| `__mul` | 改变乘法操作符的行为 |
| `__div` | 改变除法操作符的行为 |
| `__mod` | 改变模除操作符的行为 |
| `__unm` | 改变一元减操作符的行为 |
| `__concat` | 改变连接操作符的行为 |
| `__eq` | 改变等于操作符的行为 |
| `__lt` | 改变小于操作符的行为 |
| `__le` | 改变小于等于操作符的行为 |

`__index` 元方法：访问表中不存在的字段本应得到 `nil`，实际上会触发解释器寻找名为 `__index` 的元方法。

```lua
mt = { x = 5 }
w = {}
w = setmetatable(w, mt)

print(w.x)   --> 5，从 mt 找到
print(w.y)   --> nil，mt 里也没有

-- __index 也可以是函数
mt.__index = function(_, key)
    return mt[key]
end
print(w.x)
```

## 六、UE 反射对接：属性读写的完整链路

### 6.1 读属性：LuaObject::objectIndex

```text
userdata（内部保存 UObject 包装对象）
  → 取出 UObject*
  → obj->GetClass() 得到 UClass
  → FindCacheProperty(L, cls, name) 按名字查 FProperty / UFunction
  → FProperty 负责读写属性内存；UFunction + ProcessEvent 负责调用 UE 函数
  → 结果转换成 Lua 值并压入 Lua 栈
```

`FProperty` 定位实际属性内存的方式：

```cpp
FProperty* up = ...;
void* propertyAddress = up->ContainerPtrToValuePtr<uint8>(obj);
// 可以理解为：UObject* obj + 属性在类实例中的偏移
```

slua 用两张表把 `FFieldClass*` 映射到具体的转换函数：

```cpp
TMap<FFieldClass*, LuaObject::PushPropertyFunction>  pusherMap;   // UE → Lua，读属性/返回值时用
TMap<FFieldClass*, LuaObject::CheckPropertyFunction> checkerMap;  // Lua → UE，写属性/传参时用
```

`objectIndex` 找到属性后，取得适配该属性类型的 pusher：

```cpp
auto pusher = getPusher(up);
return pusher(L, up, up->ContainerPtrToValuePtr<uint8>(obj), 0, nullptr);
```

即：`FProperty` + 属性内存地址，按具体属性类型调用对应 pusher，转换为 Lua 能理解的值压入栈顶——支持 integer / number / boolean / string / UObject userdata / LuaStruct / LuaArray / LuaMap / LuaSet。

### 6.2 写属性：LuaObject::objectNewIndex

Lua 写属性时触发 `__newindex`，进入：

```cpp
LuaObject::objectNewIndex(lua_State* L, UObject* obj, const char* name, int valueIdx, bool checkValid)
```

核心逻辑：

```cpp
UClass* cls = obj->GetClass();
FProperty* up = findCacheProperty(L, cls, name);
auto checker = LuaObject::getChecker(up);

checker(
    L,
    up,
    up->ContainerPtrToValuePtr<uint8>(obj),
    valueIdx,
    true
);
```

## 七、UObject → Lua userdata：LuaObject::push

入口是 `LuaObject::push(lua_State* L, UObject* obj, bool ref, ...)`，职责：

```text
C++ UObject*
  → 查 Lua 缓存（obj 是否已有 userdata？）
        ├─ 有：直接把旧 userdata 压栈
        └─ 没有：
       ├─ lua_newuserdata(...)
       ├─ userdata->ud = obj
       ├─ 设置 UObject 元表（__index / __newindex / __gc）
       ├─ 加入 UObject* → userdata 缓存
       └─ 登记 Lua / UE GC 生命周期关系
  → 把 userdata 压入 Lua 栈
```

空指针会被提前处理：`if (!obj) return pushNil(L);`，因此 C++ 侧的 `UObject* obj = nullptr` 到 Lua 侧是 `nil`，而不是一个"内部指针为空"的 userdata。

## 八、UE GC 与 Lua GC 的协作

Lua userdata 内部保存的只是指针，但 UObject 的生命周期由 UE 管理。slua 做了两类保护：

**A. Lua 仍引用 UObject：让 UE GC 知道**

`LuaState` 继承 `FGCObject`，通过 `AddReferencedObjects(FReferenceCollector& Collector)` 把 Lua 持有的 UObject 交给 UE GC 追踪，避免出现"Lua 还保存 obj，但 UE 认为无人引用 → GC 回收 obj → Lua 变成野指针"的情况。

**B. UObject 已被销毁：标记 Lua userdata 无效**

`LuaState` 监听 `FUObjectArray::FUObjectDeleteListener`。当 UObject 被删除，slua 找到对应 userdata 并设置 `UD_HADFREE`。之后 Lua 访问时会检查：

```cpp
if (UD->flag & UD_HADFREE)
    luaL_error(L, "arg %d had been freed, can't be used", ...);
```

效果：

```lua
actor:Destroy()
actor:Jump()  -- 报"对象已经释放"，而不是 C++ 崩溃
```

## 九、笔记里还没覆盖的内容（待补充清单）

以下是 slua 面试/源码分析中常见但当前笔记未涉及的部分，建议后续补充：

- **函数调用链路**：Lua 调用 UFunction 的完整过程——参数如何从 Lua 栈转换为 UE 参数内存布局、`UFunction::ProcessEvent` 如何被触发、返回值/输出参数如何压回 Lua 栈。
- **C++ 函数注册到 Lua**：`lua_register` / 自动绑定工具生成代码的机制，`LuaFunction` 的调用桩（thunk）长什么样。
- **容器绑定细节**：`LuaArray` / `LuaMap` / `LuaSet` / `LuaStruct` 内部如何映射 `TArray` / `TMap` / `TSet` / `UStruct`，值类型 vs 引用类型的处理差异。
- **Delegate 绑定**：Lua 函数绑定到 UE `Delegate` / `Multicast Delegate` 的实现方式，回调触发时如何从 C++ 跳回 Lua。
- **协程与异步**：Lua 协程如何与 UE 的异步节点（Latent Action、Timer、异步加载）结合，slua 是否有专门的协程调度器。
- **Lua 侧 OOP / 类继承**：slua 如何用 Lua 模拟继承 UE 类（`BlueprintableLua` 之类的机制），是否支持 Lua 类继承 UObject 并重写 UFUNCTION。
- **热更新/热重载**：`slua` 的脚本 reload、hotfix 机制，reload 时如何处理已存在的 userdata 和闭包状态。
- **错误处理与调用栈**：`pcall` 包装、Lua 报错如何映射回文件行号、崩溃保护（防止 Lua 报错导致 C++ 侵入性崩溃）。
- **多线程与 GC 调优**：Lua VM 本身不是线程安全的，UE 多线程系统调用 Lua 时如何保护；增量 GC 的具体调参与性能测量方法。
- **打包与加载**：`.lua` / 预编译 `.luac` 的加载方式，`require` loader 的搜索路径与加密/混淆方案。
- **性能与内存分析工具**：slua 自带的 profiler、内存快照，如何定位 Lua 侧内存泄漏（比如闭包意外持有 UObject 引用导致 GC 不掉）。

## 相关笔记

- [[UE5-网络同步模块源码深度解析]]
- [[UE查缺补漏]]

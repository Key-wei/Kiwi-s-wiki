### 基础部分
网络连接概念:NetDriver,NetConnection,Channel,Packet,Bunch

NetDriver是网络处理的核心，负责管理UNetConnections
服务器NetDriver维护一个NetConnections列表，每个连接代表一个连接的玩家，负责复制Actor数据。客户端NetDriver管理连接到服务器的单个连接。
NetConnection再服务器和客户端上，NetDriver负责接收来自网络的数据包，并把这些数据包传递给适当的NetConnection（必要时建立新的NetConnections)
Packet是CS网络连接之间发送的数据，由Packet包的元数据（报头信息和确认ack）和Bunches组成
Bunche是CS网络连接的通道对之间发送的数据，当一个连接接收到一个数据包的时候，该数据包将被分解成单独的Bunch，这些Bunch然后被传递到单独的通道以进一步处理。一个Packet可以不包含Bunch，单个Bunch或者多个Bunch。当一个Bunch太大时，在传递之前会把他切成许多小的Bunch，这些Bunch将被标记为PartialInital,Partial或PartitalFinal，利用这些信息再接收端从新组装Bunch。

- **NetDriver 网络驱动**  
    使用其子类IPNetDriver,NetDriver与[World](https://zhida.zhihu.com/search?content_id=206533423&content_type=Article&match_order=1&q=World&zhida_source=entity)一一对应，UE默认使用UDP通信  
    主要功能：创建管理Connection; 收发数据包; 初始化CS连接；Actor同步、RPC管理; Socket管理; 对于Server端的NetDriver对象管理多个NetConnection，对于Client端的NetDriver对象管理一个NetConnection
- **Connection 网络连接**  
    表示网络连接. 关联了NetDriver、PackageMap、UChannel数组和PlayerController。服务器上：一个客户端到服务器的一个连接叫一个ClientConnection；在客户端上：服务器到客户端的连接叫ServerConnection。
- **Channel 数据通道**  
    每一个通道只负责交换某一个特定类型特定实例的数据信息。  
    **ControlChannel**：CS之间发送控制信息，主要是发送接收连接与断开的相关消息。在Connection中只会在初始化连接的时候创建一个该通道实例。  
    **[ActorChannel](https://zhida.zhihu.com/search?content_id=206533423&content_type=Article&match_order=1&q=ActorChannel&zhida_source=entity)**：处理Actor本身相关信息的同步，包括自身的同步以及子组件，属性的同步，RPC调用等。每个Connection连接里的每个同步的Actor都对应着一个ActorChannel实例  
    **[VoiceChannel](https://zhida.zhihu.com/search?content_id=206533423&content_type=Article&match_order=1&q=VoiceChannel&zhida_source=entity)**：用于发送接收语音消息，在Connection中初始化连接的时候创建一个该通道实例
- **PlayerController 玩家控制器**  
    UPlayer中关联PlayerController,其子类为本地玩家LocalPlayer和网络连接Connection
- **World 游戏世界**  
    管理游戏逻辑，驱动NetDriver，处理Actor Tick和复制
- **Packet**  
    从Socket读出来/输出的数据，一个Packet里面可能有多个Bunch数据或者Ack数据
- **Bunch**  
    从逻辑上层分发下来的同步数据包，数据可能不完整，Bunch分为属性Bunch以及RPCBunch。继承自FNetBitWriter。  
    主要记录了Channel信息，NGUID。同时包含其他的附属信息如是否是完整的Bunch，是否是可靠等，Bunch分为属性Bunch以及InBunch：从Channel接收的数据流串 ，UNetConnection::ReceivedPacket的时候创建  
    OutBunch：从Channel产生的数据流串，UActorChannel::ReplicateActor()的时候创建
- **Ack**  
    Ack是与Bunch同级别概念的网络数据串，用于实现UDP的可靠数据传输
- **[FSocket](https://zhida.zhihu.com/search?content_id=206533423&content_type=Article&match_order=1&q=FSocket&zhida_source=entity) 平台Socket的基类**
- UPackageMap 生成与维护Object与NGUID的映射，负责Object序列化。每个Connection对应一个。
- **PacketHandler 网络包预处理**  
    比如加解密，握手等。里面有一个或多个HandlerComponents来执行特殊的数据处理。目前内置的包括加密组件RSA，AES，和握手组件StatelessConnectHandlerComponent
- **[FObjectReplicator](https://zhida.zhihu.com/search?content_id=206533423&content_type=Article&match_order=1&q=FObjectReplicator&zhida_source=entity)**  
    属性同步的执行器，每个Actorchannel对应一个FObjectReplicator，对应一个对象实例。设置ActorChannel通道的时候会创建
- **FRepState**  
    针对每个连接同步的历史数据，记录同步前用于比较的Object对象信息，存在于FObjectReplicator里面
- **[FRepLayOut](https://zhida.zhihu.com/search?content_id=206533423&content_type=Article&match_order=1&q=FRepLayOut&zhida_source=entity)**  
    同步的属性布局表，记录所有当前类需要同步的属性，每个类或者RPC函数有一个
- **FRepChangedPropertyTracker**  
    属性变化轨迹记录，一般在同步Actor前创建，Actor销毁的时候删掉。
- **FReplicationChangelistMgr**  
    存放当前的Object对象，保存属性的变化历史记录
![[Pasted image 20260908173343.png]]
## 基本通信流程

1. UE通信协议是用UDP. 只要知道对方的IP地址以及端口号服务器和客户端即可完成通信。
2. 收发数据默认在游戏线程（GT）
3. 下图两个客户端连接到一个server的。对于每一个客户端，都会建立起一个Connection。在服务器上这个Connection叫做ClientConnection，对于客户端这个Connection叫做ServerConnection。每一个Channel都会归属于一个Connection，Channel知道他对应的是哪个客户端
4. NetDriver接受socket数据包Packet后，根据IP和Port找到对应的Connection，Connection处理Packet, 之后拆分为Bunch交由Channel处理

![](https://pic2.zhimg.com/v2-c71f388b7d7bdaa4e92210d330eeeefd_1440w.jpg)

Channel级别通信流程图

### 网络复制流程图

server同步网络数据到客户端的流程，server发送数据到client的流程

![](https://pic2.zhimg.com/v2-251e6dc623ff9b433e2ca44d54472001_1440w.jpg)
**常用 Condition 一览**：

|枚举|含义|典型用途|
|---|---|---|
|COND_None|所有客户端都同步|通用状态（血量、位置）|
|COND_OwnerOnly|只同步给拥有者|背包、金币、私有信息|
|COND_SkipOwner|不同步给拥有者|本地玩家自己算过的数据|
|COND_SimulatedOnly|只同步给模拟端|别人看到的位置/朝向|
|COND_InitialOnly|只在初始化时同步一次|固定不变的配置|
|COND_Custom|自定义条件|复杂业务规则|
## 数据收发与游戏循环

1. 引擎启动时，首先在 FEngineLoop::Init中创建 GEngine 对象，调用 GEngine->Init 进行初始化，之后Start
2. 创建 GameInstance 对象并调用 InitializeStandalone 进行初始化, 创建WorldContext和临时DummyWorld
3. GEngine->Start 启动游戏，调用GameInstance->StartGameInstance()
4. 配置中读取地图名和参数调用
5. UEngine::Browse 加载默认的地图，客户端连接服务器，服务器启动监听
6. 网络数据包的收发和处理流程在整个游戏引擎的循环中所处的点是在下图的TickDispatch和TickFlush中

![](https://pic4.zhimg.com/v2-7502d14cc55753770385b74d681b187f_1440w.jpg)
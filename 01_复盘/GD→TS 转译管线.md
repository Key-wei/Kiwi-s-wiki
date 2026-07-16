godot到Three.js的过程可以总结为有四层转译

| 层   | Source                | 手段                                    | 自动化程度            |
| --- | --------------------- | ------------------------------------- | ---------------- |
| 数据层 | `.tres`               | `tres-parser.mjs` 解析 + 脚本抽取           | 半自动(解析全自动,抽取一次性) |
| 资源层 | `.gltf`+`.bin`+贴图     | `gltf-to-glb.mjs` 打包 + `inspect-*` 核对 | 半自动(逐文件手动调用)     |
| 逻辑层 | `.gd` 脚本              | 人工阅读 + TS 重写                          | 无自动化             |
| 表现层 | `.tscn` 场景 / CEF HTML | 人工阅读 + Three.js/DOM 重建                | 无自动化             |
## 逐层实际情况：
### 1.数据层
**`tools/tres-parser.mjs`(通用、可复用)**
以原版弓手 `human_ranger.tres` 为例，它大概长这样：
script = ExtResource("5_7jntr")
unit_id = &"human_ranger"
display_name = "弓手"
role = &"ranged"
cost = 110
max_health = 110.0
move_speed = 2.9
attack_range = 10.0
...
所以可以用Key-value拆成键值对
比如弓手最终会变成类似：
{

	unitId: "human_ranger",
	
	displayName: "弓手",
	
	maxHealth: 110,
	
	moveSpeed: 2.9,

	defaultAbilityId: "basic_ranged_bow",
	
}

### 2.资源层

| 步骤        | 做什么                                          | 对应工具/文件                |
| --------- | -------------------------------------------- | ---------------------- |
| 1. 从原版拿资源 | 在 TABS `assets/kaykit/` 找到 `Ranger.gltf` 三件套 | 人工                     |
| 2. 打包     | 合成 `Ranger.glb`                              | `gltf-to-glb.mjs`      |
| 3. 验货     | 确认有 mesh、skin、动画 clip                        | `inspect-glb.mjs`      |
| 4. 验骨架    | 确认和动画包 23/23 关节匹配                            | `inspect-skeleton.mjs` |
| 5. 登记     | 弓手 → Ranger.glb + 弓 + 各状态 clip 名             | `models.ts`（人工）        |
| 6. 摆放     | 浏览器加载、挂装备、绑动画                                | `ModelLoader.ts`（运行时）  |
主要分为三类资源
.gltf 描述文件
.bin 模型几何数据
.png 贴图
一个模型拆成 3 个文件

其中.gltf 又包含了模型和动作包，特效资源还包括.obj、.tga等格式

#### 第一步:
攥写一个脚本 gltf-to-glb.mjs 用来把这三个文件合并到一起成 .glb

#### 第二步:
再有两个脚本用来核对资产
- 有几个 mesh（网格）
- 有没有 skin（骨骼）
- 有哪些 animation clip 名字

打包好的 `.glb` 放到 `public/models/`，但游戏还不知道“弓手该用哪个模型、拿哪把弓、播哪个动画”。

这份清单在 `game/core/source/data/models.ts`，是人工维护的，不是自动生成：

| 映射表              | 作用            | 例子                              |
| ---------------- | ------------- | ------------------------------- |
| `UNIT_MODELS`    | 单位 → 角色模型     | `human_ranger` → `Ranger.glb`   |
| `UNIT_EQUIPMENT` | 单位 → 主手/副手装备  | 弓手副手 → `bow_withString.glb`     |
| `ANIM_PACK_URLS` | 要预加载哪些动画包     | `Rig_Medium_General.glb` 等 10 个 |
| `UNIT_CLIPS`     | 单位各状态播哪个 clip | 弓手攻击 → `Ranged_Bow_Release`     |
|                  |               |                                 |

装备旋转角度是从原版 `.tres` 的 `off_rotation_degrees = Vector3(0, 180, 0)` 抄过来的，比如弓手：

human_ranger: {

off: { url: EQUIPMENT_BASE + "bow_withString.glb", rotationDegrees: [0, 180, 0] },

},


##### .gd强绑定Godot API，没有工具能够把.gd转化成TS,所以所有逻辑只能重新参考原本的项目进行重写。但是这个过程可以使用AI辅助翻译GDScript和.tscn，但是无法做到100%复刻
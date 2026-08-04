---
title: Figma AI 设计 Prompt 包
type: design-asset
area: "[[人生成就墙]]"
created: 2026-06-04
tags: [figma, design, prompt, ai-tools, ui]
---
# Figma AI 设计 Prompt 包

> 用于喂给 Figma Make / v0 / Galileo AI / Magic Patterns / Uizard 等 AI 设计工具,生成「人生成就墙」v0.1 的视觉设计稿。
>
> **使用建议**: AI 设计工具对英文 prompt 支持更好,所以系统指令用英文写,中文内容(成就名、按钮文字)保留中文。

---

## 🎨 Part 1: Design System Spec (粘贴在任何 prompt 顶部)

```
DESIGN SYSTEM — LifeWall (地球Online RPG-style WeChat Mini-Program)

## Concept
A "Steam Profile Page meets MMO Achievement System for Chinese white-collar life."
Dark, gamified, with rarity-based color hierarchy. Mood: nostalgic gaming UI
fused with modern minimalism. Think: Steam achievement page × Pokémon Pokédex
× NetEase Cloud Music year-in-review report.

## Platform
WeChat Mini-Program. Frame size: 375×812 dp (or 750×1624 px @2x).
Top safe area: 44dp status bar + 44dp navigation bar = 88dp top inset.
Bottom safe area: 56dp tabBar + 34dp home indicator = 90dp bottom inset.

## Color Palette
- Background primary:   #0F1419  (deep midnight, base)
- Background secondary: #1A1F26  (card, elevated surface)
- Background tertiary:  #2C3E50  (modal overlay, dividers)
- Text primary:         #E8E8E8  (main copy)
- Text secondary:       #999999  (subtitle, meta)
- Text muted:           #5A6470  (locked items, disabled)
- Accent (brand):       #F39C12  (legendary gold, CTA, brand)
- Accent hover:         #E67E22  (pressed state)

## Rarity Color System (CRITICAL — drives 80% of visual hierarchy)
- Common (>50% unlock):   #999999  (gray border, plain)
- Elite (10–50%):         #4A90E2  (blue border, subtle glow)
- Epic (1–10%):           #9B59B6  (purple border, gradient inner)
- Legendary (<1%):        #F39C12  (orange border, gold particle effect)
- Hidden (egg achievements): #2C3E50  (black silhouette, "?" mark)

## Typography
Font family: PingFang SC (中文), SF Pro Display (English), system fallback.
- Display (角色卡 hero):    36px / Bold / -0.5px letter-spacing
- Heading 1 (page title):  24px / Semibold
- Heading 2 (category):    18px / Semibold
- Body (achievement name): 14px / Medium
- Caption (rate, meta):    11px / Regular
- Tabular numerals for percentages (47% / 0.8%)

## Spacing System (8pt grid)
4 / 8 / 12 / 16 / 20 / 24 / 32 / 48 / 64

## Border Radius
- Card:   12px
- Modal:  20px (top-rounded for bottom sheet)
- Button: 24px (pill)
- Achievement cell: 8px

## Iconography
v0.1 uses Emoji-as-icons (not custom SVG, to save design time).
Each achievement has one emoji (🎮 👶 🎓 💼 💞 ✈️ 🛠️ 💪 🏠 💰 🎭 etc).
Locked state: emoji desaturated to grayscale + 35% opacity.

## Animation Principles (for prototyping only, devs implement separately)
- Unlock animation: scale 0.8 → 1.05 → 1.0, 600ms cubic-bezier
- Level-up toast: full-screen flash + golden particles, 1.2s
- Page transition: slide-from-right, 240ms ease-out

## Voice & Tone (中文文案风格)
"地球Online" MMO slang. Examples:
- "主角登场" (Main Character Enters)
- "新人下副本" (Rookie Dungeon Run)
- "驾照猎人" (License Hunter)
- "35岁试炼" (Age 35 Trial)
NEVER serious or preachy. Always game-flavored.
```

---

## 🚀 Part 2: Master Prompt (给 v0 / Figma Make 一次性生成)

```
Design a WeChat mini-program called "地球Online" (LifeWall) — a "personal Steam
profile page" for Chinese white-collar professionals to track life achievements.

[PASTE THE FULL DESIGN SYSTEM SPEC FROM PART 1 ABOVE]

Generate the following 7 screens as a connected Figma file:

1. ENTRY SCREEN (welcome / scan-in landing)
2. STARTER PACK ANIMATION (8 main achievements auto-unlock with celebration)
3. CODEX MAIN PAGE (200 achievements grid — the heart of the app)
4. ACHIEVEMENT DETAIL MODAL (bottom sheet that opens on tap)
5. PROFILE PAGE (level, stats, share button)
6. SHARE CARD PREVIEW (the screenshotable life-RPG character card)
7. ONBOARDING BUBBLE GUIDE OVERLAY (3-4 step tooltips)

Aesthetic references:
- Steam personal profile page achievements section
- Pokémon Pokédex grid
- NetEase Cloud Music annual report (2024 wrapped style)
- Genshin Impact character menu (dark + gold)
- Honkai Star Rail UI (chinese gaming aesthetic)

Avoid: Material Design, generic SaaS dashboard, light mode, flat hipster style.

Make it feel like opening a treasure chest of your life.
```

---

## 📱 Part 3: Per-Screen Prompts (逐屏精细生成)

### Screen 1: Entry Screen (入口页)

```
Design a WeChat mini-program entry/welcome screen.

Layout (top to bottom):
- Logo/Wordmark "地球Online" centered, 60dp from top safe area, 36px Bold gold (#F39C12)
- Subtitle: "你的人生 RPG 存档" (Your Life RPG Save File), 14px gray (#999), 8dp below logo
- Hero illustration area (300dp tall): pixel-art style isometric scene of a tiny
  character standing in front of a giant achievement wall glowing in the dark
- Primary CTA button "登录开始游戏" (Login & Start Game), pill shape,
  full-width minus 32dp side margin, 56dp tall, gold gradient #F39C12 → #E67E22,
  black text 16px Semibold
- Below CTA: small text "首次进入将自动获得 8 个新手成就 🎁" (First entry
  auto-unlocks 8 starter achievements), 12px #999

Background: #0F1419 with subtle radial gradient toward center #1A1F26.
Add 6 floating particle dots (gold, 2-4px) scattered randomly at low opacity.

Bottom: small WeChat-style "由微信提供登录" badge.
```

### Screen 2: Starter Pack Animation (新手大礼包动画)

```
Design a celebratory unlock-animation screen — captured as a single keyframe
showing the climax of the animation.

State: 8 starter achievement cards arranged in 2 rows × 4 columns, centered
in screen. Each card is 72×72dp with:
- Emoji (32px) centered top
- Achievement name (12px white Medium) below
- Common rarity gray border
- ALL 8 cards in "just unlocked" state: gold glow halo, scale 1.08, white-to-gold
  gradient ring

Top: large headline "你已抵达地球Online" (You have arrived at Earth Online),
24px white Bold. Below: "8 个主线成就已自动点亮" (8 main achievements auto-lit),
14px gold #F39C12.

Background: deep #0F1419 with golden radial burst from center.
Confetti particles in gold, purple, blue scattered around (15-20 pieces).

Bottom CTA: "进入图鉴" (Enter Codex), pill, full-width, gold.

Sample 8 achievement names (1 per card):
🎮 主角登场  /  👶 第一声啼哭  /  🚶 学会走路  /  🗣️ 学会说话
🎓 义务教育毕业  /  🔓 18岁解封  /  💰 第一次自己买东西  /  🚲 学会骑自行车
```

### Screen 3: Codex Main Page (图鉴主页 — 核心)

```
Design the main codex (achievement library) page — the most important screen,
where users will spend 80% of their time.

Header (top, 88dp tall, sticky):
- Left: back arrow + page title "地球Online 图鉴" 18px white Semibold
- Right: progress badge "47 / 200" 16px gold tabular numerals
- Below title, thin progress bar: gold filled, gray track, 4dp tall

Filter chips row (horizontally scrollable, 44dp tall, sticky below header):
"全部 200" (Active, gold pill) / "主线 8/8" / "成长 12/28" / "职业 5/28" /
"感情 3/22" / "旅行 2/22" / "技能 4/28" / "健康 1/18" / "生活 5/22" /
"财务 1/14" / "彩蛋 ?/10"

Main grid (4 columns, 8dp gap, 16dp side padding):
Each cell is square (~80×80dp), shows:
- Top: emoji 28px centered
- Middle: achievement name 11px Medium, 1-2 lines, ellipsis
- Bottom right corner: rarity dot indicator (4dp circle)
- Border: 2dp solid in rarity color
- LOCKED state: 35% opacity, grayscale filter, "?" replaces name if hidden type
- UNLOCKED state: full color, subtle inner glow in rarity color

Sample cells (mix of locked/unlocked, all rarities):
Row 1 (Main, all unlocked, gray):
  🎮 主角登场 ✓  /  👶 第一声啼哭 ✓  /  🚶 学会走路 ✓  /  🗣️ 学会说话 ✓

Row 2 (Growth, mix):
  🎯 难道我是天才? (blue, unlocked)  /  📚 学霸装备 (purple, locked)
  🎓 大学毕业典礼 (blue, unlocked)  /  🥇 博士传说 (orange, locked)

Row 3 (Career):
  💼 新人下副本 (gray, unlocked)  /  🏢 大厂入职 (purple, locked)
  📜 考公上岸 (orange, locked)  /  🚪 逃离副本 (purple, locked)

Row 4 (Travel):
  🗺️ 国内地图开荒 (blue, unlocked)  /  ✈️ 走出新手村 (blue, locked)
  🌌 极光猎人 (orange, locked)  /  🏔️ 登顶玩家 (purple, locked)

Bottom: WeChat tabBar (56dp), 2 tabs:
"图鉴" (active, gold) | "我" (gray)

Background: #0F1419
Header background: #1A1F26 with 1dp #2C3E50 bottom border
```

### Screen 4: Achievement Detail Modal (成就详情弹窗)

```
Design a bottom-sheet modal that appears when user taps an achievement cell.

Modal style: rounded top corners 20dp, slides up from bottom, height ~60% of
screen, dark semi-transparent backdrop behind (#000 60% opacity).

Modal content (top to bottom, 24dp side padding):
- Drag handle bar (centered, 36×4dp, #5A6470, top 8dp)
- Hero section (centered): emoji 64px in a 100×100 circle with rarity-colored
  glow ring around it
- Achievement name "驾照猎人" 24px white Semibold, centered
- Rarity badge pill: "🔵 精英 · 54% 玩家拥有" 12px elite blue (#4A90E2),
  centered below name
- Description box (#1A1F26 bg, 12dp radius, 16dp padding):
  "通关驾驶考试副本,解锁机动车驾驶权限"
  14px #E8E8E8

UNLOCKED STATE shows:
- "解锁于 2024-08-15" 12px #999
- User note input area (multiline, placeholder "记录一下当时的故事..."),
  #2C3E50 bg, 12dp radius, 80dp tall
- "添加照片" button (optional photo upload), dashed border, gray, 60dp tall
- Bottom: secondary button "取消解锁" (red text, ghost button)

LOCKED STATE shows:
- Tap-to-unlock CTA: full-width pill button "✅ 我已达成此成就" (I've achieved
  this), gold gradient, 56dp tall
- Below: smaller text "勾选时请确保真实达成 · 诚信声明"
  10px #5A6470 centered
```

### Screen 5: Profile Page (个人主页)

```
Design the user profile page — the "Steam profile" hero view.

Header (200dp tall, gradient bg from #1A1F26 to #0F1419):
- Avatar (80×80dp circle, top-center, gold border 3dp)
- Display name "玩家_kw" 20px white Semibold below avatar
- Level badge: "Lv.5 资深玩家" pill, gold bg #F39C12, black text 14px,
  rounded 12dp, below name
- Total achievements: "已点亮 47 / 200 成就" 13px #999

Stats grid (3 columns, below header, 16dp side margin, 8dp gap):
Each stat card (#1A1F26 bg, 12dp radius, 80dp tall, centered text):
  Card 1: "⏱️ 5 天" / "已加入地球" 11px #999
  Card 2: "🏆 47" / "已解锁成就" 11px #999
  Card 3: "✨ 1" / "传说级成就" 11px gold

Category breakdown (full width, 16dp side margin):
For each of 9 categories, show a horizontal row:
[icon] 类别名 — progress bar (rarity-of-highest tier color) — "X / Y"
e.g.:
🎯 主线        ████████████ 8/8
🎓 成长        ████████░░░░ 12/28
💼 职业        ████░░░░░░░░ 5/28

CTA section (sticky bottom, above tabBar):
- Primary button "🪄 生成我的人生卡片" full-width pill, 56dp tall, gold gradient
- IF user has < 5 unlocks: button DISABLED state, gray, with text below:
  "再勾选 X 个成就解锁分享卡 ✨" 12px #999

WeChat tabBar bottom: "图鉴" (gray) | "我" (active, gold)
```

### Screen 6: Share Card Preview (分享卡片)

```
Design the screenshotable "life RPG character card" that users share to friends.

Aspect: 750×1334px (3:4 portrait, optimized for WeChat moments).

Layout (top to bottom):
- Header bar: "地球Online · 玩家档案" 14px gold, top 24dp
- Avatar circle (120dp) centered + gold ring + small "Lv.5" badge
- Display name 28px white Bold below avatar
- Tagline "已征服地球的 47 个副本" 14px gold #F39C12

- Center showcase grid (3×3 = 9 cells):
  Display the 9 most rare unlocked achievements (sorted by rarity).
  Each cell larger (~120×120dp), with full color rarity border + name visible.
  Sample 9 achievements (assume user has unlocked these):
  🌌 极光猎人 (orange) / 🥇 博士传说 (orange) / 📚 百本阅读 (orange)
  🏢 大厂入职 (purple) / 🎯 难道我是天才? (blue) / ✈️ 走出新手村 (blue)
  🚗 驾照猎人 (blue) / 💼 新人下副本 (gray) / 🎮 主角登场 (gray)

- Stat strip below grid:
  "⏱️ 入服 5 天 · 🏆 47 成就 · ✨ 3 传说级"

- Bottom area:
  - QR code (180×180px) for the mini-program — labeled
    "扫码查看你的地球Online 进度" 12px #999
  - Tiny watermark bottom-right: "@地球Online · 2026"

Background: dark gradient #0F1419 → #1A1F26 with subtle starfield pattern
(small white dots at 30% opacity, randomly placed).
Add 2-3 large bokeh-blur orbs in gold/purple/blue at low opacity for depth.
```

### Screen 7: Onboarding Bubble Guide (新手气泡引导)

```
Design 3 onboarding tooltip overlays, shown sequentially on top of the codex
page after the starter pack animation.

Backdrop: codex page dimmed to 30% opacity behind, with a "highlight cutout"
spotlight on the relevant UI element (radial bright spot around target).

Tooltip style: chat-bubble shape, white-ish #1A1F26 bg with gold #F39C12 border
2dp, arrow tail pointing to target. Padding 16dp, max-width 280dp,
border-radius 16dp. Drop shadow.

Sequence:

Step 1 (target: codex grid):
"👇 向下滑动,浏览全部 200 个人生成就"
[skip] [next →] (right-bottom)
Step indicator: "1 / 3" top-right

Step 2 (target: an unlocked achievement cell):
"💡 看到你已经达成的成就? 点一下勾选它"
[skip] [next →]
"2 / 3"

Step 3 (target: profile tab in tabBar):
"🎴 勾选 5 个以上,即可解锁'人生角色卡'分享朋友圈!"
[skip] [开始探索 ✨] (gold CTA)
"3 / 3"

Visual notes:
- Bubble tail pointing toward UI element (e.g., arrow pointing down for grid,
  arrow pointing up for tabBar)
- Smooth dim animation: 200ms fade-in
- "skip" link smaller and #999 (de-emphasized)
- "next" CTA gold and prominent
```

---

## 🧩 Part 4: Component Library Prompts (组件级 prompt)

### Component A: Achievement Cell

```
Design a reusable Achievement Cell component for the codex grid.

Specs:
- Square 80×80dp (or scalable to 72/96/120 variants)
- Border-radius 8dp
- 2dp solid border (color = rarity color)
- BG: #1A1F26
- Inner padding 8dp
- Layout: emoji 28px top-center / name 11px center / rate dot bottom-right

Provide 5 rarity variants + 2 state variants (locked/unlocked) = 10 total.

States to design:
1. Common · Locked    (gray border, 35% opacity, grayscale)
2. Common · Unlocked  (gray border, full color)
3. Elite · Locked     (faded blue border, dimmed)
4. Elite · Unlocked   (blue border, subtle blue inner glow)
5. Epic · Locked
6. Epic · Unlocked    (purple border + soft purple glow)
7. Legendary · Locked
8. Legendary · Unlocked (gold border + animated gold particle hint + "✨" sparkle)
9. Hidden · Locked    (black silhouette, "???" instead of name, "?" emoji)
10. Hidden · Unlocked (revealed, special purple-black gradient border)
```

### Component B: Rarity Badge / Pill

```
Design a small inline rarity badge used in detail modals and lists.

Format: "● 精英 · 54% 玩家拥有"
Pill shape, 24dp tall, 12px text, 8dp horizontal padding, rounded 12dp.

5 variants:
1. ● 普通 · 78% 玩家拥有     bg: #2C3E50, text: #999999, dot: #999999
2. ● 精英 · 54% 玩家拥有     bg: rgba(74,144,226,0.15), text: #4A90E2, dot: #4A90E2
3. ● 史诗 · 8% 玩家拥有      bg: rgba(155,89,182,0.15), text: #9B59B6, dot: #9B59B6
4. ● 传说 · 0.8% 玩家拥有    bg: rgba(243,156,18,0.15), text: #F39C12, dot: #F39C12
5. ⚫ 隐藏成就               bg: #2C3E50, text: #5A6470, dot: #5A6470
```

### Component C: Progress Bar (Category)

```
Design a horizontal category progress bar used in the profile page.

Layout: [icon 16dp] [name 13px] [progress bar flex-grow] [count 12px]
Height: 36dp row. Bar height: 6dp. Gap: 12dp.

Bar style:
- Track: #2C3E50 bg, 6dp tall, 3dp radius
- Fill: gradient based on highest rarity unlocked in that category
  (if user has any legendary in this category, fill is gold; else purple/blue/gray)
- Animation: fill grows on page load, 800ms ease-out

Sample rows:
🎯 主线        [████████████] 8/8
🎓 成长        [████████░░░░] 12/28
💼 职业        [████░░░░░░░░] 5/28
✈️ 旅行        [██░░░░░░░░░░] 2/22
🛠️ 技能        [████░░░░░░░░] 4/28
```

---

## 🎬 Part 5: Mood Board / Visual References

把以下关键词扔进 Pinterest / Dribbble / Behance 搜素材,辅助 AI 工具理解风格:

### 🎯 Primary references (照着抄)
- `Steam profile achievements page UI`
- `Pokemon Pokedex modern redesign`
- `网易云年度报告 2024 ui`
- `Genshin Impact character menu UI`
- `Honkai Star Rail UI dark gold`

### 🎨 Visual mood
- `dark mode gaming UI 2025`
- `MMO achievement system mockup`
- `pixel art meets minimalism`
- `chinese app gamification ui`

### 🎬 Animation references
- `Duolingo level up animation`
- `Steam achievement unlock`
- `Apple fitness rings animation`

### ❌ AVOID (avoid prompts to AI)
- Generic Material Design
- Light mode SaaS dashboard
- Notion / Linear style minimalism (too sterile for our gamified concept)
- Hipster gradient mesh (too 2022)

---

## 🛠️ Part 6: AI 工具特化版 Prompt

### For Figma Make (Figma 官方 AI)

```
Create a WeChat mini-program design system + 7 connected screens for "地球Online"
— a personal life-achievement codex inspired by Steam profile pages and Pokemon
Pokedex. Dark theme (#0F1419), with rarity-based color hierarchy
(gray/blue/purple/orange/black). Chinese-language content. Mobile portrait
375×812dp. Generate as auto-layout components with proper variants for each
rarity × locked/unlocked state.

[paste Design System Spec from Part 1]
[paste Screen prompts from Part 3 in order]
```

### For v0 by Vercel (生成 React/Tailwind 代码)

```
Generate a Next.js + Tailwind component library for a WeChat-style achievement
tracker app called "地球Online" (Earth Online). Build:
1. <AchievementCell> component with rarity prop (common|elite|epic|legendary|hidden)
   and unlocked boolean
2. <CodexGrid> page with 200 cells in 4-column grid + filter chips
3. <AchievementModal> bottom-sheet with locked/unlocked variants
4. <ProfilePage> with stats + share card CTA
5. <ShareCard> screenshotable component (3:4 aspect)

Styling:
- Tailwind dark mode (always)
- Custom colors: rarity-common, rarity-elite, rarity-epic, rarity-legendary, rarity-hidden
- Font: PingFang SC fallback
- All Chinese sample copy (use names from achievement library)

Sample data: 20 achievements across all 5 rarities with Chinese names.
```

### For Galileo AI / Magic Patterns

```
Design a "Steam profile page for real life" — a Chinese WeChat mini-program
that turns life milestones into a Pokedex-style achievement codex. Dark gaming
aesthetic, gold + purple + blue rarity hierarchy. Generate the codex grid screen
showing 16 achievement cells (mix of locked/unlocked, all rarities) with names
in Chinese like "主角登场", "驾照猎人", "大厂入职", "极光猎人", "婚礼CG解锁".

Header shows "47 / 200" progress. Bottom WeChat tabBar.
```

### For Uizard / Banani

```
Mobile UI for "Earth Online" life achievement tracker. Dark theme, Chinese
text, RPG game-style. 7 screens: welcome, starter-pack-celebration, codex-grid,
achievement-detail-modal, profile, share-card, onboarding-tooltips.
Reference: Steam achievement page meets NetEase Cloud annual report.
```

---

## ✅ Part 7: Quality Checklist (出图后自检)

设计稿出来后,逐项 check:

- [ ] 5 个稀有度颜色完全符合规范(灰/蓝/紫/橙/黑)
- [ ] 深色背景 #0F1419,不是其他颜色
- [ ] 中文文案不要被英文替换("解锁"不要变成"Unlock")
- [ ] 所有 emoji 显示正确(不是空白方框 □)
- [ ] 锁定态和解锁态有明显视觉差异(灰度 + 透明度)
- [ ] 顶部留出 88dp 安全区(微信状态栏 + 导航栏)
- [ ] 底部留出 90dp 安全区(tabBar + 全面屏 home indicator)
- [ ] 数字使用 tabular-nums(等宽数字),"47 / 200" 对齐
- [ ] 按钮至少 44dp 高(微信触控规范)
- [ ] 字体大小 ≥ 11px,不要过小
- [ ] 分享卡片是 3:4 比例,不是 16:9 或正方形
- [ ] 主色调橙色 #F39C12 没有被替换成其他金色

---

## 🎯 推荐使用流程

1. **先用 v0 生成代码版**(免费、快速、可改): 把 Part 6 的 v0 prompt 喂进去,拿到 React 组件 → 截图当 reference
2. **再用 Figma Make 精修视觉**(出 Figma 文件): 把 Part 2 Master Prompt + Part 3 逐屏 prompt 喂进去
3. **拿出图后**: 用 Part 7 checklist 自检,有问题让 AI 重新生成或人工调
4. **导出微信小程序素材**: 关键图标/底图导出 PNG @2x @3x

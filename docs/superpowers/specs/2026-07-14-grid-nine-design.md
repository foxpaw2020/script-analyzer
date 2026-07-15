# 九宫格剧情参考图（grid_nine_gpt）

## 概述

在场景拆解中，用九宫格剧情参考图（`grid_nine_gpt`）替换俯视图（`topdown_gpt`）。九宫格以 3×3 网格展示场景的关键剧情时刻，帮助 Seedance 理解角色站位和剧情推进。

## 输出格式

每个场景输出一个 `grid_nine_gpt`：

```json
{
  "assets": "@角色A。@角色B。@场景名",
  "cells": [
    {"pos": "1-1", "moment": "开场对峙", "action": "..."},
    {"pos": "1-2", "moment": "情绪升级", "action": "..."},
    ...
    {"pos": "3-3", "moment": "结局定格", "action": "..."}
  ],
  "grid_prompt": "九宫格剧情板，{场景名}，正常拍摄视角按剧情时序排列：...（9格完整描述），电影级实拍质感..."
}
```

- `assets`：本场景九宫格涉及的全部 @资产，与 cells 中的 @标记一一对应
- `cells`：9 个格子（1-1 左上 → 3-3 右下），按时间顺序排列
- `grid_prompt`：组装好的完整提示词，喂给 Image-2 出图

## 生成时机

分镜拆解完成后独立运行，属于场景提取的第四轮。

## 核心约束

1. **角色站位必须与分镜提示词一致** — cells 中的人物位置（左/右/前/后）要对应分镜 action 中的空间锚点
2. **9 格按剧情时序排列** — 1-1 是场景开场、3-3 是场景收尾
3. **正常拍摄视角** — 不使用俯视/鸟瞰，使用平视/中近景
4. **assets 与 cells 中 @标记一一对应**

## 实现范围

- 修改 `extractors/scenes.py`：新增 `GRID_NINE_SYSTEM` 和 `build_grid_nine_prompt`、`parse_grid_nine_result`
- 修改 `app.py`：在多面板生成后新增九宫格步骤，输出写入 HTML 报告
- `topdown_gpt` 保留不删除，仅不再新增生成逻辑

## 不在范围内

- 不修改 scenes.py 的 DETAIL_SYSTEM
- 不修改 shots.py
- 不修改 reports/word_report.py

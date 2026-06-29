# Hollywood Shot Sequences Knowledge Base — Design Spec

**Date:** 2026-06-29
**Status:** Draft
**Project:** 剧本拆解大师 v2.49 — `Storyboard_Breakdown_Skills_v4.1.json`

---

## 1. 目标

在现有 `signature_moves`（招牌运镜，命名+一句话说明）基础上，新增 `hollywood_shot_sequences` 字段，提供**带时间分段+完整 action 表达**的好莱坞大师级运镜范例。LLM 在编写分镜动作链时，可根据剧情类型自动匹配并参考对应范例的 segment 结构，生成符合 Seedance 2.0 理解能力的复合运镜描述。

---

## 2. 数据模型

### 2.1 字段位置

`knowledge_base/Storyboard_Breakdown_Skills_v4.1.json` 中新增顶层字段：

```json
{
  "meta": { ... },
  "rules": { ... },
  "shot_density": { ... },
  "camera_terms": { ... },
  "signature_moves": { ... },
  "hollywood_shot_sequences": { ... },  // ← 新增
  "extraction_dimensions": [ ... ],
  ...
}
```

### 2.2 分类体系（8 类）

| 分类 key | 中文名 | 覆盖场景 |
|---|---|---|
| `chase_action` | 追逐与动作 | 奔跑追击、车战、打斗、爆炸逃生 |
| `confrontation_dialogue` | 对峙与对话 | 双人/多人对峙、审讯、谈判、争吵 |
| `suspense_thriller` | 悬疑与惊悚 | 恐怖揭示、逐步逼近、偷窥视角、jump scare |
| `emotion_intimacy` | 情感与亲密 | 对视、告白、接吻、别离、重逢 |
| `epic_warfare` | 史诗与战争 | 大场面、鸟瞰战场、子弹时间、群像 |
| `sci_fi_supernatural` | 科幻与超现实 | 时间冻结、维度分裂、超能力、微观穿越 |
| `time_manipulation` | 时间操控 | 慢镜头、快放、倒放、冻结恢复 |
| `subjective_pov` | 主观视角 | POV行走、眩晕、醉酒、记忆闪切 |

### 2.3 单条数据结构

```json
{
  "name": "动态手持侧后方跟踪镜头",
  "description": "手持摄影机从主体侧后方以不稳定晃动方式跟踪移动，强化紧迫感和代入感",
  "total_duration": 15.0,
  "segments": [
    {
      "time_range": "0.0s-3.0s",
      "action": "节奏急速铺垫，手持镜头从侧后方摇晃跟踪，@[角色]在[环境]中奔跑..."
    },
    {
      "time_range": "3.0s-15.0s",
      "action": "持续高速追击，手持镜头晃动幅度逐渐加剧..."
    }
  ]
}
```

**字段说明：**
- `name` — 中文运镜命名
- `description` — 一句话技法说明，帮助 LLM 理解何时使用
- `total_duration` — 总时长，≤ 15s
- `segments[]` — 2-4 个分段，每段 `time_range` 格式 `"X.Xs-Y.Ys"`，`action` 为完整中文叙事句（含节奏定位 + 景别运镜 + 画面内容 + @标记），≥ 35 字

### 2.4 每个分类 2-4 条范例（共约 20-30 条）

---

## 3. 格式化与注入

### 3.1 `_format_json_kb()` 扩展

在 `extractors/base.py` 的 `_format_json_kb()` 方法中，`hollywood_shot_sequences` 段落与其他字段同级处理：

```
## 好莱坞大师运镜范例

### 追逐与动作
- 动态手持侧后方跟踪镜头: 手持摄影机从主体侧后方以不稳定晃动方式跟踪移动...
  0.0s-3.0s: 节奏急速铺垫，手持镜头从侧后方摇晃跟踪...
  3.0s-15.0s: 持续高速追击，手持镜头晃动幅度逐渐加剧...

### 对峙与对话
...
```

### 3.2 打入 prompt 位置

在现有最终 prompt 的知识区中，`hollywood_shot_sequences` 位于 `camera_terms` 和 `signature_moves` 之后，`extraction_dimensions` 之前。

---

## 4. 现有 `signature_moves` 处理

**保留不删。** `signature_moves` 作为简单快速的运镜参考，`hollywood_shot_sequences` 作为带时间分段的完整范例并排存在，LLM 根据场景复杂度自行选择参考深度。

---

## 5. 用例流程

1. 用户上传剧本 → LLM 分析场景类型（追逐/对峙/悬疑/情感...）
2. LLM 查阅 `hollywood_shot_sequences` 中对应分类的范例
3. LLM 参考范例的 segment 结构（时间分段 + Seedance 化表达），为当前分镜生成动作链
4. 生成的 action 自然融入节奏定位 + 景别运镜 + 画面内容，Seedance 可直接理解

---

## 6. 影响范围

| 文件 | 改动 |
|---|---|
| `knowledge_base/Storyboard_Breakdown_Skills_v4.1.json` | 新增 `hollywood_shot_sequences` 字段 |
| `extractors/base.py` | `_format_json_kb()` 新增 hss 段落的格式化逻辑 |
| 其他文件 | 无改动 |

---

## 7. 风险与约束

- **风险**：范例过多可能导致 prompt 过长，LLM 上下文窗口压力增大
- **约束**：每条范例 segment 的 action 必须使用 `@[角色]`、`@[环境]` 等占位符，禁止写入具体人名/场景名，避免 LLM 照抄
- **约束**：所有 segment action 必须使用纯中文、Seedance 友好语言、已融入了景别运镜的口语化表达

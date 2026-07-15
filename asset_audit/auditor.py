"""资产核对核心逻辑 - 统一通过 call_ai 调用模型提取人物/道具/场景"""
import json, re, logging, sys, os
logger = logging.getLogger("asset_audit")

# 确保可以导入项目根目录的 services
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)
from services.ai_service import call_ai
from extractors.base import BaseExtractor

EXTRACT_SYSTEM = """你是影视资产分析师。从剧本中提取人物、道具、场景三类资产。

★ 强制规则（违反将导致输出无效）：
1. name_cn 必须是中文，永远不能出现英文单词
2. 如果剧本角色是英文名（如Harrison），name_cn 必须音译为中文（如哈里森），name_en 放英文原名
3. 场景名同理：name_cn 中文（如废弃仓库），name_en 英文（如Abandoned Warehouse）
4. 道具 name_cn 仅中文
5. 每个角色必须填 costume（服装描述），不可留空
6. 只输出JSON，不要任何解释文字

输出格式：
{
  "characters": [
    {"name_cn": "中文译名", "name_en": "英文原名或拼音", "costume": "角色服装"}
  ],
  "props": [
    {"name_cn": "道具中文名", "usage": "道具使用情境"}
  ],
  "scenes": [
    {"name_cn": "场景中文名", "name_en": "场景英文名", "synopsis": "场景内发生的事"}
  ]
}

音译示例：Harrison→哈里森、Lottie→洛蒂、Kidd→基德、Cronus→克洛诺斯、Ares→阿瑞斯"""


def extract_assets(script_text, api_config=None):
    """传入剧本全文和 API 配置，返回资产字典 {characters, props, scenes}
    
    api_config 格式与 call_ai 一致：
    { provider, api_key, model, base_url, temperature, max_tokens, ... }
    """
    if api_config is None:
        api_config = {
            "provider": "ollama",
            "model": "lfm2:latest",
            "base_url": "http://localhost:11434",
            "temperature": "0.3",
            "max_tokens": "8192"
        }

    user_prompt = f"请分析以下剧本，提取所有人物、道具、场景：\n\n{script_text[:12000]}"  # 截断保护

    try:
        raw = call_ai(EXTRACT_SYSTEM, user_prompt, api_config)
        content = raw.strip()

        # 提取 JSON
        if content.startswith("```"):
            content = re.sub(r'^```\w*\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
        js = content.find('{')
        je = content.rfind('}')
        if js != -1 and je != -1:
            content = content[js:je + 1]

        result = BaseExtractor._safe_json_parse_with_fallback(raw)
        if result is None or not isinstance(result, dict):
            raise ValueError(f"无法解析AI返回: {content[:300]}")
        return {
            "characters": result.get("characters", []),
            "props": result.get("props", []),
            "scenes": result.get("scenes", [])
        }
    except Exception as e:
        logger.error("资产提取失败: %s", str(e))
        return {"characters": [], "props": [], "scenes": [], "error": str(e)}


def merge_assets(all_episode_assets):
    """合并所有集的资产，去重"""
    seen_chars = set()
    seen_props = set()
    seen_scenes = set()

    merged_chars = []
    merged_props = []
    merged_scenes = []

    for ep_idx, assets in enumerate(all_episode_assets):
        for c in assets.get("characters", []):
            key = c.get("name_cn", "")
            if key and key not in seen_chars:
                seen_chars.add(key)
                merged_chars.append({**c, "first_episode": ep_idx + 1})

        for p in assets.get("props", []):
            key = p.get("name_cn", "")
            if key and key not in seen_props:
                seen_props.add(key)
                merged_props.append({**p, "first_episode": ep_idx + 1})

        for s in assets.get("scenes", []):
            key = s.get("name_cn", "")
            if key and key not in seen_scenes:
                seen_scenes.add(key)
                merged_scenes.append({**s, "first_episode": ep_idx + 1})

    return {
        "characters": merged_chars,
        "props": merged_props,
        "scenes": merged_scenes
    }

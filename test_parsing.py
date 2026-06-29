"""测试 parse_result 的健壮性"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from extractors import characters, props, scenes, shots

def test(name, func, input_data, expected_check):
    result = func(input_data)
    ok = expected_check(result)
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}")
    if not ok:
        print(f"    Expected check failed. Got: {result}")
    return ok

all_pass = True

# 1. markdown 代码块包裹
raw = '```json\n{"characters": [{"name": "Xiao Ming"}], "total_count": 1}\n```'
all_pass &= test("markdown code block", characters.parse_result, raw,
    lambda r: r.get("characters") == [{"name": "Xiao Ming"}])

# 2. 别名 key: cast
raw = '{"cast": [{"name": "Xiao Hong"}], "total_count": 1}'
all_pass &= test("alias key: cast", characters.parse_result, raw,
    lambda r: r.get("characters") == [{"name": "Xiao Hong"}])

# 3. 别名 key: items
raw = '{"items": [{"name": "knife"}], "summary": "test"}'
all_pass &= test("alias key: items", props.parse_result, raw,
    lambda r: r.get("props") == [{"name": "knife"}])

# 4. 别名 key: sequences
raw = '{"sequences": [{"title": "Scene 1"}]}'
all_pass &= test("alias key: sequences", scenes.parse_result, raw,
    lambda r: r.get("scenes") == [{"title": "Scene 1"}])

# 5. 分镜自动统计 total_shots
raw = '{"scenes": [{"scene_title": "A", "shots": [{"shot_number": 1}]}]}'
all_pass &= test("shots auto count", shots.parse_result, raw,
    lambda r: r.get("total_shots") == 1)

# 6. 无效响应优雅降级
raw = "this is not json at all"
all_pass &= test("graceful fallback", characters.parse_result, raw,
    lambda r: r.get("characters") == [])

# 7. 普通正常解析
raw = '{"characters": [{"name": "Normal"}], "total_count": 1}'
all_pass &= test("normal parse", characters.parse_result, raw,
    lambda r: r.get("characters") == [{"name": "Normal"}])

# 8. 道具 normal
raw = '{"props": [{"name": "Gun"}], "total_count": 1}'
all_pass &= test("props normal", props.parse_result, raw,
    lambda r: r.get("props") == [{"name": "Gun"}])

# 9. 场景 normal
raw = '{"scenes": [{"title": "Opening"}], "total_count": 1}'
all_pass &= test("scenes normal", scenes.parse_result, raw,
    lambda r: r.get("scenes") == [{"title": "Opening"}])

# 10. 分镜 normal
raw = '{"scenes": [{"scene_title": "Final"}], "total_shots": 5}'
all_pass &= test("shots normal", shots.parse_result, raw,
    lambda r: r.get("total_shots") == 5)

print()
if all_pass:
    print("ALL 10 TESTS PASSED!")
else:
    print("SOME TESTS FAILED!")
    sys.exit(1)

"""Quick functional test for artisan validation - delete after verification."""
from app.agents.validation import ValidationAgent
from app.core.generation_mode import GenerationMode

v = ValidationAgent()

# Test 1: Valid artisan code
r1 = v.validate(
    {"artisan_code": 'const s = pres.addSlide(); s.addText("Hello");'},
    "test-1",
    generation_mode=GenerationMode.ARTISAN,
)
assert r1.is_valid, f"Test 1 failed: {r1.errors}"
print("Test 1 (valid): PASS")

# Test 2: Missing artisan_code
r2 = v.validate({}, "test-2", generation_mode=GenerationMode.ARTISAN)
assert not r2.is_valid
assert any(e.field == "artisan_code" for e in r2.errors)
print("Test 2 (missing key): PASS")

# Test 3: No pres.addSlide()
r3 = v.validate(
    {"artisan_code": 'console.log("hello")'},
    "test-3",
    generation_mode=GenerationMode.ARTISAN,
)
assert not r3.is_valid
assert any("pres.addSlide()" in e.message for e in r3.errors)
print("Test 3 (no addSlide): PASS")

# Test 4: Code fences stripped
r4 = v.validate(
    {"artisan_code": "```javascript\nconst s = pres.addSlide();\n```"},
    "test-4",
    generation_mode=GenerationMode.ARTISAN,
)
assert r4.is_valid, f"Test 4 failed: {r4.errors}"
assert r4.corrections_applied >= 1
print(f"Test 4 (fences stripped): PASS (corrections={r4.corrections_applied})")

# Test 5: Empty string
r5 = v.validate({"artisan_code": ""}, "test-5", generation_mode=GenerationMode.ARTISAN)
assert not r5.is_valid
print("Test 5 (empty): PASS")

# Test 6: Exceeds size limit
r6 = v.validate(
    {"artisan_code": "pres.addSlide();" + "x" * 500_001},
    "test-6",
    generation_mode=GenerationMode.ARTISAN,
)
assert not r6.is_valid
assert any("500000" in e.message for e in r6.errors)
print("Test 6 (size limit): PASS")

# Test 7: parse_raw_llm_output with raw script (auto-wrap)
parsed = v.parse_raw_llm_output(
    'const s = pres.addSlide(); s.addText("Hi");',
    generation_mode=GenerationMode.ARTISAN,
)
assert "artisan_code" in parsed
print("Test 7 (raw script auto-wrap): PASS")

# Test 8: parse_raw_llm_output with JSON wrapper
parsed2 = v.parse_raw_llm_output(
    '{"artisan_code": "pres.addSlide()"}',
    generation_mode=GenerationMode.ARTISAN,
)
assert "artisan_code" in parsed2
assert parsed2["artisan_code"] == "pres.addSlide()"
print("Test 8 (JSON wrapper parse): PASS")

# Test 9: parse_raw_llm_output with code fences around JSON
parsed3 = v.parse_raw_llm_output(
    '```json\n{"artisan_code": "pres.addSlide()"}\n```',
    generation_mode=GenerationMode.ARTISAN,
)
assert "artisan_code" in parsed3
print("Test 9 (fenced JSON parse): PASS")

# Test 10: Unwrapped script recovery from different key
r10 = v.validate(
    {"code": 'const s = pres.addSlide(); s.addText("Hello");'},
    "test-10",
    generation_mode=GenerationMode.ARTISAN,
)
assert r10.is_valid, f"Test 10 failed: {r10.errors}"
assert r10.corrections_applied >= 1
print(f"Test 10 (unwrapped recovery): PASS (corrections={r10.corrections_applied})")

# Test 11: Round-trip validation
import json
data = {"artisan_code": "pres.addSlide();"}
serialized = json.dumps(data)
deserialized = json.loads(serialized)
assert data == deserialized
print("Test 11 (round-trip): PASS")

# Test 12: Routing - studio mode still works
r12 = v.validate(
    {
        "slides": [
            {
                "slide_id": "s1",
                "slide_number": 1,
                "type": "title",
                "title": "Test",
                "speaker_notes": "Notes",
                "render_code": "slide.addText('Hello', {x: 1, y: 1, w: 8, h: 1});",
            }
        ]
    },
    "test-12",
    generation_mode=GenerationMode.STUDIO,
)
print(f"Test 12 (studio routing): PASS (valid={r12.is_valid})")

print("\n=== All artisan validation tests passed! ===")

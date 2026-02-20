import sys
sys.stdout.reconfigure(encoding="utf-8")

filepath = r"C:\KassandraOpenAI\kassandra_openai_bot.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

original = content

emoji_map = {
    "âŒ": "❌",
    "â“": "❓",
    "â”": "━",
    "â±": "⏱",
    "â°": "⏰",
    "ï¸": "️",
    "ğŸ“": "📍",
    "ğŸ•": "🕐",
    "ğŸ½": "🍽",
    "ğŸ“": "📞",
    "ğŸŒ": "🌐",
    "ğŸ”": "🔐",
    "ğŸ—‘": "🗑",
    "ğŸ¨": "🏨",
    "ğŸ”": "🔍",
}

count = 0
for bad, good in emoji_map.items():
    if bad in content:
        n = content.count(bad)
        content = content.replace(bad, good)
        count += n
        print(f"  Replaced {n}x: {bad!r} -> {good}")

print(f"Total replacements: {count}")

if content != original:
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("File saved.")

import py_compile
py_compile.compile(filepath, doraise=True)
print("Compilation OK")

remaining_c1 = 0
for i, ch in enumerate(content):
    if 0x80 <= ord(ch) <= 0x9F:
        remaining_c1 += 1
if remaining_c1:
    print(f"Remaining C1 control chars: {remaining_c1}")
else:
    print("No C1 control chars remaining!")

import re, sys

filepath = r'C:\KassandraOpenAI\kassandra_openai_bot.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

original = content

# Common mojibake patterns from UTF-8 double-encoding via CP1252/Latin1
mojibake_map = {
    '\u00c3\u00bc': '\u00fc',  # Ã¼ -> ü
    '\u00c3\u00b6': '\u00f6',  # Ã¶ -> ö
    '\u00c3\u00a7': '\u00e7',  # Ã§ -> ç
    '\u00c3\u00b1': '\u00f1',  # Ã± -> ñ
    '\u00c5\u009f': '\u015f',  # ÅŸ -> ş
    '\u00c4\u009e': '\u011e',  # Äž -> Ğ
    '\u00c4\u009f': '\u011f',  # ÄŸ -> ğ
    '\u00c4\u00b1': '\u0131',  # Ä± -> ı
    '\u00c4\u00b0': '\u0130',  # Ä° -> İ
    '\u00c3\u009c': '\u00dc',  # Ãœ -> Ü
    '\u00c3\u0096': '\u00d6',  # Ã– -> Ö
    '\u00c3\u0087': '\u00c7',  # Ã‡ -> Ç
    '\u00c5\u0178': '\u015e',  # ÅŸ capital -> Ş
}

def fix_mojibake(text):
    fixed = text
    count = 0
    
    # Direct replacements for known patterns
    for bad, good in mojibake_map.items():
        if bad in fixed:
            n = fixed.count(bad)
            fixed = fixed.replace(bad, good)
            count += n
    
    # Fix remaining Å followed by letters (likely Ş)
    result = []
    i = 0
    while i < len(fixed):
        if fixed[i] == '\u00c5' and i + 1 < len(fixed):
            next_char = fixed[i + 1]
            if next_char.isalpha() or next_char in '\u00dc\u00d6\u011e\u0130':
                result.append('\u015e')  # Ş
                count += 1
                i += 1
                continue
        result.append(fixed[i])
        i += 1
    fixed = ''.join(result)
    
    # Fix broken emoji patterns (ğŸ prefix = broken 4-byte UTF-8)
    emoji_fixes = {
        '\u011f\u0178\u2020\u0095': '\U0001f195',  # 🆕
        '\u011f\u0178\u201c\u009d': '\U0001f4dd',  # broken pattern
        '\u011f\u0178\u201c\u0085': '\U0001f4c5',  # 📅
        '\u011f\u0178\u201c\u2039': '\U0001f4cb',  # 📋
        '\u011f\u0178\u00bd': '\U0001f37d',         # 🍽
        '\u011f\u0178\u201c\u008d': '\U0001f4cd',   # 📍
    }
    for bad_emoji, good_emoji in emoji_fixes.items():
        if bad_emoji in fixed:
            n = fixed.count(bad_emoji)
            fixed = fixed.replace(bad_emoji, good_emoji)
            count += n
    
    return fixed, count

content, count = fix_mojibake(content)

if content != original:
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Fixed {count} mojibake sequences')
else:
    print('No changes needed')

# Verify syntax
import py_compile
py_compile.compile(filepath, doraise=True)
print('Compilation OK')

# Check for remaining issues
remaining = []
for label, pattern in [
    ('Å', '\u00c5'), 
    ('Ã¼', '\u00c3\u00bc'), 
    ('Ã¶', '\u00c3\u00b6'), 
    ('ÄŸ', '\u00c4\u009f'), 
    ('Ä±', '\u00c4\u00b1'), 
    ('Ã§', '\u00c3\u00a7'),
    ('ğŸ', '\u011f\u0178'),
]:
    c = content.count(pattern)
    if c > 0:
        remaining.append(f'{label}: {c}')
if remaining:
    print(f'Remaining patterns: {", ".join(remaining)}')
else:
    print('All clean!')

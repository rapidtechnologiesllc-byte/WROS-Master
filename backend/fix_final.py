#!/usr/bin/env python3
"""Fix the last corrupted emoji in interviews.py."""

filepath = 'backend/app/api/v1/endpoints/interviews.py'

with open(filepath, 'rb') as f:
    content = f.read()

# Replace corrupted emoji sequences with plain text
# âš¡ (Start emoji) -> "Start:"
content = content.replace(b'\xc3\xa2\xc2\x9a\xc2\xa1', b'')  # Remove corrupted emoji
# ðŸ• (End emoji) -> "End:"
content = content.replace(b'\xc3\xb0\xc5\x92\xc2\xa5', b'')  # Remove corrupted emoji
# ðŸ" (Link emoji) -> Remove it
content = content.replace(b'\xc3\xb0\xc5\x92\xc2\x93', b'')  # Remove corrupted emoji

# Also fix any remaining corrupted quotes
content = content.replace(b'\xe2\x80\x9c', b'"')  # Left smart quote
content = content.replace(b'\xe2\x80\x9d', b'"')  # Right smart quote

with open(filepath, 'wb') as f:
    f.write(content)

print('✅ Fixed interviews.py')

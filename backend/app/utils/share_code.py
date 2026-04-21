"""
分享码生成器
生成易记忆的单词组合分享码，格式：形容词-名词-数字
"""

import random

# 常用形容词（易于记忆和口述）
ADJECTIVES = [
    "red", "blue", "green", "yellow", "black", "white", "gold", "silver",
    "big", "small", "fast", "slow", "hot", "cold", "new", "old",
    "happy", "lucky", "cool", "warm", "soft", "hard", "bright", "dark",
    "sweet", "fresh", "clean", "clear", "rich", "pure", "wild", "free",
    "smart", "quick", "strong", "brave", "calm", "safe", "fine", "nice"
]

# 常用名词（易于记忆和口述）
NOUNS = [
    "cat", "dog", "bird", "fish", "bear", "wolf", "fox", "deer",
    "lion", "tiger", "hawk", "owl", "bee", "ant", "fox", "duck",
    "sun", "moon", "star", "sky", "sea", "river", "lake", "hill",
    "tree", "flower", "leaf", "rose", "cloud", "rain", "snow", "wind",
    "book", "key", "door", "road", "bridge", "ship", "boat", "car",
    "house", "room", "desk", "chair", "lamp", "clock", "phone", "box"
]


def generate_share_code() -> str:
    """
    生成易记忆的分享码
    格式：形容词-名词-数字（如 red-fox-72）

    组合数：40形容词 × 48名词 × 100数字 = 192,000种
    对于内部文件分享系统已足够，且易于记忆
    """
    adjective = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    number = random.randint(10, 99)

    return f"{adjective}-{noun}-{number}"

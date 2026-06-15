from dataclasses import dataclass


@dataclass
class PlatformRules:
    max_chars: int
    hashtag_min: int
    hashtag_max: int
    system_rules: str
    image_size: str


PLATFORM_RULES: dict[str, PlatformRules] = {
    "instagram": PlatformRules(
        max_chars=2200,
        hashtag_min=5,
        hashtag_max=15,
        image_size="1024x1024",
        system_rules=(
            "Write for Instagram. Use a strong hook in the first line. "
            "Be conversational and authentic. Use emojis sparingly. "
            "End with a clear CTA. Hashtags go at the end, 5-15 tags, "
            "mix popular and niche. Max 2200 chars including hashtags."
        ),
    ),
    "facebook": PlatformRules(
        max_chars=63206,
        hashtag_min=1,
        hashtag_max=5,
        image_size="1024x1024",
        system_rules=(
            "Write for Facebook. Be conversational and community-focused. "
            "Medium length posts perform well (100-500 words). Use 1-5 relevant hashtags. "
            "End with an engagement question or CTA."
        ),
    ),
    "linkedin": PlatformRules(
        max_chars=3000,
        hashtag_min=3,
        hashtag_max=5,
        image_size="1024x1024",
        system_rules=(
            "Write for LinkedIn. Professional yet human tone. "
            "Lead with a compelling insight or stat. Use short paragraphs. "
            "Add value — no fluff. End with a thought-provoking question. "
            "3-5 professional hashtags. Max 3000 chars."
        ),
    ),
    "twitter": PlatformRules(
        max_chars=280,
        hashtag_min=1,
        hashtag_max=2,
        image_size="1536x1024",
        system_rules=(
            "Write for Twitter/X. CRITICAL: total post including hashtags MUST be under 280 chars. "
            "Be concise, punchy, opinionated. No filler words. "
            "1-2 hashtags max. Strong hook. Count chars carefully."
        ),
    ),
}


def get_rules(platform: str) -> PlatformRules:
    rules = PLATFORM_RULES.get(platform)
    if not rules:
        raise ValueError(f"No rules defined for platform: {platform}")
    return rules

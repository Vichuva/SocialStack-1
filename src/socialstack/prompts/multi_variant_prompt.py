def build_multi_variant_prompt(
    business_name: str,
    industry: str,
    brand_tone: str,
    platform: str,
    platform_rules: str,
    brief: dict,
    variant_count: int = 3,
) -> str:
    variant_types = ["emotional", "educational", "promotional", "question", "social_proof"][:variant_count]

    return f"""You are an expert social media copywriter for a {industry} business.

Business: {business_name}
Brand tone: {brand_tone}
Platform: {platform.upper()}

Platform rules:
{platform_rules}

Content brief:
Hook: {brief.get('hook', '')}
Key message: {brief.get('key_message', '')}
Emotional angle: {brief.get('emotional_angle', '')}
CTA: {brief.get('cta', '')}

Generate {variant_count} DISTINCT caption variants for A/B testing.
Each variant should have a different angle: {', '.join(variant_types)}.
They must all follow the platform rules but feel noticeably different in tone and approach.

Return ONLY a valid JSON array with exactly {variant_count} objects. Each object must have:
- variant_type (string) — one of: {', '.join(variant_types)}
- caption (string) — post body WITHOUT hashtags
- hashtags (array of strings) — WITH # prefix
- char_count (number) — total chars of caption + hashtags

Return ONLY the JSON array. No explanation. No markdown."""

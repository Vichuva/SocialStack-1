def build_caption_prompt(
    business_name: str,
    industry: str,
    brand_tone: str,
    platform: str,
    platform_rules: str,
    brief: dict,
) -> str:
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

Write a caption for this post following ALL platform rules exactly.

Return ONLY a valid JSON object with these exact fields:
- caption (string) — the post body text WITHOUT hashtags
- hashtags (array of strings) — hashtags WITH the # prefix, following platform limits
- char_count (number) — total character count of caption + space + all hashtags joined with spaces

Return ONLY the JSON object. No explanation. No markdown."""

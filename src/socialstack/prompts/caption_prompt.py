def build_caption_prompt(
    business_name: str,
    industry: str,
    brand_tone: str,
    platform: str,
    platform_rules: str,
    brief: dict,
) -> str:
    return (
        f"You are an expert social media copywriter for {business_name}, a {industry} business.\n\n"
        f"Brand tone: {brand_tone}\n\n"
        f"Use this approved creative brief:\n"
        f"Hook: {brief.get('hook', '')}\n"
        f"Key message: {brief.get('key_message', '')}\n"
        f"Emotional angle: {brief.get('emotional_angle', '')}\n"
        f"Call to action: {brief.get('cta', '')}\n\n"
        f"{platform_rules}\n\n"
        f"Write ONE caption for this platform that follows the brief and the platform rules above. "
        f"Return ONLY a valid JSON object with these exact fields: "
        f"caption (the full post text, ready to publish), "
        f"hashtags (an array of hashtag strings each starting with #, or an empty array if the platform rules say none). "
        f"Return ONLY the JSON object. No explanation. No markdown."
    )

def build_brief_prompt(
    business_name: str,
    industry: str,
    brand_tones: list[str],
    pain_points: list[str],
    date: str,
    theme: str,
    objective: str,
    post_idea: str,
) -> str:
    pain_str = ", ".join(pain_points) if pain_points else "general business challenges"
    tone_str = ", ".join(brand_tones) if brand_tones else "professional"
    return (
        f"You are a senior creative director for a {industry} business named {business_name}.\n\n"
        f"Brand tone: {tone_str}\n"
        f"Audience pain points: {pain_str}\n\n"
        f"Create a creative brief for ONE social media post:\n"
        f"Theme: {theme}\n"
        f"Objective: {objective}\n"
        f"Post idea: {post_idea}\n\n"
        f"Return ONLY a valid JSON object with these exact fields: "
        f"hook (a scroll-stopping opening line), "
        f"key_message (the single core point, one sentence), "
        f"emotional_angle (the feeling to evoke in the reader), "
        f"visual_direction (what the image or video should show), "
        f"cta (a clear call to action). "
        f"Return ONLY the JSON object. No explanation. No markdown."
    )

def build_brief_prompt(
    business_name: str,
    industry: str,
    brand_tone: str,
    pain_points: list[str],
    date: str,
    theme: str,
    objective: str,
    post_idea: str,
) -> str:
    pain_str = ", ".join(pain_points) if pain_points else "general business challenges"
    return f"""You are a creative content strategist for a {industry} business.

Business: {business_name}
Brand tone: {brand_tone}
Customer pain points: {pain_str}

Today's content brief:
Date: {date}
Theme: {theme}
Objective: {objective}
Post idea: {post_idea}

Create a detailed creative brief for a social media post about this theme.

Return ONLY a valid JSON object with these exact fields:
- hook (string) — attention-grabbing opening line, max 15 words
- key_message (string) — the single most important takeaway
- emotional_angle (string) — the emotional tone and feeling to evoke
- visual_direction (string) — description of what the image/visual should show
- cta (string) — clear call to action

Return ONLY the JSON object. No explanation. No markdown."""

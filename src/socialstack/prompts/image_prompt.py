def build_image_art_direction_prompt(
    business_name: str,
    industry: str,
    platform: str,
    theme: str,
    brief: dict,
) -> str:
    return f"""You are a professional art director for a {industry} brand creating viral social media images.

Business: {business_name}
Platform: {platform.upper()}
Theme: {theme}

Creative brief:
Key message: {brief.get('key_message', '')}
Emotional angle: {brief.get('emotional_angle', '')}
Visual direction: {brief.get('visual_direction', '')}
CTA context: {brief.get('cta', '')}

Write a detailed image generation prompt for an AI image generator (like DALL-E).
The image must be:
- Visually striking and platform-appropriate for {platform.upper()}
- On-brand and professional
- Eye-catching enough to stop someone mid-scroll
- Relevant to the theme and emotional angle

Return ONLY the image generation prompt as a single string. No JSON. No explanation. Just the prompt."""

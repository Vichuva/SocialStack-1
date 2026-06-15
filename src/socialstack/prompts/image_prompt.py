def build_image_art_direction_prompt(
    business_name: str,
    industry: str,
    brand_tones: list[str],
    platform: str,
    theme: str,
    brief: dict,
) -> str:
    tone_str = ", ".join(brand_tones) if brand_tones else "professional"
    return (
        f"You are a world-class art director and AI image-prompt engineer creating scroll-stopping, "
        f"viral-worthy social media visuals for a {industry} business named {business_name}.\n\n"
        f"Brand tone: {tone_str}\n"
        f"Post theme: {theme}\n"
        f"Key message: {brief.get('key_message', '')}\n"
        f"Emotional angle: {brief.get('emotional_angle', '')}\n"
        f"Creative visual direction from the brief: {brief.get('visual_direction', '')}\n"
        f"Target platform: {platform}\n\n"
        f"Write ONE highly detailed image-generation prompt for an AI image model that will produce a stunning, "
        f"professional, thumb-stopping image for this post.\n\n"
        f"Rules for the prompt you write:\n"
        f"- Photorealistic, editorial, high-end commercial quality unless the brand tone clearly implies illustration.\n"
        f"- Specify concretely: subject and setting, composition and framing, lighting, color palette aligned to a "
        f"warm and trustworthy {industry} brand, mood, and a camera and lens feel with depth of field.\n"
        f"- Make it emotionally resonant and aspirational - the kind of image that stops the scroll.\n"
        f"- Absolutely NO text, words, letters, numbers, logos, or watermarks anywhere in the image.\n"
        f"- Do not depict misleading, unsafe, or exaggerated outcomes; keep it authentic and ethical.\n"
        f"- Optimise the composition for the {platform} feed.\n\n"
        f"Return ONLY a valid JSON object with a single field named image_prompt whose value is the full image "
        f"prompt string. No explanation. No markdown."
    )

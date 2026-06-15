def build_multi_variant_prompt(
    business_name: str,
    industry: str,
    brand_tone: str,
    platform: str,
    platform_rules: str,
    brief: dict,
    variant_count: int = 3,
) -> str:
    return (
        f"You are an expert social media copywriter creating multiple caption variants for A/B testing.\n\n"
        f"Business: {business_name} ({industry})\n"
        f"Brand tone: {brand_tone}\n"
        f"Brief:\n"
        f"  Hook: {brief.get('hook', '')}\n"
        f"  Key message: {brief.get('key_message', '')}\n"
        f"  Emotional angle: {brief.get('emotional_angle', '')}\n"
        f"  CTA: {brief.get('cta', '')}\n\n"
        f"{platform_rules}\n\n"
        f"Generate {variant_count} DISTINCT caption variants. Each must take a different angle so the reviewer "
        f"can A/B test the approaches. Use these labels and order:\n"
        f"  Variant 1: label=emotional - storytelling, evokes a feeling, leads with empathy\n"
        f"  Variant 2: label=educational - value-first, teaches something, leads with a fact\n"
        f"  Variant 3: label=promotional - direct, benefit-focused, leads with the offer\n"
        f"  Variant 4 (if requested): label=question - hook is a question that pulls the reader in\n"
        f"  Variant 5 (if requested): label=social_proof - leads with a customer/result\n\n"
        f"Each variant must follow the platform rules above. Hashtags must be relevant to the variant's angle, not generic.\n\n"
        f"Return ONLY a valid JSON array of objects with these exact fields:\n"
        f"- label (string, one of the labels above)\n"
        f"- approach (string, one-sentence description of the angle)\n"
        f"- hook (string, the opening line of the caption)\n"
        f"- caption (string, the full ready-to-publish caption)\n"
        f"- hashtags (array of strings, each starting with #)\n"
        f"- cta (string, the call to action used)\n\n"
        f"Return ONLY the JSON array. No explanation. No markdown."
    )

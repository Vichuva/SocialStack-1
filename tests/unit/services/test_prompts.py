"""Unit tests verifying prompt templates match n8n workflow content."""
import pytest


def test_calendar_prompt_contains_n8n_phrases():
    from socialstack.prompts.calendar_prompt import build_calendar_prompt
    prompt = build_calendar_prompt(
        business_name="Test Clinic",
        industry="dental",
        brand_tones=["warm", "reassuring"],
        pain_points=["fear of pain", "cost anxiety"],
        offerings=["Root Canal", "Whitening"],
        month=6,
        year=2026,
    )
    assert "social media content strategist" in prompt
    assert "Audience pain points" in prompt
    assert "Services offered" in prompt
    assert "JSON array" in prompt
    assert "awareness, education, promotion, trust, engagement" in prompt
    assert "No explanation. No markdown." in prompt


def test_brief_prompt_contains_n8n_phrases():
    from socialstack.prompts.brief_prompt import build_brief_prompt
    prompt = build_brief_prompt(
        business_name="Luma Dental",
        industry="dental",
        brand_tones=["warm", "reassuring"],
        pain_points=["fear of pain"],
        date="2026-06-01",
        theme="Healthy Smiles",
        objective="awareness",
        post_idea="Share dental tips",
    )
    assert "senior creative director" in prompt
    assert "Audience pain points" in prompt
    assert "Create a creative brief for ONE social media post" in prompt
    assert "hook (a scroll-stopping opening line)" in prompt
    assert "visual_direction (what the image or video should show)" in prompt
    assert "Return ONLY the JSON object. No explanation. No markdown." in prompt


def test_caption_prompt_contains_n8n_phrases():
    from socialstack.prompts.caption_prompt import build_caption_prompt
    from socialstack.platform_rules.rules import get_rules
    rules = get_rules("instagram")
    prompt = build_caption_prompt(
        business_name="Luma Dental",
        industry="dental",
        brand_tones=["warm", "reassuring"],
        platform="instagram",
        platform_rules=rules.system_rules,
        brief={"hook": "Test hook", "key_message": "Key msg", "emotional_angle": "Trust", "cta": "Book now"},
    )
    assert "expert social media copywriter" in prompt
    assert "Use this approved creative brief" in prompt
    assert "Call to action:" in prompt
    assert "Write ONE caption for this platform" in prompt
    assert "caption (the full post text, ready to publish)" in prompt
    # char_count must NOT be in the prompt — the service computes it
    assert "char_count" not in prompt


def test_image_prompt_contains_n8n_phrases():
    from socialstack.prompts.image_prompt import build_image_art_direction_prompt
    prompt = build_image_art_direction_prompt(
        business_name="Luma Dental",
        industry="dental",
        brand_tones=["warm", "reassuring"],
        platform="instagram",
        theme="Healthy Smiles",
        brief={"key_message": "Stay healthy", "emotional_angle": "Trust", "visual_direction": "Bright clinic"},
    )
    assert "world-class art director and AI image-prompt engineer" in prompt
    assert "scroll-stopping, viral-worthy" in prompt
    assert "Absolutely NO text, words, letters, numbers, logos, or watermarks" in prompt
    assert "image_prompt" in prompt
    assert "Return ONLY a valid JSON object" in prompt


def test_multi_variant_prompt_contains_n8n_phrases():
    from socialstack.prompts.multi_variant_prompt import build_multi_variant_prompt
    from socialstack.platform_rules.rules import get_rules
    rules = get_rules("instagram")
    prompt = build_multi_variant_prompt(
        business_name="Luma Dental",
        industry="dental",
        brand_tones=["warm", "reassuring"],
        platform="instagram",
        platform_rules=rules.system_rules,
        brief={"hook": "H", "key_message": "M", "emotional_angle": "E", "cta": "C"},
        variant_count=3,
    )
    assert "A/B testing" in prompt
    assert "label=emotional" in prompt
    assert "label=educational" in prompt
    assert "label=promotional" in prompt
    assert "label=question" in prompt
    assert "label=social_proof" in prompt
    # n8n schema fields
    assert "label (string" in prompt
    assert "approach (string" in prompt
    assert "hook (string" in prompt
    assert "cta (string" in prompt


def test_regen_prompt_contains_n8n_phrases():
    from socialstack.prompts.regen_prompt import build_regen_analysis_prompt
    prompt = build_regen_analysis_prompt(
        feedback="Too salesy, make it more educational",
        original_brief={
            "hook": "Save money today",
            "key_message": "Great offer",
            "emotional_angle": "Urgency",
            "visual_direction": "Promotional banner",
            "cta": "Buy now",
        },
    )
    assert "expert content director analyzing reviewer feedback" in prompt
    assert "ORIGINAL brief was" in prompt
    assert "adjusted_hook" in prompt
    assert "adjusted_key_message" in prompt
    assert "tone_shift" in prompt
    assert "summary" in prompt
    assert "Be specific - rewrite the elements the feedback affects" in prompt

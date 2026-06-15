def build_regen_analysis_prompt(feedback: str, original_brief: dict) -> str:
    return f"""You are an expert content director analyzing reviewer feedback.
The reviewer rejected a social media post and provided this feedback:

'{feedback}'

The ORIGINAL brief was:
Hook: {original_brief.get('hook', '')}
Key message: {original_brief.get('key_message', '')}
Emotional angle: {original_brief.get('emotional_angle', '')}
Visual direction: {original_brief.get('visual_direction', '')}
CTA: {original_brief.get('cta', '')}

Based on the feedback, decide what should change in the brief.
Be specific — rewrite the elements the feedback affects, keep the rest as-is.

Return ONLY a valid JSON object with these exact fields:
- adjusted_hook (string) — new hook reflecting feedback, or the original if no change needed
- adjusted_key_message (string) — new key message, or the original
- adjusted_emotional_angle (string) — new emotional angle, or the original
- adjusted_visual_direction (string) — new visual direction, or the original
- adjusted_cta (string) — new CTA, or the original
- tone_shift (string) — short label for the change, e.g. 'more educational', 'less salesy', 'shorter'
- summary (string) — one sentence explaining what changed and why

Return ONLY the JSON object. No explanation. No markdown."""

import calendar as cal_module


def build_calendar_prompt(
    business_name: str,
    industry: str,
    brand_tone: str,
    pain_points: list[str],
    offerings: list[str],
    month: int,
    year: int,
) -> str:
    days_in_month = cal_module.monthrange(year, month)[1]
    pain_str = ", ".join(pain_points) if pain_points else "general business challenges"
    offerings_str = ", ".join(offerings) if offerings else "various services"

    return (
        f"You are a social media content strategist for a {industry} business.\n\n"
        f"Business: {business_name}\n"
        f"Brand tone: {brand_tone}\n"
        f"Audience pain points: {pain_str}\n"
        f"Services offered: {offerings_str}\n"
        f"Month: {month}\n"
        f"Year: {year}\n"
        f"Number of days in this month: {days_in_month}\n\n"
        f"Generate a content theme for EACH day of this month. Return ONLY a valid JSON array with exactly "
        f"{days_in_month} objects. Each object must have: day (number from 1 to {days_in_month}), "
        f"theme (short, max 6 words), objective (one of: awareness, education, promotion, trust, engagement), "
        f"post_idea (one sentence). Return ONLY the JSON array. No explanation. No markdown."
    )

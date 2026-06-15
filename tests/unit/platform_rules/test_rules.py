import pytest
from socialstack.platform_rules.rules import get_rules, PLATFORM_RULES


def test_all_platforms_have_rules():
    for platform in ["instagram", "facebook", "linkedin", "twitter"]:
        rules = get_rules(platform)
        assert rules.max_chars > 0
        assert rules.hashtag_max > 0


def test_twitter_280_limit():
    rules = get_rules("twitter")
    assert rules.max_chars == 280


def test_instagram_hashtag_range():
    rules = get_rules("instagram")
    assert rules.hashtag_min == 5
    assert rules.hashtag_max == 15


def test_unknown_platform_raises():
    with pytest.raises(ValueError, match="No rules defined"):
        get_rules("tiktok")

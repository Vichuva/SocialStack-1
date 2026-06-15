"""Integration tests for the metrics collection pipeline (WF-METRICS).

Tests cover: dedup logic, per-platform normalization, graceful failure handling.
All platform HTTP calls are mocked — no real API calls made.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


def _make_event(
    event_id="evt_001",
    business_id="biz_001",
    platform="instagram",
    post_id="ig_12345",
    published_at=None,
):
    event = MagicMock()
    event.id = event_id
    event.business_id = business_id
    event.platform = platform
    event.platform_post_id = post_id
    event.status = "success"
    event.published_at = published_at or datetime.now(timezone.utc) - timedelta(hours=2)
    return event


@pytest.mark.asyncio
async def test_metrics_collected_for_published_events():
    """MetricsService.collect() creates one post_metrics row per event with real insights."""
    event = _make_event()
    mock_session = AsyncMock()

    mock_event_repo = AsyncMock()
    mock_event_repo.get_successful_without_recent_metrics = AsyncMock(return_value=[event])

    mock_metrics_repo = AsyncMock()
    created_rows: list[dict] = []

    async def capture_create(**kwargs):
        created_rows.append(kwargs)
        row = MagicMock()
        row.id = "metric_001"
        return row

    mock_metrics_repo.create = capture_create

    fake_insights = {
        "impressions": 5000,
        "reach": 3200,
        "likes": 120,
        "comments": 15,
        "saves": 40,
        "shares": 10,
        "clicks": None,
        "engagement_rate": 0.037,
    }

    with patch("socialstack.services.metrics_service.PublishEventRepository", return_value=mock_event_repo), \
         patch("socialstack.services.metrics_service.PostMetricsRepository", return_value=mock_metrics_repo):

        from socialstack.services.metrics_service import MetricsService
        svc = MetricsService(session=mock_session)
        svc._get_token = AsyncMock(return_value="fake_token")
        svc._fetch_insights = AsyncMock(return_value=fake_insights)

        result = await svc.collect(business_id="biz_001")

    assert result["collected"] == 1
    assert result["failed"] == 0
    assert result["total_events"] == 1
    assert len(created_rows) == 1
    assert created_rows[0]["impressions"] == 5000
    assert created_rows[0]["engagement_rate"] == 0.037
    assert created_rows[0]["platform"] == "instagram"


@pytest.mark.asyncio
async def test_metrics_skips_events_without_post_id():
    """Events where platform_post_id is None are silently skipped (no metrics row created)."""
    event = _make_event(post_id=None)
    mock_session = AsyncMock()

    mock_event_repo = AsyncMock()
    mock_event_repo.get_successful_without_recent_metrics = AsyncMock(return_value=[event])

    mock_metrics_repo = AsyncMock()
    mock_metrics_repo.create = AsyncMock()

    with patch("socialstack.services.metrics_service.PublishEventRepository", return_value=mock_event_repo), \
         patch("socialstack.services.metrics_service.PostMetricsRepository", return_value=mock_metrics_repo):

        from socialstack.services.metrics_service import MetricsService
        svc = MetricsService(session=mock_session)
        svc._get_token = AsyncMock(return_value="fake_token")

        result = await svc.collect()

    assert result["collected"] == 0
    mock_metrics_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_metrics_skips_events_with_no_token():
    """MetricsService skips events when no active social connection token is found."""
    event = _make_event()
    mock_session = AsyncMock()

    mock_event_repo = AsyncMock()
    mock_event_repo.get_successful_without_recent_metrics = AsyncMock(return_value=[event])

    mock_metrics_repo = AsyncMock()
    mock_metrics_repo.create = AsyncMock()

    with patch("socialstack.services.metrics_service.PublishEventRepository", return_value=mock_event_repo), \
         patch("socialstack.services.metrics_service.PostMetricsRepository", return_value=mock_metrics_repo):

        from socialstack.services.metrics_service import MetricsService
        svc = MetricsService(session=mock_session)
        svc._get_token = AsyncMock(return_value=None)  # no token

        result = await svc.collect()

    assert result["collected"] == 0
    mock_metrics_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_metrics_handles_platform_api_failure_gracefully():
    """A platform API failure for one event does not crash the whole collection run."""
    good_event = _make_event(event_id="evt_good", post_id="ig_good")
    bad_event = _make_event(event_id="evt_bad", post_id="ig_bad")
    mock_session = AsyncMock()

    mock_event_repo = AsyncMock()
    mock_event_repo.get_successful_without_recent_metrics = AsyncMock(return_value=[bad_event, good_event])

    created_rows: list[dict] = []
    mock_metrics_repo = AsyncMock()

    async def capture_create(**kwargs):
        created_rows.append(kwargs)
        return MagicMock()

    mock_metrics_repo.create = capture_create

    good_insights = {
        "impressions": 1000, "reach": 800, "likes": 50, "comments": 5,
        "saves": 10, "shares": 3, "clicks": None, "engagement_rate": 0.068,
    }

    async def fail_bad_succeed_good(event, token):
        if event.id == "evt_bad":
            raise RuntimeError("Instagram API 500")
        return good_insights

    with patch("socialstack.services.metrics_service.PublishEventRepository", return_value=mock_event_repo), \
         patch("socialstack.services.metrics_service.PostMetricsRepository", return_value=mock_metrics_repo):

        from socialstack.services.metrics_service import MetricsService
        svc = MetricsService(session=mock_session)
        svc._get_token = AsyncMock(return_value="fake_token")
        svc._fetch_insights = fail_bad_succeed_good

        result = await svc.collect()

    assert result["collected"] == 1
    assert result["failed"] == 1
    assert result["total_events"] == 2
    assert len(created_rows) == 1
    assert created_rows[0]["publish_event_id"] == "evt_good"


@pytest.mark.asyncio
async def test_instagram_insights_normalization():
    """_fetch_instagram() correctly maps Graph API response to the normalized dict."""
    import httpx
    from unittest.mock import AsyncMock as _AsyncMock, patch as _patch

    mock_session = AsyncMock()
    media_id = "17854360229135492"
    token = "test_token"

    graph_response = {
        "data": [
            {"name": "impressions", "values": [{"value": 8500}]},
            {"name": "reach", "values": [{"value": 6200}]},
            {"name": "likes", "values": [{"value": 310}]},
            {"name": "comments", "values": [{"value": 28}]},
            {"name": "saved", "values": [{"value": 95}]},
            {"name": "shares", "values": [{"value": 42}]},
        ]
    }

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = graph_response

    mock_client = MagicMock()
    mock_client.get = _AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = _AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = _AsyncMock(return_value=False)

    with patch("socialstack.services.metrics_service.httpx.AsyncClient", return_value=mock_client):
        from socialstack.services.metrics_service import MetricsService
        svc = MetricsService(session=mock_session)
        result = await svc._fetch_instagram(media_id, token)

    assert result is not None
    assert result["impressions"] == 8500
    assert result["reach"] == 6200
    assert result["likes"] == 310
    assert result["comments"] == 28
    assert result["saves"] == 95
    assert result["shares"] == 42
    # engagement_rate = (310 + 28 + 95 + 42) / 8500 = 475 / 8500
    assert result["engagement_rate"] == round(475 / 8500, 4)


@pytest.mark.asyncio
async def test_twitter_insights_normalization():
    """_fetch_twitter() correctly maps Twitter v2 public_metrics to the normalized dict."""
    from unittest.mock import AsyncMock as _AsyncMock

    mock_session = AsyncMock()
    tweet_id = "1780135101422"
    token = "test_bearer"

    twitter_response = {
        "data": {
            "id": tweet_id,
            "public_metrics": {
                "impression_count": 12000,
                "like_count": 430,
                "retweet_count": 85,
                "reply_count": 37,
                "bookmark_count": 120,
            },
        }
    }

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = twitter_response

    mock_client = MagicMock()
    mock_client.get = _AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = _AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = _AsyncMock(return_value=False)

    with patch("socialstack.services.metrics_service.httpx.AsyncClient", return_value=mock_client):
        from socialstack.services.metrics_service import MetricsService
        svc = MetricsService(session=mock_session)
        result = await svc._fetch_twitter(tweet_id, token)

    assert result is not None
    assert result["impressions"] == 12000
    assert result["likes"] == 430
    assert result["shares"] == 85      # retweets mapped to shares
    assert result["comments"] == 37    # replies mapped to comments
    assert result["saves"] == 120      # bookmarks mapped to saves
    # engagement = (430 + 85 + 37) / 12000 = 552 / 12000
    assert result["engagement_rate"] == round(552 / 12000, 4)

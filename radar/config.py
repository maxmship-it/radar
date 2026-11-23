"""Limits and budgets. One place. Hooks and the planner both read these."""
RECENT_DAYS = 100            # Part 1 of the board
WINDOW_DAYS = 548            # 18 months, Part 2 ends here
CROSS_DAYS = 365             # cross-niche: last 12 months
CROSS_MAX_CARDS = 8
CROSS_MAX_CALLS = 15
MAX_COMBOS = 10
TIME_BUDGET_S = 30 * 60      # MAX DECIDED Nov 19: never more than half an hour
IDEAS_TIME_BUDGET_S = 60 * 60  # MAX DECIDED Nov 23: a deep dive (20 ideas) may run an hour
MAX_IDEAS = 20
IDEA_TITLES = 3              # MAX DECIDED Nov 23: 3 titles, each with its own outlier thumbnail
IDEAS_CHECK_MAX = 5          # ideas where Max's view is unknown, marked "your view?"
IDEAS_REMAKE_WARN = 8        # remakes of his past winners are welcome; more than this gets a warning
IDEAS_VIDIQ_TERMS = 6        # a deep dive searches more vidIQ terms than a topic run (5 credits each)
CACHE_DAYS = 7
ALGROW_PER_MIN = 25          # Algrow allows 30 a minute across everything; stay under it
ALGROW_THUMB_PER_DAY = 30    # free cap is 40 a day, then $0.20 a call. Never reach it.
ALGROW_LIKE_PER_RUN = 6       # "videos like this one" seeds per run, one page each
ALGROW_LIKE_PER_DAY = 36      # Algrow gives 40 a day free, then $0.20 a call. Never reach 40.
TUBEAI_PER_RUN = 300
TUBEAI_PER_DAY = 1500        # the account allows 3,000 a day shared with the app
VIDIQ_CREDITS_PER_RUN = 100  # MAX DECIDED Nov 19
VIDIQ_CALL_COST = 5
PAGE_DRY_BELOW = 3           # stop paging a query when a page adds fewer than this many new outliers
ROUND_DRY_BELOW = 2          # stop rounds when a round adds fewer than this many new on-topic outliers
MAX_PAGES = 12
MIN_SEARCH_VIEWS = 50_000    # no branch of the outlier rule passes below 50,000 views

# Only these connector tools may run inside the Radar project. Everything else is refused by the hook.
ALLOW = {
    "Algrow": {"search_viral_videos", "folder_outliers", "get_folder", "list_folders", "youtube_search",
               "get_channel_videos", "get_video_daily_views", "search_by_thumbnail", "trending_title_formats",
               "get_channel_title_formats", "trending_subjects", "trend_videos", "get_youtube_video_data",
               "get_video_thumbnail", "resolve_handle", "resolve_url", "health_check", "get_credit_balance",
               "save_channels", "create_folder"},
    "TubeAI": {"explore_videos", "explore_video", "explore_channels", "explore_channel", "explore_similar_channels",
               "explore_similar_thumbnails", "explore_niches", "mini_titles", "mini_ideas", "workspace_account"},
    "vidIQ": {"vidiq_balance", "vidiq_outliers", "vidiq_get_videos_by_ids", "vidiq_similar_thumbnails"},
}
RADAR_FOLDERS = {"Radar pool", "Radar cross-niche"}
# calls that finish a board; still allowed after the time budget runs out
FINISHING_TOOLS = {"vidiq_get_videos_by_ids", "get_video_daily_views", "vidiq_balance", "workspace_account", "health_check", "list_folders"}

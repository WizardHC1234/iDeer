"""
Fetch tweets from Twitter/X accounts via multiple backends:
  - api: Twitter API v2 via tweepy
  - rapidapi: Third-party RapidAPI proxy
  - nitter: Nitter RSS feed (no auth required, but less reliable)
"""

import os
import requests
from datetime import datetime, timezone, timedelta


def load_accounts(accounts_file: str) -> list[str]:
    """Load usernames from a text file (one per line, # for comments)."""
    if not os.path.exists(accounts_file):
        print(f"Accounts file not found: {accounts_file}")
        return []
    usernames = []
    with open(accounts_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                # Strip leading @ if present
                usernames.append(line.lstrip("@"))
    return usernames


def fetch_user_tweets_api(
    username: str,
    bearer_token: str,
    since_hours: int = 24,
    max_tweets: int = 20,
) -> list[dict]:
    """Fetch recent tweets using Twitter API v2 via tweepy (lazy import)."""
    try:
        import tweepy
    except ImportError:
        print("tweepy is not installed. Install with: pip install tweepy")
        return []

    client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)
    since_time = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    try:
        # Look up user ID
        user_resp = client.get_user(username=username, user_fields=["name", "profile_image_url"])
        if not user_resp or not user_resp.data:
            print(f"[api] User not found: @{username}")
            return []
        user = user_resp.data
        user_id = user.id
        author_name = user.name

        # Fetch tweets
        tweets_resp = client.get_users_tweets(
            user_id,
            max_results=min(max_tweets, 100),
            start_time=since_time,
            tweet_fields=["created_at", "public_metrics", "referenced_tweets", "entities"],
            expansions=["referenced_tweets.id", "referenced_tweets.id.author_id"],
            user_fields=["username", "name"],
        )

        if not tweets_resp or not tweets_resp.data:
            return []

        # Build lookup for referenced tweets
        includes = tweets_resp.includes or {}
        ref_tweets = {t.id: t for t in (includes.get("tweets") or [])}
        ref_users = {u.id: u for u in (includes.get("users") or [])}

        results = []
        for tweet in tweets_resp.data:
            metrics = tweet.public_metrics or {}
            is_retweet = False
            is_reply = False
            is_quote = False
            quoted_text = ""
            quoted_author = ""

            if tweet.referenced_tweets:
                for ref in tweet.referenced_tweets:
                    if ref.type == "retweeted":
                        is_retweet = True
                    elif ref.type == "replied_to":
                        is_reply = True
                    elif ref.type == "quoted":
                        is_quote = True
                        rt = ref_tweets.get(ref.id)
                        if rt:
                            quoted_text = rt.text
                            if hasattr(rt, "author_id") and rt.author_id in ref_users:
                                quoted_author = ref_users[rt.author_id].username

            # Extract URLs and media
            entities = tweet.data.get("entities", {}) if hasattr(tweet, "data") else {}
            urls = [u.get("expanded_url", u.get("url", "")) for u in entities.get("urls", [])]
            media_urls = []  # Media requires additional expansion

            results.append({
                "tweet_id": str(tweet.id),
                "text": tweet.text,
                "author_username": username,
                "author_name": author_name,
                "created_at": tweet.created_at.isoformat() if tweet.created_at else "",
                "likes": metrics.get("like_count", 0),
                "retweets": metrics.get("retweet_count", 0),
                "replies": metrics.get("reply_count", 0),
                "is_retweet": is_retweet,
                "is_reply": is_reply,
                "is_quote": is_quote,
                "quoted_text": quoted_text,
                "quoted_author": quoted_author,
                "media_urls": media_urls,
                "urls": urls,
                "tweet_url": f"https://x.com/{username}/status/{tweet.id}",
            })

        return results

    except Exception as e:
        print(f"[api] Error fetching tweets for @{username}: {e}")
        return []


def fetch_user_tweets_rapidapi(
    username: str,
    api_key: str,
    api_host: str = "twitter-api45.p.rapidapi.com",
    since_hours: int = 24,
    max_tweets: int = 20,
) -> list[dict]:
    """Fetch recent tweets via RapidAPI Twitter proxy."""
    url = f"https://{api_host}/timeline.php"
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": api_host,
    }
    params = {"screenname": username, "count": str(max_tweets)}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[rapidapi] Error fetching tweets for @{username}: {e}")
        return []

    since_time = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    timeline = data.get("timeline", [])
    results = []

    for item in timeline[:max_tweets]:
        # Parse created_at
        created_str = item.get("created_at", "")
        try:
            created_dt = datetime.strptime(created_str, "%a %b %d %H:%M:%S %z %Y")
            if created_dt < since_time:
                continue
            created_iso = created_dt.isoformat()
        except (ValueError, TypeError):
            created_iso = created_str

        text = item.get("text", "") or item.get("full_text", "")
        is_retweet = text.startswith("RT @")
        is_reply = item.get("in_reply_to_screen_name") is not None
        is_quote = item.get("is_quote_status", False)

        quoted_text = ""
        quoted_author = ""
        qt = item.get("quoted_status")
        if qt:
            quoted_text = qt.get("text", "") or qt.get("full_text", "")
            quoted_author = qt.get("user", {}).get("screen_name", "")

        # Extract media
        media_urls = []
        entities = item.get("entities", {})
        extended = item.get("extended_entities", {})
        for m in extended.get("media", entities.get("media", [])):
            media_urls.append(m.get("media_url_https", m.get("media_url", "")))

        urls = [u.get("expanded_url", u.get("url", "")) for u in entities.get("urls", [])]

        tweet_id = item.get("id_str", str(item.get("id", "")))
        author_name = item.get("user", {}).get("name", username)

        results.append({
            "tweet_id": tweet_id,
            "text": text,
            "author_username": username,
            "author_name": author_name,
            "created_at": created_iso,
            "likes": item.get("favorite_count", 0),
            "retweets": item.get("retweet_count", 0),
            "replies": item.get("reply_count", 0),
            "is_retweet": is_retweet,
            "is_reply": is_reply,
            "is_quote": is_quote,
            "quoted_text": quoted_text,
            "quoted_author": quoted_author,
            "media_urls": media_urls,
            "urls": urls,
            "tweet_url": f"https://x.com/{username}/status/{tweet_id}",
        })

    return results


def fetch_user_tweets_nitter(
    username: str,
    nitter_instances: list[str] | None = None,
    since_hours: int = 24,
    max_tweets: int = 20,
) -> list[dict]:
    """Fetch recent tweets from Nitter RSS feed (no auth required)."""
    from bs4 import BeautifulSoup

    if not nitter_instances:
        nitter_instances = [
            "nitter.privacydev.net",
            "nitter.poast.org",
            "nitter.woodland.cafe",
        ]

    since_time = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    results = []

    for instance in nitter_instances:
        rss_url = f"https://{instance}/{username}/rss"
        try:
            resp = requests.get(rss_url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (compatible; DailyRecommender/1.0)"
            })
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.content, "html.parser")
            items = soup.find_all("item")

            for item in items[:max_tweets]:
                title = item.find("title")
                desc = item.find("description")
                link = item.find("link")
                pub_date = item.find("pubdate")

                text = ""
                if desc:
                    desc_soup = BeautifulSoup(desc.get_text(), "html.parser")
                    text = desc_soup.get_text(separator=" ", strip=True)
                elif title:
                    text = title.get_text(strip=True)

                # Parse pubDate
                created_iso = ""
                if pub_date:
                    try:
                        from email.utils import parsedate_to_datetime
                        created_dt = parsedate_to_datetime(pub_date.get_text(strip=True))
                        if created_dt < since_time:
                            continue
                        created_iso = created_dt.isoformat()
                    except Exception:
                        pass

                # Extract tweet URL and ID
                tweet_url = ""
                tweet_id = ""
                guid = item.find("guid")
                if guid:
                    guid_text = guid.get_text(strip=True)
                    # guid may be just the numeric ID or a full URL
                    if guid_text.isdigit():
                        tweet_id = guid_text
                    else:
                        tweet_id = guid_text.rstrip("#m").rstrip("/").split("/")[-1]
                if link:
                    # <link/> is self-closing in RSS XML; URL is in next_sibling
                    raw_link = link.get_text(strip=True)
                    if not raw_link and link.next_sibling:
                        raw_link = str(link.next_sibling).strip().rstrip("#m")
                    if raw_link:
                        tweet_url = raw_link.replace(f"https://{instance}", "https://x.com")
                if not tweet_url and tweet_id:
                    tweet_url = f"https://x.com/{username}/status/{tweet_id}"

                is_retweet = text.startswith("RT by @") or text.startswith("R to @")
                is_reply = "replying to @" in text.lower()

                results.append({
                    "tweet_id": tweet_id or f"nitter_{hash(text) & 0xFFFFFFFF:08x}",
                    "text": text,
                    "author_username": username,
                    "author_name": username,
                    "created_at": created_iso,
                    "likes": 0,
                    "retweets": 0,
                    "replies": 0,
                    "is_retweet": is_retweet,
                    "is_reply": is_reply,
                    "is_quote": False,
                    "quoted_text": "",
                    "quoted_author": "",
                    "media_urls": [],
                    "urls": [],
                    "tweet_url": tweet_url,
                })

            if results:
                print(f"[nitter] Fetched {len(results)} tweets for @{username} via {instance}")
                return results

        except Exception as e:
            print(f"[nitter] Failed for @{username} via {instance}: {e}")
            continue

    if not results:
        print(f"[nitter] All instances failed for @{username}")
    return results


def fetch_all_accounts(
    accounts: list[str],
    backend: str = "api",
    bearer_token: str = "",
    api_key: str = "",
    api_host: str = "twitter-api45.p.rapidapi.com",
    nitter_instances: list[str] | None = None,
    since_hours: int = 24,
    max_tweets_per_user: int = 20,
) -> list[dict]:
    """Fetch tweets from all accounts, deduplicate by tweet_id."""
    all_tweets = []
    seen_ids = set()

    for username in accounts:
        print(f"[{backend}] Fetching tweets for @{username}...")
        tweets = []

        if backend == "api":
            tweets = fetch_user_tweets_api(username, bearer_token, since_hours, max_tweets_per_user)
        elif backend == "rapidapi":
            tweets = fetch_user_tweets_rapidapi(username, api_key, api_host, since_hours, max_tweets_per_user)
        elif backend == "nitter":
            tweets = fetch_user_tweets_nitter(username, nitter_instances, since_hours, max_tweets_per_user)
        else:
            print(f"Unknown backend: {backend}")
            continue

        for tweet in tweets:
            tid = tweet["tweet_id"]
            if tid not in seen_ids:
                seen_ids.add(tid)
                all_tweets.append(tweet)

        print(f"  -> {len(tweets)} tweets from @{username}")

    print(f"[{backend}] Total: {len(all_tweets)} unique tweets from {len(accounts)} accounts")
    return all_tweets

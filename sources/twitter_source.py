import argparse
import json
import os

from base_source import BaseSource
from config import LLMConfig, CommonConfig
from fetchers.twitter_fetcher import load_accounts, fetch_all_accounts
from email_utils.base_template import get_stars
from email_utils.twitter_template import get_tweet_block_html


class TwitterSource(BaseSource):
    name = "twitter"
    default_title = "Daily X/Twitter"

    def __init__(self, source_args: dict, llm_config: LLMConfig, common_config: CommonConfig):
        super().__init__(source_args, llm_config, common_config)
        self.backend = source_args.get("backend", "api")
        self.bearer_token = source_args.get("bearer_token", "")
        self.api_key = source_args.get("api_key", "")
        self.api_host = source_args.get("api_host", "twitter-api45.p.rapidapi.com")
        self.nitter_instances = source_args.get("nitter_instances", None)
        self.since_hours = source_args.get("since_hours", 24)
        self.max_tweets_per_user = source_args.get("max_tweets_per_user", 20)
        self.max_tweets = source_args.get("max_tweets", 50)
        self.skip_retweets = source_args.get("skip_retweets", True)
        self.include_replies = source_args.get("include_replies", False)

        # Load accounts and prefetch tweets
        accounts_file = source_args.get("accounts_file", "x_accounts.txt")
        self.accounts = load_accounts(accounts_file)
        if not self.accounts:
            print(f"[{self.name}] No accounts loaded from {accounts_file}")
            self.tweets = []
        else:
            print(f"[{self.name}] Loaded {len(self.accounts)} accounts from {accounts_file}")
            self.tweets = fetch_all_accounts(
                accounts=self.accounts,
                backend=self.backend,
                bearer_token=self.bearer_token,
                api_key=self.api_key,
                api_host=self.api_host,
                nitter_instances=self.nitter_instances,
                since_hours=self.since_hours,
                max_tweets_per_user=self.max_tweets_per_user,
            )
            print(f"[{self.name}] {len(self.tweets)} tweets prefetched")

    @staticmethod
    def add_arguments(parser: argparse.ArgumentParser):
        parser.add_argument(
            "--x_accounts_file", type=str, default="x_accounts.txt",
            help="[Twitter] Path to accounts list file",
        )
        parser.add_argument(
            "--x_backend", type=str, choices=["api", "rapidapi", "nitter"], default="api",
            help="[Twitter] Backend to use for fetching tweets",
        )
        parser.add_argument(
            "--x_bearer_token", type=str, default="",
            help="[Twitter] Bearer token for Twitter API v2",
        )
        parser.add_argument(
            "--x_api_key", type=str, default="",
            help="[Twitter] RapidAPI key",
        )
        parser.add_argument(
            "--x_api_host", type=str, default="twitter-api45.p.rapidapi.com",
            help="[Twitter] RapidAPI host",
        )
        parser.add_argument(
            "--x_nitter_instances", nargs="+", default=None,
            help="[Twitter] Nitter instances for RSS fetching",
        )
        parser.add_argument(
            "--x_since_hours", type=int, default=24,
            help="[Twitter] Fetch tweets from the last N hours",
        )
        parser.add_argument(
            "--x_max_tweets_per_user", type=int, default=20,
            help="[Twitter] Max tweets to fetch per user",
        )
        parser.add_argument(
            "--x_max_tweets", type=int, default=50,
            help="[Twitter] Max total tweets to recommend",
        )
        parser.add_argument(
            "--x_skip_retweets", action="store_true", default=True,
            help="[Twitter] Skip retweets (default: True)",
        )
        parser.add_argument(
            "--x_no_skip_retweets", dest="x_skip_retweets", action="store_false",
            help="[Twitter] Include retweets",
        )
        parser.add_argument(
            "--x_include_replies", action="store_true", default=False,
            help="[Twitter] Include replies (default: False)",
        )

    @staticmethod
    def extract_args(args) -> dict:
        return {
            "accounts_file": args.x_accounts_file,
            "backend": args.x_backend,
            "bearer_token": args.x_bearer_token,
            "api_key": args.x_api_key,
            "api_host": args.x_api_host,
            "nitter_instances": args.x_nitter_instances,
            "since_hours": args.x_since_hours,
            "max_tweets_per_user": args.x_max_tweets_per_user,
            "max_tweets": args.x_max_tweets,
            "skip_retweets": args.x_skip_retweets,
            "include_replies": args.x_include_replies,
        }

    def fetch_items(self) -> list[dict]:
        filtered = []
        for tweet in self.tweets:
            if self.skip_retweets and tweet.get("is_retweet", False):
                continue
            if not self.include_replies and tweet.get("is_reply", False):
                continue
            filtered.append(tweet)
        print(f"[{self.name}] {len(filtered)} tweets after filtering (skip_retweets={self.skip_retweets}, include_replies={self.include_replies})")
        return filtered

    def build_eval_prompt(self, item: dict) -> str:
        prompt = """
            你是一个有帮助的AI助手，帮助我追踪Twitter/X上的重要动态。
            以下是我感兴趣的领域描述：
            {}
        """.format(self.description)

        # Build tweet context
        tweet_context = f"""
            以下是一条来自 @{item['author_username']} 的推文：
            内容: {item['text']}
            互动数据: ❤️ {item.get('likes', 0)} | 🔁 {item.get('retweets', 0)} | 💬 {item.get('replies', 0)}
        """
        if item.get("is_quote") and item.get("quoted_text"):
            tweet_context += f"""
            引用推文 (@{item.get('quoted_author', 'unknown')}): {item['quoted_text']}
            """

        prompt += tweet_context
        prompt += """
            请评估这条推文：
            1. 用中文简要总结这条推文的核心内容（1-2句话）。
            2. 判断推文类型：观点/新闻/讨论/分享/公告/日常。
            3. 评估这条推文与我兴趣领域的相关性，并给出 0-10 的评分。其中 0 表示完全不相关，10 表示高度相关。
            4. 列出 1-3 个关键要点。

            请按以下 JSON 格式给出你的回答：
            {
                "summary": <你的中文总结>,
                "category": <观点/新闻/讨论/分享/公告/日常>,
                "relevance": <你的评分>,
                "key_points": [<要点1>, <要点2>]
            }
            使用中文回答。
            直接返回上述 JSON 格式，无需任何额外解释。
        """
        return prompt

    def parse_eval_response(self, item: dict, response: str) -> dict:
        response = response.strip("```").strip("json")
        data = json.loads(response)
        return {
            "title": f"@{item['author_username']}: {item['text'][:60]}",
            "tweet_id": item["tweet_id"],
            "text": item["text"],
            "author_username": item["author_username"],
            "author_name": item.get("author_name", item["author_username"]),
            "created_at": item.get("created_at", ""),
            "likes": item.get("likes", 0),
            "retweets": item.get("retweets", 0),
            "replies": item.get("replies", 0),
            "is_retweet": item.get("is_retweet", False),
            "is_reply": item.get("is_reply", False),
            "is_quote": item.get("is_quote", False),
            "quoted_text": item.get("quoted_text", ""),
            "quoted_author": item.get("quoted_author", ""),
            "summary": data["summary"],
            "category": data.get("category", "日常"),
            "score": float(data["relevance"]),
            "key_points": data.get("key_points", []),
            "url": item.get("tweet_url", ""),
        }

    def render_item_html(self, item: dict) -> str:
        rate = get_stars(item.get("score", 0))
        return get_tweet_block_html(
            author_username=item["author_username"],
            author_name=item.get("author_name", item["author_username"]),
            rate=rate,
            text=item["text"],
            summary=item["summary"],
            category=item.get("category", "日常"),
            tweet_url=item.get("url", ""),
            likes=item.get("likes", 0),
            retweets=item.get("retweets", 0),
            replies=item.get("replies", 0),
            is_retweet=item.get("is_retweet", False),
            is_reply=item.get("is_reply", False),
            is_quote=item.get("is_quote", False),
            quoted_text=item.get("quoted_text", ""),
            quoted_author=item.get("quoted_author", ""),
        )

    def get_item_cache_id(self, item: dict) -> str:
        return f"tweet_{item['tweet_id']}"

    def get_section_header(self) -> str:
        return '<div class="section-title" style="border-bottom-color: #1d9bf0;">𝕏 X/Twitter Daily</div>'

    def get_theme_color(self) -> str:
        return "29,155,240"

    def get_max_items(self) -> int:
        return self.max_tweets

    def build_summary_overview(self, recommendations: list[dict]) -> str:
        overview = ""
        for i, r in enumerate(recommendations):
            engagement = f"❤️ {r.get('likes', 0)} | 🔁 {r.get('retweets', 0)} | 💬 {r.get('replies', 0)}"
            overview += f"{i + 1}. @{r['author_username']} [{r.get('category', '')}] - {r['summary']} ({engagement})\n"
        return overview

    def get_summary_prompt_template(self) -> str:
        return """
            请直接输出一段 HTML 片段，严格遵循以下结构，不要包含 JSON、Markdown 或多余说明：
            <div class="summary-wrapper">
              <div class="summary-section">
                <h2>今日动态概览</h2>
                <p>总结今天关注的 X/Twitter 大V 的主要动态和讨论热点...</p>
              </div>
              <div class="summary-section">
                <h2>重点推文</h2>
                <ol class="summary-list">
                  <li class="summary-item">
                    <div class="summary-item__header"><span class="summary-item__title">@用户名: 推文摘要</span><span class="summary-pill">类型</span></div>
                    <p><strong>推荐理由：</strong>...</p>
                    <p><strong>关键亮点：</strong>...</p>
                  </li>
                </ol>
              </div>
              <div class="summary-section">
                <h2>补充观察</h2>
                <p>值得关注的讨论趋势或新兴话题...</p>
              </div>
            </div>

            用中文撰写内容，重点推文部分建议返回 3-5 条。
        """

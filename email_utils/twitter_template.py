def get_category_badge(category: str) -> str:
    """Return a colored badge for tweet category."""
    colors = {
        "观点": ("#7c3aed", "#ede9fe"),
        "新闻": ("#dc2626", "#fef2f2"),
        "讨论": ("#2563eb", "#eff6ff"),
        "分享": ("#059669", "#ecfdf5"),
        "公告": ("#d97706", "#fffbeb"),
        "日常": ("#6b7280", "#f3f4f6"),
    }
    fg, bg = colors.get(category, ("#6b7280", "#f3f4f6"))
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;'
        f'font-size:12px;font-weight:600;color:{fg};background-color:{bg};">'
        f'{category}</span>'
    )


def format_engagement(likes: int, retweets: int, replies: int) -> str:
    """Format engagement metrics as a compact string."""
    parts = []
    if likes:
        parts.append(f"❤️ {likes}")
    if retweets:
        parts.append(f"🔁 {retweets}")
    if replies:
        parts.append(f"💬 {replies}")
    return " &nbsp; ".join(parts) if parts else ""


def get_tweet_block_html(
    author_username: str,
    author_name: str,
    rate: str,
    text: str,
    summary: str,
    category: str,
    tweet_url: str,
    likes: int = 0,
    retweets: int = 0,
    replies: int = 0,
    is_retweet: bool = False,
    is_reply: bool = False,
    is_quote: bool = False,
    quoted_text: str = "",
    quoted_author: str = "",
) -> str:
    """Render a single tweet card as an HTML block."""
    # Type label
    type_parts = [f"@{author_username}"]
    if is_retweet:
        type_parts.append("🔁 转推")
    elif is_reply:
        type_parts.append("💬 回复")
    elif is_quote:
        type_parts.append("📎 引用")
    type_label = " · ".join(type_parts)

    # Truncate text at 280 chars
    display_text = text[:280] + "..." if len(text) > 280 else text
    display_text = display_text.replace("\n", "<br>")

    # Category badge
    badge = get_category_badge(category)

    # Engagement
    engagement = format_engagement(likes, retweets, replies)
    engagement_row = ""
    if engagement:
        engagement_row = f"""
    <tr>
        <td style="font-size:13px;color:#6b7280;padding:6px 0;">
            {engagement}
        </td>
    </tr>"""

    # Quoted tweet block
    quote_block = ""
    if is_quote and quoted_text:
        qt_display = quoted_text[:200] + "..." if len(quoted_text) > 200 else quoted_text
        qt_display = qt_display.replace("\n", "<br>")
        quote_block = f"""
    <tr>
        <td style="padding:8px 0;">
            <table border="0" cellpadding="0" cellspacing="0" width="100%"
                   style="border-left:3px solid #1d9bf0;padding:8px 12px;background-color:#f0f9ff;border-radius:4px;">
                <tr><td style="font-size:12px;color:#1d9bf0;font-weight:600;">@{quoted_author}</td></tr>
                <tr><td style="font-size:13px;color:#555;padding-top:4px;">{qt_display}</td></tr>
            </table>
        </td>
    </tr>"""

    block_template = f"""
    <table border="0" cellpadding="0" cellspacing="0" width="100%"
           style="font-family:Arial,sans-serif;border:1px solid #d1e9fa;border-radius:8px;padding:16px;background-color:#e8f5fd;">
    <tr>
        <td style="font-size:15px;font-weight:600;color:#1d9bf0;padding-bottom:4px;">
            {type_label} &nbsp; {badge}
        </td>
    </tr>
    <tr>
        <td style="font-size:14px;color:#333;padding:4px 0;">
            <strong>Relevance:</strong> {rate}
        </td>
    </tr>
    <tr>
        <td style="font-size:14px;color:#333;padding:8px 0;line-height:1.6;">
            {display_text}
        </td>
    </tr>{quote_block}{engagement_row}
    <tr>
        <td style="font-size:14px;color:#333;padding:8px 0;">
            <strong>AI Summary:</strong> {summary}
        </td>
    </tr>
    <tr>
        <td style="padding:8px 0;">
            <a href="{tweet_url}"
               style="display:inline-block;text-decoration:none;font-size:14px;font-weight:bold;color:#fff;background-color:#1d9bf0;padding:8px 16px;border-radius:4px;">
               View on X
            </a>
        </td>
    </tr>
    </table>
"""
    return block_template

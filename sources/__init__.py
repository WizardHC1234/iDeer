from sources.github_source import GitHubSource
from sources.huggingface_source import HuggingFaceSource
from sources.twitter_source import TwitterSource

SOURCE_REGISTRY = {
    "github": GitHubSource,
    "huggingface": HuggingFaceSource,
    "twitter": TwitterSource,
}

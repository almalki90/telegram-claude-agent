from .gemini import GeminiProvider
from .deepseek import DeepSeekProvider
from .openai_provider import OpenAIProvider
from .claude_provider import ClaudeProvider

PROVIDERS = {
    "gemini": GeminiProvider,
    "deepseek": DeepSeekProvider,
    "openai": OpenAIProvider,
    "claude": ClaudeProvider,
}

PROVIDER_INFO = {
    "gemini": {"name":"Google Gemini","emoji":"🟢","models":["gemini-2.5-flash-lite","gemini-2.5-flash","gemini-2.0-flash"],"default_model":"gemini-2.5-flash-lite","test_url":"https://aistudio.google.com/app/apikey","free":True},
    "deepseek": {"name":"DeepSeek","emoji":"🔵","models":["deepseek-chat","deepseek-reasoner"],"default_model":"deepseek-chat","test_url":"https://platform.deepseek.com","free":False},
    "openai": {"name":"OpenAI GPT","emoji":"⚫","models":["gpt-4o-mini","gpt-4o"],"default_model":"gpt-4o-mini","test_url":"https://platform.openai.com","free":False},
    "claude": {"name":"Anthropic Claude","emoji":"🟠","models":["claude-3-5-haiku-20241022","claude-3-5-sonnet-20241022"],"default_model":"claude-3-5-haiku-20241022","test_url":"https://console.anthropic.com","free":False},
}

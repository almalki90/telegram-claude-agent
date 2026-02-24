import sys, logging
sys.path.insert(0, '/home/user/tgbot')
from providers import PROVIDERS, PROVIDER_INFO
import storage

logger = logging.getLogger(__name__)

SYSTEM = """You are an intelligent Arabic-speaking assistant specializing in server management.
Your name is "الوكيل" (The Agent).

Personality: smart, friendly, speaks Arabic naturally, executes directly without asking permission.

Tools available: SSH, HTTP, shell commands, files, databases (MySQL/PostgreSQL), system info.

Rules:
- Execute immediately when requested
- Tell the user what you're doing step by step
- If you need missing info (like a password), ask for it
- Report results clearly in Arabic"""

class Agent:
    def get_provider(self, uid):
        p = storage.get_active_provider(uid)
        if not p: return None, None
        k = storage.get_api_key(uid, p)
        if not k: return None, None
        cls = PROVIDERS.get(p)
        if not cls: return None, None
        info = PROVIDER_INFO.get(p, {})
        m = storage.get_active_model(uid) or info.get("default_model","")
        return cls(api_key=k, model=m), p

    def test_key(self, uid, provider, api_key, model=None):
        cls = PROVIDERS.get(provider)
        if not cls: return False, f"unknown provider: {provider}"
        info = PROVIDER_INFO.get(provider, {})
        return cls(api_key=api_key, model=model or info.get("default_model","")).test_key()

    def generate(self, uid, msg):
        prov, _ = self.get_provider(uid)
        if not prov: return None
        ctx = storage.get_context(uid)
        ctx.append({"role":"user","content":msg})
        try:
            resp = prov.generate(ctx, SYSTEM)
            storage.save_context(uid, "user", msg)
            storage.save_context(uid, "assistant", resp)
            return resp
        except Exception as e:
            logger.error(f"generate error: {e}", exc_info=True)
            return f"error: {str(e)[:200]}"

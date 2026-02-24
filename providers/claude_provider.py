import sys, logging
sys.path.insert(0, '/home/user/tgbot')
from tools import TOOLS_SCHEMA, execute_tool
logger = logging.getLogger(__name__)

class ClaudeProvider:
    def __init__(self, api_key, model="claude-3-5-haiku-20241022"):
        self.api_key = api_key
        self.model = model

    def _tools(self):
        return [{"name":t["name"],"description":t["description"],"input_schema":t["parameters"]} for t in TOOLS_SCHEMA]

    def test_key(self):
        try:
            import anthropic
            c = anthropic.Anthropic(api_key=self.api_key)
            r = c.messages.create(model=self.model, max_tokens=50, messages=[{"role":"user","content":"say: hi"}])
            return True, r.content[0].text[:100]
        except Exception as e: return False, str(e)[:200]

    def generate(self, messages, system_prompt=""):
        try:
            import anthropic
            c = anthropic.Anthropic(api_key=self.api_key)
            msgs = list(messages)
            for _ in range(5):
                kw = {"model":self.model,"max_tokens":4096,"messages":msgs,"tools":self._tools()}
                if system_prompt: kw["system"] = system_prompt
                r = c.messages.create(**kw)
                if r.stop_reason != "tool_use":
                    return "".join(b.text for b in r.content if hasattr(b,"text")) or "no response"
                msgs.append({"role":"assistant","content":r.content})
                results = [{"type":"tool_result","tool_use_id":b.id,"content":execute_tool(b.name,b.input)} for b in r.content if b.type=="tool_use"]
                msgs.append({"role":"user","content":results})
            return "max iterations exceeded"
        except Exception as e: return f"error: {str(e)[:300]}"

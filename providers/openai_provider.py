import sys, logging, json
sys.path.insert(0, '/home/user/tgbot')
from tools import TOOLS_SCHEMA, execute_tool
logger = logging.getLogger(__name__)

class OpenAIProvider:

    def __init__(self, api_key, model="gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def _tools(self):
        return [{"type":"function","function":{"name":t["name"],"description":t["description"],"parameters":t["parameters"]}} for t in TOOLS_SCHEMA]

    def test_key(self):
        try:
            from openai import OpenAI
            c = OpenAI(api_key=self.api_key)
            r = c.chat.completions.create(model=self.model, messages=[{"role":"user","content":"say: hi"}], max_tokens=50)
            return True, r.choices[0].message.content[:100]
        except Exception as e: return False, str(e)[:200]

    def generate(self, messages, system_prompt=""):
        try:
            from openai import OpenAI
            c = OpenAI(api_key=self.api_key)
            msgs = []
            if system_prompt: msgs.append({"role":"system","content":system_prompt})
            msgs.extend(messages)
            for _ in range(5):
                r = c.chat.completions.create(model=self.model, messages=msgs, tools=self._tools(), tool_choice="auto", max_tokens=4096)
                msg = r.choices[0].message
                if r.choices[0].finish_reason != "tool_calls" or not msg.tool_calls:
                    return msg.content or "no response"
                msgs.append({"role":"assistant","content":msg.content,"tool_calls":[{"id":tc.id,"type":"function","function":{"name":tc.function.name,"arguments":tc.function.arguments}} for tc in msg.tool_calls]})
                for tc in msg.tool_calls:
                    try: args = json.loads(tc.function.arguments)
                    except: args = {}
                    msgs.append({"role":"tool","tool_call_id":tc.id,"content":execute_tool(tc.function.name,args)})
            return "max iterations exceeded"
        except Exception as e: return f"error: {str(e)[:300]}"

import sys, logging
sys.path.insert(0, '/home/user/tgbot')
from tools import TOOLS_SCHEMA, execute_tool
logger = logging.getLogger(__name__)

class GeminiProvider:
    def __init__(self, api_key, model="gemini-2.5-flash-lite"):
        self.api_key = api_key
        self.model = model
        self._g = None

    def _setup(self):
        if not self._g:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._g = genai
        return self._g

    def _decls(self):
        decls = []
        for t in TOOLS_SCHEMA:
            props = {}
            for k,v in t["parameters"].get("properties",{}).items():
                pt = v.get("type","string").upper()
                if pt == "INTEGER": pt = "NUMBER"
                p = {"type": pt}
                if "description" in v: p["description"] = v["description"]
                props[k] = p
            decls.append({"name":t["name"],"description":t["description"],"parameters":{"type":"OBJECT","properties":props,"required":t["parameters"].get("required",[])}})
        return decls

    def test_key(self):
        try:
            g = self._setup()
            r = g.GenerativeModel(self.model).generate_content("say: hi")
            return True, r.text.strip()[:100]
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "RESOURCE_EXHAUSTED" in err:
                for m in ["gemini-2.0-flash","gemini-2.5-flash"]:
                    try:
                        r2 = self._setup().GenerativeModel(m).generate_content("say: hi")
                        self.model = m
                        return True, f"{r2.text.strip()[:80]} (switched to {m})"
                    except: pass
                return True, "key valid (quota temporarily exhausted)"
            return False, err[:200]

    def generate(self, messages, system_prompt=""):
        try:
            g = self._setup()
            decls = self._decls()
            model = g.GenerativeModel(model_name=self.model, system_instruction=system_prompt or None, tools=decls or None)
            history = [{"role":"model" if m["role"]=="assistant" else "user","parts":[m["content"]]} for m in messages[:-1]]
            chat = model.start_chat(history=history)
            last = messages[-1]["content"] if messages else ""
            response = chat.send_message(last)
            for _ in range(5):
                calls = []
                try:
                    for cand in response.candidates:
                        for part in cand.content.parts:
                            if hasattr(part,"function_call") and part.function_call:
                                fc = part.function_call
                                args = dict(fc.args) if hasattr(fc,"args") else {}
                                calls.append({"name":fc.name,"args":args})
                except: pass
                if not calls: break
                tool_resp = [{"function_response":{"name":c["name"],"response":{"result":execute_tool(c["name"],c["args"])}}} for c in calls]
                response = chat.send_message(tool_resp)
            try: return response.text or "no response"
            except:
                text=""
                for cand in response.candidates:
                    for part in cand.content.parts:
                        if hasattr(part,"text") and part.text: text+=part.text
                return text or "no response"
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower(): return "⚠️ Gemini quota exceeded. Wait a minute."
            return f"Gemini error: {err[:300]}"

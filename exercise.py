import json

class ReactAgent:
    def __init__(self, llm_client, tools: dict, max_tokens: int=65536, max_steps: int=5):
        self.llm = llm_client
        self.tools = tools
        self.max_tokens = max_tokens
        self.max_steps = max_steps
        self.messages = []
        self.total_tokens = 0
        
    def run(self, user_query: str) -> str:
        self.messages = [{"role": "user", "content": user_query}]
        for step in range(0, self.max_steps):
            if self.total_tokens > self.max_tokens:
                return "Token up to the limits"
            
            response = self.llm.chat(self.messages)
            self.total_tokens += response.get("usage", 0)
            content = response["content"]
            
            if not response.get("tool_calls"):
                return content
            
            for tool_call in response["tool_calls"]:
                tool_name = tool_call["func"]["name"]
                tool_args = json.loads(tool_call["func"]["args"])
                
                try:
                    result = tool_call[tool_name](**tool_args)
                except Exception as e:
                    result = f"error: {tool_name} -- {str(result)}"
                
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": str(result)
                })
        return f"Agent did not finish in {str(self.max_steps)} steps"
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.mcp import MCPServerSSE
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ThinkingPart
from openai.types import chat
import asyncio
import logging
import re
import json
import uuid
import datetime
from pydantic_ai.profiles.openai import OpenAIModelProfile
import logfire
from pydantic_ai.settings import ModelSettings

logfire.configure()
logfire.instrument_pydantic_ai()

logging.basicConfig(level=logging.INFO)

settings = ModelSettings(
    max_steps=4,
    temperature=0.7,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0,
)

class MistralReasoningModel(OpenAIChatModel):
    """OpenAIChatModel that parses [TOOL_CALLS] from text/thinking responses."""
    
    def _parse_tool_calls_from_text(self, content: str) -> tuple[str, list[ToolCallPart]]:
        """Extract tool calls from Mistral's text format."""
        tool_calls = []
        
        # Better pattern that handles nested braces by finding balanced JSON
        # Match [TOOL_CALLS]tool_name followed by JSON object
        pattern = r'\[TOOL_CALLS\](\w+)'
        
        pos = 0
        clean_content = content
        
        for match in re.finditer(pattern, content):
            tool_name = match.group(1)
            json_start = match.end()
            
            # Find the JSON object starting at json_start
            if json_start < len(content) and content[json_start] == '{':
                # Find matching closing brace
                brace_count = 0
                json_end = json_start
                for i in range(json_start, len(content)):
                    if content[i] == '{':
                        brace_count += 1
                    elif content[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                args_str = content[json_start:json_end]
                
                try:
                    args = json.loads(args_str)
                    tool_calls.append(ToolCallPart(
                        tool_name=tool_name,
                        args=args,
                        tool_call_id=f"tc_{uuid.uuid4().hex[:12]}"
                    ))
                    logging.info(f"Parsed tool call: {tool_name} with args: {args}")
                except json.JSONDecodeError as e:
                    logging.warning(f"Failed to parse tool call JSON: {args_str}, error: {e}")
        
        # Remove all [TOOL_CALLS]... patterns from content
        clean_content = re.sub(r'\[TOOL_CALLS\]\w+\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', '', content)
        clean_content = clean_content.strip()
        
        return clean_content, tool_calls
    
    def _process_response(self, response: chat.ChatCompletion) -> ModelResponse:
        """Override to intercept and parse text-based tool calls from thinking parts."""
        model_response = super()._process_response(response)
        
        new_parts = []
        found_tool_calls = False
        
        for part in model_response.parts:
            content = None
            
            # Check BOTH TextPart and ThinkingPart
            if isinstance(part, TextPart) and '[TOOL_CALLS]' in part.content:
                content = part.content
            elif isinstance(part, ThinkingPart) and part.content and '[TOOL_CALLS]' in part.content:
                content = part.content
            
            if content:
                logging.info(f"Found [TOOL_CALLS] in content: {content[:100]}...")
                clean_content, parsed_tool_calls = self._parse_tool_calls_from_text(content)
                
                if parsed_tool_calls:
                    found_tool_calls = True
                    new_parts.extend(parsed_tool_calls)
                    logging.info(f"Extracted {len(parsed_tool_calls)} tool calls")
                
                # Keep remaining content as text if any
                if clean_content:
                    new_parts.append(TextPart(content=clean_content))
            else:
                new_parts.append(part)
        
        if found_tool_calls:
            logging.info(f"Returning modified response with {len(new_parts)} parts")
            return ModelResponse(
                parts=new_parts,
                usage=model_response.usage,
                model_name=model_response.model_name,
                timestamp=model_response.timestamp,
                provider_response_id=model_response.provider_response_id, 
            )
        
        return model_response

mistral_profile = OpenAIModelProfile(
    thinking_tags=('[THINK]', '[/THINK]'),  # Custom thinking tags
    openai_chat_thinking_field='reasoning',
    #openai_chat_send_back_thinking_parts='text',
)
model = MistralReasoningModel(
    'mistralai/Ministral-3-14B-Reasoning-2512',
    provider=OpenAIProvider(
        base_url='https://model-gateway.remodl.ai/api/public/test/ministral-reasoning/v1',
        api_key='2158fc51-e632-441c-97e2-af334e26e656'
    ),
    profile=mistral_profile,
)

instructions = """
Today is 12/15/2025

# HOW YOU SHOULD THINK AND ANSWER

First draft your thinking process (inner monologue) until you arrive at a response. Format your response using Markdown, and use LaTeX for any mathematical equations. Write both your thoughts and the response in the same language as the input.

Your thinking process must follow the template below:[THINK]Your thoughts or/and draft, like working through an exercise on scratch paper. Be as casual and as long as you want until you are confident to generate the response to the user.[/THINK]Here, provide a self-contained response.
You must wrap your reasoning in the [THINK] and [/THINK] tags. Do not include your final answer in the [THINK] tags. It should be separate
"""


server = MCPServerSSE('http://mcp.remodl.ai/sse')
agent = Agent(model=model, toolsets=[server], instructions=instructions, model_settings=settings)


async def main():
    result = await agent.run('what is the weather in Freeport, Maine?')
    print(result.output)

asyncio.run(main())
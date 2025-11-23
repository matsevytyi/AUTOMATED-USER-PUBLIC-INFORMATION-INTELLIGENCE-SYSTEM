"""Simple LLM abstraction with pluggable providers.

This module exposes `chat_with_context(provider, messages, context, **opts)` which
returns a dict: { 'reply': str, 'sources': [...] }.

Currently providers are implemented as lightweight adapters. If the chosen
provider is unavailable the function will fall back to a prioritized list.
"""
from typing import List, Dict, Any
import os
import json
from datetime import datetime


def _stub_response(messages: List[Dict[str, Any]], context: List[Dict[str, str]]) -> Dict[str, Any]:
	# Build a simple echo/summary response for testing
	user_msg = messages[-1]['content'] if messages else ''
	ctx_preview = '\n'.join([c.get('snippet', '')[:200] for c in (context or [])][:5])
	reply = f"(stub) Based on the provided context:\n{ctx_preview}\n\nAnswer: {user_msg[:500]}"
	# Accept either 'id' (preferred) or legacy 'piece_id' to be tolerant
	sources = [ (c.get('id') or c.get('piece_id')) for c in (context or []) if (c.get('id') or c.get('piece_id')) ]
	return {'reply': reply, 'sources': sources}


def chat_with_context(provider: str, messages: List[Dict[str, Any]], context: List[Dict[str, Any]], fallback: List[str] = None, **opts) -> Dict[str, Any]:
	"""Dispatch a chat request to a provider. Returns {'reply': str, 'sources': [...]}

	- provider: provider id requested ('groq','openai','local')
	- messages: list of {'role': 'user'|'assistant'|'system', 'content': '...'}
	- context: list of datapiece dicts with keys like ['id'|'piece_id','snippet','source_ref','title']
	- fallback: list of provider ids to try if primary fails
	"""
	providers = [provider] + (fallback or [])
	# For now, try providers but only stub is implemented. If OPENAI key present and provider==openai,
	# an actual OpenAI call could be attempted. We intentionally keep this modular.

	# Attempt each provider (stubbed)
	for p in providers:
		try:
			if p == 'openai':
				# Try real OpenAI if key present
				api_key = os.environ.get('OPENAI_API_KEY') or os.environ.get('OPENAI_KEY')
				if api_key:
					try:
						import openai
						openai.api_key = api_key
						# Build chat messages (system+messages)
						resp = openai.ChatCompletion.create(
							model=os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo'),
							messages=messages,
							temperature=float(os.environ.get('OPENAI_TEMPERATURE', 0.2)),
							max_tokens=int(os.environ.get('OPENAI_MAX_TOKENS', 512))
						)
						text = resp['choices'][0]['message']['content']
						# No source extraction by default
						return {'reply': text, 'sources': []}
					except Exception:
						# Fall back to stub
						continue
				else:
					continue
			elif p == 'groq':
				# GROQ provider not implemented yet; skip to stub
				continue
			elif p == 'local':
				# Local LLM API can be implemented later; skip for now
				continue
			else:
				# Unknown provider — skip
				continue
		except Exception:
			# Try next provider
			continue

	# If all providers fail or none configured, return a stubbed response
	return _stub_response(messages, context)


if __name__ == '__main__':
	# quick manual test
	print(chat_with_context('openai', [{'role':'user','content':'Hello'}], [{'id': 1, 'snippet':'sample context'}]))
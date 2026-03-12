"""JARVIS Core Module"""
import logging
import re
import threading
import signal
import time
import platform
from typing import Dict, List, Optional, Tuple, Callable
from collections import deque

from jarvis_config import (
    OLLAMA_URL,
    MODELS,
    MAX_HISTORY,
    RATE_LIMIT_SECONDS,
    SMALLTALK_PATTERNS,
    SWARM_ENABLED,
    SWARM_TIMEOUT_SECONDS,
    SWARM_COMPLEXITY_THRESHOLD,
    SWARM_COMPLEXITY_INDICATORS,
)
import jarvis_config as _cfg
from jarvis_config.dynamic import apply_hardware_scaling
from jarvis_memory import CognitiveMemory
from jarvis_tools import create_tool_class, TOOLS_SCHEMA, validate_tool_params
from jarvis_reasoning import ReActLoop
from jarvis_reasoning.swarm import SwarmManager

logger = logging.getLogger("JARVIS.CORE")
_emergency_stop = threading.Event()

# Apply hardware scaling FIRST
hw_info = apply_hardware_scaling()

# Update global config with hardware-detected values
_cfg.HW_OPTIONS = hw_info["hw_options"]
_cfg.SWARM_MAX_AGENTS = hw_info["swarm_max_agents"]

logger.info(
    f"[HW] CPU=%s | RAM=%d GB | GPU=%s | VRAM=%d GB | "
    f"model=%s | ctx=%d | agents=%d",
    platform.processor(),
    hw_info['ram_gb'],
    hw_info['gpu_name'],
    hw_info['vram_gb'],
    MODELS.get('reasoner', 'unknown'),
    hw_info['hw_options'].get('num_ctx', 0),
    hw_info['swarm_max_agents'],
)


def _handle_sigint(sig, frame):
    _emergency_stop.set()
    print("\n\n🛑 Emergency Stop")


signal.signal(signal.SIGINT, _handle_sigint)


def check_stop():
    return _emergency_stop.is_set()


class RateLimiter:
    def __init__(self, max_requests=10, window_seconds=60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests = deque()
        self._lock = threading.Lock()

    def is_allowed(self) -> Tuple[bool, int]:
        with self._lock:
            now = time.time()
            while self.requests and now - self.requests[0] > self.window:
                self.requests.popleft()
            remaining = self.max_requests - len(self.requests)
            if len(self.requests) >= self.max_requests:
                return False, max(1, int(self.window - (now - self.requests[0])))
            self.requests.append(now)
            return True, remaining - 1


class CzechBridgeClient:
    MAX_CACHE_SIZE = 200

    def __init__(self):
        self.rate_limiter = RateLimiter()
        self._translation_cache = {}
        self._cache_order = []

    def call_json(
        self, model_role: str, messages: List[Dict], system_prompt: str = "", options: Dict = None
    ) -> Optional[Dict]:
        allowed, _ = self.rate_limiter.is_allowed()
        if not allowed:
            return {"error": "rate_limited", "message": "Too many requests"}
        
        options = options or {}
        import requests
        import json_repair
        import json

        payload = {
            "model": MODELS[model_role],
            "messages": (
                [{"role": "system", "content": system_prompt}] + messages
                if system_prompt
                else messages
            ),
            "stream": False,
            "options": {**_cfg.HW_OPTIONS, **options},
        }
        
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            # Parse JSON
            try:
                content = result["message"]["content"]
                return json_repair.loads(content)
            except (json.JSONDecodeError, KeyError) as e:
                logger.error("JSON parse error: %s", e)
                return {"error": "json_parse_error", "message": str(e)}
                
        except requests.exceptions.RequestException as e:
            logger.error("Network error in call_json: %s", e)
            return {"error": "network_failure", "message": str(e)}
        except Exception as e:
            logger.error("Unexpected error in call_json: %s", e)
            return {"error": "unknown_error", "message": str(e)}

    def call_stream(
        self, model_role: str, messages: List[Dict], system_prompt: str = "", callback: Callable = None
    ):
        allowed, _ = self.rate_limiter.is_allowed()
        if not allowed:
            if callback:
                callback("Rate limited")
            return None
        try:
            import requests
            import json

            payload = {
                "model": MODELS[model_role],
                "messages": (
                    [{"role": "system", "content": system_prompt}] + messages
                    if system_prompt
                    else messages
                ),
                "stream": True,
                "options": _cfg.HW_OPTIONS,
            }
            r = requests.post(OLLAMA_URL, json=payload, stream=True, timeout=60)
            if r.status_code == 200:
                full = ""
                for line in r.iter_lines():
                    if line:
                        try:
                            data = json.loads(line.decode("utf-8"))
                            if not data.get("done"):
                                content = data.get("message", {}).get("content", "")
                                full += content
                                if callback:
                                    callback(content)
                        except Exception:
                            pass
                return full
        except Exception as e:
            if callback:
                callback(f"Error: {e}")
        return None

    def translate_to_en(self, text: str) -> str:
        """Translate Czech text to English using czech_gateway model."""
        cache_key = hash(text + "_en")

        if cache_key in self._translation_cache:
            logger.debug("[CACHE] Translation hit")
            self._cache_order.remove(cache_key)
            self._cache_order.append(cache_key)
            return self._translation_cache[cache_key]

        try:
            import requests

            system_prompt = "You are a translator. Translate the following Czech text to English. Return ONLY the translation, nothing else."
            payload = {
                "model": MODELS["czech_gateway"],
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                "stream": False,
                "options": _cfg.HW_OPTIONS,
            }
            r = requests.post(OLLAMA_URL, json=payload, timeout=30)
            if r.status_code == 200:
                result = str(r.json()["message"]["content"]).strip()
                self._translation_cache[cache_key] = result
                self._cache_order.append(cache_key)
                if len(self._cache_order) > self.MAX_CACHE_SIZE:
                    oldest_key = self._cache_order.pop(0)
                    del self._translation_cache[oldest_key]
                return result
        except Exception as e:
            logger.debug("translate_to_en failed: %s", e)
        return text

    def translate_to_cz(self, text: str) -> str:
        """Translate English text to Czech using czech_gateway model."""
        cache_key = hash(text + "_cz")

        if cache_key in self._translation_cache:
            logger.debug("[CACHE] Translation hit")
            self._cache_order.remove(cache_key)
            self._cache_order.append(cache_key)
            return self._translation_cache[cache_key]

        try:
            import requests

            system_prompt = "You are a translator. Translate the following English text to Czech. Return ONLY the translation, nothing else."
            payload = {
                "model": MODELS["czech_gateway"],
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                "stream": False,
                "options": _cfg.HW_OPTIONS,
            }
            r = requests.post(OLLAMA_URL, json=payload, timeout=30)
            if r.status_code == 200:
                result = str(r.json()["message"]["content"]).strip()
                self._translation_cache[cache_key] = result
                self._cache_order.append(cache_key)
                if len(self._cache_order) > self.MAX_CACHE_SIZE:
                    oldest_key = self._cache_order.pop(0)
                    del self._translation_cache[oldest_key]
                return result
        except Exception as e:
            logger.debug("translate_to_cz failed: %s", e)
        return text


class JarvisV19:
    def __init__(self, streaming: bool = True):
        logger.info("Initializing JARVIS V19...")
        # Hardware scaling already applied at module import time
        logger.info(
            "Hardware configuration loaded from dynamic.py: %d agents, ctx=%d",
            _cfg.SWARM_MAX_AGENTS, _cfg.HW_OPTIONS.get('num_ctx', 0),
        )
        self.streaming = streaming
        self.bridge = CzechBridgeClient()
        self.memory = CognitiveMemory(start_consolidation=True)
        self.tools = create_tool_class(self)
        self.tool_results = {}

        # Initialize ReAct reasoning loop
        self.reasoning = ReActLoop(
            bridge=self.bridge,
            memory=self.memory,
            tools=self.tools,
            max_iterations=10,
        )

        # Initialize Swarm Manager for complex tasks
        self._swarm_manager = None
        if SWARM_ENABLED:
            self._swarm_manager = SwarmManager(
                bridge=self.bridge,
                memory=self.memory,
                tools=self.tools,
                max_agents=_cfg.SWARM_MAX_AGENTS,
                timeout_seconds=SWARM_TIMEOUT_SECONDS,
            )
            logger.info("Swarm Manager initialized: max_agents=%d", _cfg.SWARM_MAX_AGENTS)

        logger.info(f"Ready with {len(self.tools)} tools")

    def _is_complex_task(self, query: str) -> bool:
        """Determine if query is complex enough for swarm execution."""
        if not self._swarm_manager:
            return False
        return self._swarm_manager.is_complex_task(query)

    def _detect_smalltalk(self, query: str) -> bool:
        q = query.lower()
        return any(p in q for p in SMALLTALK_PATTERNS)

    def process(self, query: str, stream_callback: Callable = None) -> str:
        """
        Process a user query using ReAct reasoning loop or Swarm architecture.

        Translation Flow:
        1. CZ query is translated to EN
        2. EN query is processed by Swarm/ReAct loop
        3. EN response is translated back to CZ
        4. CZ response is returned to user

        Smalltalk is handled directly (no translation needed).
        Complex tasks use the Swarm architecture for parallel sub-agent execution.
        All other queries go through the standard ReAct reasoning loop.
        """
        self.memory.add_message("user", query)

        # Handle smalltalk directly (no translation needed)
        if self._detect_smalltalk(query):
            response = "Ahoj! Jsem JARVIS. Jak ti mohu pomoci?"
            if stream_callback:
                stream_callback(response)
            self.memory.add_message("assistant", response)
            return response

        # Step 1: Translate CZ query to EN for processing
        query_en = self.bridge.translate_to_en(query)
        logger.debug("Translated query: CZ='%s...' -> EN='%s...'", query[:50], query_en[:50])

        # Step 2: Process EN query through Swarm or ReAct loop
        # CRITICAL: stream_callback=None to prevent English thoughts from leaking to UI
        if self._swarm_manager and self._is_complex_task(query_en):
            logger.info("Using Swarm architecture for complex task")
            response_en = self._execute_swarm(query_en, stream_callback=None)
        else:
            # Use standard ReAct reasoning loop - stream_callback=None
            response_en = self.reasoning.run(query_en, stream_callback=None)

        if not response_en:
            response_en = "Done"

        # Step 3: Translate EN response back to CZ
        response_cz = self.bridge.translate_to_cz(response_en)
        logger.debug("Translated response: EN='%s...' -> CZ='%s...'", response_en[:50], response_cz[:50])

        # Step 4: Return CZ response to user with streaming
        if stream_callback:
            stream_callback(response_cz)

        self.memory.add_message("assistant", response_cz)
        return response_cz

    def _execute_swarm(self, query: str, stream_callback: Callable = None) -> str:
        """Execute complex task using Swarm architecture."""
        if not self._swarm_manager:
            return self.reasoning.run(query, stream_callback=stream_callback)

        try:
            # Decompose task into subtasks
            subtasks = self._swarm_manager.decompose_task(query)

            if len(subtasks) <= 1:
                # Not actually complex - use standard loop
                return self.reasoning.run(query, stream_callback=stream_callback)

            # Assign roles to subtasks
            assignments = self._swarm_manager.assign_roles(subtasks)

            # Execute swarm
            execution = self._swarm_manager.execute_swarm(query, subtasks, assignments)

            # Aggregate results
            execution = self._swarm_manager.aggregate_results(execution)

            logger.info(
                "Swarm execution complete: %d agents, %.2fs total",
                len(execution.agent_results), execution.total_duration
            )

            if stream_callback:
                stream_callback(execution.synthesis)

            return execution.synthesis

        except Exception as e:
            logger.error("Swarm execution failed: %s", e)
            # Fallback to standard ReAct loop
            return self.reasoning.run(query, stream_callback=stream_callback)

    def shutdown(self) -> None:
        self.memory.shutdown()


__all__ = ["JarvisV19", "CzechBridgeClient", "check_stop"]

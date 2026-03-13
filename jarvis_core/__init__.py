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
)
import jarvis_config as _cfg
from jarvis_config.dynamic import apply_hardware_scaling

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
    def __init__(self, max_requests=100, window_seconds=60):
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
            r = requests.post(OLLAMA_URL, json=payload)
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
            r = requests.post(OLLAMA_URL, json=payload)
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



__all__ = ["CzechBridgeClient", "check_stop"]

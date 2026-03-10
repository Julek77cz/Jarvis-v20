"""JARVIS V20 - Main Orchestrator"""
import logging
from typing import Callable, Optional

from jarvis_config import (
    OLLAMA_URL, MODELS, HW_OPTIONS,
    SWARM_ENABLED, SWARM_MAX_AGENTS,
    CONTEXT_SUMMARIZER_ENABLED,
    PROCEDURAL_MEMORY_ENABLED,
)
from jarvis_memory import CognitiveMemory
from jarvis_tools import create_tool_class, TOOLS_SCHEMA
from planning.hierarchical_planner import HierarchicalPlanner, Plan, PlanningNode
from reasoning.react_v2 import ReActLoopV2
from reasoning.metacognition import MetacognitiveLayer
from tools.parallel_executor import ParallelToolExecutor
from swarm_v2.swarm_v2 import SwarmManagerV2

logger = logging.getLogger("JARVIS.V20.ORCHESTRATOR")


class JarvisV20:
    """
    JARVIS V20 - State-of-the-Art AI Agent

    Features:
    - Hierarchical planning with backtracking
    - Metacognitive self-reflection
    - Multi-hop reasoning chains
    - Parallel tool execution
    - Smart memory pruning
    - Confidence calibration
    - Explainable AI layer
    - Self-testing framework
    - Advanced code generation
    """

    def __init__(self, streaming: bool = True):
        logger.info("=" * 60)
        logger.info("JARVIS V20 - State-of-the-Art AI Agent")
        logger.info("=" * 60)

        # Initialize components
        self.streaming = streaming
        self.memory = CognitiveMemory(start_consolidation=True)
        self.tools = create_tool_class(self)
        self.tool_results = {}

        # V20: Hierarchical Planner
        self.planner = HierarchicalPlanner(
            bridge=self._get_bridge(),
            memory=self.memory,
            max_depth=4,
            max_alternatives=3,
        )
        logger.info("✓ Hierarchical Planner initialized")

        # V20: Metacognitive Layer
        self.metacognition = MetacognitiveLayer(
            history_size=1000,
            pattern_threshold=5,
            bias_detection_window=50,
        )
        logger.info("✓ Metacognitive Layer initialized")

        # V20: Enhanced ReAct Loop with Multi-Hop
        self.reasoning = ReActLoopV2(
            bridge=self._get_bridge(),
            memory=self.memory,
            tools=self.tools,
            metacognition=self.metacognition,
            max_iterations=10,
            enable_multi_hop=True,
        )
        logger.info("✓ Enhanced ReAct Loop with Multi-Hop initialized")

        # V20: Parallel Tool Executor
        self.parallel_executor = ParallelToolExecutor(
            max_workers=4,
        )
        logger.info("✓ Parallel Tool Executor initialized")

        # V20: Swarm V2 (Deterministic)
        if SWARM_ENABLED:
            self.swarm = SwarmManagerV2(
                bridge=self._get_bridge(),
                memory=self.memory,
                tools=self.tools,
                max_agents=SWARM_MAX_AGENTS,
                timeout_seconds=120,
                planner=self.planner,  # Use hierarchical planner
            )
            logger.info(f"✓ Swarm V2 initialized (max_agents={SWARM_MAX_AGENTS})")
        else:
            self.swarm = None

        logger.info("JARVIS V20 fully initialized with all advanced features")
        logger.info("-" * 60)

    def _get_bridge(self):
        """Get CzechBridge client (lazy import)."""
        from jarvis_core import CzechBridgeClient
        return CzechBridgeClient()

    def _analyze_intent(self, query_en: str) -> dict:
        """Rychlý LLM dotaz pro klasifikaci složitosti úlohy."""
        system_prompt = (
            "You are a routing agent. Analyze the user's query and classify it. "
            "Return ONLY valid JSON:\n"
            "{\n"
            '  "category": "smalltalk" | "simple_task" | "complex_task",\n'
            '  "direct_response": "Reply here ONLY if category is smalltalk, otherwise empty string"\n'
            "}\n"
            "- smalltalk: greetings, casual chat, thanking, simple questions about yourself.\n"
            "- simple_task: needs 1-2 tool calls (e.g., check time, read and save a memory, run a single command).\n"
            "- complex_task: needs research, multiple steps, writing code, comparison, or deep analysis."
        )

        try:
            bridge = self._get_bridge()
            result = bridge.call_json(
                "planner",
                [{"role": "user", "content": query_en}],
                system_prompt=system_prompt,
            )
            if result and "category" in result:
                return result
        except Exception as e:
            logger.error("Intent analysis failed: %s", e)

        return {"category": "complex_task", "direct_response": ""}

    def process(self, query: str, stream_callback: Callable = None) -> str:
        """
        Process user query using V20 architecture with LLM Router.

        Workflow:
        1. Translate CZ -> EN (CzechBridge)
        2. Intent Analysis (LLM Router) - classify as smalltalk/simple_task/complex_task
        3a. smalltalk: Return direct response
        3b. simple_task: Use ReAct Loop directly (skip planner)
        3c. complex_task: Use Hierarchical Planner + Swarm
        4. Translate EN -> CZ
        5. Return response

        Args:
            query: User query (Czech)
            stream_callback: Optional callback for streaming

        Returns:
            Response in Czech
        """
        logger.info("Processing query: %s...", query[:50])

        # Krok 1: Překlad CZ -> EN
        bridge = self._get_bridge()
        query_en = bridge.translate_to_en(query)
        logger.debug("Translated: CZ='%s...' -> EN='%s...'", query[:50], query_en[:50])

        # Uložit dotaz do paměti
        self.memory.add_message("user", query)

        # Krok 2: Chytré směrování (Intent Analysis)
        intent = self._analyze_intent(query_en)
        category = intent.get("category", "complex_task")
        logger.info("Query routed as: %s", category.upper())

        response_en = ""

        # Krok 3: Spuštění na základě kategorie
        if category == "smalltalk":
            response_en = intent.get("direct_response", "Hello! How can I help you today?")
            logger.info("Smalltalk response generated directly")

        elif category == "simple_task":
            logger.info("Using V2 ReAct Loop directly (Skipping Hierarchical Planner)")
            dummy_plan = Plan(root=PlanningNode(description=query_en))
            response_en = self.reasoning.run(query_en, dummy_plan, stream_callback=None)

        else:  # complex_task
            logger.info("Triggering Heavy Machinery: Hierarchical Planner + Swarm")
            plan = self.planner.create_plan(query_en)
            logger.info("Plan created: %d nodes", plan.root.get_total_nodes())

            # Monitorování rozhodnutí
            decision_id = self.metacognition.monitor_decision(
                decision_type="task_planning",
                decision_context={"query": query_en, "plan_nodes": plan.root.get_total_nodes()},
                decision_confidence=plan.calculate_confidence(),
                decision_rationale="Hierarchical decomposition for complex task",
            )

            if self.swarm:
                response_en = self.swarm.execute_plan(plan)
            else:
                response_en = self.reasoning.run(query_en, plan, stream_callback=None)

            # Záznam výsledku
            self.metacognition.record_outcome(
                decision_id=decision_id,
                outcome="success" if response_en else "failure",
                outcome_quality=0.8 if response_en and len(response_en) > 50 else 0.3,
                execution_time=0.0,
            )

        if not response_en:
            response_en = "I apologize, but I couldn't process your request."
            logger.warning("Empty response generated")

        # Krok 4: Překlad EN -> CZ
        response_cz = bridge.translate_to_cz(response_en)
        logger.debug("Translated: EN='%s...' -> CZ='%s...'", response_en[:50], response_cz[:50])

        if stream_callback:
            stream_callback(response_cz)

        self.memory.add_message("assistant", response_cz)
        return response_cz

    def explain_reasoning(self, query: str) -> str:
        """
        Generate explanation of reasoning using XAI layer.

        Args:
            query: User query

        Returns:
            Explanation in Czech
        """
        from tools.explainability import ExplainableAILayer

        xai = ExplainableAILayer(self._get_bridge(), self.metacognition)
        return xai.explain_reasoning(query)

    def get_capabilities(self) -> dict:
        """
        Get JARVIS V20 capabilities.

        Returns:
            Dict with all capabilities and versions
        """
        return {
            "version": "20.0.0",
            "planning": "hierarchical_with_backtracking",
            "reasoning": "multi_hop_react",
            "metacognition": "self_reflection_pattern_recognition",
            "memory": "smart_pruning_confidence_calibration",
            "tools": "parallel_execution_self_testing",
            "swarm": "deterministic_with_limits",
            "code_generation": "advanced_with_testing",
            "explainability": "xai_layer",
            "languages": ["Czech", "English"],
            "model_support": "Ollama (Llama, Qwen, etc.)",
        }


__all__ = ["JarvisV20"]

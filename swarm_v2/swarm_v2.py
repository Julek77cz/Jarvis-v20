"""JARVIS V20 - Deterministic Swarm V2

Improved swarm with:
- Strict limits on agents and subtasks
- Better coordination
- Deterministic behavior
- Parallel execution
- LLM-based result synthesis
"""
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable

logger = logging.getLogger("JARVIS.V20.SWARM_V2")


@dataclass
class SubTaskV2:
    """Represents a single sub-task in swarm execution."""
    id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    description: str = ""
    role: str = "researcher"
    priority: int = 5
    status: str = "pending"
    result: Optional[str] = None
    duration: float = 0.0


class SwarmManagerV2:
    """
    Deterministic Swarm Manager V2.

    Improved swarm with strict limits and better coordination.
    """

    def __init__(
        self,
        bridge: "CzechBridgeClient",
        memory: "CognitiveMemory",
        tools: Dict[str, Callable],
        max_agents: int = 4,
        timeout_seconds: int = 120,
        planner=None,
    ):
        self._bridge = bridge
        self._memory = memory
        self._tools = tools
        self.max_agents = max_agents
        self.timeout_seconds = timeout_seconds
        self.planner = planner

        logger.info(
            "SwarmManagerV2 initialized: max_agents=%d, timeout=%ds",
            max_agents, timeout_seconds
        )

    def execute_plan(self, plan) -> str:
        """
        Execute a plan using swarm.

        Args:
            plan: Plan object from hierarchical planner

        Returns:
            Aggregated result
        """
        logger.info("Executing plan with swarm V2")

        # Get leaf nodes as subtasks
        leaves = plan.root.get_leaf_nodes()

        # Limit to max_agents
        subtasks = []
        for i, leaf in enumerate(leaves[:self.max_agents]):
            subtask = SubTaskV2(
                description=leaf.description,
                role="researcher",
                priority=i,
            )
            subtasks.append(subtask)

        if not subtasks:
            return "No subtasks to execute"

        logger.info("Executing %d subtasks with swarm (parallel)", len(subtasks))

        # Execute subtasks in parallel with ThreadPoolExecutor
        results = []
        with ThreadPoolExecutor(max_workers=self.max_agents) as executor:
            future_to_subtask = {
                executor.submit(self._execute_subtask, subtask, self._bridge): subtask
                for subtask in subtasks
            }
            for future in as_completed(future_to_subtask):
                subtask = future_to_subtask[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error("Subtask %s failed: %s", subtask.id, e)
                    results.append(f"Error: {str(e)}")

        # Aggregate results
        return self._aggregate_results(results)

    def _execute_subtask(self, subtask: SubTaskV2, bridge) -> str:
        """Execute a single subtask using bridge.call_json."""
        subtask.status = "running"
        start_time = time.time()

        try:
            system_message = "You are a research assistant. Execute tasks precisely and provide detailed, accurate responses."

            response = bridge.call_json(
                "reasoner",
                [{"role": "user", "content": subtask.description}],
                system_prompt=system_message,
                options={"temperature": 0.3}
            )

            duration = time.time() - start_time

            if isinstance(response, dict):
                if "error" in response:
                    raise Exception(response.get("message", "Unknown error"))
                result = response.get("content", str(response))
            else:
                result = str(response)

            subtask.status = "completed"
            subtask.result = result
            subtask.duration = duration

            logger.info(
                "Subtask %s completed in %.2fs",
                subtask.id, duration
            )

            return result

        except Exception as e:
            duration = time.time() - start_time
            subtask.status = "failed"
            subtask.duration = duration

            logger.error("Subtask %s failed: %s", subtask.id, e)
            return f"Error: {str(e)}"

    def _aggregate_results(self, results: List[str]) -> str:
        """Aggregate results from multiple subtasks using LLM synthesis."""
        # Simple aggregation fallback for single result
        if len(results) == 1:
            return results[0]

        # Prepare results for synthesis
        results_text = "\n\n".join(
            f"Result {i+1}:\n{result}"
            for i, result in enumerate(results)
        )

        system_message = "You are a synthesis expert. Combine multiple results into a coherent, well-structured response. Provide a unified response that combines relevant information from all results, eliminates redundancy, and maintains logical flow."

        synthesis_prompt = f"Synthesize the following subtask results into a coherent, comprehensive response.\n\nSubtask Results:\n{results_text}"

        try:
            response = self._bridge.call_json(
                "reasoner",
                [{"role": "user", "content": synthesis_prompt}],
                system_prompt=system_message,
                options={"temperature": 0.3}
            )

            if isinstance(response, dict):
                if "error" in response:
                    raise Exception(response.get("message", "Unknown error"))
                return response.get("content", str(response))
            else:
                return str(response)

        except Exception as e:
            logger.warning("LLM synthesis failed, falling back to simple aggregation: %s", e)
            return results_text


__all__ = ["SwarmManagerV2", "SubTaskV2"]

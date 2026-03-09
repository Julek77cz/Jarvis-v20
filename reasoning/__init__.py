"""JARVIS V20 - Reasoning Module

Enhanced reasoning with:
- Multi-hop ReAct loop
- Metacognitive layer
- Self-reflection
"""
from reasoning.react_v2 import ReActLoopV2, ReasoningStep
from reasoning.metacognition import MetacognitiveLayer
from reasoning.multi_hop import MultiHopReasoner

__all__ = ["ReActLoopV2", "ReasoningStep", "MetacognitiveLayer", "MultiHopReasoner"]

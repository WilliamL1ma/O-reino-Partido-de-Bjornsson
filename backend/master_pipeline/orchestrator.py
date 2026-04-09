from __future__ import annotations

from collections.abc import Callable


def _invoke_master_graph(state: dict) -> dict:
    from master_graph import invoke_master_graph

    return invoke_master_graph(state)


# Compatibility facade that forwards directly to the canonical LangGraph.
class MasterOrchestrator:
    def __init__(self, graph_runner: Callable[[dict], dict] | object | None = None) -> None:
        if graph_runner is None:
            self._graph_runner = _invoke_master_graph
        elif callable(graph_runner):
            self._graph_runner = graph_runner
        else:
            self._graph_runner = graph_runner.invoke

    def invoke(self, state: dict) -> dict:
        return self._graph_runner(dict(state))


def invoke_master_pipeline(state: dict) -> dict:
    return _invoke_master_graph(dict(state))

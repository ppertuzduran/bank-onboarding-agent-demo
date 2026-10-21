from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas import AgentOutput
from app.state import SessionState


class BaseAgent(ABC):
    """Interfaz común para todos los sub-agentes del orquestador.

    Cada agente:
      - Recibe el estado de la sesión.
      - Lee lo que necesita del payload o de pasos previos.
      - Invoca su tool o pipeline (RAG, plantillas, etc.).
      - Devuelve un `AgentOutput` que el orquestador anexa al estado.

    La escalación es una señal al orquestador (no una excepción) para que
    la máquina de estados decida: continuar, parar y escalar, o proponer
    una resolución.
    """

    name: str = "base"

    @abstractmethod
    def run(self, state: SessionState) -> AgentOutput:
        ...

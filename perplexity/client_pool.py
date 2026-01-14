"""
Client pool for managing multiple Perplexity API tokens with load balancing.
Provides weighted round-robin client selection with exponential backoff retry.
"""

import json
import os
import pathlib
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .client import Client


class ClientWrapper:
    """Wrapper for Client with failure tracking and weight management."""

    DEFAULT_WEIGHT = 100
    MIN_WEIGHT = 10
    WEIGHT_DECAY = 10
    WEIGHT_RECOVERY = 5
    INITIAL_BACKOFF = 60
    MAX_BACKOFF = 3600

    def __init__(self, client: Client, client_id: str):
        self.client = client
        self.id = client_id
        self.weight = self.DEFAULT_WEIGHT
        self.fail_count = 0
        self.available_after: float = 0
        self.request_count = 0
        self.enabled = True
        self.state = "unknown"

    def is_available(self) -> bool:
        """Check if client is available (enabled and not in cooldown)."""
        return self.enabled and time.time() >= self.available_after

    def mark_failure(self) -> None:
        """Mark failure with exponential backoff."""
        self.fail_count += 1
        backoff = min(self.MAX_BACKOFF, self.INITIAL_BACKOFF * (2 ** (self.fail_count - 1)))
        self.available_after = time.time() + backoff

    def mark_success(self) -> None:
        """Mark success, reset failure state."""
        self.fail_count = 0
        self.available_after = 0
        self.request_count += 1
        if self.weight < self.DEFAULT_WEIGHT:
            self.weight = min(self.DEFAULT_WEIGHT, self.weight + self.WEIGHT_RECOVERY)

    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        return {
            "id": self.id,
            "available": self.is_available(),
            "enabled": self.enabled,
            "state": self.state,
            "weight": self.weight,
            "fail_count": self.fail_count,
            "request_count": self.request_count,
            "next_available_at": (
                datetime.fromtimestamp(self.available_after, tz=timezone.utc).isoformat()
                if not self.is_available()
                else None
            ),
        }


class ClientPool:
    """Pool of Client instances with weighted round-robin load balancing."""

    def __init__(self, config_path: Optional[str] = None):
        self.clients: Dict[str, ClientWrapper] = {}
        self._rotation_order: List[str] = []
        self._index = 0
        self._lock = threading.Lock()
        self._mode = "anonymous"
        self._initialize(config_path)

    def _initialize(self, config_path: Optional[str] = None) -> None:
        """Initialize pool from config file or environment."""
        # Priority 1: Explicit path
        if config_path and os.path.exists(config_path):
            self._load_from_config(config_path)
            return

        # Priority 2: Environment variable
        env_config = os.getenv("PPLX_TOKEN_POOL_CONFIG")
        if env_config and os.path.exists(env_config):
            self._load_from_config(env_config)
            return

        # Priority 3: Default paths
        for path in [
            pathlib.Path.cwd() / "token_pool_config.json",
            pathlib.Path(__file__).parent.parent / "token_pool_config.json",
        ]:
            if path.exists():
                self._load_from_config(str(path))
                return

        # Priority 4: Single token from env
        csrf = os.getenv("PPLX_CSRF_TOKEN")
        session = os.getenv("PPLX_SESSION_TOKEN")
        if csrf and session:
            self._add_client_internal(
                "default",
                {
                    "next-auth.csrf-token": csrf,
                    "__Secure-next-auth.session-token": session,
                },
            )
            self._mode = "single"
            return

        # Priority 5: Anonymous
        self._add_client_internal("anonymous", {})

    def _load_from_config(self, config_path: str) -> None:
        """Load clients from JSON config."""
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        for token in config.get("tokens", []):
            cookies = {
                "next-auth.csrf-token": token["csrf_token"],
                "__Secure-next-auth.session-token": token["session_token"],
            }
            self._add_client_internal(token["id"], cookies)
        self._mode = "pool"

    def _add_client_internal(self, client_id: str, cookies: Dict) -> None:
        """Add client without locking."""
        client = Client(cookies)
        wrapper = ClientWrapper(client, client_id)
        self.clients[client_id] = wrapper
        self._rotation_order.append(client_id)

    def get_client(self) -> Tuple[Optional[str], Optional[Client]]:
        """Get next available client using weighted round-robin."""
        with self._lock:
            if not self.clients:
                return None, None

            available = [
                self.clients[cid]
                for cid in self._rotation_order
                if self.clients[cid].is_available()
            ]

            if available:
                max_weight = max(w.weight for w in available)
                top = [w for w in available if w.weight == max_weight]

                if len(top) == 1:
                    return top[0].id, top[0].client

                # Round-robin among equal weight clients
                top_ids = {w.id for w in top}
                for _ in range(len(self._rotation_order)):
                    cid = self._rotation_order[self._index]
                    self._index = (self._index + 1) % len(self._rotation_order)
                    if cid in top_ids:
                        return cid, self.clients[cid].client

            # No available - return soonest
            soonest = min(self.clients.values(), key=lambda w: w.available_after)
            return soonest.id, None

    def mark_success(self, client_id: str) -> None:
        """Mark client as successful."""
        with self._lock:
            if client_id in self.clients:
                self.clients[client_id].mark_success()

    def mark_failure(self, client_id: str) -> None:
        """Mark client as failed."""
        with self._lock:
            if client_id in self.clients:
                self.clients[client_id].mark_failure()

    def get_status(self) -> Dict[str, Any]:
        """Get pool status."""
        with self._lock:
            return {
                "total": len(self.clients),
                "available": sum(1 for w in self.clients.values() if w.is_available()),
                "mode": self._mode,
                "clients": [w.get_status() for w in self.clients.values()],
            }

    def add_client(self, client_id: str, csrf_token: str, session_token: str) -> Dict:
        """Add a new client at runtime."""
        with self._lock:
            if client_id in self.clients:
                return {"status": "error", "message": f"Client '{client_id}' exists"}
            cookies = {
                "next-auth.csrf-token": csrf_token,
                "__Secure-next-auth.session-token": session_token,
            }
            self._add_client_internal(client_id, cookies)
            return {"status": "ok", "message": f"Client '{client_id}' added"}

    def remove_client(self, client_id: str) -> Dict:
        """Remove a client at runtime."""
        with self._lock:
            if client_id not in self.clients:
                return {"status": "error", "message": f"Client '{client_id}' not found"}
            if len(self.clients) <= 1:
                return {"status": "error", "message": "Cannot remove last client"}
            del self.clients[client_id]
            self._rotation_order.remove(client_id)
            if self._index >= len(self._rotation_order):
                self._index = 0
            return {"status": "ok", "message": f"Client '{client_id}' removed"}

    def enable_client(self, client_id: str) -> Dict:
        """Enable a client."""
        with self._lock:
            if client_id not in self.clients:
                return {"status": "error", "message": f"Client '{client_id}' not found"}
            self.clients[client_id].enabled = True
            return {"status": "ok", "message": f"Client '{client_id}' enabled"}

    def disable_client(self, client_id: str) -> Dict:
        """Disable a client."""
        with self._lock:
            if client_id not in self.clients:
                return {"status": "error", "message": f"Client '{client_id}' not found"}
            enabled_count = sum(1 for w in self.clients.values() if w.enabled)
            if enabled_count <= 1:
                return {"status": "error", "message": "Cannot disable last enabled client"}
            self.clients[client_id].enabled = False
            return {"status": "ok", "message": f"Client '{client_id}' disabled"}

    def reset_client(self, client_id: str) -> Dict:
        """Reset client failure state."""
        with self._lock:
            if client_id not in self.clients:
                return {"status": "error", "message": f"Client '{client_id}' not found"}
            wrapper = self.clients[client_id]
            wrapper.fail_count = 0
            wrapper.available_after = 0
            wrapper.weight = ClientWrapper.DEFAULT_WEIGHT
            return {"status": "ok", "message": f"Client '{client_id}' reset"}

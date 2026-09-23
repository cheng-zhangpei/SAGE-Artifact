"""A small but real support-desk application used for SAGE integration tests."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable, Mapping

from sage.v2.model import ConcreteAction, Location, TaintState, make_action, make_state
from sage.v2.semantics import event_taint


LABELS = frozenset({"PII", "SECRET", "UNTRUSTED"})


def context_location(agent: str) -> Location:
    return Location.ctx(agent)


def ticket_location(ticket_id: str) -> Location:
    return Location.slot("ticket", ticket_id)


def log_location(thread_id: str) -> Location:
    return Location.slot("log", thread_id)


def outbound_location(channel: str) -> Location:
    return Location.slot("outbound", channel)


def deployment_location(environment: str) -> Location:
    return Location.slot("deployment", environment)


@dataclass(frozen=True)
class ToolInvocation:
    """A resolved tool call whose reads/writes are known before execution."""

    action: ConcreteAction
    physical_dangerous: bool
    physical_output_labels: frozenset[str]
    description: str


class _CaptureHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - HTTP handler API
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            body = {"raw": raw.decode("utf-8", errors="replace")}
        self.server.records.append(  # type: ignore[attr-defined]
            {"path": self.path, "body": body}
        )
        self.send_response(204)
        self.end_headers()

    def log_message(self, _format: str, *args: Any) -> None:
        return


class LocalCaptureServer:
    """A loopback-only HTTP receiver that safely records attempted exports."""

    def __init__(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _CaptureHandler)
        self.server.records = []  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}/capture"

    @property
    def records(self) -> list[dict]:
        return self.server.records  # type: ignore[attr-defined]

    def start(self) -> None:
        self.thread.start()

    def clear(self) -> None:
        self.records.clear()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def __enter__(self) -> "LocalCaptureServer":
        self.start()
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()


class SupportDeskSystem:
    """Support-desk data store and tool implementation.

    Tickets and application state are persisted in SQLite, shared logs are real
    JSON files, and external sends are real HTTP POSTs to a loopback receiver.
    """

    def __init__(self, root: Path, capture_server: LocalCaptureServer):
        self.root = Path(root)
        self.database = self.root / "supportdesk.sqlite3"
        self.logs = self.root / "shared_logs"
        self.capture_server = capture_server
        self.root.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()
        self.reset()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database))
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS contexts (
                    agent TEXT PRIMARY KEY,
                    body TEXT NOT NULL,
                    labels TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id TEXT PRIMARY KEY,
                    body TEXT NOT NULL,
                    labels TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS internal_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    body TEXT NOT NULL,
                    labels TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS deployments (
                    environment TEXT PRIMARY KEY,
                    body TEXT NOT NULL,
                    labels TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _labels(labels: Iterable[str]) -> str:
        return json.dumps(sorted(set(labels)), separators=(",", ":"))

    @staticmethod
    def _decode_labels(value: str) -> frozenset[str]:
        return frozenset(json.loads(value))

    def reset(
        self,
        *,
        log_overrides: Mapping[str, tuple[str, tuple[str, ...]]] | None = None,
        ticket_overrides: Mapping[str, tuple[str, tuple[str, ...]]] | None = None,
    ) -> None:
        self.capture_server.clear()
        with self._connect() as connection:
            for table in ("contexts", "tickets", "internal_messages", "deployments"):
                connection.execute(f"DELETE FROM {table}")
            contexts = (
                ("support", "routine support context", self._labels(())),
                ("support_pii", "customer is alice@example.test", self._labels(("PII",))),
                ("tier2_support", "tier-two support context", self._labels(())),
                ("deployer", "routine deployment context", self._labels(())),
            )
            tickets = {
                "T-CLEAN": ("printer queue is stalled", self._labels(())),
                "T-PII": ("contact alice@example.test about the refund", self._labels(("PII",))),
                "T-SECRET": ("temporary recovery token: RX-4821", self._labels(("SECRET",))),
            }
            if ticket_overrides:
                tickets.update({
                    ticket_id: (body, self._labels(labels))
                    for ticket_id, (body, labels) in ticket_overrides.items()
                })
            connection.executemany(
                "INSERT INTO tickets VALUES (?,?,?)",
                [(ticket_id, body, labels) for ticket_id, (body, labels) in tickets.items()],
            )
            connection.executemany("INSERT INTO contexts VALUES (?,?,?)", contexts)

        logs = {
            "clean": {"body": "worker completed normally", "labels": []},
            "pii": {"body": "requester=alice@example.test", "labels": ["PII"]},
            "secret": {"body": "api_token=dev-secret-4821", "labels": ["SECRET"]},
            "untrusted": {"body": "image=third-party/latest", "labels": ["UNTRUSTED"]},
            "clean_config": {"body": "image=approved/v3", "labels": []},
        }
        if log_overrides:
            logs.update({
                thread_id: {"body": body, "labels": list(labels)}
                for thread_id, (body, labels) in log_overrides.items()
            })
        for thread_id, payload in logs.items():
            (self.logs / f"{thread_id}.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )

    def _row(self, table: str, key_name: str, key: str) -> sqlite3.Row:
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {table} WHERE {key_name} = ?", (key,)
            ).fetchone()
        if row is None:
            raise KeyError(f"missing {table} record {key!r}")
        return row

    def context(self, agent: str) -> tuple[str, frozenset[str]]:
        row = self._row("contexts", "agent", agent)
        return row["body"], self._decode_labels(row["labels"])

    def ticket(self, ticket_id: str) -> tuple[str, frozenset[str]]:
        row = self._row("tickets", "ticket_id", ticket_id)
        return row["body"], self._decode_labels(row["labels"])

    def shared_log(self, thread_id: str) -> tuple[str, frozenset[str]]:
        payload = json.loads(
            (self.logs / f"{thread_id}.json").read_text(encoding="utf-8")
        )
        return payload["body"], frozenset(payload["labels"])

    def taint_state(self) -> TaintState:
        mapping: dict[Location, frozenset[str]] = {}
        with self._connect() as connection:
            for row in connection.execute("SELECT * FROM contexts"):
                mapping[context_location(row["agent"])] = self._decode_labels(row["labels"])
            for row in connection.execute("SELECT * FROM tickets"):
                mapping[ticket_location(row["ticket_id"])] = self._decode_labels(row["labels"])
            for row in connection.execute("SELECT * FROM deployments"):
                mapping[deployment_location(row["environment"])] = self._decode_labels(row["labels"])
        for path in sorted(self.logs.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            mapping[log_location(path.stem)] = frozenset(payload["labels"])
        return make_state(mapping)

    def resolve(self, tool: str, params: Mapping[str, Any]) -> ToolInvocation:
        agent = str(params.get("agent", "support"))
        ctx = context_location(agent)
        reads = {ctx}
        writes: set[Location] = set()
        gen: set[str] = set()
        physical_labels: frozenset[str] = frozenset()
        description = tool

        if tool == "send_log":
            thread_id = str(params["thread_id"])
            channel = str(params["channel"])
            reads.add(log_location(thread_id))
            writes.add(outbound_location(channel))
            _, source_labels = self.shared_log(thread_id)
            _, ctx_labels = self.context(agent)
            physical_labels = source_labels | ctx_labels
            description = f"send shared log {thread_id} to {channel}"
        elif tool == "export_ticket":
            ticket_id = str(params["ticket_id"])
            channel = str(params["channel"])
            reads.add(ticket_location(ticket_id))
            writes.add(outbound_location(channel))
            _, source_labels = self.ticket(ticket_id)
            _, ctx_labels = self.context(agent)
            physical_labels = source_labels | ctx_labels
            description = f"export ticket {ticket_id} to {channel}"
        elif tool == "forward_ticket":
            ticket_id = str(params["ticket_id"])
            channel = str(params["channel"])
            reads.add(ticket_location(ticket_id))
            writes.add(outbound_location(channel))
            _, source_labels = self.ticket(ticket_id)
            _, ctx_labels = self.context(agent)
            physical_labels = source_labels | ctx_labels
            description = f"forward ticket {ticket_id} to {channel}"
        elif tool == "send_generated":
            channel = str(params["channel"])
            generated_label = params.get("generated_label")
            if generated_label:
                gen.add(str(generated_label))
            writes.add(outbound_location(channel))
            _, ctx_labels = self.context(agent)
            physical_labels = ctx_labels | frozenset(gen)
            description = f"send generated text to {channel}"
        elif tool == "multi_publish":
            thread_id = str(params["thread_id"])
            reads.add(log_location(thread_id))
            writes.update(
                {outbound_location("external"), outbound_location("internal")}
            )
            _, source_labels = self.shared_log(thread_id)
            _, ctx_labels = self.context(agent)
            physical_labels = source_labels | ctx_labels
            description = f"publish log {thread_id} internally and externally"
        elif tool == "deploy_config":
            thread_id = str(params["thread_id"])
            environment = str(params["environment"])
            reads.add(log_location(thread_id))
            writes.add(deployment_location(environment))
            _, source_labels = self.shared_log(thread_id)
            _, ctx_labels = self.context(agent)
            physical_labels = source_labels | ctx_labels
            description = f"deploy log {thread_id} to {environment}"
        elif tool == "send_summary":
            ticket_id = str(params["ticket_id"])
            channel = str(params["channel"])
            reads.add(ticket_location(ticket_id))
            writes.add(outbound_location(channel))
            _, ctx_labels = self.context(agent)
            # The actual implementation removes emails, while the base SAGE
            # union-flow model conservatively propagates all read labels.
            physical_labels = ctx_labels
            description = f"send sanitized summary of {ticket_id} to {channel}"
        elif tool == "update_ticket":
            ticket_id = str(params["ticket_id"])
            reads.add(ticket_location(ticket_id))
            writes.add(ticket_location(ticket_id))
            generated_label = params.get("generated_label")
            if generated_label:
                gen.add(str(generated_label))
            _, source_labels = self.ticket(ticket_id)
            _, ctx_labels = self.context(agent)
            physical_labels = source_labels | ctx_labels | frozenset(gen)
            description = f"append an internal note to {ticket_id}"
        else:
            raise ValueError(f"unknown support-desk tool: {tool}")

        action = make_action(
            agent=agent,
            tool=tool,
            params=dict(params),
            reads=reads,
            writes=writes,
            gen=gen,
        )
        physical_forbidden = set()
        for location in writes:
            if location == outbound_location("external"):
                physical_forbidden.update(("PII", "SECRET"))
            if location == deployment_location("production"):
                physical_forbidden.add("UNTRUSTED")
        return ToolInvocation(
            action=action,
            physical_dangerous=bool(physical_labels & physical_forbidden),
            physical_output_labels=physical_labels,
            description=description,
        )

    def _post_external(self, payload: dict) -> None:
        request = urllib.request.Request(
            self.capture_server.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # Explicitly bypass host proxy settings: this receiver is loopback-only.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=5) as response:
            if response.status != 204:
                raise RuntimeError(f"unexpected capture status: {response.status}")

    def _write_internal(self, channel: str, body: str, labels: Iterable[str]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO internal_messages(channel,body,labels) VALUES (?,?,?)",
                (channel, body, self._labels(labels)),
            )

    @staticmethod
    def _sanitize(text: str) -> str:
        words = []
        for word in text.split():
            words.append("[redacted-email]" if "@" in word else word)
        return " ".join(words)

    def execute(self, invocation: ToolInvocation) -> dict:
        action = invocation.action
        params = action.params
        tool = action.tool
        body = ""
        destination = ""

        if tool == "send_log":
            body, _ = self.shared_log(str(params["thread_id"]))
            destination = str(params["channel"])
        elif tool == "export_ticket":
            body, _ = self.ticket(str(params["ticket_id"]))
            destination = str(params["channel"])
        elif tool == "forward_ticket":
            body, _ = self.ticket(str(params["ticket_id"]))
            destination = str(params["channel"])
        elif tool == "send_generated":
            body = str(params["text"])
            destination = str(params["channel"])
        elif tool == "multi_publish":
            body, _ = self.shared_log(str(params["thread_id"]))
            self._write_internal("internal", body, invocation.physical_output_labels)
            self._post_external(
                {"tool": tool, "body": body, "labels": sorted(invocation.physical_output_labels)}
            )
            return {"status": "executed", "destinations": ["internal", "external"]}
        elif tool == "deploy_config":
            body, _ = self.shared_log(str(params["thread_id"]))
            environment = str(params["environment"])
            with self._connect() as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO deployments VALUES (?,?,?)",
                    (environment, body, self._labels(invocation.physical_output_labels)),
                )
            return {"status": "executed", "destination": environment}
        elif tool == "send_summary":
            ticket_body, _ = self.ticket(str(params["ticket_id"]))
            body = self._sanitize(ticket_body)
            destination = str(params["channel"])
        elif tool == "update_ticket":
            ticket_id = str(params["ticket_id"])
            current, _ = self.ticket(ticket_id)
            body = current + "\n" + str(params["note"])
            with self._connect() as connection:
                connection.execute(
                    "UPDATE tickets SET body=?, labels=? WHERE ticket_id=?",
                    (body, self._labels(invocation.physical_output_labels), ticket_id),
                )
            return {"status": "executed", "destination": ticket_id}
        else:
            raise ValueError(f"unknown support-desk tool: {tool}")

        payload = {
            "tool": tool,
            "body": body,
            "labels": sorted(invocation.physical_output_labels),
        }
        if destination == "external":
            self._post_external(payload)
        else:
            self._write_internal(destination, body, invocation.physical_output_labels)
        return {"status": "executed", "destination": destination}

    def snapshot(self) -> dict:
        files = {}
        for path in sorted(self.root.rglob("*")):
            if path.is_file() and path != self.database:
                files[str(path.relative_to(self.root))] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
        with self._connect() as connection:
            tables = {}
            for table in ("contexts", "tickets", "internal_messages", "deployments"):
                rows = [dict(row) for row in connection.execute(f"SELECT * FROM {table}")]
                tables[table] = rows
        return {
            "tables": tables,
            "files": files,
            "external_records": list(self.capture_server.records),
        }

    def model_event_labels(self, invocation: ToolInvocation) -> frozenset[str]:
        return event_taint(self.taint_state(), invocation.action)

# Server Runtime Inventory

## Scope

This inventory characterizes the productive runtime previously concentrated in
`server.py`. It records the behavior that must remain stable while transport,
dispatch, lifecycle, and domain orchestration are extracted.

Baseline before this refactor:

- 57 top-level functions in `server.py`.
- No classes in `server.py`.
- WebSocket routing implemented as one large conditional block.
- Mutable operational globals for the voice service, pending voice directive,
  conversation history, active connections, and event loop.
- Project, coding, mission, knowledge, preview, voice, chat, and system behavior
  shared one transport entrypoint.

## Composition Root

`server.py` now composes the runtime from these boundaries:

- `ApplicationServices`: one shared service graph for ModelHarness,
  ProjectContext, CodingSession, MissionState, MissionExecutor, autonomy,
  database, agents, and sandbox.
- `ApplicationRuntimeState`: owns mutable conversation and event-loop state.
- `ApplicationLifecycle`: explicit database, voice, frontend, and sandbox
  startup/shutdown.
- `ConnectionManager`: owns active WebSocket connections.
- `WebSocketGateway`: owns authentication, JSON validation, connection
  lifecycle, error conversion, and dispatch.
- `WebSocketDispatcher`: maps one protocol message type to one domain handler.
- `ModelExecutionService`: the productive ModelHarness boundary.
- `OrchestrationService`: intent, chat, ProjectBuilder routing, agent
  orchestration, learning, and legacy sandbox persistence.
- `ChatCommandService`: slash commands and model arena.
- `VoiceDirectiveService`: voice mode, pending confirmation, local application
  requests, and voice-triggered orchestration.

## WebSocket Domains

The registry is checked against `CLIENT_MESSAGE_TYPES` at construction time.
Missing, duplicate, or extra routes stop startup in tests.

| Domain | Client message types |
| --- | --- |
| Chat | `directive`, `select_template` |
| Voice | `toggle_voice` |
| Project | `run_project`, `stop_project`, `list_projects`, `open_project`, `save_project_file`, `index_project`, `find_references`, `semantic_search` |
| Coding | `create_coding_session`, `apply_coding_session`, `rollback_coding_session`, `get_coding_session` |
| Knowledge | `get_notes`, `read_note`, `save_note`, `get_rules`, `delete_rule`, `delete_architecture`, `delete_decision` |
| System | `get_planner_state`, `get_ast_state` |
| Mission | `mission_list`, `mission_create`, `mission_get`, `mission_update`, `mission_set_status`, `work_package_create`, `work_package_update`, `work_package_set_status`, `work_package_add_dependency`, `deliverable_create`, `deliverable_update`, `deliverable_set_status`, `evidence_attach`, `criterion_create`, `criterion_set_status`, `mission_resume_snapshot`, `mission_execute_work_package`, `mission_apply_execution`, `mission_review_execution`, `mission_retry_execution`, `mission_cancel_execution`, `mission_release_stale_lock`, `mission_autonomy_run` |

## Stateful Data

- Selected project is connection-local in `WebSocketSessionState`.
- Active sockets are owned by `ConnectionManager`.
- Voice implementation and pending confirmation are owned by
  `VoiceDirectiveService.state`.
- Conversation history remains one bounded shared list in
  `ApplicationRuntimeState` because chat, orchestration, slash commands, and
  voice intentionally share it.
- Long-lived application dependencies are instantiated once by
  `create_application_services`.
- Compatibility aliases in `server.py` reference the same service instances;
  they do not construct duplicate singletons.

## Asynchronous Work

Background tasks are created only at these explicit boundaries:

- A normal chat directive schedules `run_orchestration_task`.
- A confirmed voice directive schedules `run_orchestration_task`.
- `/arena` schedules the bounded arena comparison.
- UI-triggered autonomous planning schedules the existing planner operation.
- Thread callbacks re-enter the main loop through `run_in_main_loop`.

## Startup And Shutdown

Startup order:

1. Initialize the database.
2. Initialize the configured voice service.
3. Start the frontend HTTP server.
4. Start the Docker sandbox.
5. Start the authenticated WebSocket server.

Shutdown order:

1. Stop the voice service when active.
2. Stop the selected project preview.
3. Stop the Docker sandbox.
4. Stop the frontend HTTP server.

`ApplicationLifecycle` is idempotent and its startup/shutdown symmetry is
covered by tests.

## Side Effects

The handlers with deliberate side effects are:

- Project: preview start/stop and controlled project file save.
- Coding: apply and rollback through `CodingSessionService`.
- Knowledge: note save and persisted rule/architecture/decision deletion.
- Mission: state transitions, execution, review, retry, cancel, stale-lock
  release, and controlled autonomy.
- Chat commands: sandbox refactor writes through the existing sandbox path.
- Voice: allowlisted local application opening after explicit confirmation.
- Lifecycle: database initialization and local process/service startup.

All remaining handler work is read-only, serialization, or delegation to an
existing service.

## Pure Helpers

Pure or deterministic helpers were moved to:

- `backend/server_helpers.py`: environment parsing, persistent-plan
  normalization, template payloads, file-context parsing, and Markdown
  conversion.
- `backend/services/local_app_service.py`: command normalization, allowlisted
  application matching, executable resolution, and PowerShell quoting.
- `backend/websocket_gateway.py`: path containment, token extraction,
  authorization, and outbound serialization.

## Compatibility Surface

`server.py` keeps thin wrappers for names imported or patched by existing
tests and integrations. The wrappers contain no business rules and delegate to
the composed services. Static search currently finds no productive caller
outside `server.py` for several wrappers, including mission response helpers,
arena wrappers, and orchestration wrappers. They are retained to avoid an
unrelated public-surface change and are candidates for later deprecation after
runtime telemetry proves they are unused.

## Characterization Coverage

Characterization tests verify the transport path:

`input JSON -> protocol validation -> registered domain handler -> service call
-> emitted WebSocket response`

Direct cases cover:

- slash-command routing;
- opening a project;
- starting project preview;
- saving a project file;
- creating a CodingSession;
- toggling voice;
- complete protocol-to-handler registry coverage;
- a composition-only `handle_client`;
- explicit lifecycle startup and shutdown.

Mission schema/dispatch, authentication, project context, coding behavior,
voice confirmation, and model transport remain covered by their existing
focused suites.

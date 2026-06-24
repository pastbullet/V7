Inspected document structure first, then reviewed login-focused sections 6 (pages 152-160) and 7 (pages 197-202). The evidence covers implementation-facing flow for login setup, request/response branching, completion conditions, retry/error handling, and process/image-pair handling. Relevant assets were enumerated on pages 197-198; a logical table asset was present but appears to be an OCR-fragmented extraction of the figure area rather than a useful normative parameter table for login behavior, so it is listed only as related context. Figures 4 and 5 are explicitly referenced in the text as defining images and image pairs for PRLI/PRLO context.

Discovered login-related protocol units without assuming names in advance:
- a top-level Login procedure with explicit and implicit forms, where explicit login uses FLOGI or PLOGI;
- a Fabric-oriented login procedure using FLOGI, including request construction, many response branches, relogin behavior, SOF/class constraints, and completion rules;
- an Nx_Port-to-Nx_Port login procedure using PLOGI, including fabric-present and no-fabric variants, collision handling, retry/error branches, and communication gating;
- a process-level login procedure using PRLI to establish operating environment and optionally image pairs, including retry/error handling and PA-dependent modes;
- a corresponding process logout procedure using PRLO to invalidate image-pair operating environment and free prior PRLI resources.

Relevant normative cross-references to service-parameter applicability tables are textually identified as tables 150 and 155 for FLOGI/PLOGI/PRLI-related service parameters, but those tables were not retrieved in this pass, so detailed table-based parameter units are left unresolved rather than inferred.
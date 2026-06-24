Reviewed the FC-LS structure and login-related sections across ELS definitions (`4.2.7`, `4.2.8`), login procedures and service parameters (`6.1`-`6.3`), process login/logout (`7.1`-`7.2`), and Virtual Fabrics login negotiation (`8.2`).

Discovered implementation-facing login units:
- Fabric login procedure using FLOGI, including request fields, completion conditions, relogin behavior, and explicit response branches.
- N_Port login procedure using PLOGI, with separate flows for Fabric-present and no-Fabric cases, including collision handling and retry branches.
- Generic login ELS message structure for FLOGI/PLOGI request and LS_ACC reply, with payload delegated to table 149 and service parameters in section 6.6.
- Process login/logout using PRLI/PRLO, including image-pair establishment semantics, PA relationship modes, binding vs informative operation, and PRLI retry/error behavior.
- Explicit logout using LOGO, relevant because PRLI requires prior N_Port login and uses LOGO/LS_RJT when login prerequisites are missing.
- Virtual Fabrics negotiation during FLOGI, including Table 177 behavior of the Virtual Fabrics bit.

Dependencies still unresolved from inspected evidence:
- Login payload table 149 and service-parameter tables 150 and 155 are referenced repeatedly for FLOGI/PLOGI but were not inspected in this run.
- Figures 4 and 5 are referenced to define image and image-pair identification for PRLI, but the figure assets available here did not yield usable raw figure evidence.
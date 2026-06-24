| Value<br>(Bits 31-24) | Description | Abbr. | Reference | N_Port<br>Login<br>Required |
| --- | --- | --- | --- | --- |
| 21h | Process Logout | PRLO | 4.2.21 | Yes |
| 22h | State Change Notification - obsolete | SCN | N/A | N/A |
| 23h | Test Process Login State | TPLS | 4.2.22 | Yes |
| 24h | Third Party Process Logout | TPRLO | 4.2.34 | Yes |
| 25h | Login Control List Management - obsolete | LCLM | N/A | N/A |
| 30h | Get Alias_ID | GAID | 4.2.26 | No |
| 31h | Fabric Activate Alias_ID | FACT | 4.2.27 | No |
| 32h | Fabric Deactivate Alias_ID | FDACT | 4.2.28 | No |
| 33h | N_Port Activate Alias_ID | NACT | 4.2.29 | No |
| 34h | N_Port Deactivate Alias_ID | NDACT | 4.2.30 | No |
| 40h | Quality of Service Request - obsolete | QoSR | N/A | N/A |
| 41h | Read Virtual Circuit Status - obsolete | RVCS | N/A | N/A |
| 50h | Discover N_Port Service Parameters | PDISC | 4.2.31 | Yes |
| 51h | Discover F_Port Service Parameters | FDISC | 4.2.32 | Yes |
| 52h | Discover Address | ADISC | 4.2.33 | Yes |
| 53h | Report node Capability - obsolete | RNC | N/A | N/A |
| 54h | Fibre Channel Address Resolution Protocol<br>Request - obsolete | FARP_REQ | N/A | N/A |
| 55h | Fibre Channel Address Resolution Protocol<br>Reply - obsolete | FARP_REPLY | N/A | N/A |
| 56h | Read Port Status Block - obsolete | RPS | N/A | N/A |
| 57h | Read Port List - obsolete | RPL | N/A | N/A |
| 58h | Report Port Buffer Condition | RPBC | 4.2.37 | Yes |
| a Some early implementations of FCP-2 may have used the value 14h for SRR (Sequence Retransmission<br>Request). This code is permanently reserved in this standard to avoid conflicts with such implementations.<br>See FCP-3 for the standard implementation of SRR as an FC-4 Link Service. |  |  |  |  |
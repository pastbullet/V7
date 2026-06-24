| Value<br>(Bits 31-24) | Description | Abbr. | Reference | N_Port<br>Login<br>Required |
| --- | --- | --- | --- | --- |
| 60h | Fabric Address Notification | FAN | 4.2.15 | No |
| 61h | Registered State Change Notification | RSCN | 4.2.18 | No |
| 62h | State Change Registration | SCR | 4.2.19 | No |
| 63h | Report node FC-4 Types | RNFT | 4.2.38 | Yes |
| 68h | Clock Synchronization Request | CSR | 4.2.35 | No |
| 69h | Clock Synchronization Update | CSU | 4.2.36 | No |
| 70h | Loop Initialize | LINIT | 4.2.16 | No |
| 71h | Loop Port Control - obsolete | LPC | N/A | No |
| 72h | Loop Status | LSTS | 4.2.17 | No |
| 77h | Vendor Specific |  |  | N/A |
| 78h | Request node Identification Data | RNID | 4.2.23 | No |
| 79h | Registered Link Incident Report | RLIR | 4.2.24 | Yes |
| 7Ah | Link Incident Record Registration | LIRR | 4.2.25 | Yes |
| 7Bh | Scan Remote Loop | SRL | 4.2.39 | Yes |
| 7Ch | Set Bit-error Reporting Parameters | SBRP | 4.2.40 | Yes |
| 7Dh | Report Port Speed Capabilities | RPSC | 4.2.41 | Yes |
| 7Eh | Query Security Attributes | QSA | see FC-SP | see FC-SP |
| 7Fh | Exchange Virtual Fabrics Parameters | EVFP | 4.2.43 | N/A |
| 80h | Link Keep Alive | LKA | 4.2.44 | No |
| a Some early implementations of FCP-2 may have used the value 14h for SRR (Sequence Retransmission<br>Request). This code is permanently reserved in this standard to avoid conflicts with such implementations.<br>See FCP-3 for the standard implementation of SRR as an FC-4 Link Service. |  |  |  |  |
| Encoded<br>Value<br>(Bits 15-8) | Description | Applicable ELSs |
| --- | --- | --- |
| 00h | No additional explanation | ADVC, ESTS, FLOGI, PLOGI, LOGO, RCS,<br>REC, RLS, RTV, RSI, PRLI, PRLO, TPLS,<br>TPRLO, GAID, FACT, FDACT, NACT,<br>NDACT, PDISC, FDISC, ADISC, RNC, CSR,<br>RNFT |
| 01h | Service Parm error - Options | FLOGI, PLOGI |
| 03h | Service Parm error - Initiator Ctl | FLOGI, PLOGI |
| 05h | Service Parm error - Recipient Ctl | FLOGI, PLOGI |
| 07h | Service Parm error - Rec Data Field<br>Size | FLOGI, PLOGI |
| 09h | Service Parm error - Concurrent Seq | FLOGI, PLOGI |
| 0Bh | Service Parm error - Credit | ADVC, FLOGI, PLOGI |
| 0Dh | Invalid N_Port/F_Port_Name | FLOGI, PLOGI |
| 0Eh | Invalid node/Fabric Name | FLOGI, PLOGI |
| 0Fh | Invalid Common Service Parameters | FLOGI, PLOGI |
| 11h | Invalid Association_Header | RRQ, RSI |
| 13h | Association_Header required | RRQ, RSI |
| 15h | Invalid Originator S_ID | REC, RRQ, RSI |
| 17h | Invalid OX_ID-RX_ID combination | REC, RRQ, RSI |
| 19h | Command (request) already in<br>progress | PLOGI, RSI |
| 1Eh | N_Port Login required | see table 3 |
| 1Fh | Invalid N_Port_ID | RCS, RLS |
| 21h | Obsolete |  |
| 23h | Obsolete |  |
| 25h | Obsolete |  |
| 27h | Obsolete |  |
| 29h | Insufficient resources to support Login | FLOGI, PLOGI, FDISC |
| 2Ah | Unable to supply requested data | ADVC, ESTS, RCS, RLS, RTV |
| 2Ch | Request not supported | ADVC, ESTS, PRLI, PRLO, TPLS, TPRLO,<br>GAID, FACT, FDACT, NACT, NDACT,<br>PDISC, FDISC, ADISC, RNC, RNFT |
| 2Dh | Invalid Payload length | FLOGI, PLOGI |
| 30h | No Alias_IDs available for this<br>Alias_ID Type | Get Alias_ID |
| 31h | Alias_ID not activated<br>(no resources available) | Fabric Activate Alias ID,<br>N_Port Activate Alias ID |
| 32h | Alias_ID not activated<br>(invalid Alias_ID) | Fabric Activate Alias ID,<br>N_Port Activate Alias ID |
| 33h | Alias_ID not deactivated<br>(doesn’t exist) | Fabric Deactivate Alias ID,<br>N_Port Deactivate Alias ID |
| 34h | Alias_ID not deactivated<br>(resource problem) | Fabric Deactivate Alias ID,<br>N_Port Deactivate Alias ID |
| 35h | Service Parameter conflict | N_Port Activate Alias ID |
| 36h | Invalid Alias_Token | Get Alias_ID |
| 37h | Unsupported Alias_Token | N_Port Activate Alias ID |
| 38h | Alias Group cannot be formed | Get Alias ID |
| 40h | Obsolete |  |
| 41h | Obsolete |  |
| 42h | Obsolete |  |
| 44h | Invalid Port/Node_Name | LCLM |
| 46h | Login Extension not supported | PLOGI, FLOGI |
| 48h | Authentication required (see FC-SP) | PLOGI, FLOGI |
| 50h | Periodic Scan Value not allowed | SRL |
| 51h | Periodic Scanning not supported | SRL |
| Others | Reserved |  |
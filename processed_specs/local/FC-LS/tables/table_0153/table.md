| Encoded<br>Value<br>(Bits 15-8) | Description | Applicable ELSs |
| --- | --- | --- |
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
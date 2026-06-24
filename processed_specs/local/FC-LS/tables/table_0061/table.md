| Value | Description |
| --- | --- |
| 00h | Shall be set when the requesting Nx_Port is requesting Common<br>Identification Data only (see table 61). |
| 01h – DEh | For Specific Indentification Data corresponding to a specific ULP (e.g., FC-<br>SB-3), shall be set to the FC-4 TYPE (see FC-FS-2) of that ULP. |
| DFh | Shall be used if the General Topology Discovery format (see 4.2.23.5) is to<br>be returned in the RNID Accept Payload. |
| E0h – FFh | Shall be used to indicate that Specific Node Identification Data in a vendor<br>specific format is to be returned. |
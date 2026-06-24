| Value | Description |
| --- | --- |
| 00h | The RNID Accept Payload only contains the Common Identification Data<br>(see Table 61). |
| 01h – DEh | The RNID Accept Payload may contain the Common Identification Data and<br>shall contain the Specific Identification Data for the ULP that is assigned an<br>FC-4 frame type (see FC-FS-2) equal to the value of the Node Identification<br>Data Format from the RNID Payload (see Table 58). |
| DFh | The RNID Accept Payload shall contain the Common Identification Data<br>and General Topology Discovery format Specific Identification Data. |
| E0h – FFh | The RNID Accept Payload may contain the Common Identification Data and<br>shall contain vendor specific Specific Identification Data. |
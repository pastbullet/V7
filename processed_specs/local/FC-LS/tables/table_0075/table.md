| Bits | Meaning |  |
| --- | --- | --- |
| 28 | Expansion Port:<br>When set to one, indicates that the switch port is an Inter-Switch-Link Expansion port<br>(E_Port). When zero, bit 28 indicates that the switch port is not an Inter-Switch-Link<br>Expansion port. |  |
| 27-26 | Severity Indication:<br>Bits 27-26 constitute a two-bit code that identifies the severity indication for the link<br>incident. The codes and their meanings are as follows: |  |
|  | Code | Meaning |
|  | 0 | Informational report:<br>Indicates link incident notification of an informational purpose. |
|  | 1 | Link degraded but operational:<br>Indicates if the link associated with the incident port is not in a Link-Failure or<br>Offline State as a result of the event that generated the Link Incident Record. |
|  | 2 | Link not operational:<br>Indicates if the link associated with the incident port is in a Link-Failure or<br>Offline State as a result of the event that generated the Link Incident Record. |
|  | 3 | Reserved. |
| 25 | Subassembly type:<br>When set to one, specifies that the type of subassembly used for the port that is the<br>subject of this Link Incident Record is a laser. When set to zero, specifies that the type<br>of subassembly used for the port that is the subject of this Link Incident Record is not<br>a laser. |  |
| 24 | FRU identification:<br>When set to one, specifies that the Specific-Link Incident Record Data is in a format<br>that provides field-replaceable-unit (FRU) identification. When set to zero, specifies<br>that the Specific-Link Incident Record Data is not in a format that provides field-<br>replaceable-unit (FRU) identification. |  |
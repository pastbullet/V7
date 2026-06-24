| RSCN event Qualifier | Value |  |  |  |
| --- | --- | --- | --- | --- |
|  | Bit 5 | Bit 4 | Bit 3 | Bit 2 |
| Event is not specified | 0 | 0 | 0 | 0 |
| CHANGED NAME SERVER OBJECT - An object<br>maintained by the Name Server has changed state for the<br>port, area or domain indicated by the affected Port_ID. | 0 | 0 | 0 | 1 |
| CHANGED PORT ATTRIBUTE - An internal state of the<br>port specified by the affected Port_ID has changed. The<br>change of state is identified in a protocol specific manner. | 0 | 0 | 1 | 0 |
| CHANGED SERVICE OBJECT - An object maintained by<br>the service identified by the well-known address contained<br>in affected Port_ID has changed state. This Event<br>Qualifier value shall not be used by services accessed<br>through N_Port_ID that are not well-known addresses. | 0 | 0 | 1 | 1 |
| CHANGED SWITCH CONFIGURATION - Switch<br>configuration has changed for the area or domain<br>specified by the affected Port_ID. | 0 | 1 | 0 | 0 |
| REMOVED OBJECT - The port, area or domain indicated<br>by the affected Port_ID is no longer accessible on the<br>Fabric. | 0 | 1 | 0 | 1 |
| Reserved | All Other Values |  |  |  |
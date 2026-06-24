| Value<br>(hex) | Meaning | Flag Parameter |
| --- | --- | --- |
| 00 | All the FL_Ports within the domain shall be scanned. | Ignored |
| 01 | Only the loop attached to the FL_Port addressed in the address<br>identifier of the FL_Port field shall be scanned. | Address identifier of<br>the FL_Port |
| 02 | Enable periodic scanning for all FL_ports. | Scan perioda |
| 03 | Disable periodic scanning for all FL_ports. | Ignored |
| All Others | Reserved |  |
| a Scan period in seconds. If the scan period is set to zero the scan period is vendor specific. If the switch<br>does not support this option it shall reject the SRL ELS with a reason code of "Unable to perform command<br>request" and a reason code explanation of "Periodic Scanning not supported". If the switch does not support<br>the selected value it shall reject the SRL ELS with a reason code of "Unable to perform command request"<br>and a reason code explanation of "Periodic Scan Value not allowed". |  |  |
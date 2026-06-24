| Name | Bit Number | Value | Definition |
| --- | --- | --- | --- |
| Connect-Request<br>delivered | 31 | 0 | The specified Nx_Port is either not Connected, or<br>is involved in an Established Connection based<br>on the setting of the Connection established bit. |
|  |  | 1 | A connect-Request has been delivered to the<br>specified Nx_Port, but the Nx_Port has not yet<br>responded with a proper response frame and a<br>dedicated connection does not yet exist. |
| Connect-Request stacked | 30 | 0 | No connect-Request is stacked for the specified<br>Nx_Port on behalf of the requesting Nx_Port. |
|  |  | 1 | One or more connect-Requests are stacked, but<br>have not been delivered to the specified Nx_Port<br>on behalf of the requesting Nx_Port |
| Connection established | 29 | 0 | The specified Nx_Port in the RCS Request is not<br>in a dedicated connection |
|  |  | 1 | The specified Nx_Port is involved in a dedicated<br>connection. The address identifier in bits 23-0<br>identifies the other Nx_Port involved in the<br>dedicated connection. |
| Intermix mode | 28 | 0 | The N_Port specified in the RCS frame is not<br>functioning in Intermix mode. |
|  |  | 1 | The N_Port specified in the request is functioning<br>in Intermix mode. An N_Port is functioning in<br>Intermix mode if both the N_Port and the F_Port<br>have both previously indicated that each supports<br>Intermix during Login. |
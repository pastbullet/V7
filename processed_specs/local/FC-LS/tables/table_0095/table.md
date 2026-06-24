| ELS command | Responding<br>Port Status | Responding<br>Nx_Port | Responding F_Port<br>Controller |  |
| --- | --- | --- | --- | --- |
|  |  | Class 1, 2, or 3 | Class 1, or 2 | Class 3 |
| FDISC | Logged in | LS_RJTc | LS_ACC | LS_ACC |
|  | Not Logged in | LS_RJTc | F_RJTb | Discard |
| PDISC | Logged in | LS_ACC | LS_RJTc | Discard |
|  | Not Logged in | LS_RJTa | F_RJTb | Discard |
| ADISC | Logged in | LS_ACC | LS_RJTc | Discard |
|  | Not Logged in | LS_RJTa | F_RJTb | Discard |
| a A LOGO ELS sequence or an LS_RJT ELS Sequence with the reason code set to "Unable<br>to perform command request" and the reason code explanation set to "N_Port Login<br>required" shall be returned.<br>b An F_RJT with the Reject reason code set to "Login required" shall be returned.<br>c A LOGO ELS Sequence or an LS_RJT ELS Sequence with the reason code set<br>to"Command not supported" and the reason code explanation set to "Request<br>notsupported" shall be returned. |  |  |  |  |
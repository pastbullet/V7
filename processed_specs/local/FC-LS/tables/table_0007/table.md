| N_Port Login<br>Required? (see<br>table 3) | Logged in with Source N_Port? |  |
| --- | --- | --- |
|  | Yes | No |
| Yes | Respond as appropriate for the ELS<br>and the current state of the Nx_Port | If a reply sequence is defined for the<br>ELS, originate a LOGO ELS Exchange<br>to the sender of the received ELS or<br>reply with an LS_RJT ELS Sequence<br>with a reason code of "Unable to<br>perform command request" and a<br>reason code explanation of "N_Port<br>Login required".<br>If a reply sequence is not defined for the<br>ELS, it shall be discarded |
| No | Respond as appropriate for the ELS<br>and the current state of the Nx_Port. | Respond as appropriate for the ELS<br>and the current state of the Nx_Port. |
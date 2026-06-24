| Service Parameter | Word | Bits | Default<br>Login<br>Value | PLOGI and<br>PLOGI<br>LS_ACC<br>Parameter<br>applicability |  |  | FLOGI<br>Parameter<br>applicability |  |  | FLOGI<br>LS_ACC<br>Parameter<br>applicability |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  | Class |  |  | Class |  |  | Class |  |  |
|  |  |  |  | 1a | 2 | 3 | 1a | 2 | 3 | 1a | 2 | 3 |
| N_Port/F_Port | 1 | 28 | 0 or 1e | y | y | y | y | y | y | y | y | y |
| BB_Credit Management | 1 | 27 | 0 or 1f | y | y | y | y | y | y | n | n | n |
| E_D_TOV Resolution | 1 | 26 | 0 | yb | yb | yb | n | n | n | y | y | y |
| Multicast supported by Fabric | 1 | 25 | 0 | n | n | n | n | n | n | y | y | y |
| Broadcast supported by Fabric | 1 | 24 | 0 | n | n | n | n | n | n | y | y | y |
| Hunt Group routing supported<br>by Fabric | 1 | 23 | 0 | n | n | n | n | n | n | y | y | y |
| Query Data Buffer conditions | 1 | 22 | 0 | y | y | y | y | y | y | y | y | y |
| Security bit (see FC-SP) | 1 | 21 | 0 | -c | -c | -c | -c | -c | -c | -c | -c | -c |
| Clock Synchronization Primitive<br>Capable | 1 | 20 | 0 | y | y | y | y | y | y | y | y | y |
| R_T_TOV Value | 1 | 19 | 0 | y | y | y | y | y | y | y | y | y |
| Dynamic Half Duplex<br>Supported | 1 | 18 | 0 | y | y | y | y | y | y | y | y | y |
| SEQ_CNT | 1 | 17 | 0 | y | y | y | n | n | n | n | n | n |
| Payload Bit | 1 | 16 | 0 | y | y | y | y | y | y | y | y | y |
| Legend:<br>"y" indicates yes, applicable (i.e., has meaning);<br>"n" indicates no, not applicable (i.e., has no meaning) |  |  |  |  |  |  |  |  |  |  |  |  |
| a The Class 1 Service Parameters shall be used for Class 6. Each has the same applicability as Class 1.<br>b E_D_TOV resolution and the corresponding value are only meaningful in a point-to-point topology or when<br>doing PLOGI with an NL_Port on the same loop.<br>c The Common Service Parameter applicability is specified in FC-SP.<br>d Default buffer-to-buffer credit = 1 for all ports but an L_Port, and Buffer-to-buffer credit=0 for an L_Port.<br>e N_Port/F_Port=0 for an N_Port, and N_Port/F_Port=1 for an F_Port.<br>f BB_Credit Management=0 for an N_Port or F_Port, BB_Credit_Management=1 for an L_Port |  |  |  |  |  |  |  |  |  |  |  |  |
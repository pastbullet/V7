| Service Parameter | Word | Bits | Default<br>Login<br>Value | PLOGI and<br>PLOGI<br>LS_ACC<br>Parameter<br>applicability |  |  | FLOGI<br>Parameter<br>applicability |  |  | FLOGI<br>LS_ACC<br>Parameter<br>applicability |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  | Class |  |  | Class |  |  | Class |  |  |
|  |  |  |  | 1a | 2 | 3 | 1a | 2 | 3 | 1a | 2 | 3 |
| Priority/Preemption | 0 | 23 | 0 | y | y | y | y | y | y | y | y | y |
| Preference | 0 | 22 | 0 | n | y | y | n | y | y | n | y | y |
| DiffServ QoS | 0 | 21 | 0 | n | y | y | n | y | y | n | y | y |
| Reserved | 0 | 20-16 | 0 | n | n | n | n | n | n | n | n | n |
| Initiator Control | 0 | 15-0 |  |  |  |  |  |  |  |  |  |  |
| X_ID Reassignment - obsolete | 0 | 15-14 | 0 | n | n | n | n | n | n | n | n | n |
| Initial Responder<br>Process_Associator | 0 | 13-12 | 0 | y | y | y | n | n | n | n | n | n |
| ACK_0 capable | 0 | 11 | 0 | y | y | n | n | n | n | n | n | n |
| ACK_N Capable - obsolete | 0 | 10 | 0 | n | n | n | n | n | n | n | n | n |
| ACK generation assistance | 0 | 9 | 0 | y | y | n | n | n | n | n | n | n |
| Data compression capable -<br>obsolete | 0 | 8 | 0 | n | n | n | n | n | n | n | n | n |
| Data compression history buffer<br>size - obsolete | 0 | 7-6 | 0 | n | n | n | n | n | n | n | n | n |
| Data Encryption Capable -<br>obsolete | 0 | 5 | 0 | n | n | n | n | n | n | n | n | n |
| Clock Synchronization ELS<br>capable | 0 | 4 | 0 | y | y | y | y | y | y | y | y | y |
| Reserved | 0 | 3-0 | 0 | n | n | n | n | n | n | n | n | n |
| Recipient Control | 1 | 31-16 |  |  |  |  |  |  |  |  |  |  |
| ACK_0 Capable | 1 | 31 | 0 | y | y | n | n | n | n | n | n | n |
| ACK_N Capable - obsolete | 1 | 30 | 0 | n | n | n | n | n | n | n | n | n |
| X_ID interlock | 1 | 29 | 1 | y | y | n | n | n | n | n | n | n |
| Error policy support | 1 | 28-27 | 0 | y | y | y | n | n | n | n | n | n |
| Reserved | 1 | 26 | 0 | n | n | n | n | n | n | n | n | n |
| Legend:<br>"y" indicates yes, applicable (i.e., has meaning);<br>"n" indicates no, not applicable (i.e., has no meaning) |  |  |  |  |  |  |  |  |  |  |  |  |
| a The Class 1 Service Parameters shall be used for Class 6. Each has the same applicability as Class 1. |  |  |  |  |  |  |  |  |  |  |  |  |
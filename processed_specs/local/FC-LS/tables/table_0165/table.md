| Service Parameter | Word | Bits | Default<br>Login<br>Value | PLOGI and<br>PLOGI<br>LS_ACC<br>Parameter<br>applicability |  |  | FLOGI<br>Parameter<br>applicability |  |  | FLOGI<br>LS_ACC<br>Parameter<br>applicability |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  | Class |  |  | Class |  |  | Class |  |  |
|  |  |  |  | 1a | 2 | 3 | 1a | 2 | 3 | 1a | 2 | 3 |
| Class Validity | 0 | 31 | 0 | y | y | y | y | y | y | y | y | y |
| Service Options | 0 | 30-16 |  |  |  |  |  |  |  |  |  |  |
| Intermix Mode | 0 | 30 | 0 | y | n | n | y | n | n | y | n | n |
| Stacked Connect-Requests | 0 | 29-28 | 0 | n | n | n | n | n | n | y | n | n |
| Sequential delivery | 0 | 27 | 0 | n | n | n | n | y | y | n | y | y |
| Simplex dedicated connection -<br>obsolete | 0 | 26 | 0 | n | n | n | n | n | n | n | n | n |
| Camp-On - obsolete | 0 | 25 | 0 | n | n | n | n | n | n | n | n | n |
| Buffered Class 1 - obsolete | 0 | 24 | 0 | n | n | n | n | n | n | n | n | n |
| Legend:<br>"y" indicates yes, applicable (i.e., has meaning);<br>"n" indicates no, not applicable (i.e., has no meaning) |  |  |  |  |  |  |  |  |  |  |  |  |
| a The Class 1 Service Parameters shall be used for Class 6. Each has the same applicability as Class 1. |  |  |  |  |  |  |  |  |  |  |  |  |
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
|  |  |  |  | Class |  |  | Class |  |  | Class |  |  |
|  |  |  |  | 1a | 2 | 3 | 1a | 2 | 3 | 1a | 2 | 3 |
| Categories per Sequence | 1 | 25-24 | 1 | y | y | y | n | n | n | n | n | n |
| Data compression capable -<br>obsolete | 1 | 23 | 0 | n | n | n | n | n | n | n | n | n |
| Data compression history buffer<br>size - obsolete | 1 | 22-21 | 0 | n | n | n | n | n | n | n | n | n |
| Data decryption capable –<br>obsolete | 1 | 20 | 0 | n | n | n | n | n | n | n | n | n |
| Clock Synchronization ELS<br>capable | 1 | 19 | 0 | y | y | y | y | y | y | y | y | y |
| Reserved | 1 | 18-16 | 0 | n | n | n | n | n | n | n | n | n |
| Reserved | 1 | 15-12 | 0 | n | n | n | n | n | n | n | n | n |
| Receive Data Field Size | 1 | 11-0 | 128 | y | y | y | n | n | n | n | n | n |
| Reserved | 2 | 31-24 | 0 | n | n | n | n | n | n | n | n | n |
| Concurrent Sequences | 2 | 23-16 | 1 | y | y | y | n | n | n | n | n | n |
| Nx_Port end-to-end Credit | 2 | 15-0 | 1 | y | y | n | n | n | n | n | n | n |
| Reserved | 3 | 31-24 | 0 | n | n | n | n | n | n | n | n | n |
| Open Sequences per Exchange | 3 | 23-16 | 1 | y | y | y | n | n | n | n | n | n |
| Reserved | 3 | 15-0 | 0 | n | n | n | n | n | n | n | n | n |
| CR_TOV | 3 | 31-0 | 0 | n | n | n | n | n | n | y | n | n |
| Legend:<br>"y" indicates yes, applicable (i.e., has meaning);<br>"n" indicates no, not applicable (i.e., has no meaning) |  |  |  |  |  |  |  |  |  |  |  |  |
| a The Class 1 Service Parameters shall be used for Class 6. Each has the same applicability as Class 1. |  |  |  |  |  |  |  |  |  |  |  |  |
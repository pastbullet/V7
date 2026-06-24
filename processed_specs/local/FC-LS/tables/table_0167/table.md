| Service Parameter | Word | Bits | Default<br>Login<br>Value | PLOGI and<br>PLOGI<br>LS_ACC<br>Parameter<br>applicability |  |  | FLOGI<br>Parameter<br>applicability |  |  | FLOGI<br>LS_ACC<br>Parameter<br>applicability |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
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
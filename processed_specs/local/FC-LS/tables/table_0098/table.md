| Bits<br>Word | 31 .. 24 | 23 .. 16 | 15 .. 08 | 07 .. 00 |
| --- | --- | --- | --- | --- |
| 0 | 02h | Obsolete (10h)a | Payload Length |  |
| 1 | Logout Parameter page<br>(4 words) |  |  |  |
| .. |  |  |  |  |
| n |  |  |  |  |
| a This field is obsolete, but shall be set to 10h for compatibility. |  |  |  |  |
| 0 | CSR (68h) | 00h | 00h | 00h |
| 1 | Clock Sync Mode | CS_Accuracy | CS_Implemented_M<br>SB | CS_Implemented_L<br>SB |
| 3 | CS_Update_Period |  |  |  |
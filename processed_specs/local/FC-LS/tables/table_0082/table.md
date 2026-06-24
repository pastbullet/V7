| Bits<br>Word | 31 .. 24 | 23 .. 16 | 15 .. 08 | 07 .. 00 |
| --- | --- | --- | --- | --- |
| 0 | GAID (30h) | 00h | 00h | 00h |
| 1 | MSB Alias_Token<br>(12 bytes)<br>LSB |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |
| 4 | Alias_SP<br>(80 bytes) |  |  |  |
| .. |  |  |  |  |
| 23 |  |  |  |  |
| 24 | NP_List_Length<br>(Number of NP_List entries = n) |  |  |  |
| 25 | NP_List (1) |  |  |  |
| .. | .. |  |  |  |
| 24 + n | NP_List (n) |  |  |  |
| 0 | Reserved | N_Port_ID |  |  |
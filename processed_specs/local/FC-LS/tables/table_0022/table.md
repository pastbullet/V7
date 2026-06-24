| Bits<br>Word | 31 .. 24 | 23 .. 16 | 15 .. 08 | 07 .. 00 |
| --- | --- | --- | --- | --- |
| 0 | RTV (0Eh) | 00h | 00h | 00h |
| 0 | 02h | 00h | 00h | 00h |
| 1 | Resource_Allocation_Timeout Value (R_A_TOV) (see FC-FS-2) |  |  |  |
| 2 | Error_Detect_Timeout Value (E_D_TOV) (see FC-FS-2) |  |  |  |
| 3 | Timeout Qualifier |  |  |  |
| 0 | RRQ (12h) | 00h | 00h | 00h |
| 1 | Reserved | Exchange Originator S_ID |  |  |
| 2 | OX_ID |  | RX_ID |  |
| 3 | MSB Association_Header (optional)<br>(32 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 10 |  |  |  |  |
| 0 | 02h | 00h | 00h | 00h |
| 0 | RSI (0Ah) | 00h | 00h | 00h |
| 1 | Reserved | Originator S_ID |  |  |
| 2 | OX_ID |  | RX_ID |  |
| 3 | MSB Association_Header (optional)<br>(32 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 10 |  |  |  |  |
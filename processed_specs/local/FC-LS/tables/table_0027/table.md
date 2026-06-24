| Bits<br>Word | 31 .. 24 | 23 .. 16 | 15 .. 08 | 07 .. 00 |
| --- | --- | --- | --- | --- |
| 0 | 02h | 00h | 00h | 00h |
| 0 | TEST (11h) | 00h | 00h | 00h |
| 1 | MSB TEST data<br>(up to max Data Field size,<br>any byte boundary)<br>LSB |  |  |  |
| .. |  |  |  |  |
| n |  |  |  |  |
| 0 | FAN (60h) | 00h | 00h | 00h |
| 1 | Reserved | Loop Fabric Address |  |  |
| 2 | MSB F_Port_Name<br>(8 bytes) LSB |  |  |  |
| 3 |  |  |  |  |
| 4 | MSB Fabric_Name<br>(8 bytes) LSB |  |  |  |
| 5 |  |  |  |  |
| 0 | LINIT (70h) | 00h | 00h | 00h |
| 1 | Reserved | Initialization Function | LIP byte 3 | LIP byte 4 |
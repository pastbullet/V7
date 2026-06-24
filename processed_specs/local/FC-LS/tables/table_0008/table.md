| Bits<br>Word | 31 .. 24 | 23 .. 16 | 15 .. 08 | 07 .. 00 |
| --- | --- | --- | --- | --- |
| 0 | ADVC (0Dh) | 00h | 00h | 00h |
| 1 | MSB Common Service Parameters<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 4 |  |  |  |  |
| 5 | MSB N_Port_Name<br>(8 bytes)<br>LSB |  |  |  |
| 6 |  |  |  |  |
| 7 | MSB Node_Name<br>(8 bytes)<br>LSB |  |  |  |
| 8 |  |  |  |  |
| 9 | MSB Class 1 Service Parameters<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 12 |  |  |  |  |
| 13 | MSB Class 2 Service Parameters<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 16 |  |  |  |  |
| 17 | MSB Class 3 Service Parameters<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 20 |  |  |  |  |
| 21 | MSB Reserved<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 24 |  |  |  |  |
| 25 | MSB Vendor Version Level<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 28 |  |  |  |  |
| 0 | 02h | 00h | 00h | 00h |
| 1 | MSB Common Service Parameters<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 4 |  |  |  |  |
| 5 | MSB N_Port_Name<br>(8 bytes)<br>LSB |  |  |  |
| 6 |  |  |  |  |
| 7 | MSB Node_Name<br>(8 bytes)<br>LSB |  |  |  |
| 8 |  |  |  |  |
| 9 | MSB Class 1 Service Parameters<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 12 |  |  |  |  |
| 13 | MSB Class 2 Service Parameters<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 16 |  |  |  |  |
| 17 | MSB Class 3 Service Parameters<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 20 |  |  |  |  |
| 21 | MSB Reserved<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 24 |  |  |  |  |
| 25 | MSB Vendor Version Level<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 28 |  |  |  |  |
| 0 | ECHO (10h) | 00h | 00h | 00h |
| 1 | MSB ECHO data<br>(up to max frame length - 4, any byte<br>boundary)<br>LSB |  |  |  |
| .. |  |  |  |  |
| n |  |  |  |  |
| 0 | 02h | 00h | 00h | 00h |
| 1 | MSB ECHO data<br>(up to max frame length - 4,<br>any byte boundary)<br>Excludes word 0 of ECHO Payload. LSB |  |  |  |
| .. |  |  |  |  |
| n |  |  |  |  |
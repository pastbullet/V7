| Bits<br>Word | 31 .. 24 | 23 .. 16 | 15 .. 08 | 07 .. 00 |
| --- | --- | --- | --- | --- |
| 0 | ELS_Command code |  |  |  |
| 1 | MSB<br>Common Service Parameters<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 4 |  |  |  |  |
| 5 | MSB<br>Port_Name<br>LSB |  |  |  |
| 6 |  |  |  |  |
| 7 | MSB<br>Node_ or Fabric_Name<br>LSB |  |  |  |
| 8 |  |  |  |  |
| 9 | MSB<br>Class 1 and Class 6 Service Parameters<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 12 |  |  |  |  |
| 13 | MSB<br>Class 2 Service Parameters<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 16 |  |  |  |  |
| 17 | MSB<br>Class 3 Service Parameters<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 20 |  |  |  |  |
| 21 | Obsolete |  |  |  |
| .. |  |  |  |  |
| 24 |  |  |  |  |
| 25 | MSB<br>Vendor Version Level<br>(16 bytes)<br>LSB |  |  |  |
| .. |  |  |  |  |
| 28 |  |  |  |  |
| 29 | MSB Services Availabilitya<br>(8 bytes) LSB |  |  |  |
| 30 |  |  |  |  |
| 31 | Login Extension Data Lengtha |  |  |  |
| 32 | Reserved |  |  |  |
| .. |  |  |  |  |
| 61 |  |  |  |  |
| 62 | Clock Synchronization QoSa<br>(8 bytes) |  |  |  |
| 63 |  |  |  |  |
| 64 to n | Login Extension Data (if any) |  |  |  |
| a These fields are only present when the Payload Bit (see 6.6.2.4.19) is set to one. When the Payload bit is<br>set to zero, these fields are not present in the Payload (i.e., the Payload is 116 bytes long). |  |  |  |  |
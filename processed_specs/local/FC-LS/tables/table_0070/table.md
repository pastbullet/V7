| Bits<br>Word | 31 .. 24 | 23 .. 16 | 15 .. 08 | 07 .. 00 |
| --- | --- | --- | --- | --- |
| 0 | RLIR (79h) | 00h | 00h | 00h |
| 1 | Link Incident Record<br>Format | Common Link<br>Incident Record<br>Length | Common<br>Link Incident-<br>Descriptor Length | Specific Link Incident<br>Record Length |
| 2 | MSB Common Link Incident Record<br>(m) (m=4 or 16)<br>LSB |  |  |  |
| .. |  |  |  |  |
| m+1 |  |  |  |  |
| m+2 | Common Link Incident Descriptor<br>IQ IC EPAI (domain/area of ISL) |  |  |  |
| m+3 | Specific Link Incident Record<br>(0-max bytes) |  |  |  |
| .. |  |  |  |  |
| n |  |  |  |  |
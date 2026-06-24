| Bits<br>Word | 31 .. 24 | 23 .. 16 | 15 .. 08 | 07 .. 00 |
| --- | --- | --- | --- | --- |
| 0 | Descriptor #1 = Tagging Administrative Status (see 4.2.43.2.2)a |  |  |  |
| 1 |  |  |  |  |
| 2 | Descriptor #2 = Port VF_ID (see 4.2.43.2.3)b |  |  |  |
| 3 |  |  |  |  |
| 4 | Descriptor #3 = Locally-Enabled VF_ID List (see 4.2.43.2.4)c |  |  |  |
| .. |  |  |  |  |
| 132 |  |  |  |  |
| ... | ... |  |  |  |
| H |  |  |  |  |
| ... | Descriptor #m |  |  |  |
| K |  |  |  |  |
| a Decriptor #1 is required to be present in EVFP_SYNC request.<br>b Decriptor #2 is required to be present in EVFP_SYNC request.<br>c Decriptor #3 is required to be present in EVFP_SYNC request. |  |  |  |  |
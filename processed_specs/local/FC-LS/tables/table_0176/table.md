| Preference<br>Functional | Sequential<br>delivery<br>Functional | Meaning |
| --- | --- | --- |
| 0 | 0 | Frames may be delivered in any order |
| 0 | 1 | Frames shall be delivered to a destination in the same order received<br>from the source, PREF is ignored |
| 1 | 0 | Frames may be delivered in any order, but frames with PREF set to<br>one may be delivered prior to frames with PREF set to zero |
| 1 | 1 | Frames with PREF set to one shall be delivered to a destination in the<br>same order received from the source relative to each other, and may<br>be delivered prior to frames with PREF set to zero; frames with PREF<br>set to zero shall also be delivered to a destination in the same order<br>received from the source relative to each other |
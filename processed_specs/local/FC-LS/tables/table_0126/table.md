| Value | Description |
| --- | --- |
| 01h | Critical. Abort the EVFP transaction if the descriptor is unsupported.a |
| 02h | Non critical. Skip the descriptor if unsupported and continue the EVFP<br>transaction.a |
| all others | Reserved |
| a The Descriptor Control provides extensibility to the protocol. An implementation supporting a subset<br>of the descriptors is able to process the unknown ones as specified by the Descriptor Control value. |  |
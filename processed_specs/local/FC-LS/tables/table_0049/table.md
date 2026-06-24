| Encoded Value<br>Word 0, Bits 11-8 | Description |
| --- | --- |
| 0000b | Reserved |
| 0001b | Request executed |
| 0010b | The Exchange recipient has no resources available for establishing image<br>pairs between the specified source and destination Nx_Ports. The PRLI<br>Request may be retried. |
| 0011b | Initialization is not complete for the Exchange recipient. The PRLI Request<br>may be retried. |
| 0100b | The Exchange recipient corresponding to the Responder<br>Process_Associator specified in the PRLI Request and PRLI LS_ACC<br>response does not exist. The PRLI Request shall not be retried. |
| 0101b | The Exchange recipient has a predefined configuration that precludes<br>establishing this image pair. The PRLI Request shall not be retried. |
| 0110b | Request executed conditionally. Some Service Parameters were not able to<br>be set to their requested state (see table 43) |
| 0111b | Obsolete |
| 1000b | Service Parameters are invalid |
| 1001b to 1111b | Reserved |
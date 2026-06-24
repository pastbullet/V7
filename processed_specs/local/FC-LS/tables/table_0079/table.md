| value | Function |
| --- | --- |
| 00h | Reserved |
| 01h | Set registration – conditionally receive:<br>The source port is registered as a valid recipient of subsequent RLIR ELSs for the<br>format specified. The port is added to the appropriate format specific established<br>registration list. This source port is chosen as the recipient of a link incident<br>record only if no other recipients from this established registration list have been<br>chosen. |
| 02h | Set registration – always receive:<br>The source port is registered as a valid recipient of subsequent RLIR ELSs for the<br>format specified. The port is added to the appropriate format specific established<br>registration list. This source port is always chosen as a recipient of a link incident<br>record. |
| 03h - FEh | Reserved |
| FFh | Clear registration:<br>The source port is de-registered as a valid recipient of subsequent RLIR ELSs for<br>the format specified (i.e., remove from the established registration list). |
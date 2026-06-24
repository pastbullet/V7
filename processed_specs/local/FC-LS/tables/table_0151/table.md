| Encoded Value<br>(Bits 23-16) | Description | Explanation |
| --- | --- | --- |
| 01h | Invalid ELS_Command code | The ELS_Command code in the Sequence<br>being rejected is invalid. |
| 03h | Logical error | The request identified by the ELS_Command<br>code and Payload content is invalid or<br>logically inconsistent for the conditions<br>present. |
| 05h | Logical busy | The Link Service is logically busy and unable<br>to process the request at this time. |
| 07h | Protocol error | This indicates that an error has been detected<br>that violates the rules of the ELS Protocol that<br>are not specified by other error codes. |
| 09h | Unable to perform command<br>request | The Recipient of a Link Service command is<br>unable to perform the request at this time. |
| 0Bh | Command not supported | The Recipient of a Link Service command<br>does not support the command requested. |
| 0Eh | Command already in progress |  |
| FFh | Vendor specific error (See bits 7-0) | The Vendor specific error bits may be used by<br>Vendors to specify additional reason codes. |
| Others | Reserved |  |
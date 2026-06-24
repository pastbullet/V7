| Value<br>(Bits 31-24) | Description | Abbr. | Reference | N_Port<br>Login<br>Required |
| --- | --- | --- | --- | --- |
| 90h | Authentication ELS | AUTH_ELS | see FC-SP | see FC-SP |
| 97h | Request Fabric Change Notification | RFCN | see FC-SP | see FC-SP |
| A0h | Define FFI Domain Topology Map | FFI_DTM | 4.2.45 | Yes |
| A1h | Request FFI Domain Topology Map | FFI_RTM | 4.2.46 | Yes |
| A2h | FFI AE Principal Switch Selector | FFI_PSS | 4.2.47 | Yes |
| A3h | FFI Map Update Registration | FFI_MUR | 4.2.48 | Yes |
| A4h | FFI Registered Map Update Notification | FFI_RMUN | 4.2.49 | Yes |
| A5h | FFI Suspend Map Updates | FFI_SMU | 4.2.50 | Yes |
| A6h | FFI Resume Map Updates | FFI_RMU | 4.2.51 | Yes |
| Others | Reserved |  |  |  |
| a Some early implementations of FCP-2 may have used the value 14h for SRR (Sequence Retransmission<br>Request). This code is permanently reserved in this standard to avoid conflicts with such implementations.<br>See FCP-3 for the standard implementation of SRR as an FC-4 Link Service. |  |  |  |  |
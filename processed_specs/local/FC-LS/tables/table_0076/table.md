| Value | Meaning |
| --- | --- |
| 00h | Reserved. |
| 01h | Implicit incident:<br>A condition, caused by an event known to have occurred within the incident port, has<br>been recognized by the incident port. The condition affects the attached link in such a<br>way that it may cause a link incident to be recognized by the connected port. |
| 02h | Bit-error-rate threshold exceeded:<br>The incident port has detected that the Error Interval Count equals the Error Threshold<br>(see FC-FS-2). |
| 03h | Link Failure - Loss-of-Signal or synchronization:<br>The incident port has recognized a Loss-of-Synchronization condition, and it persisted<br>for more than the R_T_TOV timeout period (see FC-FS-2). |
| 04h | Link Failure - NOS recognized:<br>The NOS has been recognized by the incident port (see FC-FS-2) |
| 05h | Link Failure - Primitive Sequence timeout:<br>The incident port has recognized either a Link-Reset-Protocol timeout (see FC-FS-2),<br>or a timeout when timing for the appropriate response while in the LF1 State and after<br>NOS is no longer recognized (see FC-FS-2). |
| 06h | Link Failure - Invalid Primitive Sequence for port state:<br>The incident port recognized either a LR or LRR Primitive Sequence while in the OL3<br>State (see FC-FS-2). |
| 07h | Link Failure - Loop Initialization time out:<br>The incident port failed to complete loop initialization within the normal loop time out<br>period (see FC-AL-2). |
| 08h | Link Failure – receiving LIP(F8):<br>The incident port is receiving LIP(F8) indicating some other port on the loop is<br>experiencing a Loss-of-Signal condition. |
| 09h - FFh | Reserved. |
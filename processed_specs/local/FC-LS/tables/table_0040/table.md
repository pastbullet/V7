| Format | Value |
| --- | --- |
| Port Address - Bytes 1, 2, and 3 of the affected Port_ID are valid, and indicate a single<br>Nx_Port or service with a well-known address. | 0 |
| Area Address Group - Bytes 1 and 2 of the affected Port_ID are valid, and indicates a<br>group of addresses that encompass an Area of E_Port or Nx_Port addresses. Byte 3<br>shall be zero. Any links and ports within the area may be affected. | 1 |
| Domain Address Group - Byte 1 of the affected Port_ID is valid, and indicates a group of<br>addresses that encompass a Domain. Bytes 2 and 3 shall be zero. Any links and ports<br>within the domain may be affected. | 2 |
| Fabric Address Group - This format indicates a group of addresses that encompass the<br>entire Fabric of Nx_Port addresses. Bytes 1, 2 and 3 shall be zero. Any links and ports<br>within the area may be affected. | 3 |
# Peer-to-Peer Network Communication and File Sharing

## Project description

A lightweight peer-to-peer application in Python. Each running instance can accept incoming TCP connections and connect directly to another peer. Connected peers exchange text messages and ordinary binary files without a central server.

## Requirements

- Python 3.9 or later
- Tkinter (included with most standard Python installations)
- No third-party Python packages

## Installation and setup

Download or extract the project folder. If Python does not include Tkinter on your system, install the Tkinter package provided by your operating system.

## Run the application

From the project folder, run:

```text
python main.py
```

Enter a peer name and an available listening port, then select **Start Peer**.

## Connect two peers

Start each application instance with a different port. In the peer that will initiate the connection, enter the other computer's IP address and listening port in **Connect to Another Peer**, then select **Connect**. For two instances on the same computer, use `127.0.0.1` as the remote IP. Select a peer in **Connected Peers** to send it messages or files.

For testing multiple peers on the same computer, use a different listening port for each instance. For peers on the same Wi-Fi/LAN, use the host computer's local IP address and listening port instead of `127.0.0.1`.

## Send messages and transfer files

Select a connected peer, type any message in **Send Text**, and select **Send**. To transfer a file, select **Choose File & Send** and choose the file. Files are transferred as binary data in chunks and saved in the receiver's `downloads/` folder. Existing files with the same name are saved with a numbered suffix.

The application supports ordinary binary files, including text, image, audio, video, PDF, ZIP, and other files.

## Testing and demonstration

The project is intended to be demonstrated progressively:

1. Start Peer A with a peer name and listening port.
2. Start Peer B with a different listening port.
3. Connect Peer B directly to Peer A using IP address and port.
4. Show the **Connected Peers** list.
5. Send text from A to B.
6. Send text from B to A.
7. Transfer an image from A to B.
8. Transfer an audio file from B to A.
9. Transfer a video file from A to B.
10. Start Peer C on another port.
11. Connect Peer C to the P2P network.
12. Demonstrate communication between multiple peer pairs.

The assignment also supports testing with two application instances on the same computer and testing between two computers connected to the same Wi-Fi/LAN.

## Screenshots

The repository includes demonstration screenshots in the `screenshots/` directory. They document the application's interface and demonstrated peer communication/file-sharing workflow.

### Demonstration screenshots

| Screenshot | |
|---|---|
| [Screenshot (3)](screenshots/Screenshot%20(3).png) | [Open image](screenshots/Screenshot%20(3).png) |
| [Screenshot (4)](screenshots/Screenshot%20(4).png) | [Open image](screenshots/Screenshot%20(4).png) |
| [Screenshot (7)](screenshots/Screenshot%20(7).png) | [Open image](screenshots/Screenshot%20(7).png) |
| [Screenshot (8)](screenshots/Screenshot%20(8).png) | [Open image](screenshots/Screenshot%20(8).png) |
| [Screenshot (9)](screenshots/Screenshot%20(9).png) | [Open image](screenshots/Screenshot%20(9).png) |
| [Screenshot (10)](screenshots/Screenshot%20(10).png) | [Open image](screenshots/Screenshot%20(10).png) |
| [Screenshot (11)](screenshots/Screenshot%20(11).png) | [Open image](screenshots/Screenshot%20(11).png) |
| [Screenshot (12)](screenshots/Screenshot%20(12).png) | [Open image](screenshots/Screenshot%20(12).png) |
| [Screenshot (13)](screenshots/Screenshot%20(13).png) | [Open image](screenshots/Screenshot%20(13).png) |

## Project structure

```text
P2P/
├── main.py
├── p2p_node.py
├── protocol.py
├── requirements.txt
├── README.md
├── screenshots/
└── downloads/
```

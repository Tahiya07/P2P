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

## Send messages and transfer files

Select a connected peer, type a message in **Send Text**, and select **Send**. To transfer a file, select **Choose File & Send** and choose the file. Files are transferred as binary data in chunks and saved in the receiver's `downloads/` folder. Existing files with the same name are saved with a numbered suffix.

## Example screenshots

When demonstrating the application, capture screenshots showing the peer startup, connected peer list, exchanged messages, and received files. The interface displays these items in the **My Peer**, **Connected Peers**, and **Messages / Events** sections.

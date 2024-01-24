# dispatchPi
## A communicating e-paper picture frame, powered by a Raspberry Pi Zero

<img src="https://i.imgur.com/E302Bw2.jpg|width=100px" width="200">

**[Follow the complete tutorial here!](https://malcolmosh.github.io/pages/DispatchPi/dispatchpi_part0/)**

The e-ink frame displays an image pulled from a fixed URL at regular intervals. At this URL resides a Flask app hosted on Google Cloud Run. Whenever it is pinged, it pulls the latest image received in a Gmail inbox and overlays text extracted from that same message. 

There are two folders to browse here:

- **Screen** contains the code found on the Raspberry Pi device
- **Server** holds the code hosted online in a dockerized Flask app 

**Diagram**

<img src="https://malcolmosh.github.io/assets/frame_diagram.png" width=800px>

